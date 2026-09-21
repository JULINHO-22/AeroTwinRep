# Reglas de negocio del MVP

Todas las reglas son deterministas y sus parámetros se validan una vez desde
`backend/settings.json`.

## Calidad y ReScan

`quality_score` mide calidad operacional, no probabilidad de IA. Hay dos
capturas totales como máximo:

- Score ≥ 85: `ACCEPTED`.
- Score < 85 en intento 1: `RESCAN_REQUIRED`.
- Score < 85 en intento 2: `HUMAN_REVIEW_REQUIRED`.

Un primer intento malo no penaliza el riesgo si la lectura final fue aceptada.

## Caducidad, rotación y cobertura

- Vencido: días restantes < 0.
- Riesgo alto: 0–30 días.
- Riesgo medio: 31–90 días.
- Normal: más de 90 días.
- Rotación: suma de cantidades `OUTBOUND` en los últimos 30 días.
- Rotación alta: ≥ 300; media: ≥ 100; baja: < 100.
- Cobertura: stock esperado / salida diaria promedio.
- Cobertura ≤ 7 días: `LOW_COVERAGE`.
- Sin salidas: cobertura `None`, estado `NO_CONSUMPTION_DATA`.

El stock esperado se calcula exclusivamente desde los pallets presentes en
`expected_inventory`.

## FEFO

Existe riesgo cuando sale un lote y todavía hay stock WMS disponible del mismo
producto en otro lote con vencimiento anterior. El resultado identifica lote
outbound, lote preferente y explicación. La cobertura física de posiciones
sigue calculándose exclusivamente desde `expected_inventory`.

## Prevención de pérdida

La señal explicable `EXCESS_EXPIRY_RISK` no modifica el Risk Score. Se activa
únicamente si existen ambos datos y `coverage_days > days_to_expiry`: al ritmo
actual, el inventario podría durar más que la vida restante del lote. Si falta
consumo o caducidad, no se infiere una señal.

## Slotting sugerido

La sugerencia es deliberadamente conservadora: solo se muestra cuando un
producto tiene rotación `HIGH` y su `Location.level` es mayor que 1. Nunca
mueve inventario ni altera el recorrido por sí sola. El seed actual usa nivel
1 para todas las posiciones, por lo que no presenta una recomendación real de
slotting: hace falta metadata física adicional de accesibilidad para emitirla
de forma defendible.

## Risk Score

Pesos:

| Regla | Puntos |
|---|---:|
| PALLET_MISMATCH | 35 |
| EXPECTED_PALLET_MISSING | 40 |
| UNEXPECTED_PALLET | 35 |
| EXPIRING_SOON | 20 |
| HIGH_ROTATION | 15 |
| LOW_COVERAGE | 25 |
| LOW_QUALITY | 10 |
| FEFO_RISK | 10 |
| HISTORICAL_ANOMALY | 10 |

El total se limita a 100. Severidad: 0–39 baja, 40–59 media, 60–79 alta y
80–100 crítica. Una discrepancia física nunca queda por debajo de severidad
media, aunque su score individual sea 35.
