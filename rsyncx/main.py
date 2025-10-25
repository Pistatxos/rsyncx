#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# rsyncx - Sincronizador tipo Git con papelera versionada (modular)
# -----------------------------------------------------------------------------
# Comandos:
#   configure  -> crea ~/.xsoft/rsyncx/config.py y filtros
#   push       -> SUBE (local → remoto) moviendo lo borrado a _papelera remota
#   pull       -> BAJA (remoto → local) moviendo lo borrado a _papelera local
#   purge      -> limpia papeleras local y remota
#   grupos     -> muestra los grupos configurados
# -----------------------------------------------------------------------------

import argparse
import os
import sys
import subprocess
import shutil
import socket
from datetime import datetime
from pathlib import Path
import importlib.util

# Import del módulo de comandos rsync
from rsyncx.rsync_command import build_rsync_command, run_rsync

# -----------------------------------------------------------------------------
# Rutas base
# -----------------------------------------------------------------------------
CONFIG_DIR = Path.home() / ".xsoft" / "rsyncx"
CONFIG_PATH = CONFIG_DIR / "config.py"
RSYNC_FILTER_FILE = CONFIG_DIR / ".rsync-filter"

# -----------------------------------------------------------------------------
# Utilidades generales
# -----------------------------------------------------------------------------
def print_header():
    print("rsyncx - sincronizador tipo Git con papelera versionada\n")

def iso_now():
    return datetime.now().strftime("%Y-%m-%d_%H-%M-%S")

def ensure_config_exists():
    """Crea config.py y .rsync-filter si no existen."""
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)

    if not CONFIG_PATH.exists():
        CONFIG_PATH.write_text(
            "# Config básica de rsyncx\n"
            "servers = {\n"
            "  'default': {\n"
            "    'host_local': '192.168.1.2',\n"
            "    'host_vpn': '',\n"
            "    'port': 22,\n"
            "    'user': 'usuario',\n"
            "    'passw': 'contraseña',\n"
            "    'remote': '/volume1/backups/rsyncx_default'\n"
            "  }\n"
            "}\n\n"
            "SINCRONIZAR = [\n"
            "  {\n"
            "    'grupo': 'ejemplo',\n"
            "    'server': 'default',\n"
            "    'name_folder_backup': 'carpetaEjemplo',\n"
            "    'sync': '~/Documentos/ejemplo'\n"
            "  }\n"
            "]\n"
        )
        print(f"✔ Config creada: {CONFIG_PATH}")
    else:
        print(f"✔ Config existente: {CONFIG_PATH}")

    if not RSYNC_FILTER_FILE.exists():
        RSYNC_FILTER_FILE.write_text(
            "# Filtros globales de rsyncx\n"
            "- @eaDir/\n"
            "- .Trash*/\n"
            "- .Spotlight*/\n"
            "- **/__pycache__/\n"
            "- **/venv/\n"
            "- **/VENV/\n"
            "- **/.xsoft/\n"
            "- **/node_modules/\n"
            "- *.pyc\n"
            "- *.log\n"
            "- *.egg-info/\n"
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

def choose_reachable_host(server_conf):
    """Devuelve el host accesible (local o VPN)."""
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
    print("❌ No se pudo alcanzar ningún host (local ni VPN).")
    sys.exit(1)

def ensure_remote_dirs(server_conf, host, remote_root):
    """Asegura que existan las carpetas base y _papelera en remoto."""
    env = os.environ.copy()
    env["SSHPASS"] = server_conf.get("passw", "")
    cmd = [
        "sshpass", "-e",
        "ssh", "-o", "StrictHostKeyChecking=no",
        "-p", str(server_conf["port"]),
        f"{server_conf['user']}@{host}",
        f"mkdir -p '{remote_root}' '{remote_root}/_papelera'"
    ]
    try:
        subprocess.run(cmd, check=True, env=env)
        print("📁 Estructura remota verificada.")
    except subprocess.CalledProcessError:
        print("⚠ No se pudo crear/verificar estructura remota (posible falta de permisos).")

# -----------------------------------------------------------------------------
# PUSH (local → remoto)
# -----------------------------------------------------------------------------
def sync_push(group_conf, server_conf):
    print(f"\n🟢 SUBIENDO (push) grupo: {group_conf['grupo']}")
    local_path = Path(group_conf["sync"]).expanduser()
    remote_root = os.path.join(server_conf["remote"], group_conf["name_folder_backup"])

    # Detecta y guarda el host correcto (local primero, luego VPN)
    host = choose_reachable_host(server_conf)
    server_conf["selected_host"] = host
    ensure_remote_dirs(server_conf, host, remote_root)

    cmd, env = build_rsync_command(server_conf, str(local_path), remote_root)    
    run_rsync(cmd, env)
    print(f"✨ Push completo ({group_conf['grupo']}).")

# -----------------------------------------------------------------------------
# PULL (remoto → local)
# -----------------------------------------------------------------------------
def sync_pull(group_conf, server_conf):
    print(f"\n🔵 DESCARGANDO (pull) grupo: {group_conf['grupo']}")
    local_path = Path(group_conf["sync"]).expanduser()
    local_path.mkdir(parents=True, exist_ok=True)
    remote_root = os.path.join(server_conf["remote"], group_conf["name_folder_backup"])

    # Detecta y guarda el host correcto (local primero, luego VPN)
    host = choose_reachable_host(server_conf)
    server_conf["selected_host"] = host
    ensure_remote_dirs(server_conf, host, remote_root)

    fecha = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    env = os.environ.copy()
    env["SSHPASS"] = server_conf.get("passw", "")

    cmd = [
        "sshpass", "-e", "rsync",
        "-avz",
        "--update",
        "--backup",
        f"--backup-dir=_papelera/{fecha}",
        "--exclude", "_papelera/",
        "--exclude", ".xsoft/",
        "--exclude-from", str(RSYNC_FILTER_FILE),
        "-e", f"ssh -o StrictHostKeyChecking=no -p {server_conf['port']}",
        f"{server_conf['user']}@{host}:{remote_root}/",
        f"{local_path}/"
    ]
    run_rsync(cmd, env)
    print(f"✨ Pull completo ({group_conf['grupo']}).")

# -----------------------------------------------------------------------------
# PURGE (limpia papeleras)
# -----------------------------------------------------------------------------
def purge_group_trash(group_conf, server_conf):
    print(f"\n🧹 Limpiando papeleras para: {group_conf['grupo']}")

    # 🗑 Limpia papelera local
    local_trash = Path(group_conf["sync"]).expanduser() / "_papelera"
    if local_trash.exists():
        shutil.rmtree(local_trash, ignore_errors=True)
    local_trash.mkdir(parents=True, exist_ok=True)

    # 🌐 Detecta y guarda el host correcto (local primero, luego VPN)
    host = choose_reachable_host(server_conf)
    server_conf["selected_host"] = host

    # 💾 Limpia papelera remota
    remote_trash = os.path.join(
        server_conf["remote"],
        group_conf["name_folder_backup"],
        "_papelera"
    )

    env = os.environ.copy()
    env["SSHPASS"] = server_conf.get("passw", "")

    cmd = [
        "sshpass", "-e",
        "ssh", "-p", str(server_conf["port"]),
        f"{server_conf['user']}@{host}",
        f"rm -rf '{remote_trash}'/*"
    ]

    try:
        subprocess.run(cmd, check=True, env=env)
        print("✅ Papelera local y remota vaciadas correctamente.")
    except subprocess.CalledProcessError:
        print("⚠ No se pudo limpiar la papelera remota (posibles permisos insuficientes).")

# -----------------------------------------------------------------------------
# CLI
# -----------------------------------------------------------------------------
def build_arg_parser():
    parser = argparse.ArgumentParser(description="rsyncx - sincronizador tipo Git")
    sub = parser.add_subparsers(dest="command")
    sub.add_parser("configure", help="Crea configuración inicial (~/.xsoft/rsyncx)")
    sub.add_parser("grupos", help="Muestra los grupos configurados")
    for cmd, desc in [
        ("push", "Sube cambios locales (local → remoto)"),
        ("pull", "Descarga cambios remotos (remoto → local)"),
        ("purge", "Limpia papeleras local y remota")
    ]:
        p = sub.add_parser(cmd, help=desc)
        p.add_argument("grupo", nargs="?", help="Nombre del grupo a sincronizar")
    return parser

def seleccionar_grupos(config):
    """Menú interactivo para elegir grupo o todos."""
    print("\n📁 Selecciona el grupo a sincronizar:")
    for i, g in enumerate(config.SINCRONIZAR, start=1):
        print(f" {i}. {g['grupo']} → {g['sync']}")
    print(" 0. Todos")

    try:
        choice = int(input("👉 Opción: ").strip() or "0")
    except ValueError:
        print("❌ Opción inválida.")
        return []

    if choice == 0:
        return config.SINCRONIZAR
    elif 1 <= choice <= len(config.SINCRONIZAR):
        return [config.SINCRONIZAR[choice - 1]]
    else:
        print("❌ Opción fuera de rango.")
        return []

def main():
    if len(sys.argv) == 1:
        print_header()
        print("Uso: rsyncx [configure|grupos|push|pull|purge] [grupo]")
        return 0

    parser = build_arg_parser()
    args = parser.parse_args()

    if args.command == "configure":
        ensure_config_exists()
        return 0

    ensure_config_exists()
    config = load_config()

    if args.command == "grupos":
        print("\n📁 Grupos configurados:")
        for i, g in enumerate(config.SINCRONIZAR, start=1):
            print(f" {i}. {g['grupo']} → {g['sync']}")
        print()
        return 0

    # Interactivo para push, pull o purge
    if args.command in ("push", "pull", "purge") and not getattr(args, "grupo", None):
        grupos = seleccionar_grupos(config)
        if not grupos:
            return 1
    else:
        grupos = (
            [g for g in config.SINCRONIZAR if g["grupo"] == args.grupo]
            if getattr(args, "grupo", None)
            else config.SINCRONIZAR
        )

    if not grupos:
        print(f"❌ Grupo '{args.grupo}' no encontrado.")
        return 1

    for g in grupos:
        server_conf = config.servers[g["server"]]
        if args.command == "push":
            sync_push(g, server_conf)
        elif args.command == "pull":
            sync_pull(g, server_conf)
        elif args.command == "purge":
            purge_group_trash(g, server_conf)

    print(f"\n✔ Comando '{args.command}' ejecutado correctamente.")
    return 0

if __name__ == "__main__":
    sys.exit(main())