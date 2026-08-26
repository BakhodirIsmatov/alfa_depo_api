from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ProductLabelTemplate:
    code: str
    kind: str
    width_mm: int
    height_mm: int
    title: str
    description: str
    min_module_mm: float
    quiet_zone_mm: float
    recommended: bool = False


_TEMPLATES: tuple[ProductLabelTemplate, ...] = (
    ProductLabelTemplate(
        code="barcode-30x20",
        kind="barcode",
        width_mm=30,
        height_mm=20,
        title="30 x 20 mm",
        description="Compact CODE128 layout for short thermal shelf and roll labels.",
        min_module_mm=0.33,
        quiet_zone_mm=2.0,
        recommended=True,
    ),
    ProductLabelTemplate(
        code="barcode-40x30",
        kind="barcode",
        width_mm=40,
        height_mm=30,
        title="40 x 30 mm",
        description="Wider CODE128 layout with more horizontal tolerance for scanner reliability.",
        min_module_mm=0.33,
        quiet_zone_mm=2.5,
    ),
    ProductLabelTemplate(
        code="qr-30x30",
        kind="qr",
        width_mm=30,
        height_mm=30,
        title="30 x 30 mm",
        description="Minimum square QR label that preserves a dedicated quiet zone.",
        min_module_mm=0.50,
        quiet_zone_mm=2.0,
        recommended=True,
    ),
    ProductLabelTemplate(
        code="qr-40x40",
        kind="qr",
        width_mm=40,
        height_mm=40,
        title="40 x 40 mm",
        description="Larger QR layout for easier long-term warehouse scanning.",
        min_module_mm=0.40,
        quiet_zone_mm=2.5,
    ),
)


def list_product_label_templates() -> list[ProductLabelTemplate]:
    return list(_TEMPLATES)
