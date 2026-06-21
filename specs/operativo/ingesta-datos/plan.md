# ingesta-datos · Plan de implementación (speckit-plan)

> Paquete: `ingesta-datos` · OP1 · CU-O01, CU-O02 · Ingeniería de datos.
> Spec fuente: [ingesta-datos-spec.md](ingesta-datos-spec.md). Marco:
> [000-general](../000-general/operativo-general-spec.md). No se programa nada que
> no esté en el spec (Princ. III).

---

## 1. Arquitectura del paquete

```
Fuente externa (API / feed / archivo)
        │  (lectura incremental)
        ▼
┌──────────────────────┐      registra/lee metadatos     ┌──────────────┐
│  Conector de ingesta │◄───────────────────────────────►│  PocketBase  │
│  (Python)            │     catálogo de fuentes (CU-O01) │ (operacional)│
│  - valida esquema    │                                  └──────────────┘
│  - deduplica (clave   │
│    natural)          │      escribe crudo válido
│  - reporte de ingesta│ ───────────────────────────────► Parquet staging (snappy)
└──────────────────────┘                                   particionado fuente/fecha
        │  registros inválidos
        ▼
   rejects/  (área de rechazos)
```

Orquestación: una tarea `ingesta` por fuente activa dentro del DAG
`dag_pipeline_diario` (Airflow), **antes** de la tarea de calidad. *(RT-03)*

## 2. Herramientas y componentes

| Componente | Tecnología | Responsabilidad |
|---|---|---|
| Catálogo de fuentes | **PocketBase** | Persistir metadatos de fuentes (CU-O01). |
| Conector de ingesta | **Python** (`requests`/cliente de la fuente) | Leer incremento de la fuente externa. |
| Validador de esquema | **pydantic** / esquema declarativo | Verificar campos obligatorios por `tipo`. |
| Deduplicador | **pyarrow** / pandas | Eliminar duplicados por clave natural. |
| Escritor de staging | **pyarrow** (Parquet, `compression='snappy'`) | Escribir particionado por `fuente`/`fecha_ingesta`. |
| Orquestación | **Apache Airflow** | DAG idempotente con `retries`/`retry_delay`. |
| Empaquetado | **Docker** + `docker-compose.yml` | Conector, PocketBase, Airflow contenedorizados. |

## 3. Modelo de datos

**Catálogo de fuentes (PocketBase) — colección `fuentes_externas`:**
`id`, `nombre`, `tipo` (reseñas|precios|puntuaciones), `formato`, `endpoint`,
`frecuencia` (cron), `mercado_id` → `Dim_Mercado`, `catador_id` → `Dim_Catador_Sumiller`,
`estado` (BORRADOR|VALIDANDO_CONEXION|ACTIVA|PAUSADA|BAJA|RECHAZADA),
`ultima_ingesta`, `created`, `updated`.

**Staging Parquet (snappy):**
- `staging/resena/fuente=<id>/fecha_ingesta=<YYYY-MM-DD>/*.parquet` → origen de `Fact_Resena`.
- `staging/precio_mercado/...` → origen de `Fact_Precio_Mercado`.
- `staging/puntuacion/...` → origen de `Fact_Puntuacion`.

Claves naturales (dedup, RN-203):
`Fact_Resena (fuente, catador, vino, fecha_resena)` ·
`Fact_Precio_Mercado (fuente, vino, mercado, fecha_precio)` ·
`Fact_Puntuacion (fuente, catador, vino, fecha_cata)`.

## 4. Secuencia de implementación

1. Modelar la colección `fuentes_externas` en PocketBase (CU-O01).
2. Implementar el registro de fuentes con validación de conexión/esquema y guardia
   anti-duplicados (RF-101..RF-105).
3. Implementar el conector de ingesta con lectura incremental por fuente (RF-106).
4. Añadir validación de esquema con desvío a `rejects/` y umbral de rechazo (RF-107, RN-204).
5. Implementar deduplicación por clave natural (RF-108, RN-203).
6. Implementar el escritor Parquet snappy particionado (RF-109, RNF-101).
7. Generar el reporte de ingesta por lote (RF-110).
8. Envolver todo como tarea Airflow en `dag_pipeline_diario` con `retries` (RNF-106).
9. Contenedorizar y validar arranque con `docker compose up` (RT-17).

## 5. Riesgos

| Riesgo | Impacto | Mitigación |
|---|---|---|
| Esquema de la fuente cambia sin aviso | Lote `FALLIDA` masiva | Validación de esquema + umbral RN-204 + alerta. |
| Duplicados por reejecución | Datos inflados en staging | Dedup por clave natural + idempotencia (RN-203, RNF-102). |
| Fuente caída / latente | Pipeline bloqueado | `retries`/`retry_delay` en Airflow + alerta (Esc-107). |
| Tentación de transformar en la ingesta | Salto de capa | RN-206: la ingesta solo aterriza crudo; transformar es OP2. |
| Volumen alto | Degradación del DAG diario | Lectura incremental + particionado + Parquet columnar. |

## 6. Trazabilidad de cumplimiento constitucional

- Princ. I (solo operativo) → paquete bajo `specs/operativo/`.
- Princ. II/IV (trazabilidad) → bloque OP1/OT7/OE4/CU-O01-02 en el spec.
- Princ. V (calidad) → validación de esquema aquí; GE profunda en `etl-calidad`.
- Princ. VIII (Docker) y IX (Airflow) → §2 y paso 8–9.
