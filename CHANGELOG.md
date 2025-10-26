# CHANGELOG — rsyncx

---
---

## [0.1.8] — 2025-10-26
- Pull borra carpetas, las pasa _papelera y informa de ello para tenerlo en cuenta.

---

## [0.1.7] — 2025-10-26
- Se pone --delete de rsync al hacer push para tener en cuenta lo borrados y así trabajar entre equipos con estructura del local, lo borrado se guarda en _papelera y no se elimina hasta que el usuario quiera.

---

## [0.1.6] — 2025-10-26
- Al hacer push se descarga papelera remota para tener eliminados.
- Se quita --delete de rsync al hacer push para mantener archivos ya subidos.

---

## [0.1.5] — 2025-10-25
- Actualizado push-pull-purge para que la conexión primero prueba en local y luego en vpn.

---

## [0.1.4] — 2025-10-25
- Se configura con push & pull tipo git para que el usuario tenga el control/elección total.

---

## [0.1.3] — 2025-10-24
- Se actualiza para hacer sincronización push y pull.

---

## [0.1.2] — 2025-10-24
- Quitamos .datarsyncx
- Se actualiza a que se haga simpre un pull para descargar si existen datos nuevos y luego ya hace el push de los cambios de local.

---

## [0.1.1] — 2025-10-22
- Añadido sistema de control de sincronización con archivo .datarsyncx en cada carpeta local.Este archivo guarda el timestamp de la última sincronización y el estado del grupo.
- Implementado comportamiento inteligente de sincronización:
- Si no existe .datarsyncx → se considera primera sincronización, realiza pull completo inicial.
- En sincronizaciones normales → prevalece siempre el archivo más reciente (--update).
- Se evita poner archivos en papelera cuando la diferencia es solo por falta de sincronización inicial.
- Mejora en la detección de carpetas vacías en remoto (sin romper el flujo).
- Preparado comando CLI rsyncx time para listar los grupos y la fecha de última sincronización.
- Ajustes menores en el flujo de configure() para asegurar creación de .rsync-filter y estructura base.
- Actualización de la versión en setup.py a 0.1.1.
- Refactorización de funciones relacionadas con detección de “primera sincronización”.
- Preparación de estructura para futuras mejoras de seguimiento (JSON con timestamp y acción).
- Añadido soporte para CLI extensible (time, status, etc.).

---

## [0.1.0] — 2025-10-21
- Implementación base del CLI rsyncx:
- Comandos: configure, push, pull, run, purge.
- Sincronización local ↔ Synology con papelera versionada.
- Soporte para múltiples grupos definidos en config.py.
- Compatibilidad multiplataforma (macOS, Linux, Windows WSL).
- Inclusión de .rsync-filter global con exclusiones de sistema y entornos virtuales.
- Creación automática de estructura ~/.xsoft/rsyncx.