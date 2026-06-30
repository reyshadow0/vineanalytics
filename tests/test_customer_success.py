"""
Pruebas de CU-O14 (onboarding/tickets) y CU-O15 (consulta de uso por cliente),
paquete `customer-success` (OP10).

Verifican las reglas SIN Docker ni DW: PocketBase falso en memoria (FakePB, el
mismo de test_suscripciones) y la lectura de uso se inyecta sustituyendo serving._q.

Cubren:
  CU-O14:
    - regla del enunciado: ticket/onboarding sobre cuenta INEXISTENTE se rechaza;
      sobre cuenta EXISTENTE (las de la Sesión 1) se registra.
    - CA-1101/Esc-1101: onboarding registrado con pasos/estado; idempotente (RN-1104).
    - CA-1102/Esc-1102: ticket clasificado, con tiempos (RF-1003) y NPS (RF-1004).
    - Esc-1105/RN-1101: transición inválida CERRADO→EN_PROCESO rechazada.
    - CA-1104/RN-1103: alerta de churn prioriza y vincula acción de retención.
    - CA-1105/RF-1007: reporte de soporte por cuenta.
  CU-O15:
    - CA-1103/Esc-1103: la consulta de uso lee la AGREGACIÓN agg_uso_cliente.
    - Esc-1106/RN-1102: NO lee los eventos crudos (fact_uso_plataforma) — sin salto de capa.

Ejecutar:
    python -m pytest tests/test_customer_success.py -q
    python tests/test_customer_success.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import models_customer_success as cs
import models_alertas as ma
import serving
from tests.test_suscripciones import FakePB


def _cuenta(pb: FakePB) -> dict:
    """Crea una cuenta existente (como las de la Sesión 1) en `clientes`."""
    return pb.create("clientes", {"razon_social": "Bodega Andina S.A.",
                                  "id_fiscal": "EC-0991", "mercado": "Chile"})


# ── Regla del enunciado: asociar a una cuenta EXISTENTE ───────────────────────
def test_onboarding_cuenta_inexistente_se_rechaza():
    pb = FakePB()
    try:
        cs.iniciar_onboarding("cli_fantasma", client=pb)
        assert False, "Debió rechazar onboarding de cuenta inexistente"
    except cs.CuentaInexistente as e:
        assert e.codigo == "cuenta_inexistente"


def test_ticket_cuenta_inexistente_vs_existente():
    pb = FakePB()
    try:
        cs.abrir_ticket("cli_fantasma", "No puedo entrar", client=pb)
        assert False, "Debió rechazar ticket de cuenta inexistente"
    except cs.CuentaInexistente as e:
        assert e.codigo == "cuenta_inexistente"
    # con cuenta existente sí se abre
    cuenta = _cuenta(pb)
    tk = cs.abrir_ticket(cuenta["id"], "No puedo entrar", client=pb)
    assert tk["estado"] == cs.T_ABIERTO and tk["cuenta"] == cuenta["id"]


# ── CA-1101 / Esc-1101 / RN-1104: onboarding registrado + idempotente ─────────
def test_onboarding_registrado_y_idempotente():
    pb = FakePB()
    cuenta = _cuenta(pb)
    onb = cs.iniciar_onboarding(cuenta["id"], client=pb)
    assert onb["estado"] == cs.ONB_PENDIENTE
    assert onb["pasos_totales"] == len(cs.PASOS_ONBOARDING_DEFAULT)
    assert onb["paso"] == cs.PASOS_ONBOARDING_DEFAULT[0]
    # RN-1104: re-disparar al alta NO duplica
    onb2 = cs.iniciar_onboarding(cuenta["id"], client=pb)
    assert onb2["id"] == onb["id"]
    assert len(pb.find("onboarding", cuenta=cuenta["id"])) == 1
    # avanzar hasta completar
    estado = None
    for _ in range(onb["pasos_totales"]):
        estado = cs.avanzar_onboarding(onb["id"], client=pb)
    assert estado["estado"] == cs.ONB_COMPLETADO
    assert estado["pasos_completados"] == onb["pasos_totales"]


# ── CA-1102 / Esc-1102: ticket con ciclo de vida, tiempos (RF-1003) y NPS ─────
def test_ticket_ciclo_de_vida_tiempos_y_nps():
    pb = FakePB()
    cuenta = _cuenta(pb)
    tk = cs.abrir_ticket(cuenta["id"], "Error 500 al exportar",
                         categoria="incidencia", prioridad="alta",
                         ahora="2026-06-29T09:00:00", client=pb)
    # primera respuesta a los 30 min
    tk = cs.transicionar_ticket(tk["id"], cs.T_EN_PROCESO,
                                ahora="2026-06-29T09:30:00", client=pb)
    assert tk["tiempo_primera_respuesta_min"] == 30.0
    # resuelto a las 2 h del alta
    tk = cs.transicionar_ticket(tk["id"], cs.T_RESUELTO,
                                ahora="2026-06-29T11:00:00", client=pb)
    assert tk["estado"] == cs.T_RESUELTO
    assert tk["tiempo_resolucion_min"] == 120.0
    # cierre + NPS (RF-1004)
    tk = cs.transicionar_ticket(tk["id"], cs.T_CERRADO,
                                ahora="2026-06-29T11:05:00", client=pb)
    assert tk["estado"] == cs.T_CERRADO and tk["cerrado_en"]
    tk = cs.registrar_satisfaccion(tk["id"], 9, client=pb)
    assert tk["nps"] == 9 and tk["satisfaccion"] == "promotor"


# ── Esc-1105 / RN-1101: transición inválida CERRADO→EN_PROCESO rechazada ──────
def test_transicion_invalida_cerrado_a_en_proceso():
    pb = FakePB()
    cuenta = _cuenta(pb)
    tk = cs.abrir_ticket(cuenta["id"], "Consulta de facturación", client=pb)
    cs.transicionar_ticket(tk["id"], cs.T_RESUELTO, client=pb)
    cs.transicionar_ticket(tk["id"], cs.T_CERRADO, client=pb)
    try:
        cs.transicionar_ticket(tk["id"], cs.T_EN_PROCESO, client=pb)
        assert False, "CERRADO→EN_PROCESO debe rechazarse (sin reabrir)"
    except cs.TransicionTicketInvalida as e:
        assert e.codigo == "transicion_invalida"
    # reabrir sí es válido
    tk = cs.transicionar_ticket(tk["id"], cs.T_REABIERTO, client=pb)
    assert tk["estado"] == cs.T_REABIERTO


# ── RF-1004: NPS fuera de 0..10 se rechaza ────────────────────────────────────
def test_nps_invalido_se_rechaza():
    pb = FakePB()
    cuenta = _cuenta(pb)
    tk = cs.abrir_ticket(cuenta["id"], "Duda", client=pb)
    try:
        cs.registrar_satisfaccion(tk["id"], 12, client=pb)
        assert False, "NPS 12 debe rechazarse"
    except cs.NpsInvalido as e:
        assert e.codigo == "nps_invalido"


# ── CA-1104 / RN-1103: alerta de churn prioriza y vincula acción de retención ─
def test_alerta_churn_vincula_retencion():
    pb = FakePB()
    cuenta = _cuenta(pb)
    # sin churn → prioridad normal, no crea acción
    base = cs.vincular_retencion(cuenta["razon_social"], client=pb)
    assert base["vinculada"] is False and base["prioridad"] == "normal"
    # OP9 genera una alerta de churn VIVA sobre la cuenta (entidad = nombre)
    alerta, creada = ma.generar_alerta(
        tipo="churn", clave=f"churn:{cuenta['razon_social']}:202606",
        causa="Churn alto", entidad=cuenta["razon_social"], severidad="critical",
        client=pb)
    assert creada
    # ahora sí prioriza y vincula UNA acción
    res = cs.vincular_retencion(cuenta["razon_social"], client=pb)
    assert res["vinculada"] and res["prioridad"] == "alta"
    assert res["accion"]["estado"] == "PENDIENTE"
    # idempotente: no apila otra acción para la misma alerta
    res2 = cs.vincular_retencion(cuenta["razon_social"], client=pb)
    assert res2["accion"]["id"] == res["accion"]["id"]
    assert len(pb.find("acciones_retencion", cuenta=cuenta["razon_social"])) == 1
    # la lectura sin efectos también reporta el riesgo (RF-1006)
    ev = cs.evaluar_retencion(cuenta["razon_social"], client=pb)
    assert ev["en_riesgo"] and ev["prioridad"] == "alta"


# ── CA-1105 / RF-1007: reporte de soporte por cuenta ──────────────────────────
def test_reporte_soporte_por_cuenta():
    pb = FakePB()
    cuenta = _cuenta(pb)
    cs.iniciar_onboarding(cuenta["id"], client=pb)
    tk = cs.abrir_ticket(cuenta["id"], "Incidencia", ahora="2026-06-29T08:00:00",
                         client=pb)
    cs.transicionar_ticket(tk["id"], cs.T_RESUELTO, ahora="2026-06-29T09:00:00",
                           client=pb)
    cs.registrar_satisfaccion(tk["id"], 8, client=pb)
    rep = cs.reporte_soporte(cuenta["id"], client=pb)
    assert rep["onboarding"]["estado"] == cs.ONB_PENDIENTE
    assert rep["tickets"]["total"] == 1
    assert rep["tickets"]["tiempo_resolucion_prom_min"] == 60.0
    assert rep["tickets"]["nps_promedio"] == 8.0


# ── CA-1103 / Esc-1103 / Esc-1106 / RN-1102: uso desde la AGREGACIÓN, sin salto ─
def test_uso_por_cliente_lee_agregacion_no_eventos_crudos():
    consultas: list[str] = []
    fila = (7, "Bodega Andina S.A.", 2, 6, 480, 1200, 12, 9.5, 8, 11,
            80.0, 72.7, 8.4, 202606)

    def fake_q(sql):
        consultas.append(sql)
        return [fila] if "agg_uso_cliente" in sql and "id_cliente = 7" in sql else []

    original = serving._q
    serving._q = fake_q
    try:
        uso = serving.uso_por_cliente(7)
    finally:
        serving._q = original

    assert uso is not None
    assert uso["id_cliente"] == 7 and uso["sesiones"] == 480
    assert uso["frecuencia_sesiones"] == 80.0 and uso["adopcion_pct"] == 72.7
    # RN-1102 / Esc-1106: la consulta usa la agregación, NUNCA los eventos crudos.
    assert any("agg_uso_cliente" in q for q in consultas)
    assert all("fact_uso_plataforma" not in q for q in consultas)


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for fn in fns:
        fn()
        print(f"  [OK] {fn.__name__}")
    print(f"\n{len(fns)} pruebas pasaron.")
