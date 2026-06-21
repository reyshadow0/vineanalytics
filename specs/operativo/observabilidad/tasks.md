# observabilidad · Tareas (speckit-tasks)

> Paquete: `observabilidad` · OP7 · CU-O11. Tareas atómicas ordenadas por dependencia.
> Marca `[x]` al completar. Citan RF/RN/CA de [observabilidad-spec.md](observabilidad-spec.md).

---

## A. CU-O11 — Monitorear uptime y latencia

- [ ] **T-01** Instrumentar cada servicio (ingesta, ETL, API, dashboards) con métricas y health checks. *(RF-701, RF-705)*
- [ ] **T-02** Desplegar el recolector (Prometheus) y la visualización (Grafana). *(RF-701)*
- [ ] **T-03** Implementar el cálculo de uptime (tiempo_operativo/tiempo_total×100) y latencia promedio por región. *(RF-702)*
- [ ] **T-04** Implementar el registro de mediciones en `Fact_Disponibilidad`. *(RF-703)*
- [ ] **T-05** Configurar SLO/umbrales (uptime > 99.9%, latencia < 200 ms). *(RN-801)*
- [ ] **T-06** Implementar la señal a `alertas` ante incumplimiento de SLO. *(RF-704, RN-802)*
- [ ] **T-07** Conservar historial de incidentes para SLA mensual. *(RF-706)*

## B. Pruebas (incluye casos de error)

- [ ] **T-08** Prueba: medición nominal calcula y registra uptime/latencia en `Fact_Disponibilidad`. *(CA-701, Esc-701)*
- [ ] **T-09** Prueba: uptime < 99.9% → estado `INCUMPLIDO` + señal a `alertas`. *(CA-702, Esc-702)*
- [ ] **T-10** Prueba: latencia > 200 ms en una región → señal a `alertas`. *(Esc-703)*
- [ ] **T-11** Prueba: health check fallido → servicio `CAIDO`, incidente registrado y señalado. *(Esc-704)*
- [ ] **T-12** Prueba: la recolección no degrada el rendimiento monitoreado. *(Esc-705, RNF-703)*

## C. Capas, contenedores y cierre

- [ ] **T-13** Confirmar que el dashboard de disponibilidad lee agregados de ClickHouse. *(RN-803, CA-705)*
- [ ] **T-14** Verificar health checks de cada componente del `docker-compose`. *(CA-703)*
- [ ] **T-15** Contenedorizar el stack de observabilidad (versiones fijas). *(RNF-704, RT-17)*
- [ ] **T-16** Verificar arranque con `docker compose up`. *(RT-17)*
- [ ] **T-17** Validar spec contra constitución y completar [checklist.md](checklist.md). *(RT-18, RT-19)*
