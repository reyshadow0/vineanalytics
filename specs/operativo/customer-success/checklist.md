# customer-success · Checklist — Definición de Terminado (speckit-checklist)

> Paquete: `customer-success` · OP10 · CU-O14, CU-O15. No se integra hasta marcar
> todos los ítems. Verifica contra
> [customer-success-spec.md](customer-success-spec.md) y la
> [constitución](../../../.specify/memory/constitution.md).

---

## 1. Spec y trazabilidad (obligatorio)

- [ ] Spec validado contra la constitución sin conflictos. *(RT-18)*
- [ ] Bloque de trazabilidad completo: OP10, OT9/OE1, CU-O14/CU-O15. *(RT-19)*
- [ ] Historias de usuario y modelo Fact-Dim (`Fact_Uso_Plataforma`, `Dim_Cliente`, `Dim_Tiempo`) declarados. *(Princ. IV)*
- [ ] `speckit-analyze` sin inconsistencias con `000-general`, `suscripciones`, `alertas`.

## 2. Reglas de negocio (obligatorio)

- [ ] Ciclo de vida del ticket válido; transiciones inválidas rechazadas. *(RN-1101)*
- [ ] Onboarding registrado para toda cuenta nueva de OP5. *(RN-1104)*
- [ ] Alerta de churn prioriza y vincula acción de retención. *(RN-1103)*

## 3. Capas (obligatorio)

- [ ] Onboarding/tickets en **PocketBase**; uso consultado **agregado en ClickHouse**. *(RT-01, RT-02, RN-1102)*
- [ ] Sin lectura de eventos crudos saltando capas. *(RN-1102, Esc-1106)*
- [ ] Linaje de `Fact_Uso_Plataforma` documentado en `dbt docs`. *(Princ. VII, RT-14)*

## 4. Calidad de datos

- [ ] Suite GE sobre `Fact_Uso_Plataforma` (no-nulos, conteos coherentes) — verificación con `etl-calidad`. *(Princ. V)*

## 5. Privacidad y contenedores (obligatorio)

- [ ] Datos de cliente y soporte protegidos. *(RNF-1003)*
- [ ] **`docker compose up` levanta** los componentes; imágenes con versión fija. *(Princ. VIII, RT-17)*

## 6. Funcionalidad (criterios de aceptación)

- [ ] CA-1101 onboarding registrado.
- [ ] CA-1102 tickets con tiempos/NPS y ciclo de vida.
- [ ] CA-1103 consulta de uso desde ClickHouse.
- [ ] CA-1104 alerta de churn vincula retención.
- [ ] CA-1105 reporte de adopción/soporte por cuenta.

## 7. Observabilidad

- [ ] Métricas de soporte (tiempos, NPS) auditables y disponibles para reportes (OP11). *(RN-1105)*
- [ ] Apoya objetivo de respuesta de soporte < 24 h. *(RNF-1002)*
