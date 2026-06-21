# api-publica · Checklist — Definición de Terminado (speckit-checklist)

> Paquete: `api-publica` · OP4 · CU-O07. No se integra hasta marcar todos los ítems.
> Verifica contra [api-publica-spec.md](api-publica-spec.md) y la
> [constitución](../../../.specify/memory/constitution.md).

---

## 1. Spec y trazabilidad (obligatorio)

- [ ] Spec validado contra la constitución sin conflictos. *(RT-18)*
- [ ] Bloque de trazabilidad completo: OP4, OT3/OT4/OE2, CU-O07. *(RT-19)*
- [ ] Historia(s) de usuario y modelo Fact-Dim (`Fact_Consumo_API`, `Dim_Partner_API`) declarados. *(Princ. IV)*
- [ ] `speckit-analyze` sin inconsistencias con `000-general`, `etl-calidad`, `suscripciones`.

## 2. Contrato y SDD (obligatorio)

- [ ] Contrato **OpenAPI `/v1`** definido antes del código; 100% de endpoints documentados. *(OT3, RNF-404, RF-401)*
- [ ] Versionado sin cambios rompientes dentro de la versión mayor. *(RN-506)*

## 3. Seguridad y cuotas (obligatorio)

- [ ] Autenticación obligatoria; credencial inválida → 401. *(RN-501)*
- [ ] Rate limiting por plan; exceso → 429. *(RN-502)*
- [ ] TLS y credenciales nunca en claro. *(RNF-403)*

## 4. Capas y registro (obligatorio)

- [ ] Datos servidos **solo desde ClickHouse** (no StarRocks/PocketBase). *(RT-01, RT-02, RN-503)*
- [ ] Toda llamada registrada en `Fact_Consumo_API` (latencia, estado, partner). *(RN-504, RF-405)*
- [ ] Linaje de `Fact_Consumo_API` documentado en `dbt docs`. *(Princ. VII, RT-14)*

## 5. Contenedores y rendimiento (obligatorio)

- [ ] **`docker compose up` levanta** el servicio API; imagen con versión fija. *(Princ. VIII, RT-17)*
- [ ] Latencia < 200 ms promedio verificada. *(RNF-401, CA-405)*
- [ ] Disponibilidad objetivo > 99.9% considerada. *(RNF-402)*

## 6. Funcionalidad (criterios de aceptación)

- [ ] CA-401 endpoints OpenAPI documentados.
- [ ] CA-402 llamada autenticada y dentro de cuota → 200 desde ClickHouse.
- [ ] CA-403 401 / 429 / 400 según corresponda.
- [ ] CA-404 toda llamada registrada en `Fact_Consumo_API`.
- [ ] CA-405 latencia < 200 ms.
- [ ] CA-406 pico de errores genera alerta.

## 7. Observabilidad y alertas

- [ ] Métricas de consumo y errores expuestas a `observabilidad` (OP7). *(RNF-406)*
- [ ] Pico de errores 5xx dispara alerta (CU-O13). *(RN-505, RT-16)*
