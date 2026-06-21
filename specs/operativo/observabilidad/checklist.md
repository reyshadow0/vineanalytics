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

- [ ] SLO definidos: uptime > 99.9% mensual, latencia < 200 ms promedio. *(RN-801)*
- [ ] Incumplir SLO **emite señal** a `alertas` (caída de uptime / latencia elevada). *(Princ. X, RN-802, RT-16)*
- [ ] Confirmado que el paquete mide y señala, **no** remedia. *(RN-805)*

## 3. Capas y registro (obligatorio)

- [ ] Mediciones registradas en `Fact_Disponibilidad`; llegan al DW **solo vía ETL**. *(RT-01, RN-803)*
- [ ] Dashboard de disponibilidad lee agregados de **ClickHouse**. *(RN-803, CA-705)*
- [ ] Linaje de `Fact_Disponibilidad` documentado en `dbt docs`. *(Princ. VII, RT-14)*

## 4. Calidad de datos

- [ ] Suite GE sobre `Fact_Disponibilidad` (uptime ∈ [0,100], latencia ≥ 0, no-nulos) — verificación con `etl-calidad`. *(Princ. V)*

## 5. Cobertura y contenedores (obligatorio)

- [ ] Cobertura de todos los servicios del pipeline y la API. *(RNF-701)*
- [ ] Health checks de cada componente del `docker-compose`. *(CA-703, RF-705)*
- [ ] **`docker compose up` levanta** el stack de observabilidad; imágenes con versión fija. *(Princ. VIII, RT-17)*

## 6. Funcionalidad (criterios de aceptación)

- [ ] CA-701 uptime/latencia calculados y registrados.
- [ ] CA-702 incumplimiento de SLO → señal.
- [ ] CA-703 health checks presentes.
- [ ] CA-704 historial permite SLA mensual.
- [ ] CA-705 dashboard de disponibilidad lee de ClickHouse.
