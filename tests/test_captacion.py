"""
Pruebas de CU-O09 «Ejecutar campaña de captación automatizada» y CU-O10 «Registrar
conversión del embudo» (paquete `captacion-conversion`, OP6).

Verifican las reglas SIN Docker ni DW: PocketBase falso en memoria (FakePB, el mismo
de test_suscripciones) con los catálogos de canales/mercados sembrados.

Cubren:
  CU-O09:
    - Regla del enunciado/RN-701: campaña con canal/mercado INEXISTENTE se rechaza;
      con existentes se crea en BORRADOR.
    - CA-601/Esc-601: campaña programada se ejecuta y puebla eventos_campana
      (impresiones/clics/gasto/leads) → Fact_Campana vía ETL.
    - Anti-doble-conteo: re-ejecutar el mismo período UPSERTA (una sola fila).
    - CA-602/Esc-602/RN-702: leads deduplicados (un prospecto = un lead).
  CU-O10:
    - CA-603/Esc-603/RN-703: conversión atribuida a la campaña/canal de origen.
    - Esc-604: una segunda campaña que reclama el mismo prospecto NO re-atribuye.
    - Regla del enunciado: la misma conversión de un lead en la misma etapa no se
      cuenta dos veces.
    - CA-605/RN-705/Esc-605: conversión a cliente → alta sin duplicar cuenta.
    - CA-604/RN-704: CAC y tasa de conversión con fórmulas canónicas.
    - CA-606/RN-706: caída de conversión emite señal al bus de alertas (OP9).

Ejecutar:
    python -m pytest tests/test_captacion.py -q
    python tests/test_captacion.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import models_captacion as cap
import models_alertas as ma
from db.pb_setup import CANALES_SEED, MERCADOS_SEED
from tests.test_suscripciones import FakePB


def _pb() -> FakePB:
    """FakePB con catálogos de canal/mercado sembrados (como el setup real)."""
    pb = FakePB()
    for c in CANALES_SEED:
        pb.create("canales_adquisicion", dict(c))
    for m in MERCADOS_SEED:
        pb.create("mercados", dict(m))
    return pb


def _campana(pb, **kw) -> dict:
    base = dict(nombre="Captación España Pago", canal="pago", mercado="España",
                segmento="Mid-Market", presupuesto=1000.0)
    base.update(kw)
    return cap.crear_campana(client=pb, **base)


# ── RN-701 / enunciado: canal y mercado deben EXISTIR ─────────────────────────
def test_campana_requiere_canal_y_mercado_existentes():
    pb = _pb()
    try:
        cap.crear_campana("X", "telepatia", "España", client=pb)
        assert False, "Debió rechazar el canal inexistente"
    except cap.CanalInexistente as e:
        assert e.codigo == "canal_inexistente"
    try:
        cap.crear_campana("X", "pago", "Narnia", client=pb)
        assert False, "Debió rechazar el mercado inexistente"
    except cap.MercadoInexistente as e:
        assert e.codigo == "mercado_inexistente"
    # con ambos válidos se crea en BORRADOR
    c = _campana(pb)
    assert c["estado"] == cap.C_BORRADOR
    assert c["canal"] == "pago" and c["mercado"] == "España"


# ── CA-601 / Esc-601: campaña programada se ejecuta y puebla Fact_Campana ──────
def test_campana_ejecutada_registra_metricas():
    pb = _pb()
    c = _campana(pb)
    c = cap.programar_campana(c["id"], "2026-06-01T08:00:00", client=pb)
    assert c["estado"] == cap.C_PROGRAMADA
    res = cap.ejecutar_campana(c["id"], periodo=202606, ahora="2026-06-15T09:00:00",
                               client=pb)
    assert res["campana"]["estado"] == cap.C_EN_EJECUCION
    ev = res["evento"]
    # presupuesto 1000 → métricas deterministas (CPM 10, CTR 2 %, lead 12 %)
    assert ev["impresiones"] == 100000 and ev["clics"] == 2000 and ev["leads"] == 240
    assert ev["gasto"] == 1000.0 and ev["id_tiempo"] == 202606
    assert len(pb.find("eventos_campana", campana=c["id"])) == 1


# ── Anti-doble-conteo de campaña: reejecutar el período no duplica ────────────
def test_ejecucion_repetida_no_duplica_metricas():
    pb = _pb()
    c = _campana(pb)
    cap.programar_campana(c["id"], "2026-06-01T08:00:00", client=pb)
    m = {"impresiones": 5000, "clics": 100, "gasto": 300.0, "leads": 20}
    r1 = cap.ejecutar_campana(c["id"], metricas=m, periodo=202606, client=pb)
    r2 = cap.ejecutar_campana(c["id"], metricas=m, periodo=202606, client=pb)
    # una sola fila (upsert), no dos
    filas = pb.find("eventos_campana", campana=c["id"])
    assert len(filas) == 1
    assert filas[0]["leads"] == 20 and filas[0]["gasto"] == 300.0
    assert r1["nuevo"] is True and r2["nuevo"] is False
    # la corrida (auditoría de reanudación) avanza, pero `ejecuciones` no se infla
    assert r2["corrida"] == 2
    assert pb.find_one("campanas", id=c["id"])["ejecuciones"] == 1


# ── CA-602 / Esc-602 / RN-702: leads deduplicados ─────────────────────────────
def test_lead_deduplicado():
    pb = _pb()
    c = _campana(pb)
    r1 = cap.registrar_lead("prospecto@bodega.es", c["id"], prospecto="Bodega Ibérica",
                            client=pb)
    assert r1["nuevo"] is True and r1["duplicado"] is False
    r2 = cap.registrar_lead("prospecto@bodega.es", c["id"], client=pb)
    assert r2["duplicado"] is True
    assert r2["lead"]["id"] == r1["lead"]["id"]
    assert len(pb.find("leads", clave="prospecto@bodega.es")) == 1


# ── CA-603 / Esc-603 / Esc-604 / RN-703: atribución first-touch ÚNICA ─────────
def test_conversion_atribuida_a_campana_de_origen():
    pb = _pb()
    cA = _campana(pb, nombre="A Pago", canal="pago")
    cB = _campana(pb, nombre="B Referido", canal="referido")
    # el lead lo capta A
    cap.registrar_lead("lead-001", cA["id"], client=pb)
    # B intenta reclamar el mismo prospecto → NO re-atribuye (Esc-604)
    rB = cap.registrar_lead("lead-001", cB["id"], client=pb)
    assert rB["atribucion"]["campana"] == cA["id"]
    # la conversión se atribuye a A / canal pago
    res = cap.registrar_conversion("lead-001", cap.E_OPORTUNIDAD, client=pb)
    assert res["contada"] is True
    assert res["atribucion"]["campana"] == cA["id"]
    assert res["atribucion"]["canal"] == "pago"


# ── Enunciado: la misma conversión de un lead en la misma etapa no se cuenta 2× ─
def test_conversion_no_se_cuenta_dos_veces():
    pb = _pb()
    c = _campana(pb)
    cap.registrar_lead("lead-xyz", c["id"], client=pb)
    r1 = cap.registrar_conversion("lead-xyz", cap.E_OPORTUNIDAD, client=pb)
    r2 = cap.registrar_conversion("lead-xyz", cap.E_OPORTUNIDAD, client=pb)
    assert r1["contada"] is True and r2["contada"] is False
    assert len(pb.find("eventos_conversion", lead=r1["conversion"]["lead"])) == 1


# ── CA-605 / RN-705 / Esc-605: conversión a cliente → alta sin duplicar ───────
def test_conversion_cliente_origina_alta_sin_duplicar():
    pb = _pb()
    c = _campana(pb)
    cap.registrar_lead("EC-555", c["id"], prospecto="Distribuidora Austral", client=pb)
    # 1ª conversión a CLIENTE crea la cuenta en `clientes` (hand-off OP5)
    res = cap.registrar_conversion("EC-555", cap.E_CLIENTE, resultado="ganado",
                                   client=pb)
    assert res["contada"] is True and res["alta"] is not None
    assert res["alta"]["id_fiscal"] == "EC-555"
    assert len(pb.find("clientes", id_fiscal="EC-555")) == 1
    # el evento de conversión quedó enlazado a la cuenta
    assert res["conversion"]["cliente"] == res["alta"]["id"]
    # re-registrar la misma conversión NO duplica la cuenta (anti-doble-conteo + RN-705)
    res2 = cap.registrar_conversion("EC-555", cap.E_CLIENTE, client=pb)
    assert res2["contada"] is False
    assert len(pb.find("clientes", id_fiscal="EC-555")) == 1


# ── CA-604 / RN-704: CAC y tasa de conversión con fórmulas canónicas ──────────
def test_indicadores_cac_y_tasa():
    pb = _pb()
    c = _campana(pb)
    cap.programar_campana(c["id"], "2026-06-01T08:00:00", client=pb)
    cap.ejecutar_campana(c["id"], metricas={"impresiones": 0, "clics": 0,
                                            "gasto": 1000.0, "leads": 0},
                         periodo=202606, ahora="2026-06-10T08:00:00", client=pb)
    cap.registrar_lead("l1", c["id"], ahora="2026-06-10T08:00:00", client=pb)
    cap.registrar_lead("l2", c["id"], ahora="2026-06-10T08:00:00", client=pb)
    cap.registrar_conversion("l1", cap.E_CLIENTE, ahora="2026-06-12T08:00:00",
                             client=pb)
    ind = cap.indicadores_captacion(202606, client=pb)
    assert ind["leads"] == 2 and ind["conversiones"] == 1
    assert ind["tasa_conversion"] == 50.0      # 1/2 × 100
    assert ind["cac"] == 1000.0                # gasto 1000 / 1 nuevo cliente


# ── CA-606 / Esc-606 / RN-706: caída de conversión emite señal al bus ─────────
def test_caida_conversion_emite_senal():
    pb = _pb()
    c = _campana(pb)
    # 3 leads, 0 conversiones a cliente → tasa 0 % < umbral
    for i in range(3):
        cap.registrar_lead(f"l{i}", c["id"], ahora="2026-06-10T08:00:00", client=pb)
    res = cap.evaluar_caida_conversion(202606, umbral=5.0, mercado="España", client=pb)
    assert res["alerta"] is True and res["tasa"] == 0.0
    # la señal está en el bus y `alertas` (OP9) la convierte en alerta enrutada
    senales = pb.find("senales_alerta", tipo="conversion")
    assert len(senales) == 1 and senales[0]["origen"] == "conversion"
    out = ma.procesar_pendientes(client=pb)
    alerta = out["alertas"][0]
    assert alerta["tipo"] == "conversion"
    assert alerta["responsable"] == "Growth & Marketing"   # RF-905


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for fn in fns:
        fn()
        print(f"  [OK] {fn.__name__}")
    print(f"\n{len(fns)} pruebas pasaron.")
