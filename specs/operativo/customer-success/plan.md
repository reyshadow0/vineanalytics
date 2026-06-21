# customer-success · Plan de implementación (speckit-plan)

> Paquete: `customer-success` · OP10 · CU-O14, CU-O15 · Customer Success.
> Spec fuente: [customer-success-spec.md](customer-success-spec.md). Marco:
> [000-general](../000-general/operativo-general-spec.md).

---

## 1. Arquitectura del paquete

```
suscripciones (OP5)        alertas (OP9, churn)
   │ cuenta nueva                │ acción de retención
   ▼                             ▼
┌──────────────────────────────────────────┐
│  Onboarding + Soporte (CU-O14)            │ ──► PocketBase (operacional)
│  - pasos, estado, tickets, tiempos, NPS   │
└──────────────────────────────────────────┘
┌──────────────────────────────────────────┐
│  Consulta de uso/adopción (CU-O15)        │ ◄── ClickHouse (Fact_Uso_Plataforma agregado)
│  - sesiones, funciones, frecuencia         │
└──────────────────────────────────────────┘
                     │ métricas
                     ▼
        reportes-operativos (OP11) · BSC cliente
```

## 2. Herramientas y componentes

| Componente | Tecnología | Responsabilidad |
|---|---|---|
| Onboarding/tickets | **PocketBase** + herramienta de tickets/CRM | Registrar CU-O14. |
| Consulta de uso | **ClickHouse** (lectura) | Adopción por cuenta (CU-O15, RN-1102). |
| Vínculo de retención | Integración con `alertas` | Priorizar cuentas en riesgo (RN-1103). |
| Empaquetado | **Docker** | Componentes contenedorizados. |

## 3. Modelo de datos

- **PocketBase — `onboarding`**: `cuenta_id` → `Dim_Cliente`, `paso`, `estado`, `fecha` → `Dim_Tiempo`.
- **PocketBase — `tickets`**: `cuenta_id`, `categoria`, `prioridad`, `estado`,
  `abierto_en`, `resuelto_en`, `nps`.
- **Consulta (ClickHouse):** agregaciones de `Fact_Uso_Plataforma` por `Dim_Cliente`
  (sesiones, dashboards vistos, funciones, frecuencia).

## 4. Secuencia de implementación

1. Modelar `onboarding` y `tickets` en PocketBase. *(RF-1001, RF-1002)*
2. Implementar el ciclo de vida del ticket y el cálculo de tiempos. *(RF-1003, RN-1101)*
3. Capturar NPS por cuenta. *(RF-1004)*
4. Implementar la consulta de uso/adopción desde ClickHouse. *(RF-1005, RN-1102)*
5. Vincular alertas de churn a acciones de retención. *(RF-1006, RN-1103)*
6. Disparar onboarding al alta de cuenta (OP5). *(RN-1104)*
7. Exponer reporte de adopción/soporte. *(RF-1007)*
8. Contenedorizar y validar. *(RNF-1004)*

## 5. Riesgos

| Riesgo | Impacto | Mitigación |
|---|---|---|
| Onboarding no registrado | Baja adopción no detectada | Disparo automático al alta (RN-1104). |
| Lectura de eventos crudos | Salto de capa | Consultar agregado en ClickHouse (RN-1102). |
| Alerta de churn sin acción | Churn evitable | Vínculo retención (RN-1103). |
| Datos sensibles expuestos | Riesgo legal | Privacidad (RNF-1003). |

## 6. Trazabilidad de cumplimiento constitucional

- OT9/OE1 (retención) → §1. Arquitectura de capas → RN-1102. Princ. VIII (Docker) → §2, paso 8.
