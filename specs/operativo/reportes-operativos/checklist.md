# reportes-operativos · Checklist — Definición de Terminado (speckit-checklist)

> Paquete: `reportes-operativos` · OP11 · CU-O16. No se integra hasta marcar todos los
> ítems. Verifica contra
> [reportes-operativos-spec.md](reportes-operativos-spec.md) y la
> [constitución](../../../.specify/memory/constitution.md).

---

## 1. Spec y trazabilidad (obligatorio)

- [ ] Spec validado contra la constitución sin conflictos. *(RT-18)*
- [ ] Bloque de trazabilidad completo: OP11, OT7/OE4, CU-O16. *(RT-19)*
- [ ] Historias de usuario y modelo Fact-Dim (`Fact_Uso_Plataforma`, `Fact_Consumo_API`, `Dim_Tiempo`) declarados. *(Princ. IV)*
- [ ] `speckit-analyze` sin inconsistencias con `000-general`, `etl-calidad`, paquetes fuente.

## 2. Regla crítica de negocio (obligatorio)

- [ ] **El reporte se construye solo sobre datos validados por calidad (CU-O04)**; día sin calidad → bloqueado. *(Princ. X, RT-15, RN-1201)*
- [ ] Verificado el bloqueo `BLOQUEADO_SIN_CALIDAD`. *(CA-1203, Esc-1202)*

## 3. Capas y trazabilidad de cifras (obligatorio)

- [ ] Cifras leídas **solo de ClickHouse** (no StarRocks/PocketBase). *(RT-01, RT-02, RN-1202)*
- [ ] Cada métrica es trazable a su Fact/agregación de origen. *(RN-1204, RNF-1104)*
- [ ] Linaje (`exposure`) del reporte documentado en `dbt docs`. *(Princ. VII, RT-14)*

## 4. Orquestación y reproducibilidad (obligatorio)

- [ ] Reporte generado como **último paso** del `dag_pipeline_diario`. *(Princ. IX, RN-1203, RT-03)*
- [ ] Reporte archivado por fecha y reproducible. *(RN-1205, RNF-1105)*
- [ ] **`docker compose up` levanta** el generador; imagen con versión fija. *(Princ. VIII, RT-17)*

## 5. Funcionalidad (criterios de aceptación)

- [ ] CA-1201 reporte consolida ingesta/API/uso/incidentes por `Dim_Tiempo`.
- [ ] CA-1202 generación automática al cierre del DAG.
- [ ] CA-1203 sin calidad del día → bloqueado.
- [ ] CA-1204 cifras solo de ClickHouse y trazables.
- [ ] CA-1205 archivado por fecha y reproducible.

## 6. Observabilidad y alcance

- [ ] Evento de generación (éxito/fallo) expuesto a `observabilidad`/`alertas`.
- [ ] Confirmado que reportes mensuales/estratégicos quedan **fuera** del alcance operativo. *(§13)*
