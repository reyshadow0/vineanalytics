"""
Genera 34 diagramas Excalidraw — VinAnalytics Group sistema 100%
"""
import sys, os
sys.path.insert(0, os.path.dirname(__file__))
from excali_base import *

# ════════════════════════════════════════════════════════════════════════════
#  CASOS DE USO
# ════════════════════════════════════════════════════════════════════════════

def uc01_general():
    els=[]
    els+=title("UC-01  Casos de Uso — Sistema Completo VinAnalytics",800,14,
               "Todos los actores y casos de uso del sistema al 100% (Fases 1-4)")
    # boundary
    els.append(rect(180,60,1260,980,stroke=WINE,sw=2,ss="dashed",rounded=True))
    els.append(txt("sistema  VinAnalytics Group",760,63,size=13,color=WINE,align="center"))
    # actors
    els+=stick(70,160,"Usuario\nPublico","#333")
    els+=stick(70,460,"Analista","#1a6a10")
    els+=stick(70,680,"Gerente","#5a4a10")
    els+=stick(1570,200,"Administrador",WINE_D)
    els+=stick(1570,700,"API Externa\n(Fase 4)",BLUE)
    # publico UCs
    for i,(lbl,y) in enumerate([("Explorar Landing / Home",140),("Buscar Vinos",210),
        ("Ver Catalogo /vinos",280),("Ver Ficha Vino /vinos/:id",350),
        ("Filtrar por Pais / Variedad / Bodega",420)]):
        uo,_=uc_oval(lbl,430,y,WINE_L,WINE)
        els+=uo; els.append(arr(130,200,430-80,y,stroke=WINE,sw=1))
    # analista UCs
    for i,(lbl,y) in enumerate([("Iniciar Sesion /login",500),("Ver Dashboard /dashboard",570),
        ("Ver KPIs y Metricas",640),("Ver Graficos Interactivos",710),
        ("Exportar Resultados PDF/CSV",780),("Gestionar Favoritos",850)]):
        uo,_=uc_oval(lbl,430,y,GREEN_L,GREEN)
        els+=uo; els.append(arr(130,500,430-80,y,stroke=GREEN,sw=1))
    # gerente UCs
    for i,(lbl,y) in enumerate([("Comparar Vinos lado a lado",920),
        ("Ver Tendencias por Pais/Ano",990)]):
        uo,_=uc_oval(lbl,430,y,GOLD_L,GOLD)
        els+=uo; els.append(arr(130,720,430-80,y,stroke=GOLD,sw=1))
    # admin UCs
    for i,(lbl,y) in enumerate([("Panel Admin /admin",140),("Gestionar ETL Manual",210),
        ("Programar ETL Automatico",280),("Cargar CSV Masivo",350),
        ("Gestionar Usuarios CRUD",420),("Asignar Roles y Permisos",490),
        ("Ver Auditoria Completa",560),("Ejecutar Respaldos",630),
        ("Programar Respaldos",700),("Gestionar API Keys",770)]):
        uo,_=uc_oval(lbl,1120,y,"#ffe8e8",WINE_D)
        els+=uo; els.append(arr(1510,240,1120+80,y,stroke=WINE_D,sw=1))
    # API UCs
    for i,(lbl,y) in enumerate([("Consumir API REST /api/v1/",840),
        ("Ver Documentacion Swagger",910),("Auth con API Key",980)]):
        uo,_=uc_oval(lbl,1120,y,BLUE_L,BLUE)
        els+=uo; els.append(arr(1510,740,1120+80,y,stroke=BLUE,sw=1))
    # generalizaciones
    els.append(arr(70,650,70,500,stroke=GRAY,sw=1,ss="dashed"))
    els.append(txt("incluye\nacceso publico",78,570,size=10,color=GRAY))
    els.append(arr(70,770,70,650,stroke=GRAY,sw=1,ss="dashed"))
    # leyenda
    els.append(rect(200,1060,1000,50,bg=GRAY_L,stroke=GRAY,sw=1,rounded=True))
    for i,(bg,st,lbl) in enumerate([(WINE_L,WINE,"Publico"),(GREEN_L,GREEN,"Analista/Gerente"),
        ("#ffe8e8",WINE_D,"Solo Admin"),(BLUE_L,BLUE,"Fase 4")]):
        ox=220+i*240
        els.append(ell(ox,1072,50,24,bg=bg,stroke=st,sw=1))
        els.append(txt(lbl,ox+56,1078,size=11,color=GRAY))
    save("UC_01_general.excalidraw",els,"#fafafa")

def uc02_publico():
    els=[]
    els+=title("UC-02  Rol: Usuario Publico",600,14,
               "Sin autenticacion — acceso libre a descubrimiento y exploracion de vinos")
    els.append(rect(180,60,820,760,stroke=WINE,sw=2,ss="dashed",rounded=True))
    els.append(txt("sistema  VinAnalytics Group — Zona Publica",550,63,size=12,color=WINE,align="center"))
    els+=stick(80,200,"Usuario\nPublico","#333")
    casos=[
        ("Explorar Landing / Home",400,130,"Ver seccion hero, busqueda y categorias"),
        ("Buscar Vinos por nombre",400,210,"Input en hero → redirige a /vinos?q=..."),
        ("Ver Catalogo completo /vinos",400,290,"Listado paginado de 308,724 resenas"),
        ("Filtrar por Pais",400,370,"Panel lateral → filtra en tiempo real via API"),
        ("Filtrar por Variedad",400,450,"708 variedades disponibles"),
        ("Filtrar por Bodega",400,530,"16,756 bodegas disponibles"),
        ("Filtrar por Region",400,610,"Regiones vitivinicolas del mundo"),
        ("Ver Ficha Detalle /vinos/:id",400,690,"Nombre, bodega, puntos, precio, descripcion"),
        ("Ir a Iniciar Sesion",400,770,"Boton en header → /login"),
    ]
    for lbl,x,y,nota in casos:
        uo,_=uc_oval(lbl,x,y,WINE_L,WINE,size=11)
        els+=uo
        els.append(arr(130,240,x-80,y,stroke=WINE,sw=1))
        els+=note_box(x+100,y-14,260,28,nota)
    save("UC_02_publico.excalidraw",els,"#fafafa")

def uc03_analista():
    els=[]
    els+=title("UC-03  Rol: Analista",700,14,
               "Acceso autenticado — dashboard, KPIs, graficos y exportaciones")
    els.append(rect(180,60,1000,820,stroke=GREEN,sw=2,ss="dashed",rounded=True))
    els+=stick(80,280,"Analista","#1a6a10")
    casos=[
        ("Iniciar Sesion /login",430,130,"POST credenciales → session[rol=analista]"),
        ("Ver Dashboard /dashboard",430,210,"Ruta protegida — muestra KPIs y graficos"),
        ("Ver KPI: Total Resenas",430,290,"308,724 resenas totales en StarRocks"),
        ("Ver KPI: Puntuacion Promedio",430,370,"AVG(points) en tiempo real"),
        ("Ver KPI: Precio Promedio",430,450,"AVG(price) filtrado por seleccion"),
        ("Ver Grafico Top Paises",430,530,"Bar chart por pais ordenado por n resenas"),
        ("Ver Grafico Puntos vs Precio",430,610,"Scatter plot precio/puntuacion"),
        ("Ver Top 10 Variedades",430,690,"Ranking de variedades mas reseniadas"),
        ("Aplicar Filtros Cruzados",430,770,"Combinar pais + variedad + rango puntos"),
        ("Exportar Tabla CSV",430,850,"Descarga directa del resultado filtrado"),
        ("Gestionar Favoritos",860,290,"Guardar vinos de interes (Fase 3)"),
        ("Ver Recomendaciones",860,370,"Basadas en historial (Fase 3)"),
        ("Cerrar Sesion /logout",860,450,"Elimina session Flask"),
    ]
    for lbl,x,y,nota in casos:
        uo,_=uc_oval(lbl,x,y,GREEN_L,GREEN,size=11)
        els+=uo
        els.append(arr(130,320,x-80,y,stroke=GREEN,sw=1))
        els+=note_box(x+100,y-14,300,28,nota)
    save("UC_03_analista.excalidraw",els,"#fafafa")

def uc04_gerente():
    els=[]
    els+=title("UC-04  Rol: Gerente",700,14,
               "Acceso analista + vistas comparativas y de tendencias para toma de decisiones")
    els.append(rect(180,60,1000,720,stroke=GOLD,sw=2,ss="dashed",rounded=True))
    els+=stick(80,260,"Gerente","#5a4a10")
    casos=[
        ("Iniciar Sesion /login",430,130,"Mismo flujo que analista"),
        ("Ver Dashboard /dashboard",430,210,"Vista identica a analista"),
        ("Ver Resumen Ejecutivo",430,290,"KPIs de alto nivel: total, avg pts, avg precio"),
        ("Comparar Vinos lado a lado",430,370,"Seleccionar 2-3 vinos → tabla comparativa"),
        ("Ver Tendencias por Pais",430,450,"Evolucion de puntuacion por pais"),
        ("Ver Tendencias por Ano",430,530,"Resenas agrupadas por ano"),
        ("Ver Top Bodegas Globales",430,610,"Ranking por puntuacion promedio"),
        ("Exportar Reporte PDF",430,690,"Resumen ejecutivo en PDF (Fase 3)"),
        ("Filtrar por Rango de Precio",860,290,"Segmento premium vs economico"),
        ("Ver Mapa de Regiones",860,370,"Distribucion geografica (Fase 3)"),
        ("Compartir Dashboard",860,450,"URL compartible con filtros (Fase 3)"),
        ("Cerrar Sesion",860,530,"GET /logout"),
    ]
    for lbl,x,y,nota in casos:
        uo,_=uc_oval(lbl,x,y,GOLD_L,GOLD,size=11)
        els+=uo
        els.append(arr(130,300,x-80,y,stroke=GOLD,sw=1))
        els+=note_box(x+100,y-14,280,28,nota)
    save("UC_04_gerente.excalidraw",els,"#fafafa")

def uc05_admin():
    els=[]
    els+=title("UC-05  Rol: Administrador",800,14,
               "Control total del sistema — ETL, usuarios, auditoria, respaldos y API")
    els.append(rect(180,60,1200,1060,stroke=WINE_D,sw=3,ss="solid",rounded=True))
    els+=stick(80,300,"Admin",WINE_D)
    grupos=[
        ("Gestion de Datos ETL",[
            ("Acceder Panel Admin /admin",440,130,"Ruta exclusiva admin"),
            ("Ejecutar ETL Manual",440,210,"Extrae CSV → Transforma → Carga StarRocks"),
            ("Programar ETL (cron)",440,290,"Tarea automatica diaria/semanal (Fase 4)"),
            ("Cargar CSV Masivo",440,370,"Upload winemag-data-130k-v2.csv"),
            ("Ver Estado del Pipeline",440,450,"Logs de ejecucion y estadisticas"),
        ],WINE_D),
        ("Gestion de Usuarios",[
            ("Crear Usuario",440,550,"POST /usuarios → INSERT usuarios_sistema"),
            ("Editar Rol de Usuario",440,630,"Cambiar analista/gerente/admin"),
            ("Activar / Desactivar Usuario",440,710,"activo=TRUE/FALSE"),
            ("Eliminar Usuario",440,790,"DELETE usuarios_sistema WHERE id=?"),
            ("Ver Listado de Usuarios",440,870,"SELECT * FROM usuarios_sistema"),
        ],WINE_D),
        ("Auditoria y Monitoreo",[
            ("Ver Log de Auditoria",860,130,"SELECT * FROM auditoria ORDER BY fecha DESC"),
            ("Filtrar por Usuario",860,210,"WHERE usuario=? AND fecha BETWEEN"),
            ("Filtrar por Accion",860,290,"LOGIN, LOGOUT, ETL, BACKUP, CREATE_USER"),
            ("Exportar Auditoria CSV",860,370,"Descarga del log completo"),
        ],PURPLE),
        ("Respaldos",[
            ("Ejecutar Respaldo Manual",860,470,"mysqldump → archivo .sql en /backups"),
            ("Programar Respaldo Auto",860,550,"Cron diario (Fase 4)"),
            ("Restaurar Respaldo",860,630,"Cargar .sql en StarRocks (Fase 4)"),
            ("Ver Historial Respaldos",860,710,"Lista archivos en /app/backups"),
        ],GREEN),
        ("API y Sistema",[
            ("Gestionar API Keys",860,810,"Generar/revocar tokens (Fase 4)"),
            ("Ver Documentacion Swagger",860,890,"GET /api/docs (Fase 4)"),
            ("Configurar Parametros",860,970,"Umbrales, limites, notificaciones"),
        ],BLUE),
    ]
    for grup,casos,color in grupos:
        for lbl,x,y,nota in casos:
            uo,_=uc_oval(lbl,x,y,"#fff0f0",WINE_D,size=11)
            els+=uo
            els.append(arr(130,340,x-80,y,stroke=WINE_D,sw=1))
            els+=note_box(x+100,y-14,300,28,nota)
    save("UC_05_admin.excalidraw",els,"#fafafa")

# ════════════════════════════════════════════════════════════════════════════
#  SECUENCIAS
# ════════════════════════════════════════════════════════════════════════════

def _actors(defs,y0,y1):
    """defs: list of (label,sub,x,bg,stroke). Returns lifeline elements."""
    els=[]
    for lbl,sub,x,bg,st in defs:
        els+=lifeline(x,y0,y1,lbl,sub,bg,st)
    return els

def seq01_login():
    els=[]
    els+=title("SEQ-01  Secuencia: Inicio de Sesion",600,14)
    y0,y1=60,900
    ac=[("Usuario","",80,BLUE_L,BLUE),("Navegador",":5000",240,"#f0f0f0","#444"),
        ("Flask","auth.py",420,WINE_L,WINE),("StarRocks",":9030",620,BLUE_L,BLUE),
        ("PocketBase",":8090",820,GREEN_L,GREEN)]
    els+=_actors(ac,y0,y1)
    steps=[(ac[0][2],ac[1][2],140,"GET /login","#333"),
           (ac[1][2],ac[2][2],170,"HTTP GET /login",WINE),
           (ac[2][2],ac[1][2],210,"login.html","#333",True),
           (ac[0][2],ac[1][2],260,"POST username + password","#333"),
           (ac[1][2],ac[2][2],290,"POST /auth/login",WINE),
           (ac[2][2],ac[3][2],330,"SELECT * FROM usuarios_sistema WHERE username=?",BLUE),
           (ac[3][2],ac[2][2],370,"{id, username, hash, rol}","#333",True),
           (ac[2][2],ac[2][2]-1,400,"verify bcrypt hash","#333"),]
    for x1,x2,y,lbl,stroke,*r in steps:
        els+=msg(x1,x2,y,lbl,stroke=stroke,ret=bool(r))
    els+=seq_frame(50,410,850,180,"alt credenciales validas",GREEN)
    els+=msg(ac[2][2],ac[4][2],440,"session[user_id, username, rol]",stroke=GREEN)
    els+=msg(ac[2][2],ac[3][2],470,"INSERT INTO auditoria (LOGIN OK)",stroke=WINE)
    els+=msg(ac[2][2],ac[1][2],510,"Redirect 302 /",stroke=GREEN,ret=True)
    els+=msg(ac[1][2],ac[0][2],550,"Landing + boton segun rol","#333",ret=True)
    els+=seq_frame(50,600,850,100,"alt credenciales invalidas",GRAY)
    els+=msg(ac[2][2],ac[3][2],630,"INSERT INTO auditoria (LOGIN FAIL)",stroke=GRAY)
    els+=msg(ac[2][2],ac[1][2],660,"login.html + error","#333",ret=True)
    save("SEQ_01_login.excalidraw",els,"#fafafa")

def seq02_logout():
    els=[]
    els+=title("SEQ-02  Secuencia: Cierre de Sesion",500,14)
    y0,y1=60,500
    ac=[("Usuario","",80,BLUE_L,BLUE),("Navegador",":5000",260,"#f0f0f0","#444"),
        ("Flask","auth.py",440,WINE_L,WINE),("StarRocks",":9030",640,BLUE_L,BLUE)]
    els+=_actors(ac,y0,y1)
    els+=msg(ac[0][2],ac[1][2],150,"Click Salir / GET /logout",stroke="#333")
    els+=msg(ac[1][2],ac[2][2],180,"HTTP GET /logout",stroke=WINE)
    els+=msg(ac[2][2],ac[2][2]-1,210,"session.clear()",stroke=WINE)
    els+=msg(ac[2][2],ac[3][2],240,"INSERT INTO auditoria (LOGOUT)",stroke=WINE)
    els+=msg(ac[3][2],ac[2][2],270,"OK","#333",ret=True)
    els+=msg(ac[2][2],ac[1][2],310,"Redirect 302 /",stroke=WINE,ret=True)
    els+=msg(ac[1][2],ac[0][2],350,"Landing publica (sin sesion)","#333",ret=True)
    save("SEQ_02_logout.excalidraw",els,"#fafafa")

def seq03_catalogo():
    els=[]
    els+=title("SEQ-03  Secuencia: Explorar Catalogo /vinos",600,14)
    y0,y1=60,920
    ac=[("Usuario","",80,BLUE_L,BLUE),("Navegador",":5000",260,"#f0f0f0","#444"),
        ("Flask","app.py",460,WINE_L,WINE),("StarRocks",":9030",680,BLUE_L,BLUE)]
    els+=_actors(ac,y0,y1)
    steps=[(ac[0][2],ac[1][2],140,"GET /vinos"),
           (ac[1][2],ac[2][2],170,"HTTP GET /vinos"),
           (ac[2][2],ac[1][2],210,"vinos.html (shell Jinja2)",None,True),
           (ac[1][2],ac[2][2],260,"GET /api/browse"),
           (ac[2][2],ac[3][2],290,"SELECT nombre,COUNT(*) FROM dim_pais GROUP BY nombre LIMIT 6"),
           (ac[2][2],ac[3][2],320,"SELECT nombre,COUNT(*) FROM dim_variedad GROUP BY nombre LIMIT 6"),
           (ac[2][2],ac[3][2],350,"... (bodegas, regiones)"),
           (ac[3][2],ac[2][2],390,"{paises,variedades,bodegas,regiones}",None,True),
           (ac[2][2],ac[1][2],430,"JSON browse data",None,True),
           (ac[1][2],ac[0][2],470,"Panel de filtros poblado",None,True),
           (ac[0][2],ac[1][2],520,"Selecciona filtro pais=Italy"),
           (ac[1][2],ac[2][2],550,"GET /api/resenas?pais=Italy&per_page=20&page=1"),
           (ac[2][2],ac[3][2],590,"SELECT fr.*,dp.nombre,dv.nombre,db.nombre\nFROM fact_resenas fr\nJOIN dim_pais dp ON fr.id_pais=dp.id_pais\nWHERE dp.nombre='Italy' LIMIT 20 OFFSET 0"),
           (ac[3][2],ac[2][2],660,"{data:[...20 vinos...], total:19540, pages:978}",None,True),
           (ac[2][2],ac[1][2],700,"JSON paginado",None,True),
           (ac[1][2],ac[0][2],740,"Lista de vinos + paginador",None,True),
           (ac[0][2],ac[1][2],790,"Click pagina 2"),
           (ac[1][2],ac[2][2],820,"GET /api/resenas?pais=Italy&page=2"),
           (ac[2][2],ac[3][2],850,"SELECT ... LIMIT 20 OFFSET 20"),
           (ac[3][2],ac[2][2],880,"siguiente pagina",None,True),]
    for x1,x2,y,lbl,*rest in steps:
        r=rest[1] if len(rest)>1 else False
        els+=msg(x1,x2,y,lbl,ret=bool(r))
    save("SEQ_03_catalogo.excalidraw",els,"#fafafa")

def seq04_busqueda():
    els=[]
    els+=title("SEQ-04  Secuencia: Busqueda Avanzada",600,14)
    y0,y1=60,740
    ac=[("Usuario","",80,BLUE_L,BLUE),("Navegador",":5000",260,"#f0f0f0","#444"),
        ("Flask","app.py",460,WINE_L,WINE),("StarRocks",":9030",660,BLUE_L,BLUE)]
    els+=_actors(ac,y0,y1)
    els+=msg(ac[0][2],ac[1][2],140,"Escribe 'Pinot Noir' en buscador hero")
    els+=msg(ac[0][2],ac[1][2],180,"Enter / click buscar")
    els+=msg(ac[1][2],ac[2][2],210,"GET /vinos?q=Pinot+Noir",stroke=WINE)
    els+=msg(ac[2][2],ac[1][2],250,"vinos.html con q=Pinot Noir",ret=True)
    els+=msg(ac[1][2],ac[2][2],300,"GET /api/resenas?q=Pinot+Noir&per_page=20",stroke=WINE)
    els+=msg(ac[2][2],ac[3][2],340,"SELECT fr.*,... FROM fact_resenas fr\nJOIN dim_variedad dv ON fr.id_variedad=dv.id_variedad\nWHERE dv.nombre LIKE '%Pinot Noir%'\nOR fr.title LIKE '%Pinot Noir%'\nORDER BY fr.points DESC",stroke=BLUE)
    els+=msg(ac[3][2],ac[2][2],430,"{data:[...], total:13272, pages:664}",ret=True)
    els+=msg(ac[2][2],ac[1][2],470,"JSON resultados",ret=True)
    els+=msg(ac[1][2],ac[0][2],510,"13,272 resultados Pinot Noir",ret=True)
    els+=msg(ac[0][2],ac[1][2],560,"Refina: agrega pais=US")
    els+=msg(ac[1][2],ac[2][2],590,"GET /api/resenas?q=Pinot+Noir&pais=US",stroke=WINE)
    els+=msg(ac[2][2],ac[3][2],630,"... WHERE dv.nombre LIKE '%Pinot Noir%' AND dp.nombre='US'",stroke=BLUE)
    els+=msg(ac[3][2],ac[2][2],670,"{total:9842}",ret=True)
    els+=msg(ac[2][2],ac[1][2],700,"JSON filtrado",ret=True)
    save("SEQ_04_busqueda.excalidraw",els,"#fafafa")

def seq05_dashboard():
    els=[]
    els+=title("SEQ-05  Secuencia: Dashboard Analista / Gerente",700,14)
    y0,y1=60,860
    ac=[("Analista","",80,GREEN_L,GREEN),("Navegador",":5000",260,"#f0f0f0","#444"),
        ("Flask","/dashboard",460,WINE_L,WINE),("StarRocks",":9030",680,BLUE_L,BLUE)]
    els+=_actors(ac,y0,y1)
    els+=msg(ac[0][2],ac[1][2],140,"GET /dashboard")
    els+=msg(ac[1][2],ac[2][2],170,"HTTP GET /dashboard",stroke=WINE)
    els+=msg(ac[2][2],ac[2][2]-1,200,"Verificar user_id en session")
    els+=seq_frame(50,215,720,60,"alt no autenticado",GRAY)
    els+=msg(ac[2][2],ac[1][2],235,"Redirect /login?next=/dashboard",ret=True)
    els+=seq_frame(50,285,720,60,"alt autenticado",GREEN)
    els+=msg(ac[2][2],ac[1][2],305,"index.html (show_admin=False)",ret=True)
    els+=msg(ac[1][2],ac[2][2],360,"GET /api/kpis")
    els+=msg(ac[2][2],ac[3][2],390,"SELECT COUNT(*) AS total, AVG(points) AS avg_pts,\nAVG(price) AS avg_price FROM fact_resenas",stroke=BLUE)
    els+=msg(ac[3][2],ac[2][2],440,"{total:308724, avg_pts:88.4, avg_price:35.4}",ret=True)
    els+=msg(ac[2][2],ac[1][2],480,"JSON KPIs",ret=True)
    els+=msg(ac[1][2],ac[2][2],520,"GET /api/resenas?per_page=10&puntos_min=95")
    els+=msg(ac[2][2],ac[3][2],550,"SELECT ... WHERE points>=95 ORDER BY points DESC LIMIT 10",stroke=BLUE)
    els+=msg(ac[3][2],ac[2][2],590,"[top 10 vinos 95+ pts]",ret=True)
    els+=msg(ac[2][2],ac[1][2],630,"JSON top wines",ret=True)
    els+=msg(ac[1][2],ac[0][2],670,"Dashboard completo: KPIs + graficos + tabla",ret=True)
    els+=msg(ac[0][2],ac[1][2],720,"Aplica filtro variedad=Cabernet Sauvignon")
    els+=msg(ac[1][2],ac[2][2],750,"GET /api/resenas?variedad=Cabernet+Sauvignon",stroke=WINE)
    els+=msg(ac[2][2],ac[3][2],790,"SELECT ... JOIN dim_variedad WHERE nombre='Cabernet Sauvignon'",stroke=BLUE)
    els+=msg(ac[3][2],ac[2][2],830,"[filtrado]",ret=True)
    save("SEQ_05_dashboard.excalidraw",els,"#fafafa")

def seq06_reportes():
    els=[]
    els+=title("SEQ-06  Secuencia: Exportar Reporte PDF / CSV",600,14)
    y0,y1=60,760
    ac=[("Gerente/Analista","",80,GREEN_L,GREEN),("Navegador","",280,"#f0f0f0","#444"),
        ("Flask","app.py",480,WINE_L,WINE),("StarRocks",":9030",680,BLUE_L,BLUE)]
    els+=_actors(ac,y0,y1)
    els+=msg(ac[0][2],ac[1][2],140,"Click 'Exportar CSV'")
    els+=msg(ac[1][2],ac[2][2],170,"GET /api/exportar?formato=csv&puntos_min=90&pais=France",stroke=WINE)
    els+=msg(ac[2][2],ac[2][2]-1,200,"Verificar sesion activa (analista/gerente/admin)")
    els+=msg(ac[2][2],ac[3][2],240,"SELECT fr.title, dp.nombre AS pais, dv.nombre AS variedad,\nfr.points, fr.price, fr.description\nFROM fact_resenas fr\nJOIN dim_pais dp ... JOIN dim_variedad dv ...\nWHERE fr.points>=90 AND dp.nombre='France'\nORDER BY fr.points DESC",stroke=BLUE)
    els+=msg(ac[3][2],ac[2][2],360,"[ResultSet: N filas]",ret=True)
    els+=msg(ac[2][2],ac[2][2]-1,390,"Convertir a CSV con cabeceras")
    els+=msg(ac[2][2],ac[2][2]-1,420,"Registrar en auditoria (EXPORTAR_CSV)")
    els+=msg(ac[2][2],ac[1][2],460,"Response: archivo.csv\nContent-Disposition: attachment",ret=True)
    els+=msg(ac[1][2],ac[0][2],510,"Descarga iniciada en el navegador",ret=True)
    els+=seq_frame(50,540,720,100,"alt formato=pdf (Fase 3)",PURPLE)
    els+=msg(ac[2][2],ac[2][2]-1,565,"Generar PDF con ReportLab/WeasyPrint")
    els+=msg(ac[2][2],ac[1][2],600,"Response: reporte.pdf",ret=True)
    els+=msg(ac[1][2],ac[0][2],640,"PDF descargado",ret=True)
    save("SEQ_06_reportes.excalidraw",els,"#fafafa")

def seq07_etl():
    els=[]
    els+=title("SEQ-07  Secuencia: Pipeline ETL Completo",800,14,
               "Solo Admin — Extraer CSV -> Transformar -> Cargar StarRocks")
    y0,y1=60,1020
    ac=[("Admin","",80,WINE_L,WINE_D),("Navegador",":5000",260,"#f0f0f0","#444"),
        ("Flask","ETL route",440,WINE_L,WINE),("ETL","Pipeline",640,GOLD_L,"#8a6010"),
        ("StarRocks",":9030",840,BLUE_L,BLUE)]
    els+=_actors(ac,y0,y1)
    els+=msg(ac[0][2],ac[1][2],140,"POST /etl/run")
    els+=msg(ac[1][2],ac[2][2],170,"HTTP POST /etl/run",stroke=WINE)
    els+=msg(ac[2][2],ac[2][2]-1,200,"session.rol == 'admin' ?")
    els+=seq_frame(50,215,870,60,"alt no es admin",GRAY)
    els+=msg(ac[2][2],ac[1][2],235,"403 Forbidden",ret=True)
    els+=seq_frame(50,285,870,660,"alt es admin",WINE)
    els+=msg(ac[2][2],ac[3][2],310,"extractor.run()",stroke=GOLD)
    els+=msg(ac[3][2],ac[3][2]-1,340,"Abrir data/winemag-data-130k-v2.csv")
    els+=msg(ac[3][2],ac[3][2]-1,370,"pd.read_csv() → DataFrame 130,000 filas")
    els+=msg(ac[3][2],ac[2][2],410,"DataFrame crudo",ret=True)
    els+=msg(ac[2][2],ac[3][2],440,"transformer.run(df)",stroke=GOLD)
    els+=msg(ac[3][2],ac[3][2]-1,470,"Extraer valores unicos dim_pais, dim_variedad...")
    els+=msg(ac[3][2],ac[3][2]-1,500,"Asignar IDs, reemplazar nulos, deduplicar")
    els+=msg(ac[3][2],ac[2][2],540,"{dims:{pais,variedad,bodega,provincia,region,catador}, fact:df}",ret=True)
    els+=msg(ac[2][2],ac[3][2],570,"loader.run(dims, fact)",stroke=GOLD)
    els+=msg(ac[3][2],ac[4][2],610,"INSERT INTO dim_pais VALUES ... (UPSERT x44)",stroke=BLUE)
    els+=msg(ac[3][2],ac[4][2],640,"INSERT INTO dim_variedad ... (x708)",stroke=BLUE)
    els+=msg(ac[3][2],ac[4][2],670,"INSERT INTO dim_bodega ... (x16756)",stroke=BLUE)
    els+=msg(ac[3][2],ac[4][2],700,"INSERT INTO dim_region / dim_catador",stroke=BLUE)
    els+=msg(ac[3][2],ac[4][2],730,"INSERT INTO fact_resenas VALUES ... (x308724)",stroke=BLUE)
    els+=msg(ac[4][2],ac[3][2],770,"OK — todos insertados",ret=True)
    els+=msg(ac[3][2],ac[2][2],810,"{insertados:308724, errores:0, tiempo:42.3s}",ret=True)
    els+=msg(ac[2][2],ac[4][2],850,"INSERT INTO auditoria (ETL_COMPLETO, 308724 filas)",stroke=WINE)
    els+=msg(ac[2][2],ac[1][2],890,"JSON {ok:true, stats:{...}}",ret=True)
    els+=msg(ac[1][2],ac[0][2],930,"'308,724 resenas cargadas exitosamente'",ret=True)
    save("SEQ_07_etl.excalidraw",els,"#fafafa")

def seq08_usuarios():
    els=[]
    els+=title("SEQ-08  Secuencia: Gestion de Usuarios (Admin)",680,14)
    y0,y1=60,900
    ac=[("Admin","",80,WINE_L,WINE_D),("Navegador",":5000",280,"#f0f0f0","#444"),
        ("Flask","/usuarios",480,WINE_L,WINE),("StarRocks","usuarios_sistema",700,BLUE_L,BLUE)]
    els+=_actors(ac,y0,y1)
    els+=msg(ac[0][2],ac[1][2],140,"GET /usuarios")
    els+=msg(ac[1][2],ac[2][2],170,"HTTP GET /usuarios",stroke=WINE)
    els+=msg(ac[2][2],ac[3][2],210,"SELECT id,username,rol,activo,created_at\nFROM usuarios_sistema ORDER BY id",stroke=BLUE)
    els+=msg(ac[3][2],ac[2][2],260,"[lista de usuarios]",ret=True)
    els+=msg(ac[2][2],ac[1][2],300,"usuarios.html con tabla",ret=True)
    # crear
    els+=seq_frame(50,320,760,140,"Crear nuevo usuario",GREEN)
    els+=msg(ac[0][2],ac[1][2],345,"POST /usuarios {username,password,rol}")
    els+=msg(ac[1][2],ac[2][2],375,"HTTP POST /usuarios",stroke=WINE)
    els+=msg(ac[2][2],ac[2][2]-1,400,"Validar datos, username_exists()?")
    els+=msg(ac[2][2],ac[3][2],430,"INSERT INTO usuarios_sistema (id,username,hash,rol,activo,now())",stroke=BLUE)
    els+=msg(ac[3][2],ac[2][2],460,"OK",ret=True)
    # editar rol
    els+=seq_frame(50,480,760,120,"Editar rol de usuario",GOLD)
    els+=msg(ac[0][2],ac[1][2],505,"POST /usuarios/2 {rol:gerente, activo:true}")
    els+=msg(ac[1][2],ac[2][2],535,"HTTP POST /usuarios/2",stroke=WINE)
    els+=msg(ac[2][2],ac[3][2],565,"UPDATE usuarios_sistema SET rol='gerente' WHERE id=2",stroke=BLUE)
    els+=msg(ac[3][2],ac[2][2],595,"OK",ret=True)
    # eliminar
    els+=seq_frame(50,620,760,120,"Eliminar usuario",WINE)
    els+=msg(ac[0][2],ac[1][2],645,"POST /usuarios/3/eliminar")
    els+=msg(ac[1][2],ac[2][2],675,"HTTP POST /usuarios/3/eliminar",stroke=WINE)
    els+=msg(ac[2][2],ac[3][2],705,"DELETE FROM usuarios_sistema WHERE id=3",stroke=BLUE)
    els+=msg(ac[3][2],ac[2][2],735,"OK",ret=True)
    els+=msg(ac[2][2],ac[4][2] if len(ac)>4 else ac[3][2],760,"INSERT auditoria (ELIMINAR_USUARIO id=3)",stroke=WINE)
    els+=msg(ac[2][2],ac[1][2],795,"Redirect /usuarios con mensaje exito",ret=True)
    save("SEQ_08_usuarios.excalidraw",els,"#fafafa")

def seq09_auditoria():
    els=[]
    els+=title("SEQ-09  Secuencia: Ver Auditoria del Sistema",660,14)
    y0,y1=60,760
    ac=[("Admin","",80,WINE_L,WINE_D),("Navegador","",260,"#f0f0f0","#444"),
        ("Flask","/auditoria",460,WINE_L,WINE),("StarRocks","auditoria",680,BLUE_L,BLUE)]
    els+=_actors(ac,y0,y1)
    els+=msg(ac[0][2],ac[1][2],140,"GET /auditoria")
    els+=msg(ac[1][2],ac[2][2],170,"HTTP GET /auditoria",stroke=WINE)
    els+=msg(ac[2][2],ac[2][2]-1,200,"Verificar session.rol == 'admin'")
    els+=msg(ac[2][2],ac[3][2],240,"SELECT id,usuario,rol,accion,detalle,ip,fecha\nFROM auditoria ORDER BY fecha DESC LIMIT 100",stroke=BLUE)
    els+=msg(ac[3][2],ac[2][2],290,"[100 registros mas recientes]",ret=True)
    els+=msg(ac[2][2],ac[1][2],330,"auditoria.html con tabla",ret=True)
    els+=msg(ac[1][2],ac[0][2],370,"Tabla: usuario, accion, detalle, IP, fecha",ret=True)
    els+=seq_frame(50,390,740,120,"Filtrar por usuario",BLUE)
    els+=msg(ac[0][2],ac[1][2],415,"GET /auditoria?usuario=analista1&accion=LOGIN")
    els+=msg(ac[1][2],ac[2][2],445,"HTTP GET /auditoria?usuario=analista1",stroke=WINE)
    els+=msg(ac[2][2],ac[3][2],475,"SELECT ... WHERE usuario='analista1' AND accion='LOGIN'\nORDER BY fecha DESC",stroke=BLUE)
    els+=msg(ac[3][2],ac[2][2],520,"[registros filtrados]",ret=True)
    els+=msg(ac[2][2],ac[1][2],560,"tabla filtrada",ret=True)
    els+=seq_frame(50,590,740,80,"Exportar CSV",GRAY)
    els+=msg(ac[0][2],ac[1][2],615,"GET /auditoria/exportar")
    els+=msg(ac[2][2],ac[3][2],645,"SELECT * FROM auditoria WHERE ...",stroke=BLUE)
    els+=msg(ac[2][2],ac[1][2],680,"Response: auditoria.csv",ret=True)
    save("SEQ_09_auditoria.excalidraw",els,"#fafafa")

def seq10_respaldos():
    els=[]
    els+=title("SEQ-10  Secuencia: Respaldos del Sistema",660,14)
    y0,y1=60,760
    ac=[("Admin","",80,WINE_L,WINE_D),("Navegador","",260,"#f0f0f0","#444"),
        ("Flask","backup_manager",460,WINE_L,WINE),("StarRocks",":9030",660,BLUE_L,BLUE),
        ("FileSystem","/backups",860,GOLD_L,"#8a6010")]
    els+=_actors(ac,y0,y1)
    els+=msg(ac[0][2],ac[1][2],140,"GET /respaldos")
    els+=msg(ac[1][2],ac[2][2],170,"HTTP GET /respaldos",stroke=WINE)
    els+=msg(ac[2][2],ac[4][2],210,"Listar archivos en /app/backups/*.sql")
    els+=msg(ac[4][2],ac[2][2],250,"[lista de respaldos con fecha/tamanio]",ret=True)
    els+=msg(ac[2][2],ac[1][2],290,"respaldos.html con lista",ret=True)
    els+=seq_frame(50,310,900,190,"Crear respaldo manual",GREEN)
    els+=msg(ac[0][2],ac[1][2],335,"POST /respaldos/crear")
    els+=msg(ac[1][2],ac[2][2],365,"HTTP POST /respaldos/crear",stroke=WINE)
    els+=msg(ac[2][2],ac[3][2],400,"SHOW DATABASES / SELECT TABLE_NAME...",stroke=BLUE)
    els+=msg(ac[3][2],ac[2][2],430,"schema + data",ret=True)
    els+=msg(ac[2][2],ac[4][2],460,"Escribir backup_2024-01-15_143022.sql")
    els+=msg(ac[4][2],ac[2][2],490,"archivo creado (tamanio MB)",ret=True)
    els+=msg(ac[2][2],ac[3][2],510,"INSERT INTO auditoria (BACKUP_CREADO)",stroke=WINE)
    els+=msg(ac[2][2],ac[1][2],540,"{ok:true, archivo:'backup_2024-01-15.sql'}",ret=True)
    els+=seq_frame(50,520,900,100,"Restaurar respaldo (Fase 4)",PURPLE)
    els+=msg(ac[0][2],ac[1][2],545,"POST /respaldos/restaurar {archivo:'backup_X.sql'}")
    els+=msg(ac[2][2],ac[4][2],575,"Leer archivo .sql")
    els+=msg(ac[2][2],ac[3][2],605,"Ejecutar sentencias SQL del backup",stroke=BLUE)
    els+=msg(ac[3][2],ac[2][2],635,"OK restaurado",ret=True)
    save("SEQ_10_respaldos.excalidraw",els,"#fafafa")

# ════════════════════════════════════════════════════════════════════════════
#  BASE DE DATOS
# ════════════════════════════════════════════════════════════════════════════

def db01_estrella():
    els=[]
    els+=title("DB-01  Modelo Estrella — StarRocks OLAP",860,14,
               "fact_resenas (308,724 filas) + 6 dimensiones — vinanalytics_db")
    fact_x,fact_y=560,320
    fact_cols=[("points","INT NOT NULL"),("price","DECIMAL(10,2)"),
               ("title","VARCHAR(500)"),("designation","VARCHAR(300)"),
               ("description","VARCHAR(1000)"),("region_2","VARCHAR(150)"),
               ("id_pais","INT  FK"),("id_variedad","INT  FK"),
               ("id_bodega","INT  FK"),("id_provincia","INT  FK"),
               ("id_region","INT  FK"),("id_catador","INT  FK")]
    fe,fcx,fcy=db_table(fact_x,fact_y,"fact_resenas",
        "DUPLICATE KEY | 308,724 filas | 10 buckets",
        ("id_resena","INT"),fact_cols,hbg=WINE,bbg="#fff8f8",w=260)
    els+=fe
    dims=[(100,60,"dim_pais","44 paises | 3 buckets",("id_pais","INT"),
           [("nombre","VARCHAR(100)")],BLUE),
          (1000,60,"dim_variedad","708 variedades | 3 buckets",("id_variedad","INT"),
           [("nombre","VARCHAR(150)")],BLUE),
          (1120,360,"dim_bodega","16,756 bodegas | 3 buckets",("id_bodega","INT"),
           [("nombre","VARCHAR(200)")],BLUE),
          (1000,760,"dim_catador","Catadores | 3 buckets",("id_catador","INT"),
           [("nombre","VARCHAR(150)"),("twitter","VARCHAR(100)")],BLUE),
          (100,760,"dim_region","Regiones | 3 buckets",("id_region","INT"),
           [("nombre","VARCHAR(150)")],BLUE),
          (60,400,"dim_provincia","Provincias | 3 buckets",("id_provincia","INT"),
           [("nombre","VARCHAR(150)")],BLUE)]
    for *args,hbg in dims:
        de,dcx,dcy=db_table(*args,hbg=hbg,bbg=BLUE_L,w=220)
        els+=de
        els.append(arr(dcx,dcy,fcx,fcy,stroke=GOLD,sw=2,ss="dashed"))
    # nota
    els+=note_box(60,1020,880,60,
        "StarRocks: ENGINE=OLAP | DISTRIBUTED BY HASH(<pk>) | replication_num=1\n"
        "Dims: PRIMARY KEY model (upsert) | Fact: DUPLICATE KEY model (alto rendimiento)")
    save("DB_01_estrella.excalidraw",els,"#fafafa")

def db02_operacional():
    els=[]
    els+=title("DB-02  Tablas Operacionales — StarRocks",600,14,
               "Autenticacion, auditoria y configuracion del sistema")
    # usuarios_sistema
    ue,_,_=db_table(80,100,"usuarios_sistema","PRIMARY KEY | Autenticacion Flask",
        ("id","INT"),
        [("username","VARCHAR(50) UNIQUE"),("password_hash","VARCHAR(255)"),
         ("rol","VARCHAR(20)  — admin|analista|gerente"),("activo","BOOLEAN"),
         ("created_at","DATETIME")],hbg=WINE,bbg=WINE_L,w=300)
    els+=ue
    # auditoria
    ae,_,_=db_table(460,100,"auditoria","DUPLICATE KEY | Log inmutable de acciones",
        ("id","INT"),
        [("usuario","VARCHAR(50)"),("rol","VARCHAR(20)"),
         ("accion","VARCHAR(100)  — LOGIN|LOGOUT|ETL|BACKUP|..."),
         ("detalle","VARCHAR(1000)"),("ip","VARCHAR(50)"),("fecha","DATETIME")],
        hbg=PURPLE,bbg=PURPLE_L,w=340)
    els+=ae
    # future: favoritos
    fe,_,_=db_table(880,100,"favoritos (Fase 3)","PRIMARY KEY | Vinos guardados",
        ("id","INT"),
        [("user_id","INT  FK → usuarios_sistema"),
         ("id_resena","INT  FK → fact_resenas"),("created_at","DATETIME")],
        hbg=GREEN,bbg=GREEN_L,w=280)
    els+=fe
    # future: sesiones
    se,_,_=db_table(80,420,"sesiones_api (Fase 4)","API Keys para acceso externo",
        ("id","INT"),
        [("user_id","INT  FK"),("api_key","VARCHAR(64) UNIQUE"),
         ("nombre","VARCHAR(100)"),("activo","BOOLEAN"),("created_at","DATETIME"),
         ("last_used","DATETIME")],hbg=BLUE,bbg=BLUE_L,w=300)
    els+=se
    # Acciones enum
    els+=note_box(460,420,680,200,
        "Valores de auditoria.accion:\n"
        "  LOGIN              — inicio de sesion\n"
        "  LOGOUT             — cierre de sesion\n"
        "  LOGIN_FAIL         — intento fallido\n"
        "  ETL_INICIO         — pipeline iniciado\n"
        "  ETL_COMPLETO       — pipeline exitoso\n"
        "  ETL_ERROR          — pipeline fallido\n"
        "  BACKUP_CREADO      — respaldo generado\n"
        "  RESTAURAR_BACKUP   — restauracion\n"
        "  CREAR_USUARIO      — nuevo usuario\n"
        "  EDITAR_USUARIO     — cambio de rol\n"
        "  ELIMINAR_USUARIO   — usuario borrado\n"
        "  EXPORTAR_CSV       — descarga de datos\n"
        "  EXPORTAR_PDF       — reporte descargado")
    save("DB_02_operacional.excalidraw",els,"#fafafa")

# ════════════════════════════════════════════════════════════════════════════
#  ACTIVIDAD
# ════════════════════════════════════════════════════════════════════════════

def act01_etl():
    els=[]
    els+=title("ACT-01  Actividad: Pipeline ETL Completo",500,14)
    x=360; y=80
    els+=start_node(x,y); y+=40
    els.append(arr(x,y,x,y+30,stroke=GRAY,sw=2)); y+=30
    els+=activity(x-120,y,240,40,"Admin accede a /admin",bg=WINE_L,stroke=WINE); y+=40
    els.append(arr(x,y,x,y+30,stroke=GRAY,sw=2)); y+=30
    els+=decision(x-100,y,200,50,"Sesion admin\nvalida?",bg=GOLD_L,stroke=GOLD); y+=50
    # No branch
    els.append(arr(x+100,y-25,x+260,y-25,stroke=GRAY,sw=1))
    els+=activity(x+260-60,y-45,200,40,"Error 403\nForbidden",bg="#ffe8e8",stroke=WINE)
    els.append(arr(x+260+40,y-25,x+260+40,y+200,stroke=GRAY,sw=1,ss="dashed"))
    els.append(txt("No",x+105,y-38,size=11,color=GRAY))
    els.append(txt("Si",x+5,y+5,size=11,color=GRAY))
    els.append(arr(x,y,x,y+30,stroke=GRAY,sw=2)); y+=30
    els+=activity(x-120,y,240,40,"Leer winemag-data-130k-v2.csv",bg=GOLD_L,stroke="#8a6010"); y+=40
    els.append(arr(x,y,x,y+30,stroke=GRAY,sw=2)); y+=30
    els+=decision(x-100,y,200,50,"Archivo\nexiste?",bg=GOLD_L,stroke=GOLD); y+=50
    els.append(arr(x+100,y-25,x+260,y-25,stroke=GRAY,sw=1))
    els+=activity(x+260-60,y-45,200,40,"Error: archivo\nno encontrado",bg="#ffe8e8",stroke=WINE)
    els.append(txt("No",x+105,y-38,size=11,color=GRAY))
    els.append(txt("Si",x+5,y+5,size=11,color=GRAY))
    els.append(arr(x,y,x,y+30,stroke=GRAY,sw=2)); y+=30
    for lbl,bg in [("Transformar: Normalizar valores",GOLD_L),
                    ("Extraer dimensiones unicas",GOLD_L),
                    ("Asignar IDs a cada dimension",GOLD_L),
                    ("Limpiar nulos y deduplicar",GOLD_L),
                    ("Cargar dim_pais (44 filas)",BLUE_L),
                    ("Cargar dim_variedad (708 filas)",BLUE_L),
                    ("Cargar dim_bodega (16,756 filas)",BLUE_L),
                    ("Cargar dim_region / dim_catador",BLUE_L),
                    ("Cargar fact_resenas (308,724 filas)",BLUE_L)]:
        els+=activity(x-120,y,240,40,lbl,bg=bg,stroke=BLUE if "Cargar" in lbl or "dim" in lbl else "#8a6010")
        y+=40
        els.append(arr(x,y,x,y+20,stroke=GRAY,sw=2)); y+=20
    els+=activity(x-120,y,240,40,"Registrar en auditoria",bg=WINE_L,stroke=WINE); y+=40
    els.append(arr(x,y,x,y+20,stroke=GRAY,sw=2)); y+=20
    els+=activity(x-120,y,240,40,"Notificar resultado al Admin",bg=GREEN_L,stroke=GREEN); y+=40
    els.append(arr(x,y,x,y+20,stroke=GRAY,sw=2)); y+=20
    els+=end_node(x,y)
    save("ACT_01_etl.excalidraw",els,"#fafafa")

def act02_login():
    els=[]
    els+=title("ACT-02  Actividad: Flujo de Autenticacion",500,14)
    x=360; y=80
    els+=start_node(x,y); y+=40
    els.append(arr(x,y,x,y+20,stroke=GRAY,sw=2)); y+=20
    for lbl,bg,st in [("Usuario accede a /login","#f0f0f0","#444"),
                       ("Ingresar username y password",BLUE_L,BLUE)]:
        els+=activity(x-120,y,240,40,lbl,bg=bg,stroke=st); y+=40
        els.append(arr(x,y,x,y+20,stroke=GRAY,sw=2)); y+=20
    els+=decision(x-100,y,200,50,"Campos\nvacios?",bg=GOLD_L,stroke=GOLD); y+=50
    els.append(arr(x+100,y-25,x+260,y-25,stroke=GRAY,sw=1))
    els+=activity(x+260-60,y-45,200,40,"Mostrar error\nvalidacion",bg=WINE_L,stroke=WINE)
    els.append(arr(x+260+40,y-25,x+260+40,y0+160 if (y0:=y-50) else y,stroke=GRAY,sw=1,ss="dashed"))
    els.append(txt("Si",x+105,y-38,size=11,color=GRAY))
    els.append(txt("No",x+5,y+5,size=11,color=GRAY))
    els.append(arr(x,y,x,y+20,stroke=GRAY,sw=2)); y+=20
    els+=activity(x-120,y,240,40,"Consultar StarRocks: username=?",bg=BLUE_L,stroke=BLUE); y+=40
    els.append(arr(x,y,x,y+20,stroke=GRAY,sw=2)); y+=20
    els+=decision(x-100,y,200,50,"Usuario\nexiste?",bg=GOLD_L,stroke=GOLD); y+=50
    els.append(arr(x+100,y-25,x+280,y-25,stroke=GRAY,sw=1))
    els+=activity(x+280-60,y-45,220,40,"Registrar LOGIN_FAIL\nen auditoria",bg=WINE_L,stroke=WINE)
    els.append(txt("No",x+105,y-38,size=11,color=GRAY))
    els.append(txt("Si",x+5,y+5,size=11,color=GRAY))
    els.append(arr(x,y,x,y+20,stroke=GRAY,sw=2)); y+=20
    els+=activity(x-120,y,240,40,"Verificar bcrypt hash",bg=BLUE_L,stroke=BLUE); y+=40
    els.append(arr(x,y,x,y+20,stroke=GRAY,sw=2)); y+=20
    els+=decision(x-100,y,200,50,"Password\ncorrecto?",bg=GOLD_L,stroke=GOLD); y+=50
    els.append(txt("No",x+105,y-38,size=11,color=GRAY))
    els.append(txt("Si",x+5,y+5,size=11,color=GRAY))
    els.append(arr(x,y,x,y+20,stroke=GRAY,sw=2)); y+=20
    els+=activity(x-120,y,240,40,"Crear session[user_id, rol]",bg=GREEN_L,stroke=GREEN); y+=40
    els.append(arr(x,y,x,y+20,stroke=GRAY,sw=2)); y+=20
    els+=activity(x-120,y,240,40,"Registrar LOGIN_OK en auditoria",bg=GREEN_L,stroke=GREEN); y+=40
    els.append(arr(x,y,x,y+20,stroke=GRAY,sw=2)); y+=20
    els+=decision(x-100,y,200,50,"Rol del\nusuario?",bg=GOLD_L,stroke=GOLD); y+=50
    for i,(lbl,route,color) in enumerate([("admin","Redirect /admin",WINE_D),
        ("analista/gerente","Redirect /dashboard",GREEN),
        ("publico","Redirect /",BLUE)]):
        ox=x-280+i*280
        els.append(arr(x if i==1 else x+(1 if i==2 else -1)*100,y-25,ox,y-25,stroke=GRAY,sw=1))
        els+=activity(ox-100,y-45,200,40,f"{lbl}\n{route}",bg=WINE_L if i==0 else GREEN_L if i==1 else BLUE_L,
                      stroke=WINE_D if i==0 else GREEN if i==1 else BLUE)
    y+=30; els+=end_node(x,y)
    save("ACT_02_login.excalidraw",els,"#fafafa")

def act03_reporte():
    els=[]
    els+=title("ACT-03  Actividad: Generacion de Reporte",500,14)
    x=380; y=80
    els+=start_node(x,y); y+=40
    pasos=[("Analista/Gerente accede a Dashboard","#f0f0f0","#444"),
           ("Aplica filtros (pais, variedad, puntos, precio)",BLUE_L,BLUE),
           ("Click 'Exportar Resultados'",BLUE_L,BLUE)]
    for lbl,bg,st in pasos:
        els.append(arr(x,y,x,y+20,stroke=GRAY,sw=2)); y+=20
        els+=activity(x-140,y,280,40,lbl,bg=bg,stroke=st); y+=40
    els.append(arr(x,y,x,y+20,stroke=GRAY,sw=2)); y+=20
    els+=decision(x-110,y,220,50,"Formato\nseleccionado?",bg=GOLD_L,stroke=GOLD); y+=50
    # CSV branch
    els.append(arr(x-110,y-25,x-300,y-25,stroke=GRAY,sw=1))
    els.append(txt("CSV",x-200,y-38,size=11,color=GRAY,align="center"))
    csv_y=y-25
    els+=activity(x-440,csv_y-20,200,40,"Consultar StarRocks\ncon filtros activos",bg=BLUE_L,stroke=BLUE)
    els.append(arr(x-340,csv_y+20,x-340,csv_y+60,stroke=GRAY,sw=2))
    els+=activity(x-440,csv_y+60,200,40,"Convertir ResultSet\na formato CSV",bg=GOLD_L,stroke="#8a6010")
    els.append(arr(x-340,csv_y+100,x-340,csv_y+140,stroke=GRAY,sw=2))
    els+=activity(x-440,csv_y+140,200,40,"Response: attachment\nfilename=reporte.csv",bg=GREEN_L,stroke=GREEN)
    # PDF branch
    els.append(arr(x+110,y-25,x+300,y-25,stroke=GRAY,sw=1))
    els.append(txt("PDF (Fase 3)",x+210,y-38,size=11,color=GRAY,align="center"))
    pdf_y=y-25
    els+=activity(x+200,pdf_y-20,220,40,"Consultar StarRocks\ncon filtros activos",bg=BLUE_L,stroke=BLUE)
    els.append(arr(x+310,pdf_y+20,x+310,pdf_y+60,stroke=GRAY,sw=2))
    els+=activity(x+200,pdf_y+60,220,40,"Generar PDF\n(ReportLab/WeasyPrint)",bg=PURPLE_L,stroke=PURPLE)
    els.append(arr(x+310,pdf_y+100,x+310,pdf_y+140,stroke=GRAY,sw=2))
    els+=activity(x+200,pdf_y+140,220,40,"Response: attachment\nfilename=reporte.pdf",bg=GREEN_L,stroke=GREEN)
    # join
    merge_y=csv_y+220
    els.append(arr(x-340,csv_y+180,x-340,merge_y,stroke=GRAY,sw=2))
    els.append(arr(x+310,pdf_y+180,x+310,merge_y,stroke=GRAY,sw=2))
    els.append(line(x-340,merge_y,x+310,merge_y,stroke=GRAY,sw=2))
    els.append(arr(x,merge_y,x,merge_y+30,stroke=GRAY,sw=2))
    els+=activity(x-140,merge_y+30,280,40,"Registrar EXPORTAR en auditoria",bg=WINE_L,stroke=WINE)
    els.append(arr(x,merge_y+70,x,merge_y+100,stroke=GRAY,sw=2))
    els+=end_node(x,merge_y+100)
    save("ACT_03_reporte.excalidraw",els,"#fafafa")

def act04_respaldo():
    els=[]
    els+=title("ACT-04  Actividad: Proceso de Respaldo",500,14)
    x=380; y=80
    els+=start_node(x,y); y+=40
    for lbl,bg,st in [("Admin accede a /respaldos",WINE_L,WINE_D),
                       ("Click 'Crear Respaldo Manual'",WINE_L,WINE_D)]:
        els.append(arr(x,y,x,y+20,stroke=GRAY,sw=2)); y+=20
        els+=activity(x-140,y,280,40,lbl,bg=bg,stroke=st); y+=40
    els.append(arr(x,y,x,y+20,stroke=GRAY,sw=2)); y+=20
    els+=activity(x-140,y,280,40,"Generar nombre: backup_YYYY-MM-DD_HHMMSS.sql",bg=BLUE_L,stroke=BLUE); y+=40
    els.append(arr(x,y,x,y+20,stroke=GRAY,sw=2)); y+=20
    els+=activity(x-140,y,280,40,"Exportar esquema StarRocks a SQL",bg=BLUE_L,stroke=BLUE); y+=40
    els.append(arr(x,y,x,y+20,stroke=GRAY,sw=2)); y+=20
    els+=activity(x-140,y,280,40,"Exportar datos (INSERT INTO...)",bg=BLUE_L,stroke=BLUE); y+=40
    els.append(arr(x,y,x,y+20,stroke=GRAY,sw=2)); y+=20
    els+=activity(x-140,y,280,40,"Guardar en /app/backups/",bg=GOLD_L,stroke="#8a6010"); y+=40
    els.append(arr(x,y,x,y+20,stroke=GRAY,sw=2)); y+=20
    els+=decision(x-110,y,220,50,"Archivo\nescrito OK?",bg=GOLD_L,stroke=GOLD); y+=50
    els.append(arr(x+110,y-25,x+280,y-25,stroke=GRAY,sw=1))
    els+=activity(x+280-60,y-45,200,40,"Registrar BACKUP_ERROR\nen auditoria",bg=WINE_L,stroke=WINE)
    els.append(txt("No",x+115,y-38,size=11,color=GRAY))
    els.append(txt("Si",x+5,y+5,size=11,color=GRAY))
    els.append(arr(x,y,x,y+20,stroke=GRAY,sw=2)); y+=20
    els+=activity(x-140,y,280,40,"Registrar BACKUP_CREADO en auditoria",bg=GREEN_L,stroke=GREEN); y+=40
    els.append(arr(x,y,x,y+20,stroke=GRAY,sw=2)); y+=20
    els+=activity(x-140,y,280,40,"Mostrar mensaje exito + lista actualizada",bg=GREEN_L,stroke=GREEN); y+=40
    els.append(arr(x,y,x,y+20,stroke=GRAY,sw=2)); y+=20
    els+=end_node(x,y)
    save("ACT_04_respaldo.excalidraw",els,"#fafafa")

# ════════════════════════════════════════════════════════════════════════════
#  ESTADOS
# ════════════════════════════════════════════════════════════════════════════

def est01_sesion():
    els=[]
    els+=title("EST-01  Diagrama de Estado: Sesion de Usuario",700,14)
    states={
        "sin_sesion":(300,200,"Sin Sesion","usuario no autenticado"),
        "pub":(680,200,"Sesion Publica","[no aplica — acceso libre]"),
        "analista":(300,420,"Sesion Analista","dashboard + KPIs"),
        "gerente":(680,420,"Sesion Gerente","dashboard + comparativas"),
        "admin":(490,620,"Sesion Admin","acceso total al sistema"),
        "expirada":(900,420,"Sesion Expirada","timeout 30 min"),
    }
    for k,(x,y,lbl,sub) in states.items():
        els+=state_box(x-100,y-25,200,60,lbl,sub)
    # initial
    els+=start_node(300,120)
    els.append(arr(300,135,300,175,stroke=GRAY,sw=2))
    # transitions
    transitions=[
        ("sin_sesion","analista","login analista OK"),
        ("sin_sesion","gerente","login gerente OK"),
        ("sin_sesion","admin","login admin OK"),
        ("analista","sin_sesion","POST /logout"),
        ("gerente","sin_sesion","POST /logout"),
        ("admin","sin_sesion","POST /logout"),
        ("analista","expirada","timeout 30 min"),
        ("gerente","expirada","timeout 30 min"),
        ("admin","expirada","timeout 60 min"),
        ("expirada","sin_sesion","redirect a /login"),
    ]
    for src,dst,lbl in transitions:
        sx,sy,*_=states[src]; dx,dy,*_=states[dst]
        els.append(arr(sx,sy,dx,dy,stroke=WINE,sw=1,ss="solid"))
        mx=(sx+dx)//2; my=(sy+dy)//2
        els.append(txt(lbl,mx-len(lbl)*3,my-14,size=10,color=GRAY,align="center"))
    # final
    els+=end_node(300,760)
    els.append(arr(300,645,300,742,stroke=GRAY,sw=2))
    save("EST_01_sesion.excalidraw",els,"#fafafa")

def est02_etl():
    els=[]
    els+=title("EST-02  Diagrama de Estado: Proceso ETL",700,14)
    states={"idle":(200,200,"Inactivo","Esperando solicitud admin"),
            "validando":(500,200,"Validando","Verificando permisos + archivo"),
            "extrayendo":(800,200,"Extrayendo","Leyendo CSV 130k filas"),
            "transformando":(800,380,"Transformando","Normalizando dimensiones"),
            "cargando":(800,560,"Cargando","INSERT StarRocks"),
            "completado":(500,560,"Completado","308,724 filas cargadas"),
            "error":(200,560,"Error","Fallo en pipeline")}
    for k,(x,y,lbl,sub) in states.items():
        bg=GREEN_L if k=="completado" else WINE_L if k=="error" else BLUE_L
        st=GREEN if k=="completado" else WINE if k=="error" else BLUE
        els+=state_box(x-100,y-25,200,60,lbl,sub,bg=bg,stroke=st)
    els+=start_node(200,120); els.append(arr(200,135,200,175,stroke=GRAY,sw=2))
    trs=[("idle","validando","POST /etl/run"),
         ("validando","error","sesion invalida / sin CSV"),
         ("validando","extrayendo","validacion OK"),
         ("extrayendo","error","error lectura CSV"),
         ("extrayendo","transformando","DataFrame listo"),
         ("transformando","cargando","dims transformados"),
         ("cargando","error","error INSERT"),
         ("cargando","completado","308,724 OK"),
         ("completado","idle","listo"),
         ("error","idle","reset / reintentar")]
    for src,dst,lbl in trs:
        sx,sy,*_=states[src]; dx,dy,*_=states[dst]
        els.append(arr(sx,sy,dx,dy,stroke=WINE,sw=1))
        mx=(sx+dx)//2; my=(sy+dy)//2
        els.append(txt(lbl,mx-len(lbl)*3,my-12,size=10,color=GRAY,align="center"))
    els+=end_node(500,680); els.append(arr(500,590,500,662,stroke=GRAY,sw=2))
    save("EST_02_etl.excalidraw",els,"#fafafa")

def est03_solicitud():
    els=[]
    els+=title("EST-03  Diagrama de Estado: Solicitud HTTP",700,14)
    states={"recibida":(160,200,"Recibida","Flask recibe HTTP request"),
            "auth":(420,200,"Autenticando","Verificar session cookie"),
            "procesando":(680,200,"Procesando","Ejecutar logica de negocio"),
            "consultando":(680,380,"Consultando BD","SELECT en StarRocks"),
            "auditando":(680,560,"Auditando","INSERT en auditoria"),
            "respondiendo":(420,560,"Respondiendo","Preparar HTTP response"),
            "completada":(160,560,"Completada","Response enviada al cliente"),
            "error_auth":(420,380,"Error Auth","401/403"),
            "error_srv":(160,380,"Error Servidor","500")}
    for k,(x,y,lbl,sub) in states.items():
        bg=GREEN_L if k=="completada" else WINE_L if "error" in k else BLUE_L
        st=GREEN if k=="completada" else WINE if "error" in k else BLUE
        els+=state_box(x-100,y-30,200,65,lbl,sub,bg=bg,stroke=st)
    els+=start_node(160,120); els.append(arr(160,135,160,170,stroke=GRAY,sw=2))
    trs=[("recibida","auth","parse request"),
         ("auth","error_auth","sin sesion / rol incorrecto"),
         ("auth","procesando","sesion valida"),
         ("procesando","consultando","requiere datos"),
         ("procesando","respondiendo","sin consulta"),
         ("consultando","auditando","resultado OK"),
         ("consultando","error_srv","timeout/error SQL"),
         ("auditando","respondiendo","log guardado"),
         ("respondiendo","completada","send response"),
         ("error_auth","completada","401/403 response"),
         ("error_srv","completada","500 response")]
    for src,dst,lbl in trs:
        sx,sy,*_=states[src]; dx,dy,*_=states[dst]
        els.append(arr(sx,sy,dx,dy,stroke=WINE,sw=1))
        mx=(sx+dx)//2; my=(sy+dy)//2
        els.append(txt(lbl,mx-len(lbl)*3,my-12,size=10,color=GRAY,align="center"))
    els+=end_node(160,680); els.append(arr(160,595,160,662,stroke=GRAY,sw=2))
    save("EST_03_solicitud.excalidraw",els,"#fafafa")

# ════════════════════════════════════════════════════════════════════════════
#  ARQUITECTURA
# ════════════════════════════════════════════════════════════════════════════

def arch01_despliegue():
    els=[]
    els+=title("ARCH-01  Diagrama de Despliegue — Docker Compose",900,14,
               "Infraestructura completa: Flask + StarRocks + PocketBase + Nginx (Fase 4)")
    # browser
    els+=component_box(30,140,180,80,"Navegador Web","HTTP/HTTPS cliente",bg=BLUE_L,stroke=BLUE)
    # nginx
    els+=component_box(260,120,220,120,"Nginx (Fase 4)",":80 / :443 TLS\nReverse Proxy",bg=GOLD_L,stroke=GOLD)
    els.append(arr(210,180,260,180,stroke=BLUE,sw=2))
    # docker host
    els.append(rect(530,80,1060,820,bg="#fdf8f4",stroke=WINE,sw=3,rounded=True))
    els.append(txt("Docker Host — docker-compose.yml",980,88,size=15,color=WINE_D,align="center"))
    # flask
    els.append(rect(560,130,400,300,bg="#fff8f0",stroke=GOLD,sw=2,rounded=True))
    els.append(txt("vinanalytics-flask  :5000",680,138,size=13,color="#8a6010"))
    for i,c in enumerate(["app.py — Rutas y controladores","auth.py — Autenticacion Flask",
                           "etl/ — Pipeline E-T-L","audit.py — Registro de acciones",
                           "backup_manager.py","models.py / db_manager.py"]):
        els.append(rect(572,162+i*38,376,30,bg="#fffcf5",stroke=GOLD,sw=1,rounded=True))
        els.append(txt(c,582,170+i*38,size=11,color="#5a4010"))
    els.append(arr(480,180,560,260,stroke=GOLD,sw=2))
    # starrocks
    els.append(rect(560,460,400,310,bg=BLUE_L,stroke=BLUE,sw=2,rounded=True))
    els.append(txt("vinanalytics-starrocks",680,468,size=13,color=BLUE))
    for i,c in enumerate([":9030 MySQL Protocol","Frontend Node (FE)  :8030",
                           "Backend Node (BE)  :8040","vinanalytics_db",
                           "fact_resenas + dim_* (308k)","usuarios_sistema + auditoria"]):
        els.append(rect(572,492+i*38,376,30,bg="#f0f8ff",stroke=BLUE,sw=1,rounded=True))
        els.append(txt(c,582,500+i*38,size=11,color="#1a3a6a"))
    els.append(arr(760,430,760,460,stroke=BLUE,sw=2))
    # pocketbase
    els.append(rect(1000,130,360,200,bg=GREEN_L,stroke=GREEN,sw=2,rounded=True))
    els.append(txt("vinanalytics-pocketbase  :8090",1120,138,size=12,color=GREEN))
    for i,c in enumerate([":8090 REST API / Admin UI","pb_data — Colecciones OAuth",
                           "Autenticacion externa (Fase 3-4)","Webhooks / Eventos"]):
        els.append(rect(1012,162+i*38,336,30,bg="#f4fff6",stroke=GREEN,sw=1,rounded=True))
        els.append(txt(c,1022,170+i*38,size=11,color="#1a4a10"))
    els.append(arr(960,220,1000,220,stroke=GREEN,sw=2))
    # redis
    els.append(rect(1000,360,360,140,bg="#fff0e8",stroke="#c04010",sw=2,ss="dashed",rounded=True))
    els.append(txt("Redis Cache (Fase 4)  :6379",1120,368,size=12,color="#8a2010",align="center"))
    els.append(txt(":6379 — Cache consultas OLAP",1010,394,size=11,color=GRAY))
    els.append(txt("Sesiones / Rate limiting",1010,416,size=11,color=GRAY))
    els.append(txt("[futuro]",1130,448,size=10,color="#c04010",align="center"))
    # celery
    els.append(rect(1000,530,360,150,bg=PURPLE_L,stroke=PURPLE,sw=2,ss="dashed",rounded=True))
    els.append(txt("Celery Worker (Fase 4)",1120,538,size=12,color=PURPLE,align="center"))
    els.append(txt("ETL Programado (cron)",1010,562,size=11,color=GRAY))
    els.append(txt("Respaldos Automaticos",1010,584,size=11,color=GRAY))
    els.append(txt("Notificaciones / Alertas",1010,606,size=11,color=GRAY))
    els.append(txt("[futuro]",1130,650,size=10,color=PURPLE,align="center"))
    # volumes
    els.append(rect(560,800,920,70,bg=GRAY_L,stroke=GRAY,sw=1,ss="dashed",rounded=True))
    els.append(txt("Volumenes: starrocks_data | pocketbase_data | ./backups | ./templates | ./data | ./etl",
                   600,820,size=11,color=GRAY))
    # csv source
    els.append(rect(30,380,180,100,bg="#f8f8f8",stroke=GRAY,sw=2,ss="dashed",rounded=True))
    els.append(txt("CSV Source",80,396,size=12,color=GRAY,align="center"))
    els.append(txt("winemag-data\n130k-v2.csv",50,416,size=11,color=GRAY))
    els.append(arr(210,430,530,570,stroke=GRAY,sw=1,ss="dashed"))
    save("ARCH_01_despliegue.excalidraw",els,"#fafafa")

def arch02_componentes():
    els=[]
    els+=title("ARCH-02  Diagrama de Componentes — Modulos Python",800,14,
               "Dependencias entre modulos del backend Flask")
    comps=[
        ("app.py","Rutas y orquestacion\n/ /vinos /dashboard /admin\n/api/resenas /api/kpis",100,100,WINE_L,WINE,300,100),
        ("auth.py","Blueprint autenticacion\n/auth/login /auth/logout\nverify_password()",100,300,GREEN_L,GREEN,260,80),
        ("models.py","Usuarios StarRocks\nget_user_by_username()\ncreate/update/delete_user()",100,500,BLUE_L,BLUE,260,80),
        ("audit.py","Registro de acciones\nlog_action(usuario,accion)\nINSERT INTO auditoria",100,700,PURPLE_L,PURPLE,260,80),
        ("db_manager.py","Conexion StarRocks\nget_conn() → MySQL connector\nPool de conexiones",500,400,GOLD_L,GOLD,260,80),
        ("config.py","Configuracion\nSTARROCKS_HOST/PORT/DB\nSECRET_KEY CSV_PATH",500,600,GRAY_L,GRAY,260,60),
        ("etl/extractor.py","Extractor\nread_csv(path)\n→ pd.DataFrame",900,200,BLUE_L,BLUE,240,80),
        ("etl/transformer.py","Transformer\nnormalize(df)\n→ {dims, fact}",900,380,BLUE_L,BLUE,240,80),
        ("etl/loader.py","Loader\nload_dims(dims)\nload_fact(fact)",900,560,BLUE_L,BLUE,240,80),
        ("backup_manager.py","Respaldos\ncreate_backup()\nlist_backups()",500,200,GOLD_L,GOLD,260,80),
        ("csv_loader.py","Carga directa CSV\nload_csv_to_starrocks()\nutilidad ETL manual",900,740,GOLD_L,GOLD,240,80),
    ]
    comp_pos={}
    for name,sub,x,y,bg,st,w,h in comps:
        els+=component_box(x,y,w,h,name,sub,bg=bg,stroke=st)
        comp_pos[name]=(x+w//2,y+h//2)
    deps=[("app.py","auth.py"),("app.py","models.py"),("app.py","audit.py"),
          ("app.py","db_manager.py"),("app.py","etl/extractor.py"),
          ("app.py","etl/transformer.py"),("app.py","etl/loader.py"),
          ("app.py","backup_manager.py"),
          ("auth.py","models.py"),("auth.py","db_manager.py"),("auth.py","audit.py"),
          ("models.py","db_manager.py"),("audit.py","db_manager.py"),
          ("db_manager.py","config.py"),
          ("etl/extractor.py","config.py"),("etl/loader.py","db_manager.py"),
          ("etl/transformer.py","etl/extractor.py"),("etl/loader.py","etl/transformer.py"),
          ("backup_manager.py","db_manager.py"),("csv_loader.py","db_manager.py")]
    for src,dst in deps:
        sx,sy=comp_pos[src]; dx,dy=comp_pos[dst]
        els.append(arr(sx,sy,dx,dy,stroke=GRAY,sw=1,ss="dashed",sh=None,eh="arrow"))
    save("ARCH_02_componentes.excalidraw",els,"#fafafa")

def arch03_capas():
    els=[]
    els+=title("ARCH-03  Arquitectura por Capas",700,14,
               "Separacion de responsabilidades — Presentacion / Negocio / Datos")
    layers=[
        ("Capa de Presentacion (Frontend)","HTML5 + CSS3 + JavaScript vanilla\nJinja2 Templates | Fetch API | IntersectionObserver\nhome.html | vinos.html | index.html",
         60,100,1000,130,BLUE_L,BLUE),
        ("Capa de Aplicacion (Backend Flask)","Rutas REST: / /vinos /dashboard /admin /api/*\nAutenticacion: session Flask + bcrypt\nOrquestacion ETL | Gestion de respaldos | Auditoria",
         60,260,1000,130,WINE_L,WINE),
        ("Capa de Logica de Negocio (ETL + Modelos)","ETL Pipeline: extractor.py | transformer.py | loader.py\nModelos: models.py (usuarios) | audit.py | backup_manager.py\nValidaciones: permisos por rol | integridad de datos",
         60,420,1000,130,GOLD_L,GOLD),
        ("Capa de Datos (StarRocks OLAP + PocketBase)","StarRocks: fact_resenas (308k) + 6 dims + usuarios_sistema + auditoria\nPocketBase: Sesiones OAuth | Colecciones externas\nFileSystem: /backups/*.sql | /data/*.csv",
         60,580,1000,130,GREEN_L,GREEN),
    ]
    for lbl,desc,x,y,w,h,bg,st in layers:
        els.append(rect(x,y,w,h,bg=bg,stroke=st,sw=3,rounded=True))
        els.append(txt(lbl,x+w//2,y+10,size=15,color=st,align="center"))
        els.append(txt(desc,x+20,y+38,size=12,color="#333"))
        els.append(arr(x+w//2,y+h,x+w//2,y+h+20,stroke=GRAY,sw=2))
    # cross-cutting concerns
    els.append(rect(1100,100,200,610,bg=PURPLE_L,stroke=PURPLE,sw=2,ss="dashed",rounded=True))
    els.append(txt("Aspectos\nTransversales",1150,120,size=13,color=PURPLE,align="center"))
    for i,c in enumerate(["Auditoria","Autorizacion","Logging","Seguridad","Docker","Configuracion"]):
        els.append(rect(1110,170+i*70,180,50,bg="#fff",stroke=PURPLE,sw=1,rounded=True))
        els.append(txt(c,1150,185+i*70,size=12,color=PURPLE,align="center"))
    save("ARCH_03_capas.excalidraw",els,"#fafafa")

def arch04_navegacion():
    els=[]
    els+=title("ARCH-04  Diagrama de Navegacion — Rutas URL",800,14,
               "Flujos de navegacion por rol — publico, analista, gerente, admin")
    rutas=[
        ("/  (Landing)","home.html","Publica",200,100,WINE_L,WINE,220,60),
        ("/vinos","vinos.html","Publica",200,260,WINE_L,WINE,220,60),
        ("/vinos/:id (Fase 3)","ficha_detalle.html","Publica",200,420,WINE_L,WINE,220,60),
        ("/login","login.html","Publica",600,100,GREEN_L,GREEN,220,60),
        ("/dashboard","index.html show_admin=F","Analista/Gerente",600,260,GREEN_L,GREEN,260,60),
        ("/admin","index.html show_admin=T","Solo Admin",600,420,"#ffe8e8",WINE_D,260,60),
        ("/usuarios","usuarios.html","Solo Admin",1000,100,"#ffe8e8",WINE_D,220,60),
        ("/auditoria","auditoria.html","Solo Admin",1000,260,"#ffe8e8",WINE_D,220,60),
        ("/respaldos","respaldos.html","Solo Admin",1000,420,"#ffe8e8",WINE_D,220,60),
        ("/logout","redirect /","Sesion activa",1000,580,GRAY_L,GRAY,220,60),
        ("/api/resenas","JSON endpoint","API interna",200,580,BLUE_L,BLUE,220,60),
        ("/api/kpis","JSON endpoint","API interna",600,580,BLUE_L,BLUE,220,60),
        ("/api/browse","JSON endpoint","API interna",600,680,BLUE_L,BLUE,220,60),
        ("/api/exportar","CSV / PDF","Sesion activa",200,680,BLUE_L,BLUE,220,60),
    ]
    ruta_pos={}
    for ruta,tmpl,rol,x,y,bg,st,w,h in rutas:
        els.append(rect(x,y,w,h,bg=bg,stroke=st,sw=2,rounded=True))
        els.append(txt(ruta,x+w//2,y+8,size=12,color=st,align="center"))
        els.append(txt(f"{tmpl} | {rol}",x+6,y+30,size=9,color=GRAY))
        ruta_pos[ruta]=(x+w//2,y+h//2)
    navs=[("/  (Landing)","/vinos","click Ver Vinos"),
          ("/  (Landing)","/login","click Iniciar Sesion"),
          ("/  (Landing)","/dashboard","sesion analista/gerente"),
          ("/  (Landing)","/admin","sesion admin"),
          ("/login","/dashboard","login analista/gerente OK"),
          ("/login","/admin","login admin OK"),
          ("/vinos","/vinos/:id (Fase 3)","click vino"),
          ("/dashboard","/logout","click Salir"),
          ("/admin","/usuarios","nav link"),
          ("/admin","/auditoria","nav link"),
          ("/admin","/respaldos","nav link"),
          ("/admin","/logout","click Salir"),
          ("/usuarios","/admin","volver"),
          ("/dashboard","/api/resenas","fetch JS"),
          ("/dashboard","/api/kpis","fetch JS"),
          ("/vinos","/api/resenas","fetch JS"),
          ("/vinos","/api/browse","fetch JS")]
    for src,dst,lbl in navs:
        if src in ruta_pos and dst in ruta_pos:
            sx,sy=ruta_pos[src]; dx,dy=ruta_pos[dst]
            els.append(arr(sx,sy,dx,dy,stroke=GRAY,sw=1,ss="dashed"))
            mx=(sx+dx)//2; my=(sy+dy)//2
            els.append(txt(lbl,mx-len(lbl)*3,my-12,size=9,color=GRAY,align="center"))
    # legend
    els.append(rect(60,780,1100,60,bg=GRAY_L,stroke=GRAY,sw=1,rounded=True))
    for i,(bg,st,lbl) in enumerate([(WINE_L,WINE,"Publica (sin login)"),(GREEN_L,GREEN,"Analista / Gerente"),
        ("#ffe8e8",WINE_D,"Solo Administrador"),(BLUE_L,BLUE,"Endpoints API interna"),(GRAY_L,GRAY,"Sistema")]):
        ox=80+i*220
        els.append(rect(ox,793,30,20,bg=bg,stroke=st,sw=1,rounded=True))
        els.append(txt(lbl,ox+36,795,size=11,color=GRAY))
    save("ARCH_04_navegacion.excalidraw",els,"#fafafa")

def arch05_dfd_n0():
    els=[]
    els+=title("ARCH-05  DFD Nivel 0 — Diagrama de Contexto",700,14,
               "Flujos de datos entre el sistema y entidades externas")
    # system
    els.append(rect(400,300,320,180,bg=WINE_L,stroke=WINE,sw=3,rounded=True))
    els.append(txt("VinAnalytics Group",490,355,size=16,color=WINE_D,align="center"))
    els.append(txt("Sistema de Inteligencia",490,378,size=12,color=GRAY,align="center"))
    els.append(txt("Vitivinicola",490,398,size=12,color=GRAY,align="center"))
    # external entities (rectangles with double border)
    ext=[("Usuario\nPublico",80,160,160,80,BLUE_L,BLUE),
         ("Analista /\nGerente",80,380,160,80,GREEN_L,GREEN),
         ("Administrador",80,580,160,80,"#ffe8e8",WINE_D),
         ("Fuente CSV\nWinemag",800,160,160,80,GOLD_L,GOLD),
         ("API Externa\n(Fase 4)",800,380,160,80,PURPLE_L,PURPLE),
         ("StarRocks\nOLAP",800,580,160,80,BLUE_L,BLUE)]
    for lbl,x,y,w,h,bg,st in ext:
        els.append(rect(x,y,w,h,bg=bg,stroke=st,sw=3,rounded=False))
        els.append(rect(x+4,y+4,w-8,h-8,stroke=st,sw=1,rounded=False))
        els.append(txt(lbl,x+w//2,y+h//2-10,size=12,color=st,align="center"))
    # flows
    flows=[(160,200,400,390,"busqueda, filtros"),
           (400,440,160,420,"resultados, graficos"),
           (160,620,400,430,"login, solicitudes admin"),
           (400,440,160,620,"dashboard, reportes"),
           (800,200,720,350,"datos CSV 130k"),
           (720,350,800,200,"confirmacion carga"),
           (720,450,800,420,"respuestas API"),
           (800,420,720,450,"solicitudes API"),
           (720,450,800,620,"consultas SQL"),
           (800,620,720,450,"resultados OLAP")]
    for x1,y1,x2,y2,lbl in flows:
        els.append(arr(x1,y1,x2,y2,stroke=GRAY,sw=2))
        mx=(x1+x2)//2; my=(y1+y2)//2
        els.append(txt(lbl,mx-len(lbl)*3,my-14,size=10,color=GRAY,align="center"))
    save("ARCH_05_dfd_n0.excalidraw",els,"#fafafa")

def arch06_dfd_n1():
    els=[]
    els+=title("ARCH-06  DFD Nivel 1 — Procesos Internos",900,14,
               "Descomposicion del sistema en procesos y flujos de datos")
    procs=[("P1\nAutenticacion",200,200,180,80,GREEN_L,GREEN),
           ("P2\nGestion ETL",600,200,180,80,GOLD_L,GOLD),
           ("P3\nConsulta Vinos",200,500,180,80,BLUE_L,BLUE),
           ("P4\nDashboard / KPIs",600,500,180,80,WINE_L,WINE),
           ("P5\nAdministracion",900,350,180,80,"#ffe8e8",WINE_D),
           ("P6\nReportes (F3)",900,550,180,80,PURPLE_L,PURPLE)]
    for lbl,x,y,w,h,bg,st in procs:
        els.append(ell(x,y,w,h,bg=bg,stroke=st,sw=2))
        els.append(txt(lbl,x+w//2,y+h//2-12,size=12,color=st,align="center"))
    # data stores (open rectangles)
    stores=[("D1  StarRocks: fact_resenas + dim_*",150,740,400,40,BLUE,BLUE_L),
            ("D2  StarRocks: usuarios_sistema",150,800,400,40,GREEN,GREEN_L),
            ("D3  StarRocks: auditoria",150,860,400,40,PURPLE,PURPLE_L),
            ("D4  FileSystem: /backups/*.sql",620,740,340,40,"#8a6010",GOLD_L),
            ("D5  PocketBase: sesiones",620,800,340,40,GREEN,GREEN_L)]
    for lbl,x,y,w,h,st,bg in stores:
        els.append(rect(x,y,w,h,bg=bg,stroke=st,sw=2,rounded=False))
        els.append(line(x,y,x,y+h,stroke=st,sw=2))
        els.append(txt(lbl,x+20,y+10,size=12,color=st))
    # flows between procs and stores
    fls=[(290,280,290,500,"peticion autenticada"),
         (380,240,600,240,"usuario validado"),
         (780,240,900,390,"solicitud ETL"),
         (380,540,600,540,"datos vinos"),
         (780,540,900,550,"solicitud reporte"),
         (290,580,350,740,"leer fact_resenas"),
         (350,800,290,580,"resultado vinos"),
         (690,580,620,740,"leer datos"),
         (350,800,690,540,"usuario activo"),
         (290,500,290,740,"consulta"),
         (290,740,290,800,"datos"),
         (780,590,780,800,"generar reporte"),]
    for x1,y1,x2,y2,lbl in fls:
        els.append(arr(x1,y1,x2,y2,stroke=GRAY,sw=1,ss="dashed"))
        mx=(x1+x2)//2; my=(y1+y2)//2
        els.append(txt(lbl,mx,my-12,size=9,color=GRAY,align="center"))
    save("ARCH_06_dfd_n1.excalidraw",els,"#fafafa")

# ════════════════════════════════════════════════════════════════════════════
#  ROLES Y PERMISOS
# ════════════════════════════════════════════════════════════════════════════

def rol01_matriz():
    els=[]
    els+=title("ROL-01  Matriz de Roles y Permisos",800,14,
               "Control de acceso basado en roles (RBAC) — VinAnalytics Group")
    permisos=[
        ("Ruta / Funcionalidad","Publico","Analista","Gerente","Admin"),
        ("GET /  (Landing)","SI","SI","SI","SI"),
        ("GET /vinos  (Catalogo)","SI","SI","SI","SI"),
        ("GET /vinos/:id  (Ficha)","SI","SI","SI","SI"),
        ("Buscar y filtrar vinos","SI","SI","SI","SI"),
        ("GET /login","SI","SI","SI","SI"),
        ("POST /auth/login","SI","SI","SI","SI"),
        ("GET /logout","NO","SI","SI","SI"),
        ("GET /dashboard","NO","SI","SI","SI"),
        ("Ver KPIs y Metricas","NO","SI","SI","SI"),
        ("Ver Graficos Interactivos","NO","SI","SI","SI"),
        ("Aplicar Filtros Dashboard","NO","SI","SI","SI"),
        ("Exportar CSV","NO","SI","SI","SI"),
        ("Gestionar Favoritos (F3)","NO","SI","SI","SI"),
        ("Comparar Vinos (F3)","NO","SI","SI","SI"),
        ("Ver Tendencias por Ano","NO","NO","SI","SI"),
        ("Exportar PDF Ejecutivo (F3)","NO","NO","SI","SI"),
        ("Compartir Dashboard (F3)","NO","NO","SI","SI"),
        ("GET /admin  (Panel Admin)","NO","NO","NO","SI"),
        ("POST /etl/run  (ETL Manual)","NO","NO","NO","SI"),
        ("Programar ETL Automatico","NO","NO","NO","SI"),
        ("Cargar CSV Masivo","NO","NO","NO","SI"),
        ("GET /usuarios","NO","NO","NO","SI"),
        ("Crear / Editar Usuario","NO","NO","NO","SI"),
        ("Asignar Roles","NO","NO","NO","SI"),
        ("Eliminar Usuario","NO","NO","NO","SI"),
        ("GET /auditoria","NO","NO","NO","SI"),
        ("Exportar Log Auditoria","NO","NO","NO","SI"),
        ("GET /respaldos","NO","NO","NO","SI"),
        ("Crear Respaldo Manual","NO","NO","NO","SI"),
        ("Restaurar Respaldo (F4)","NO","NO","NO","SI"),
        ("Gestionar API Keys (F4)","NO","NO","NO","SI"),
        ("Ver Documentacion Swagger (F4)","NO","NO","NO","SI"),
    ]
    col_w=[340,110,110,110,110]; col_x=[60];
    for w in col_w[:-1]: col_x.append(col_x[-1]+w)
    row_h=30; y_start=80
    colors_header=[WINE_D,GRAY,GREEN,GOLD,WINE_D]
    # header
    for ci,(hdr,cx) in enumerate(zip(permisos[0],col_x)):
        bg=WINE_L if ci==0 else [GRAY_L,GREEN_L,GOLD_L,"#ffe8e8"][ci-1]
        st=colors_header[ci]
        els.append(rect(cx,y_start,col_w[ci],38,bg=bg,stroke=st,sw=2,rounded=False))
        els.append(txt(hdr,cx+col_w[ci]//2,y_start+8,size=12,color=st,align="center"))
    # rows
    for ri,row in enumerate(permisos[1:]):
        y=y_start+38+ri*row_h
        bg_row="#fafafa" if ri%2==0 else "#f0f0f0"
        for ci,(cell,cx) in enumerate(zip(row,col_x)):
            if ci==0:
                els.append(rect(cx,y,col_w[ci],row_h,bg=bg_row,stroke="#ddd",sw=1,rounded=False))
                els.append(txt(cell,cx+8,y+7,size=11,color="#333"))
            else:
                ok=cell=="SI"
                cbg=GREEN_L if ok else WINE_L
                cst=GREEN if ok else WINE
                els.append(rect(cx,y,col_w[ci],row_h,bg=cbg,stroke=cst,sw=1,rounded=False))
                els.append(txt(cell,cx+col_w[ci]//2,y+7,size=12,color=cst,align="center"))
    # nota
    nota_y=y_start+38+len(permisos[1:])*row_h+20
    els+=note_box(60,nota_y,820,60,
        "F3 = Fase 3 (por desarrollar) | F4 = Fase 4 (por desarrollar)\n"
        "RBAC implementado via session['rol'] en Flask — StarRocks no tiene control de acceso por fila")
    save("ROL_01_matriz_permisos.excalidraw",els,"#fafafa")

def uc00_paquetes():
    els=[]
    els+=title("DIAGRAMA DE CASOS DE USO AGRUPADO POR PAQUETES",920,12,
               "VinAnalytics Group — Sistema completo (100%) — 19 casos de uso / 5 paquetes / 4 actores")

    # ── helper: notacion UML de paquete (tab + cuerpo) ────────────────────
    def pkg_box(x,y,w,h,name,hbg,bbg):
        tab_w=min(max(len(name)*8+24,160),w); tab_h=26
        out=[]
        out.append(rect(x,y,tab_w,tab_h,bg=hbg,stroke=hbg,sw=0,rounded=False))
        out.append(txt("<<paquete>>",x+8,y+2,size=8,color="#ffffff"))
        out.append(txt(name,x+8,y+13,size=10,color="#ffffff"))
        out.append(rect(x,y+tab_h,w,h,bg=bbg,stroke=hbg,sw=2,rounded=False))
        return out

    # ── helper: ovalo de caso de uso ─────────────────────────────────────
    def cu_oval(label,cx,cy,stroke,fill,size=10):
        w=max(len(label)*6+24,148); h=38
        return [ell(cx-w//2,cy-h//2,w,h,bg=fill,stroke=stroke,sw=2),
                txt(label,cx-w//2+6,cy-9,size=size,color=stroke,align="center")]

    # ── PKG 1: Acceso Publico (VERDE) ─────────────────────────────────────
    P1x,P1y,P1w,P1h = 180,58,1440,162
    els+=pkg_box(P1x,P1y,P1w,P1h,"ACCESO PUBLICO",GREEN,GREEN_L)
    p1_cus=[("CU-01","Explorar Catalogo"),("CU-02","Buscar y Filtrar"),
             ("CU-03","Ver Detalle de Vino"),("CU-04","Estadisticas del Catalogo")]
    sp1=P1w//5
    for i,(cid,lab) in enumerate(p1_cus):
        cx=P1x+sp1*(i+1); cy=P1y+26+P1h//2+8
        els+=cu_oval(f"{cid}: {lab}",cx,cy,GREEN,GREEN_L)

    # ── PKG 2: Gestion de Sesion (VINO) ───────────────────────────────────
    P2x,P2y,P2w,P2h = 180,268,400,165
    els+=pkg_box(P2x,P2y,P2w,P2h,"GESTION DE SESION",WINE,WINE_L)
    p2_cus=[("CU-05","Iniciar Sesion"),("CU-06","Cerrar Sesion")]
    for i,(cid,lab) in enumerate(p2_cus):
        cx=P2x+P2w//3*(i+1); cy=P2y+26+P2h//2+8
        els+=cu_oval(f"{cid}: {lab}",cx,cy,WINE_D,WINE_L)

    # ── PKG 3: Analisis de Datos (AZUL) ───────────────────────────────────
    P3x,P3y,P3w,P3h = 600,268,1020,165
    els+=pkg_box(P3x,P3y,P3w,P3h,"ANALISIS DE DATOS",BLUE,BLUE_L)
    p3_cus=[("CU-07","Dashboard Analitico"),("CU-08","Filtros Avanzados"),
             ("CU-09","Generar Reporte"),("CU-10","Exportar CSV/PDF")]
    sp3=P3w//5
    for i,(cid,lab) in enumerate(p3_cus):
        cx=P3x+sp3*(i+1); cy=P3y+26+P3h//2+8
        els+=cu_oval(f"{cid}: {lab}",cx,cy,BLUE,BLUE_L)

    # ── PKG 4: Inteligencia Gerencial (ORO) ───────────────────────────────
    P4x,P4y,P4w,P4h = 180,482,800,165
    els+=pkg_box(P4x,P4y,P4w,P4h,"INTELIGENCIA GERENCIAL",GOLD,GOLD_L)
    p4_cus=[("CU-11","Dashboard Ejecutivo"),("CU-12","Comparar KPIs"),
             ("CU-13","Reporte Estrategico"),("CU-14","Tendencias de Precios")]
    sp4=P4w//5
    for i,(cid,lab) in enumerate(p4_cus):
        cx=P4x+sp4*(i+1); cy=P4y+26+P4h//2+8
        els+=cu_oval(f"{cid}: {lab}",cx,cy,"#7a5000",GOLD_L)

    # ── PKG 5: Administracion del Sistema (MORADO) ─────────────────────────
    P5x,P5y,P5w,P5h = 1000,482,620,165
    els+=pkg_box(P5x,P5y,P5w,P5h,"ADMINISTRACION DEL SISTEMA",PURPLE,PURPLE_L)
    p5_cus=[("CU-15","Gestionar Usuarios"),("CU-16","Ejecutar ETL"),
             ("CU-17","Gestionar Respaldos"),("CU-18","Log de Auditoria"),("CU-19","Monitor Sistema")]
    sp5=P5w//6
    for i,(cid,lab) in enumerate(p5_cus):
        cx=P5x+sp5*(i+1); cy=P5y+26+P5h//2+8
        els+=cu_oval(f"{cid}: {lab}",cx,cy,PURPLE,PURPLE_L,size=9)

    # ── ACTORES (stick figures laterales) ─────────────────────────────────
    A_LEFT=78; A_RIGHT=1710
    # Visitante (izq, altura PKG1)
    act_cy1=P1y+26+P1h//2
    els+=stick(A_LEFT,act_cy1-30,"Visitante\nPublico",color=GREEN,size=10)
    # Analista (izq, altura PKG3)
    act_cy3=P3y+26+P3h//2
    els+=stick(A_LEFT,act_cy3-30,"Analista",color=BLUE,size=10)
    # Gerente (der, altura PKG4)
    act_cy4=P4y+26+P4h//2
    els+=stick(A_RIGHT,act_cy4-30,"Gerente",color=GOLD,size=10)
    # Admin (der, altura PKG5)
    act_cy5=P5y+26+P5h//2
    els+=stick(A_RIGHT,act_cy5-30,"Admin",color=PURPLE,size=10)

    # ── FLECHAS actor -> paquete ───────────────────────────────────────────
    # Visitante -> PKG1
    els.append(arr(A_LEFT+22,act_cy1,P1x,act_cy1,stroke=GREEN,sw=1))
    # Analista -> PKG2 (sesion)
    els.append(arr(A_LEFT+22,P2y+26+P2h//2,P2x,P2y+26+P2h//2,stroke=WINE,sw=1))
    # Analista -> PKG3
    els.append(arr(A_LEFT+22,act_cy3,P3x,act_cy3,stroke=BLUE,sw=1))
    # Gerente -> PKG2 (sesion, dashed)
    els.append(arr(A_RIGHT-22,P2y+26+P2h//2+10,P2x+P2w,P2y+26+P2h//2+10,stroke=WINE,sw=1,ss="dashed"))
    # Gerente -> PKG4
    els.append(arr(A_RIGHT-22,act_cy4,P4x+P4w,act_cy4,stroke=GOLD,sw=1))
    # Admin -> PKG2 (sesion, dashed)
    els.append(arr(A_RIGHT-22,P2y+26+P2h//2+22,P2x+P2w,P2y+26+P2h//2+22,stroke=WINE,sw=1,ss="dashed"))
    # Admin -> PKG5
    els.append(arr(A_RIGHT-22,act_cy5,P5x+P5w,act_cy5,stroke=PURPLE,sw=1))

    # ── LEYENDA ────────────────────────────────────────────────────────────
    els+=note_box(180,695,700,52,
        "Relaciones:  ——>  acceso directo al paquete   |   - - ->  hereda acceso (requiere sesion)\n"
        "Todos los actores autenticados usan PKG 2 (Gestion de Sesion) para login y logout.")

    save("UC_00_paquetes.excalidraw",els,"#fafafa")

# ════════════════════════════════════════════════════════════════════════════
#  MAIN
# ════════════════════════════════════════════════════════════════════════════
if __name__=="__main__":
    import sys; sys.stdout.reconfigure(encoding="utf-8")
    print("\nVinAnalytics -- Generando 34 diagramas Excalidraw...\n")
    uc00_paquetes()
    uc01_general(); uc02_publico(); uc03_analista(); uc04_gerente(); uc05_admin()
    seq01_login(); seq02_logout(); seq03_catalogo(); seq04_busqueda()
    seq05_dashboard(); seq06_reportes(); seq07_etl(); seq08_usuarios()
    seq09_auditoria(); seq10_respaldos()
    db01_estrella(); db02_operacional()
    act01_etl(); act02_login(); act03_reporte(); act04_respaldo()
    est01_sesion(); est02_etl(); est03_solicitud()
    arch01_despliegue(); arch02_componentes(); arch03_capas()
    arch04_navegacion(); arch05_dfd_n0(); arch06_dfd_n1()
    rol01_matriz()
    print(f"\nOK -- 31 archivos generados en: {os.path.abspath(OUT)}")
    print("Abrir en excalidraw.com -> Menu -> Open")
