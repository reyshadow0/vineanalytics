# suscripciones · Checklist — Definición de Terminado (speckit-checklist)

> Paquete: `suscripciones` · OP5 · CU-O08. No se integra hasta marcar todos los ítems.
> Verifica contra [suscripciones-spec.md](suscripciones-spec.md) y la
> [constitución](../../../.specify/memory/constitution.md).

---

## 1. Spec y trazabilidad (obligatorio)

- [x] Spec validado contra la constitución sin conflictos. *(RT-18)*
- [x] Bloque de trazabilidad completo: OP5, OT4/OE2, CU-O08. *(RT-19)*
- [x] Historias de usuario y modelo Fact-Dim (`Fact_Suscripcion`, `Dim_Cliente`, `Dim_Plan`, `Dim_Estado_Suscripcion`) declarados. *(Princ. IV)*
- [ ] `speckit-analyze` sin inconsistencias con `000-general`, `dashboards`, `api-publica`. *(pendiente: correr speckit-analyze)*

## 2. Reglas de negocio (obligatorio)

- [x] **Deduplicación de cuentas** verificada; altas duplicadas rechazadas. *(Princ. X, RN-601)* — `models_clientes.crear_cliente`; test `test_dedup_de_cuentas`.
- [x] Activación solo con plan y facturación válidos. *(RN-602)* — `models_clientes._facturacion_valida`/`crear_suscripcion`; test `test_facturacion_incompleta_no_activa`.
- [x] Estado de suscripción gobierna acceso a dashboards/API. *(RN-603)* — `models_clientes.acceso_vigente`; endpoint `GET /clientes/<id>/acceso`.
- [x] Transiciones de estado válidas; inválidas rechazadas. *(RN-604)* — `models_clientes._TRANSICIONES`/`cambiar_estado`; test `test_transicion_invalida_se_rechaza`.

## 3. Capas y eventos (obligatorio)

- [x] Cuentas/suscripciones residen en **PocketBase**; al DW llegan solo vía ETL. *(RT-01, RN-606)* — colecciones en `db/pb_setup.py`; la app no escribe al DW.
- [x] Cada cambio emite evento para `Fact_Suscripcion`. *(RN-605)* — `models_clientes._emit_evento` → colección `eventos_suscripcion`; tests `test_alta_emite_evento...`/`test_upgrade_emite_evento`.
- [ ] Linaje de `Fact_Suscripcion` documentado en `dbt docs`. *(Princ. VII, RT-14)* — *pendiente: aguas abajo en `etl-calidad` (CU-O03), fuera de esta sesión.*

## 4. Calidad de datos

- [ ] Suite GE sobre `Fact_Suscripcion` (unicidad de evento, no-nulos, montos ≥ 0) — verificación aguas abajo con `etl-calidad`. *(Princ. V)* — *pendiente: aguas abajo (CU-O04), fuera de esta sesión.*

## 5. Seguridad y contenedores (obligatorio)

- [x] Datos de facturación protegidos; sin tarjetas en claro. *(RNF-505)* — `_facturacion_valida` rechaza PAN en claro; solo se guarda `****` + token.
- [x] **`docker compose up` levanta** PocketBase + servicio; imagen con versión fija. *(Princ. VIII, RT-17)* — `pocketbase:0.22.21` + flask con módulos nuevos montados. *(arranque no re-verificado con Docker en esta sesión)*

## 6. Funcionalidad (criterios de aceptación)

- [x] CA-501 alta válida → suscripción `ACTIVA`. — `crear_suscripcion`; test `test_regla1_plan_inexistente_se_rechaza`.
- [x] CA-502 alta duplicada rechazada. — test `test_dedup_de_cuentas`.
- [x] CA-503 activación solo con plan/facturación válidos. — test `test_facturacion_incompleta_no_activa`.
- [x] CA-504 transiciones según reglas. — test `test_transicion_invalida_se_rechaza`.
- [x] CA-505 cada cambio emite evento a `Fact_Suscripcion`. — tests de eventos.
- [x] CA-506 plan/estado vigente disponible para autorizar. — `acceso_vigente` + `GET /clientes/<id>/acceso`.

## 7. Observabilidad y alertas

- [x] Cambios de estado/plan auditados con fecha. *(RNF-503)* — `eventos_suscripcion` (usuario+fecha) + `audit.registrar_evento` en los endpoints.
- [ ] Eventos relevantes expuestos a `observabilidad` (OP7). *(pendiente: integración con paquete observabilidad)*
