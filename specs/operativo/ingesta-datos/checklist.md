# ingesta-datos · Checklist — Definición de Terminado (speckit-checklist)

> Paquete: `ingesta-datos` · OP1 · CU-O01, CU-O02. El paquete **no se integra**
> hasta marcar todos los ítems. Verifica contra
> [ingesta-datos-spec.md](ingesta-datos-spec.md) y la
> [constitución](../../../.specify/memory/constitution.md).

---

## 1. Spec y trazabilidad (obligatorio)

- [ ] Spec validado contra la constitución (Princ. I–X) sin conflictos abiertos. *(RT-18)*
- [ ] Bloque de trazabilidad completo: Nivel, Departamento, Paquete, OP1, OT7/OE4, CU-O01/CU-O02. *(RT-19)*
- [ ] Cada CU-O del paquete tiene ≥ 1 historia de usuario y su modelo Fact-Dim declarado. *(Princ. IV)*
- [ ] `speckit-analyze` sin inconsistencias entre spec, plan, tasks y `000-general`.

## 2. Calidad de datos (obligatorio)

- [ ] **Suite Great Expectations pasando** sobre el staging Parquet (unicidad de clave natural, no-nulos críticos, dominios `precio>0` / `puntaje∈[80,100]` / fecha no futura / `moneda` ISO-4217, conteo de filas). *(Princ. V, RN-205)*
- [ ] Fail-fast verificado: un lote con > 5% de rechazos termina `FALLIDA`, no aterriza y emite alerta. *(RN-204, CA-105)*
- [ ] Deduplicación verificada por clave natural en los tres tipos de fuente. *(RN-203)*

## 3. Transformación y linaje (obligatorio)

- [ ] **Tests DBT pasando** en los modelos de staging que consumen el Parquet (`unique`, `not_null` en clave natural) — verificación aguas abajo con `etl-calidad`. *(Princ. VI)*
- [ ] **Linaje documentado**: el staging aparece como `source` en `dbt docs` y se rastrea hasta `Fact_Resena`, `Fact_Precio_Mercado`, `Fact_Puntuacion`. *(Princ. VII, RT-14)*
- [ ] Confirmado que la ingesta **no** transforma a Fact-Dim ni carga StarRocks. *(RN-206, RT-01)*

## 4. Formato y staging (obligatorio)

- [ ] Staging escrito en **Parquet snappy**, particionado por `fuente`/`fecha_ingesta`, verificado con pyarrow. *(RNF-101, CA-103)*
- [ ] Sin CSV en el flujo de producción. *(RT-04)*
- [ ] Idempotencia verificada: reejecución de una ventana no duplica filas. *(RNF-102, CA-104)*

## 5. Orquestación y contenedores (obligatorio)

- [ ] Tarea `ingesta` integrada en `dag_pipeline_diario`, **antes** de calidad, con `retries`/`retry_delay`. *(RT-03, CA-107)*
- [ ] **`docker compose up` levanta** conector + PocketBase + Airflow; imágenes con versión fija (sin `latest`). *(Princ. VIII, RT-17)*
- [ ] `docker compose config` válido.

## 6. Funcionalidad (criterios de aceptación)

- [ ] CA-101 alta válida → fuente `ACTIVA` y asociada a su Dim.
- [ ] CA-102 alta duplicada rechazada con id existente.
- [ ] CA-103 ingesta produce Parquet snappy particionado.
- [ ] CA-104 reejecución idempotente sin filas extra.
- [ ] CA-105 lote con > 5% rechazo → `FALLIDA` + alerta.
- [ ] CA-106 reporte de ingesta generado por lote.
- [ ] CA-107 ingesta corre en el DAG dentro de `docker compose up`.

## 7. Observabilidad y alertas

- [ ] Métricas/logs estructurados emitidos para `observabilidad` (OP7). *(RNF-105)*
- [ ] Evento de fallo de ingesta llega a `alertas` (OP9). *(RT-16)*
