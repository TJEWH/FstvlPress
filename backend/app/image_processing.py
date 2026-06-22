"""
Image processing utilities for uploaded images.
Creates original + configurable responsive variants.
"""

from __future__ import annotations

import io
import math
from dataclasses import dataclass
from lxml import etree
from PIL import Image


@dataclass
class ImageVariants:
    """Container for processed image variants."""

    original: bytes
    responsive: dict[str, bytes]
    responsive_dimensions: dict[str, tuple[int, int]]
    content_type: str
    width: int
    height: int


@dataclass
class SvgProcessResult:
    """Container for processed SVG payload and dimensions."""

    data: bytes
    width: int | None
    height: int | None


def _get_output_format(content_type: str) -> tuple[str, str]:
    """Map content type to PIL format and file extension."""
    mapping = {
        "image/jpeg": ("JPEG", "jpg"),
        "image/jpg": ("JPEG", "jpg"),
        "image/png": ("PNG", "png"),
        "image/webp": ("WEBP", "webp"),
    }
    return mapping.get(content_type, ("JPEG", "jpg"))


def _trim_transparent_padding(img: Image.Image) -> Image.Image:
    """Trim transparent borders from an image if it has an alpha channel."""
    working = img
    if working.mode == "P":
        working = working.convert("RGBA")

    if "A" not in working.getbands():
        return working.copy()

    alpha = working.getchannel("A")
    bbox = alpha.getbbox()
    if not bbox:
        return working.copy()
    return working.crop(bbox)


def _resize_max_dimension(img: Image.Image, max_dim: int) -> Image.Image:
    """Resize image so longest side is at most max_dim, preserving aspect ratio."""
    width, height = img.size
    if width <= max_dim and height <= max_dim:
        return img.copy()

    if width > height:
        new_width = max_dim
        new_height = int(height * (max_dim / width))
    else:
        new_height = max_dim
        new_width = int(width * (max_dim / height))

    return img.resize((new_width, new_height), Image.Resampling.LANCZOS)


def _resize_max_width(img: Image.Image, max_width: int) -> Image.Image:
    """Resize image so width is at most max_width, preserving aspect ratio."""
    width, height = img.size
    target_width = max(1, int(max_width))
    if width <= target_width:
        return img.copy()
    new_height = max(1, int(height * (target_width / width)))
    return img.resize((target_width, new_height), Image.Resampling.LANCZOS)


def _to_bytes(img: Image.Image, fmt: str, content_type: str) -> bytes:
    """Convert PIL Image to bytes."""
    buffer = io.BytesIO()

    # Handle RGBA images for JPEG (which doesn't support alpha)
    if fmt == "JPEG" and img.mode in ("RGBA", "LA", "P"):
        # Convert to RGB, using white background for transparency
        background = Image.new("RGB", img.size, (255, 255, 255))
        if img.mode == "P":
            img = img.convert("RGBA")
        background.paste(img, mask=img.split()[-1] if img.mode == "RGBA" else None)
        img = background

    save_kwargs = {}
    if fmt == "JPEG":
        save_kwargs["quality"] = 85
        save_kwargs["optimize"] = True
    elif fmt == "PNG":
        save_kwargs["optimize"] = True
    elif fmt == "WEBP":
        save_kwargs["quality"] = 85

    img.save(buffer, format=fmt, **save_kwargs)
    return buffer.getvalue()


def process_image(
    data: bytes,
    content_type: str,
    responsive_widths: dict[str, int] | None = None,
    max_original_dim: int = 2000,
    trim_transparent_padding: bool = True,
) -> ImageVariants:
    """
    Process an uploaded image into original + responsive variants.

    Args:
        data: Raw image bytes
        content_type: MIME type of the image
        responsive_widths: map of variant_id => max width
        max_original_dim: max dimension for the stored original
        trim_transparent_padding: trim alpha-only borders for PNG uploads
    """
    img = Image.open(io.BytesIO(data))
    if content_type == "image/png" and trim_transparent_padding:
        img = _trim_transparent_padding(img)

    fmt, _ = _get_output_format(content_type)

    original_img = _resize_max_dimension(img, max(256, int(max_original_dim or 2000)))
    original_bytes = _to_bytes(original_img, fmt, content_type)
    width, height = original_img.size

    responsive: dict[str, bytes] = {}
    responsive_dimensions: dict[str, tuple[int, int]] = {}
    safe_responsive_widths = responsive_widths if isinstance(responsive_widths, dict) else {}
    for variant_id, raw_width in safe_responsive_widths.items():
        key = str(variant_id or "").strip().lower()
        if not key:
            continue
        try:
            target_width = max(64, int(raw_width))
        except Exception:
            continue
        variant_img = _resize_max_width(original_img, target_width)
        responsive[key] = _to_bytes(variant_img, fmt, content_type)
        responsive_dimensions[key] = variant_img.size

    return ImageVariants(
        original=original_bytes,
        responsive=responsive,
        responsive_dimensions=responsive_dimensions,
        content_type=content_type,
        width=width,
        height=height,
    )


def _parse_svg_content_bbox(data: bytes) -> tuple[float, float, float, float] | None:
    """Return min_x, min_y, width, height for all renderable SVG elements."""
    try:
        from svgelements import SVG
    except Exception:
        return None

    try:
        svg = SVG.parse(data.decode("utf-8", errors="replace"))
    except Exception:
        return None
    min_x = math.inf
    min_y = math.inf
    max_x = -math.inf
    max_y = -math.inf

    try:
        elements = svg.elements()
    except Exception:
        return None

    for element in elements:
        try:
            bbox = element.bbox()
        except Exception:
            continue

        if not bbox or len(bbox) != 4:
            continue
        x1, y1, x2, y2 = bbox
        if (
            x1 is None
            or y1 is None
            or x2 is None
            or y2 is None
            or not math.isfinite(x1)
            or not math.isfinite(y1)
            or not math.isfinite(x2)
            or not math.isfinite(y2)
            or x2 <= x1
            or y2 <= y1
        ):
            continue

        min_x = min(min_x, x1)
        min_y = min(min_y, y1)
        max_x = max(max_x, x2)
        max_y = max(max_y, y2)

    if not math.isfinite(min_x) or not math.isfinite(min_y):
        return None
    return (min_x, min_y, max_x - min_x, max_y - min_y)


def _format_svg_number(value: float) -> str:
    """Format SVG numbers with reasonable precision and no trailing zeros."""
    return f"{value:.6f}".rstrip("0").rstrip(".")


def _svg_dimension_to_int(value: float) -> int | None:
    if not math.isfinite(value) or value <= 0:
        return None
    return max(1, int(round(value)))


def process_svg(data: bytes) -> SvgProcessResult:
    """
    Trim implicit SVG padding by fitting viewBox and dimensions to content bounds.

    If bounds cannot be determined or parsing fails, returns the original SVG
    payload unchanged.
    """
    try:
        bbox = _parse_svg_content_bbox(data)
    except Exception:
        return SvgProcessResult(data=data, width=None, height=None)
    if not bbox:
        return SvgProcessResult(data=data, width=None, height=None)

    min_x, min_y, width, height = bbox
    parser = etree.XMLParser(
        remove_blank_text=False,
        recover=True,
        resolve_entities=False,
        no_network=True,
    )
    try:
        root = etree.fromstring(data, parser=parser)
    except Exception:
        return SvgProcessResult(data=data, width=None, height=None)

    try:
        tag_name = etree.QName(root.tag).localname.lower()
    except Exception:
        return SvgProcessResult(data=data, width=None, height=None)
    if tag_name != "svg":
        return SvgProcessResult(data=data, width=None, height=None)

    root.set(
        "viewBox",
        " ".join(
            (
                _format_svg_number(min_x),
                _format_svg_number(min_y),
                _format_svg_number(width),
                _format_svg_number(height),
            )
        ),
    )
    root.set("width", _format_svg_number(width))
    root.set("height", _format_svg_number(height))

    try:
        out = etree.tostring(
            root,
            encoding="utf-8",
            xml_declaration=data.lstrip().startswith(b"<?xml"),
        )
    except Exception:
        return SvgProcessResult(data=data, width=None, height=None)
    return SvgProcessResult(
        data=out,
        width=_svg_dimension_to_int(width),
        height=_svg_dimension_to_int(height),
    )


def is_image(content_type: str) -> bool:
    """Check if content type is a supported image format."""
    return content_type in (
        "image/jpeg",
        "image/jpg",
        "image/png",
        "image/webp",
        "image/gif",
    )
