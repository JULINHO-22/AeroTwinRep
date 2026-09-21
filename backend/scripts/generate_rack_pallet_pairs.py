"""Create printable paired QR labels for the AeroTwin physical rack demo."""

from io import BytesIO
from pathlib import Path

import qrcode
from reportlab.lib.colors import HexColor, black, white
from reportlab.lib.pagesizes import A4
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen.canvas import Canvas


ROOT = Path(__file__).resolve().parents[2]
# Keep the printable demo artifact alongside the other hand-off artifacts.
# QR payloads below remain intentionally limited to LOC:/PAL: identifiers.
OUTPUT = ROOT / "artifacts" / "demo-labels" / "aerotwin-demo-rack-pallet-pairs.pdf"
PAGE_WIDTH, PAGE_HEIGHT = A4
PAIRS = (
    ("A-01-01", "PAL-001"), ("A-01-02", "PAL-002"), ("A-01-03", "PAL-003"),
    ("A-02-01", "PAL-004"), ("A-02-02", None), ("A-02-03", "PAL-005"),
    ("B-01-01", "PAL-006"), ("B-01-02", "PAL-007"), ("B-01-03", "PAL-008"),
    ("B-02-01", "PAL-009"), ("B-02-02", None), ("B-02-03", "PAL-010"),
)
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
SCENARIOS = (
    ("A-01-01", "PAL-001", "Esperado: PAL-001"),
    ("A-01-02", "PAL-008", "Esperado: PAL-002 - DEMO: PAL-008"),
    ("A-02-02", "PAL-011", "Esperado: VACIO - pallet no esperado"),
    ("B-01-01", "PAL-006", "ReScan: primer intento de baja calidad; luego PAL-006"),
)


def qr_image(payload: str) -> ImageReader:
    code = qrcode.QRCode(error_correction=qrcode.constants.ERROR_CORRECT_M, box_size=16, border=6)
    code.add_data(payload)
    code.make(fit=True)
    buffer = BytesIO()
    code.make_image(fill_color="black", back_color="white").convert("RGB").save(buffer, format="PNG")
    buffer.seek(0)
    return ImageReader(buffer)


def location_payload(location: str) -> str:
    """The Core-resolved location payload; keep product metadata out of QR."""

    return f"LOC:{location}"


def pallet_payload(pallet: str) -> str:
    """The Core-resolved pallet payload; product data remains human-readable."""

    return f"PAL:{pallet}"


def header(canvas: Canvas, title: str, subtitle: str) -> None:
    canvas.setFillColor(HexColor("#1E5EC8"))
    canvas.rect(0, PAGE_HEIGHT - 76, PAGE_WIDTH, 76, stroke=0, fill=1)
    canvas.setFillColor(white)
    canvas.setFont("Helvetica-Bold", 19)
    canvas.drawString(42, PAGE_HEIGHT - 38, "AEROTWIN - RACK DEMO")
    canvas.setFont("Helvetica", 10)
    canvas.drawRightString(PAGE_WIDTH - 42, PAGE_HEIGHT - 38, subtitle)
    canvas.setFillColor(HexColor("#17212B"))
    canvas.setFont("Helvetica-Bold", 20)
    canvas.drawString(42, PAGE_HEIGHT - 110, title)


def _draw_product(canvas: Canvas, x: float, y: float, product: str | None) -> None:
    if not product:
        return
    words = product.split()
    lines: list[str] = []
    current = ""
    for word in words:
        candidate = f"{current} {word}".strip()
        if current and canvas.stringWidth(candidate, "Helvetica", 8.5) > 210:
            lines.append(current)
            current = word
        else:
            current = candidate
    if current:
        lines.append(current)
    canvas.setFillColor(HexColor("#52606D"))
    canvas.setFont("Helvetica", 8.5)
    for index, line in enumerate(lines[:2]):
        canvas.drawCentredString(x + 122.5, y - index * 11, line)


def draw_qr_block(canvas: Canvas, x: float, y: float, heading: str, payload: str, code: str, product: str | None = None) -> None:
    canvas.setFillColor(HexColor("#F4F7FB"))
    canvas.roundRect(x, y, 245, 300, 8, stroke=0, fill=1)
    canvas.setFillColor(HexColor("#52606D"))
    canvas.setFont("Helvetica-Bold", 10)
    canvas.drawCentredString(x + 122.5, y + 274, heading)
    canvas.drawImage(qr_image(payload), x + 36, y + 72, width=173, height=173, preserveAspectRatio=True, mask="auto")
    canvas.setFillColor(black)
    canvas.setFont("Helvetica-Bold", 17)
    canvas.drawCentredString(x + 122.5, y + 48, code)
    _draw_product(canvas, x, y + 28, product)


def draw_pair_page(canvas: Canvas, location: str, pallet: str | None) -> None:
    header(canvas, f"Zona {location[0]} - Posicion {location[2:4]}", "PAREJA DE PRUEBA")
    draw_qr_block(canvas, 38, 335, "UBICACION", location_payload(location), location)
    if pallet:
        draw_qr_block(canvas, 312, 335, "PALLET ESPERADO", pallet_payload(pallet), pallet, PALLET_PRODUCTS.get(pallet))
    else:
        canvas.setFillColor(HexColor("#FFF7E6"))
        canvas.roundRect(312, 335, 245, 300, 8, stroke=0, fill=1)
        canvas.setFillColor(HexColor("#8A5A00"))
        canvas.setFont("Helvetica-Bold", 17)
        canvas.drawCentredString(434.5, 505, "POSICIÓN")
        canvas.drawCentredString(434.5, 480, "ESPERADA VACÍA")
        canvas.setFont("Helvetica", 11)
        canvas.drawCentredString(434.5, 445, "No hay QR de pallet para esta ubicacion.")
    canvas.setStrokeColor(HexColor("#D7DEE8"))
    canvas.line(42, 300, PAGE_WIDTH - 42, 300)
    canvas.setFillColor(HexColor("#52606D"))
    canvas.setFont("Helvetica", 11)
    canvas.drawCentredString(PAGE_WIDTH / 2, 268, "Imprime al 100% - conserva el margen blanco alrededor de cada QR.")
    canvas.setFont("Helvetica", 8.5)
    canvas.drawCentredString(PAGE_WIDTH / 2, 247, "Productos de referencia pública. SKU, lote, pallet y cantidades son datos WMS sintéticos.")
    canvas.showPage()


def draw_scenario_page(canvas: Canvas, location: str, pallet: str, note: str) -> None:
    header(canvas, "Escenario de prueba", "LECTURA CONTROLADA")
    canvas.setFillColor(HexColor("#17212B"))
    canvas.setFont("Helvetica-Bold", 18)
    canvas.drawCentredString(PAGE_WIDTH / 2, 650, location)
    draw_qr_block(canvas, 38, 300, "UBICACION", location_payload(location), location)
    draw_qr_block(canvas, 312, 300, "PALLET A PRESENTAR", pallet_payload(pallet), pallet, PALLET_PRODUCTS.get(pallet))
    canvas.setFillColor(HexColor("#E9F1FF"))
    canvas.roundRect(42, 210, PAGE_WIDTH - 84, 60, 8, stroke=0, fill=1)
    canvas.setFillColor(HexColor("#17212B"))
    canvas.setFont("Helvetica-Bold", 13)
    canvas.drawCentredString(PAGE_WIDTH / 2, 242, note)
    canvas.showPage()


def main() -> None:
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    canvas = Canvas(str(OUTPUT), pagesize=A4, pageCompression=1)
    canvas.setTitle("AeroTwin - Rack pallet pairs")
    for location, pallet in PAIRS:
        draw_pair_page(canvas, location, pallet)
    for location, pallet, note in SCENARIOS:
        draw_scenario_page(canvas, location, pallet, note)
    canvas.save()
    print(OUTPUT)


if __name__ == "__main__":
    main()
