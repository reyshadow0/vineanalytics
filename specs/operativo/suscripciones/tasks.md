# suscripciones · Tareas (speckit-tasks)

> Paquete: `suscripciones` · OP5 · CU-O08. Tareas atómicas ordenadas por dependencia.
> Marca `[x]` al completar. Citan RF/RN/CA de [suscripciones-spec.md](suscripciones-spec.md).

---

## A. CU-O08 — Registrar cuenta y suscripción del cliente

- [x] **T-01** Modelar la colección PocketBase `clientes` (`Dim_Cliente`). *(RF-501)* — `db/pb_setup.py`.
- [x] **T-02** Modelar las colecciones PocketBase `planes`, `estados_suscripcion` y `suscripciones` (`Dim_Plan`, `Dim_Estado_Suscripcion`). *(RF-502)* — `db/pb_setup.py`.
- [x] **T-03** Implementar deduplicación de cuentas (id fiscal/email corporativo). *(RF-503, RN-601)* — `models_clientes.crear_cliente`.
- [x] **T-04** Implementar validación de plan y datos de facturación previa a activar. *(RF-504, RN-602)* — `models_clientes.crear_suscripcion`/`_facturacion_valida`.
- [x] **T-05** Implementar la máquina de estados (prueba→activa→pausa→cancelada; upgrades/downgrades). *(RF-505, RN-604)* — `models_clientes.cambiar_estado`/`cambiar_plan`.
- [x] **T-06** Implementar la emisión de eventos a `Fact_Suscripcion` por cada cambio. *(RF-506, RN-605)* — `models_clientes._emit_evento` → `eventos_suscripcion`.
- [x] **T-07** Exponer plan/estado vigente a `dashboards` (RN-402) y `api-publica` (cuota). *(RF-507, RN-603)* — `models_clientes.acceso_vigente` + `GET /clientes/<id>/acceso`.
- [x] **T-08** Implementar historial/auditoría de cambios. *(RNF-503)* — `eventos_suscripcion` (usuario+fecha) + `audit.registrar_evento` en endpoints.

## B. Pruebas (incluye casos de error)

- [x] **T-09** Prueba: alta nominal deja suscripción `ACTIVA` + evento a `Fact_Suscripcion`. *(CA-501, Esc-501)* — `test_alta_emite_evento_y_acceso_vigente`.
- [x] **T-10** Prueba: alta duplicada rechazada con id existente. *(CA-502, Esc-502)* — `test_dedup_de_cuentas`.
- [x] **T-11** Prueba: facturación incompleta impide la activación. *(CA-503, Esc-503)* — `test_facturacion_incompleta_no_activa`.
- [x] **T-12** Prueba: transición inválida (`CANCELADA`→`EN_PAUSA`) rechazada. *(CA-504, Esc-504)* — `test_transicion_invalida_se_rechaza`.
- [ ] **T-13** Prueba: cancelación corta acceso en `dashboards`/`api-publica`. *(Esc-505)* — *parcial: `acceso_vigente` cubre el corte; la integración real con dashboards/API es aguas abajo.*
- [x] **T-14** Prueba: upgrade emite evento a `Fact_Suscripcion`. *(CA-505, Esc-506)* — `test_upgrade_emite_evento`.

## C. Seguridad, contenedores y cierre

- [x] **T-15** Proteger datos de facturación (sin tarjetas en claro). *(RNF-505)* — `_facturacion_valida` rechaza PAN; solo `****`+token.
- [x] **T-16** Confirmar que cuentas/suscripciones viven en PocketBase y el DW se nutre solo vía ETL. *(RN-606, RT-01)* — la app no escribe al DW; eventos quedan en PocketBase.
- [x] **T-17** Contenedorizar PocketBase + servicio en `docker-compose.yml` (versión fija). *(RNF-504, RT-17)* — `pocketbase:0.22.21` + módulos montados en flask.
- [ ] **T-18** Verificar arranque con `docker compose up`. *(RT-17)* — *pendiente: no se levantó Docker en esta sesión.*
- [ ] **T-19** Validar spec contra constitución y completar [checklist.md](checklist.md). *(RT-18, RT-19)* — checklist actualizado; falta `speckit-analyze`.
