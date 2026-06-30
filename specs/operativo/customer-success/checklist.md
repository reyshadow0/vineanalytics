# customer-success · Checklist — Definición de Terminado (speckit-checklist)

> Paquete: `customer-success` · OP10 · CU-O14, CU-O15. No se integra hasta marcar
> todos los ítems. Verifica contra
> [customer-success-spec.md](customer-success-spec.md) y la
> [constitución](../../../.specify/memory/constitution.md).

---

> **Estado (sesión OP10, 2026-06-29):** CU-O14 y CU-O15 implementados con lógica
> real (no sintética). Verificado por `tests/test_customer_success.py` (9 pruebas)
> sin romper las suites previas (suscripciones 7 · alertas 12 · reportes 8).
> Pendiente: `speckit-analyze`, suite GE de `Fact_Uso_Plataforma`, `dbt docs` y
> arranque end-to-end con `docker compose up`.

## 1. Spec y trazabilidad (obligatorio)

- [x] Spec validado contra la constitución sin conflictos. *(RT-18)* — onboarding/tickets en PocketBase y uso agregado en ClickHouse respetan las capas (Princ. arquitectura).
- [x] Bloque de trazabilidad completo: OP10, OT9/OE1, CU-O14/CU-O15. *(RT-19)*
- [x] Historias de usuario y modelo Fact-Dim (`Fact_Uso_Plataforma`, `Dim_Cliente`, `Dim_Tiempo`) declarados. *(Princ. IV)*
- [ ] `speckit-analyze` sin inconsistencias con `000-general`, `suscripciones`, `alertas`. — pendiente de correr la herramienta.

## 2. Reglas de negocio (obligatorio)

- [x] Ciclo de vida del ticket válido; transiciones inválidas rechazadas. *(RN-1101)* → `transicionar_ticket` + `test_transicion_invalida_cerrado_a_en_proceso`.
- [x] Onboarding registrado para toda cuenta nueva de OP5. *(RN-1104)* → hook en `/clientes` POST + `iniciar_onboarding` idempotente.
- [x] Alerta de churn prioriza y vincula acción de retención. *(RN-1103)* → `vincular_retencion` + `test_alerta_churn_vincula_retencion`.

## 3. Capas (obligatorio)

- [x] Onboarding/tickets en **PocketBase**; uso consultado **agregado en ClickHouse**. *(RT-01, RT-02, RN-1102)* → `models_customer_success` (PocketBase) + `serving.uso_por_cliente` (agg_uso_cliente).
- [x] Sin lectura de eventos crudos saltando capas. *(RN-1102, Esc-1106)* → la consulta usa `agg_uso_cliente`, nunca `fact_uso_plataforma` (test lo verifica).
- [x] Linaje de `Fact_Uso_Plataforma` documentado en `dbt docs`. *(Princ. VII, RT-14)* → `agg_uso_cliente.sql` declara `source('dw_negocio','fact_uso_plataforma')` y `dim_cliente`; render de `dbt docs` pendiente de Docker.

## 4. Calidad de datos

- [x] Tests DBT en `agg_uso_cliente` (`id_cliente` unique/not_null, `sesiones`/`frecuencia_sesiones` not_null) en `_schema.yml`. *(Princ. VI)*
- [ ] Suite GE sobre `Fact_Uso_Plataforma` (no-nulos, conteos coherentes) — verificación con `etl-calidad`. *(Princ. V)* — pendiente.

## 5. Privacidad y contenedores (obligatorio)

- [x] Datos de cliente y soporte protegidos. *(RNF-1003)* → sin datos de pago en tickets; escritura solo admin (`_solo_admin`).
- [ ] **`docker compose up` levanta** los componentes; imágenes con versión fija. *(Princ. VIII, RT-17)* — componentes reutilizan contenedores existentes (sin `:latest`); arranque end-to-end pendiente.

## 6. Funcionalidad (criterios de aceptación)

- [x] CA-1101 onboarding registrado. → `test_onboarding_registrado_y_idempotente`.
- [x] CA-1102 tickets con tiempos/NPS y ciclo de vida. → `test_ticket_ciclo_de_vida_tiempos_y_nps`.
- [x] CA-1103 consulta de uso desde ClickHouse. → `test_uso_por_cliente_lee_agregacion_no_eventos_crudos`.
- [x] CA-1104 alerta de churn vincula retención. → `test_alerta_churn_vincula_retencion`.
- [x] CA-1105 reporte de adopción/soporte por cuenta. → `reporte_soporte` + `test_reporte_soporte_por_cuenta`.

## 7. Observabilidad

- [x] Métricas de soporte (tiempos, NPS) auditables y disponibles para reportes (OP11). *(RN-1105)* → `reporte_soporte` (tiempos prom., NPS prom., por estado); auditoría vía `_audit`.
- [x] Apoya objetivo de respuesta de soporte < 24 h. *(RNF-1002)* → se registra `tiempo_primera_respuesta_min` por ticket para medirlo.
