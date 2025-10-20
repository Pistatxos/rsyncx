#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# rsyncx - CLI de sincronización segura basada en rsync (Synology + multi-equipo)
# -----------------------------------------------------------------------------
# Comandos:
#   configure  -> instala dependencias y crea ~/.xsoft/rsyncx/config.py desde rsyncx/config.dist.py
#   push       -> SUBE (local -> remoto) con papelera versionada en remoto
#   pull       -> BAJA (remoto -> local) y sincroniza también _papelera (solo pull)
#   run        -> push + pull
#   purge      -> borra papeleras local y remota
#
# Consideraciones:
#   - La "papelera maestra" es la del Synology. La local es un espejo (solo pull).
#   - En push NO subimos la papelera local.
#   - En pull NO borramos archivos locales si no existen en remoto (protección).
#   - En pull SÍ espejamos la papelera (remota) en local.
#   - Si no hay args, mostramos ayuda (igual que -h/--help).
# -----------------------------------------------------------------------------

import argparse
import os
import sys
import subprocess
import shutil
import platform
import importlib.util
import socket
from pathlib import Path

# Import de nuestro helper de rsync (para PUSH). PON EL IMPORT PAQUETIZADO.
from rsyncx.rsync_command import build_rsync_command, run_rsync

# Rutas fijas del proyecto/config
CONFIG_DIR = Path.home() / ".xsoft" / "rsyncx"
CONFIG_PATH = CONFIG_DIR / "config.py"
PACKAGE_DIR = Path(__file__).resolve().parent     # .rsync-filter vive dentro del paquete
RSYNC_FILTER_FILE = Path.home() / ".xsoft/rsyncx/.rsync-filter"
CONFIG_DIST = PACKAGE_DIR / "config.dist.py" # plantilla incluida en el paquete


# -----------------------------------------------------------------------------
# Utilidades genéricas
# -----------------------------------------------------------------------------

def print_header():
    print("rsyncx - sincronizador seguro (push/pull) con papelera remota")


def ensure_config_exists():
    """Crea ~/.xsoft/rsyncx/config.py y ~/.xsoft/rsyncx/.rsync-filter si no existen, desde los ficheros del paquete."""
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)

    # --- CONFIG PRINCIPAL ---
    if not CONFIG_PATH.exists():
        if CONFIG_DIST.exists():
            shutil.copyfile(CONFIG_DIST, CONFIG_PATH)
            print(f"✔ Config creado: {CONFIG_PATH}")
        else:
            CONFIG_PATH.write_text(
                "# Config de ejemplo para rsyncx\n\n"
                "parallel = 2\n"
                "rsync_path = '/usr/bin/rsync'\n\n"
                "servers = {\n"
                "    'default': {\n"
                "        'host_local': '192.168.1.185',\n"
                "        'host_vpn': '100.95.203.63',\n"
                "        'port': 2908,\n"
                "        'user': 'rsyncx_user',\n"
                "        'remote': '/volume1/devBackup/rsyncx_mac/',\n"
                "        'identity': 'passw',\n"
                "        'file': '',\n"
                "        'passw': 'cambia_esto'\n"
                "    }\n"
                "}\n\n"
                "SINCRONIZAR = [\n"
                "    {\n"
                "        'grupo': 'ejemplo',\n"
                "        'server': 'default',\n"
                "        'name_folder_backup': 'carpetaEjemplo',\n"
                "        'sync': '~/rsyncx_demo/'\n"
                "    }\n"
                "]\n"
            )
            print(f"✔ Config de emergencia generado: {CONFIG_PATH}")
    else:
        print(f"✔ Config existente: {CONFIG_PATH}")

    # --- FILTRO RSYNC ---
    FILTER_PATH = CONFIG_DIR / ".rsync-filter"
    if not FILTER_PATH.exists():
        FILTER_PATH.write_text(
            "# Filtros globales de rsyncx\n"
            "# Formato rsync-filter:\n"
            "# - Excluir => \"- pattern\"\n"
            "# + Incluir => \"+ pattern\"\n\n"
            "# Carpetas del sistema y ocultas\n"
            "- @eaDir/\n"
            "- .Trash*/\n"
            "- .Spotlight*/\n"
            "- .fseventsd/\n"
            "- .TemporaryItems/\n"
            "- .cache/\n"
            "- .idea/\n"
            "- **/.idea/\n\n"
            "# Carpetas de entornos virtuales\n"
            "- venv/\n"
            "- **/venv/\n"
            "- VENV/\n"
            "- **/VENV/\n"
            "- menv/\n"
            "- **/menv/\n\n"
            "# Carpetas de compilación y temporales\n"
            "- __pycache__/\n"
            "- **/__pycache__/\n"
            "- node_modules/\n"
            "- **/node_modules/\n"
            "- dist/\n"
            "- **/dist/\n"
            "- build/\n"
            "- **/build/\n\n"
            "# Archivos temporales y de sistema\n"
            "- .DS_Store\n"
            "- Thumbs.db\n"
            "- *.pyc\n"
            "- *.pyo\n"
            "- *.tmp\n"
            "- *.swp\n"
            "- *.swo\n"
            "- *.log\n"
            "- @eaDir\n"
        )
        print(f"✔ Filtro creado: {FILTER_PATH}")
    else:
        print(f"✔ Filtro existente: {FILTER_PATH}")


def load_config():
    """Carga ~/.xsoft/rsyncx/config.py como módulo."""
    if not CONFIG_PATH.exists():
        print("❌ No se encontró configuración. Ejecuta: rsyncx configure")
        sys.exit(1)
    spec = importlib.util.spec_from_file_location("rsyncx_user_config", str(CONFIG_PATH))
    config = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(config)
    return config


def install_if_missing(pkg):
    """Instala (si es posible) un paquete del SO (rsync, sshpass) en macOS/Linux. En otros SO, solo avisa."""
    print(f"• comprobando {pkg}...")
    if shutil.which(pkg):
        print(f"  ✔ {pkg} ya está instalado.")
        return True

    system = platform.system().lower()
    if "darwin" in system:
        # macOS
        if shutil.which("brew"):
            print(f"  ➜ instalando {pkg} con Homebrew...")
            os.system(f"brew install {pkg}")
            ok = shutil.which(pkg) is not None
            print("  ✔ ok" if ok else "  ✖ fallo")
            return ok
        else:
            print(f"  ✖ Homebrew no encontrado. Instala {pkg} manualmente: https://brew.sh/")
            return False
    elif "linux" in system:
        print(f"  ➜ intentando apt/dnf para {pkg}...")
        rc = os.system(f"sudo apt-get install -y {pkg} || sudo dnf install -y {pkg}")
        ok = (rc == 0) and shutil.which(pkg)
        print("  ✔ ok" if ok else "  ✖ fallo")
        return bool(ok)
    else:
        print(f"  ✖ instalación automática no soportada en {system}. Instala {pkg} manualmente.")
        return False


def configure():
    """Instala dependencias (en lo posible) y crea el config desde la plantilla del paquete."""
    print_header()
    print("⚙ Preparando entorno (configure)...")

    ensure_config_exists()

    print("\n🔍 Comprobando dependencias del sistema...")
    rsync_ok = install_if_missing("rsync")
    sshpass_ok = install_if_missing("sshpass")

    if rsync_ok and sshpass_ok:
        print("✔ Todas las dependencias necesarias están disponibles.")
    else:
        print("⚠ Algunas dependencias faltan. Revisa manualmente su instalación.")

    print("\n✔ Configuración inicial lista. Edita si hace falta:")
    print(f"  {CONFIG_PATH}")


def choose_reachable_host(server_conf):
    """
    Devuelve host accesible (local o VPN) probando un socket al puerto configurado.
    """
    local_host = server_conf.get("host_local")
    vpn_host = server_conf.get("host_vpn")
    port = int(server_conf.get("port", 22))

    if local_host:
        try:
            with socket.create_connection((local_host, port), timeout=1):
                print(f"🌐 Usando host local: {local_host}")
                return local_host
        except Exception:
            pass

    if vpn_host:
        print(f"🛰 Usando host VPN: {vpn_host}")
        return vpn_host

    print("❌ No hay host_local ni host_vpn definido en el server.")
    sys.exit(1)


def ensure_remote_dirs(server_conf, host_selected, remote_root):
    """
    Verifica o crea la estructura remota (_papelera incluida) usando sshpass -e
    con entorno explícito (corrige fallos en macOS).
    """
    env = os.environ.copy()
    env["SSHPASS"] = server_conf.get("passw", "")

    cmd = [
        "sshpass", "-e",
        "ssh", "-o", "StrictHostKeyChecking=no",
        "-p", str(server_conf["port"]),
        f"{server_conf['user']}@{host_selected}",
        f"mkdir -p '{remote_root}' '{remote_root}/_papelera'"
    ]

    print(f"🛠 Verificando estructura remota ({host_selected})...")
    try:
        result = subprocess.run(cmd, check=True, text=True, capture_output=True, env=env)
        if result.stdout.strip():
            print(result.stdout.strip())
        print("🧱 Estructura remota verificada correctamente.")
    except subprocess.CalledProcessError as e:
        stderr = (e.stderr or "").strip().lower()

        # Si fue un fallo de clave privada, no mostramos mensaje técnico
        if "permission denied" in stderr or "please try again" in stderr:
            # Silencio total: simplemente dejamos que el siguiente paso use sshpass
            pass
        else:
            # Otros errores sí deben mostrarse
            print(f"⚠ No se pudo asegurar la estructura remota: {e.stderr.strip() if e.stderr else e}")


def is_remote_empty(server_conf, host_selected, remote_root):
    """
    Devuelve True si la carpeta remota está vacía (primera sincronización),
    False si tiene contenido. Si no podemos saberlo, devolvemos False (comportamiento conservador).
    """
    passw = server_conf.get("passw", "")
    cmd = [
        "sshpass", "-p", passw,
        "ssh", "-o", "StrictHostKeyChecking=no",
        "-p", str(server_conf["port"]),
        f"{server_conf['user']}@{host_selected}",
        f"bash -lc \"shopt -s dotglob nullglob 2>/dev/null; "
        f"items=({remote_root}/*); "
        f"if [ -e \\\"$remote_root\\\" ] && [ ! -e \\\"${{items[0]}}\\\" ]; then echo EMPTY; else echo NONEMPTY; fi\""
    ]
    try:
        out = subprocess.check_output(" ".join(cmd), shell=True, text=True).strip()
        return (out == "EMPTY")
    except Exception:
        return False


# -----------------------------------------------------------------------------
# PUSH: local -> remoto (papelera versionada en remoto)
# -----------------------------------------------------------------------------

def sync_push(group_conf, server_conf):
    print(f"\n🟢 SUBIENDO (push) grupo: {group_conf['grupo']}")
    local_path = Path(group_conf["sync"]).expanduser()
    remote_root = os.path.join(server_conf["remote"], group_conf["name_folder_backup"])

    host_selected = choose_reachable_host(server_conf)
    ensure_remote_dirs(server_conf, host_selected, remote_root)

    # Pasamos el host elegido al server_conf para que lo use build_rsync_command
    server_conf = dict(server_conf)
    server_conf["selected_host"] = host_selected

    # Comando de subida (usa build_rsync_command de rsync_command.py)
    # - incluye --delete + --backup + --backup-dir=_papelera/FECHA
    # - excluye "_papelera/" para no recursar
    cmd, env = build_rsync_command(server_conf, str(local_path), remote_root)
 
    # Si el remoto está vacío, igualmente no habrá nada que "delete" (no rompe nada).
    # Ejecutamos
    run_rsync(cmd, env)   


# -----------------------------------------------------------------------------
# PULL: remoto -> local (trae cambios y _papelera; NO borra local)
# -----------------------------------------------------------------------------

def rsync_pull_main(server_conf, host_selected, remote_root, local_path):
    """
    Pull del contenido principal: queremos traer archivos nuevos/actualizados
    SIN borrar los que solo existan en local (protección).
    """
    passw = server_conf.get("passw", "")
    ssh_e = f"ssh -o StrictHostKeyChecking=no -p {server_conf['port']}"
    src = f"{server_conf['user']}@{host_selected}:{remote_root}/"
    dst = f"{str(local_path)}/"

    # OJO: aquí NO usamos --delete ni --backup (no queremos borrar local en pull)
    cmd = [
        "sshpass", "-p", passw,
        "rsync",
        "-avz",
        "--update",
        "--progress",
        "--partial",
        "--exclude-from", str(RSYNC_FILTER_FILE),  # aplica tu .rsync-filter
        "--exclude", "_papelera/",
        "-e", ssh_e,
        src, dst
    ]
    print("🔵 Descargando (pull) contenido principal...")
    try:
        subprocess.run(cmd, check=True)
    except subprocess.CalledProcessError as e:
        print(f"❌ Error en pull (main): {e}")


def rsync_pull_trash(server_conf, host_selected, remote_root, local_path):
    """
    Descarga la papelera remota si existe.
    Si no existe, lo ignora sin marcar error.
    """
    print("🔵 Descargando (pull) papelera remota...")
    cmd = [
        "sshpass", "-p", server_conf["passw"],
        "rsync", "-avz", "--update", "--progress", "--partial", "--delete",
        "-e", f"ssh -o StrictHostKeyChecking=no -p {server_conf['port']}",
        f"{server_conf['user']}@{host_selected}:{remote_root}/_papelera/",
        f"{local_path}/_papelera/"
    ]

    try:
        subprocess.run(cmd, check=True, text=True, capture_output=True)
    except subprocess.CalledProcessError as e:
        stderr = e.stderr or ""
        if "No such file or directory" in stderr or "No such file" in stderr:
            print("🗑 No hay papelera remota. Se creará automáticamente al subir archivos borrados.")
        else:
            print(f"⚠ Error en pull (trash): {stderr.strip()}")


def sync_pull(group_conf, server_conf):
    print(f"\n🔵 DESCARGANDO (pull) grupo: {group_conf['grupo']}")
    local_path = Path(group_conf["sync"]).expanduser()
    local_path.mkdir(parents=True, exist_ok=True)
    remote_root = os.path.join(server_conf["remote"], group_conf["name_folder_backup"])

    host_selected = choose_reachable_host(server_conf)
    # pull principal (no borra local) + pull de papelera (sí espejo)
    rsync_pull_main(server_conf, host_selected, remote_root, local_path)
    rsync_pull_trash(server_conf, host_selected, remote_root, local_path)


# -----------------------------------------------------------------------------
# RUN: push + pull
# -----------------------------------------------------------------------------

def sync_run(group_conf, server_conf):
    sync_push(group_conf, server_conf)
    sync_pull(group_conf, server_conf)
    print("✨ Sincronización completa (push + pull).")


# -----------------------------------------------------------------------------
# PURGE: limpia papeleras local y remota
# -----------------------------------------------------------------------------

def purge_group_trash(group_conf, server_conf):
    print(f"\n🧹 Limpiando papelera: {group_conf['grupo']}")
    local_trash = Path(group_conf["sync"]).expanduser() / "_papelera"
    if local_trash.exists():
        try:
            shutil.rmtree(local_trash)
            print(f"  ✔ Papelera local vaciada: {local_trash}")
        except Exception as e:
            print(f"  ⚠ No se pudo limpiar papelera local: {e}")
    local_trash.mkdir(parents=True, exist_ok=True)

    # Remota
    host = choose_reachable_host(server_conf)
    remote_trash = os.path.join(server_conf["remote"], group_conf["name_folder_backup"], "_papelera")
    passw = server_conf.get("passw", "")
    cmd = [
        "sshpass", "-p", passw,
        "ssh", "-o", "StrictHostKeyChecking=no",
        "-p", str(server_conf["port"]),
        f"{server_conf['user']}@{host}",
        f"find {remote_trash} -mindepth 1 -exec rm -rf {{}} +"
    ]
    try:
        subprocess.run(cmd, check=True)
        print(f"  ✔ Papelera remota vaciada: {remote_trash}")
    except subprocess.CalledProcessError as e:
        print(f"  ⚠ No se pudo limpiar papelera remota: {e}")


def purge_all(config):
    for g in config.SINCRONIZAR:
        purge_group_trash(g, config.servers[g["server"]])
    print("\n✅ Papeleras limpiadas (local y remota).")


# -----------------------------------------------------------------------------
# CLI
# -----------------------------------------------------------------------------

def build_arg_parser():
    parser = argparse.ArgumentParser(
        description="rsyncx - sincronizador seguro basado en rsync",
        add_help=True
    )
    sub = parser.add_subparsers(dest="command")

    # configure
    sub.add_parser("configure", help="Instala dependencias y crea el archivo de configuración")

    # push
    p_push = sub.add_parser("push", help="Sube cambios (local -> remoto) con papelera versionada en remoto")
    p_push.add_argument("grupo", nargs="?", help="Nombre del grupo a sincronizar (opcional). Si se omite, todos.")

    # pull
    p_pull = sub.add_parser("pull", help="Descarga cambios (remoto -> local) y sincroniza la papelera remota")
    p_pull.add_argument("grupo", nargs="?", help="Nombre del grupo a sincronizar (opcional). Si se omite, todos.")

    # run
    p_run = sub.add_parser("run", help="Ejecuta push y luego pull")
    p_run.add_argument("grupo", nargs="?", help="Nombre del grupo a sincronizar (opcional). Si se omite, todos.")

    # purge
    sub.add_parser("purge", help="Limpia papelera local y remota de todos los grupos")

    return parser


def print_usage_examples():
    print("""
Uso:
  rsyncx configure
  rsyncx push [grupo]
  rsyncx pull [grupo]
  rsyncx run  [grupo]
  rsyncx purge

Ejemplos:
  rsyncx configure
  rsyncx push                # sube todos los grupos
  rsyncx push nombreGrupo    # sube solo ese grupo
  rsyncx pull                # descarga todos los grupos (incluye papelera remota)
  rsyncx run                 # push + pull
  rsyncx purge               # limpia papeleras (local y remota)
""")


def main():
    # Si no hay argumentos, mostramos ayuda breve
    if len(sys.argv) == 1:
        print_header()
        print_usage_examples()
        return 0

    parser = build_arg_parser()
    args = parser.parse_args()

    if args.command == "configure":
        configure()
        return 0

    # Para el resto de comandos necesitamos config cargada
    ensure_config_exists()
    config = load_config()

    # Resolver grupos
    if getattr(args, "grupo", None):
        grupos = [g for g in config.SINCRONIZAR if g["grupo"] == args.grupo]
        if not grupos:
            print(f"❌ Grupo '{args.grupo}' no encontrado en config.")
            return 1
    else:
        grupos = list(config.SINCRONIZAR)

    if args.command == "push":
        for g in grupos:
            server_conf = config.servers[g["server"]]
            sync_push(g, server_conf)
        print("\n✔ push terminado.")
        return 0

    if args.command == "pull":
        for g in grupos:
            server_conf = config.servers[g["server"]]
            sync_pull(g, server_conf)
        print("\n✔ pull terminado.")
        return 0

    if args.command == "run":
        for g in grupos:
            server_conf = config.servers[g["server"]]
            sync_run(g, server_conf)
        print("\n✔ run terminado.")
        return 0

    if args.command == "purge":
        purge_all(config)
        return 0

    # Si cae aquí, mostramos ayuda
    print_usage_examples()
    return 0


if __name__ == "__main__":
    sys.exit(main())