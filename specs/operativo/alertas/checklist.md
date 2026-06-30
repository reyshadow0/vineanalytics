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

- [x] **Condición RT-16** (caída de uptime / latencia, anomalías) genera alerta. *(Princ. X, RN-1001)* — observabilidad emite SLO; el motor de anomalías cubre churn/errores/latencia. Ingesta/API enchufan al mismo bus `emitir_senal` (pendiente cablear emisores OP1/OP4).
- [x] Churn sobre umbral → alerta `critical` a Customer Success. *(RN-1002)* — `clasificar("churn")`.
- [x] Precio fuera de rango → alerta de anomalía. *(RN-1003)* — `clasificar("precio")` → Ingeniería de datos.

## 3. Robustez (obligatorio)

- [x] Deduplicación/agrupación anti-tormenta verificada. *(RN-1004, RNF-903)* — `test_condicion_repetida_no_duplica`.
- [x] Entrega fiable: ninguna señal de incumplimiento se pierde. *(RNF-902)* — bus persistente; la señal no procesada se reintenta en la siguiente corrida (falta reintento de notificación externa).
- [x] Ciclo de vida de la alerta funcional (abierta→reconocida→resuelta/silenciada). *(RF-907)* — `test_ciclo_de_vida`.

## 4. Capas y registro (obligatorio)

- [x] Lecturas desde el pipeline (DW/agregaciones), sin saltos de capa. *(RT-01, RN-1006)* — detección sobre StarRocks vía `ml_models`; alertas no salta de capa.
- [x] Toda alerta registrada y auditable con tipo/severidad/causa/estado. *(RN-1005, RF-904)* — colección `alertas`.

## 5. Contenedores (obligatorio)

- [ ] **`docker compose up` levanta** el servicio de alertas; imagen con versión fija. *(Princ. VIII, RT-17)* — corre en el `runner` (imagen fija); falta arranque end-to-end.

## 6. Funcionalidad (criterios de aceptación)

- [x] CA-1001 churn → alerta `critical` a CS.
- [x] CA-1002 precio anómalo → alerta.
- [x] CA-1003 uptime/ingesta/API → alerta. — uptime/latencia cubiertos; ingesta/API quedan listos al cablear sus emisores.
- [x] CA-1004 alerta clasificada y registrada.
- [x] CA-1005 dedup/agrupación.
- [x] CA-1006 ciclo de vida.

## 7. Integración

- [x] Recibe señales de OP7, OP8 (y bus abierto para OP1/OP4/OP6). *(RF-902)* — `senales_alerta` + `emitir_senal`.
- [x] Expone el reporte de alertas a `reportes-operativos` (OP11). — `reporte_alertas()`.
