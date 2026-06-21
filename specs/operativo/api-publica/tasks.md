# api-publica · Tareas (speckit-tasks)

> Paquete: `api-publica` · OP4 · CU-O07. Tareas atómicas ordenadas por dependencia.
> Marca `[x]` al completar. Citan RF/RN/CA de [api-publica-spec.md](api-publica-spec.md).

---

## A. Contrato y servicio (SDD-first)

- [ ] **T-01** Definir el contrato **OpenAPI `/v1`** (endpoints, esquemas) antes de codificar. *(RF-401, OT3)*
- [ ] **T-02** Andamiar el servicio FastAPI a partir del contrato. *(RF-401, RNF-404)*

## B. CU-O07 — Atender solicitud de la API pública

- [ ] **T-03** Implementar autenticación por API key/token de partner (401 si inválida). *(RF-402, RN-501)*
- [ ] **T-04** Implementar rate limiting por plan/partner (429 al exceder). *(RF-403, RN-502)*
- [ ] **T-05** Implementar handlers que sirven datos **desde ClickHouse**. *(RF-404, RN-503)*
- [ ] **T-06** Implementar validación de esquema entrada/salida contra OpenAPI (400 si malformado). *(RF-406)*
- [ ] **T-07** Implementar el registro de cada llamada en `Fact_Consumo_API` (latencia, estado, partner). *(RF-405, RN-504)*
- [ ] **T-08** Implementar versionado/deprecación controlada (sin cambios rompientes en `/v1`). *(RF-407, RN-506)*
- [ ] **T-09** Prueba: llamada nominal → 200 desde ClickHouse + registro en `Fact_Consumo_API`. *(CA-402, CA-404, Esc-401)*
- [ ] **T-10** Prueba: credencial inválida → 401; cuota excedida → 429; payload inválido → 400. *(CA-403, Esc-402, Esc-403, Esc-404)*

## C. Observabilidad, rendimiento y cierre

- [ ] **T-11** Emitir métricas y errores a `observabilidad` (OP7). *(RNF-406)*
- [ ] **T-12** Disparar alerta ante pico de errores 5xx sobre umbral (CU-O13). *(RN-505, Esc-405)*
- [ ] **T-13** Validar latencia < 200 ms promedio. *(RNF-401, CA-405)*
- [ ] **T-14** Asegurar TLS y credenciales nunca en claro. *(RNF-403)*
- [ ] **T-15** Contenedorizar el servicio en `docker-compose.yml` (versión fija). *(RNF-405, RT-17)*
- [ ] **T-16** Verificar arranque con `docker compose up`. *(RT-17)*
- [ ] **T-17** Confirmar que no se sirve desde StarRocks/PocketBase. *(RN-503, Esc-406)*
- [ ] **T-18** Validar spec contra constitución y completar [checklist.md](checklist.md). *(RT-18, RT-19)*
