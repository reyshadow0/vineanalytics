# suscripciones · Checklist — Definición de Terminado (speckit-checklist)

> Paquete: `suscripciones` · OP5 · CU-O08. No se integra hasta marcar todos los ítems.
> Verifica contra [suscripciones-spec.md](suscripciones-spec.md) y la
> [constitución](../../../.specify/memory/constitution.md).

---

## 1. Spec y trazabilidad (obligatorio)

- [ ] Spec validado contra la constitución sin conflictos. *(RT-18)*
- [ ] Bloque de trazabilidad completo: OP5, OT4/OE2, CU-O08. *(RT-19)*
- [ ] Historias de usuario y modelo Fact-Dim (`Fact_Suscripcion`, `Dim_Cliente`, `Dim_Plan`, `Dim_Estado_Suscripcion`) declarados. *(Princ. IV)*
- [ ] `speckit-analyze` sin inconsistencias con `000-general`, `dashboards`, `api-publica`.

## 2. Reglas de negocio (obligatorio)

- [ ] **Deduplicación de cuentas** verificada; altas duplicadas rechazadas. *(Princ. X, RN-601)*
- [ ] Activación solo con plan y facturación válidos. *(RN-602)*
- [ ] Estado de suscripción gobierna acceso a dashboards/API. *(RN-603)*
- [ ] Transiciones de estado válidas; inválidas rechazadas. *(RN-604)*

## 3. Capas y eventos (obligatorio)

- [ ] Cuentas/suscripciones residen en **PocketBase**; al DW llegan solo vía ETL. *(RT-01, RN-606)*
- [ ] Cada cambio emite evento para `Fact_Suscripcion`. *(RN-605)*
- [ ] Linaje de `Fact_Suscripcion` documentado en `dbt docs`. *(Princ. VII, RT-14)*

## 4. Calidad de datos

- [ ] Suite GE sobre `Fact_Suscripcion` (unicidad de evento, no-nulos, montos ≥ 0) — verificación aguas abajo con `etl-calidad`. *(Princ. V)*

## 5. Seguridad y contenedores (obligatorio)

- [ ] Datos de facturación protegidos; sin tarjetas en claro. *(RNF-505)*
- [ ] **`docker compose up` levanta** PocketBase + servicio; imagen con versión fija. *(Princ. VIII, RT-17)*

## 6. Funcionalidad (criterios de aceptación)

- [ ] CA-501 alta válida → suscripción `ACTIVA`.
- [ ] CA-502 alta duplicada rechazada.
- [ ] CA-503 activación solo con plan/facturación válidos.
- [ ] CA-504 transiciones según reglas.
- [ ] CA-505 cada cambio emite evento a `Fact_Suscripcion`.
- [ ] CA-506 plan/estado vigente disponible para autorizar.

## 7. Observabilidad y alertas

- [ ] Cambios de estado/plan auditados con fecha. *(RNF-503)*
- [ ] Eventos relevantes expuestos a `observabilidad` (OP7).
