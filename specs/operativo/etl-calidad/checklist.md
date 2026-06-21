# etl-calidad · Checklist — Definición de Terminado (speckit-checklist)

> Paquete: `etl-calidad` · OP2 · CU-O03, CU-O04. No se integra hasta marcar todos
> los ítems. Verifica contra [etl-calidad-spec.md](etl-calidad-spec.md) y la
> [constitución](../../../.specify/memory/constitution.md).

---

## 1. Spec y trazabilidad (obligatorio)

- [ ] Spec validado contra la constitución (Princ. I–X) sin conflictos. *(RT-18)*
- [ ] Bloque de trazabilidad completo: OP2, OT7/OE4, CU-O03/CU-O04. *(RT-19)*
- [ ] Historias de usuario y modelo Fact-Dim declarados por CU-O. *(Princ. IV)*
- [ ] `speckit-analyze` sin inconsistencias con `000-general` ni `ingesta-datos`.

## 2. Calidad de datos (obligatorio)

- [ ] **Suite Great Expectations PREVIA pasando** sobre staging (clave única, no-nulos, dominios, conteo). *(Princ. V, RF-201)*
- [ ] **Suite Great Expectations POSTERIOR pasando** sobre el DW StarRocks. *(RF-203)*
- [ ] Fail-fast verificado: expectativa fallida detiene el pipeline y bloquea la carga/promoción. *(RF-202, RN-301, RN-302)*
- [ ] Calidad del DW ≥ 98% de registros válidos. *(RNF-203, RT-08)*

## 3. Transformación y linaje (obligatorio)

- [ ] **Tests DBT pasando**: `unique`, `not_null`, `relationships`, `accepted_values` en columnas clave. *(Princ. VI, RF-207)*
- [ ] Toda transformación es modelo DBT versionado; 0 SQL imperativo suelto. *(RN-303, RNF-204)*
- [ ] Integridad referencial Fact→Dim verificada (sin hechos huérfanos). *(RN-304)*
- [ ] **Linaje documentado** en `dbt docs`: cada columna Fact-Dim rastreada a su origen. *(Princ. VII, RF-210, RN-306)*

## 4. Formato y capas (obligatorio)

- [ ] El ETL lee de Parquet/PocketBase y escribe en StarRocks; **no** alimenta ClickHouse directamente. *(RT-01, RT-02)*
- [ ] Idempotencia verificada: reproceso incremental sin duplicar hechos. *(RNF-202, CA-207)*

## 5. Orquestación y contenedores (obligatorio)

- [ ] Tramo `GE previa → DBT → GE posterior` integrado en `dag_pipeline_diario` en el orden fijo. *(RT-03)*
- [ ] **`docker compose up` levanta** runner DBT/GE + StarRocks; imágenes con versión fija. *(Princ. VIII, RT-17)*

## 6. Funcionalidad (criterios de aceptación)

- [ ] CA-201 GE previa pasa antes del ETL.
- [ ] CA-202 expectativa fallida detiene el pipeline.
- [ ] CA-203 DW contiene los Fact/Dim del alcance vía DBT.
- [ ] CA-204 tests DBT pasan.
- [ ] CA-205 GE posterior pasa antes de agregaciones.
- [ ] CA-206 `dbt docs` muestra linaje completo.
- [ ] CA-207 reejecución sin duplicados.
- [ ] CA-208 reportes de calidad y de ejecución generados.

## 7. Observabilidad y alertas

- [ ] Eventos de fallo de calidad/ETL llegan a `alertas` (OP9). *(RT-16)*
- [ ] Métricas de ejecución expuestas a `observabilidad` (OP7).
