"""Local deterministic operational tools. All tools are read-only except audit logging."""
from __future__ import annotations
import re, time
from datetime import date, timedelta
from sqlalchemy import func, select
from sqlalchemy.orm import Session
from app.models.enums import ExceptionStatus, ExceptionType, InspectionStatus, ReadingStatus
from app.models.inspection import EvidenceFile, Inspection, InspectionReading
from app.models.operations import AgentQueryLog, ExceptionEvent, FlowTwinChange
from app.models.warehouse import ExpectedInventory, Location, Lot, Pallet, Product, WarehouseZone
from app.services.flowtwin_service import calculate
from app.services.inspection_service import inspection_progress
from app.services.inventory_analytics import fefo_for_outbound_lot, product_coverage_from_history, product_rotation_from_history
from app.domain.settings import load_business_rule_settings
from app.services.warehouse_memory_service import (
    get_location_history,
    latest_evidence,
    location_list,
    location_memory,
    zone_memory,
)

def _params(question: str) -> dict:
    """Extract only explicit, deterministic query parameters from Spanish text."""
    q = question.upper()
    location = re.search(r"\b[A-Z]-\d{2}-\d{2}\b", q)
    zones = re.findall(r"\bZONA\s+([A-Z0-9_-]+)\b", q)
    days = re.search(r"\b(\d+)\s+D[IÍ]AS\b", q)
    limit = re.search(r"\b(?:TOP|L[ÍI]MITE|PRIMER[AO]S?)\s+(\d+)\b", q)
    return {
        "location": location.group() if location else None,
        "zones": zones,
        "days": int(days.group(1)) if days else 30,
        "limit": min(int(limit.group(1)), 10) if limit else 5,
    }

def route(question: str) -> str:
    q=question.lower()
    if any(x in q for x in ("confirma", "cierra inspección", "completa la inspección", "actualiza", "mueve pallet", "borra", "escribe en sap")): return "READ_ONLY_DENIED"
    if "evidencia" in q: return "LATEST_EVIDENCE"
    if "historial" in q or "qué ha pasado" in q: return "LOCATION_HISTORY"
    if re.search(r"\b[a-z]-\d{2}-\d{2}\b",q): return "LOCATION_STATUS"
    if "compara zona" in q: return "COMPARE_ZONES"
    if "cambi" in q: return "RECENT_CHANGES"
    if "vence" in q or "caduc" in q: return "EXPIRY"
    if "fefo" in q: return "FEFO"
    if "cobertura de zona" in q or "cobertura zona" in q: return "INSPECTION_COVERAGE"
    if "cobertura" in q or "stock bajo" in q: return "LOW_COVERAGE"
    if "no se pudo resolver" in q or "falta revisar" in q or "no inspeccion" in q: return "UNRESOLVED"
    if "repite" in q or "errores" in q or "se repite" in q: return "RECURRENT"
    if any(x in q for x in ("revis", "urgente", "prioridad")): return "PRIORITY"
    return "UNKNOWN"

def result(name, summary, data, sources, actions=None):
    return {
        "tool_name": name,
        "success": True,
        "summary": summary,
        "data": data,
        "sources": sources,
        "suggested_actions": actions or [],
    }
def loc(session, code): return session.scalar(select(Location).where(Location.code==code))


def _unique_sources(*sources: dict | None) -> list[dict]:
    """Deduplicate entity references without inventing a source entity."""
    result_sources: list[dict] = []
    seen: set[tuple[tuple[str, object], ...]] = set()
    for source in sources:
        if not source:
            continue
        key = tuple(sorted(source.items()))
        if key not in seen:
            seen.add(key)
            result_sources.append(source)
    return result_sources


def _location_status_summary(memory: dict) -> str:
    code = memory["code"]
    comparison = memory.get("last_comparison_result")
    if memory.get("is_never_inspected"):
        return f"{code} aún no tiene una lectura final de inspección."
    if memory.get("is_unresolved"):
        headline = f"{code} requiere revisión humana; la lectura final no quedó resuelta."
    elif comparison == "PALLET_MISMATCH":
        headline = f"{code} presenta una discrepancia de pallet."
    elif comparison == "EXPECTED_PALLET_MISSING":
        headline = f"{code} tiene el pallet esperado ausente."
    elif comparison == "UNEXPECTED_PALLET":
        headline = f"{code} tiene un pallet no esperado."
    elif comparison in ("CORRECT", "CORRECT_EMPTY"):
        headline = f"{code} está conforme con la última lectura final."
    else:
        headline = f"Estado operativo de {code}."

    lines = [headline]
    if memory.get("expected_pallet") is not None:
        lines.append(f"Esperado: {memory['expected_pallet']}")
    if memory.get("last_observed_pallet") is not None:
        lines.append(f"Observado: {memory['last_observed_pallet']}")
    elif memory.get("last_observed_state") == "EMPTY":
        lines.append("Observado: Vacío confirmado")
    elif memory.get("is_unresolved"):
        lines.append("Observado: No resuelto")
    if memory.get("last_risk_score"):
        severity_raw = memory.get("last_severity") or "SIN SEVERIDAD"
        severity = {
            "LOW": "BAJO",
            "MEDIUM": "MEDIO",
            "HIGH": "ALTO",
            "CRITICAL": "CRÍTICO",
        }.get(severity_raw, severity_raw)
        lines.append(f"Riesgo: {memory['last_risk_score']} · {severity}")
    breakdown = memory.get("risk_breakdown") or {}
    if breakdown:
        lines.append("Razones:")
        lines.extend(f"- {reason} +{score}" for reason, score in breakdown.items())
    streak = memory.get("consecutive_anomalous_inspections") or 0
    if streak >= 2:
        lines.append(f"Esta condición se repite en {streak} inspecciones consecutivas.")
    return "\n".join(lines)

def execute(session: Session, intent: str, p: dict) -> dict:
    if intent == "PRIORITY":
        rows = session.execute(
            select(ExceptionEvent, Location.code)
            .outerjoin(Location, ExceptionEvent.location_id == Location.id)
            .where(ExceptionEvent.status.in_((ExceptionStatus.OPEN, ExceptionStatus.IN_REVIEW)))
            .order_by(ExceptionEvent.risk_score.desc(), ExceptionEvent.severity.desc(), ExceptionEvent.created_at.desc())
            .limit(p["limit"])
        ).all()
        data = [
            {
                "exception_id": event.id,
                "location_id": event.location_id,
                "location": code,
                "risk_score": event.risk_score,
                "severity": event.severity.value,
                "title": event.title,
            }
            for event, code in rows
        ]
        return result(
            "get_top_priorities",
            "Prioridades abiertas ordenadas por riesgo.",
            data,
            [{"type": "ExceptionEvent", "id": event.id} for event, _ in rows],
            [{"type": "OPEN_EXCEPTION", "id": event.id} for event, _ in rows],
        )
    if intent in ("LOCATION_STATUS","LOCATION_HISTORY","LATEST_EVIDENCE"):
        location=loc(session,p['location']) if p['location'] else None
        if not location: return {"tool_name":"get_location_status","success":False,"summary":"No hay información suficiente para esa ubicación.","data":{},"sources":[],"suggested_actions":[]}
        memory=location_memory(session,location)
        if intent=="LATEST_EVIDENCE":
            evidence = latest_evidence(session,location)
            data = evidence or {"location": location.code, "available": False, "evidence_id": None}
            sources = _unique_sources(
                {"type":"Location","id":location.id},
                {"type":"EvidenceFile","id":evidence["evidence_id"]} if evidence else None,
                {"type":"InspectionReading","id":evidence["reading_id"]} if evidence else None,
            )
            actions = ([{"type":"OPEN_EVIDENCE","id":evidence["evidence_id"]}] if evidence else [])
            return result("get_latest_evidence", "Última evidencia disponible." if evidence else "No existe evidencia final disponible para esta ubicación.", data, sources, actions)
        if intent=="LOCATION_HISTORY":
            timeline = get_location_history(session, location)
            sources = [{"type":"Location","id":location.id}]
            for item in timeline:
                sources.extend(
                    _unique_sources(
                        {"type": "InspectionReading", "id": item["reading_id"]},
                        {"type": "ExceptionEvent", "id": item["exception_id"]} if item.get("exception_id") else None,
                        {"type": "EvidenceFile", "id": item["evidence_id"]} if item.get("evidence_id") else None,
                        {"type": "FlowTwinChange", "id": item["flowtwin_change"]["id"]} if item.get("flowtwin_change") else None,
                    )
                )
            return result("get_location_history","Historial físico basado únicamente en lecturas finales.",{"memory":memory,"timeline":timeline,"latest_evidence":memory["latest_evidence"]},_unique_sources(*sources),[{"type":"OPEN_LOCATION_HISTORY","id":location.id}])
        sources = _unique_sources(
            {"type":"Location","id":location.id},
            {"type":"InspectionReading","id":memory["last_reading_id"]} if memory.get("last_reading_id") else None,
            {"type":"ExceptionEvent","id":memory["current_exception_id"]} if memory.get("current_exception_id") else None,
            {"type":"EvidenceFile","id":memory["latest_evidence"]["evidence_id"]} if memory.get("latest_evidence") else None,
        )
        actions = [{"type":"OPEN_LOCATION_HISTORY","id":location.id}]
        if memory.get("current_exception_id"):
            actions.insert(0, {"type":"OPEN_EXCEPTION","id":memory["current_exception_id"]})
        return result("get_location_status",_location_status_summary(memory),memory,sources,actions)
    if intent=="RECURRENT":
        rows=[x for x in location_list(session) if x['consecutive_anomalous_inspections']>=2][:p['limit']]
        return result("get_recurrent_anomalies","Ubicaciones con racha recurrente.",rows,[{"type":"Location","id":x['location_id']} for x in rows])
    if intent=="UNRESOLVED":
        rows = session.execute(
            select(InspectionReading, Location.code, Inspection.completed_at)
            .join(Location, InspectionReading.location_id == Location.id)
            .join(Inspection, InspectionReading.inspection_id == Inspection.id)
            .where(
                InspectionReading.is_final.is_(True),
                InspectionReading.reading_status == ReadingStatus.HUMAN_REVIEW_REQUIRED,
            )
            .order_by(InspectionReading.created_at.desc())
        ).all()
        groups = [reading.reading_group_id for reading, _, _ in rows]
        attempt_counts = {
            group_id: count
            for group_id, count in session.execute(
                select(InspectionReading.reading_group_id, func.count())
                .where(InspectionReading.reading_group_id.in_(groups))
                .group_by(InspectionReading.reading_group_id)
            ).all()
        } if groups else {}
        final_ids = [reading.id for reading, _, _ in rows]
        evidence_by_reading = {}
        if final_ids:
            evidence_rows = session.scalars(
                select(EvidenceFile)
                .where(EvidenceFile.reading_id.in_(final_ids))
                .order_by(EvidenceFile.captured_at.desc(), EvidenceFile.id.desc())
            ).all()
            for evidence in evidence_rows:
                evidence_by_reading.setdefault(evidence.reading_id, evidence)
        data = []
        sources = []
        for reading, code, completed_at in rows:
            evidence = evidence_by_reading.get(reading.id)
            reason = (
                "Se agotaron los reintentos de calidad; requiere revisión humana."
                if reading.reading_status == ReadingStatus.HUMAN_REVIEW_REQUIRED
                else "La lectura final no pudo resolverse."
            )
            data.append({
                "location": code,
                "location_id": reading.location_id,
                "inspection_id": reading.inspection_id,
                "inspection_completed_at": completed_at,
                "reading_id": reading.id,
                "attempts": attempt_counts.get(reading.reading_group_id, reading.attempt_number),
                "quality": reading.quality_score,
                "reason": reason,
                "status": reading.reading_status.value,
                "latest_evidence": {
                    "evidence_id": evidence.id,
                    "reading_id": evidence.reading_id,
                    "captured_at": evidence.captured_at,
                    "mime_type": evidence.mime_type,
                } if evidence else None,
            })
            sources.extend(_unique_sources(
                {"type":"Location", "id": reading.location_id},
                {"type":"Inspection", "id": reading.inspection_id},
                {"type":"InspectionReading", "id": reading.id},
                {"type":"EvidenceFile", "id": evidence.id} if evidence else None,
            ))
        return result("get_unresolved_locations","Lecturas que requieren revisión humana.",data,_unique_sources(*sources),[{"type":"OPEN_LOCATION_HISTORY","id":row["location_id"]} for row in data])
    if intent=="EXPIRY":
        until=date.today()+timedelta(days=p['days']); rows=session.execute(select(Lot,Product,Pallet).join(Product).join(Pallet).where(Lot.expires_at<=until,Pallet.quantity>0).order_by(Lot.expires_at)).all()
        data=[{"product":pr.name,"sku":pr.sku,"lot":lot.lot_code,"pallet":pal.pallet_code,"expires_at":lot.expires_at,"days_remaining":(lot.expires_at-date.today()).days} for lot,pr,pal in rows]
        return result("get_expiring_lots",f"Lotes con stock que vencen en {p['days']} días.",data,[{"type":"Lot","id":x[0].id} for x in rows])
    if intent=="LOW_COVERAGE":
        settings=load_business_rule_settings(); data=[]; sources=[]
        reference_at = __import__('datetime').datetime.now(__import__('datetime').timezone.utc)
        for product in session.scalars(select(Product).where(Product.is_active.is_(True))).all():
            coverage=product_coverage_from_history(session=session,product_id=product.id,reference_at=reference_at,settings=settings)
            if coverage.status.value != 'LOW_COVERAGE':
                continue
            rotation = product_rotation_from_history(session=session, product_id=product.id, reference_at=reference_at, settings=settings)
            event = session.scalar(
                select(ExceptionEvent)
                .where(
                    ExceptionEvent.product_id == product.id,
                    ExceptionEvent.exception_type == ExceptionType.LOW_COVERAGE,
                    ExceptionEvent.status.in_((ExceptionStatus.OPEN, ExceptionStatus.IN_REVIEW)),
                )
                .order_by(ExceptionEvent.risk_score.desc(), ExceptionEvent.created_at.desc())
            )
            location = session.get(Location, event.location_id) if event and event.location_id else None
            pallet = session.get(Pallet, event.pallet_id) if event and event.pallet_id else None
            data.append({
                "product":product.name,
                "product_id":product.id,
                "sku":product.sku,
                "coverage_days":coverage.coverage_days,
                "status":coverage.status.value,
                "rotation":rotation.level.value,
                "rotation_outbound_quantity":rotation.outbound_quantity,
                "associated_risk_score":event.risk_score if event else None,
                # Short alias retained for structured Android rendering.
                "risk_score":event.risk_score if event else None,
                "exception_id":event.id if event else None,
                "location":location.code if location else None,
                "location_id":location.id if location else None,
                "pallet":pallet.pallet_code if pallet else None,
                "pallet_id":pallet.id if pallet else None,
            })
            sources.extend(_unique_sources(
                {"type":"Product", "id":product.id},
                {"type":"ExceptionEvent", "id":event.id} if event else None,
                {"type":"Location", "id":location.id} if location else None,
                {"type":"Pallet", "id":pallet.id} if pallet else None,
            ))
        data.sort(key=lambda row: row['coverage_days'] if row['coverage_days'] is not None else float('inf'))
        return result("get_low_coverage_items","Productos con cobertura baja.",data,_unique_sources(*sources),[{"type":"OPEN_EXCEPTION", "id":row["exception_id"]} for row in data if row["exception_id"]])
    if intent=="FEFO":
        data=[]
        for lot in session.scalars(select(Lot)).all():
            value=fefo_for_outbound_lot(session=session,outbound_lot_id=lot.id)
            if value.risk:data.append({"lot":lot.lot_code,"preferred_lot":value.preferred_lot,"reason":value.reason})
        return result("get_fefo_risks","Riesgos FEFO calculados por Core.",data,[{"type":"Lot","lot":x['lot']} for x in data])
    if intent=="COMPARE_ZONES":
        zones=[session.scalar(select(WarehouseZone).where(WarehouseZone.code==z)) for z in p['zones'][:2]]
        data=[zone_memory(session,z) for z in zones if z]
        return result("compare_zones","Comparación operativa entre zonas.",data,[{"type":"WarehouseZone","id":x['zone_id']} for x in data])
    if intent=="RECENT_CHANGES":
        current=session.scalar(select(Inspection).where(Inspection.status==InspectionStatus.COMPLETED).order_by(Inspection.completed_at.desc(), Inspection.id.desc()))
        if not current:return {"tool_name":"get_recent_changes","success":False,"summary":"No hay información suficiente.","data":{},"sources":[],"suggested_actions":[]}
        previous,changes,_=calculate(session,current)
        if previous is None:
            return result("get_recent_changes", "No existe una inspección comparable anterior.", [], [{"type":"Inspection","id":current.id}], [{"type":"OPEN_FLOWTWIN"}])
        persisted = {
            (row.location_id, row.change_type.value): row
            for row in session.scalars(
                select(FlowTwinChange).where(
                    FlowTwinChange.current_inspection_id == current.id,
                    FlowTwinChange.previous_inspection_id == previous.id,
                )
            ).all()
        }
        pallet_ids = {pallet_id for change in changes for pallet_id in (change.previous.observed_pallet_id, change.current.observed_pallet_id) if pallet_id}
        pallets = {row.id: row.pallet_code for row in session.scalars(select(Pallet).where(Pallet.id.in_(pallet_ids))).all()} if pallet_ids else {}
        data=[]; sources=[]
        for change in changes:
            stored = persisted.get((change.location_id, change.type.value))
            data.append({
                "location_id":change.location_id,
                "type":change.type.value,
                "previous":pallets.get(change.previous.observed_pallet_id),
                "current":pallets.get(change.current.observed_pallet_id),
                "previous_reading_id":change.previous.id,
                "current_reading_id":change.current.id,
                "flowtwin_change_id":stored.id if stored else None,
            })
            # A calculated but not persisted change is supported by the two
            # actual readings, never by an invented FlowTwinChange entity.
            sources.extend(_unique_sources(
                {"type":"FlowTwinChange", "id":stored.id} if stored else None,
                {"type":"InspectionReading", "id":change.previous.id} if not stored else None,
                {"type":"InspectionReading", "id":change.current.id} if not stored else None,
            ))
        return result("get_recent_changes","Cambios respecto a la última inspección comparable.",data,_unique_sources(*sources),[{"type":"OPEN_FLOWTWIN"}])
    if intent=="INSPECTION_COVERAGE":
        zone_code = p['zones'][0] if p['zones'] else None
        zone = session.scalar(select(WarehouseZone).where(WarehouseZone.code == zone_code)) if zone_code else None
        if zone_code and zone is None:
            return {"tool_name":"get_inspection_coverage","success":False,"summary":f"No existe la Zona {zone_code}.","data":{},"sources":[],"suggested_actions":[]}
        query = select(Inspection).where(Inspection.status==InspectionStatus.IN_PROGRESS)
        if zone is not None:
            query = query.where(Inspection.zone_id == zone.id)
        inspection=session.scalar(query.order_by(Inspection.started_at.desc(), Inspection.id.desc()))
        if not inspection:
            label = f" en Zona {zone_code}" if zone_code else ""
            return {"tool_name":"get_inspection_coverage","success":False,"summary":f"No hay una inspección activa{label} para calcular cobertura.","data":{},"sources":[],"suggested_actions":[]}
        progress=inspection_progress(session=session,inspection=inspection)
        progress["inspection_id"] = progress["id"]
        progress["pending"]=progress["total_locations"]-progress["completed_locations"]
        return result("get_inspection_coverage","Cobertura de la inspección activa.",progress,[{"type":"Inspection","id":inspection.id}])
    return {"tool_name":None,"success":False,"summary":"No identifiqué una consulta operativa segura para esa pregunta.","data":{},"sources":[],"suggested_actions":[]}

def query(session: Session,user_id:int,question:str)->dict:
    started=time.perf_counter(); intent=route(question); payload={"tool_name":None,"success":False,"summary":"El Agente AeroTwin actual es de consulta y explicación; no realiza acciones operativas.","data":{},"sources":[],"suggested_actions":[]} if intent=="READ_ONLY_DENIED" else execute(session,intent,_params(question)); latency=int((time.perf_counter()-started)*1000)
    session.add(AgentQueryLog(user_id=user_id,question=question,tool_called=payload['tool_name'],response=payload['summary'],fallback_used=not payload['success'],latency_ms=latency)); session.commit()
    return {"mode":"LOCAL","intent":intent,"tool":payload['tool_name'],"answer":payload['summary'],"data":payload['data'],"sources":payload['sources'],"actions":payload['suggested_actions']}
