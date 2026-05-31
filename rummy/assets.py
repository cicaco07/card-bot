"""Image renderer for rummy cards, including jokers."""

from __future__ import annotations

from functools import lru_cache
from io import BytesIO
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from .cards import RummyCard


SVG_ASSET_DIR = Path(__file__).resolve().parent.parent / "assets" / "playing-cards" / "svg-cards"
PNG_ASSET_DIR = Path(__file__).resolve().parent.parent / "assets" / "playing-cards" / "png"
RANK_ASSET_NAMES = {"A": "ace", "J": "jack", "Q": "queen", "K": "king"}


def card_asset_path(card: RummyCard, fallback: bool = False) -> Path:
    directory = PNG_ASSET_DIR if fallback else SVG_ASSET_DIR
    extension = "png" if fallback else "svg"
    if card.is_joker:
        filename = f"{card.joker_color}_joker.{extension}"
    else:
        filename = f"{RANK_ASSET_NAMES.get(card.rank, card.rank)}_of_{card.suit}.{extension}"
    path = directory / filename
    if not path.exists():
        raise FileNotFoundError(f"Asset kartu rummy tidak ditemukan: {path.name}")
    return path


def render_rummy_hand_image(
    cards: list[RummyCard],
    page: int,
    selected_number: int | None = None,
    page_size: int = 25,
    filename: str = "rummy_hand.jpg",
) -> tuple[BytesIO, str]:
    start = page * page_size
    shown_cards = cards[start : start + page_size]
    if not shown_cards:
        canvas = Image.new("RGB", (640, 180), (22, 24, 31))
        ImageDraw.Draw(canvas).text((24, 70), "Tidak ada kartu di tanganmu.", fill=(245, 245, 245), font=_font(22))
        return _to_jpeg(canvas, filename)
    thumb_width, thumb_height, gap, pad, header_height = 112, 156, 14, 24, 58
    columns = min(5, len(shown_cards))
    rows = (len(shown_cards) + columns - 1) // columns
    canvas = Image.new(
        "RGB",
        (pad * 2 + columns * thumb_width + (columns - 1) * gap, pad * 2 + header_height + rows * thumb_height + (rows - 1) * gap),
        (17, 19, 26),
    )
    draw = ImageDraw.Draw(canvas)
    draw.text((pad, pad), "Kartu Rummy", fill=(245, 245, 245), font=_font(24))
    draw.text((pad, pad + 32), "Pilih kartu yang akan dibuang", fill=(172, 180, 195), font=_font(14))
    for offset, card in enumerate(shown_cards):
        number = start + offset + 1
        x = pad + (offset % columns) * (thumb_width + gap)
        y = pad + header_height + (offset // columns) * (thumb_height + gap)
        border = (236, 196, 65) if number == selected_number else (45, 48, 60)
        draw.rounded_rectangle((x - 5, y - 5, x + thumb_width + 5, y + thumb_height + 5), radius=12, fill=border)
        canvas.paste(_open_card(card, thumb_width, thumb_height), (x, y))
        _draw_number_badge(draw, x, y, number)
    return _to_jpeg(canvas, filename)


def render_discard_image(card: RummyCard, filename: str = "rummy_discard.jpg") -> tuple[BytesIO, str]:
    image = _open_card(card, 224, 312)
    canvas = Image.new("RGB", (256, 344), (22, 24, 31))
    canvas.paste(image, (16, 16))
    return _to_jpeg(canvas, filename)


def _open_card(card: RummyCard, width: int, height: int) -> Image.Image:
    return _open_card_cached(card.rank, card.suit, card.joker_color, width, height).copy()


@lru_cache(maxsize=256)
def _open_card_cached(rank: str, suit: str | None, joker_color: str | None, width: int, height: int) -> Image.Image:
    card = RummyCard(rank, suit, joker_color)
    try:
        import cairosvg
        png_bytes = cairosvg.svg2png(url=str(card_asset_path(card)), output_width=width, output_height=height)
        return _with_white_background(Image.open(BytesIO(png_bytes))).resize((width, height), Image.Resampling.LANCZOS)
    except (ModuleNotFoundError, OSError):
        return _with_white_background(Image.open(card_asset_path(card, fallback=True))).resize((width, height), Image.Resampling.LANCZOS)


def _with_white_background(image: Image.Image) -> Image.Image:
    image = image.convert("RGBA")
    background = Image.new("RGBA", image.size, (255, 255, 255, 255))
    background.alpha_composite(image)
    return background.convert("RGB")


def _draw_number_badge(draw: ImageDraw.ImageDraw, x: int, y: int, number: int) -> None:
    label = str(number)
    font = _font(17)
    bbox = draw.textbbox((0, 0), label, font=font)
    width = bbox[2] - bbox[0]
    badge_size = max(30, width + 16)
    draw.rounded_rectangle((x + 7, y + 7, x + 7 + badge_size, y + 37), radius=9, fill=(15, 17, 22))
    draw.text((x + 7 + (badge_size - width) / 2, y + 13), label, fill=(255, 255, 255), font=font)


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
