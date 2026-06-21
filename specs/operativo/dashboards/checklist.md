# dashboards · Checklist — Definición de Terminado (speckit-checklist)

> Paquete: `dashboards` · OP3 · CU-O05, CU-O06. No se integra hasta marcar todos los
> ítems. Verifica contra [dashboards-spec.md](dashboards-spec.md) y la
> [constitución](../../../.specify/memory/constitution.md).

---

## 1. Spec y trazabilidad (obligatorio)

- [ ] Spec validado contra la constitución sin conflictos. *(RT-18)*
- [ ] Bloque de trazabilidad completo: OP3, OT7/OE4, CU-O05/CU-O06. *(RT-19)*
- [ ] Historias de usuario y modelo Fact-Dim declarados por CU-O. *(Princ. IV)*
- [ ] `speckit-analyze` sin inconsistencias con `000-general`, `etl-calidad`, `suscripciones`.

## 2. Regla crítica de negocio (obligatorio)

- [ ] **No se publica ningún dashboard sin validación de calidad de datos previa (CU-O04)** — gate verificado. *(Princ. X, RN-401, RF-305)*
- [ ] Verificado el bloqueo `BLOQUEADO_SIN_CALIDAD` cuando no hay sello vigente. *(CA-302, Esc-303)*

## 3. Capas y aislamiento (obligatorio)

- [ ] Los datos analíticos se leen **solo de ClickHouse** (no StarRocks ni PocketBase). *(RT-01, RT-02, RN-404)*
- [ ] Aislamiento multi-tenant verificado: un cliente solo ve su cuenta. *(RNF-302, RN-403)*
- [ ] Publicación limitada por `Dim_Plan` vigente. *(RN-402)*

## 4. Calidad de datos y linaje

- [ ] Las agregaciones consumidas provienen de un DW que pasó GE (CU-O04). *(Princ. V)*
- [ ] Linaje del dashboard documentado como `exposure` en `dbt docs`. *(Princ. VII, RT-14)*

## 5. Contenedores y rendimiento (obligatorio)

- [ ] **`docker compose up` levanta** la herramienta de dashboards; imagen con versión fija. *(Princ. VIII, RT-17)*
- [ ] Latencia de consultas < 200 ms promedio verificada. *(RNF-301, CA-305)*

## 6. Funcionalidad (criterios de aceptación)

- [ ] CA-301 dashboard construido leyendo de ClickHouse.
- [ ] CA-302 publicación exige y verifica calidad vigente.
- [ ] CA-303 publicación asocia cuenta/permisos/plan/versión y queda registrada.
- [ ] CA-304 cliente solo ve su cuenta.
- [ ] CA-305 consultas < 200 ms.
- [ ] CA-306 historial de versiones + despublicar/reemplazar.

## 7. Observabilidad y alertas

- [ ] Eventos de publicación/errores expuestos a `observabilidad` (OP7).
- [ ] Fallos de publicación reportables a `alertas` (OP9) si aplica. *(RT-16)*
