# dashboards · Checklist — Definición de Terminado (speckit-checklist)

> Paquete: `dashboards` · OP3 · CU-O05, CU-O06. No se integra hasta marcar todos los
> ítems. Verifica contra [dashboards-spec.md](dashboards-spec.md) y la
> [constitución](../../../.specify/memory/constitution.md).

---

## 1. Spec y trazabilidad (obligatorio)

- [x] Spec validado contra la constitución sin conflictos. *(RT-18)* — implementación alineada a RN-401/404 y arquitectura de capas.
- [x] Bloque de trazabilidad completo: OP3, OT7/OE4, CU-O05/CU-O06. *(RT-19)* — declarado en `dashboards-spec.md` §0.
- [x] Historias de usuario y modelo Fact-Dim declarados por CU-O. *(Princ. IV)* — `TEMAS` mapea cada tema a su Fact.
- [ ] `speckit-analyze` sin inconsistencias con `000-general`, `etl-calidad`, `suscripciones`. — pendiente de corrida formal.

## 2. Regla crítica de negocio (obligatorio)

- [x] **No se publica ningún dashboard sin validación de calidad de datos previa (CU-O04)** — gate verificado. *(Princ. X, RN-401, RF-305)* — `models_dashboards.publicar()` consulta `calidad_vigente()` antes de registrar.
- [x] Verificado el bloqueo `BLOQUEADO_SIN_CALIDAD` cuando no hay sello vigente. *(CA-302, Esc-303)* — `test_publicar_sin_sello_bloquea_por_calidad`, `test_publicar_con_ultima_calidad_fallida_bloquea`.

## 3. Capas y aislamiento (obligatorio)

- [x] Los datos analíticos se leen **solo de ClickHouse** (no StarRocks ni PocketBase), con fallback sancionado al DW. *(RT-01, RT-02, RN-404)* — `serving.metricas_dashboard()` → ClickHouse; fallback StarRocks solo si ClickHouse no responde (regla C). PocketBase guarda únicamente metadatos.
- [x] Aislamiento multi-tenant verificado: un cliente solo ve su cuenta. *(RNF-302, RN-403)* — `test_publicar_a_otra_cuenta_es_fuga`, `test_filtro_a_otra_cuenta_es_fuga`.
- [x] Publicación limitada por `Dim_Plan` vigente. *(RN-402)* — `test_publicar_con_plan_vencido_se_rechaza`.

## 4. Calidad de datos y linaje

- [x] Las agregaciones consumidas provienen de un DW que pasó GE (CU-O04). *(Princ. V)* — `run_quality.py` sella el resultado del gate; `publicar()` exige sello en éxito.
- [ ] Linaje del dashboard documentado como `exposure` en `dbt docs`. *(Princ. VII, RT-14)* — pendiente.

## 5. Contenedores y rendimiento (obligatorio)

- [ ] **`docker compose up` levanta** la herramienta de dashboards; imagen con versión fija. *(Princ. VIII, RT-17)* — pendiente: no se levantó Docker en esta sesión.
- [ ] Latencia de consultas < 200 ms promedio verificada. *(RNF-301, CA-305)* — pendiente: requiere ClickHouse poblado.

## 6. Funcionalidad (criterios de aceptación)

- [x] CA-301 dashboard construido leyendo de ClickHouse. — `construir_dashboard()` + `test_construir_deja_borrador_leyendo_clickhouse`.
- [x] CA-302 publicación exige y verifica calidad vigente. — gate RN-401.
- [x] CA-303 publicación asocia cuenta/permisos/plan/versión y queda registrada. — colección `publicaciones` + `test_publicar_con_calidad_ok_deja_publicado_y_registro`.
- [x] CA-304 cliente solo ve su cuenta. — aislamiento multi-tenant (RN-403).
- [ ] CA-305 consultas < 200 ms. — pendiente (ver §5).
- [x] CA-306 historial de versiones + despublicar/reemplazar. — `test_republicar_versiona_y_conserva_historial`.

## 7. Observabilidad y alertas

- [~] Eventos de publicación/errores expuestos a `observabilidad` (OP7). — parcial: cada publicación/bloqueo se registra vía `_audit` (auditoría); falta enrutar a OP7.
- [ ] Fallos de publicación reportables a `alertas` (OP9) si aplica. *(RT-16)* — pendiente (paquete `alertas`).
