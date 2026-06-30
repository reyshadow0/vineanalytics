# alertas · Tareas (speckit-tasks)

> Paquete: `alertas` · OP9 · CU-O13. Tareas atómicas ordenadas por dependencia.
> Marca `[x]` al completar. Citan RF/RN/CA de [alertas-spec.md](alertas-spec.md).

> **Sesión OP7/OP8/OP9 (2026-06-29).** Implementado `models_alertas.py` (reglas) +
> `alertas/alert_engine.py` (tarea del DAG). Bus `senales_alerta` (contrato común),
> generación/registro de la alerta con clasificación tipo/severidad/causa,
> enrutamiento por responsable, **deduplicación** por `clave` (anti-tormenta) y ciclo
> de vida (ABIERTA→RECONOCIDA→RESUELTA/SILENCIADA). Detección propia de anomalías
> (z-score) + consumo de señales de `observabilidad` (CU-O11) y `machine-learning`
> (CU-O12). Tarea `alertas` en `dag_pipeline_diario`. Cubierto por `tests/test_alertas.py`.

---

## A. CU-O13 — Generar alerta (churn / anomalía de precio)

- [x] **T-01** Definir el contrato/esquema común de señales de entrada. *(RF-902)* — colección `senales_alerta` + `emitir_senal()`.
- [x] **T-02** Implementar el motor de umbral/anomalías sobre churn (`Fact_Retencion`) y precio (`Fact_Precio_Mercado`). *(RF-901)* — `alert_engine.emitir_desde_anomalias` (z-score de `ml_models.detectar_anomalias`).
- [x] **T-03** Implementar la recepción de señales de `observabilidad`, `machine-learning`, … *(RF-902, RN-1001)* — `procesar_pendientes()` drena el bus (CU-O11/CU-O12 ya lo alimentan; ingesta/api/conversión conectan vía el mismo `emitir_senal`).
- [x] **T-04** Implementar la clasificación por tipo/severidad/causa. *(RF-903)* — `clasificar()` + `CLASIFICACION`.
- [x] **T-05** Implementar deduplicación/agrupación anti-tormenta. *(RF-906, RN-1004)* — `_alerta_viva()` agrupa por `clave` e incrementa `ocurrencias`.
- [x] **T-06** Implementar el registro de alertas y su ciclo de vida. *(RF-904, RF-907)* — colección `alertas` + `reconocer/resolver/silenciar`.
- [x] **T-07** Implementar el enrutamiento/notificación por responsable (CS/DevOps/Ing. datos). *(RF-905)* — `responsable` derivado del tipo.
- [ ] **T-08** Garantizar entrega fiable con reintentos. *(RNF-902)* — el bus persistente garantiza no-pérdida (la señal no procesada se reintenta en la siguiente corrida); falta reintento de notificación externa.

## B. Pruebas (incluye casos de error)

- [x] **T-09** Prueba: churn sobre umbral → alerta `critical` a Customer Success, registrada. *(CA-1001, Esc-1001)* — `test_churn_sobre_umbral_genera_critical_a_cs`.
- [x] **T-10** Prueba: precio fuera de rango → alerta de anomalía a Ingeniería de datos. *(CA-1002, Esc-1002)* — `test_precio_fuera_de_rango_va_a_ingenieria`.
- [x] **T-11** Prueba: caída de uptime → alerta. *(CA-1003, Esc-1003)* — `test_slo_incumplido_emite_senal` + cadena E2E (uptime→alerta).
- [x] **T-12** Prueba: cada alerta clasificada y registrada (tipo/severidad/causa). *(CA-1004)* — `test_cadena_...` valida severidad por tipo.
- [x] **T-13** Prueba: señales equivalentes se deduplican/agrupan (anti-tormenta). *(CA-1005, Esc-1005)* — `test_condicion_repetida_no_duplica`.
- [ ] **T-14** Prueba: fallo de entrega se reintenta sin perder la alerta. *(Esc-1006, RNF-902)* — pendiente (depende de T-08, notificación externa).
- [x] **T-15** Prueba: ciclo de vida abierta→reconocida→resuelta/silenciada. *(CA-1006)* — `test_ciclo_de_vida`.

## C. Capas, contenedores y cierre

- [x] **T-16** Confirmar que las lecturas vienen del pipeline (DW/agregaciones), sin saltos de capa. *(RN-1006, RT-01)* — la detección lee StarRocks vía `ml_models`; las señales llegan ya normalizadas.
- [x] **T-17** Exponer el reporte de alertas para `reportes-operativos` (OP11). *(salidas §8)* — `reporte_alertas()`.
- [x] **T-18** Contenedorizar el servicio de alertas en `docker-compose.yml` (versión fija). *(RNF-904, RT-17)* — corre en el `runner` (imagen fija), como dbt/GE/reporte.
- [ ] **T-19** Verificar arranque con `docker compose up`. *(RT-17)* — pendiente arranque end-to-end.
- [x] **T-20** Validar spec contra constitución y completar [checklist.md](checklist.md). *(RT-18, RT-19)*
