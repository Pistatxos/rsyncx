# CHANGELOG — rsyncx

---
---

## [0.1.5] — 2025-10-25
- Se añade creación de papelera si no existe.

---

## [0.1.4] — 2025-10-25
- Se añaden los archivos de estado (state.json) y registro de borrados (deleted.json) para cada grupo de sincronización.
- Se crean automáticamente las carpetas ~/.xsoft/rsyncx/state/ y ~/.xsoft/rsyncx/deleted/ durante la configuración inicial (rsyncx configure).
- Cada grupo mantiene su propio archivo de estado en state/<grupo>.json, con la lista de archivos sincronizados y su timestamp de última actualización.
- Los borrados locales ahora se registran en deleted/<grupo>.json, permitiendo un historial seguro y auditable de archivos eliminados.
- Se garantiza compatibilidad total con sincronizaciones previas: si no existen los nuevos archivos de estado, se crean sin afectar al contenido existente.
- Se mantiene el flujo normal de sincronización (pull, push, run, purge), integrando los nuevos archivos de forma transparente.

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