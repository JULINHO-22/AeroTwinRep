"""Generate printable QR labels for the Sensor Mode MVP."""

from pathlib import Path

import qrcode
from PIL import Image, ImageDraw, ImageFont


ROOT = Path(__file__).resolve().parents[2]
OUTPUT = ROOT / "artifacts" / "demo-labels"
FONT_PATH = Path("C:/Windows/Fonts/arial.ttf")
LOCATIONS = ("A-01-01", "A-01-02", "A-01-03", "A-02-01", "A-02-02", "A-02-03", "B-01-01", "B-01-02", "B-01-03", "B-02-01", "B-02-02", "B-02-03")
PALLETS = tuple(f"PAL-{number:03d}" for number in range(1, 16))
PALLET_PRODUCTS = {
    "PAL-001": "NESCAFÉ Tradición",
    "PAL-002": "Galletas AMOR Wafer Chocolate 100 g",
    "PAL-003": "MAGGI Caldo de Gallina 15 unidades",
    "PAL-004": "CHOCAPIC 300 g",
    "PAL-005": "KITKAT 4 Finger Milk 41.5 g",
    "PAL-006": "NIDO FortiGrow Lata 400 g",
    "PAL-007": "TANGO Original 25 g",
    "PAL-008": "GALAK Barra MilkFirst Blanco 90 g",
    "PAL-009": "MAGGI Sopa Pollo Fideos 60 g",
    "PAL-010": "Galletas AMOR Wafer Fresa 100 g",
    "PAL-011": "TANGO Original 25 g · pallet demo no esperado",
}


def _draw_wrapped_centered(
    draw: ImageDraw.ImageDraw,
    text: str,
    *,
    y: int,
    font: ImageFont.ImageFont,
    max_width: int,
) -> None:
    """Keep long public product names readable without changing QR payloads."""

    words = text.split()
    lines: list[str] = []
    line = ""
    for word in words:
        candidate = f"{line} {word}".strip()
        if line and draw.textlength(candidate, font=font) > max_width:
            lines.append(line)
            line = word
        else:
            line = candidate
    if line:
        lines.append(line)
    for offset, line in enumerate(lines[:2]):
        draw.text((700, y + offset * 50), line, fill="black", anchor="mt", font=font)


def label(payload: str, visible_code: str, category: str, product: str | None = None) -> Image.Image:
    # A generous quiet zone and integer modules are essential for phone cameras.
    generator = qrcode.QRCode(
        error_correction=qrcode.constants.ERROR_CORRECT_M,
        box_size=24,
        border=6,
    )
    generator.add_data(payload)
    generator.make(fit=True)
    qr = generator.make_image(fill_color="black", back_color="white").convert("RGB")
    image = Image.new("RGB", (1400, 1700), "white")
    image.paste(qr, ((1400 - qr.width) // 2, 90))
    draw = ImageDraw.Draw(image)
    font = ImageFont.truetype(FONT_PATH, 100) if FONT_PATH.exists() else ImageFont.load_default(100)
    small = ImageFont.truetype(FONT_PATH, 38) if FONT_PATH.exists() else ImageFont.load_default(38)
    draw.text((700, 1215), visible_code, fill="black", anchor="mt", font=font)
    if product:
        _draw_wrapped_centered(draw, product, y=1370, font=small, max_width=1180)
    draw.text((700, 1535), category, fill="black", anchor="mt", font=small)
    draw.text((700, 1590), "Datos WMS simulados · payload QR sin producto", fill="black", anchor="mt", font=small)
    return image


def main() -> None:
    OUTPUT.mkdir(parents=True, exist_ok=True)
    labels = [(f"LOC:{code}", code, "UBICACIÓN", None) for code in LOCATIONS]
    labels += [
        (f"PAL:{code}", code, "PALLET", PALLET_PRODUCTS.get(code, "Pallet WMS demo"))
        for code in PALLETS
    ]
    pages: list[Image.Image] = []
    for index, (payload, code, category, product) in enumerate(labels, 1):
        image = label(payload, code, category, product)
        image.save(OUTPUT / f"{index:02d}-{category.lower()}-{code}.png")
        pages.append(image)
    pages[0].save(OUTPUT / "aerotwin-demo-qr-labels.pdf", save_all=True, append_images=pages[1:], resolution=150)


if __name__ == "__main__":
    main()
