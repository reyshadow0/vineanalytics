# dashboards · Tareas (speckit-tasks)

> Paquete: `dashboards` · OP3 · CU-O05, CU-O06. Tareas atómicas ordenadas por
> dependencia. Marca `[x]` al completar. Citan RF/RN/CA de
> [dashboards-spec.md](dashboards-spec.md).

---

## A. CU-O05 — Construir dashboard de cliente

- [ ] **T-01** Conectar la herramienta BI a ClickHouse en modo solo lectura. *(RF-301, RN-404)*
- [ ] **T-02** Implementar la definición de un dashboard (métricas + definiciones) por tema. *(RF-301, RF-304)*
- [ ] **T-03** Implementar filtros por `Dim_Tiempo`, `Dim_Mercado`, `Dim_Cliente`, `Dim_Plan`. *(RF-302)*
- [ ] **T-04** Implementar versionado de dashboard (borrador → publicable). *(RF-303)*
- [ ] **T-05** Prueba: construir dashboard de ingresos leyendo de ClickHouse deja estado `BORRADOR`. *(CA-301, Esc-301)*

## B. CU-O06 — Publicar dashboard a la cuenta del cliente

- [ ] **T-06** Implementar el gate que verifica el sello de calidad vigente (CU-O04). *(RF-305, RN-401)*
- [ ] **T-07** Implementar la publicación por cuenta con permisos por rol. *(RF-306)*
- [ ] **T-08** Verificar `Dim_Plan` vigente antes de publicar. *(RN-402)*
- [ ] **T-09** Registrar la publicación (cuenta, permisos, versión, fecha). *(RF-307, RN-405)*
- [ ] **T-10** Implementar despublicar/reemplazar con historial de versiones. *(RF-308, CA-306)*
- [ ] **T-11** Reforzar aislamiento multi-tenant por cuenta. *(RNF-302, RN-403)*
- [ ] **T-12** Prueba: publicación nominal con calidad vigente deja `PUBLICADO` + registro. *(CA-303, Esc-302)*
- [ ] **T-13** Prueba: publicar sin calidad vigente bloquea en `BLOQUEADO_SIN_CALIDAD`. *(CA-302, Esc-303)*
- [ ] **T-14** Prueba: plan vencido rechaza la publicación. *(Esc-304)*
- [ ] **T-15** Prueba: filtro que expondría otra cuenta es bloqueado. *(Esc-305)*

## C. Rendimiento, contenedores y cierre

- [ ] **T-16** Validar latencia de consultas < 200 ms promedio sobre ClickHouse. *(RNF-301, CA-305)*
- [ ] **T-17** Contenedorizar la herramienta BI en `docker-compose.yml` (versión fija). *(RNF-304, RT-17)*
- [ ] **T-18** Verificar arranque con `docker compose up`. *(RT-17)*
- [ ] **T-19** Confirmar que ningún dato analítico se lee de StarRocks/PocketBase. *(RN-404, Esc-306)*
- [ ] **T-20** Validar spec contra constitución y completar [checklist.md](checklist.md). *(RT-18, RT-19)*
