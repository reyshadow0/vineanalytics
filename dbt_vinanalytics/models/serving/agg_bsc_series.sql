-- agg_bsc_series — series temporales y rankings del BSC (formato largo).
--
-- Princ. VI: ÚNICA fuente de la agregación de series del BSC. Reemplaza el SQL
-- imperativo de clickhouse/populate.py::_pop_bsc (16 consultas + enumerate) y el
-- DUPLICADO en app.py::api_bsc_series. El campo `orden` (índice cronológico o
-- ranking que en Python venía de enumerate()) se reproduce con row_number() sobre
-- el MISMO ORDER BY de cada consulta original → mismas filas, mismo orden.
--   perspectiva ∈ {financiera, cliente, procesos, ecosistema}
--   etiqueta    = periodo 'AAAA-MM' o nombre (plan/país/región/partner/etapa)
{{ config(materialized='view') }}

with periodos as (
    select max(id_tiempo) as latest
    from {{ source('dw_negocio', 'dim_tiempo') }}
),
emb as (
    select
        sum(case when f.id_tiempo = p.latest then f.leads else 0 end)         as leads,
        sum(case when f.id_tiempo = p.latest then f.oportunidades else 0 end) as oportunidades,
        sum(case when f.id_tiempo = p.latest then f.conversiones else 0 end)  as conversiones
    from {{ source('dw_negocio', 'fact_conversion') }} f
    cross join periodos p
)

-- ── FINANCIERA ────────────────────────────────────────────────────────────────
select 'financiera' as perspectiva, 'mrr' as serie, t.periodo as etiqueta,
       cast(row_number() over (order by t.id_tiempo) - 1 as int) as orden,
       round(coalesce(sum(f.mrr), 0), 4) as valor
from {{ source('dw_negocio', 'fact_suscripcion') }} f
join {{ source('dw_negocio', 'dim_tiempo') }} t on f.id_tiempo = t.id_tiempo
where f.es_churn = 0
group by t.periodo, t.id_tiempo

union all
select 'financiera', 'api', t.periodo,
       cast(row_number() over (order by t.id_tiempo) - 1 as int),
       round(coalesce(sum(f.ingreso_api), 0), 4)
from {{ source('dw_negocio', 'fact_consumo_api') }} f
join {{ source('dw_negocio', 'dim_tiempo') }} t on f.id_tiempo = t.id_tiempo
group by t.periodo, t.id_tiempo

union all
select 'financiera', 'cac', t.periodo,
       cast(row_number() over (order by t.id_tiempo) - 1 as int),
       round(coalesce(avg(f.cac), 0), 4)
from {{ source('dw_negocio', 'fact_conversion') }} f
join {{ source('dw_negocio', 'dim_tiempo') }} t on f.id_tiempo = t.id_tiempo
where f.conversiones > 0
group by t.periodo, t.id_tiempo

union all
select 'financiera', 'por_plan', pl.nombre,
       cast(row_number() over (order by sum(f.mrr) desc) - 1 as int),
       round(coalesce(sum(f.mrr), 0), 4)
from {{ source('dw_negocio', 'fact_suscripcion') }} f
join {{ source('dw_negocio', 'dim_plan') }} pl on f.id_plan = pl.id_plan
cross join periodos p
where f.id_tiempo = p.latest and f.es_churn = 0
group by pl.nombre

-- ── CLIENTE ───────────────────────────────────────────────────────────────────
union all
select perspectiva, serie, etiqueta, cast(orden as int), valor
from (
    select 'cliente' as perspectiva, 'nuevos_mercado' as serie, m.pais as etiqueta,
           row_number() over (order by sum(f.es_nuevo) desc) - 1 as orden,
           round(coalesce(sum(f.es_nuevo), 0), 4) as valor
    from {{ source('dw_negocio', 'fact_suscripcion') }} f
    join {{ source('dw_negocio', 'dim_cliente') }} c on f.id_cliente = c.id_cliente
    join {{ source('dw_negocio', 'dim_mercado') }} m on c.id_mercado = m.id_mercado
    group by m.pais
) z
where orden < 12

union all
select 'cliente', 'conversion', t.periodo,
       cast(row_number() over (order by t.id_tiempo) - 1 as int),
       round(coalesce(sum(f.conversiones) * 100.0 / nullif(sum(f.leads), 0), 0), 4)
from {{ source('dw_negocio', 'fact_conversion') }} f
join {{ source('dw_negocio', 'dim_tiempo') }} t on f.id_tiempo = t.id_tiempo
group by t.periodo, t.id_tiempo

union all
select 'cliente', 'churn', t.periodo,
       cast(row_number() over (order by t.id_tiempo) - 1 as int),
       round(coalesce(sum(f.cancelacion) * 100.0 / nullif(sum(f.activo) + sum(f.cancelacion), 0), 0), 4)
from {{ source('dw_negocio', 'fact_retencion') }} f
join {{ source('dw_negocio', 'dim_tiempo') }} t on f.id_tiempo = t.id_tiempo
group by t.periodo, t.id_tiempo

union all
select 'cliente', 'nps', t.periodo,
       cast(row_number() over (order by t.id_tiempo) - 1 as int),
       round(coalesce(
           (sum(case when f.nps_score >= 9 then 1 else 0 end)
            - sum(case when f.nps_score between 0 and 6 then 1 else 0 end)) * 100.0
           / nullif(sum(case when f.nps_score >= 0 then 1 else 0 end), 0), 0), 4)
from {{ source('dw_negocio', 'fact_uso_plataforma') }} f
join {{ source('dw_negocio', 'dim_tiempo') }} t on f.id_tiempo = t.id_tiempo
group by t.periodo, t.id_tiempo

union all
select 'cliente', 'embudo', 'leads', 0, round(coalesce(leads, 0), 4) from emb
union all
select 'cliente', 'embudo', 'oportunidades', 1, round(coalesce(oportunidades, 0), 4) from emb
union all
select 'cliente', 'embudo', 'conversiones', 2, round(coalesce(conversiones, 0), 4) from emb

-- ── PROCESOS ──────────────────────────────────────────────────────────────────
union all
select 'procesos', 'uptime', t.periodo,
       cast(row_number() over (order by t.id_tiempo) - 1 as int),
       round(coalesce(avg(f.uptime), 0), 4)
from {{ source('dw_negocio', 'fact_disponibilidad') }} f
join {{ source('dw_negocio', 'dim_tiempo') }} t on f.id_tiempo = t.id_tiempo
group by t.periodo, t.id_tiempo

union all
select 'procesos', 'ttm', t.periodo,
       cast(row_number() over (order by t.id_tiempo) - 1 as int),
       round(coalesce(avg(f.time_to_market_dias), 0), 4)
from {{ source('dw_negocio', 'fact_disponibilidad') }} f
join {{ source('dw_negocio', 'dim_tiempo') }} t on f.id_tiempo = t.id_tiempo
group by t.periodo, t.id_tiempo

union all
select 'procesos', 'latencia_region', m.region_geo,
       cast(row_number() over (order by avg(f.latencia_ms) desc) - 1 as int),
       round(coalesce(avg(f.latencia_ms), 0), 4)
from {{ source('dw_negocio', 'fact_disponibilidad') }} f
join {{ source('dw_negocio', 'dim_mercado') }} m on f.id_mercado = m.id_mercado
cross join periodos p
where f.id_tiempo = p.latest
group by m.region_geo

union all
select 'procesos', 'incidentes', t.periodo,
       cast(row_number() over (order by t.id_tiempo) - 1 as int),
       round(coalesce(sum(f.incidentes), 0), 4)
from {{ source('dw_negocio', 'fact_disponibilidad') }} f
join {{ source('dw_negocio', 'dim_tiempo') }} t on f.id_tiempo = t.id_tiempo
group by t.periodo, t.id_tiempo

-- ── ECOSISTEMA ────────────────────────────────────────────────────────────────
union all
select 'ecosistema', 'ingresos_partner', pa.nombre,
       cast(row_number() over (order by sum(f.ingreso_api) desc) - 1 as int),
       round(coalesce(sum(f.ingreso_api), 0), 4)
from {{ source('dw_negocio', 'fact_consumo_api') }} f
join {{ source('dw_negocio', 'dim_partner_api') }} pa on f.id_partner = pa.id_partner
group by pa.nombre

union all
select 'ecosistema', 'llamadas', t.periodo,
       cast(row_number() over (order by t.id_tiempo) - 1 as int),
       round(coalesce(sum(f.llamadas), 0), 4)
from {{ source('dw_negocio', 'fact_consumo_api') }} f
join {{ source('dw_negocio', 'dim_tiempo') }} t on f.id_tiempo = t.id_tiempo
group by t.periodo, t.id_tiempo

union all
select 'ecosistema', 'conexiones_partner', pa.nombre,
       cast(row_number() over (order by max(f.conexiones_activas) desc) - 1 as int),
       round(coalesce(max(f.conexiones_activas), 0), 4)
from {{ source('dw_negocio', 'fact_integracion_partner') }} f
join {{ source('dw_negocio', 'dim_partner_api') }} pa on f.id_partner = pa.id_partner
cross join periodos p
where f.id_tiempo = p.latest
group by pa.nombre
