"""
Genera 3 diagramas Excalidraw para VinAnalytics Group:
  1. Diagrama de Casos de Uso (UML)
  2. Diagrama de Componentes
  3. Diagrama de Despliegue
"""

import json, random
from pathlib import Path

_ctr = 0
def uid():
    global _ctr; _ctr += 1
    return f"va{_ctr:05d}"

def rnd(): return random.randint(100000, 999999)
TS = 1716000000000

C = {
    'bordo':   '#9b1f42', 'bordo_bg':  '#fdf2f5',
    'dorado':  '#c9933a', 'dorado_bg': '#fefce8',
    'verde':   '#22a35f', 'verde_bg':  '#f0fdf4',
    'azul':    '#1d4ed8', 'azul_bg':   '#eff6ff',
    'morado':  '#7c3aed', 'morado_bg': '#f5f3ff',
    'gris':    '#4b5563', 'gris_bg':   '#f9fafb',
    'negro':   '#111827', 'blanco':    '#ffffff',
    'naranja_bg': '#fff7ed',
}

class D:
    def __init__(self):
        self.els = []

    def _base(self, tp, x, y, w, h):
        return {
            "id": uid(), "type": tp,
            "x": float(x), "y": float(y),
            "width": float(w), "height": float(h),
            "angle": 0,
            "strokeColor": C['negro'], "backgroundColor": "transparent",
            "fillStyle": "solid", "strokeWidth": 2, "strokeStyle": "solid",
            "roughness": 0, "opacity": 100,
            "groupIds": [], "frameId": None, "roundness": None,
            "seed": rnd(), "version": 1, "versionNonce": rnd(),
            "isDeleted": False, "boundElements": [],
            "updated": TS, "link": None, "locked": False,
        }

    def _text_el(self, rid, x, y, w, h, text, fs, color, family, align='center', valign='middle'):
        lines = text.count('\n') + 1
        th = fs * 1.35 * lines
        ty = y + h/2 - th/2 if valign == 'middle' else y + 8
        return {
            "id": uid(), "type": "text",
            "x": float(x + 6), "y": float(ty),
            "width": float(w - 12), "height": float(th),
            "angle": 0,
            "strokeColor": color, "backgroundColor": "transparent",
            "fillStyle": "solid", "strokeWidth": 1, "strokeStyle": "solid",
            "roughness": 0, "opacity": 100,
            "groupIds": [], "frameId": None, "roundness": None,
            "seed": rnd(), "version": 1, "versionNonce": rnd(),
            "isDeleted": False, "boundElements": None,
            "updated": TS, "link": None, "locked": False,
            "text": text, "fontSize": fs, "fontFamily": family,
            "textAlign": align, "verticalAlign": valign,
            "containerId": rid, "originalText": text, "lineHeight": 1.35,
        }

    def rect(self, x, y, w, h, label='', bg='transparent', stroke=C['negro'],
             sw=2, fs=14, color=C['negro'], rounded=True, dashed=False,
             family=2, align='center', valign='middle', fill='solid'):
        el = self._base("rectangle", x, y, w, h)
        el["strokeColor"] = stroke
        el["backgroundColor"] = bg
        el["fillStyle"] = fill
        el["strokeWidth"] = sw
        el["strokeStyle"] = "dashed" if dashed else "solid"
        el["roughness"] = 0
        if rounded: el["roundness"] = {"type": 3}
        rid = el["id"]
        self.els.append(el)
        if label:
            te = self._text_el(rid, x, y, w, h, label, fs, color, family, align, valign)
            el["boundElements"] = [{"id": te["id"], "type": "text"}]
            self.els.append(te)
        return rid

    def ellipse(self, x, y, w, h, label='', bg=C['azul_bg'], stroke=C['azul'],
                fs=12, color=C['negro'], family=2):
        el = self._base("ellipse", x, y, w, h)
        el["strokeColor"] = stroke
        el["backgroundColor"] = bg
        el["fillStyle"] = "solid"
        el["roughness"] = 0
        eid = el["id"]
        self.els.append(el)
        if label:
            lines = label.count('\n') + 1
            th = fs * 1.35 * lines
            te = {**self._text_el(eid, x, y, w, h, label, fs, color, family),
                  "x": float(x + w*0.12), "width": float(w*0.76)}
            el["boundElements"] = [{"id": te["id"], "type": "text"}]
            self.els.append(te)
        return eid

    def txt(self, x, y, text, fs=14, color=C['negro'], align='center',
            family=2, bold=False, w=None):
        lines = text.count('\n') + 1
        tw = w or max(len(l) for l in text.split('\n')) * fs * 0.65
        th = fs * 1.35 * lines
        ox = x - tw/2 if align == 'center' else x
        el = {
            "id": uid(), "type": "text",
            "x": float(ox), "y": float(y),
            "width": float(tw), "height": float(th),
            "angle": 0,
            "strokeColor": color, "backgroundColor": "transparent",
            "fillStyle": "solid", "strokeWidth": 1, "strokeStyle": "solid",
            "roughness": 0, "opacity": 100,
            "groupIds": [], "frameId": None, "roundness": None,
            "seed": rnd(), "version": 1, "versionNonce": rnd(),
            "isDeleted": False, "boundElements": [],
            "updated": TS, "link": None, "locked": False,
            "text": text, "fontSize": fs, "fontFamily": family,
            "textAlign": align, "verticalAlign": "top",
            "containerId": None, "originalText": text, "lineHeight": 1.35,
        }
        self.els.append(el)
        return el["id"]

    def arrow(self, x1, y1, x2, y2, color=C['negro'], sw=2,
              label='', dashed=False, ah='arrow', sah=None,
              sid=None, eid_=None):
        el = self._base("arrow", x1, y1, x2-x1 or 1, y2-y1 or 1)
        el["x"] = float(x1); el["y"] = float(y1)
        el["strokeColor"] = color
        el["strokeWidth"] = sw
        el["strokeStyle"] = "dashed" if dashed else "solid"
        el["roughness"] = 0
        el["points"] = [[0.0, 0.0], [float(x2-x1), float(y2-y1)]]
        el["lastCommittedPoint"] = None
        el["startBinding"] = {"elementId": sid, "focus": 0.0, "gap": 6} if sid else None
        el["endBinding"]   = {"elementId": eid_, "focus": 0.0, "gap": 6} if eid_ else None
        el["startArrowhead"] = sah
        el["endArrowhead"]   = ah
        self.els.append(el)
        if label:
            self.txt((x1+x2)/2, (y1+y2)/2 - 18, label, fs=11, color=color)
        return el["id"]

    def line(self, x1, y1, x2, y2, color=C['gris'], sw=1, dashed=False):
        el = self._base("line", x1, y1, x2-x1 or 1, y2-y1 or 1)
        el["x"] = float(x1); el["y"] = float(y1)
        el["strokeColor"] = color; el["strokeWidth"] = sw
        el["strokeStyle"] = "dashed" if dashed else "solid"
        el["roughness"] = 0
        el["points"] = [[0.0, 0.0], [float(x2-x1), float(y2-y1)]]
        el["lastCommittedPoint"] = None
        el["startBinding"] = el["endBinding"] = None
        el["startArrowhead"] = el["endArrowhead"] = None
        self.els.append(el)

    def save(self, fname):
        doc = {
            "type": "excalidraw", "version": 2,
            "source": "https://excalidraw.com",
            "elements": self.els,
            "appState": {
                "gridSize": 20,
                "viewBackgroundColor": "#ffffff",
                "currentItemFontFamily": 2,
            },
            "files": {}
        }
        Path(fname).write_text(json.dumps(doc, ensure_ascii=False, indent=2), encoding='utf-8')
        print(f"  [OK] {fname}")


# ══════════════════════════════════════════════════════════════════════════════
# DIAGRAMA 1 — CASOS DE USO
# ══════════════════════════════════════════════════════════════════════════════
def diag_casos_de_uso():
    d = D()

    # Título principal
    d.rect(0, 0, 1380, 60, label='DIAGRAMA DE CASOS DE USO — VinAnalytics Group',
           bg=C['bordo'], stroke=C['bordo'], fs=20, color=C['blanco'],
           rounded=True, sw=0)

    # ── Sistema (boundary) ───────────────────────────────────────────────────
    sys_x, sys_y, sys_w, sys_h = 270, 90, 880, 810
    d.rect(sys_x, sys_y, sys_w, sys_h,
           bg='transparent', stroke=C['bordo'], sw=3, dashed=True, rounded=False)
    d.txt(sys_x + sys_w/2, sys_y + 12, '<<Sistema>>\nVinAnalytics Group',
          fs=15, color=C['bordo'], family=2)

    # ── Use Cases (ellipses) ─────────────────────────────────────────────────
    ew, eh = 210, 56
    col1_x = sys_x + 40
    col2_x = sys_x + 310
    col3_x = sys_x + 600

    ucs = [
        # col, row, label, bg, stroke
        (col1_x, 200, 'Iniciar Sesión',            C['azul_bg'],   C['azul']),
        (col1_x, 310, 'Ver Dashboard\ny KPIs',     C['verde_bg'],  C['verde']),
        (col1_x, 420, 'Analizar\nGráficas',        C['verde_bg'],  C['verde']),
        (col1_x, 530, 'Filtrar Reseñas\nde Vino',  C['verde_bg'],  C['verde']),
        (col1_x, 640, 'Exportar /\nRespaldo',      C['dorado_bg'], C['dorado']),

        (col2_x, 200, 'Ejecutar\nPipeline ETL',    C['bordo_bg'],  C['bordo']),
        (col2_x, 310, 'Cargar CSV\na PocketBase',  C['bordo_bg'],  C['bordo']),
        (col2_x, 420, 'Generar Datos\nAleatorios', C['bordo_bg'],  C['bordo']),
        (col2_x, 530, 'Gestionar\nUsuarios',       C['morado_bg'], C['morado']),
        (col2_x, 640, 'Ver Auditoría\ndel Sistema',C['morado_bg'], C['morado']),

        (col3_x, 310, 'Extraer →\nParquet',        C['naranja_bg'],C['dorado']),
        (col3_x, 420, 'Transformar\nDimensiones',  C['naranja_bg'],C['dorado']),
        (col3_x, 530, 'Cargar →\nStarRocks',       C['naranja_bg'],C['dorado']),
        (col3_x, 640, 'Reset\nStarRocks',          C['naranja_bg'],C['dorado']),
    ]

    uc_ids = {}
    for (cx, cy, label, bg, stroke) in ucs:
        eid = d.ellipse(cx, cy, ew, eh, label=label, bg=bg, stroke=stroke,
                        fs=12, color=C['negro'])
        uc_ids[label.replace('\n',' ')] = (eid, cx + ew/2, cy + eh/2)

    # include/extend arrows between related UCs
    # Ejecutar ETL incluye los 3 sub-pasos
    etl_cx = col2_x + ew/2
    etl_cy = 310 + eh/2
    for sub_label, sub_cx, sub_cy in [
        ('Extraer →\nParquet', col3_x + ew/2, 310 + eh/2),
        ('Transformar\nDimensiones', col3_x + ew/2, 420 + eh/2),
        ('Cargar →\nStarRocks', col3_x + ew/2, 530 + eh/2),
        ('Reset\nStarRocks', col3_x + ew/2, 640 + eh/2),
    ]:
        k = sub_label.replace('\n',' ')
        d.arrow(etl_cx + ew/2, etl_cy,
                col3_x, uc_ids[k][2],
                color=C['dorado'], sw=1, dashed=True,
                label='<<include>>' if 'Reset' not in sub_label else '<<extend>>',
                ah='arrow')

    # ── Actores ──────────────────────────────────────────────────────────────
    actors = [
        (60, 220,  'Administrador', C['bordo']),
        (60, 440,  'Analista',      C['azul']),
        (60, 660,  'Gerente',       C['verde']),
    ]
    actor_ids = {}
    for ax, ay, name, color in actors:
        # Icono de actor (cabeza + cuerpo)
        head = d.ellipse(ax + 15, ay, 30, 30, bg=color, stroke=color)
        d.line(ax+30, ay+30, ax+30, ay+70, color=color, sw=2)
        d.line(ax+10, ay+42, ax+50, ay+42, color=color, sw=2)
        d.line(ax+30, ay+70, ax+10, ay+90, color=color, sw=2)
        d.line(ax+30, ay+70, ax+50, ay+90, color=color, sw=2)
        d.txt(ax+30, ay+96, name, fs=12, color=color, align='center')
        actor_ids[name] = (ax+30, ay+45)

    # Líneas actor → use cases
    def connect(actor_name, uc_labels, stroke_color):
        ax, ay = actor_ids[actor_name]
        for lbl in uc_labels:
            k = lbl.replace('\n',' ')
            if k in uc_ids:
                uid_target, ux, uy = uc_ids[k]
                d.line(ax+30, ay, ux - ew/2, uy, color=stroke_color, sw=1)

    connect('Administrador', [
        'Iniciar Sesión', 'Ver Dashboard\ny KPIs', 'Analizar\nGráficas',
        'Filtrar Reseñas\nde Vino', 'Ejecutar\nPipeline ETL',
        'Cargar CSV\na PocketBase', 'Generar Datos\nAleatorios',
        'Gestionar\nUsuarios', 'Ver Auditoría\ndel Sistema', 'Exportar /\nRespaldo',
    ], C['bordo'])
    connect('Analista', [
        'Iniciar Sesión', 'Ver Dashboard\ny KPIs', 'Analizar\nGráficas',
        'Filtrar Reseñas\nde Vino', 'Generar Datos\nAleatorios',
    ], C['azul'])
    connect('Gerente', [
        'Iniciar Sesión', 'Ver Dashboard\ny KPIs', 'Analizar\nGráficas',
    ], C['verde'])

    # Leyenda
    leg_x, leg_y = 1170, 100
    d.rect(leg_x, leg_y, 190, 260, bg=C['gris_bg'], stroke=C['gris'], sw=1,
           rounded=True)
    d.txt(leg_x+95, leg_y+10, 'Leyenda', fs=13, color=C['negro'])
    items = [
        (C['azul'],   C['azul_bg'],   'Sesión / Login'),
        (C['verde'],  C['verde_bg'],  'Consulta / Análisis'),
        (C['bordo'],  C['bordo_bg'],  'ETL / Datos'),
        (C['morado'], C['morado_bg'], 'Administración'),
        (C['dorado'], C['dorado_bg'], 'Operaciones ETL'),
    ]
    for i, (stroke, bg, label) in enumerate(items):
        iy = leg_y + 45 + i*40
        d.ellipse(leg_x+12, iy, 30, 22, bg=bg, stroke=stroke)
        d.txt(leg_x+55, iy+4, label, fs=11, color=C['negro'], align='left')

    d.save("01_DiagramaCasosDeUso.excalidraw")


# ══════════════════════════════════════════════════════════════════════════════
# DIAGRAMA 2 — COMPONENTES
# ══════════════════════════════════════════════════════════════════════════════
def diag_componentes():
    d = D()

    d.rect(0, 0, 1380, 60, label='DIAGRAMA DE COMPONENTES — VinAnalytics Group',
           bg=C['bordo'], stroke=C['bordo'], fs=20, color=C['blanco'],
           rounded=True, sw=0)

    # ── CAPA 0: Cliente ──────────────────────────────────────────────────────
    d.rect(510, 80, 360, 70,
           label='🌐  Cliente / Navegador Web\nHTTP :5000', bg=C['gris_bg'],
           stroke=C['gris'], fs=13, color=C['gris'], rounded=True)
    browser_cx = 690

    # ── CAPA 1: Frontend ─────────────────────────────────────────────────────
    fe_y = 220
    d.rect(300, fe_y, 780, 110,
           bg='#f8f4f6', stroke=C['bordo'], sw=2, rounded=True)
    d.txt(690, fe_y+10, '📄  CAPA DE PRESENTACIÓN — Frontend', fs=13, color=C['bordo'])
    comps_fe = [
        (320, fe_y+38, 140, 55, 'HTML5 / CSS3\nGlassmorphism',  C['bordo_bg'],  C['bordo']),
        (480, fe_y+38, 140, 55, 'Chart.js 4.4\nVisualizaciones',C['verde_bg'],  C['verde']),
        (640, fe_y+38, 140, 55, 'JavaScript\nFetch API / SPA',  C['azul_bg'],   C['azul']),
        (800, fe_y+38, 160, 55, 'Jinja2\nTemplates',            C['dorado_bg'], C['dorado']),
    ]
    for cx, cy, cw, ch, label, bg, stroke in comps_fe:
        d.rect(cx, cy, cw, ch, label=label, bg=bg, stroke=stroke, fs=11,
               color=C['negro'], rounded=True, sw=1)

    # ── CAPA 2: Backend Flask ────────────────────────────────────────────────
    bk_y = 400
    d.rect(60, bk_y, 560, 130,
           bg='#f2f0fd', stroke=C['morado'], sw=2, rounded=True)
    d.txt(340, bk_y+10, '⚙  CAPA DE LÓGICA — Flask Backend', fs=13, color=C['morado'])
    comps_bk = [
        (80,  bk_y+38, 120, 55, 'app.py\nRoutes / API', C['morado_bg'], C['morado']),
        (220, bk_y+38, 120, 55, 'auth.py\nLogin/Roles', C['morado_bg'], C['morado']),
        (350, bk_y+38, 120, 55, 'models.py\nUsuarios',  C['morado_bg'], C['morado']),
        (480, bk_y+38, 120, 55, 'audit.py\nAuditoría',  C['morado_bg'], C['morado']),
    ]
    for cx, cy, cw, ch, label, bg, stroke in comps_bk:
        d.rect(cx, cy, cw, ch, label=label, bg=bg, stroke=stroke, fs=11,
               color=C['negro'], rounded=True, sw=1)

    # backup_manager
    d.rect(80, bk_y+38+65, 520, 45,
           label='backup_manager.py  —  Respaldos JSON automáticos + Health Check',
           bg=C['morado_bg'], stroke=C['morado'], fs=11, color=C['negro'], rounded=True, sw=1)

    # ── CAPA 3: ETL ──────────────────────────────────────────────────────────
    etl_y = 400
    d.rect(660, etl_y, 540, 210,
           bg=C['naranja_bg'], stroke=C['dorado'], sw=2, rounded=True)
    d.txt(930, etl_y+10, '🔄  MÓDULO ETL', fs=13, color=C['dorado'])
    comps_etl = [
        (680,  etl_y+38, 150, 50, 'pb_loader.py\nCSV → PocketBase',   C['dorado_bg'], C['dorado']),
        (850,  etl_y+38, 150, 50, 'extractor.py\nPocketBase → Parquet',C['dorado_bg'], C['dorado']),
        (1020, etl_y+38, 160, 50, 'transformer.py\nModelo Estrella',   C['dorado_bg'], C['dorado']),
        (680,  etl_y+105,150, 50, 'loader.py\nParquet → StarRocks',    C['dorado_bg'], C['dorado']),
        (850,  etl_y+105,150, 50, 'data_generator.py\nDatos Aleatorios',C['dorado_bg'],C['dorado']),
        (1020, etl_y+105,160, 50, 'pandas / PyArrow\nTransformaciones', C['verde_bg'],  C['verde']),
    ]
    for cx, cy, cw, ch, label, bg, stroke in comps_etl:
        d.rect(cx, cy, cw, ch, label=label, bg=bg, stroke=stroke, fs=10,
               color=C['negro'], rounded=True, sw=1)

    # Stage (parquet files)
    d.rect(680, etl_y+165, 500, 35,
           label='📁 stage/  —  wine_raw.parquet · wine_clean.parquet · dim_*.parquet · fact_resenas.parquet',
           bg=C['gris_bg'], stroke=C['gris'], fs=10, color=C['gris'], rounded=True, sw=1)

    # ── CAPA 4: StarRocks ────────────────────────────────────────────────────
    sr_y = 680
    d.rect(60, sr_y, 680, 160,
           bg=C['verde_bg'], stroke=C['verde'], sw=2, rounded=True)
    d.txt(400, sr_y+10, '🗄  STARRROCKS — Almacén de Datos OLAP (retailytics)', fs=13, color=C['verde'])
    comps_sr = [
        (80,  sr_y+40, 180, 50, 'fact_resenas\n308,724 filas',  C['verde_bg'], C['verde']),
        (280, sr_y+40, 110, 50, 'dim_pais\n44 países',          C['blanco'],   C['verde']),
        (400, sr_y+40, 110, 50, 'dim_variedad\n708 cepas',      C['blanco'],   C['verde']),
        (520, sr_y+40, 110, 50, 'dim_bodega\n16,756',           C['blanco'],   C['verde']),
        (280, sr_y+105,110, 45, 'dim_provincia\n426',           C['blanco'],   C['verde']),
        (400, sr_y+105,110, 45, 'dim_region\n1,230',            C['blanco'],   C['verde']),
        (520, sr_y+105,110, 45, 'dim_catador\n20',              C['blanco'],   C['verde']),
        (640, sr_y+40, 80,  50, 'usuarios\n_sistema',           C['morado_bg'],C['morado']),
        (640, sr_y+105,80,  45, 'auditoria\nlogs',              C['morado_bg'],C['morado']),
    ]
    for cx, cy, cw, ch, label, bg, stroke in comps_sr:
        d.rect(cx, cy, cw, ch, label=label, bg=bg, stroke=stroke, fs=10,
               color=C['negro'], rounded=True, sw=1)

    # ── CAPA 4: PocketBase ───────────────────────────────────────────────────
    pb_y = 680
    d.rect(780, pb_y, 320, 100,
           bg=C['azul_bg'], stroke=C['azul'], sw=2, rounded=True)
    d.txt(940, pb_y+10, '☁  POCKETBASE :8090', fs=13, color=C['azul'])
    d.rect(800, pb_y+38, 280, 50,
           label='Colección: wine_reviews\nStaging de registros',
           bg=C['blanco'], stroke=C['azul'], fs=11, color=C['negro'], rounded=True, sw=1)

    # CSV File
    d.rect(1130, pb_y, 210, 80,
           label='📄 winemag-data\n-130k-v2.csv\n129,971 filas',
           bg=C['gris_bg'], stroke=C['gris'], fs=11, color=C['gris'], rounded=True, sw=1)

    # ── Flechas de conexión ──────────────────────────────────────────────────
    # Browser → Frontend
    d.arrow(690, 150, 690, 218, color=C['gris'], label='HTTP GET /\nRender Templates')
    # Frontend → Flask
    d.arrow(690, 330, 450, 398, color=C['bordo'], label='fetch() REST API')
    # Flask → StarRocks
    d.arrow(350, 560, 350, 678, color=C['verde'], label='MySQL :9030\nSELECT / INSERT')
    # ETL → PocketBase
    d.arrow(930, 610, 940, 678, color=C['azul'], label='HTTP :8090')
    # ETL → StarRocks
    d.arrow(850, 610, 400, 678, color=C['verde'], label='LOAD OLAP', dashed=True)
    # CSV → PocketBase
    d.arrow(1235, pb_y, 1100, pb_y+50, color=C['gris'], label='pb_loader.py')
    # Flask → ETL
    d.arrow(620, 470, 660, 470, color=C['dorado'], label='import etl.*')

    d.save("02_DiagramaComponentes.excalidraw")


# ══════════════════════════════════════════════════════════════════════════════
# DIAGRAMA 3 — DESPLIEGUE
# ══════════════════════════════════════════════════════════════════════════════
def diag_despliegue():
    d = D()

    d.rect(0, 0, 1380, 60, label='DIAGRAMA DE DESPLIEGUE — VinAnalytics Group',
           bg=C['bordo'], stroke=C['bordo'], fs=20, color=C['blanco'],
           rounded=True, sw=0)

    # ── Host: Máquina con Docker ─────────────────────────────────────────────
    d.rect(40, 80, 1100, 780,
           bg='#f8f8ff', stroke=C['gris'], sw=3, dashed=True, rounded=True)
    d.txt(590, 95, '🖥  Servidor / Host  —  Windows 11 · Docker Engine',
          fs=15, color=C['gris'])

    # ── Red Docker interna ───────────────────────────────────────────────────
    d.rect(80, 125, 1020, 700,
           bg='#f2f8ff', stroke=C['azul'], sw=2, dashed=True, rounded=True)
    d.txt(590, 138, 'Docker Network: vinanalytics_default  (bridge)',
          fs=12, color=C['azul'])

    # ── Contenedor PocketBase ────────────────────────────────────────────────
    pb_x, pb_y = 100, 180
    d.rect(pb_x, pb_y, 300, 260, bg=C['azul_bg'], stroke=C['azul'], sw=2, rounded=True)
    d.rect(pb_x+10, pb_y+10, 280, 30,
           label='☁  Container: pocketbase', bg=C['azul'], stroke=C['azul'],
           fs=12, color=C['blanco'], rounded=True, sw=0)
    specs_pb = [
        ('Imagen:', 'elestio/pocketbase:latest'),
        ('Host:',   'pocketbase'),
        ('Puerto:',  '8090 → 8090'),
        ('Volumen:', 'pocketbase_data:/pb/data'),
        ('Colección:','wine_reviews'),
        ('Registros:','≤ 129,971'),
    ]
    for i, (k, v) in enumerate(specs_pb):
        d.txt(pb_x+20, pb_y+50+i*30, k, fs=11, color=C['azul'], align='left', w=90)
        d.txt(pb_x+115, pb_y+50+i*30, v, fs=11, color=C['negro'], align='left', w=175)

    # ── Contenedor StarRocks ─────────────────────────────────────────────────
    sr_x, sr_y = 460, 180
    d.rect(sr_x, sr_y, 320, 300, bg=C['verde_bg'], stroke=C['verde'], sw=2, rounded=True)
    d.rect(sr_x+10, sr_y+10, 300, 30,
           label='🗄  Container: starrocks', bg=C['verde'], stroke=C['verde'],
           fs=12, color=C['blanco'], rounded=True, sw=0)
    specs_sr = [
        ('Imagen:',  'starrocks/allin1-ubuntu:latest'),
        ('Host:',    'starrocks'),
        ('FE HTTP:', '8030 → 8030'),
        ('BE HTTP:', '8040 → 8040'),
        ('MySQL:',   '9030 → 9030'),
        ('Base:',    'retailytics'),
        ('Tablas:',  '9 (fact + dims + sistema)'),
        ('Filas:',   '308,724+ en fact_resenas'),
    ]
    for i, (k, v) in enumerate(specs_sr):
        d.txt(sr_x+20, sr_y+50+i*30, k, fs=11, color=C['verde'], align='left', w=80)
        d.txt(sr_x+105, sr_y+50+i*30, v, fs=11, color=C['negro'], align='left', w=225)

    # ── Contenedor Flask ─────────────────────────────────────────────────────
    fk_x, fk_y = 840, 180
    d.rect(fk_x, fk_y, 290, 300, bg=C['bordo_bg'], stroke=C['bordo'], sw=2, rounded=True)
    d.rect(fk_x+10, fk_y+10, 270, 30,
           label='🍷  Container: flask', bg=C['bordo'], stroke=C['bordo'],
           fs=12, color=C['blanco'], rounded=True, sw=0)
    specs_fk = [
        ('Build:',  './Dockerfile'),
        ('Base:',   'python:3.13-slim'),
        ('Host:',   'flask'),
        ('Puerto:', '5000 → 5000'),
        ('STARROCKS_HOST:', 'starrocks'),
        ('POCKETBASE_URL:', 'http://pocketbase:8090'),
        ('SECRET_KEY:',     '(env variable)'),
        ('Deps:',   'flask, pandas, pyarrow,'),
        ('',        'mysql-connector-python,'),
        ('',        'apscheduler, requests'),
    ]
    for i, (k, v) in enumerate(specs_fk):
        d.txt(fk_x+15, fk_y+50+i*26, k, fs=10, color=C['bordo'], align='left', w=105)
        d.txt(fk_x+125, fk_y+50+i*26, v, fs=10, color=C['negro'], align='left', w=155)

    # ── Volúmenes Docker ─────────────────────────────────────────────────────
    vol_y = 520
    d.rect(100, vol_y, 680, 70, bg=C['gris_bg'], stroke=C['gris'], sw=1,
           rounded=True, dashed=True)
    d.txt(440, vol_y+8, '💾  Volúmenes Docker Persistentes', fs=12, color=C['gris'])
    vols = [
        (120, vol_y+32, 195, 28, 'pocketbase_data', C['azul_bg'], C['azul']),
        (330, vol_y+32, 195, 28, 'starrocks_data',  C['verde_bg'], C['verde']),
        (540, vol_y+32, 220, 28, './stage/ (bind mount)',C['gris_bg'], C['gris']),
    ]
    for vx, vy, vw, vh, label, bg, stroke in vols:
        d.rect(vx, vy, vw, vh, label=label, bg=bg, stroke=stroke,
               fs=10, color=C['negro'], rounded=True, sw=1)

    # ── docker-compose.yml ───────────────────────────────────────────────────
    dc_y = 620
    d.rect(100, dc_y, 1020, 150, bg=C['gris_bg'], stroke=C['gris'],
           sw=1, rounded=True)
    d.txt(610, dc_y+8, '📋  docker-compose.yml — Orquestación de Servicios',
          fs=12, color=C['gris'])
    d.txt(120, dc_y+35,
          'services:\n  pocketbase: { image: elestio/pocketbase, ports: 8090:8090, volumes: pocketbase_data }\n'
          '  starrocks:  { image: starrocks/allin1-ubuntu, ports: 9030,8030,8040 }\n'
          '  flask:      { build: ., ports: 5000:5000, depends_on: [pocketbase, starrocks] }',
          fs=10, color=C['gris'], align='left', w=980)

    # ── Actores Externos ─────────────────────────────────────────────────────
    # Cliente Navegador
    br_x, br_y = 1200, 180
    d.rect(br_x, br_y, 160, 120, bg=C['blanco'], stroke=C['negro'], sw=2, rounded=True)
    d.txt(br_x+80, br_y+10, '👤 Usuario\nNavegador', fs=13, color=C['negro'])
    d.txt(br_x+80, br_y+65, 'Chrome / Edge\nlocalhost:5000', fs=11, color=C['gris'])

    # CSV File
    csv_x, csv_y = 1200, 340
    d.rect(csv_x, csv_y, 160, 100, bg=C['gris_bg'], stroke=C['gris'], sw=2, rounded=True)
    d.txt(csv_x+80, csv_y+10, '📄 CSV File', fs=13, color=C['gris'])
    d.txt(csv_x+80, csv_y+45, 'winemag-data\n-130k-v2.csv', fs=11, color=C['gris'])

    # ── Flechas de comunicación ───────────────────────────────────────────────
    # Usuario → Flask
    d.arrow(br_x, br_y+60, fk_x+290, fk_y+60,
            color=C['bordo'], sw=2, label='HTTP REST\n:5000', ah='arrow', sah='arrow')

    # Flask → StarRocks
    d.arrow(fk_x+145, fk_y+300, sr_x+160, sr_y+300,
            color=C['verde'], sw=2, label='MySQL Protocol\n:9030')

    # Flask → PocketBase (ETL)
    d.arrow(fk_x+145, fk_y+260, pb_x+150, pb_y+260,
            color=C['azul'], sw=2, label='HTTP API\n:8090', dashed=True)

    # CSV → Flask (ETL carga)
    d.arrow(csv_x, csv_y+50, fk_x+290, fk_y+160,
            color=C['gris'], sw=1, label='pb_loader.py\nlectura CSV', dashed=True)

    # PocketBase → Flask (extractor)
    d.arrow(pb_x+150, pb_y+150, fk_x+145, fk_y+200,
            color=C['azul'], sw=1, label='Extracción\npaginada', dashed=True, ah='arrow')

    d.save("03_DiagramaDespliegue.excalidraw")


# ══════════════════════════════════════════════════════════════════════════════
if __name__ == "__main__":
    print("Generando diagramas Excalidraw ...")
    diag_casos_de_uso()
    diag_componentes()
    diag_despliegue()
    print("\nAbre los archivos .excalidraw en https://excalidraw.com → File → Open")
