# alertas · Tareas (speckit-tasks)

> Paquete: `alertas` · OP9 · CU-O13. Tareas atómicas ordenadas por dependencia.
> Marca `[x]` al completar. Citan RF/RN/CA de [alertas-spec.md](alertas-spec.md).

---

## A. CU-O13 — Generar alerta (churn / anomalía de precio)

- [ ] **T-01** Definir el contrato/esquema común de señales de entrada. *(RF-902)*
- [ ] **T-02** Implementar el motor de umbral/anomalías sobre churn (`Fact_Retencion`) y precio (`Fact_Precio_Mercado`). *(RF-901)*
- [ ] **T-03** Implementar la recepción de señales de `observabilidad`, `ingesta-datos`, `api-publica`, `captacion-conversion`, `machine-learning`. *(RF-902, RN-1001)*
- [ ] **T-04** Implementar la clasificación por tipo/severidad/causa. *(RF-903)*
- [ ] **T-05** Implementar deduplicación/agrupación anti-tormenta. *(RF-906, RN-1004)*
- [ ] **T-06** Implementar el registro de alertas y su ciclo de vida (abierta→reconocida→resuelta/silenciada). *(RF-904, RF-907)*
- [ ] **T-07** Implementar el enrutamiento/notificación por responsable (CS/DevOps/Ing. datos). *(RF-905)*
- [ ] **T-08** Garantizar entrega fiable con reintentos. *(RNF-902)*

## B. Pruebas (incluye casos de error)

- [ ] **T-09** Prueba: churn sobre umbral → alerta `critical` a Customer Success, registrada. *(CA-1001, Esc-1001)*
- [ ] **T-10** Prueba: precio fuera de rango → alerta de anomalía a Ingeniería de datos. *(CA-1002, Esc-1002)*
- [ ] **T-11** Prueba: caída de uptime / fallo de ingesta / pico de errores API → alerta. *(CA-1003, Esc-1003, Esc-1004)*
- [ ] **T-12** Prueba: cada alerta clasificada y registrada (tipo/severidad/causa). *(CA-1004)*
- [ ] **T-13** Prueba: señales equivalentes se deduplican/agrupan (anti-tormenta). *(CA-1005, Esc-1005)*
- [ ] **T-14** Prueba: fallo de entrega se reintenta sin perder la alerta. *(Esc-1006, RNF-902)*
- [ ] **T-15** Prueba: ciclo de vida abierta→reconocida→resuelta/silenciada. *(CA-1006)*

## C. Capas, contenedores y cierre

- [ ] **T-16** Confirmar que las lecturas vienen del pipeline (DW/agregaciones), sin saltos de capa. *(RN-1006, RT-01)*
- [ ] **T-17** Exponer el reporte de alertas para `reportes-operativos` (OP11). *(salidas §8)*
- [ ] **T-18** Contenedorizar el servicio de alertas en `docker-compose.yml` (versión fija). *(RNF-904, RT-17)*
- [ ] **T-19** Verificar arranque con `docker compose up`. *(RT-17)*
- [ ] **T-20** Validar spec contra constitución y completar [checklist.md](checklist.md). *(RT-18, RT-19)*
