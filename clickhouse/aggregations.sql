-- ──────────────────────────────────────────────────────────────────────────────
-- ClickHouse · Capa de agregaciones / serving del dashboard (OP3, Fase 2).
-- Alimentada SOLO desde StarRocks por clickhouse/populate.py (RT-02: ClickHouse
-- nunca se alimenta de PocketBase). El dashboard/API leen de estas tablas
-- (serving.py) con fallback a StarRocks.
--
-- Cubre TODAS las agregaciones del dashboard actual:
--   Vino:  KPIs, países, variedades, puntuación, bodegas, regiones.
--   BSC:   MRR, % API, CAC, LTV/CAC, costo cloud, conversión, churn, NPS,
--          adopción, uptime, time-to-market, latencia, calidad, aprendizaje,
--          rankings (plan, mercado, partner) y embudo.
-- populate.py recrea el contenido de forma idempotente (TRUNCATE + INSERT).
-- ──────────────────────────────────────────────────────────────────────────────

CREATE DATABASE IF NOT EXISTS vinanalytics;

-- ── Vino: KPIs globales (una fila) ────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS vinanalytics.agg_kpis_vino (
    total_resenas        UInt64,
    puntuacion_promedio  Float64,
    precio_promedio      Float64,
    precio_maximo        Float64,
    precio_minimo        Float64,
    total_paises         UInt32,
    total_variedades     UInt32,
    total_bodegas        UInt32,
    updated              DateTime DEFAULT now()
) ENGINE = MergeTree ORDER BY tuple();

-- ── Vino: por país (sirve gráfica países, lista de países, browse, v1/mercados,
--    comparar-mercados) ─────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS vinanalytics.agg_pais (
    pais                 String,
    total                UInt64,
    puntuacion_promedio  Float64,
    precio_promedio      Float64,
    variedades           UInt32
) ENGINE = MergeTree ORDER BY pais;

-- ── Vino: por variedad ────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS vinanalytics.agg_variedad (
    variedad             String,
    total                UInt64,   -- todas las reseñas (sirve lista/browse)
    precio_promedio      Float64,  -- promedio sobre price > 0
    total_con_precio     UInt64    -- reseñas con price > 0 (sirve la gráfica de precios)
) ENGINE = MergeTree ORDER BY variedad;

-- ── Vino: por bodega ──────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS vinanalytics.agg_bodega (
    bodega               String,
    total                UInt64,
    puntuacion_promedio  Float64
) ENGINE = MergeTree ORDER BY bodega;

-- ── Vino: por región ──────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS vinanalytics.agg_region (
    region               String,
    total                UInt64
) ENGINE = MergeTree ORDER BY region;

-- ── Vino: histograma de puntuación ────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS vinanalytics.agg_puntuacion_hist (
    puntuacion           Int32,
    total                UInt64
) ENGINE = MergeTree ORDER BY puntuacion;

-- ── BSC: KPIs del período más reciente (una fila) ─────────────────────────────
CREATE TABLE IF NOT EXISTS vinanalytics.agg_bsc_kpis (
    periodo              String,
    clientes_activos     UInt32,
    mrr_actual           Float64,
    mrr_growth           Float64,
    api_share            Float64,
    cac                  Float64,
    ltv_cac              Float64,
    cloud_cli            Float64,
    conversion           Float64,
    churn                Float64,
    nps                  Float64,
    adopcion             Float64,
    nuevos_trim          Float64,
    uptime               Float64,
    ttm                  Float64,
    latencia             Float64,
    calidad              Float64,
    horas                Float64,
    ddd                  Float64,
    mlmod                Float64,
    rotacion             Float64,
    tecno                Float64,
    updated              DateTime DEFAULT now()
) ENGINE = MergeTree ORDER BY tuple();

-- ── BSC: series temporales y rankings (formato largo) ─────────────────────────
--   perspectiva ∈ {financiera, cliente, procesos, ecosistema}
--   serie       ∈ {mrr, api, cac, por_plan, nuevos_mercado, conversion, churn,
--                  nps, embudo, uptime, ttm, latencia_region, incidentes,
--                  ingresos_partner, llamadas, conexiones_partner}
--   etiqueta    = periodo 'AAAA-MM' o nombre (plan/país/región/partner/etapa)
--   orden       = índice cronológico o ranking
CREATE TABLE IF NOT EXISTS vinanalytics.agg_bsc_series (
    perspectiva          String,
    serie                String,
    etiqueta             String,
    orden                Int32,
    valor                Float64
) ENGINE = MergeTree ORDER BY (perspectiva, serie, orden);

-- ── Uso/adopción por cliente (CU-O15 · OP10): una fila por Dim_Cliente ────────
--   Sesiones, dashboards, funciones, frecuencia, adopción y NPS agregados desde
--   Fact_Uso_Plataforma. populate.py la transporta desde la vista DBT
--   serving.agg_uso_cliente. CU-O15 (serving.uso_por_cliente) lee de aquí (RN-1102:
--   uso consultado AGREGADO, nunca eventos crudos saltando capas).
CREATE TABLE IF NOT EXISTS vinanalytics.agg_uso_cliente (
    id_cliente           Int32,
    nombre               String,
    id_plan              Int32,
    periodos             Int32,
    sesiones             UInt64,
    dashboards_vistos    UInt64,
    funciones_total      UInt64,
    funciones_promedio   Float64,
    usuarios_activos     Int32,
    usuarios_totales     Int32,
    frecuencia_sesiones  Float64,
    adopcion_pct         Float64,
    nps_promedio         Float64,
    ultimo_periodo       Int32
) ENGINE = MergeTree ORDER BY id_cliente;

-- ── Reporte operativo diario (CU-O16 · OP11): consolidación por Dim_Tiempo ────
--   Una fila por período con métricas de API (Fact_Consumo_API), uso
--   (Fact_Uso_Plataforma) e incidentes/disponibilidad (Fact_Disponibilidad).
--   La poblar.py la transporta desde la vista DBT serving.agg_reporte_diario.
--   reportes/reporte_diario.py (CU-O16) lee SOLO de aquí (RN-1202).
CREATE TABLE IF NOT EXISTS vinanalytics.agg_reporte_diario (
    id_tiempo            Int32,
    periodo              String,
    api_llamadas         UInt64,
    api_errores          UInt32,
    api_latencia_ms      Float64,
    api_ingreso          Float64,
    uso_sesiones         UInt64,
    uso_funciones        UInt64,
    uso_usuarios_activos UInt32,
    uso_dashboards       UInt64,
    incidentes           UInt32,
    uptime               Float64,
    despliegues          UInt32
) ENGINE = MergeTree ORDER BY id_tiempo;
