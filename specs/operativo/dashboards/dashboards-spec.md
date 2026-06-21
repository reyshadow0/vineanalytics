# dashboards · Especificación — VinAnalytics Group

> **Bloque de trazabilidad**
> - **Nivel:** Operativo
> - **Departamento responsable:** Analista de datos (publicación con apoyo de Administrador)
> - **Paquete:** `dashboards`
> - **Objetivo operativo (OP):** OP3 — Construir y publicar dashboards para los clientes.
> - **Objetivos de origen (OT/OE):** OT7 (Consolidar el Data Warehouse unificado para BI) → OE4 (Inteligencia de Negocio Centralizada).
> - **Casos de uso (CU-O):** CU-O05 (Construir dashboard de cliente) y CU-O06 (Publicar dashboard a la cuenta del cliente).
> - **Modelo Fact-Dim que toca (matriz §9.8):**
>   - CU-O05 → Fact según tema + `Dim_Tiempo`, `Dim_Mercado`, `Dim_Cliente`, `Dim_Plan`.
>   - CU-O06 → reglas de publicación y permisos (sobre `Dim_Cliente`, `Dim_Plan`).

Hereda arquitectura, glosario y reglas de [000-general](../000-general/operativo-general-spec.md),
[glossary.md](../000-general/glossary.md) y [rules.md](../000-general/rules.md).

---

## 1. Objetivo

Construir dashboards de cliente sobre las **agregaciones de ClickHouse** (alimentadas
desde StarRocks) y **publicarlos** a la cuenta correcta con los permisos y el plan
adecuados, garantizando que **ningún dashboard se publica sin validación de calidad
de datos previa** (CU-O04). Convierte el DW en valor consumible por el cliente.

## 2. Contexto

Es el último eslabón del flujo orientado al cliente: lee **solo** de **ClickHouse**
(serving de baja latencia), nunca de StarRocks ni PocketBase directamente para los
datos analíticos. CU-O05 modela métricas, filtros y definiciones de un dashboard por
tema (ingresos, reseñas, precios, uso); CU-O06 lo publica a la cuenta del cliente
respetando permisos, plan y versión. Departamento: **Analista de datos** (construye)
y **Administrador** (autoriza publicación).

### Historias de usuario

**CU-O05 — Construir dashboard de cliente**
- HU-01: *Como Analista de datos, quiero componer un dashboard con métricas, filtros
  y definiciones sobre las agregaciones de ClickHouse, para responder preguntas de
  negocio del cliente.*
- HU-02: *Como Analista de datos, quiero filtrar por `Dim_Tiempo`, `Dim_Mercado`,
  `Dim_Cliente` y `Dim_Plan`, para segmentar la vista según el cliente.*

**CU-O06 — Publicar dashboard a la cuenta del cliente**
- HU-03: *Como Administrador, quiero publicar un dashboard a una cuenta con permisos
  y versión, para que solo el cliente autorizado lo vea.*
- HU-04: *Como Analista/Administrador, quiero que el sistema bloquee la publicación
  si la calidad de datos no fue validada, para no exponer datos sucios.*

## 3. Actores

| Actor | Participación |
|---|---|
| **Analista de datos** | Construye y versiona dashboards (CU-O05). |
| **Administrador** | Autoriza y ejecuta la publicación por cuenta (CU-O06). |
| **Cliente empresarial** | Consume el dashboard publicado (lectura). |
| Paquete `etl-calidad` (OP2) | Provee el sello de calidad (CU-O04) requerido para publicar. |

## 4. Requisitos funcionales

**De CU-O05 (Construir dashboard):**
- **RF-301** El sistema permite definir un dashboard con métricas, filtros y
  definiciones, leyendo de **agregaciones ClickHouse**. *(RT-01, RT-02)*
- **RF-302** El sistema soporta filtros por `Dim_Tiempo`, `Dim_Mercado`,
  `Dim_Cliente` y `Dim_Plan`.
- **RF-303** El sistema versiona cada dashboard (borrador → versión publicable).
- **RF-304** El sistema selecciona la(s) Fact por tema (p. ej. `Fact_Suscripcion`,
  `Fact_Resena`, `Fact_Precio_Mercado`, `Fact_Uso_Plataforma`) según el dashboard.

**De CU-O06 (Publicar dashboard):**
- **RF-305** El sistema **verifica que existe validación de calidad de datos vigente**
  (CU-O04) antes de permitir publicar. *(RN-401, RT-15)*
- **RF-306** El sistema publica el dashboard a una **cuenta de cliente** concreta con
  permisos por rol y según el `Dim_Plan` contratado.
- **RF-307** El sistema registra cada publicación (cuenta, permisos, versión, fecha).
- **RF-308** El sistema permite despublicar o reemplazar por una versión nueva sin
  perder el historial.

## 5. Requisitos no funcionales

- **RNF-301 Latencia:** las consultas del dashboard sobre ClickHouse responden en
  < 200 ms promedio por región. *(RNF-G05, BSC)*
- **RNF-302 Aislamiento:** un cliente solo ve los datos de su cuenta (multi-tenant).
- **RNF-303 Capa correcta:** los datos analíticos provienen **solo** de ClickHouse. *(RT-01)*
- **RNF-304 Reproducibilidad:** la herramienta de dashboard corre en contenedor. *(RT-17)*
- **RNF-305 Adopción:** dashboards listos que faciliten ≥ 70% de adopción (BSC cliente).

## 6. Reglas de negocio

- **RN-401** **No publicar un dashboard sin validación de calidad de datos previa**
  (CU-O04). *(RT-15, Princ. X)*
- **RN-402** Un dashboard solo se publica a cuentas con plan vigente; el contenido se
  limita a lo permitido por `Dim_Plan`. *(RT, suscripciones OP5)*
- **RN-403** Aislamiento por cliente: prohibido mezclar datos de cuentas distintas. *(RNF-302)*
- **RN-404** Los datos analíticos se leen de ClickHouse; prohibido leer de PocketBase
  o StarRocks para servir el dashboard. *(RT-01, RT-02)*
- **RN-405** Toda publicación queda registrada y versionada (auditable). *(RF-307)*

## 7. Entradas

- **Agregaciones ClickHouse** (MRR, churn, sentimiento, precios, uso, etc.).
- **Sello de calidad** vigente de CU-O04 (`etl-calidad`).
- **Metadatos de cuenta/plan/permisos** (PocketBase, vía `suscripciones`).
- **Definición del dashboard** (métricas, filtros, layout).

## 8. Salidas

- **Dashboard del cliente** publicado y filtrable.
- **Registro de publicaciones** (cuenta, permisos, versión, fecha).
- **Versiones** de dashboard (historial).

## 9. Estados posibles

**Dashboard:** `BORRADOR` → `EN_REVISION` → `LISTO_PARA_PUBLICAR` →
`PUBLICADO` → (`DESPUBLICADO` | `REEMPLAZADO`). Bloqueo:
`BLOQUEADO_SIN_CALIDAD` si no hay validación vigente de CU-O04.

## 10. Escenarios (Dado / Cuando / Entonces)

- **Esc-301 (construcción):** *Dado* un Analista, *cuando* compone un dashboard de
  ingresos con filtros por `Dim_Tiempo`/`Dim_Mercado`, *entonces* el sistema lo
  guarda como `BORRADOR` leyendo de ClickHouse.
- **Esc-302 (publicación nominal):** *Dado* un dashboard `LISTO_PARA_PUBLICAR` y
  calidad CU-O04 vigente, *cuando* el Administrador publica a una cuenta con plan
  activo, *entonces* queda `PUBLICADO` con su registro de publicación. *(RF-306, RF-307)*
- **Esc-303 (sin calidad — error):** *Dado* un dashboard listo pero **sin** validación
  de calidad vigente, *cuando* se intenta publicar, *entonces* el sistema lo bloquea
  en `BLOQUEADO_SIN_CALIDAD`. *(RN-401, RT-15)*
- **Esc-304 (plan no vigente — error):** *Dado* una cuenta con plan vencido, *cuando*
  se intenta publicar, *entonces* el sistema rechaza la publicación. *(RN-402)*
- **Esc-305 (fuga de datos — error):** *Dado* un dashboard, *cuando* un filtro
  intentaría exponer datos de otra cuenta, *entonces* el aislamiento multi-tenant lo
  impide. *(RN-403)*
- **Esc-306 (capa incorrecta — error):** *Dado* una métrica nueva, *cuando* se intenta
  leerla desde StarRocks/PocketBase, *entonces* la revisión lo rechaza por violar RN-404.

## 11. Criterios de aceptación

- **CA-301** Un dashboard se construye y previsualiza leyendo de ClickHouse. *(RF-301)*
- **CA-302** Publicar exige y verifica calidad vigente (CU-O04); sin ella, se bloquea. *(RF-305, RN-401)*
- **CA-303** La publicación asocia cuenta, permisos, plan y versión, y queda registrada. *(RF-306, RF-307)*
- **CA-304** Un cliente solo accede a los datos de su cuenta. *(RNF-302, RN-403)*
- **CA-305** Las consultas del dashboard responden < 200 ms promedio. *(RNF-301)*
- **CA-306** Existe historial de versiones y se puede despublicar/reemplazar. *(RF-308)*

## 12. Dependencias

- **Capas:** ClickHouse (origen de datos del dashboard), PocketBase (cuentas/permisos).
- **Paquetes:** `etl-calidad` (OP2, sello CU-O04 + agregaciones desde StarRocks);
  `suscripciones` (OP5, plan/cuenta); `reportes-operativos` reutiliza vistas.
- **Tablas Fact/Dim:** Fact por tema (`Fact_Suscripcion`, `Fact_Resena`,
  `Fact_Precio_Mercado`, `Fact_Uso_Plataforma`) + `Dim_Tiempo`, `Dim_Mercado`,
  `Dim_Cliente`, `Dim_Plan`.

## 13. Fuera de alcance

- Cálculo/poblamiento de las agregaciones en ClickHouse (es parte del pipeline OP2/OP3 base).
- Validación de calidad en sí (es CU-O04 / `etl-calidad`).
- Gestión de cuentas/planes/facturación (es OP5 / `suscripciones`).
- Dashboards estratégicos / BSC corporativo (nivel estratégico, fuera del repo).
