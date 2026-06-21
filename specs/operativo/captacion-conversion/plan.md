# captacion-conversion · Plan de implementación (speckit-plan)

> Paquete: `captacion-conversion` · OP6 · CU-O09, CU-O10 · Growth & Marketing.
> Spec fuente: [captacion-conversion-spec.md](captacion-conversion-spec.md). Marco:
> [000-general](../000-general/operativo-general-spec.md).

---

## 1. Arquitectura del paquete

```
Growth & Marketing
       │  configura campaña
       ▼
┌────────────────────────────┐   eventos impresión/clic/lead
│  Orquestador de campañas    │ ─────────────► Fact_Campana (vía ETL)
│  (CU-O09, automatizado)     │
└──────────────┬─────────────┘
               │ leads (deduplicados)
               ▼
┌────────────────────────────┐   conversión (etapa/atribución)
│  Registro de conversión     │ ─────────────► Fact_Conversion (vía ETL)
│  (CU-O10)                   │
└──────────────┬─────────────┘
               │ conversión = cliente
               ▼
        suscripciones (OP5)  ──► alta de cuenta
```

## 2. Herramientas y componentes

| Componente | Tecnología | Responsabilidad |
|---|---|---|
| Orquestador de campañas | Integración de marketing (HubSpot/Marketo) + **Airflow** | Ejecutar campañas automatizadas (CU-O09). |
| Registro de eventos | Servicio operacional | Capturar impresiones/clics/leads/conversiones. |
| Deduplicador de leads | Lógica por clave de prospecto | Evitar doble conteo (RN-702). |
| Motor de atribución | Lógica única documentada | Atribuir conversión a campaña/canal (RN-703). |
| Empaquetado | **Docker** | Componentes contenedorizados. |

## 3. Modelo de datos

- **Eventos → `Fact_Campana`**: `campana_id` → `Dim_Campana`, `canal` →
  `Dim_Canal_Adquisicion`, `mercado` → `Dim_Mercado`, `impresiones`, `clics`, `gasto`, `leads`.
- **Eventos → `Fact_Conversion`**: `lead_id`, `etapa`, `fuente`, `resultado`,
  `cliente` → `Dim_Cliente`, `mercado` → `Dim_Mercado`, `campana_atribuida`.
- **Indicadores:** CAC = gasto / nuevos_clientes; conversión = conversiones / leads × 100.

## 4. Secuencia de implementación

1. Implementar la configuración de campañas (canal/mercado/segmento/presupuesto). *(RF-601)*
2. Implementar la ejecución automatizada vía Airflow. *(RF-602, RNF-601)*
3. Capturar y registrar métricas en `Fact_Campana`. *(RF-603)*
4. Implementar deduplicación de leads. *(RF-604, RN-702)*
5. Implementar el registro de conversiones en `Fact_Conversion`. *(RF-605)*
6. Implementar el motor de atribución único. *(RF-606, RN-703)*
7. Calcular insumos de CAC y tasa de conversión. *(RF-607, RN-704)*
8. Integrar la entrega de conversión→alta a `suscripciones`. *(RF-608, RN-705)*
9. Disparar alerta ante caída de conversión. *(RN-706)*
10. Contenedorizar y validar. *(RNF-604)*

## 5. Riesgos

| Riesgo | Impacto | Mitigación |
|---|---|---|
| Leads duplicados | CAC/embudo distorsionado | Dedup (RN-702). |
| Doble atribución | Métricas infladas | Motor de atribución único (RN-703). |
| Cuenta duplicada al convertir | Padrón sucio | Entrega idempotente a OP5 (RN-705). |
| Campaña sin medición | Decisiones a ciegas | Registro obligatorio en `Fact_Campana` (RF-603). |
| Privacidad de prospectos | Riesgo legal | Tratamiento conforme normativa (RNF-605). |

## 6. Trazabilidad de cumplimiento constitucional

- OT1/OT2 (automatización/analítica) → RF-602, RNF-601. Princ. X (dedup) → RN-702.
- Arquitectura de capas → RNF-603. Princ. VIII (Docker) → §2, paso 10.
