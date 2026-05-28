from __future__ import annotations

from io import BytesIO
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from .game import Card


ASSET_DIR = Path(__file__).resolve().parent.parent / "assets" / "uno_regular"
COLOR_ASSET_NAMES = {
    "red": "Red",
    "yellow": "Yellow",
    "green": "Green",
    "blue": "Blue",
}
VALUE_ASSET_NAMES = {
    "skip": "Skip",
    "reverse": "Reverse",
    "draw2": "Draw_2",
    "wild": "Wild",
    "wild_draw4": "Wild_Draw_4",
}


def card_asset_path(card: Card) -> Path:
    filename = _asset_filename(card)
    exact_path = ASSET_DIR / filename
    if exact_path.exists():
        return exact_path

    # Some asset packs have inconsistent casing, e.g. RED_Reverse.jpg.
    normalized = filename.lower()
    for path in ASSET_DIR.glob("*"):
        if path.name.lower() == normalized:
            return path

    raise FileNotFoundError(f"Asset kartu tidak ditemukan: {filename}")


def render_card_image(card: Card, filename: str = "uno_card.jpg") -> tuple[BytesIO, str]:
    image = Image.open(card_asset_path(card)).convert("RGB")
    image.thumbnail((280, 400), Image.Resampling.LANCZOS)

    canvas = Image.new("RGB", (image.width + 32, image.height + 32), (22, 24, 31))
    canvas.paste(image, (16, 16))
    return _to_jpeg(canvas, filename)


def render_hand_image(
    cards: list[Card],
    playable_indices: set[int],
    page: int,
    page_size: int = 25,
    filename: str = "uno_hand.jpg",
) -> tuple[BytesIO, str]:
    start = page * page_size
    shown_cards = cards[start : start + page_size]
    if not shown_cards:
        canvas = Image.new("RGB", (640, 180), (22, 24, 31))
        draw = ImageDraw.Draw(canvas)
        draw.text((24, 70), "Tidak ada kartu di tanganmu.", fill=(245, 245, 245), font=_font(22))
        return _to_jpeg(canvas, filename)

    thumb_width = 118
    thumb_height = 168
    gap = 18
    pad = 24
    columns = min(5, len(shown_cards))
    rows = (len(shown_cards) + columns - 1) // columns
    header_height = 54
    canvas_width = pad * 2 + columns * thumb_width + (columns - 1) * gap
    canvas_height = pad * 2 + header_height + rows * thumb_height + (rows - 1) * gap
    canvas = Image.new("RGB", (canvas_width, canvas_height), (17, 19, 26))
    draw = ImageDraw.Draw(canvas)
    draw.text((pad, pad), "Kartu tanganmu", fill=(245, 245, 245), font=_font(24))
    draw.text(
        (pad, pad + 30),
        "Border hijau = bisa dimainkan",
        fill=(172, 180, 195),
        font=_font(14),
    )

    for offset, card in enumerate(shown_cards):
        global_index = start + offset
        col = offset % columns
        row = offset // columns
        x = pad + col * (thumb_width + gap)
        y = pad + header_height + row * (thumb_height + gap)
        card_image = Image.open(card_asset_path(card)).convert("RGB")
        card_image = card_image.resize((thumb_width, thumb_height), Image.Resampling.LANCZOS)

        border_color = (60, 188, 110) if global_index in playable_indices else (45, 48, 60)
        draw.rounded_rectangle(
            (x - 5, y - 5, x + thumb_width + 5, y + thumb_height + 5),
            radius=12,
            fill=border_color,
        )
        canvas.paste(card_image, (x, y))
        _draw_number_badge(draw, x, y, global_index + 1)

    return _to_jpeg(canvas, filename)


def _asset_filename(card: Card) -> str:
    if card.is_wild:
        return f"{VALUE_ASSET_NAMES[card.value]}.jpg"

    color_name = COLOR_ASSET_NAMES[card.color]
    value_name = VALUE_ASSET_NAMES.get(card.value, card.value)
    return f"{color_name}_{value_name}.jpg"


def _draw_number_badge(draw: ImageDraw.ImageDraw, x: int, y: int, number: int) -> None:
    label = str(number)
    font = _font(18)
    bbox = draw.textbbox((0, 0), label, font=font)
    width = bbox[2] - bbox[0]
    height = bbox[3] - bbox[1]
    badge_size = max(32, width + 18)
    draw.rounded_rectangle((x + 7, y + 7, x + 7 + badge_size, y + 39), radius=10, fill=(15, 17, 22))
    draw.text(
        (x + 7 + (badge_size - width) / 2, y + 13 + (18 - height) / 2),
        label,
        fill=(255, 255, 255),
        font=font,
    )


def _font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    try:
        return ImageFont.truetype("arial.ttf", size)
    except OSError:
        return ImageFont.load_default()


def _to_jpeg(image: Image.Image, filename: str) -> tuple[BytesIO, str]:
    buffer = BytesIO()
    image.save(buffer, format="JPEG", quality=88, optimize=True)
    buffer.seek(0)
    return buffer, filename
