# AeroTwin · Consola operativa

MVP web coherente con la aplicación móvil AeroTwin. Representa el Modo Operador y usa datos simulados para demostrar la continuidad entre sensor, AeroTwin Core, gemelo digital, riesgo y decisión humana.

## Funciones

- Emparejamiento ubicación-pallet mediante QR de demostración.
- Adaptive ReScan cuando la evidencia visual no supera el umbral.
- AeroTwin Core e Inspection Score para elegir dónde inspeccionar después.
- Risk Score para priorizar excepciones ya detectadas.
- Replanificación al bloquear un pasillo.
- Gemelo digital, tareas WMS simuladas, métricas e historial.
- Agente IA local conectado con el plan, los puntajes, las excepciones y las tareas.

## Instalación en Windows

```bat
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
streamlit run app.py
```
