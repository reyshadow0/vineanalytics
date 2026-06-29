"""
Pruebas de las reglas de negocio de CU-O08 (paquete `suscripciones`).

Usa un PocketBase falso en memoria (FakePB) que implementa la misma interfaz que
pb_client.PBClient, de modo que las reglas se verifican SIN Docker ni servidor.

Ejecutar:
    python -m pytest tests/test_suscripciones.py -q
    # o, sin pytest:
    python tests/test_suscripciones.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import models_clientes as mc
from db.pb_setup import PLANES_SEED, ESTADOS_SEED


class FakePB:
    """PocketBase en memoria con la interfaz usada por models_clientes."""

    def __init__(self):
        self._data: dict[str, list[dict]] = {}
        self._seq = 0

    # bootstrap de catálogos
    def seed(self):
        self._data.setdefault("planes", []).extend([dict(p) for p in PLANES_SEED])
        self._data.setdefault("estados_suscripcion", []).extend(
            [dict(e) for e in ESTADOS_SEED])
        return self

    def health(self):
        return True

    def ensure_collection(self, *a, **k):
        return False

    def _match(self, rec, filters):
        return all(str(rec.get(k)) == str(v) for k, v in filters.items())

    def find(self, collection, per_page=200, **filters):
        rows = self._data.get(collection, [])
        # Copias, como haría una respuesta REST real (sin referencias compartidas).
        return [dict(r) for r in rows if self._match(r, filters)]

    def find_one(self, collection, **filters):
        items = self.find(collection, **filters)
        return items[0] if items else None

    def create(self, collection, data):
        self._seq += 1
        rec = dict(data)
        rec["id"] = f"{collection[:3]}{self._seq:06d}"
        self._data.setdefault(collection, []).append(rec)
        return rec

    def update(self, collection, record_id, data):
        for r in self._data.get(collection, []):
            if r["id"] == record_id:
                r.update(data)
                return dict(r)
        raise KeyError(record_id)


def _fixture():
    pb = FakePB().seed()
    cliente = mc.crear_cliente(
        {"razon_social": "Bodega Andina S.A.", "id_fiscal": "EC-0991", "tipo": "bodega",
         "tamano": "mediana", "segmento": "premium", "mercado": "Chile"}, client=pb)
    fact = {"titular": "Bodega Andina S.A.", "metodo_pago_token": "tok_visa_4242"}
    return pb, cliente, fact


# ── REGLA 1: una suscripción debe asociarse a un plan EXISTENTE ───────────────
def test_regla1_plan_inexistente_se_rechaza():
    pb, cliente, fact = _fixture()
    try:
        mc.crear_suscripcion(cliente["id"], "plan_fantasma",
                             facturacion=fact, client=pb)
        assert False, "Debió rechazar el plan inexistente"
    except mc.PlanInexistente as e:
        assert e.codigo == "plan_inexistente"
    # con plan válido sí se crea y queda ACTIVA (facturación válida)
    s = mc.crear_suscripcion(cliente["id"], "profesional", facturacion=fact, client=pb)
    assert s["estado"] == mc.ACTIVA and s["plan"] == "profesional"


# ── REGLA 2: una cuenta no puede tener 2 suscripciones ACTIVAS del mismo plan ──
def test_regla2_doble_activa_mismo_plan_se_rechaza():
    pb, cliente, fact = _fixture()
    mc.crear_suscripcion(cliente["id"], "basico", facturacion=fact, client=pb)
    try:
        mc.crear_suscripcion(cliente["id"], "basico", facturacion=fact, client=pb)
        assert False, "Debió rechazar la segunda suscripción activa al mismo plan"
    except mc.SuscripcionActivaDuplicada as e:
        assert e.codigo == "suscripcion_activa_duplicada"
    # otro plan distinto sí se permite
    s2 = mc.crear_suscripcion(cliente["id"], "enterprise", facturacion=fact, client=pb)
    assert s2["estado"] == mc.ACTIVA


# ── Extras de soporte a las reglas ────────────────────────────────────────────
def test_dedup_de_cuentas():  # RN-601
    pb, cliente, _ = _fixture()
    try:
        mc.crear_cliente({"razon_social": "Otra", "id_fiscal": "EC-0991"}, client=pb)
        assert False, "Debió rechazar la cuenta duplicada"
    except mc.ClienteDuplicado as e:
        assert e.detalle["id_existente"] == cliente["id"]


def test_facturacion_incompleta_no_activa():  # RN-602
    pb, cliente, _ = _fixture()
    s = mc.crear_suscripcion(cliente["id"], "basico", facturacion=None, client=pb)
    assert s["estado"] == mc.PRUEBA and s["facturacion_ok"] is False


def test_transicion_invalida_se_rechaza():  # RN-604
    pb, cliente, fact = _fixture()
    s = mc.crear_suscripcion(cliente["id"], "basico", facturacion=fact, client=pb)
    mc.cambiar_estado(s["id"], mc.CANCELADA, client=pb)
    try:
        mc.cambiar_estado(s["id"], mc.EN_PAUSA, client=pb)
        assert False, "CANCELADA→EN_PAUSA debe rechazarse"
    except mc.TransicionInvalida as e:
        assert e.codigo == "transicion_invalida"


def test_alta_emite_evento_y_acceso_vigente():  # RN-605 / RF-507
    pb, cliente, fact = _fixture()
    mc.crear_suscripcion(cliente["id"], "profesional", facturacion=fact, client=pb)
    eventos = pb.find("eventos_suscripcion", cliente=cliente["id"])
    assert any(e["tipo_evento"] == "alta" and e["mrr_delta"] > 0 for e in eventos)
    acceso = mc.acceso_vigente(cliente["id"], client=pb)
    assert acceso["autorizado"] is True and acceso["plan"] == "profesional"


def test_upgrade_emite_evento():  # Esc-506
    pb, cliente, fact = _fixture()
    s = mc.crear_suscripcion(cliente["id"], "basico", facturacion=fact, client=pb)
    mc.cambiar_plan(s["id"], "enterprise", client=pb)
    eventos = pb.find("eventos_suscripcion", cliente=cliente["id"])
    assert any(e["tipo_evento"] == "upgrade" and e["mrr_delta"] > 0 for e in eventos)


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for fn in fns:
        fn()
        print(f"  [OK] {fn.__name__}")
    print(f"\n{len(fns)} pruebas pasaron.")
