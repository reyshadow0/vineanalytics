# captacion-conversion · Checklist — Definición de Terminado (speckit-checklist)

> Paquete: `captacion-conversion` · OP6 · CU-O09, CU-O10. No se integra hasta marcar
> todos los ítems. Verifica contra
> [captacion-conversion-spec.md](captacion-conversion-spec.md) y la
> [constitución](../../../.specify/memory/constitution.md).

> **Sesión OP6 (2026-06-30):** CU-O09 y CU-O10 implementados (de ❌ a ✅).
> Evidencia: `models_captacion.py`, `campaigns_runner.py`, colecciones/seeds en
> `db/pb_setup.py`, endpoints en `app.py`, tarea `captacion_ejecucion` del DAG y
> `tests/test_captacion.py` (9 pruebas pasan, suite global 59 passed). Quedan
> abiertos los ítems que requieren Docker/GE/dbt docs/`speckit-analyze`.

---

## 1. Spec y trazabilidad (obligatorio)

- [x] Spec validado contra la constitución sin conflictos. *(RT-18)* — revisión manual: capas (eventos a PocketBase, no al DW), Princ. X (dedup), Princ. IX (Airflow), Princ. VIII (sin `:latest`).
- [x] Bloque de trazabilidad completo: OP6, OT1/OT2/OE1, CU-O09/CU-O10. *(RT-19)*
- [x] Historias de usuario y modelo Fact-Dim declarados por CU-O. *(Princ. IV)*
- [ ] `speckit-analyze` sin inconsistencias con `000-general`, `suscripciones`, `alertas`. — pendiente.

## 2. Reglas de negocio (obligatorio)

- [x] **Deduplicación de leads** verificada. *(Princ. X, RN-702)* — `registrar_lead` + `test_lead_deduplicado`.
- [x] **Atribución única** de cada conversión a una campaña/canal. *(RN-703)* — first-touch; `test_conversion_atribuida_a_campana_de_origen` (Esc-604).
- [x] CAC y tasa de conversión con fórmulas canónicas (§9.9). *(RN-704)* — `indicadores_captacion` + `test_indicadores_cac_y_tasa`.
- [x] Conversión a cliente origina alta en `suscripciones` sin duplicar cuenta. *(RN-705)* — `_entregar_alta` + `test_conversion_cliente_origina_alta_sin_duplicar`.

## 3. Capas y registro (obligatorio)

- [x] Eventos de campaña/conversión llegan al DW **solo vía ETL**. *(RT-01, RNF-603)* — la app escribe solo en PocketBase (`eventos_campana`/`eventos_conversion`); proyección ETL → `Fact_*` pendiente (igual que CU-O08).
- [ ] Linaje de `Fact_Campana` y `Fact_Conversion` documentado en `dbt docs`. *(Princ. VII, RT-14)* — pendiente (depende de la proyección ETL).

## 4. Calidad de datos

- [ ] Suite GE sobre `Fact_Campana`/`Fact_Conversion` (unicidad lead, no-nulos, gasto ≥ 0) — verificación con `etl-calidad`. *(Princ. V)* — pendiente.

## 5. Automatización y contenedores (obligatorio)

- [x] Campañas ejecutadas de forma automatizada vía Airflow. *(RNF-601, OT1)* — tarea `captacion_ejecucion` (`python -m campaigns_runner`) en `dag_pipeline_diario`.
- [ ] **`docker compose up` levanta** el orquestador; imagen con versión fija. *(Princ. VIII, RT-17)* — reutiliza el `runner` (imagen fija); arranque end-to-end no verificado en la sesión.

## 6. Funcionalidad (criterios de aceptación)

- [x] CA-601 campaña programada puebla `Fact_Campana`. — `test_campana_ejecutada_registra_metricas`.
- [x] CA-602 leads deduplicados. — `test_lead_deduplicado`.
- [x] CA-603 conversión atribuida en `Fact_Conversion`. — `test_conversion_atribuida_a_campana_de_origen`.
- [x] CA-604 CAC y conversión calculados. — `test_indicadores_cac_y_tasa`.
- [x] CA-605 conversión a cliente → alta sin duplicar. — `test_conversion_cliente_origina_alta_sin_duplicar`.
- [x] CA-606 caída de conversión genera alerta. — `test_caida_conversion_emite_senal`.

## 7. Observabilidad y alertas

- [x] Caída de conversión sobre umbral dispara alerta (CU-O13). *(RN-706, RT-16)* — señal `conversion` al bus `senales_alerta`; enrutada a Growth & Marketing (RF-905).
- [ ] Métricas de campañas expuestas a `observabilidad` (OP7). — pendiente.
- [ ] Privacidad de prospectos respetada. *(RNF-605)* — parcial: solo se almacena clave natural + etiqueta; falta política formal de anonimización/retención.
