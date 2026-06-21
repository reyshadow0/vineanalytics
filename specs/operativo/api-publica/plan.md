# api-publica · Plan de implementación (speckit-plan)

> Paquete: `api-publica` · OP4 · CU-O07 · Sistema / Partner.
> Spec fuente: [api-publica-spec.md](api-publica-spec.md). Marco:
> [000-general](../000-general/operativo-general-spec.md).

---

## 1. Arquitectura del paquete

```
Partner / Integrador
        │  HTTPS + API key
        ▼
┌──────────────────────────────────────────────┐
│  Servicio API pública (OpenAPI /v1, SDD)      │
│  1. Autenticación (401)                       │   plan/cuota
│  2. Rate limiting por plan (429) ◄────────────┼──── PocketBase (OP5)
│  3. Validación de contrato (400)              │
│  4. Servir datos ───────────────────────────► ClickHouse (serving, < 200 ms)
│  5. Registrar llamada ──────────────────────► Fact_Consumo_API (vía pipeline)
└──────────────────────────────────────────────┘
        │ métricas / errores
        ▼
   observabilidad (OP7) · alertas (OP9)
```

## 2. Herramientas y componentes

| Componente | Tecnología | Responsabilidad |
|---|---|---|
| Servicio API | **FastAPI** (OpenAPI nativo) en contenedor | Exponer endpoints `/v1` versionados. |
| Autenticación | API key / token de partner | Validar credenciales (RF-402). |
| Rate limiting | Gateway / middleware por plan | Aplicar cuotas (RF-403). |
| Serving de datos | **ClickHouse** | Fuente única de datos servidos (RN-503). |
| Registro de consumo | Emisor a `Fact_Consumo_API` | Auditar llamadas (RF-405). |
| Empaquetado | **Docker** | Servicio API contenedorizado. |

## 3. Modelo de datos

- **Registro de consumo → `Fact_Consumo_API`**: `timestamp`, `endpoint`, `version`,
  `partner_id` → `Dim_Partner_API`, `latencia_ms`, `codigo_estado`, `bytes`, `plan`.
- **Cuotas/credenciales (PocketBase):** colección `api_keys`
  (`partner_id`, `clave_hash`, `plan`, `cuota`, `estado`).
- **Contrato:** especificación **OpenAPI** versionada (`openapi/v1.yaml`).

## 4. Secuencia de implementación

1. Definir el contrato OpenAPI `/v1` (SDD-first) antes de codificar. *(RF-401, OT3)*
2. Implementar autenticación por API key. *(RF-402, RN-501)*
3. Implementar rate limiting por plan/partner. *(RF-403, RN-502)*
4. Implementar handlers que sirven desde ClickHouse. *(RF-404, RN-503)*
5. Implementar validación de esquema entrada/salida contra OpenAPI. *(RF-406)*
6. Implementar el registro de cada llamada en `Fact_Consumo_API`. *(RF-405, RN-504)*
7. Implementar versionado/deprecación controlada. *(RF-407, RN-506)*
8. Emitir métricas/errores a observabilidad/alertas. *(RN-505)*
9. Contenedorizar y validar latencia < 200 ms. *(RNF-401, RNF-405)*

## 5. Riesgos

| Riesgo | Impacto | Mitigación |
|---|---|---|
| Abuso / DoS por exceso de llamadas | Caída de servicio | Rate limiting por plan (RF-403). |
| Fuga de datos sin auth | Brecha de seguridad | Autenticación obligatoria (RN-501). |
| Servir desde capa incorrecta | Salto de capa | Solo ClickHouse (RN-503). |
| Cambios rompientes en `/v1` | Integraciones rotas | Versionado mayor (RN-506). |
| Pico de errores no detectado | Mala experiencia partner | Alertas por umbral (RN-505). |

## 6. Trazabilidad de cumplimiento constitucional

- OT3 (SDD/OpenAPI) → RF-401, paso 1. Arquitectura de capas → RN-503.
- Princ. VIII (Docker) → §2, paso 9. Princ. X (alertas) → RN-505.
