# suscripciones · Plan de implementación (speckit-plan)

> Paquete: `suscripciones` · OP5 · CU-O08 · Administrador.
> Spec fuente: [suscripciones-spec.md](suscripciones-spec.md). Marco:
> [000-general](../000-general/operativo-general-spec.md).

---

## 1. Arquitectura del paquete

```
Administrador
     │  alta / cambios
     ▼
┌───────────────────────────────┐
│  Gestión de cuentas y          │   estado/plan vigente
│  suscripciones (CU-O08)        │ ─────────────────────► dashboards (OP3) · api-publica (OP4)
│  - dedup de cuentas            │
│  - validación plan/facturación │   eventos de suscripción
│  - ciclo de vida (estados)     │ ─────────────────────► ETL (OP2) ─► Fact_Suscripcion
└───────────────┬───────────────┘
                ▼
          PocketBase (operacional)
```

## 2. Herramientas y componentes

| Componente | Tecnología | Responsabilidad |
|---|---|---|
| Padrón de cuentas/suscripciones | **PocketBase** | Persistir cuentas, planes, estados (CU-O08). |
| Validador de plan/facturación | Lógica en servicio | Activar solo con datos válidos (RF-504). |
| Máquina de estados | Lógica de transición | Gobernar `Dim_Estado_Suscripcion` (RF-505). |
| Emisor de eventos | Hacia el ETL | Proyectar a `Fact_Suscripcion` (RF-506). |
| Empaquetado | **Docker** | PocketBase + servicio contenedorizados. |

## 3. Modelo de datos

- **PocketBase — `cuentas`**: `id`, `razon_social`, `id_fiscal`, `email_corp`,
  `tipo`, `tamano`, `segmento`, `mercado_id` → `Dim_Mercado` (→ `Dim_Cliente` en DW).
- **PocketBase — `suscripciones`**: `id`, `cuenta_id`, `plan` → `Dim_Plan`, `monto`,
  `moneda`, `periodo`, `estado` → `Dim_Estado_Suscripcion`, `inicio`, `fin`.
- **Eventos → `Fact_Suscripcion`**: `cuenta`, `plan`, `tipo_evento`
  (alta/upgrade/downgrade/pausa/cancelacion), `monto`, `fecha`, `MRR_delta`.

## 4. Secuencia de implementación

1. Modelar colecciones `cuentas` y `suscripciones` en PocketBase. *(RF-501, RF-502)*
2. Implementar deduplicación de cuentas. *(RF-503, RN-601)*
3. Implementar validación de plan/facturación para activar. *(RF-504, RN-602)*
4. Implementar la máquina de estados del ciclo de vida. *(RF-505, RN-604)*
5. Implementar emisión de eventos a `Fact_Suscripcion`. *(RF-506, RN-605)*
6. Exponer plan/estado vigente a `dashboards` y `api-publica`. *(RF-507, RN-603)*
7. Añadir historial/auditoría de cambios. *(RNF-503)*
8. Contenedorizar y validar. *(RNF-504)*

## 5. Riesgos

| Riesgo | Impacto | Mitigación |
|---|---|---|
| Cuentas duplicadas | Padrón sucio, MRR inflado | Dedup obligatoria (RN-601). |
| Acceso tras cancelación | Uso indebido | Estado como fuente de verdad de acceso (RN-603, Esc-505). |
| Transición inválida | Estado inconsistente | Máquina de estados (RN-604). |
| Datos de pago expuestos | Brecha | Sin tarjetas en claro (RNF-505). |
| Doble conteo en `Fact_Suscripcion` | Métricas erróneas | Eventos idempotentes con clave de evento. |

## 6. Trazabilidad de cumplimiento constitucional

- Princ. X (dedup de cuentas) → RN-601. Arquitectura de capas → RN-606 (PocketBase, no
  lectura directa de dashboards). Princ. VIII (Docker) → §2, paso 8.
