import re
import unicodedata


def _normalize(text):
    text = unicodedata.normalize("NFD", text.lower())
    return "".join(c for c in text if unicodedata.category(c) != "Mn")


def _find_location(query, locations):
    match = re.search(r"\b([abc]\d{2})\b", query)
    if not match:
        return None
    code = match.group(1).upper()
    return next((x for x in locations if x["code"] == code), None)


def _location_answer(location, plan):
    item = next(x for x in plan if x["code"] == location["code"])
    return (
        f"### {location['code']} · {location['product']}\n\n"
        f"- WMS esperado: **{location['expected_pallet']} / {location['expected_qty']} unidades**\n"
        f"- Observado: **{location['current_pallet']} / {location['current_qty']} unidades**\n"
        f"- Estado: **{location['status']}**\n"
        f"- Confianza visual: **{location['confidence']:.0f}%**\n"
        f"- Estado del pasillo: **{location['aisle_status']}**\n"
        f"- Inspection Score: **{item['inspection_score']}/100** ({', '.join(item['inspection_reasons'])})\n"
        f"- Risk Score: **{item['risk_score']}/100** ({', '.join(item['risk_reasons'])})\n\n"
        "La información pertenece al escenario simulado y cualquier corrección debe ser validada por un operador."
    )


def answer_question(question, locations, plan, observations, tasks, inspections):
    query = _normalize(question).strip()
    location = _find_location(query, locations)
    if location:
        return _location_answer(location, plan)

    eligible = [x for x in plan if x["eligible"]]
    active = [x for x in plan if x["status"] in ("Excepción", "ReScan")]

    if any(x in query for x in ["donde inspeccionar", "inspeccionar despues", "siguiente ubicacion", "proxima mision"]):
        if not eligible:
            return "No existe una ubicación elegible. Todos los pasillos están bloqueados o requieren confirmación."
        item = eligible[0]
        return (
            f"La siguiente ubicación recomendada es **{item['code']} · {item['product']}**, "
            f"con Inspection Score **{item['inspection_score']}/100**.\n\n"
            f"**Motivos:** {', '.join(item['inspection_reasons'])}.\n\n"
            f"Sensor sugerido para el escenario: **{item['sensor']}**. El pasillo figura como **{item['aisle_status']}**."
        )

    if any(x in query for x in ["por que", "inspection score", "puntaje de inspeccion"]):
        item = eligible[0] if eligible else plan[0]
        return (
            "El **Inspection Score** organiza ubicaciones que todavía deben inspeccionarse. "
            f"Actualmente **{item['code']}** encabeza el plan con **{item['inspection_score']}/100** por: "
            f"{', '.join(item['inspection_reasons'])}. No significa que ya exista un error; significa que conviene obtener evidencia allí."
        )

    if any(x in query for x in ["riesgo", "risk score", "atender primero", "atiendo primero", "excepcion prioritaria", "que excepcion"]):
        if not active:
            return "No existen excepciones activas. El Risk Score se utilizará cuando una inspección detecte una diferencia o una lectura insuficiente."
        item = max(active, key=lambda x: x["risk_score"])
        return (
            f"La excepción que conviene atender primero es **{item['code']} · {item['product']}**, "
            f"con Risk Score **{item['risk_score']}/100**.\n\n"
            f"**Razones:** {', '.join(item['risk_reasons'])}."
        )

    if any(x in query for x in ["que cambio", "cambios", "ultima inspeccion", "observado"]):
        if not observations:
            return "Todavía no hay evidencia procesada. Ejecuta uno de los escenarios de la pestaña **Monitor de sensor**."
        latest_id = observations[0]["inspection_id"]
        latest = [x for x in observations if x["inspection_id"] == latest_id]
        relevant = [x for x in latest if x["outcome"] != "Coincidencia"]
        if not relevant:
            return f"La inspección **#{latest_id}** no registró diferencias: todas las lecturas coincidieron con el WMS simulado."
        lines = [f"En la inspección **#{latest_id}** se encontraron:"]
        lines.extend(f"- **{x['location_code']}**: {x['outcome']}. {x['message']}" for x in relevant)
        return "\n".join(lines)

    if any(x in query for x in ["tareas", "pendientes", "wms"]):
        pending = [x for x in tasks if x["status"] == "Pendiente"]
        if not pending:
            return "No existen tareas pendientes en el WMS simulado."
        lines = [f"Existen **{len(pending)} tareas pendientes**:"]
        lines.extend(f"- Tarea **#{x['id']}**, ubicación **{x['location_code']}**, prioridad **{x['priority']}**." for x in pending)
        return "\n".join(lines)

    if any(x in query for x in ["resumen", "estado general", "como esta", "inventario"]):
        verified = sum(x["status"] == "Verificado" for x in locations)
        exceptions = sum(x["status"] == "Excepción" for x in locations)
        rescans = sum(x["status"] == "ReScan" for x in locations)
        return (
            "### Resumen del escenario\n\n"
            f"- Ubicaciones: **{len(locations)}**\n"
            f"- Verificadas: **{verified}**\n"
            f"- Excepciones: **{exceptions}**\n"
            f"- ReScan pendientes: **{rescans}**\n"
            f"- Inspecciones registradas: **{len(inspections)}**\n"
            f"- Tareas WMS: **{len(tasks)}**"
        )

    return (
        "Puedo responder preguntas como:\n\n"
        "- ¿Dónde conviene inspeccionar después?\n"
        "- ¿Por qué esa ubicación tiene mayor Inspection Score?\n"
        "- ¿Qué excepción debo atender primero?\n"
        "- ¿Qué cambió en la última inspección?\n"
        "- ¿Qué ocurre en B01?\n"
        "- Dame un resumen del inventario."
    )
