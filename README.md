## 🧩 rsyncx

rsyncx es un sincronizador seguro basado en rsync, diseñado para mantener tus carpetas idénticas entre varios equipos y un NAS o servidor (Synology o similar). Incluye papelera remota, protección ante borrados accidentales y soporte para múltiples grupos de sincronización.

---

## ⚙️ Instalación

Puedes instalarlo fácilmente desde pip o pipx:

```pip install rsyncx```

o bien

```pipx install rsyncx```

---

## 🧠 Configuración inicial

Ejecuta el siguiente comando para crear los archivos de configuración y filtro:

```rsyncx configure```

Esto generará en tu carpeta de usuario la estructura:

````
~/.xsoft/rsyncx/
 ├── config.py         # configuración general y grupos
 └── .rsync-filter     # exclusiones por defecto (venv, .idea, __pycache__, etc.)
````

Puedes editar config.py para definir tus grupos y servidores.
#### Ejemplo de configuración:
```
servers = {
    'default': {
        'host_local': '192.168.1.18',
        'host_vpn': '100.65.103.33',
        'port': 2908,
        'user': 'rsyncx_user',
        'remote': '/volume1/Backup/rsyncx_mac/',
        'identity': 'passw',
        'passw': '<aqui_tu_pass>'
    }
}

SINCRONIZAR = [
    {
        'grupo': 'scriptsVarios',
        'server': 'default',
        'name_folder_backup': 'scriptsmac',
        'sync': '~/Proyectos/scriptsmac/'
    },
    {
        'grupo': 'sshMac',
        'server': 'default',
        'name_folder_backup': 'sshMac',
        'sync': '~/.ssh/'
    }
]
```

---


## 🚀 Uso

🔄 Sincronización completa (push + pull)

Ejecuta el flujo completo para todos los grupos definidos en la configuración:

```rsyncx run```

Esto realiza primero un pull (descarga de cambios remotos) y luego un push (subida de cambios locales),
garantizando que siempre se descarguen los archivos nuevos antes de subir los cambios.

---

## ☁️ Subir cambios (push)

Envía los cambios locales al servidor remoto:

```rsyncx push```

O bien, para un grupo concreto:

```rsyncx push <nombre_grupo>```


#### Características:

🔁 Borra en remoto los archivos eliminados localmente (se mueven a _papelera/FECHA).

🚫 No sube la carpeta _papelera local.

🔑 Si no puede usar la clave privada, se usa automáticamente autenticación por contraseña (sshpass).


---

## 💾 Descargar cambios (pull)

Trae actualizaciones desde el servidor remoto:

```rsyncx pull```

O un grupo concreto:

```rsyncx pull <nombre_grupo>```

#### Características:

🔒 No borra archivos locales (protección ante pérdida de datos).

♻️ Sincroniza también la papelera remota (_papelera).

---

## 🧹 Limpiar papeleras

Vacía las papeleras locales y remotas sin eliminar sus carpetas:

`rsyncx purge`

Ideal tras revisiones o sincronizaciones finalizadas.

---

## 🧩 Estructura de carpetas

```
~/.xsoft/rsyncx/
│
├── config.py          # Config principal (editable)
└── .rsync-filter      # Exclusiones (se aplica a todos los grupos)
```

Cada grupo en SINCRONIZAR apunta a una carpeta local y su equivalente remoto:

```
Local:  ~/Proyectos/scriptsVarios/
Remoto: /volume1/Backup/rsyncx_mac/scriptsVarios/
```

Dentro del remoto, los archivos eliminados se guardan con versión:

```/_papelera/2025-10-17_1237/```


---

## 💡 Consejos
	•	✅ Puedes tener tantos grupos como quieras, y cada uno puede apuntar a un servidor distinto.
	•	✅ Si un host local no responde, rsyncx usa automáticamente el host VPN.
	•	✅ Puedes añadir tus exclusiones personalizadas en ~/.xsoft/rsyncx/.rsync-filter.
	•	✅ Usa rsyncx configure una sola vez por equipo para inicializar.
	•	🔒 sshpass se utiliza de forma controlada y segura mediante variables de entorno.

---

## 🧱 Requisitos
	•	Python ≥ 3.8
	•	rsync y sshpass instalados en el sistema

Instalación rápida (macOS/Linux):

```sudo apt install rsync sshpass```
o
```brew install rsync sshpass```

💡 El comando rsyncx configure intentará instalar automáticamente las dependencias si es posible.

---

## 🧾 Licencia

MIT License © 2025
Desarrollado por Mario x