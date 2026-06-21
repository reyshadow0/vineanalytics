# reportes-operativos · Tareas (speckit-tasks)

> Paquete: `reportes-operativos` · OP11 · CU-O16. Tareas atómicas ordenadas por
> dependencia. Marca `[x]` al completar. Citan RF/RN/CA de
> [reportes-operativos-spec.md](reportes-operativos-spec.md).

---

## A. CU-O16 — Generar reporte operativo diario

- [ ] **T-01** Definir el contenido y formato del reporte diario (secciones: ingesta, API, uso, incidentes, alertas). *(RF-1101, RF-1105)*
- [ ] **T-02** Conectar el generador a ClickHouse en modo solo lectura. *(RF-1102, RN-1202)*
- [ ] **T-03** Implementar el gate de calidad del día (verificar sello CU-O04). *(RF-1104, RN-1201)*
- [ ] **T-04** Implementar la consolidación de métricas por `Dim_Tiempo` (`Fact_Uso_Plataforma`, `Fact_Consumo_API`, incidentes, alertas). *(RF-1101)*
- [ ] **T-05** Programar la generación automática al cierre del DAG (último paso). *(RF-1103, RN-1203)*
- [ ] **T-06** Implementar el archivado por fecha y la reproducibilidad. *(RF-1105, RN-1205)*
- [ ] **T-07** Añadir trazabilidad de cada cifra a su agregación de origen. *(RN-1204)*
- [ ] **T-08** Dejar el reporte disponible como insumo para consolidación mensual/estratégica. *(RF-1106)*

## B. Pruebas (incluye casos de error)

- [ ] **T-09** Prueba: reporte nominal se genera al cierre del DAG desde ClickHouse y se archiva. *(CA-1201, CA-1202, Esc-1201)*
- [ ] **T-10** Prueba: día con calidad fallida → `BLOQUEADO_SIN_CALIDAD`, sin reporte definitivo. *(CA-1203, Esc-1202)*
- [ ] **T-11** Prueba: intento de calcular desde StarRocks/PocketBase es rechazado. *(Esc-1203, RN-1202)*
- [ ] **T-12** Prueba: cifra inconsistente con ClickHouse se detecta por trazabilidad. *(Esc-1204, RN-1204)*
- [ ] **T-13** Prueba: regenerar el reporte de una fecha produce las mismas cifras. *(CA-1205, Esc-1205)*

## C. Orquestación, contenedores y cierre

- [ ] **T-14** Integrar la tarea de reporte como **último paso** del `dag_pipeline_diario`. *(RN-1203, RT-03)*
- [ ] **T-15** Emitir evento de generación (éxito/fallo) a `observabilidad`/`alertas`. *(salidas §8)*
- [ ] **T-16** Contenedorizar el generador en `docker-compose.yml` (versión fija). *(RNF-1103, RT-17)*
- [ ] **T-17** Verificar arranque con `docker compose up`. *(RT-17)*
- [ ] **T-18** Validar spec contra constitución y completar [checklist.md](checklist.md). *(RT-18, RT-19)*
