# -*- coding: utf-8 -*-
"""
Plantilla de configuración inicial para rsyncx.
Se copia automáticamente a ~/.xsoft/rsyncx/config.py al ejecutar:
    rsyncx configure
"""

# Número de sincronizaciones simultáneas (en futuras versiones con hilos o colas)
parallel = 2

# Ruta esperada de rsync en el sistema
rsync_path = "/usr/bin/rsync"

# ---------------------------------------------------------------------
# SERVIDORES DISPONIBLES
# ---------------------------------------------------------------------
# Puedes definir tantos servidores como necesites.
# Cada grupo de sincronización (en SINCRONIZAR) hace referencia a uno de ellos.
servers = {
    "synology_local": {
        "host_local": "192.168.1.18",
        "host_vpn": "100.90.102.60",
        "port": 2354,
        "user": "rsyncx_mac",
        "remote": "/volume1/Backup/rsyncx_folder",
        "identity": "passw",         # por ahora solo 'passw'
        "passw": "<aqui_tu_pass>",
        "rsync_path": "/usr/bin/rsync"
    }
}

# ---------------------------------------------------------------------
# GRUPOS DE SINCRONIZACIÓN
# ---------------------------------------------------------------------
# Cada entrada define un conjunto local/remoto para sincronizar.
# sync -> carpeta local (expande ~)
# name_folder_backup -> nombre de la carpeta remota
# server -> referencia a la clave en 'servers'
# grupo -> nombre que usas al ejecutar rsyncx push/pull/run [grupo]
SINCRONIZAR = [
    {
        "grupo": "scripts",
        "server": "synology_local",
        "name_folder_backup": "scripts",
        "sync": "~/Desktop/Scripts"
    },
    {
        "grupo": "documentos",
        "server": "synology_local",
        "name_folder_backup": "docsBackup",
        "sync": "~/Documents/Trabajo"
    }
]