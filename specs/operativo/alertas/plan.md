# alertas · Plan de implementación (speckit-plan)

> Paquete: `alertas` · OP9 · CU-O13 · Sistema.
> Spec fuente: [alertas-spec.md](alertas-spec.md). Marco:
> [000-general](../000-general/operativo-general-spec.md).

---

## 1. Arquitectura del paquete

```
machine-learning ─┐
observabilidad   ─┤  señales (churn, precio, uptime,
ingesta-datos    ─┤  ingesta, API, conversión)
api-publica      ─┤            │
captacion-conv.  ─┘            ▼
                  ┌──────────────────────────────┐
                  │  Motor de alertas (CU-O13)    │
                  │  - umbrales / anomalías       │
                  │  - clasificación (tipo/sev/causa)
                  │  - dedup / agrupación          │
                  │  - ciclo de vida              │
                  └──────────────┬───────────────┘
                                 ▼
              registro de alertas ─► notificación al responsable
                                  └► reporte de alertas (OP11)
```

## 2. Herramientas y componentes

| Componente | Tecnología | Responsabilidad |
|---|---|---|
| Motor de reglas/umbral | Servicio de alertas (p. ej. Alertmanager + lógica propia) | Evaluar umbrales/anomalías (RF-901). |
| Ingesta de señales | Bus/colas o webhooks | Recibir señales de otros paquetes (RF-902). |
| Clasificador | Lógica de tipo/severidad/causa | Etiquetar la alerta (RF-903). |
| Notificador | Email/Slack/webhook | Enrutar al responsable (RF-905). |
| Registro de alertas | Capa operacional | Persistir alertas y su estado (RF-904). |
| Empaquetado | **Docker** | Servicio de alertas contenedorizado. |

## 3. Modelo de datos

- **Alerta:** `id`, `tipo` (churn|precio|uso|ingesta|uptime|api|conversion),
  `severidad` (info|warning|critical), `causa`, `origen` (paquete emisor),
  `fact_ref` (`Fact_Retencion`/`Fact_Precio_Mercado`/…), `estado`
  (abierta|reconocida|resuelta|silenciada), `timestamp`, `clave_dedup`.
- **Umbrales:** tabla configurable por tipo (churn ≥ X, precio fuera de [min,max], etc.).

## 4. Secuencia de implementación

1. Definir el contrato de señales de entrada (esquema común). *(RF-902)*
2. Implementar el motor de umbral/anomalías para churn y precio. *(RF-901)*
3. Implementar la recepción de señales de los demás paquetes. *(RF-902, RN-1001)*
4. Implementar clasificación (tipo/severidad/causa). *(RF-903)*
5. Implementar deduplicación/agrupación anti-tormenta. *(RF-906, RN-1004)*
6. Implementar registro y ciclo de vida de la alerta. *(RF-904, RF-907)*
7. Implementar el enrutamiento/notificación por responsable. *(RF-905)*
8. Garantizar entrega fiable (reintentos). *(RNF-902)*
9. Contenedorizar y validar. *(RNF-904)*

## 5. Riesgos

| Riesgo | Impacto | Mitigación |
|---|---|---|
| Tormenta de alertas | Fatiga, alertas ignoradas | Dedup/agrupación (RN-1004). |
| Señal perdida | Incidente sin alerta | Entrega garantizada + reintentos (RNF-902). |
| Mala clasificación | Enrutamiento erróneo | Clasificador por tipo/severidad (RF-903). |
| Umbral mal calibrado | Falsos positivos/negativos | Umbrales configurables y revisados. |

## 6. Trazabilidad de cumplimiento constitucional

- Princ. X (alertas operativas obligatorias) → RN-1001, todo el paquete.
- RT-16 (transversal) centralizado aquí. Princ. VIII (Docker) → §2, paso 9.
