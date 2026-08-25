import re
from decimal import Decimal, InvalidOperation
from io import BytesIO

import pytesseract
from PIL import Image, ImageFilter, ImageOps
from pytesseract import TesseractError, TesseractNotFoundError

from app.core.exceptions import AppError
from app.schemas.product import ProductOcrFields, ProductOcrResult

FIELD_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    (
        "color_code",
        re.compile(
            r"^(?:rang|renk|color|colour|цвет)\s*(?:kodi|kodu|code|код)\s*[:#-]?\s*(.+)$",
            re.I,
        ),
    ),
    (
        "minimum_stock",
        re.compile(
            r"^(?:minimum|min\.?)(?:\s+(?:miqdor|miktar|stock|stok|qty))?\s*[:#-]?\s*(.+)$",
            re.I,
        ),
    ),
    (
        "initial_stock",
        re.compile(
            r"^(?:miqdor|miktar|quantity|qty|net\s*(?:weight|ağırlık)|og['’]?irlik|вазн|вес)\s*[:#-]?\s*(.+)$",
            re.I,
        ),
    ),
    (
        "lot_number",
        re.compile(
            r"^(?:lot\s*(?:no|number|raqami|numarası)|lot|parti|партия)\s*[:#-]?\s*(.+)$",
            re.I,
        ),
    ),
    (
        "brand",
        re.compile(r"^(?:marka|brand|brend|марка|бренд)\s*[:#-]?\s*(.+)$", re.I),
    ),
    (
        "color",
        re.compile(r"^(?:rang|renk|color|colour|цвет)\s*[:#-]?\s*(.+)$", re.I),
    ),
    (
        "description",
        re.compile(r"^(?:description|açıklama|tavsif|описание)\s*[:#-]?\s*(.+)$", re.I),
    ),
    (
        "name",
        re.compile(
            r"^(?:product\s*name|product|ürün\s*adı|ürün|mahsulot\s*nomi|mahsulot|наименование|продукт)\s*[:#-]?\s*(.+)$",
            re.I,
        ),
    ),
)


def _decimal_from_text(value: str) -> Decimal | None:
    match = re.search(r"-?\d+(?:[.,]\d{1,3})?", value.replace(" ", ""))
    if not match:
        return None
    try:
        number = Decimal(match.group(0).replace(",", "."))
    except InvalidOperation:
        return None
    return number if number >= 0 else None


def parse_product_text(raw_text: str, *, average_confidence: float = 0.75) -> ProductOcrResult:
    values: dict[str, str | Decimal] = {}
    confidence: dict[str, float] = {}
    lines = [re.sub(r"\s+", " ", line).strip() for line in raw_text.splitlines() if line.strip()]
    for line in lines:
        for field, pattern in FIELD_PATTERNS:
            match = pattern.match(line)
            if not match or field in values:
                continue
            value = match.group(1).strip(" :-")
            if field in {"initial_stock", "minimum_stock"}:
                numeric = _decimal_from_text(value)
                if numeric is None:
                    continue
                values[field] = numeric
            elif field == "color_code":
                color_match = re.search(r"#[0-9A-Fa-f]{6}", value)
                if not color_match:
                    continue
                values[field] = color_match.group(0).upper()
            elif value:
                values[field] = value[: 5000 if field == "description" else 180]
            confidence[field] = round(max(0.0, min(1.0, average_confidence)), 2)
            break

    if "name" not in values:
        fallback = next(
            (
                line
                for line in lines
                if 2 <= len(line.split()) <= 10
                and not any(pattern.match(line) for _, pattern in FIELD_PATTERNS)
            ),
            None,
        )
        if fallback:
            values["name"] = fallback[:180]
            confidence["name"] = round(max(0.25, average_confidence * 0.55), 2)

    warnings = []
    if not raw_text.strip():
        warnings.append("No readable text was detected")
    if len(values) < 3:
        warnings.append(
            "Few fields were detected; review the image and fill missing values manually"
        )
    return ProductOcrResult(
        raw_text=raw_text[:10_000],
        fields=ProductOcrFields(**values),
        confidence=confidence,
        warnings=warnings,
    )


def _text_from_tesseract_data(data: dict[str, list[object]]) -> str:
    lines: list[str] = []
    current_key: tuple[object, object, object, object] | None = None
    current_words: list[str] = []
    texts = data.get("text", [])
    for index, raw_word in enumerate(texts):
        word = str(raw_word).strip()
        key = tuple(
            data.get(field, [None] * len(texts))[index]
            for field in ("page_num", "block_num", "par_num", "line_num")
        )
        if current_key is not None and key != current_key and current_words:
            lines.append(" ".join(current_words))
            current_words = []
        current_key = key
        if word:
            current_words.append(word)
    if current_words:
        lines.append(" ".join(current_words))
    return "\n".join(lines)


def extract_product_fields(
    content: bytes, *, languages: str, timeout_seconds: int
) -> ProductOcrResult:
    try:
        with Image.open(BytesIO(content)) as source:
            image = ImageOps.exif_transpose(source).convert("L")
            image = ImageOps.autocontrast(image)
            if image.width < 1600:
                scale = min(3, max(1, 1600 // max(1, image.width)))
                image = image.resize(
                    (image.width * scale, image.height * scale), Image.Resampling.LANCZOS
                )
            image = image.filter(ImageFilter.SHARPEN)
            data = pytesseract.image_to_data(
                image,
                lang=languages,
                config="--oem 1 --psm 6",
                output_type=pytesseract.Output.DICT,
                timeout=timeout_seconds,
            )
            raw_text = _text_from_tesseract_data(data)
    except (TesseractNotFoundError, TesseractError, RuntimeError) as exc:
        raise AppError("OCR_UNAVAILABLE", "OCR service is currently unavailable", 503) from exc
    except (OSError, ValueError) as exc:
        raise AppError("INVALID_IMAGE", "Uploaded file is not a valid image", 422) from exc

    confidences = []
    for value in data.get("conf", []):
        try:
            numeric = float(value)
        except (TypeError, ValueError):
            continue
        if numeric >= 0:
            confidences.append(numeric / 100)
    average = sum(confidences) / len(confidences) if confidences else 0.5
    return parse_product_text(raw_text, average_confidence=average)
