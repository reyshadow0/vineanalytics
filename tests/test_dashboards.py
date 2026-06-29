"""
Pruebas de CU-O05 (construir dashboard) y CU-O06 (publicar con gate de calidad)
del paquete `dashboards`.

Usa el PocketBase falso en memoria (FakePB) de test_suscripciones, de modo que
las reglas se verifican SIN Docker ni servidor. Cubre los escenarios del spec:
  - Esc-301 construcción leyendo de ClickHouse → BORRADOR.
  - Esc-302 publicación nominal con calidad vigente → PUBLICADO + registro.
  - Esc-303 sin calidad vigente → BLOQUEADO_SIN_CALIDAD (regla dura RN-401).
  - Esc-304 plan vencido → publicación rechazada (RN-402).
  - Esc-305 fuga multi-tenant → bloqueada (RN-403).
  - Fallback de lectura ClickHouse → StarRocks (RT-01/RT-02).

Ejecutar:
    python -m pytest tests/test_dashboards.py -q
    # o, sin pytest:
    python tests/test_dashboards.py
"""

from __future__ import annotations

import sys
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import models_clientes as mc
import models_dashboards as md
from tests.test_suscripciones import FakePB


# ── Helpers de fixture ────────────────────────────────────────────────────────
def _cuenta_activa(pb, id_fiscal="EC-7001", plan="profesional"):
    """Crea una cuenta con suscripción ACTIVA (plan vigente) y la devuelve."""
    cli = mc.crear_cliente(
        {"razon_social": "Bodega Demo S.A.", "id_fiscal": id_fiscal, "tipo": "bodega",
         "mercado": "Chile"}, client=pb)
    fact = {"titular": "Bodega Demo S.A.", "metodo_pago_token": "tok_visa_4242"}
    mc.crear_suscripcion(cli["id"], plan, facturacion=fact, client=pb)
    return cli


def _lectura_ch(tema, filtros):
    """Simula la lectura desde ClickHouse (fuente=clickhouse)."""
    valores = {
        "resenas": {"total_resenas": 1280, "puntuacion_promedio": 90.4},
        "ingresos": {"mrr_actual": 24500.0, "churn": 3.2, "clientes_activos": 58},
        "precios": {"precio_promedio": 34.5, "precio_maximo": 900.0, "precio_minimo": 5.0},
        "uso": {"adopcion": 72.0, "nps": 54.0},
    }[tema]
    return {"fuente": "clickhouse", "valores": valores}


def _sello_ok(pb, hace_horas=0.0):
    fecha = (datetime.now() - timedelta(hours=hace_horas)).isoformat()
    return md.registrar_sello("dw", exito=True, evaluadas=12, fallidas=0,
                              fecha=fecha, client=pb)


# ── CU-O05 · construcción (Esc-301) ───────────────────────────────────────────
def test_construir_deja_borrador_leyendo_clickhouse():
    pb = FakePB().seed()
    cli = _cuenta_activa(pb)
    dash = md.construir_dashboard(cli["id"], "resenas", lectura_fn=_lectura_ch, client=pb)
    assert dash["estado"] == md.BORRADOR
    assert dash["fuente_lectura"] == "clickhouse"
    # Las definiciones y los valores quedan en la definición del dashboard.
    claves = {m["clave"]: m for m in dash["definicion"]["metricas"]}
    assert claves["total_resenas"]["valor"] == 1280
    assert claves["puntuacion_promedio"]["definicion"]  # tiene definición de negocio
    assert dash["definicion"]["filtros"]["cliente"] == cli["id"]  # aislamiento por cuenta


def test_tema_invalido_se_rechaza():
    pb = FakePB().seed()
    cli = _cuenta_activa(pb)
    try:
        md.construir_dashboard(cli["id"], "marciano", lectura_fn=_lectura_ch, client=pb)
        assert False, "Debió rechazar el tema inexistente"
    except md.TemaInvalido as e:
        assert e.codigo == "tema_invalido"


# ── CU-O06 · publicación nominal (Esc-302) ────────────────────────────────────
def test_publicar_con_calidad_ok_deja_publicado_y_registro():
    pb = FakePB().seed()
    cli = _cuenta_activa(pb)
    _sello_ok(pb)
    dash = md.construir_dashboard(cli["id"], "ingresos", lectura_fn=_lectura_ch, client=pb)
    md.marcar_listo(dash["id"], client=pb)

    pub = md.publicar(dash["id"], cuenta_id=cli["id"], permisos=["lectura"], client=pb)
    assert pub["estado"] == md.PUB_ACTIVA
    assert pub["calidad_ok"] is True and pub["sello"]
    assert pub["plan"] == "profesional" and pub["version"] == 1

    actualizado = pb.find_one("dashboards", id=dash["id"])
    assert actualizado["estado"] == md.PUBLICADO
    # RF-307: queda registrada y es auditable.
    hist = md.publicaciones_de(dash["id"], client=pb)
    assert len(hist) == 1 and hist[0]["cuenta"] == cli["id"]


# ── CU-O06 · gate de calidad (Esc-303 · RN-401, regla dura) ───────────────────
def test_publicar_sin_sello_bloquea_por_calidad():
    pb = FakePB().seed()
    cli = _cuenta_activa(pb)
    dash = md.construir_dashboard(cli["id"], "ingresos", lectura_fn=_lectura_ch, client=pb)
    md.marcar_listo(dash["id"], client=pb)
    try:
        md.publicar(dash["id"], cuenta_id=cli["id"], client=pb)
        assert False, "Debió bloquear la publicación sin sello de calidad"
    except md.CalidadNoVigente as e:
        assert e.codigo == "calidad_no_vigente"
        assert e.detalle["estado"] == md.BLOQUEADO_SIN_CALIDAD
    # El dashboard quedó BLOQUEADO_SIN_CALIDAD y NO hay publicación.
    assert pb.find_one("dashboards", id=dash["id"])["estado"] == md.BLOQUEADO_SIN_CALIDAD
    assert md.publicaciones_de(dash["id"], client=pb) == []


def test_publicar_con_ultima_calidad_fallida_bloquea():
    pb = FakePB().seed()
    cli = _cuenta_activa(pb)
    md.registrar_sello("dw", exito=False, evaluadas=12, fallidas=3, client=pb)  # falló
    dash = md.construir_dashboard(cli["id"], "uso", lectura_fn=_lectura_ch, client=pb)
    md.marcar_listo(dash["id"], client=pb)
    try:
        md.publicar(dash["id"], cuenta_id=cli["id"], client=pb)
        assert False, "Con la última validación fallida, no se debe publicar"
    except md.CalidadNoVigente as e:
        assert "FALLÓ" in e.mensaje


def test_sello_vencido_no_es_vigente():
    pb = FakePB().seed()
    _sello_ok(pb, hace_horas=48)  # fuera de la ventana de 24 h
    cal = md.calidad_vigente(client=pb)
    assert cal["ok"] is False and "venció" in cal["motivo"]


# ── CU-O06 · plan vencido (Esc-304 · RN-402) ──────────────────────────────────
def test_publicar_con_plan_vencido_se_rechaza():
    pb = FakePB().seed()
    cli = _cuenta_activa(pb)
    _sello_ok(pb)
    # Cancela la suscripción → la cuenta deja de tener plan vigente.
    susc = pb.find_one("suscripciones", cliente=cli["id"])
    mc.cambiar_estado(susc["id"], mc.CANCELADA, client=pb)

    dash = md.construir_dashboard(cli["id"], "ingresos", lectura_fn=_lectura_ch, client=pb)
    md.marcar_listo(dash["id"], client=pb)
    try:
        md.publicar(dash["id"], cuenta_id=cli["id"], client=pb)
        assert False, "Debió rechazar por plan no vigente"
    except md.PlanNoVigente as e:
        assert e.codigo == "plan_no_vigente"


# ── CU-O06 · aislamiento multi-tenant (Esc-305 · RN-403) ──────────────────────
def test_publicar_a_otra_cuenta_es_fuga():
    pb = FakePB().seed()
    propietaria = _cuenta_activa(pb, id_fiscal="EC-A")
    otra = _cuenta_activa(pb, id_fiscal="EC-B")
    _sello_ok(pb)
    dash = md.construir_dashboard(propietaria["id"], "ingresos",
                                  lectura_fn=_lectura_ch, client=pb)
    md.marcar_listo(dash["id"], client=pb)
    try:
        md.publicar(dash["id"], cuenta_id=otra["id"], client=pb)
        assert False, "Publicar a una cuenta distinta debe bloquearse"
    except md.FugaMultiTenant as e:
        assert e.codigo == "fuga_multitenant"


def test_filtro_a_otra_cuenta_es_fuga():
    pb = FakePB().seed()
    cli = _cuenta_activa(pb)
    try:
        md.construir_dashboard(cli["id"], "resenas",
                               filtros={"cliente": "cuenta_ajena"},
                               lectura_fn=_lectura_ch, client=pb)
        assert False, "Un filtro Dim_Cliente a otra cuenta debe bloquearse"
    except md.FugaMultiTenant as e:
        assert e.codigo == "fuga_multitenant"


# ── RF-308 · reemplazo/despublicación con historial ───────────────────────────
def test_republicar_versiona_y_conserva_historial():
    pb = FakePB().seed()
    cli = _cuenta_activa(pb)
    _sello_ok(pb)
    dash = md.construir_dashboard(cli["id"], "uso", lectura_fn=_lectura_ch, client=pb)
    md.marcar_listo(dash["id"], client=pb)
    md.publicar(dash["id"], cuenta_id=cli["id"], client=pb)          # v1
    pub2 = md.publicar(dash["id"], cuenta_id=cli["id"], client=pb)   # v2 (reemplazo)
    assert pub2["version"] == 2
    hist = md.publicaciones_de(dash["id"], client=pb)
    estados = sorted(p["estado"] for p in hist)
    assert estados == [md.PUB_ACTIVA, md.PUB_REEMPLAZADA]
    # Despublicar deja el dashboard DESPUBLICADO si no quedan activas.
    md.despublicar(pub2["id"], client=pb)
    assert pb.find_one("dashboards", id=dash["id"])["estado"] == md.DESPUBLICADO


# ── Fallback de lectura ClickHouse → StarRocks (RT-01/RT-02) ───────────────────
def test_fallback_clickhouse_a_starrocks():
    import serving
    orig = serving._get_client
    serving._client = None
    serving._get_client = lambda: None      # simula ClickHouse no disponible
    try:
        # Sin ClickHouse, serving devuelve None → señal de fallback.
        assert serving.metricas_dashboard("resenas", {}) is None

        def lector_con_fallback(tema, filtros):
            ch = serving.metricas_dashboard(tema, filtros)
            if ch is not None:
                return ch
            return {"fuente": "starrocks",
                    "valores": {"total_resenas": 7, "puntuacion_promedio": 88.0}}

        pb = FakePB().seed()
        cli = _cuenta_activa(pb)
        dash = md.construir_dashboard(cli["id"], "resenas",
                                      lectura_fn=lector_con_fallback, client=pb)
    finally:
        serving._get_client = orig
    assert dash["estado"] == md.BORRADOR
    assert dash["definicion"]["fuente_lectura"] == "starrocks"  # cayó al DW
    claves = {m["clave"]: m["valor"] for m in dash["definicion"]["metricas"]}
    assert claves["total_resenas"] == 7


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for fn in fns:
        fn()
        print(f"  [OK] {fn.__name__}")
    print(f"\n{len(fns)} pruebas pasaron.")
