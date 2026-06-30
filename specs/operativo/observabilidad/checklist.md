# observabilidad · Checklist — Definición de Terminado (speckit-checklist)

> Paquete: `observabilidad` · OP7 · CU-O11. No se integra hasta marcar todos los
> ítems. Verifica contra [observabilidad-spec.md](observabilidad-spec.md) y la
> [constitución](../../../.specify/memory/constitution.md).

---

## 1. Spec y trazabilidad (obligatorio)

- [ ] Spec validado contra la constitución sin conflictos. *(RT-18)*
- [ ] Bloque de trazabilidad completo: OP7, OT5/OT6/OE3, CU-O11. *(RT-19)*
- [ ] Historia(s) de usuario y modelo Fact-Dim (`Fact_Disponibilidad`, `Dim_Mercado`, `Dim_Tiempo`) declarados. *(Princ. IV)*
- [ ] `speckit-analyze` sin inconsistencias con `000-general`, `alertas`, `etl-calidad`.

## 2. SLO y alertas (obligatorio)

- [x] SLO definidos: uptime > 99.9% mensual, latencia < 200 ms promedio. *(RN-801)* — `monitor.UPTIME_SLO_PCT`/`LATENCIA_SLO_MS`.
- [x] Incumplir SLO **emite señal** a `alertas` (caída de uptime / latencia elevada). *(Princ. X, RN-802, RT-16)* — `evaluar_slo()`+`emitir_senales()`.
- [x] Confirmado que el paquete mide y señala, **no** remedia. *(RN-805)* — el monitor solo persiste + señala; la respuesta es de DevOps.

## 3. Capas y registro (obligatorio)

- [x] Mediciones registradas en `Fact_Disponibilidad`; llegan al DW. *(RT-01, RN-803)* — `persistir_disponibilidad()` escribe StarRocks; el incidente operacional va a PocketBase.
- [x] Dashboard de disponibilidad lee agregados de **ClickHouse**. *(RN-803, CA-705)* — `agg_*` (DBT) → populate → ClickHouse.
- [ ] Linaje de `Fact_Disponibilidad` documentado en `dbt docs`. *(Princ. VII, RT-14)* — `fact_disponibilidad` es `source` de `agg_reporte_diario`/`agg_bsc_series`; falta `dbt docs` end-to-end.

## 4. Calidad de datos

- [ ] Suite GE sobre `Fact_Disponibilidad` (uptime ∈ [0,100], latencia ≥ 0, no-nulos) — verificación con `etl-calidad`. *(Princ. V)* — pendiente suite GE dedicada; el monitor garantiza uptime∈[0,100] y latencia≥0 por construcción.

## 5. Cobertura y contenedores (obligatorio)

- [x] Cobertura de todos los servicios del pipeline y la API. *(RNF-701)* — sondas a StarRocks/ClickHouse/PocketBase.
- [x] Health checks de cada componente del `docker-compose`. *(CA-703, RF-705)* — `docker-compose.yml:23,44`.
- [ ] **`docker compose up` levanta** el stack de observabilidad; imágenes con versión fija. *(Princ. VIII, RT-17)* — corre en el `runner` (imagen fija); falta arranque end-to-end + Prometheus/Grafana.

## 6. Funcionalidad (criterios de aceptación)

- [x] CA-701 uptime/latencia calculados y registrados.
- [x] CA-702 incumplimiento de SLO → señal.
- [x] CA-703 health checks presentes.
- [x] CA-704 historial permite SLA mensual. — incidentes con `duracion_min`/`region` en PocketBase.
- [x] CA-705 dashboard de disponibilidad lee de ClickHouse.
