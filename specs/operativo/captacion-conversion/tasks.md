# captacion-conversion · Tareas (speckit-tasks)

> Paquete: `captacion-conversion` · OP6 · CU-O09, CU-O10. Tareas atómicas ordenadas
> por dependencia. Marca `[x]` al completar. Citan RF/RN/CA de
> [captacion-conversion-spec.md](captacion-conversion-spec.md).

---

> **Estado (sesión OP6, 2026-06-30):** CU-O09 y CU-O10 implementados con lógica real
> (no sintética). Módulos: `models_captacion.py`, `campaigns_runner.py`; colecciones en
> `db/pb_setup.py`; endpoints en `app.py`; tarea `captacion_ejecucion` en el DAG;
> pruebas en `tests/test_captacion.py` (9, FakePB, sin Docker). Persistencia 100 %
> PocketBase (eventos → `Fact_Campana`/`Fact_Conversion` vía ETL, no se saltan capas).

## A. CU-O09 — Ejecutar campaña de captación automatizada

- [x] **T-01** Implementar la configuración de campaña (`Dim_Campana`, `Dim_Canal_Adquisicion`, `Dim_Mercado`, presupuesto). *(RF-601, RN-701)* — `models_captacion.crear_campana` (exige canal+mercado existentes).
- [x] **T-02** Implementar la ejecución automatizada vía Airflow según programación. *(RF-602, RNF-601)* — `ejecutar_pendientes`/`campaigns_runner.py` + tarea `captacion_ejecucion` del DAG.
- [x] **T-03** Capturar y registrar métricas en `Fact_Campana` (impresiones, clics, gasto, leads). *(RF-603)* — feed `eventos_campana` (proyectado por ETL).
- [x] **T-04** Implementar deduplicación de leads. *(RF-604, RN-702)* — `registrar_lead` (dedup por clave natural).
- [x] **T-05** Prueba: campaña programada se ejecuta automáticamente y puebla `Fact_Campana`. *(CA-601, Esc-601)* — `test_campana_ejecutada_registra_metricas`.
- [x] **T-06** Prueba: lead duplicado se cuenta una sola vez. *(CA-602, Esc-602)* — `test_lead_deduplicado`.

## B. CU-O10 — Registrar conversión del embudo

- [x] **T-07** Implementar el registro de conversiones en `Fact_Conversion` (etapa, fuente, resultado). *(RF-605)* — `registrar_conversion` (feed `eventos_conversion`).
- [x] **T-08** Implementar el motor de atribución único (campaña/canal). *(RF-606, RN-703)* — atribución first-touch a la campaña/canal de origen del lead.
- [x] **T-09** Calcular insumos de CAC y tasa de conversión (fórmulas canónicas). *(RF-607, RN-704)* — `indicadores_captacion`.
- [x] **T-10** Integrar la entrega de conversión→alta a `suscripciones` (sin duplicar cuenta). *(RF-608, RN-705)* — `_entregar_alta` reutiliza `models_clientes.crear_cliente` (dedup RN-601).
- [x] **T-11** Prueba: conversión nominal queda en `Fact_Conversion` atribuida y se entrega a OP5. *(CA-603, CA-605, Esc-603)* — `test_conversion_atribuida_*` + `test_conversion_cliente_origina_alta_sin_duplicar`.
- [x] **T-12** Prueba: doble atribución resuelta a una sola campaña. *(Esc-604)* — `test_conversion_atribuida_a_campana_de_origen` (B no re-atribuye).
- [x] **T-13** Prueba: conversión a cliente con cuenta existente no duplica alta. *(Esc-605, RN-601)* — `test_conversion_cliente_origina_alta_sin_duplicar`.

## C. Alertas, contenedores y cierre

- [x] **T-14** Disparar alerta ante caída de conversión sobre umbral (CU-O13). *(RN-706, CA-606, Esc-606)* — `evaluar_caida_conversion` emite señal `conversion` al bus `senales_alerta`; `test_caida_conversion_emite_senal`.
- [ ] **T-15** Asegurar tratamiento de datos de prospectos conforme a privacidad. *(RNF-605)* — parcial: el lead solo guarda clave natural + etiqueta; falta política de anonimización/retención formal.
- [x] **T-16** Confirmar que los eventos llegan al DW solo vía ETL. *(RNF-603, RT-01)* — la app escribe únicamente en PocketBase; el DW se nutre vía ETL (proyección pendiente, igual que CU-O08).
- [x] **T-17** Contenedorizar el orquestador en `docker-compose.yml` (versión fija). *(RNF-604, RT-17)* — reutiliza el contenedor `runner` (imagen fija) vía la tarea del DAG; sin `:latest` ni contenedor nuevo.
- [ ] **T-18** Verificar arranque con `docker compose up`. *(RT-17)* — pendiente (no se levantó Docker en la sesión).
- [ ] **T-19** Validar spec contra constitución y completar [checklist.md](checklist.md). *(RT-18, RT-19)* — checklist actualizado; `speckit-analyze` pendiente.
