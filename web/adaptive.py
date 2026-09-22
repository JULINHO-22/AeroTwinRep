from datetime import date, datetime

INSPECTION_WEIGHTS = {"movement": 25, "age": 20, "history": 20, "turnover": 15, "expiry": 10, "rescan": 10}


def _days_to_expiry(value):
    try:
        return (datetime.strptime(value, "%Y-%m-%d").date() - date.today()).days
    except (TypeError, ValueError):
        return 999


def inspection_score(location):
    """Prioriza dónde capturar nueva evidencia."""
    score, reasons = 0, []
    movements = int(location.get("movements_24h", 0))
    if movements >= 8:
        score += 25; reasons.append(f"{movements} movimientos recientes")
    elif movements >= 4:
        score += 15; reasons.append(f"{movements} movimientos recientes")
    hours = float(location.get("hours_since_inspection", 0))
    if hours >= 24:
        score += 20; reasons.append(f"{hours:.0f} h sin verificación")
    elif hours >= 12:
        score += 12; reasons.append(f"{hours:.0f} h sin verificación")
    anomalies = int(location.get("anomaly_count", 0))
    if anomalies >= 2:
        score += 20; reasons.append(f"{anomalies} anomalías históricas")
    elif anomalies == 1:
        score += 10; reasons.append("1 anomalía histórica")
    if location.get("turnover") == "Alta":
        score += 15; reasons.append("producto de alta rotación")
    if _days_to_expiry(location.get("expiry")) <= 30:
        score += 10; reasons.append("lote próximo a vencer")
    if int(location.get("pending_rescan", 0)):
        score += 10; reasons.append("ReScan pendiente")
    available = location.get("aisle_status", "Disponible") == "Disponible"
    if not available:
        reasons.append(f"pasillo {location.get('aisle_status', 'no disponible').lower()}")
    return min(score, 100), reasons or ["control preventivo"], available


def risk_score(location):
    """Prioriza excepciones ya observadas."""
    score, reasons = 0, []
    if location.get("expected_pallet") != location.get("current_pallet"):
        score += 35; reasons.append("pallet diferente al WMS")
    difference = abs(int(location.get("current_qty", 0)) - int(location.get("expected_qty", 0)))
    if difference:
        score += min(20, difference * 4); reasons.append(f"diferencia de {difference} unidades")
    if _days_to_expiry(location.get("expiry")) <= 30:
        score += 20; reasons.append("caducidad menor a 30 días")
    if location.get("turnover") == "Alta":
        score += 15; reasons.append("alta rotación")
    if int(location.get("anomaly_count", 0)) >= 2:
        score += 10; reasons.append("anomalías recurrentes")
    if float(location.get("confidence", 100)) < 70:
        score += 10; reasons.append("evidencia de baja confianza")
    return min(score, 100), reasons or ["sin excepción activa"]


def build_inspection_plan(locations):
    plan = []
    for location in locations:
        i_score, i_reasons, eligible = inspection_score(location)
        r_score, r_reasons = risk_score(location)
        row = dict(location)
        row.update({"inspection_score": i_score, "inspection_reasons": i_reasons, "eligible": eligible,
                    "risk_score": r_score, "risk_reasons": r_reasons,
                    "sensor": "Dron" if location.get("level") == "Alto" else "Cámara móvil"})
        plan.append(row)
    return sorted(plan, key=lambda x: (x["eligible"], x["inspection_score"]), reverse=True)


def next_mission(plan):
    return next((row for row in plan if row["eligible"]), None)
