# dashboards · Tareas (speckit-tasks)

> Paquete: `dashboards` · OP3 · CU-O05, CU-O06. Tareas atómicas ordenadas por
> dependencia. Marca `[x]` al completar. Citan RF/RN/CA de
> [dashboards-spec.md](dashboards-spec.md).

---

## A. CU-O05 — Construir dashboard de cliente

- [x] **T-01** Conectar la herramienta BI a ClickHouse en modo solo lectura. *(RF-301, RN-404)* — `serving.metricas_dashboard()` lee agregaciones ClickHouse (solo SELECT); el constructor recibe la lectura por `lectura_fn`, nunca consulta el DW directo. *(Nota: no hay BI externo; el serving propio cumple el rol — ver T-17.)*
- [x] **T-02** Implementar la definición de un dashboard (métricas + definiciones) por tema. *(RF-301, RF-304)* — `models_dashboards.TEMAS` (4 temas → Fact) + `construir_dashboard()` arma métricas con `definicion`.
- [x] **T-03** Implementar filtros por `Dim_Tiempo`, `Dim_Mercado`, `Dim_Cliente`, `Dim_Plan`. *(RF-302)* — `DIM_FILTROS`; `mercado` se aplica en `serving` (agg_pais); `cliente` fuerza el aislamiento; todos quedan en `definicion.filtros`.
- [x] **T-04** Implementar versionado de dashboard (borrador → publicable). *(RF-303)* — estados `BORRADOR→EN_REVISION→LISTO_PARA_PUBLICAR→PUBLICADO`; `version` en la colección `dashboards`.
- [x] **T-05** Prueba: construir dashboard de ingresos leyendo de ClickHouse deja estado `BORRADOR`. *(CA-301, Esc-301)* — `test_construir_deja_borrador_leyendo_clickhouse`.

## B. CU-O06 — Publicar dashboard a la cuenta del cliente

- [x] **T-06** Implementar el gate que verifica el sello de calidad vigente (CU-O04). *(RF-305, RN-401)* — `calidad_vigente()` (último sello, éxito + dentro de vigencia); `run_quality.py` emite el sello.
- [x] **T-07** Implementar la publicación por cuenta con permisos por rol. *(RF-306)* — `publicar()` + colección `publicaciones` (permisos); endpoint admin `/dashboards/<id>/publicar`.
- [x] **T-08** Verificar `Dim_Plan` vigente antes de publicar. *(RN-402)* — `acceso_vigente()` (reutiliza CU-O08); rechaza con `PlanNoVigente`.
- [x] **T-09** Registrar la publicación (cuenta, permisos, versión, fecha). *(RF-307, RN-405)* — registro en `publicaciones` (cuenta, plan, permisos, versión, sello, `publicado_en`).
- [x] **T-10** Implementar despublicar/reemplazar con historial de versiones. *(RF-308, CA-306)* — `despublicar()` + reemplazo con `version+1` y estado `REEMPLAZADA`.
- [x] **T-11** Reforzar aislamiento multi-tenant por cuenta. *(RNF-302, RN-403)* — `publicar()` exige `dashboard.cliente == cuenta`; `construir` bloquea filtro a otra cuenta.
- [x] **T-12** Prueba: publicación nominal con calidad vigente deja `PUBLICADO` + registro. *(CA-303, Esc-302)* — `test_publicar_con_calidad_ok_deja_publicado_y_registro`.
- [x] **T-13** Prueba: publicar sin calidad vigente bloquea en `BLOQUEADO_SIN_CALIDAD`. *(CA-302, Esc-303)* — `test_publicar_sin_sello_bloquea_por_calidad` + `test_publicar_con_ultima_calidad_fallida_bloquea`.
- [x] **T-14** Prueba: plan vencido rechaza la publicación. *(Esc-304)* — `test_publicar_con_plan_vencido_se_rechaza`.
- [x] **T-15** Prueba: filtro que expondría otra cuenta es bloqueado. *(Esc-305)* — `test_filtro_a_otra_cuenta_es_fuga` + `test_publicar_a_otra_cuenta_es_fuga`.

## C. Rendimiento, contenedores y cierre

- [ ] **T-16** Validar latencia de consultas < 200 ms promedio sobre ClickHouse. *(RNF-301, CA-305)* — pendiente: requiere ClickHouse poblado en Docker.
- [ ] **T-17** Contenedorizar la herramienta BI en `docker-compose.yml` (versión fija). *(RNF-304, RT-17)* — pendiente: el serving corre dentro del contenedor Flask; falta decidir si se añade BI externo (Superset).
- [ ] **T-18** Verificar arranque con `docker compose up`. *(RT-17)* — pendiente: no se levantó Docker en esta sesión.
- [x] **T-19** Confirmar que ningún dato analítico se lee de StarRocks/PocketBase. *(RN-404, Esc-306)* — la lectura entra por `serving` (ClickHouse); el único acceso a StarRocks es el **fallback sancionado** (regla C de la constitución); PocketBase solo guarda metadatos, nunca datos analíticos.
- [x] **T-20** Validar spec contra constitución y completar [checklist.md](checklist.md). *(RT-18, RT-19)* — checklist actualizado; `speckit-analyze` formal queda pendiente.
