from dataclasses import dataclass
from io import BytesIO
from pathlib import Path
from uuid import uuid4

from PIL import Image, ImageOps, UnidentifiedImageError

from app.core.exceptions import AppError

_ALLOWED_SOURCE_FORMATS = {"JPEG", "PNG", "WEBP"}


@dataclass(frozen=True)
class ProcessedImage:
    content: bytes
    width: int
    height: int


def process_product_image(content: bytes, *, max_pixels: int, max_dimension: int) -> ProcessedImage:
    try:
        with Image.open(BytesIO(content)) as source:
            if (source.format or "").upper() not in _ALLOWED_SOURCE_FORMATS:
                raise AppError(
                    "INVALID_IMAGE_TYPE", "Only JPEG, PNG, and WebP images are accepted", 422
                )
            if getattr(source, "is_animated", False):
                raise AppError("INVALID_IMAGE", "Animated images are not supported", 422)
            width, height = source.size
            if width < 1 or height < 1 or width * height > max_pixels:
                raise AppError("INVALID_IMAGE", "Image dimensions are not allowed", 422)
            source.load()
            image = ImageOps.exif_transpose(source).convert("RGB")
    except (Image.DecompressionBombError, UnidentifiedImageError, OSError) as exc:
        raise AppError("INVALID_IMAGE", "Uploaded file is not a valid image", 422) from exc

    image.thumbnail((max_dimension, max_dimension), Image.Resampling.LANCZOS)
    output = BytesIO()
    image.save(output, format="WEBP", quality=88, method=6)
    return ProcessedImage(content=output.getvalue(), width=image.width, height=image.height)


def store_product_image(media_root: Path, product_id: int, image: ProcessedImage) -> str:
    directory = media_root / "products"
    directory.mkdir(mode=0o755, parents=True, exist_ok=True)
    filename = f"{product_id}-{uuid4().hex}.webp"
    target = directory / filename
    temporary = directory / f".{filename}.tmp"
    temporary.write_bytes(image.content)
    temporary.replace(target)
    return f"/media/products/{filename}"


def delete_product_image(media_root: Path, image_url: str | None) -> None:
    if not image_url or not image_url.startswith("/media/products/"):
        return
    target = media_root / "products" / Path(image_url).name
    target.unlink(missing_ok=True)
