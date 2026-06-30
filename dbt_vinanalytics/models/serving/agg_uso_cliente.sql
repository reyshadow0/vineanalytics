-- agg_uso_cliente — uso/adopción por cliente (CU-O15 · OP10) desde Fact_Uso_Plataforma.
--
-- Una fila por Dim_Cliente con las métricas que pide RF-1005: sesiones, dashboards
-- vistos, funciones y FRECUENCIA (sesiones por período activo), más adopción y NPS.
--
-- Princ. VI: la agregación analítica vive aquí, declarativa (no en Python). CU-O15
-- la consulta SOLO agregada desde ClickHouse (serving.uso_por_cliente, RN-1102);
-- prohibido leer los eventos crudos de fact_uso_plataforma saltando capas.
-- RN-1204/Princ. VII: cada métrica es trazable a Fact_Uso_Plataforma / Dim_Cliente.
{{ config(materialized='view') }}

with uso as (
    select
        id_cliente,
        count(distinct id_tiempo)                          as periodos,
        sum(sesiones)                                      as sesiones,
        sum(dashboards_vistos)                             as dashboards_vistos,
        sum(funciones_usadas)                              as funciones_total,
        round(avg(funciones_usadas), 1)                    as funciones_promedio,
        round(avg(usuarios_activos), 0)                    as usuarios_activos,
        round(avg(usuarios_totales), 0)                    as usuarios_totales,
        avg(case when nps_score >= 0 then nps_score end)   as nps_promedio,
        max(id_tiempo)                                     as ultimo_periodo
    from {{ source('dw_negocio', 'fact_uso_plataforma') }}
    group by id_cliente
)

select
    u.id_cliente,
    coalesce(dc.nombre, '')                                as nombre,
    cast(coalesce(dc.id_plan, 0) as int)                   as id_plan,
    cast(u.periodos as int)                                as periodos,
    cast(u.sesiones as bigint)                             as sesiones,
    cast(u.dashboards_vistos as bigint)                    as dashboards_vistos,
    cast(u.funciones_total as bigint)                      as funciones_total,
    cast(coalesce(u.funciones_promedio, 0) as double)      as funciones_promedio,
    cast(u.usuarios_activos as int)                        as usuarios_activos,
    cast(u.usuarios_totales as int)                        as usuarios_totales,
    -- Frecuencia de uso: sesiones por período activo (RF-1005).
    round(u.sesiones / nullif(u.periodos, 0), 2)           as frecuencia_sesiones,
    -- Adopción: usuarios activos / totales (apoya adopción ≥ 70 %, RNF-1005).
    round(case when u.usuarios_totales > 0
               then u.usuarios_activos / u.usuarios_totales * 100 else 0 end, 1) as adopcion_pct,
    round(coalesce(u.nps_promedio, 0), 2)                  as nps_promedio,
    cast(u.ultimo_periodo as int)                          as ultimo_periodo
from uso u
left join {{ source('dw_negocio', 'dim_cliente') }} dc on u.id_cliente = dc.id_cliente
