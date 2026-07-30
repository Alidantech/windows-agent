from __future__ import annotations

from io import BytesIO
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from agent_os.models import UIElement

_PALETTE = {
    "button": (57, 255, 20, 255),
    "link": (255, 209, 102, 255),
    "input": (0, 229, 255, 255),
    "textarea": (0, 229, 255, 255),
    "textbox": (0, 229, 255, 255),
    "combobox": (213, 0, 249, 255),
    "select": (213, 0, 249, 255),
    "option": (255, 0, 229, 255),
    "checkbox": (255, 145, 0, 255),
    "radio": (255, 145, 0, 255),
    "default": (124, 174, 255, 255),
}


def _font(size: int) -> ImageFont.ImageFont:
    for name in ("DejaVuSans-Bold.ttf", "arialbd.ttf"):
        try:
            return ImageFont.truetype(name, size=size)
        except OSError:
            continue
    return ImageFont.load_default()


def _color(element: UIElement) -> tuple[int, int, int, int]:
    kind = (element.control_type or "").lower()
    input_type = (element.input_type or "").lower()
    return _PALETTE.get(input_type) or _PALETTE.get(kind) or _PALETTE["default"]


def render_set_of_mark(
    image: Image.Image,
    elements: list[UIElement],
    *,
    max_marks: int = 100,
) -> Image.Image:
    """Overlay speakable high-contrast marks on a model-only image copy."""

    marked = image.convert("RGBA")
    overlay = Image.new("RGBA", marked.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    font = _font(max(12, min(18, round(image.width / 110))))
    candidates = [
        item
        for item in elements
        if item.visible and item.rect.width >= 3 and item.rect.height >= 3
    ]
    candidates.sort(
        key=lambda item: (
            0 if item.focused else 1,
            0 if item.enabled else 1,
            item.rect.top,
            item.rect.left,
        )
    )
    label_boxes: list[tuple[int, int, int, int]] = []
    for element in candidates[:max_marks]:
        rect = element.rect
        left = max(0, min(image.width - 1, rect.left))
        top = max(0, min(image.height - 1, rect.top))
        right = max(left + 1, min(image.width - 1, rect.right - 1))
        bottom = max(top + 1, min(image.height - 1, rect.bottom - 1))
        color = _color(element)
        width = 4 if element.focused else 2
        draw.rectangle((left, top, right, bottom), outline=color, width=width)
        if not element.enabled:
            draw.line((left, top, right, bottom), fill=(255, 23, 68, 220), width=2)

        label = element.element_id
        bbox = draw.textbbox((0, 0), label, font=font, stroke_width=1)
        label_w = bbox[2] - bbox[0] + 8
        label_h = bbox[3] - bbox[1] + 6
        positions = (
            (left, max(0, top - label_h)),
            (left, min(image.height - label_h, top)),
            (max(0, right - label_w), max(0, top - label_h)),
        )
        label_rect = None
        for x, y in positions:
            candidate = (x, y, x + label_w, y + label_h)
            if not any(
                candidate[0] < existing[2]
                and candidate[2] > existing[0]
                and candidate[1] < existing[3]
                and candidate[3] > existing[1]
                for existing in label_boxes
            ):
                label_rect = candidate
                break
        if label_rect is None:
            x, y = positions[1]
            label_rect = (x, y, x + label_w, y + label_h)
        label_boxes.append(label_rect)
        draw.rounded_rectangle(
            label_rect,
            radius=3,
            fill=(8, 12, 18, 230),
            outline=color,
            width=1,
        )
        draw.text(
            (label_rect[0] + 4, label_rect[1] + 2),
            label,
            font=font,
            fill=(255, 255, 255, 255),
            stroke_width=1,
            stroke_fill=(0, 0, 0, 255),
        )

    return Image.alpha_composite(marked, overlay).convert("RGB")


def png_bytes(image: Image.Image) -> bytes:
    buffer = BytesIO()
    image.save(buffer, format="PNG", optimize=True)
    return buffer.getvalue()


def save_grounding_image(path: Path | None, image: Image.Image) -> Path | None:
    if path is None:
        return None
    output = path.with_name(f"{path.stem}-grounded{path.suffix}")
    output.parent.mkdir(parents=True, exist_ok=True)
    image.save(output, format="PNG", optimize=True)
    return output
