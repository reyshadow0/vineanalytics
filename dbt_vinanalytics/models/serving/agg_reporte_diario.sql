-- agg_reporte_diario — consolidación operativa por Dim_Tiempo para el reporte
-- diario CU-O16 (OP11). Una fila por período con las métricas del día:
--   · API   (Fact_Consumo_API):     llamadas, errores, latencia, ingreso
--   · Uso   (Fact_Uso_Plataforma):  sesiones, funciones, usuarios, dashboards
--   · Incidentes/disponibilidad (Fact_Disponibilidad): incidentes, uptime, despliegues
--
-- Princ. VI: la consolidación es transformación analítica → vive aquí, declarativa.
-- reportes/reporte_diario.py SOLO lee esta agregación desde ClickHouse (RN-1202),
-- verifica el sello de calidad (RF-1104) y archiva. No recalcula nada.
-- RN-1204: cada métrica es trazable a su Fact de origen (ver comentarios).
{{ config(materialized='view') }}

with periodos as (
    -- Períodos con actividad operativa (evita filas vacías por períodos sin hechos).
    select distinct id_tiempo from {{ source('dw_negocio', 'fact_consumo_api') }}
    union
    select distinct id_tiempo from {{ source('dw_negocio', 'fact_uso_plataforma') }}
    union
    select distinct id_tiempo from {{ source('dw_negocio', 'fact_disponibilidad') }}
),
api as (
    select id_tiempo,
           sum(llamadas)    as api_llamadas,
           sum(errores)     as api_errores,
           avg(latencia_ms) as api_latencia_ms,
           sum(ingreso_api) as api_ingreso
    from {{ source('dw_negocio', 'fact_consumo_api') }}
    group by id_tiempo
),
uso as (
    select id_tiempo,
           sum(sesiones)         as uso_sesiones,
           sum(funciones_usadas) as uso_funciones,
           sum(usuarios_activos) as uso_usuarios_activos,
           sum(dashboards_vistos) as uso_dashboards
    from {{ source('dw_negocio', 'fact_uso_plataforma') }}
    group by id_tiempo
),
disp as (
    select id_tiempo,
           sum(incidentes)  as incidentes,
           avg(uptime)      as uptime,
           sum(despliegues) as despliegues
    from {{ source('dw_negocio', 'fact_disponibilidad') }}
    group by id_tiempo
)

select
    pe.id_tiempo,
    dt.periodo,
    -- API
    cast(coalesce(api.api_llamadas, 0) as bigint)  as api_llamadas,
    cast(coalesce(api.api_errores, 0) as int)      as api_errores,
    round(coalesce(api.api_latencia_ms, 0), 2)     as api_latencia_ms,
    round(coalesce(api.api_ingreso, 0), 2)         as api_ingreso,
    -- Uso de plataforma
    cast(coalesce(uso.uso_sesiones, 0) as bigint)        as uso_sesiones,
    cast(coalesce(uso.uso_funciones, 0) as bigint)       as uso_funciones,
    cast(coalesce(uso.uso_usuarios_activos, 0) as int)   as uso_usuarios_activos,
    cast(coalesce(uso.uso_dashboards, 0) as bigint)      as uso_dashboards,
    -- Incidentes / disponibilidad
    cast(coalesce(disp.incidentes, 0) as int)   as incidentes,
    round(coalesce(disp.uptime, 0), 3)          as uptime,
    cast(coalesce(disp.despliegues, 0) as int)  as despliegues
from periodos pe
join {{ source('dw_negocio', 'dim_tiempo') }} dt on pe.id_tiempo = dt.id_tiempo
left join api  on pe.id_tiempo = api.id_tiempo
left join uso  on pe.id_tiempo = uso.id_tiempo
left join disp on pe.id_tiempo = disp.id_tiempo
