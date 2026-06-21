# etl-calidad · Plan de implementación (speckit-plan)

> Paquete: `etl-calidad` · OP2 · CU-O03, CU-O04 · Ingeniería de datos.
> Spec fuente: [etl-calidad-spec.md](etl-calidad-spec.md). Marco:
> [000-general](../000-general/operativo-general-spec.md).

---

## 1. Arquitectura del paquete

```
Parquet staging (snappy)        PocketBase (dims operacionales)
        │                                │
        ▼                                ▼
┌───────────────────────── GE previa (CU-O04) ─────────────────────────┐
│  stg_*_suite: clave única, no-nulos, dominios, conteo · FAIL-FAST     │
└───────────────────────────────┬──────────────────────────────────────┘
                                 ▼ (solo si pasa)
                    ┌──────────────────────────┐
                    │  DBT (CU-O03)            │  stg_* → dim_* / fct_*
                    │  materializa Fact-Dim     │  tests unique/not_null/
                    │  en StarRocks (:9030)    │  relationships/accepted_values
                    └──────────────┬───────────┘
                                   ▼
┌───────────────────────── GE posterior (CU-O04) ──────────────────────┐
│  fct_*/dim_*_suite sobre el DW · FAIL-FAST antes de agregaciones      │
└───────────────────────────────┬──────────────────────────────────────┘
                                 ▼ (solo si pasa)
                       Promoción a agregaciones (ClickHouse, OP3)
```

## 2. Herramientas y componentes

| Componente | Tecnología | Responsabilidad |
|---|---|---|
| Validación de calidad | **Great Expectations** | Suites previa (staging) y posterior (DW), fail-fast. |
| Transformación | **DBT** sobre StarRocks | Modelos `stg_*`, `dim_*`, `fct_*` versionados. |
| Data Warehouse | **StarRocks** (MySQL :9030) | Persistir el esquema Fact-Dim OLAP. |
| Linaje | **dbt docs** | Grafo `sources`/`exposures`, procedencia por columna. |
| Orquestación | **Apache Airflow** | DAG: GE previa → DBT → GE posterior, idempotente. |
| Empaquetado | **Docker** | Runner DBT/GE + StarRocks contenedorizados. |

## 3. Modelo de datos (capa DBT)

- **Staging models** (`view`): `stg_resena`, `stg_precio_mercado`, `stg_puntuacion`
  leen el Parquet de `ingesta-datos`.
- **Dimensiones** (`table`): `dim_tiempo`, `dim_vino`, `dim_bodega`,
  `dim_region_vitivinicola`, `dim_mercado`, `dim_catador_sumiller`.
- **Hechos** (`incremental`): `fct_resena` (→ `Fact_Resena`),
  `fct_precio_mercado` (→ `Fact_Precio_Mercado`), `fct_puntuacion` (→ `Fact_Puntuacion`).
- **schema.yml**: tests `unique`/`not_null` en PK, `relationships` Fact→Dim,
  `accepted_values` en dominios (`puntaje`, `moneda`).

## 4. Secuencia de implementación

1. Configurar el proyecto DBT con perfil StarRocks (:9030) y `sources` del staging.
2. Escribir suites GE previas (`stg_*_suite`) con dominios y unicidad (CU-O04).
3. Implementar el gate fail-fast previo en Airflow (RF-202).
4. Implementar modelos `stg_*` → `dim_*` → `fct_*` con materializaciones (RF-205, RF-206).
5. Añadir tests DBT en `schema.yml` (RF-207, RN-304).
6. Escribir suites GE posteriores sobre el DW (RF-203) y su gate.
7. Generar `dbt docs` con linaje (RF-210).
8. Producir reportes de calidad y de ejecución (RF-204, RF-209).
9. Ensamblar el DAG `dag_pipeline_diario` (tramo central) y contenedorizar (RNF-205).

## 5. Riesgos

| Riesgo | Impacto | Mitigación |
|---|---|---|
| Datos sucios pasan a DW | BI poco fiable | GE previa fail-fast + GE posterior (RN-301, RN-302). |
| SQL imperativo fuera de DBT | Pérdida de linaje | RN-303: solo modelos DBT versionados. |
| FK Fact→Dim rotas | Hechos huérfanos | Test `relationships` + RN-304. |
| Reproceso duplica hechos | Métricas infladas | Materialización `incremental` idempotente (RNF-202). |
| Linaje incompleto | Columnas sin origen | `dbt docs` + revisión (RN-306). |

## 6. Trazabilidad de cumplimiento constitucional

- Princ. V (calidad/GE) → §1, RF-201..RF-204; Princ. VI (DBT) → RF-205..RF-207.
- Princ. VII (linaje) → RF-210; Princ. VIII/IX (Docker/Airflow) → §2, paso 9.
