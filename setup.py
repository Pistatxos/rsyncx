from setuptools import setup, find_packages
from pathlib import Path
import os

def post_install():
    base_dir = Path.home() / ".xsoft" / "rsyncx"
    base_dir.mkdir(parents=True, exist_ok=True)

    config_file = base_dir / "config.py"
    if not config_file.exists():
        config_file.write_text('''# -*- coding: utf-8 -*-
# Configuración de ejemplo para rsyncx

parallel = 2
rsync_path = "/usr/bin/rsync"

servers = {
    "synology": {
        "host_local": "192.168.1.18",
        "host_vpn": "100.90.102.60",
        "port": 2354,
        "user": "rsyncx_mac",
        "remote": "/volume1/Backup/rsyncx_folder/",
        "identity": "passw",
        "file": "",
        "passw": "<aqui_tu_pass>",
    }
}

SINCRONIZAR = [
    {
        "grupo": "scripts",
        "server": "synology",
        "name_folder_backup": "scripts",
        "sync": "/Users/usuario/Desktop/Scripts/"
    },
]
''')

    ignore_file = base_dir / ".rsync-filter"
    if not ignore_file.exists():
        ignore_file.write_text('''*.log
# Filtros globales de rsyncx
# Formato rsync-filter:
# - Excluir => "- pattern"
# + Incluir => "+ pattern"

# Carpetas del sistema y ocultas
- @eaDir/
- .Trash*/
- .Spotlight*/
- .fseventsd/
- .TemporaryItems/
- .cache/
- .idea/
- **/.idea/

# Carpetas de entornos virtuales
- venv/
- **/venv/
- VENV/
- **/VENV/
- menv/
- **/menv/

# Carpetas de compilación y temporales
- __pycache__/
- **/__pycache__/
- node_modules/
- **/node_modules/
- dist/
- **/dist/
- build/
- **/build/

# Archivos temporales y de sistema
- .DS_Store
- Thumbs.db
- *.pyc
- *.pyo
- *.tmp
- *.swp
- *.swo
- *.log
- @eaDir
''')

post_install()

setup(
    name="rsyncx",
    version="0.1.5",
    author="Mario x",
    description="Sincronizador seguro basado en rsync con control de papelera y multi-equipo",
    packages=find_packages(),
    entry_points={
        "console_scripts": [
            "rsyncx=rsyncx.main:main",
        ],
    },
    python_requires=">=3.8",
)