from pathlib import Path

import cv2
import pandas as pd
import streamlit as st

from agent import answer_question
from adaptive import build_inspection_plan, next_mission
from database import (close_task, create_task, get_inspections, get_locations, get_observations,
                      get_tasks, init_db, register_inspection, reset_demo, set_aisle_status)
from vision import analyze_image, create_demo_images, decode_image

st.set_page_config(page_title="AeroTwin · Consola operativa", page_icon="🧭", layout="wide")
init_db(); ASSETS=Path(__file__).with_name("assets_adaptive"); create_demo_images(ASSETS)

st.markdown("""<style>
.stApp{background:linear-gradient(180deg,#f7faf9 0%,#eef5f5 42%,#fff 100%)}
.block-container{padding-top:1.2rem}.hero{padding:1.45rem 1.6rem;border-radius:20px;color:white;background:linear-gradient(120deg,#143b5d,#19746f);box-shadow:0 12px 28px #173f5f24}.hero h1{margin:0;font-size:2.2rem}.hero p{margin:.35rem 0 0;opacity:.92}.note{background:#eaf4f4;border-left:5px solid #1c8f82;padding:.8rem 1rem;border-radius:9px}.card{background:white;border:1px solid #dbe5e5;border-radius:14px;padding:.85rem;margin:.4rem 0;box-shadow:0 5px 14px #2345}.code{font-size:1.2rem;font-weight:800;color:#173f5f}.ok{border-left:7px solid #2f996b}.warn{border-left:7px solid #dfa62d}.bad{border-left:7px solid #ce4c4c}.rescan{border-left:7px solid #7a5ab5}[data-testid="stMetric"]{background:white;border:1px solid #dfe8e8;padding:.8rem;border-radius:14px}</style>""",unsafe_allow_html=True)
st.markdown("""<div class='hero'><h1>AeroTwin</h1><p>Consola operativa del inventario físico-digital: captura, verificación, gemelo digital y priorización en una sola experiencia.</p></div>""",unsafe_allow_html=True)

locations=get_locations(); plan=build_inspection_plan(locations); mission=next_mission(plan); observations=get_observations(); tasks=get_tasks(); inspections=get_inspections()
exceptions=sum(x["status"]=="Excepción" for x in locations); rescans=sum(x["status"]=="ReScan" for x in locations); verified=sum(x["status"]=="Verificado" for x in locations)

with st.sidebar:
    st.header("AeroTwin")
    st.caption("Modo Operador · prototipo académico")
    st.markdown("**Cadena operativa**\n1. Sensor captura\n2. Core valida\n3. Progreso se actualiza\n4. Gemelo refleja el estado\n5. Riesgo prioriza\n6. Persona decide")
    st.divider(); st.success("AeroTwin Core activo"); st.success("WMS simulado conectado"); st.info("La decisión final permanece en una persona")

c1,c2,c3,c4=st.columns(4); c1.metric("Ubicaciones",len(locations)); c2.metric("Verificadas",verified); c3.metric("Excepciones",exceptions); c4.metric("ReScan pendientes",rescans)

tabs=st.tabs(["🏠 Command Center","📡 Monitor de sensor","🗺️ Gemelo digital","⚠️ Excepciones","✅ Acciones WMS","🤖 Agente AeroTwin","📊 Indicadores","🕘 Auditoría"])

with tabs[0]:
    st.subheader("Estado de la inspección")
    st.markdown("<div class='note'><b>AeroTwin Core</b> combina actividad reciente, antigüedad de la evidencia, historial, rotación, caducidad y ReScan para recomendar el próximo objetivo seguro.</div>",unsafe_allow_html=True)
    if mission:
        a,b,c,d=st.columns(4); a.metric("Próximo objetivo",mission["code"]); b.metric("Prioridad de inspección",f'{mission["inspection_score"]}/100'); c.metric("Sensor sugerido",mission["sensor"]); d.metric("Acceso",mission["aisle_status"])
        st.info(f"**Motivos:** {', '.join(mission['inspection_reasons'])}.")
    coverage=round(100*verified/len(locations)) if locations else 0
    p1,p2,p3,p4=st.columns(4); p1.metric("Cobertura validada",f"{coverage}%"); p2.metric("En revisión",rescans); p3.metric("Discrepancias",exceptions); p4.metric("Tareas pendientes",sum(x["status"]=="Pendiente" for x in tasks))
    with st.expander("Ver plan adaptativo de AeroTwin Core",expanded=True):
        st.caption("La prioridad de inspección indica dónde conviene capturar evidencia; el Risk Score ordena problemas que ya fueron detectados.")
        frame=pd.DataFrame([{"Orden":i+1,"Ubicación":x["code"],"Prioridad de inspección":x["inspection_score"],"Elegible":"Sí" if x["eligible"] else "No","Acceso":x["aisle_status"],"Motivos":", ".join(x["inspection_reasons"]),"Sensor":x["sensor"]} for i,x in enumerate(plan)])
        st.dataframe(frame,width="stretch",hide_index=True)
        st.markdown("#### Contexto operativo del pasillo")
        x1,x2,x3=st.columns([1,1,1]); selected=x1.selectbox("Ubicación",[x["code"] for x in locations]); status=x2.selectbox("Estado",["Disponible","Ocupado por montacargas","Ocupado por personas","Bloqueado"])
        if x3.button("Actualizar y replanificar",width="stretch"): set_aisle_status(selected,status); st.rerun()

with tabs[1]:
    st.subheader("Monitor de sensor")
    st.markdown("<div class='note'>Esta pantalla representa el <b>Modo Sensor</b> del mismo sistema. En la demo recibe una fotografía; en un piloto podría recibir la cámara del dispositivo o del dron.</div>",unsafe_allow_html=True)
    samples={"1. Inventario correcto":"01_inventario_correcto.png","2. Lectura borrosa":"02_lectura_borrosa_rescan.png","3. Segunda captura resuelta":"03_rescan_resuelto.png"}
    source=st.radio("Fuente",["Ejemplo incluido","Cargar fotografía"],horizontal=True); image_bytes=None; image_name=""
    if source=="Ejemplo incluido":
        name=st.selectbox("Escenario",list(samples)); image_name=name; image_bytes=(ASSETS/samples[name]).read_bytes()
    else:
        up=st.file_uploader("Imagen PNG o JPG",type=["png","jpg","jpeg"])
        if up: image_bytes=up.getvalue(); image_name=up.name
    if image_bytes:
        image=decode_image(image_bytes); readings,annotated,quality=analyze_image(image)
        i1,i2=st.columns(2); i1.image(cv2.cvtColor(image,cv2.COLOR_BGR2RGB),caption="Evidencia recibida",width="stretch"); i2.image(cv2.cvtColor(annotated,cv2.COLOR_BGR2RGB),caption="Análisis",width="stretch")
        q1,q2,q3=st.columns(3); q1.metric("Calidad de evidencia",f"{quality}%"); q2.metric("Lecturas válidas",len(readings)); q3.metric("Validación Core","ReScan" if quality<70 else "Aceptar evidencia")
        if quality<70: st.warning("No se genera una discrepancia: la evidencia es insuficiente. Debe realizarse una nueva captura.")
        elif readings:
            st.dataframe(pd.DataFrame([{"Ubicación":k,"Pallet observado":v["pallet"],"Cantidad":v["qty"],"Confianza":f'{v["confidence"]}%'} for k,v in readings.items()]),width="stretch",hide_index=True)
        else: st.warning("La imagen tiene calidad aceptable, pero no se detectaron códigos del escenario. Use revisión humana.")
        if st.button("Procesar evidencia",type="primary",width="stretch"):
            inspection_id,result=register_inspection(readings,"Cámara móvil simulada",image_name,quality)
            st.success(f"Inspección #{inspection_id}: {result}"); st.rerun()

with tabs[2]:
    st.subheader("Gemelo digital · vista de zona")
    st.caption("Cada celda representa una posición física y confronta lo esperado por el WMS simulado con la última evidencia observada.")
    cols=st.columns(3)
    for i,x in enumerate(locations):
        css="ok" if x["status"]=="Verificado" else "rescan" if x["status"]=="ReScan" else "bad"
        display_status={"Verificado":"Correcta","ReScan":"En revisión","Excepción":"Discrepancia"}.get(x["status"],"Pendiente")
        with cols[i%3]:
            st.markdown(f"<div class='card {css}'><div class='code'>{x['code']} · {x['product']}</div><b>Esperado:</b> {x['expected_pallet']} / {x['expected_qty']}<br><b>Observado:</b> {x['current_pallet']} / {x['current_qty']}<br><b>Lote:</b> {x['lot']} · <b>Caduca:</b> {x['expiry']}<br><b>Confianza:</b> {x['confidence']:.0f}%<br><b>Estado:</b> {display_status}</div>",unsafe_allow_html=True)

with tabs[3]:
    st.subheader("Prioridades operativas")
    st.caption("AeroTwin reduce el universo del inventario a una lista corta de casos que requieren atención humana.")
    exception_rows=[x for x in plan if x["status"] in ("Excepción","ReScan")]
    if not exception_rows: st.success("No hay excepciones activas.")
    for x in sorted(exception_rows,key=lambda y:y["risk_score"],reverse=True):
        with st.expander(f"{x['code']} · Risk Score {x['risk_score']}/100 · {x['status']}",expanded=True):
            st.write(f"**Esperado:** {x['expected_pallet']} / {x['expected_qty']}  ·  **Observado:** {x['current_pallet']} / {x['current_qty']}")
            st.write("**Razones:** "+", ".join(x["risk_reasons"]))
            if st.button("Crear tarea de revisión",key=f"task-{x['code']}"):
                task_id=create_task(x["code"],"Verificación física","Alta" if x["risk_score"]>=60 else "Media",f"Confianza {x['confidence']:.0f}%"); st.success(f"Tarea #{task_id} creada en el WMS simulado.")

with tabs[4]:
    st.subheader("Acciones hacia el WMS simulado")
    st.caption("Las tareas demuestran el cierre del ciclo: AeroTwin recomienda y el supervisor confirma la acción.")
    if tasks:
        st.dataframe(pd.DataFrame(tasks),width="stretch",hide_index=True)
        pending=[x for x in tasks if x["status"]=="Pendiente"]
        if pending:
            chosen=st.selectbox("Cerrar tarea",[x["id"] for x in pending])
            if st.button("Confirmar cierre"): close_task(chosen); st.rerun()
    else: st.info("Aún no existen tareas. Créelas desde Excepciones.")

with tabs[5]:
    st.subheader("Agente AeroTwin")
    st.markdown("<div class='note'>El agente consulta únicamente los datos registrados en el MVP. No modifica el inventario y sus recomendaciones requieren validación humana.</div>",unsafe_allow_html=True)
    if "agent_messages" not in st.session_state:
        st.session_state.agent_messages=[{"role":"assistant","content":"Consulto los datos actuales de AeroTwin Core. Puedo explicar el próximo objetivo, los puntajes, las excepciones, las tareas y cualquier ubicación del escenario."}]
    quick=["¿Dónde conviene inspeccionar después?","¿Qué excepción debo atender primero?","Dame un resumen del inventario"]
    qcols=st.columns(3); selected=None
    for i,q in enumerate(quick):
        if qcols[i].button(q,key=f"quick-{i}",width="stretch"): selected=q
    for message in st.session_state.agent_messages:
        with st.chat_message(message["role"]): st.markdown(message["content"])
    typed=st.chat_input("Pregunta sobre el escenario de inventario")
    question=selected or typed
    if question:
        st.session_state.agent_messages.append({"role":"user","content":question})
        response=answer_question(question,locations,plan,observations,tasks,inspections)
        st.session_state.agent_messages.append({"role":"assistant","content":response})
        st.rerun()

with tabs[6]:
    st.subheader("Indicadores del escenario")
    st.caption("Son métricas del prototipo, no resultados reales de Nestlé.")
    m1,m2,m3,m4=st.columns(4); m1.metric("Cobertura",f"{round(100*verified/len(locations))}%"); m2.metric("Inspecciones",len(inspections)); m3.metric("Tareas",len(tasks)); m4.metric("Excepciones activas",exceptions+rescans)
    chart=pd.DataFrame([{"Ubicación":x["code"],"Inspection Score":x["inspection_score"],"Risk Score":x["risk_score"]} for x in plan]).set_index("Ubicación")
    st.bar_chart(chart,color=["#1d8f82","#ce4c4c"])

with tabs[7]:
    st.subheader("Historial y cadena de evidencia")
    if observations: st.dataframe(pd.DataFrame(observations),width="stretch",hide_index=True)
    else: st.info("Procesa una inspección para crear evidencia.")
    if inspections:
        st.markdown("#### Inspecciones"); st.dataframe(pd.DataFrame(inspections),width="stretch",hide_index=True)
    if st.button("Restablecer demostración"): reset_demo(); st.rerun()
