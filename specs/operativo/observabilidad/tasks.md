# observabilidad · Tareas (speckit-tasks)

> Paquete: `observabilidad` · OP7 · CU-O11. Tareas atómicas ordenadas por dependencia.
> Marca `[x]` al completar. Citan RF/RN/CA de [observabilidad-spec.md](observabilidad-spec.md).

> **Sesión OP7/OP8/OP9 (2026-06-29).** Implementado `observabilidad/monitor.py`:
> sonda real de uptime/latencia de los servicios del pipeline (StarRocks/ClickHouse/
> PocketBase), consolidación `uptime=operativo/total×100`, persistencia idempotente en
> `fact_disponibilidad` (DELETE período + INSERT por región), incidentes con duración y
> región en PocketBase, evaluación de SLO y **señal a `alertas`** (bus `senales_alerta`).
> Tarea `observabilidad` en `dag_pipeline_diario` (tras gate DW, antes de agregaciones).
> Cubierto por `tests/test_alertas.py`. Pendiente: stack Prometheus/Grafana y arranque
> end-to-end en Docker.

---

## A. CU-O11 — Monitorear uptime y latencia

- [x] **T-01** Instrumentar cada servicio (ingesta, ETL, API, dashboards) con métricas y health checks. *(RF-701, RF-705)* — sondas reales en `observabilidad/monitor.py:probar_servicios` + healthchecks Docker.
- [ ] **T-02** Desplegar el recolector (Prometheus) y la visualización (Grafana). *(RF-701)* — pendiente; por ahora recolección por sondas en el `runner`.
- [x] **T-03** Implementar el cálculo de uptime (tiempo_operativo/tiempo_total×100) y latencia promedio por región. *(RF-702)* — `consolidar()` + `filas_disponibilidad()`.
- [x] **T-04** Implementar el registro de mediciones en `Fact_Disponibilidad`. *(RF-703)* — `persistir_disponibilidad()` (idempotente por período).
- [x] **T-05** Configurar SLO/umbrales (uptime > 99.9%, latencia < 200 ms). *(RN-801)* — `UPTIME_SLO_PCT`/`LATENCIA_SLO_MS`.
- [x] **T-06** Implementar la señal a `alertas` ante incumplimiento de SLO. *(RF-704, RN-802)* — `evaluar_slo()` + `emitir_senales()` → `models_alertas.emitir_senal`.
- [x] **T-07** Conservar historial de incidentes para SLA mensual. *(RF-706)* — `incidentes_de()` + `registrar_incidentes()` (colección `incidentes`).

## B. Pruebas (incluye casos de error)

- [x] **T-08** Prueba: medición nominal calcula y registra uptime/latencia en `Fact_Disponibilidad`. *(CA-701, Esc-701)* — `test_medicion_nominal_persiste_filas`.
- [x] **T-09** Prueba: uptime < 99.9% → estado `INCUMPLIDO` + señal a `alertas`. *(CA-702, Esc-702)* — `test_slo_incumplido_emite_senal`.
- [x] **T-10** Prueba: latencia > 200 ms en una región → señal a `alertas`. *(Esc-703)* — cubierto por `test_slo_incumplido_emite_senal`.
- [x] **T-11** Prueba: health check fallido → servicio `CAIDO`, incidente registrado y señalado. *(Esc-704)* — `test_incidente_con_duracion_y_region`.
- [ ] **T-12** Prueba: la recolección no degrada el rendimiento monitoreado. *(Esc-705, RNF-703)* — pendiente benchmark; mitigado por muestreo acotado y timeouts.

## C. Capas, contenedores y cierre

- [x] **T-13** Confirmar que el dashboard de disponibilidad lee agregados de ClickHouse. *(RN-803, CA-705)* — `agg_reporte_diario`/`agg_bsc_series` ← `fact_disponibilidad`; populate transporta a ClickHouse.
- [x] **T-14** Verificar health checks de cada componente del `docker-compose`. *(CA-703)* — `docker-compose.yml:23,44`.
- [ ] **T-15** Contenedorizar el stack de observabilidad (versiones fijas). *(RNF-704, RT-17)* — corre en el `runner` (imagen fija); falta stack Prometheus/Grafana dedicado.
- [ ] **T-16** Verificar arranque con `docker compose up`. *(RT-17)* — pendiente arranque end-to-end.
- [x] **T-17** Validar spec contra constitución y completar [checklist.md](checklist.md). *(RT-18, RT-19)*
