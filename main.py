#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# rsyncx - CLI de sincronización segura basada en rsync (Synology + multi-equipo)
# -----------------------------------------------------------------------------
# Comandos:
#   configure  -> instala dependencias y crea ~/.xsoft/rsyncx/config.py desde rsyncx/config.dist.py
#   push       -> SUBE (local -> remoto) con papelera versionada en remoto
#   pull       -> BAJA (remoto -> local) y sincroniza también _papelera (solo pull)
#   run        -> pull + push (sin comprobaciones de estado)
#   purge      -> borra papeleras local y remota
#
# Consideraciones:
#   - La "papelera maestra" es la del Synology. La local es un espejo (solo pull).
#   - En push NO subimos la papelera local.
#   - En pull NO borramos archivos locales si no existen en remoto (protección).
#   - En pull SÍ espejamos la papelera (remota) en local.
# -----------------------------------------------------------------------------

import argparse
import os
import sys
import subprocess
import shutil
import platform
import importlib.util
import socket
from datetime import datetime, timezone
from pathlib import Path

# Import de helper de rsync (para PUSH)
from rsyncx.rsync_command import build_rsync_command, run_rsync

# -----------------------------------------------------------------------------
# Rutas base
# -----------------------------------------------------------------------------
CONFIG_DIR = Path.home() / ".xsoft" / "rsyncx"
CONFIG_PATH = CONFIG_DIR / "config.py"
PACKAGE_DIR = Path(__file__).resolve().parent
RSYNC_FILTER_FILE = CONFIG_DIR / ".rsync-filter"
CONFIG_DIST = PACKAGE_DIR / "config.dist.py"

# -----------------------------------------------------------------------------
# Utilidades generales
# -----------------------------------------------------------------------------
def print_header():
    print("rsyncx - sincronizador seguro (push/pull) con papelera remota")

def iso_now():
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")

def format_ago(when_iso: str) -> str:
    try:
        when = datetime.fromisoformat(when_iso)
    except Exception:
        return "desconocido"
    now = datetime.now(when.tzinfo or timezone.utc)
    delta = now - when
    secs = int(delta.total_seconds())
    m = secs // 60
    h = m // 60
    d = h // 24
    if secs < 60:
        return f"hace {secs} s"
    if m < 60:
        return f"hace {m} min"
    if h < 24:
        rem = m % 60
        return f"hace {h} h {rem} min" if rem else f"hace {h} h"
    remh = h % 24
    return f"hace {d} d {remh} h" if remh else f"hace {d} d"

# -----------------------------------------------------------------------------
# Configuración inicial
# -----------------------------------------------------------------------------
def ensure_config_exists():
    """Crea ~/.xsoft/rsyncx/config.py y ~/.xsoft/rsyncx/.rsync-filter si no existen."""
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)

    if not CONFIG_PATH.exists():
        if CONFIG_DIST.exists():
            shutil.copyfile(CONFIG_DIST, CONFIG_PATH)
            print(f"✔ Config creado: {CONFIG_PATH}")
        else:
            CONFIG_PATH.write_text("# Config por defecto generada automáticamente\n")
            print(f"✔ Config base generada: {CONFIG_PATH}")
    else:
        print(f"✔ Config existente: {CONFIG_PATH}")

    if not RSYNC_FILTER_FILE.exists():
        RSYNC_FILTER_FILE.write_text(
            "# Filtros globales de rsyncx\n"
            "- @eaDir/\n- .Trash*/\n- .Spotlight*/\n"
            "- __pycache__/\n- node_modules/\n"
            "- *.pyc\n- *.log\n"
        )
        print(f"✔ Filtro creado: {RSYNC_FILTER_FILE}")
    else:
        print(f"✔ Filtro existente: {RSYNC_FILTER_FILE}")

def load_config():
    if not CONFIG_PATH.exists():
        print("❌ No se encontró configuración. Ejecuta: rsyncx configure")
        sys.exit(1)
    spec = importlib.util.spec_from_file_location("rsyncx_user_config", str(CONFIG_PATH))
    config = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(config)
    return config

# -----------------------------------------------------------------------------
# Conectividad y estructura remota
# -----------------------------------------------------------------------------
def choose_reachable_host(server_conf):
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

    print("❌ No se pudo alcanzar ningún host.")
    sys.exit(1)

def ensure_remote_dirs(server_conf, host_selected, remote_root):
    env = os.environ.copy()
    env["SSHPASS"] = server_conf.get("passw", "")
    cmd = [
        "sshpass", "-e",
        "ssh", "-o", "StrictHostKeyChecking=no",
        "-p", str(server_conf["port"]),
        f"{server_conf['user']}@{host_selected}",
        f"mkdir -p '{remote_root}' '{remote_root}/_papelera'"
    ]
    try:
        subprocess.run(cmd, check=True)
        print("🧱 Estructura remota verificada correctamente.")
    except subprocess.CalledProcessError:
        print("⚠ No se pudo crear estructura remota (posible falta de permisos).")


# -----------------------------------------------------------------------------
# PUSH / PULL
# -----------------------------------------------------------------------------

def sync_push(group_conf, server_conf):
    print(f"\n🟢 SUBIENDO (push) grupo: {group_conf['grupo']}")
    local_path = Path(group_conf["sync"]).expanduser()
    remote_root = os.path.join(server_conf["remote"], group_conf["name_folder_backup"])

    host_selected = choose_reachable_host(server_conf)
    ensure_remote_dirs(server_conf, host_selected, remote_root)

    env = os.environ.copy()
    env["SSHPASS"] = server_conf.get("passw", "")

    cmd = [
        "sshpass", "-e", "rsync",
        "-avz",
        "--update",                # No sobreescribe archivos más nuevos en remoto
        "--delete",                # Borra en remoto lo que ya no existe en local
        "--backup",                # Mueve lo borrado a papelera
        "--backup-dir=_papelera",  # Carpeta de papelera remota
        "--exclude", "_papelera/",
        "--exclude-from", str(RSYNC_FILTER_FILE),
        "-e", f"ssh -o StrictHostKeyChecking=no -p {server_conf['port']}",
        f"{local_path}/",
        f"{server_conf['user']}@{host_selected}:{remote_root}/"
    ]

    print("📤 Ejecutando push con control de versiones y borrado seguro...")
    subprocess.run(cmd, check=False, env=env)


def rsync_pull_main(server_conf, host_selected, remote_root, local_path):
    """Descarga los cambios desde el servidor (solo actualiza si el remoto es más nuevo)."""
    print("🔵 Descargando (pull) contenido principal...")
    env = os.environ.copy()
    env["SSHPASS"] = server_conf.get("passw", "")

    cmd = [
        "sshpass", "-e", "rsync",
        "-avz",
        "--update",                # Solo trae archivos más nuevos o que no existen localmente
        "--exclude", "_papelera/",
        "--exclude-from", str(RSYNC_FILTER_FILE),
        "-e", f"ssh -o StrictHostKeyChecking=no -p {server_conf['port']}",
        f"{server_conf['user']}@{host_selected}:{remote_root}/",
        f"{local_path}/"
    ]

    subprocess.run(cmd, check=False, env=env)


def rsync_pull_trash(server_conf, host_selected, remote_root, local_path):
    """Espeja la papelera remota en local."""
    print("🔵 Descargando (pull) papelera remota...")
    env = os.environ.copy()
    env["SSHPASS"] = server_conf.get("passw", "")

    cmd = [
        "sshpass", "-e", "rsync",
        "-avz",
        "--update",
        "--delete",                # Mantiene sincronizada la papelera local
        "-e", f"ssh -o StrictHostKeyChecking=no -p {server_conf['port']}",
        f"{server_conf['user']}@{host_selected}:{remote_root}/_papelera/",
        f"{local_path}/_papelera/"
    ]

    subprocess.run(cmd, check=False, env=env)


def sync_pull(group_conf, server_conf):
    print(f"\n🔵 DESCARGANDO (pull) grupo: {group_conf['grupo']}")
    local_path = Path(group_conf["sync"]).expanduser()
    local_path.mkdir(parents=True, exist_ok=True)
    remote_root = os.path.join(server_conf["remote"], group_conf["name_folder_backup"])

    host_selected = choose_reachable_host(server_conf)

    rsync_pull_main(server_conf, host_selected, remote_root, local_path)
    rsync_pull_trash(server_conf, host_selected, remote_root, local_path)


def sync_run(group_conf, server_conf):
    """Sincroniza en orden seguro: primero PUSH (sube), luego PULL (trae lo nuevo)."""
    local_path = Path(group_conf["sync"]).expanduser()

    print(f"\n🔁 Ejecutando sincronización completa para '{group_conf['grupo']}'")
    print("🟩 Paso 1: subiendo cambios locales (push)...")
    sync_push(group_conf, server_conf)

    print("🟦 Paso 2: descargando cambios remotos (pull)...")
    sync_pull(group_conf, server_conf)

    print("✨ Sincronización completa (push + pull).")

# -----------------------------------------------------------------------------
# PURGE
# -----------------------------------------------------------------------------
def purge_group_trash(group_conf, server_conf):
    print(f"\n🧹 Limpiando papelera: {group_conf['grupo']}")
    local_trash = Path(group_conf["sync"]).expanduser() / "_papelera"
    if local_trash.exists():
        shutil.rmtree(local_trash, ignore_errors=True)
    local_trash.mkdir(parents=True, exist_ok=True)

    host = choose_reachable_host(server_conf)
    remote_trash = os.path.join(server_conf["remote"], group_conf["name_folder_backup"], "_papelera")
    cmd = [
        "sshpass", "-p", server_conf["passw"],
        "ssh", "-o", "StrictHostKeyChecking=no",
        "-p", str(server_conf["port"]),
        f"{server_conf['user']}@{host}",
        f"rm -rf {remote_trash}/*"
    ]
    subprocess.run(cmd, check=False)
    print("✅ Papelera local y remota vaciadas.")

def purge_all(config):
    for g in config.SINCRONIZAR:
        purge_group_trash(g, config.servers[g["server"]])
    print("\n✅ Papeleras limpiadas (local y remota).")

# -----------------------------------------------------------------------------
# CLI
# -----------------------------------------------------------------------------
def build_arg_parser():
    parser = argparse.ArgumentParser(description="rsyncx - sincronizador seguro basado en rsync")
    sub = parser.add_subparsers(dest="command")
    sub.add_parser("configure", help="Prepara entorno y configuración inicial")
    for cmd, desc in [
        ("push", "Sube cambios locales (local → remoto)"),
        ("pull", "Descarga cambios remotos (remoto → local)"),
        ("run", "Ejecuta pull + push"),
        ("purge", "Limpia papeleras local y remota")
    ]:
        p = sub.add_parser(cmd, help=desc)
        p.add_argument("grupo", nargs="?", help="Nombre del grupo a sincronizar")
    return parser

def main():
    if len(sys.argv) == 1:
        print_header()
        print("Uso: rsyncx [configure|push|pull|run|purge]")
        return 0

    parser = build_arg_parser()
    args = parser.parse_args()

    if args.command == "configure":
        ensure_config_exists()
        return 0

    ensure_config_exists()
    config = load_config()

    if getattr(args, "grupo", None):
        grupos = [g for g in config.SINCRONIZAR if g["grupo"] == args.grupo]
        if not grupos:
            print(f"❌ Grupo '{args.grupo}' no encontrado.")
            return 1
    else:
        grupos = config.SINCRONIZAR

    for g in grupos:
        server_conf = config.servers[g["server"]]
        if args.command == "push":
            sync_push(g, server_conf)
        elif args.command == "pull":
            sync_pull(g, server_conf)
        elif args.command == "run":
            sync_run(g, server_conf)
        elif args.command == "purge":
            purge_group_trash(g, server_conf)

    print(f"\n✔ Comando '{args.command}' ejecutado correctamente.")
    return 0

if __name__ == "__main__":
    sys.exit(main())