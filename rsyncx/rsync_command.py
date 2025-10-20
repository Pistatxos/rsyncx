# -*- coding: utf-8 -*-
import subprocess
import shlex
import os
from datetime import datetime
from pathlib import Path


RSYNC_FILTER_FILE = Path.home() / ".xsoft/rsyncx/.rsync-filter"

def build_rsync_command(server_conf, source, remote):
    port = server_conf["port"]
    user = server_conf["user"]
    host = server_conf.get("selected_host", server_conf["host_vpn"])
    password = server_conf.get("passw", "")
    identity_mode = server_conf.get("identity", "passw").strip().lower()
    identity_file = server_conf.get("file", "").strip()

    timestamp = datetime.now().strftime("%Y-%m-%d_%H%M")
    backup_dir = f"_papelera/{timestamp}"

    # Preparamos entorno
    env = os.environ.copy()

    # --- SSH base ---
    ssh_cmd = f"ssh -F /dev/null -o StrictHostKeyChecking=no -p {port}"

    # --- Modo autenticación ---
    if identity_mode == "file" and identity_file and os.path.exists(os.path.expanduser(identity_file)):
        # 🔑 Usa clave privada
        ssh_cmd += f" -i {os.path.expanduser(identity_file)}"
        print(f"🔐 Usando autenticación con clave: {identity_file}")
    else:
        # 🔒 Usa contraseña con sshpass
        env["SSHPASS"] = password
        print("🔑 Usando autenticación por contraseña (sshpass).")

    # --- Comando principal rsync ---
    cmd = [
        "sshpass", "-e",
        "rsync",
        "-avz",
        "--update",
        "--progress",
        "--partial",
        "--delete",
        "--backup",
        f"--backup-dir={backup_dir}",
        "--include", ".git/",
        "--include", ".git/**",
        "--exclude-from", str(RSYNC_FILTER_FILE),
        "--exclude", "_papelera/",
        "-e", ssh_cmd,
        f"{source}/", f"{user}@{host}:{remote}"
    ]

    return cmd, env


def run_rsync(cmd, env):
    """Ejecuta rsync con entorno seguro (sin mostrar contraseña)."""
    print(f"🚀 Ejecutando: {' '.join(shlex.quote(c) for c in cmd)}")
    try:
        result = subprocess.run(cmd, check=True, text=True, capture_output=True, env=env)
        print(result.stdout)
    except subprocess.CalledProcessError as e:
        print(f"❌ Error durante la sincronización: {e}")
        if e.stderr:
            print("Detalles del error:")
            print(e.stderr)