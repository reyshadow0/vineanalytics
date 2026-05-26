import sys
import re

def patch_file(filepath):
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()

    # Import backup_manager
    if 'import backup_manager' not in content:
        content = content.replace('from csv_loader import reload_data', 
                                  'from csv_loader import reload_data\nimport backup_manager')

    # Add start_scheduler right after logging configuration
    scheduler_init = '''# ---------------------------------------------------------------------------
# Scheduler
# ---------------------------------------------------------------------------
backup_manager.start_scheduler()
'''
    if 'backup_manager.start_scheduler()' not in content:
        content = content.replace('app = Flask(__name__)', scheduler_init + '\napp = Flask(__name__)')

    # Insert backup endpoints before "Entry point"
    entry_point = '''# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------'''
    
    backup_endpoints = '''# ---------------------------------------------------------------------------
# GET /respaldos - Gestión de respaldos
# ---------------------------------------------------------------------------

@app.route("/respaldos", methods=["GET"])
@login_required
@admin_required
def respaldos():
    backups = backup_manager.list_backups()
    return render_template("respaldos.html", backups=backups)

@app.route("/respaldos/crear", methods=["POST"])
@login_required
@admin_required
def crear_respaldo():
    success, result = backup_manager.create_backup("manual")
    if success:
        registrar_evento(session.get("username"), session.get("rol"), "CREAR_RESPALDO", f"Respaldo manual creado: {result}", request.remote_addr)
        flash("Respaldo creado exitosamente.", "success")
    else:
        logging.error(f"Error al crear respaldo: {result}")
        flash(f"Error al crear el respaldo: {result}", "error")
    return redirect(url_for("respaldos"))

@app.route("/respaldos/restaurar", methods=["POST"])
@login_required
@admin_required
def restaurar_respaldo():
    filename = request.form.get("filename")
    if not filename:
        flash("Nombre de archivo no proporcionado.", "error")
        return redirect(url_for("respaldos"))
        
    success, result = backup_manager.restore_backup(filename)
    if success:
        registrar_evento(session.get("username"), session.get("rol"), "RESTAURAR_RESPALDO", f"Respaldo restaurado: {filename}", request.remote_addr)
        flash(f"Base de datos restaurada exitosamente desde {filename}.", "success")
    else:
        logging.error(f"Error al restaurar respaldo: {result}")
        flash(f"Error al restaurar la base de datos: {result}", "error")
    return redirect(url_for("respaldos"))

@app.route("/respaldos/eliminar", methods=["POST"])
@login_required
@admin_required
def eliminar_respaldo():
    filename = request.form.get("filename")
    if not filename:
        flash("Nombre de archivo no proporcionado.", "error")
        return redirect(url_for("respaldos"))
        
    success = backup_manager.delete_backup(filename)
    if success:
        registrar_evento(session.get("username"), session.get("rol"), "ELIMINAR_RESPALDO", f"Respaldo eliminado: {filename}", request.remote_addr)
        flash("Respaldo eliminado exitosamente.", "success")
    else:
        flash("Error al eliminar el respaldo. Puede que el archivo no exista.", "error")
    return redirect(url_for("respaldos"))

# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------'''
    
    if '/respaldos' not in content:
        content = content.replace(entry_point, backup_endpoints)

    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(content)
    print(f'Successfully patched {filepath}')

patch_file('c:/Users/erwin/OneDrive/Documentos/retailytics/app.py')
