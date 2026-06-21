# suscripciones · Tareas (speckit-tasks)

> Paquete: `suscripciones` · OP5 · CU-O08. Tareas atómicas ordenadas por dependencia.
> Marca `[x]` al completar. Citan RF/RN/CA de [suscripciones-spec.md](suscripciones-spec.md).

---

## A. CU-O08 — Registrar cuenta y suscripción del cliente

- [ ] **T-01** Modelar la colección PocketBase `cuentas` (`Dim_Cliente`). *(RF-501)*
- [ ] **T-02** Modelar la colección PocketBase `suscripciones` (`Dim_Plan`, `Dim_Estado_Suscripcion`). *(RF-502)*
- [ ] **T-03** Implementar deduplicación de cuentas (id fiscal/email corporativo). *(RF-503, RN-601)*
- [ ] **T-04** Implementar validación de plan y datos de facturación previa a activar. *(RF-504, RN-602)*
- [ ] **T-05** Implementar la máquina de estados (prueba→activa→pausa→cancelada; upgrades/downgrades). *(RF-505, RN-604)*
- [ ] **T-06** Implementar la emisión de eventos a `Fact_Suscripcion` por cada cambio. *(RF-506, RN-605)*
- [ ] **T-07** Exponer plan/estado vigente a `dashboards` (RN-402) y `api-publica` (cuota). *(RF-507, RN-603)*
- [ ] **T-08** Implementar historial/auditoría de cambios. *(RNF-503)*

## B. Pruebas (incluye casos de error)

- [ ] **T-09** Prueba: alta nominal deja suscripción `ACTIVA` + evento a `Fact_Suscripcion`. *(CA-501, Esc-501)*
- [ ] **T-10** Prueba: alta duplicada rechazada con id existente. *(CA-502, Esc-502)*
- [ ] **T-11** Prueba: facturación incompleta impide la activación. *(CA-503, Esc-503)*
- [ ] **T-12** Prueba: transición inválida (`CANCELADA`→`EN_PAUSA`) rechazada. *(CA-504, Esc-504)*
- [ ] **T-13** Prueba: cancelación corta acceso en `dashboards`/`api-publica`. *(Esc-505)*
- [ ] **T-14** Prueba: upgrade emite evento a `Fact_Suscripcion`. *(CA-505, Esc-506)*

## C. Seguridad, contenedores y cierre

- [ ] **T-15** Proteger datos de facturación (sin tarjetas en claro). *(RNF-505)*
- [ ] **T-16** Confirmar que cuentas/suscripciones viven en PocketBase y el DW se nutre solo vía ETL. *(RN-606, RT-01)*
- [ ] **T-17** Contenedorizar PocketBase + servicio en `docker-compose.yml` (versión fija). *(RNF-504, RT-17)*
- [ ] **T-18** Verificar arranque con `docker compose up`. *(RT-17)*
- [ ] **T-19** Validar spec contra constitución y completar [checklist.md](checklist.md). *(RT-18, RT-19)*
