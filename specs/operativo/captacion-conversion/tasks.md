# captacion-conversion · Tareas (speckit-tasks)

> Paquete: `captacion-conversion` · OP6 · CU-O09, CU-O10. Tareas atómicas ordenadas
> por dependencia. Marca `[x]` al completar. Citan RF/RN/CA de
> [captacion-conversion-spec.md](captacion-conversion-spec.md).

---

## A. CU-O09 — Ejecutar campaña de captación automatizada

- [ ] **T-01** Implementar la configuración de campaña (`Dim_Campana`, `Dim_Canal_Adquisicion`, `Dim_Mercado`, presupuesto). *(RF-601, RN-701)*
- [ ] **T-02** Implementar la ejecución automatizada vía Airflow según programación. *(RF-602, RNF-601)*
- [ ] **T-03** Capturar y registrar métricas en `Fact_Campana` (impresiones, clics, gasto, leads). *(RF-603)*
- [ ] **T-04** Implementar deduplicación de leads. *(RF-604, RN-702)*
- [ ] **T-05** Prueba: campaña programada se ejecuta automáticamente y puebla `Fact_Campana`. *(CA-601, Esc-601)*
- [ ] **T-06** Prueba: lead duplicado se cuenta una sola vez. *(CA-602, Esc-602)*

## B. CU-O10 — Registrar conversión del embudo

- [ ] **T-07** Implementar el registro de conversiones en `Fact_Conversion` (etapa, fuente, resultado). *(RF-605)*
- [ ] **T-08** Implementar el motor de atribución único (campaña/canal). *(RF-606, RN-703)*
- [ ] **T-09** Calcular insumos de CAC y tasa de conversión (fórmulas canónicas). *(RF-607, RN-704)*
- [ ] **T-10** Integrar la entrega de conversión→alta a `suscripciones` (sin duplicar cuenta). *(RF-608, RN-705)*
- [ ] **T-11** Prueba: conversión nominal queda en `Fact_Conversion` atribuida y se entrega a OP5. *(CA-603, CA-605, Esc-603)*
- [ ] **T-12** Prueba: doble atribución resuelta a una sola campaña. *(Esc-604)*
- [ ] **T-13** Prueba: conversión a cliente con cuenta existente no duplica alta. *(Esc-605, RN-601)*

## C. Alertas, contenedores y cierre

- [ ] **T-14** Disparar alerta ante caída de conversión sobre umbral (CU-O13). *(RN-706, CA-606, Esc-606)*
- [ ] **T-15** Asegurar tratamiento de datos de prospectos conforme a privacidad. *(RNF-605)*
- [ ] **T-16** Confirmar que los eventos llegan al DW solo vía ETL. *(RNF-603, RT-01)*
- [ ] **T-17** Contenedorizar el orquestador en `docker-compose.yml` (versión fija). *(RNF-604, RT-17)*
- [ ] **T-18** Verificar arranque con `docker compose up`. *(RT-17)*
- [ ] **T-19** Validar spec contra constitución y completar [checklist.md](checklist.md). *(RT-18, RT-19)*
