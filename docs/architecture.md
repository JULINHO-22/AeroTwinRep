# Arquitectura — Fase 4

```text
Android Sensor / Operator App
              |
              | multipart + JWT
              v
       FastAPI AeroTwin Core
              ^
              | REST + JWT (futuro)
              |
      Web Control Station

FastAPI -> ReadingService -> QualityPolicy / Comparison Engine / Risk Engine
FastAPI -> EvidenceStorage -> filesystem local + PostgreSQL metadata
FastAPI -> SQLAlchemy 2.0 + psycopg 3 -> PostgreSQL 17 local
```

Android conserva la Base URL y el JWT en preferencias privadas, con backup
desactivado. FastAPI administra el engine y la fábrica de sesiones; los
endpoints reciben sesiones mediante `get_db`. Alembic es la única fuente del
esquema.

Los routers son adaptadores HTTP delgados. La lectura entra como
`multipart/form-data`: un campo `payload` con el JSON de `ReadingCreateRequest`
y un campo `evidence` JPEG. `ReadingService` continúa siendo el único
coordinador de comparación, calidad y riesgo; recibe la evidencia ya validada
sin duplicar reglas por protocolo.

```text
Android Field / Sensor Client
              |
              | multipart (payload JSON + JPEG)
              v
       AeroTwin Core
              |
              +-- Reading
              +-- Evidence -> backend/uploads/evidence/inspection_<id>/<uuid>.jpg
                              + PostgreSQL evidence_files metadata
```

`EvidenceStorage` acepta exclusivamente JPEG de hasta 5 MB, obtiene ancho y
alto, y calcula SHA-256. El cliente Android comprime a JPEG calidad 80 y limita
el lado largo a aproximadamente 1280 px antes de enviar. El backend genera el
nombre y solo almacena una ruta relativa, por lo que ni rutas locales ni inputs
de ruta del cliente quedan expuestos. `GET /api/v1/evidence/{id}` requiere JWT
y entrega el archivo solo al operador dueño de la inspección o a un supervisor.

La escritura usa staging en `uploads/evidence/.tmp`: valida y escribe temporal,
hace `flush` de reading y metadata, mueve atómicamente a la ruta final y recién
entonces confirma la transacción. Si el commit o el movimiento falla, intenta
limpiar el temporal/final. Un reintento con el mismo `client_reading_id` devuelve
la lectura y su evidencia existentes sin crear una segunda fila o archivo.

## Sensor Mode — Fase 5

```text
CameraX Preview + ImageAnalysis (KEEP_ONLY_LATEST)
              |
              v
ML Kit Barcode Scanner (QR; Code 128 experimental)
              |
              v
QR parser -> estabilidad de 5 frames -> calidad de captura
              |
              v
ImageCapture automático -> Evidence Pipeline multipart -> ReadingService
```

El MVP solamente acepta QR con formato explícito `LOC:<zona>-<fila>-<posición>`
o `PAL:PAL-<nnn>`; la detección no revela inventario esperado. El flujo sensor
es una máquina de estados: buscar/validar ubicación, buscar pallet, capturar,
procesar y resultado. No inferir vacío por ausencia de código: el operador debe
confirmarlo y entonces se captura evidencia amplia. Las lecturas sensor usan
`ANDROID_CAMERA`; el modo manual continúa usando `MANUAL_DEMO`.

La calidad V1 no es confianza de IA. Combina estabilidad (40%), tamaño relativo
del código (30%) y brillo medio del frame (30%). El umbral de auto-captura es
40/100 para permitir que QualityPolicy decida reescaneo; el backend conserva su
umbral de aceptación de 85/100. Para la demo física se generan etiquetas QR en
`artifacts/demo-labels/`. La proyección del teléfono puede hacerse externamente
con scrcpy; AeroTwin no transmite video ni crea un frontend web.

La autenticación usa contraseñas Argon2 y JWT HS256 con expiración configurable.
Los endpoints de consulta de zonas y ubicaciones admiten ambos roles. Crear una
inspección admite `OPERATOR` o `SUPERVISOR`; la lectura humana pertenece al
actor que inició la inspección y la lectura del sensor usa su token de
dispositivo. La ubicación nunca expone el pallet
esperado: ese snapshot se revela únicamente en la respuesta del reading.

Los enums de Python se persisten como `VARCHAR` con constraints `CHECK`, no
como tipos ENUM nativos de PostgreSQL. Esto conserva validación en base y
reduce fricción al modificar valores durante el hackathon.

`Inspection` junto con sus `inspection_readings` finales representa un
snapshot lógico. Cada intento guarda `expected_pallet_id_at_inspection`, por lo
que un cambio posterior en `expected_inventory` no altera el resultado
histórico. `client_reading_id` garantiza idempotencia. No existen tablas de
snapshots físicos. Los pesos y umbrales demo viven en `backend/settings.json`;
secretos y entorno viven en `.env`.

Las reglas de comparación, calidad, caducidad, rotación, cobertura, FEFO y
riesgo son funciones puras bajo `app/domain`. El módulo
`app/services/inventory_analytics.py` reúne datos analíticos y
`app/services/reading_service.py` coordina la lectura transaccional. Ninguna
regla pura depende de FastAPI, Android, cámara o IA.

El riesgo inicial de la Fase 3 se calcula y retorna con la lectura, pero no se
crea automáticamente una `ExceptionEvent`: la gestión completa de excepciones
queda fuera de esta fase. Tampoco se implementan cámara, evidencia, web,
WebSocket, Digital Twin ni Agent.

## Corrección Fase 5R — Sensor Device vs Operator

```text
Teléfono: AeroTwin Sensor                         Control Station (humano)
  sensor_id + device_token                                  JWT
            |                                                 |
            +---------------- Wi-Fi / FastAPI ----------------+
                              |
                         ReadingService
```

El teléfono se inicia escogiendo **Modo operador** o **Modo sensor**. El modo
operador conserva el JWT humano. El modo sensor no muestra login: la primera
vez registra un nombre, recibe `sensor_id` y un `device_token` opaco, y guarda
solo esa identidad local del dispositivo. El backend almacena únicamente el
SHA-256 del token en `sensor_devices`; nunca recibe ni guarda la contraseña o
el JWT de un operador desde Sensor Mode.

Endpoints nuevos:

- `POST /api/v1/sensor/register`: vinculación demo y entrega del token una sola vez.
- `GET /api/v1/sensor/mission`: token `X-Sensor-Token`; devuelve misión activa o `null`.
- `GET /api/v1/sensor/locations/code/{code}` y `POST /api/v1/sensor/mission/readings`:
  solo funcionan para la misión asignada y el segundo exige `ANDROID_CAMERA`.
- `POST /api/v1/inspections/{inspection_id}/assign-sensor/{sensor_id}`: supervisor.
- `GET /api/v1/sensors` y `GET /api/v1/sensors/{id}/status`: supervisor; incluyen
  presencia, misión y última lectura del sensor.

La máquina del sensor es: espera misión → busca ubicación → valida ubicación
en Core → busca pallet → estabiliza/calcúla calidad → captura → envía lectura
→ resultado o reescaneo. `ImageAnalysis` conserva solo el frame más reciente,
opera a resolución objetivo 1280×720 y cierra todos los `ImageProxy`. ML Kit
procesa todos los códigos relevantes de cada frame antes de que la máquina de
estado seleccione uno. El overlay mantiene cada candidato: azul (candidato),
verde (confirmado), ámbar (calidad baja) o rojo (formato/fase incompatible),
con tipo, código y estado sobre la caja. Los logs `AeroTwinSensor` incluyen
formato, valor QR, fase, frames estables y calidad; no contienen tokens.

La evidencia manual admite fotos que Android pueda decodificar (incluidos
JPEG, PNG, WebP y HEIC/HEIF en versiones compatibles). `ImageDecoder` se usa
cuando está disponible y toda imagen se normaliza a JPEG antes del envío. El
backend sigue aceptando JPEG porque ese es el contrato normalizado.

Para espejo de demo se usa scrcpy, sin streaming implementado en AeroTwin:

```powershell
scrcpy --video-bit-rate 8M --max-size 1280 --stay-awake
```

Activa depuración USB, conecta el teléfono y ejecuta el comando desde una
instalación de scrcpy con `adb` disponible. Todo el preview y los overlays se
dibujan localmente en el teléfono, por lo que se reflejan en scrcpy. Una
evolución posterior podrá enviar JPEGs o frames por WebSocket a Control
Station; no se implementa en esta fase.
