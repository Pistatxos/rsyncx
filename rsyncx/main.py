#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# rsyncx - Sincronización segura (Synology + multi-equipo) con propagación de borrados
# -----------------------------------------------------------------------------
# Comandos:
#   configure  -> crea ~/.xsoft/rsyncx/ (config, filtros, state/, deleted/)
#   push       -> SUBE (local -> remoto) con papelera versionada y marcadores de borrado
#   pull       -> BAJA (remoto -> local), aplica borrados (mueve a _papelera) y trae cambios
#   run        -> pull + push (orden seguro)
#   purge      -> borra papeleras local y remota
# -----------------------------------------------------------------------------

import argparse
import os
import sys
import subprocess
import shutil
import importlib.util
import socket
import json
from pathlib import Path
from datetime import datetime, timezone

# -----------------------------------------------------------------------------
# Rutas base (config + estado)
# -----------------------------------------------------------------------------
CONFIG_DIR = Path.home() / ".xsoft" / "rsyncx"
CONFIG_PATH = CONFIG_DIR / "config.py"
RSYNC_FILTER_FILE = CONFIG_DIR / ".rsync-filter"
STATE_DIR = CONFIG_DIR / "state"
DELETED_DIR = CONFIG_DIR / "deleted"

# Marcadores de borrado en servidor
DELETED_MARKER_EXT = ".rsyncx_deleted"

# -----------------------------------------------------------------------------
# Utilidades varias
# -----------------------------------------------------------------------------
def print_header():
    print("rsyncx - sincronizador seguro (pull/push) con papelera y borrados propagados")

def iso_now():
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")

def safe_group_id(group_conf):
    """ID seguro de grupo para ficheros de estado (por nombre de grupo)."""
    name = group_conf.get("grupo", "default")
    # slug simple
    return "".join(ch if ch.isalnum() or ch in ("-", "_") else "_" for ch in name)

def load_config():
    if not CONFIG_PATH.exists():
        print("❌ No se encontró configuración. Ejecuta: rsyncx configure")
        sys.exit(1)
    spec = importlib.util.spec_from_file_location("rsyncx_user_config", str(CONFIG_PATH))
    config = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(config)
    return config

def ensure_config_exists():
    """Crea estructura ~/.xsoft/rsyncx/ mínima (config, filtros, state/, deleted/)."""
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    DELETED_DIR.mkdir(parents=True, exist_ok=True)

    if not CONFIG_PATH.exists():
        CONFIG_PATH.write_text(
            "# rsyncx config\n\n"
            "servers = {\n"
            "    'default': {\n"
            "        'host_local': '192.168.1.2',\n"
            "        'host_vpn': '',\n"
            "        'port': 22,\n"
            "        'user': 'rsyncx_user',\n"
            "        'remote': '/volume1/devBackup/rsyncx_default/',\n"
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
        print(f"✔ Config creado: {CONFIG_PATH}")
    else:
        print(f"✔ Config existente: {CONFIG_PATH}")

    if not RSYNC_FILTER_FILE.exists():
        RSYNC_FILTER_FILE.write_text(
            "# Filtros globales de rsyncx\n"
            "# (formato rsync-filter: '- pattern' excluye, '+ pattern' incluye)\n"
            "- @eaDir/\n"
            "- .Trash*/\n"
            "- .Spotlight*/\n"
            "- .fseventsd/\n"
            "- .TemporaryItems/\n"
            "- .cache/\n"
            "- .idea/\n"
            "- **/.idea/\n"
            "- venv/\n"
            "- **/venv/\n"
            "- VENV/\n"
            "- **/VENV/\n"
            "- menv/\n"
            "- **/menv/\n"
            "- __pycache__/\n"
            "- **/__pycache__/\n"
            "- node_modules/\n"
            "- **/node_modules/\n"
            "- dist/\n"
            "- **/dist/\n"
            "- build/\n"
            "- **/build/\n"
            "- .DS_Store\n"
            "- Thumbs.db\n"
            "- *.pyc\n"
            "- *.pyo\n"
            "- *.tmp\n"
            "- *.swp\n"
            "- *.swo\n"
            "- *.log\n"
        )
        print(f"✔ Filtro creado: {RSYNC_FILTER_FILE}")
    else:
        print(f"✔ Filtro existente: {RSYNC_FILTER_FILE}")


def ensure_remote_papelera(server_conf, remote_path):
    """
    Crea la carpeta _papelera en el remoto si no existe.
    Usa la contraseña o la clave SSH según la configuración.
    """
    user = server_conf["user"]
    host = server_conf.get("host_local") or server_conf.get("host_vpn")
    port = server_conf["port"]
    passw = server_conf.get("passw")
    identity = server_conf.get("identity")
    remote_papelera = f"{remote_path.rstrip('/')}/_papelera"

    print(f"🧩 Verificando carpeta remota _papelera en {host}...")

    if not host:
        print("⚠ No hay host definido (ni local ni VPN) para crear _papelera.")
        return False

    if identity and identity != "passw":
        # Con clave privada
        cmd = [
            "ssh", "-p", str(port), "-i", identity,
            f"{user}@{host}",
            f"mkdir -p '{remote_papelera}'"
        ]
    else:
        # Con contraseña (sshpass)
        cmd = [
            "sshpass", "-p", passw,
            "ssh", "-p", str(port),
            f"{user}@{host}",
            f"mkdir -p '{remote_papelera}'"
        ]

    try:
        subprocess.run(cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        print("📁 Carpeta _papelera verificada o creada correctamente.")
    except subprocess.CalledProcessError as e:
        print(f"⚠ No se pudo crear/verificar _papelera: {e.stderr.decode().strip()}")

# -----------------------------------------------------------------------------
# Red / remoto
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
    print("❌ No se pudo alcanzar ningún host (host_local/host_vpn).")
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
        subprocess.run(cmd, check=True, env=env)
        print("🧱 Estructura remota verificada correctamente.")
    except subprocess.CalledProcessError:
        print("⚠ No se pudo crear/verificar estructura remota (posible falta de permisos).")

# -----------------------------------------------------------------------------
# Estado y borrados (local y marcadores en servidor)
# -----------------------------------------------------------------------------
def state_file_for_group(group_conf):
    return STATE_DIR / f"{safe_group_id(group_conf)}.json"

def deleted_log_for_group(group_conf):
    return DELETED_DIR / f"{safe_group_id(group_conf)}.json"

def read_state(group_conf):
    p = state_file_for_group(group_conf)
    if p.exists():
        try:
            return json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            return {}
    return {}

def write_state(group_conf, files_snapshot):
    p = state_file_for_group(group_conf)
    data = {
        "timestamp": iso_now(),
        "files": sorted(files_snapshot),
    }
    try:
        p.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception as e:
        print(f"⚠ No se pudo escribir estado: {p} -> {e}")

def append_deleted_log(group_conf, deleted_list):
    if not deleted_list:
        return
    p = deleted_log_for_group(group_conf)
    history = []
    if p.exists():
        try:
            history = json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            history = []
    entry = {
        "timestamp": iso_now(),
        "deleted": sorted(deleted_list),
    }
    history.append(entry)
    try:
        p.write_text(json.dumps(history, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception as e:
        print(f"⚠ No se pudo actualizar log de borrados: {p} -> {e}")

def list_current_local_files(local_path: Path):
    out = []
    for item in local_path.rglob("*"):
        if item.is_file():
            # ignorar control y papelera
            if "_papelera" in item.parts:
                continue
            if item.name.endswith(DELETED_MARKER_EXT):
                continue
            if item.name.startswith(".rsyncx_"):
                continue
            out.append(str(item.relative_to(local_path)))
    return out

def create_deletion_marker(server_conf, host, remote_root, relative_file):
    """Crea un marcador *en el servidor* para propagar el borrado a otros equipos."""
    env = os.environ.copy()
    env["SSHPASS"] = server_conf.get("passw", "")
    marker_path = f"{remote_root}/{relative_file}{DELETED_MARKER_EXT}"
    cmd = [
        "sshpass", "-e",
        "ssh", "-o", "StrictHostKeyChecking=no",
        "-p", str(server_conf["port"]),
        f"{server_conf['user']}@{host}",
        # Crear directorio y tocar marcador con timestamp
        f"mkdir -p \"$(dirname '{marker_path}')\" && date -Is > '{marker_path}'"
    ]
    subprocess.run(cmd, check=False, env=env)

def get_deletion_markers(server_conf, host, remote_root):
    """Devuelve lista de rutas relativas (con respecto a remote_root) marcadas como borradas en servidor."""
    env = os.environ.copy()
    env["SSHPASS"] = server_conf.get("passw", "")
    cmd = [
        "sshpass", "-e",
        "ssh", "-o", "StrictHostKeyChecking=no",
        "-p", str(server_conf["port"]),
        f"{server_conf['user']}@{host}",
        f"find '{remote_root}' -type f -name '*{DELETED_MARKER_EXT}' -print"
    ]
    try:
        res = subprocess.run(cmd, capture_output=True, text=True, check=True, env=env)
        lines = [l.strip() for l in res.stdout.splitlines() if l.strip()]
        out = []
        prefix = remote_root.rstrip("/") + "/"
        for abs_marker in lines:
            if abs_marker.startswith(prefix):
                rel_marker = abs_marker[len(prefix):]
            else:
                rel_marker = abs_marker
            rel_file = rel_marker[:-len(DELETED_MARKER_EXT)]
            out.append(rel_file)
        return out
    except subprocess.CalledProcessError:
        return []

def apply_deletion_markers_locally(local_path: Path, rel_files):
    """Mueve a _papelera los archivos locales listados en rel_files (si existen)."""
    if not rel_files:
        return 0
    moved = 0
    trash_root = local_path / "_papelera"
    for rel in rel_files:
        src = local_path / rel
        if src.exists() and src.is_file():
            dst_dir = trash_root / Path(rel).parent
            dst_dir.mkdir(parents=True, exist_ok=True)
            # renombrar con timestamp para no sobrescribir
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            stem = src.stem
            suff = src.suffix
            dst = dst_dir / f"{stem}_{ts}{suff}"
            try:
                shutil.move(str(src), str(dst))
                moved += 1
            except Exception:
                pass
    return moved

# -----------------------------------------------------------------------------
# PUSH (marca borrados + sube cambios con backup y delete seguro)
# -----------------------------------------------------------------------------
def sync_push(group_conf, server_conf):
    print(f"\n🟢 SUBIENDO (push) grupo: {group_conf['grupo']}")
    local_path = Path(group_conf["sync"]).expanduser()
    remote_root = os.path.join(server_conf["remote"], group_conf["name_folder_backup"])
    host = choose_reachable_host(server_conf)
    ensure_remote_papelera(server_conf, remote_root)
    ensure_remote_dirs(server_conf, host, remote_root)

    # --- Detectar borrados locales respecto al último estado y crear marcadores en servidor
    prev = set(read_state(group_conf).get("files", []))
    cur = set(list_current_local_files(local_path))
    deleted_locally = sorted(prev - cur) if prev else []
    if deleted_locally:
        print(f"📝 Borrados locales detectados: {len(deleted_locally)} (se crearán marcadores y el push los moverá a papelera remota)")
        for rel in deleted_locally:
            create_deletion_marker(server_conf, host, remote_root, rel)
        append_deleted_log(group_conf, deleted_locally)

    # --- Push (con delete + backup a _papelera) y filtros adecuados
    env = os.environ.copy()
    env["SSHPASS"] = server_conf.get("passw", "")
    cmd = [
        "sshpass", "-e", "rsync",
        "-avz",
        "--update",                    # no pisa más nuevos en remoto
        "--delete",                    # lo que no está en local, se borra en remoto...
        "--backup",                    # ...pero va a _papelera
        "--backup-dir=_papelera",
        "--exclude", "_papelera/",
        "--exclude", f"*{DELETED_MARKER_EXT}",
        "--exclude", ".rsyncx_*.json",
        "--exclude-from", str(RSYNC_FILTER_FILE),
        "-e", f"ssh -o StrictHostKeyChecking=no -p {server_conf['port']}",
        f"{local_path}/",
        f"{server_conf['user']}@{host}:{remote_root}/"
    ]
    print("📤 Ejecutando rsync (push)...")
    subprocess.run(cmd, check=False, env=env)

    # --- Guardar snapshot actual tras push
    write_state(group_conf, cur)

# -----------------------------------------------------------------------------
# PULL (aplica marcadores de borrado + trae cambios + espeja papelera)
# -----------------------------------------------------------------------------
def rsync_pull_main(server_conf, host, remote_root, local_path):
    env = os.environ.copy()
    env["SSHPASS"] = server_conf.get("passw", "")
    cmd = [
        "sshpass", "-e", "rsync",
        "-avz",
        "--update",                    # trae nuevos o más nuevos
        "--exclude", "_papelera/",
        "--exclude", f"*{DELETED_MARKER_EXT}",
        "--exclude", ".rsyncx_*.json",
        "--exclude-from", str(RSYNC_FILTER_FILE),
        "-e", f"ssh -o StrictHostKeyChecking=no -p {server_conf['port']}",
        f"{server_conf['user']}@{host}:{remote_root}/",
        f"{local_path}/"
    ]
    print("📥 Ejecutando rsync (pull contenido)...")
    subprocess.run(cmd, check=False, env=env)

def rsync_pull_trash(server_conf, host, remote_root, local_path):
    env = os.environ.copy()
    env["SSHPASS"] = server_conf.get("passw", "")
    cmd = [
        "sshpass", "-e", "rsync",
        "-avz",
        "--update",
        "--delete",                    # espejo de _papelera
        "-e", f"ssh -o StrictHostKeyChecking=no -p {server_conf['port']}",
        f"{server_conf['user']}@{host}:{remote_root}/_papelera/",
        f"{local_path}/_papelera/"
    ]
    print("🗑  Espejando papelera...")
    subprocess.run(cmd, check=False, env=env)

def sync_pull(group_conf, server_conf):
    print(f"\n🔵 DESCARGANDO (pull) grupo: {group_conf['grupo']}")
    local_path = Path(group_conf["sync"]).expanduser()
    local_path.mkdir(parents=True, exist_ok=True)
    remote_root = os.path.join(server_conf["remote"], group_conf["name_folder_backup"])
    host = choose_reachable_host(server_conf)

    ensure_remote_papelera(server_conf, remote_root)

    # 1) leer marcadores en servidor y aplicar borrados localmente
    markers = get_deletion_markers(server_conf, host, remote_root)
    if markers:
        moved = apply_deletion_markers_locally(local_path, markers)
        if moved:
            print(f"🗑  Aplicados {moved} borrados (movidos a _papelera).")

    # 2) traer contenido normal (sin _papelera)
    rsync_pull_main(server_conf, host, remote_root, local_path)

    # 3) espejo de _papelera
    rsync_pull_trash(server_conf, host, remote_root, local_path)

    # 4) snapshot de estado tras pull
    cur = set(list_current_local_files(local_path))
    write_state(group_conf, cur)

# -----------------------------------------------------------------------------
# RUN (orden seguro: pull -> push)
# -----------------------------------------------------------------------------
def sync_run(group_conf, server_conf):
    print(f"\n🔁 Ejecutando sincronización completa (pull → push) para '{group_conf['grupo']}'")
    remote_path = f"{server_conf['remote'].rstrip('/')}/{group_conf['name_folder_backup']}"
    ensure_remote_papelera(server_conf, remote_path) 
    sync_pull(group_conf, server_conf)
    sync_push(group_conf, server_conf)
    print("✨ Sincronización completa (pull + push).")

# -----------------------------------------------------------------------------
# PURGE (limpiar papelera local y remota)
# -----------------------------------------------------------------------------
def purge_group_trash(group_conf, server_conf):
    print(f"\n🧹 Limpiando papelera: {group_conf['grupo']}")
    local_trash = Path(group_conf["sync"]).expanduser() / "_papelera"
    if local_trash.exists():
        shutil.rmtree(local_trash, ignore_errors=True)
    local_trash.mkdir(parents=True, exist_ok=True)

    host = choose_reachable_host(server_conf)
    remote_trash = os.path.join(server_conf["remote"], group_conf["name_folder_backup"], "_papelera")
    env = os.environ.copy()
    env["SSHPASS"] = server_conf.get("passw", "")
    cmd = [
        "sshpass", "-e",
        "ssh", "-o", "StrictHostKeyChecking=no",
        "-p", str(server_conf["port"]),
        f"{server_conf['user']}@{host}",
        f"find '{remote_trash}' -mindepth 1 -exec rm -rf {{}} +"
    ]
    subprocess.run(cmd, check=False, env=env)
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
        ("push", "Sube cambios locales (marca borrados y usa _papelera en remoto)"),
        ("pull", "Descarga cambios, aplica borrados y espeja _papelera"),
        ("run",  "Sincroniza en orden seguro: pull → push"),
        ("purge","Limpia papeleras local y remota")
    ]:
        p = sub.add_parser(cmd, help=desc)
        p.add_argument("grupo", nargs="?", help="Nombre del grupo a sincronizar")
    return parser

def main():
    if len(sys.argv) == 1:
        print_header()
        print("Uso: rsyncx [configure|push|pull|run|purge] [grupo]")
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