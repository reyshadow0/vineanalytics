-- agg_bsc_kpis — KPIs del Balanced Scorecard del período más reciente (una fila).
--
-- Princ. VI: ÚNICA fuente de la lógica de agregación del BSC. Reemplaza el SQL
-- imperativo de clickhouse/populate.py::_pop_bsc y el DUPLICADO en
-- app.py::api_bsc_kpis (líneas señaladas por la auditoría, regla B). Las fórmulas,
-- guardas de división (denominador 0 → 0) y redondeos son idénticos a los
-- originales → resultados sin cambios.
{{ config(materialized='view') }}

with periodos as (
    select max(id_tiempo) as latest, max(id_tiempo) - 100 as prev_year
    from {{ source('dw_negocio', 'dim_tiempo') }}
),
ult3 as (
    select id_tiempo
    from {{ source('dw_negocio', 'dim_tiempo') }}
    order by id_tiempo desc
    limit 3
),

-- ── Métricas crudas por tabla de hechos (filtradas al período `latest`) ────────
c_susc as (
    select
        sum(case when s.id_tiempo = p.latest    and s.es_churn = 0 then s.mrr else 0 end) as mrr_now,
        sum(case when s.id_tiempo = p.prev_year  and s.es_churn = 0 then s.mrr else 0 end) as mrr_prev
    from {{ source('dw_negocio', 'fact_suscripcion') }} s
    cross join periodos p
),
c_nuevos as (
    select sum(es_nuevo) as nuevos_trim
    from {{ source('dw_negocio', 'fact_suscripcion') }}
    where id_tiempo in (select id_tiempo from ult3)
),
c_api as (
    select sum(case when a.id_tiempo = p.latest then a.ingreso_api else 0 end) as api_now
    from {{ source('dw_negocio', 'fact_consumo_api') }} a
    cross join periodos p
),
c_conv as (
    select
        avg(case when cv.id_tiempo = p.latest and cv.conversiones > 0 then cv.cac end) as cac_now,
        sum(case when cv.id_tiempo = p.latest then cv.conversiones else 0 end)         as conv_num,
        sum(case when cv.id_tiempo = p.latest then cv.leads else 0 end)                as conv_den
    from {{ source('dw_negocio', 'fact_conversion') }} cv
    cross join periodos p
),
c_ret as (
    select
        avg(case when r.id_tiempo = p.latest and r.activo = 1 then r.ltv end) as ltv_now,
        sum(case when r.id_tiempo = p.latest then r.activo else 0 end)        as activos,
        sum(case when r.id_tiempo = p.latest then r.cancelacion else 0 end)   as cancel
    from {{ source('dw_negocio', 'fact_retencion') }} r
    cross join periodos p
),
c_disp as (
    select
        sum(case when d.id_tiempo = p.latest then d.costo_cloud else 0 end)       as cloud,
        avg(case when d.id_tiempo = p.latest then d.uptime end)                   as uptime,
        avg(case when d.id_tiempo = p.latest then d.time_to_market_dias end)      as ttm,
        avg(case when d.id_tiempo = p.latest then d.latencia_ms end)              as lat
    from {{ source('dw_negocio', 'fact_disponibilidad') }} d
    cross join periodos p
),
c_uso as (
    select
        sum(case when u.id_tiempo = p.latest and u.nps_score >= 9 then 1 else 0 end)               as nps_prom,
        sum(case when u.id_tiempo = p.latest and u.nps_score between 0 and 6 then 1 else 0 end)    as nps_det,
        sum(case when u.id_tiempo = p.latest and u.nps_score >= 0 then 1 else 0 end)               as nps_tot,
        sum(case when u.id_tiempo = p.latest then u.usuarios_activos else 0 end)                   as usuarios_activos,
        sum(case when u.id_tiempo = p.latest then u.usuarios_totales else 0 end)                   as usuarios_totales
    from {{ source('dw_negocio', 'fact_uso_plataforma') }} u
    cross join periodos p
),
c_cal as (
    -- Calidad del DW: % de reseñas con puntaje en rango (no filtra por período).
    select
        sum(case when points between 80 and 100 then 1 else 0 end) as cal_ok,
        count(*)                                                   as cal_tot
    from {{ source('dw_vitivinicola', 'fact_resenas') }}
),
c_apr as (
    -- Aprendizaje: fila única del período (max sobre la única fila que coincide).
    select
        max(case when ap.id_tiempo = p.latest then ap.horas_capacitacion end)     as horas,
        max(case when ap.id_tiempo = p.latest then ap.decisiones_data_driven end) as ddd,
        max(case when ap.id_tiempo = p.latest then ap.tecnologias_adoptadas end)  as tecno,
        max(case when ap.id_tiempo = p.latest then ap.rotacion_personal end)      as rota,
        max(case when ap.id_tiempo = p.latest then ap.modelos_ml_produccion end)  as mlmod
    from {{ source('dw_negocio', 'fact_aprendizaje') }} ap
    cross join periodos p
),
c_per as (
    select max(case when t.id_tiempo = p.latest then t.periodo end) as periodo
    from {{ source('dw_negocio', 'dim_tiempo') }} t
    cross join periodos p
),

-- ── Métricas crudas consolidadas (coalesce a 0 como hace _f()/val() en Python) ─
base as (
    select
        c_per.periodo,
        coalesce(c_susc.mrr_now, 0)          as mrr_now,
        coalesce(c_susc.mrr_prev, 0)         as mrr_prev,
        coalesce(c_nuevos.nuevos_trim, 0)    as nuevos_trim,
        coalesce(c_api.api_now, 0)           as api_now,
        coalesce(c_conv.cac_now, 0)          as cac_now,
        coalesce(c_conv.conv_num, 0)         as conv_num,
        coalesce(c_conv.conv_den, 0)         as conv_den,
        coalesce(c_ret.ltv_now, 0)           as ltv_now,
        coalesce(c_ret.activos, 0)           as activos,
        coalesce(c_ret.cancel, 0)            as cancel,
        coalesce(c_disp.cloud, 0)            as cloud,
        coalesce(c_disp.uptime, 0)           as uptime,
        coalesce(c_disp.ttm, 0)              as ttm,
        coalesce(c_disp.lat, 0)              as lat,
        coalesce(c_uso.nps_prom, 0)          as nps_prom,
        coalesce(c_uso.nps_det, 0)           as nps_det,
        coalesce(c_uso.nps_tot, 0)           as nps_tot,
        coalesce(c_uso.usuarios_activos, 0)  as usuarios_activos,
        coalesce(c_uso.usuarios_totales, 0)  as usuarios_totales,
        coalesce(c_cal.cal_ok, 0)            as cal_ok,
        coalesce(c_cal.cal_tot, 0)           as cal_tot,
        coalesce(c_apr.horas, 0)             as horas,
        coalesce(c_apr.ddd, 0)               as ddd,
        coalesce(c_apr.tecno, 0)             as tecno,
        coalesce(c_apr.rota, 0)              as rota,
        coalesce(c_apr.mlmod, 0)             as mlmod
    from c_per
    cross join c_susc
    cross join c_nuevos
    cross join c_api
    cross join c_conv
    cross join c_ret
    cross join c_disp
    cross join c_uso
    cross join c_cal
    cross join c_apr
)

select
    periodo,
    -- clientes_activos = SUM(activo) or 1 (idéntico a populate.py)
    cast(case when activos = 0 then 1 else activos end as int)                            as clientes_activos,
    round(mrr_now, 2)                                                                     as mrr_actual,
    round(case when mrr_prev = 0 then 0 else ((mrr_now / mrr_prev) - 1) * 100 end, 4)     as mrr_growth,
    round(case when (mrr_now + api_now) = 0 then 0
               else api_now / (mrr_now + api_now) * 100 end, 4)                           as api_share,
    round(cac_now, 2)                                                                     as cac,
    round(case when cac_now = 0 then 0 else ltv_now / cac_now end, 4)                     as ltv_cac,
    round(cloud / (case when activos = 0 then 1 else activos end), 4)                     as cloud_cli,
    round(case when conv_den = 0 then 0 else conv_num * 100.0 / conv_den end, 4)          as conversion,
    round(case when (cancel + activos) = 0 then 0
               else cancel * 100.0 / (activos + cancel) end, 4)                           as churn,
    round(case when nps_tot = 0 then 0
               else (nps_prom - nps_det) * 100.0 / nps_tot end, 4)                        as nps,
    round(case when usuarios_totales = 0 then 0
               else usuarios_activos * 100.0 / usuarios_totales end, 4)                   as adopcion,
    round(nuevos_trim, 2)                                                                 as nuevos_trim,
    round(uptime, 4)                                                                      as uptime,
    round(ttm, 4)                                                                         as ttm,
    round(lat, 4)                                                                         as latencia,
    round(case when cal_tot = 0 then 100.0 else cal_ok * 100.0 / cal_tot end, 4)          as calidad,
    round(horas, 4)                                                                       as horas,
    round(ddd, 4)                                                                         as ddd,
    round(mlmod, 4)                                                                       as mlmod,
    round(rota, 4)                                                                        as rotacion,
    round(tecno, 4)                                                                       as tecno
from base
where periodo is not null
