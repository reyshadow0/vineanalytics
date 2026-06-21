# alertas · Checklist — Definición de Terminado (speckit-checklist)

> Paquete: `alertas` · OP9 · CU-O13. No se integra hasta marcar todos los ítems.
> Verifica contra [alertas-spec.md](alertas-spec.md) y la
> [constitución](../../../.specify/memory/constitution.md).

---

## 1. Spec y trazabilidad (obligatorio)

- [ ] Spec validado contra la constitución sin conflictos. *(RT-18)*
- [ ] Bloque de trazabilidad completo: OP9, OT8/OE4, CU-O13. *(RT-19)*
- [ ] Historias de usuario y modelo Fact-Dim (`Fact_Retencion`, `Fact_Precio_Mercado`) declarados. *(Princ. IV)*
- [ ] `speckit-analyze` sin inconsistencias con los paquetes emisores y `000-general`.

## 2. Regla transversal de alertas (obligatorio)

- [ ] **Toda condición RT-16** (fallo de ingesta, caída de uptime, error de API) genera alerta. *(Princ. X, RN-1001)*
- [ ] Churn sobre umbral → alerta `critical` a Customer Success. *(RN-1002)*
- [ ] Precio fuera de rango → alerta de anomalía. *(RN-1003)*

## 3. Robustez (obligatorio)

- [ ] Deduplicación/agrupación anti-tormenta verificada. *(RN-1004, RNF-903)*
- [ ] Entrega fiable: ninguna señal de incumplimiento se pierde. *(RNF-902)*
- [ ] Ciclo de vida de la alerta funcional (abierta→reconocida→resuelta/silenciada). *(RF-907)*

## 4. Capas y registro (obligatorio)

- [ ] Lecturas desde el pipeline (DW/agregaciones), sin saltos de capa. *(RT-01, RN-1006)*
- [ ] Toda alerta registrada y auditable con tipo/severidad/causa/estado. *(RN-1005, RF-904)*

## 5. Contenedores (obligatorio)

- [ ] **`docker compose up` levanta** el servicio de alertas; imagen con versión fija. *(Princ. VIII, RT-17)*

## 6. Funcionalidad (criterios de aceptación)

- [ ] CA-1001 churn → alerta `critical` a CS.
- [ ] CA-1002 precio anómalo → alerta.
- [ ] CA-1003 uptime/ingesta/API → alerta.
- [ ] CA-1004 alerta clasificada y registrada.
- [ ] CA-1005 dedup/agrupación.
- [ ] CA-1006 ciclo de vida.

## 7. Integración

- [ ] Recibe señales de OP1, OP4, OP6, OP7, OP8. *(RF-902)*
- [ ] Expone el reporte de alertas a `reportes-operativos` (OP11).
