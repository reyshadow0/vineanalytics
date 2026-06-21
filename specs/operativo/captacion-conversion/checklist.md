# captacion-conversion · Checklist — Definición de Terminado (speckit-checklist)

> Paquete: `captacion-conversion` · OP6 · CU-O09, CU-O10. No se integra hasta marcar
> todos los ítems. Verifica contra
> [captacion-conversion-spec.md](captacion-conversion-spec.md) y la
> [constitución](../../../.specify/memory/constitution.md).

---

## 1. Spec y trazabilidad (obligatorio)

- [ ] Spec validado contra la constitución sin conflictos. *(RT-18)*
- [ ] Bloque de trazabilidad completo: OP6, OT1/OT2/OE1, CU-O09/CU-O10. *(RT-19)*
- [ ] Historias de usuario y modelo Fact-Dim declarados por CU-O. *(Princ. IV)*
- [ ] `speckit-analyze` sin inconsistencias con `000-general`, `suscripciones`, `alertas`.

## 2. Reglas de negocio (obligatorio)

- [ ] **Deduplicación de leads** verificada. *(Princ. X, RN-702)*
- [ ] **Atribución única** de cada conversión a una campaña/canal. *(RN-703)*
- [ ] CAC y tasa de conversión con fórmulas canónicas (§9.9). *(RN-704)*
- [ ] Conversión a cliente origina alta en `suscripciones` sin duplicar cuenta. *(RN-705)*

## 3. Capas y registro (obligatorio)

- [ ] Eventos de campaña/conversión llegan al DW **solo vía ETL**. *(RT-01, RNF-603)*
- [ ] Linaje de `Fact_Campana` y `Fact_Conversion` documentado en `dbt docs`. *(Princ. VII, RT-14)*

## 4. Calidad de datos

- [ ] Suite GE sobre `Fact_Campana`/`Fact_Conversion` (unicidad lead, no-nulos, gasto ≥ 0) — verificación con `etl-calidad`. *(Princ. V)*

## 5. Automatización y contenedores (obligatorio)

- [ ] Campañas ejecutadas de forma automatizada vía Airflow. *(RNF-601, OT1)*
- [ ] **`docker compose up` levanta** el orquestador; imagen con versión fija. *(Princ. VIII, RT-17)*

## 6. Funcionalidad (criterios de aceptación)

- [ ] CA-601 campaña programada puebla `Fact_Campana`.
- [ ] CA-602 leads deduplicados.
- [ ] CA-603 conversión atribuida en `Fact_Conversion`.
- [ ] CA-604 CAC y conversión calculados.
- [ ] CA-605 conversión a cliente → alta sin duplicar.
- [ ] CA-606 caída de conversión genera alerta.

## 7. Observabilidad y alertas

- [ ] Caída de conversión sobre umbral dispara alerta (CU-O13). *(RN-706, RT-16)*
- [ ] Métricas de campañas expuestas a `observabilidad` (OP7).
- [ ] Privacidad de prospectos respetada. *(RNF-605)*
