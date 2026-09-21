# AeroTwin

AeroTwin es el prototipo de Two Bit para el reto de gestión inteligente de
inventarios (Track 2). El MVP actual une Sensor Mode, QualityPolicy,
Comparison Engine, Risk Score, FlowTwin, Warehouse Memory, Agent local y un
Gemelo Digital vivo que se completa con cada lectura final persistida.

Los nombres comerciales de Nestlé que aparecen en la demostración son
referencias públicas de producto. Los SKU `DEMO-*`, lotes, pallets, cantidades,
fechas, ubicaciones y movimientos son exclusivamente datos sintéticos del WMS
simulado; no representan códigos internos ni inventario real de Nestlé.

```text
Android Sensor / Operator App (Kotlin + Compose)
          |
          | HTTP en red privada
          v
FastAPI + SQLAlchemy 2.0 + psycopg 3
          |
          v
PostgreSQL 17 local
```

La API es cliente-agnóstica para que una futura estación de control pueda
consumir el mismo núcleo. El MVP actual incluye captura con cámara, QR,
evidencia, FlowTwin, Gemelo Digital por polling ligero y Agent local
explicable. No incluye Web Control Station, WebSocket, LLM, RAG ni
automatización física de inventario.

## Requisitos

- Windows 10/11.
- Python 3.12.
- PostgreSQL 17 instalado localmente.
- Android Studio compatible con Android Gradle Plugin 9.3.
- Android SDK 37 y JDK 17 o superior.
- Dispositivo con Android 8.0 (API 26) o posterior.

Se eligió PostgreSQL local porque este entorno Windows no tenía Docker ni
Docker Compose. Así se evita instalar Docker Desktop/WSL solo para una base y
el backend continúa ejecutándose directamente con Python. El esquema y el
seed siguen siendo reproducibles mediante Alembic y scripts versionados.

## Preparar PostgreSQL

Instala PostgreSQL 17 desde <https://www.postgresql.org/download/windows/> y
conserva la contraseña que elijas para el superusuario `postgres`. La
contraseña del superusuario no debe guardarse en el repositorio.

Comprueba el servicio desde PowerShell:

```powershell
Get-Service postgresql-x64-17
```

Abre `psql` como `postgres` y crea el rol y las bases de desarrollo/pruebas:

```sql
CREATE ROLE aerotwin LOGIN PASSWORD 'aerotwin_demo';
CREATE DATABASE aerotwin OWNER aerotwin;
CREATE DATABASE aerotwin_test OWNER aerotwin;
```

`aerotwin_demo` es una credencial local de demostración, no una contraseña de
producción ni del usuario de Windows.

## Preparar el backend

Desde PowerShell:

```powershell
cd backend
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
Copy-Item .env.example .env
```

Variables principales de `backend/.env`:

```dotenv
APP_ENV=development
DEMO_MODE=true
HOST=0.0.0.0
PORT=8000
DATABASE_URL=postgresql+psycopg://aerotwin:aerotwin_demo@localhost:5432/aerotwin
TEST_DATABASE_URL=postgresql+psycopg://aerotwin:aerotwin_demo@localhost:5432/aerotwin_test
JWT_SECRET_KEY=replace-with-at-least-32-random-characters
JWT_ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=480
```

`.env` está ignorado por Git; `.env.example` sí se versiona y no contiene
secretos personales.

## Migrar y cargar la demo

La base se crea exclusivamente mediante migraciones. `create_all()` no forma
parte del flujo de desarrollo.

```powershell
cd backend
.\.venv\Scripts\Activate.ps1
python -m alembic upgrade head
python -m scripts.seed_demo
```

`seed_demo` aplica una estrategia de reemplazo transaccional: vacía únicamente
las 15 tablas de dominio, reinicia sus secuencias y vuelve a insertar el
dataset determinista. Por tanto, el mismo comando sirve para seed inicial,
reset y reseed sin duplicados. Solo se permite con `DEMO_MODE=true`.

El seed histórico usa `SourceType.SEED_SYSTEM`. La captura manual de esta fase
usa `MANUAL_DEMO`; `ANDROID_CAMERA` y `DRONE` quedan reservados para fuentes
reales futuras. Sus lecturas históricas no crean
archivos físicos de evidencia porque son snapshots sintéticos anteriores al
inicio de la demo.

Credenciales exclusivas de demostración (la base almacena Argon2, no texto
plano):

```text
operator01   / AeroTwin123!
supervisor01 / AeroTwin123!
```

## Verificar datos

Desde `psql`:

```sql
\c aerotwin
\dt
SELECT version_num FROM alembic_version;
SELECT COUNT(*) FROM locations;
SELECT COUNT(*) FROM movement_history;
SELECT COUNT(*) FROM inspection_readings WHERE is_final = true;
```

O desde PowerShell:

```powershell
cd backend
.\.venv\Scripts\Activate.ps1
python -m alembic current
python -m scripts.seed_demo
```

El dataset esperado contiene 12 ubicaciones, 10 productos demo, 11 lotes, 15
pallets, 53 movimientos, 3 inspecciones históricas, 19 lecturas y 10
excepciones.

## Ejecutar tests

```powershell
cd backend
.\.venv\Scripts\Activate.ps1
python -m pytest -q
```

La suite exige que `TEST_DATABASE_URL` termine en `_test`. Reconstruye
`aerotwin_test` con `alembic downgrade base` y `upgrade head`, carga el seed y
valida autenticación, flujo E2E, Quality/ReScan, comparación, idempotencia,
relaciones y constraints. Nunca
trunca la base `aerotwin` durante los tests.

## Iniciar FastAPI

```powershell
cd backend
.\.venv\Scripts\Activate.ps1
python run.py
```

`run.py` lee host, puerto y conexión desde `.env`. FastAPI escucha en
`0.0.0.0:8000`, necesario para el teléfono.

Comprueba:

```text
http://127.0.0.1:8000/api/v1/health
```

Con `DEMO_MODE=true` y PostgreSQL disponible:

```json
{
  "status": "ok",
  "environment": "DEMO",
  "database": "connected"
}
```

Si PostgreSQL no está disponible, responde HTTP 503 con estado `degraded`. En
modo no-demo no expone detalles internos de la base.

## Ejecutar Android

1. Abre `android` con Android Studio y espera Gradle Sync.
2. Conecta el teléfono y ejecuta la variante `debug`.
3. Obtén la IPv4 de la laptop con `ipconfig`.
4. Escribe `http://<IP_LAPTOP>:8000` en AeroTwin.
5. Pulsa **PROBAR CONEXIÓN**.
6. Inicia sesión con `operator01` / `AeroTwin123!`.
7. Pulsa **NUEVA INSPECCIÓN**, elige Zona A y envía:
   `A-01-01`, `PAL-001`, calidad `95`.
8. Comprueba `✓ LECTURA CORRECTA`.
9. En una nueva lectura envía `A-01-02`, `PAL-008`, calidad `95` y comprueba
   `PALLET MISMATCH`.
10. Para ReScan crea una inspección de Zona B (después de reiniciar el seed o
    finalizar/cancelar la inspección activa), envía `B-01-01`, `PAL-006`,
    calidad `42`; cambia la calidad a `94` y pulsa **ENVIAR RE-SCAN**.

La Base URL y el token JWT se guardan en preferencias privadas de la app; el
backup de la aplicación está desactivado. Es una protección razonable para el
MVP local, no el diseño final de credenciales de producción.
HTTP sin TLS está habilitado únicamente en la variante `debug` para la red
privada; release mantiene cleartext desactivado.

Para compilar por terminal:

```powershell
cd android
.\gradlew.bat :app:assembleDebug
```

## Estructura actual

```text
aerotwin/
├── backend/
│   ├── alembic/       # esquema y evolución de enums/constraints
│   ├── app/api/       # routers, auth, dependencias y errores estructurados
│   ├── app/db/        # Base, engine, sesiones y dependencia FastAPI
│   ├── app/domain/    # comparación, calidad, analytics, riesgo y settings
│   ├── app/models/    # modelos y enums de dominio
│   ├── app/services/  # inspecciones, ReadingService y analytics
│   ├── scripts/       # seed/reset demo determinista
│   ├── tests/         # unidad, integración PostgreSQL y flujo API E2E
│   └── settings.json  # umbrales y pesos demo
├── android/           # app operador: conexión, login, inspección y reading
├── docs/
├── README.md
└── .gitignore
```

Las reglas y fórmulas están resumidas en `docs/business-rules.md`. El Gemelo
Digital solo cambia su cobertura con lecturas finales persistidas; los QR
candidatos son telemetría visual y no inventario confirmado.
