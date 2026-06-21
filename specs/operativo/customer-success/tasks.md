# customer-success · Tareas (speckit-tasks)

> Paquete: `customer-success` · OP10 · CU-O14, CU-O15. Tareas atómicas ordenadas por
> dependencia. Marca `[x]` al completar. Citan RF/RN/CA de
> [customer-success-spec.md](customer-success-spec.md).

---

## A. CU-O14 — Registrar onboarding y ticket de soporte

- [ ] **T-01** Modelar la colección PocketBase `onboarding` (`Dim_Cliente`, `Dim_Tiempo`). *(RF-1001)*
- [ ] **T-02** Modelar la colección PocketBase `tickets` (categoría, prioridad, tiempos, NPS). *(RF-1002)*
- [ ] **T-03** Implementar el ciclo de vida del ticket y el cálculo de tiempos (primera respuesta/resolución). *(RF-1003, RN-1101)*
- [ ] **T-04** Capturar señales de NPS por cuenta. *(RF-1004)*
- [ ] **T-05** Disparar el onboarding automáticamente al alta de cuenta en OP5. *(RN-1104)*
- [ ] **T-06** Prueba: onboarding de cuenta nueva queda registrado con pasos/estado. *(CA-1101, Esc-1101)*
- [ ] **T-07** Prueba: ticket nominal clasificado, con tiempos y ciclo de vida. *(CA-1102, Esc-1102)*
- [ ] **T-08** Prueba: transición inválida de ticket (`CERRADO`→`EN_PROCESO`) rechazada. *(Esc-1105, RN-1101)*

## B. CU-O15 — Consultar uso de la plataforma por cliente

- [ ] **T-09** Implementar la consulta de uso/adopción desde ClickHouse (agregado de `Fact_Uso_Plataforma`). *(RF-1005, RN-1102)*
- [ ] **T-10** Vincular alertas de churn (OP9) a la priorización de retención. *(RF-1006, RN-1103)*
- [ ] **T-11** Exponer el reporte de adopción/soporte por cuenta. *(RF-1007)*
- [ ] **T-12** Prueba: consulta de uso lee de ClickHouse (sesiones/funciones/frecuencia). *(CA-1103, Esc-1103)*
- [ ] **T-13** Prueba: alerta de churn prioriza y vincula acción de retención. *(CA-1104, Esc-1104)*
- [ ] **T-14** Prueba: intento de leer eventos crudos (salto de capa) es rechazado. *(Esc-1106, RN-1102)*

## C. Privacidad, contenedores y cierre

- [ ] **T-15** Proteger datos de cliente y soporte (privacidad). *(RNF-1003)*
- [ ] **T-16** Confirmar que onboarding/tickets viven en PocketBase y el uso se consulta agregado. *(RNF-1001, RT-01)*
- [ ] **T-17** Contenedorizar componentes en `docker-compose.yml` (versión fija). *(RNF-1004, RT-17)*
- [ ] **T-18** Verificar arranque con `docker compose up`. *(RT-17)*
- [ ] **T-19** Validar spec contra constitución y completar [checklist.md](checklist.md). *(RT-18, RT-19)*
