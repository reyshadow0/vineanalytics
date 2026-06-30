# customer-success · Tareas (speckit-tasks)

> Paquete: `customer-success` · OP10 · CU-O14, CU-O15. Tareas atómicas ordenadas por
> dependencia. Marca `[x]` al completar. Citan RF/RN/CA de
> [customer-success-spec.md](customer-success-spec.md).

---

## A. CU-O14 — Registrar onboarding y ticket de soporte

- [x] **T-01** Modelar la colección PocketBase `onboarding` (`Dim_Cliente`, `Dim_Tiempo`). *(RF-1001)* → `db/pb_setup.py` (`onboarding`), `models_customer_success.iniciar_onboarding`.
- [x] **T-02** Modelar la colección PocketBase `tickets` (categoría, prioridad, tiempos, NPS). *(RF-1002)* → `db/pb_setup.py` (`tickets`), `models_customer_success.abrir_ticket`.
- [x] **T-03** Implementar el ciclo de vida del ticket y el cálculo de tiempos (primera respuesta/resolución). *(RF-1003, RN-1101)* → `transicionar_ticket` (máquina de estados + `_minutos`).
- [x] **T-04** Capturar señales de NPS por cuenta. *(RF-1004)* → `registrar_satisfaccion` (0..10, clasificación promotor/pasivo/detractor).
- [x] **T-05** Disparar el onboarding automáticamente al alta de cuenta en OP5. *(RN-1104)* → hook best-effort en `app.py::clientes` (POST) tras `crear_cliente`; idempotente.
- [x] **T-06** Prueba: onboarding de cuenta nueva queda registrado con pasos/estado. *(CA-1101, Esc-1101)* → `test_onboarding_registrado_y_idempotente`.
- [x] **T-07** Prueba: ticket nominal clasificado, con tiempos y ciclo de vida. *(CA-1102, Esc-1102)* → `test_ticket_ciclo_de_vida_tiempos_y_nps`.
- [x] **T-08** Prueba: transición inválida de ticket (`CERRADO`→`EN_PROCESO`) rechazada. *(Esc-1105, RN-1101)* → `test_transicion_invalida_cerrado_a_en_proceso`.

## B. CU-O15 — Consultar uso de la plataforma por cliente

- [x] **T-09** Implementar la consulta de uso/adopción desde ClickHouse (agregado de `Fact_Uso_Plataforma`). *(RF-1005, RN-1102)* → modelo DBT `serving/agg_uso_cliente.sql`, transporte `clickhouse/populate.py`, lector `serving.uso_por_cliente`, endpoint `/api/uso/<cid>`.
- [x] **T-10** Vincular alertas de churn (OP9) a la priorización de retención. *(RF-1006, RN-1103)* → `evaluar_retencion`/`vincular_retencion`, endpoint `/clientes/<cid>/retencion`.
- [x] **T-11** Exponer el reporte de adopción/soporte por cuenta. *(RF-1007)* → `reporte_soporte`, endpoint `/clientes/<cid>/soporte`.
- [x] **T-12** Prueba: consulta de uso lee de ClickHouse (sesiones/funciones/frecuencia). *(CA-1103, Esc-1103)* → `test_uso_por_cliente_lee_agregacion_no_eventos_crudos`.
- [x] **T-13** Prueba: alerta de churn prioriza y vincula acción de retención. *(CA-1104, Esc-1104)* → `test_alerta_churn_vincula_retencion`.
- [x] **T-14** Prueba: intento de leer eventos crudos (salto de capa) es rechazado. *(Esc-1106, RN-1102)* → mismo test verifica que la consulta usa `agg_uso_cliente` y NUNCA `fact_uso_plataforma`.

## C. Privacidad, contenedores y cierre

- [x] **T-15** Proteger datos de cliente y soporte (privacidad). *(RNF-1003)* → onboarding/tickets no almacenan datos de pago; NPS acotado; escritura solo admin (`_solo_admin`).
- [x] **T-16** Confirmar que onboarding/tickets viven en PocketBase y el uso se consulta agregado. *(RNF-1001, RT-01)* → persistencia solo PocketBase; uso vía `agg_uso_cliente` (ClickHouse) con fallback a la misma vista DBT en StarRocks.
- [x] **T-17** Contenedorizar componentes en `docker-compose.yml` (versión fija). *(RNF-1004, RT-17)* → reutiliza contenedores existentes (`app`/`runner`, PocketBase 0.22.21, ClickHouse 24.3); sin contenedor nuevo ni `:latest`.
- [ ] **T-18** Verificar arranque con `docker compose up`. *(RT-17)* → pendiente (Docker no se levantó en esta sesión).
- [ ] **T-19** Validar spec contra constitución (`speckit-analyze`) y completar [checklist.md](checklist.md). *(RT-18, RT-19)* → checklist actualizado; `speckit-analyze` pendiente.
