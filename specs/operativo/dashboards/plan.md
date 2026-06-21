# dashboards · Plan de implementación (speckit-plan)

> Paquete: `dashboards` · OP3 · CU-O05, CU-O06 · Analista de datos.
> Spec fuente: [dashboards-spec.md](dashboards-spec.md). Marco:
> [000-general](../000-general/operativo-general-spec.md).

---

## 1. Arquitectura del paquete

```
StarRocks (DW) ──► agregaciones ──► ClickHouse (serving)
                                          │  (< 200 ms)
                                          ▼
                              ┌──────────────────────┐     gate calidad CU-O04
                              │  Constructor de       │◄──── (sello vigente de
                              │  dashboards (CU-O05)  │       etl-calidad / OP2)
                              └──────────┬───────────┘
                                         ▼
                              ┌──────────────────────┐     cuentas/permisos/plan
                              │  Publicador (CU-O06)  │◄──── PocketBase (OP5)
                              │  registro + versión   │
                              └──────────┬───────────┘
                                         ▼
                               Cliente empresarial (lectura, multi-tenant)
```

## 2. Herramientas y componentes

| Componente | Tecnología | Responsabilidad |
|---|---|---|
| Serving analítico | **ClickHouse** | Fuente única de datos del dashboard (RT-01). |
| Constructor de dashboards | Herramienta BI (p. ej. **Apache Superset**) en contenedor | Definir métricas/filtros/versiones (CU-O05). |
| Gate de calidad | Verificador del sello **CU-O04** | Bloquear publicación sin calidad (RN-401). |
| Control de cuentas/permisos | **PocketBase** | Plan, permisos y aislamiento multi-tenant. |
| Empaquetado | **Docker** | Herramienta BI contenedorizada. |

## 3. Modelo de datos

- **Lectura:** tablas de agregación en ClickHouse por tema
  (ingresos/`Fact_Suscripcion`, reseñas/`Fact_Resena`, precios/`Fact_Precio_Mercado`,
  uso/`Fact_Uso_Plataforma`), con dimensiones de filtro `Dim_Tiempo`, `Dim_Mercado`,
  `Dim_Cliente`, `Dim_Plan`.
- **Metadatos de dashboard (PocketBase):** colección `dashboards`
  (`id`, `nombre`, `tema`, `version`, `estado`, `definicion`) y colección
  `publicaciones` (`dashboard_id`, `cuenta_id`, `permisos`, `version`, `calidad_ok`,
  `publicado_en`).

## 4. Secuencia de implementación

1. Conectar la herramienta BI a ClickHouse (solo lectura). *(RF-301, RN-404)*
2. Implementar la definición de dashboards con filtros por las 4 Dim. *(RF-302)*
3. Implementar versionado de dashboards (borrador→publicable). *(RF-303)*
4. Implementar el gate de calidad: verificar sello CU-O04 vigente. *(RF-305, RN-401)*
5. Implementar la publicación por cuenta con permisos y plan. *(RF-306)*
6. Implementar el registro de publicaciones y el historial de versiones. *(RF-307, RF-308)*
7. Reforzar aislamiento multi-tenant. *(RNF-302, RN-403)*
8. Contenedorizar y validar latencia < 200 ms. *(RNF-301, RNF-304)*

## 5. Riesgos

| Riesgo | Impacto | Mitigación |
|---|---|---|
| Publicar sin calidad | Exponer datos sucios | Gate CU-O04 obligatorio (RN-401, RF-305). |
| Fuga entre cuentas | Brecha de confidencialidad | Aislamiento multi-tenant (RN-403). |
| Lectura de capa incorrecta | Salto de capa | Solo ClickHouse (RN-404, RT-01). |
| Plan vencido recibe dashboard | Inconsistencia comercial | Verificación de `Dim_Plan` (RN-402). |
| Latencia alta | Mala experiencia | Agregaciones pre-calculadas + ClickHouse (RNF-301). |

## 6. Trazabilidad de cumplimiento constitucional

- Princ. X (no publicar sin calidad) → RF-305, RN-401.
- Arquitectura de capas → RN-404 (solo ClickHouse). Princ. VIII (Docker) → §2, paso 8.
