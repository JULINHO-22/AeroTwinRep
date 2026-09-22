# AeroTwin · Consola operativa

MVP web coherente con la aplicación móvil AeroTwin para el Track 2 del Hackathon InnoLabs Nestlé. Representa el Modo Operador y usa datos simulados para demostrar la continuidad entre sensor, AeroTwin Core, gemelo digital, riesgo y decisión humana.

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

## Guion rápido

1. En **Command Center**, observe el próximo objetivo y el plan adaptativo.
2. Bloquéela y pulse **Actualizar y replanificar**.
3. En **Monitor de sensor**, procese **1. Inventario correcto**.
4. Procese **2. Lectura borrosa**: debe solicitar ReScan sin acusar una discrepancia.
5. Procese **3. Segunda captura resuelta**: aparecerán un pallet incorrecto y una posición vacía.
6. Abra **Excepciones**, cree una tarea y ciérrela desde **Acciones WMS**.
7. Abra **Agente AeroTwin** y pregunte: `¿Dónde conviene inspeccionar después?`.

## Alcance

No existe conexión real con SAP/WMS ni control autónomo de un dron. Los QR combinados se usan solo para una demostración controlada; un piloto real conservaría el marcador de ubicación y el código de barras oficial del pallet. La app móvil y esta consola representan dos vistas del mismo sistema AeroTwin, no dos propuestas distintas.
