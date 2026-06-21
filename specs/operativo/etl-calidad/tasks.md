# etl-calidad · Tareas (speckit-tasks)

> Paquete: `etl-calidad` · OP2 · CU-O03, CU-O04. Tareas atómicas ordenadas por
> dependencia. Marca `[x]` al completar. Citan RF/RN/CA de
> [etl-calidad-spec.md](etl-calidad-spec.md).

---

## A. CU-O04 — Validar calidad (suite previa, sobre staging)

- [ ] **T-01** Configurar Great Expectations contra los datasets Parquet del staging. *(RF-201)*
- [ ] **T-02** Escribir `stg_resena_suite`, `stg_precio_suite`, `stg_puntuacion_suite`: clave única, no-nulos, conteo. *(RF-201)*
- [ ] **T-03** Añadir expectativas de dominio: `precio>0`, `puntaje∈[80,100]`, fecha no futura, `moneda` ISO-4217. *(RF-201, RN-205-ref)*
- [ ] **T-04** Implementar el gate **fail-fast** previo en Airflow (si falla, no corre el ETL). *(RF-202, RN-301, CA-202)*
- [ ] **T-05** Prueba: staging con `puntaje=120` detiene el pipeline antes del ETL. *(Esc-202)*

## B. CU-O03 — Ejecutar pipeline ETL (DBT → StarRocks)

- [ ] **T-06** Inicializar proyecto DBT con perfil StarRocks (:9030) y `sources` del staging. *(RF-205)*
- [ ] **T-07** Implementar modelos `stg_*` (view) sobre el Parquet. *(RF-205)*
- [ ] **T-08** Implementar dimensiones `dim_*` (table): tiempo, vino, bodega, region, mercado, catador. *(RF-205)*
- [ ] **T-09** Implementar hechos `fct_resena`, `fct_precio_mercado`, `fct_puntuacion` (incremental). *(RF-205, RF-206)*
- [ ] **T-10** Declarar materializaciones e idempotencia en cada modelo. *(RF-206, RNF-202)*
- [ ] **T-11** Añadir tests DBT en `schema.yml`: `unique`, `not_null`, `relationships`, `accepted_values`. *(RF-207, RN-304)*
- [ ] **T-12** Resolver claves foráneas Fact→Dim (integridad referencial). *(RF-208, RN-304)*
- [ ] **T-13** Aplicar deduplicación en transformación (defensa en profundidad). *(RN-305)*
- [ ] **T-14** Generar el reporte de ejecución del ETL (modelos, filas, errores, duración). *(RF-209, CA-208)*
- [ ] **T-15** Prueba: FK de mercado inexistente hace fallar `relationships` → `FALLIDO_ETL`. *(Esc-203)*
- [ ] **T-16** Prueba: reejecución incremental no duplica hechos. *(CA-207, Esc-205)*

## C. CU-O04 — Validar calidad (suite posterior, sobre DW)

- [ ] **T-17** Escribir suites GE posteriores por Fact/Dim sobre StarRocks. *(RF-203)*
- [ ] **T-18** Implementar el gate fail-fast posterior antes de promover a agregaciones. *(RF-203, RN-302, CA-205)*
- [ ] **T-19** Generar el reporte de calidad (expectativas evaluadas/fallidas + muestras). *(RF-204, CA-208)*
- [ ] **T-20** Prueba: DW con clave duplicada bloquea la promoción a ClickHouse. *(Esc-204)*

## D. Linaje, orquestación y cierre

- [ ] **T-21** Generar `dbt docs` con `sources`/`exposures` y verificar linaje staging→Fact-Dim. *(RF-210, CA-206, RN-306)*
- [ ] **T-22** Ensamblar el tramo central del DAG `dag_pipeline_diario`: GE previa → DBT → GE posterior. *(RT-03)*
- [ ] **T-23** Contenedorizar runner DBT/GE + StarRocks en `docker-compose.yml` (versiones fijas). *(RNF-205, RT-17)*
- [ ] **T-24** Verificar arranque end-to-end con `docker compose up`. *(RT-17)*
- [ ] **T-25** Validar spec contra constitución y completar [checklist.md](checklist.md). *(RT-18, RT-19)*
