# Spotlight-Key

Spotlight-Key es una aplicación multiplataforma (Linux/Windows) para controlar
dispositivos WiZ (focos inteligentes) directamente desde la PC, sin depender
de la app de celular ni de la nube.

Reinicio del proyecto original (2024), esta vez con una arquitectura más
prolija: la lógica de control del foco vive separada de la interfaz (CLI,
bandeja del sistema, atajos de teclado), para que cada parte se pueda
desarrollar y testear de forma independiente.

## Objetivo

Ofrecer control rápido del foco WiZ desde la PC:

- Encendido/apagado y ajuste de color/brillo mediante atajos de teclado.
- Interfaz de línea de comandos (`spotlight-key on|off|color ...`).
- Ícono en la bandeja del sistema para acceso rápido.
- Descubrimiento automático de dispositivos en la red local.
- Control 100% local (sin nube), vía protocolo UDP directo al foco.
- Configuración persistente (IP del foco, atajos, etc.).

## Estado

🚧 En etapa temprana de desarrollo (reinicio desde cero).

## Arquitectura

```
spotlight-key/
├── core/           # Lógica pura: conexión al foco, descubrimiento, config.
│   ├── device.py       # Wrapper sincrónico sobre pywizlight (async por dentro).
│   ├── discovery.py    # Búsqueda de focos WiZ en la red local.
│   └── config.py       # Carga/guardado de configuración persistente.
├── cli/            # Interfaz de línea de comandos.
├── gui/            # Interfaz gráfica (PySide6) para configuración, pensada
│                   # para usuarios no programadores.
├── tray/           # Ícono de bandeja del sistema (multiplataforma, pystray).
├── hotkeys/         # Atajos de teclado, implementación específica por SO.
│   ├── windows.py
│   └── linux.py
└── tests/          # Tests.
```

La idea central: `core/` no sabe nada de teclado, bandeja, CLI ni GUI. Todo lo
demás (`cli/`, `gui/`, `tray/`, `hotkeys/`) consume `core/` como una librería
interna.

### Interfaz gráfica

Pensada para usuarios no técnicos. Se usa para configuración (buscar y
agregar el foco, asignar atajos de teclado, elegir colores favoritos), no
para el uso diario — eso lo cubren el ícono de bandeja y los atajos de
teclado una vez configurado.

Implementada con **PySide6** (Qt) por verse nativa y prolija en Windows y
Linux.

### Nota sobre atajos de teclado en Linux

En Windows los atajos globales son directos. En Linux depende del entorno:
funciona razonablemente en X11, pero en **Wayland** la mayoría de las libs de
captura global no funcionan por seguridad del protocolo. Por eso la app
expone siempre una CLI — en Wayland, el atajo "global" se configura desde
el propio entorno de escritorio (GNOME/KDE) apuntando a un comando de la CLI.

### Distribución

Para que usuarios no programadores puedan usarla sin instalar Python ni
dependencias, la app se empaquetará como ejecutable con **PyInstaller**
(y eventualmente AppImage/Flatpak para Linux). Pendiente de implementar.

## Dependencias principales

- [`pywizlight`](https://github.com/sbidy/pywizlight) — comunicación con los
  focos WiZ (UDP local).
- `pystray` — ícono de bandeja multiplataforma.
- Atajos de teclado: por definir según SO (ver nota arriba).

## Instalación

_(pendiente — el proyecto todavía no tiene un paquete instalable)_

```bash
git clone <repo>
cd spotlight-key
python -m venv .venv
source .venv/bin/activate  # En Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

## Atajos de teclado (Linux / Hyprland)

En Hyprland no hace falta ninguna librería de captura de teclado: los
atajos se configuran directamente en la config del compositor, apuntando
a la CLI de la app.

1. Asegurate de tener el foco ya configurado (`python -m cli discover` y
   `python -m cli set-ip <IP>`).
2. Usá o adaptá el script `spotlight-key.sh` de la raíz del proyecto, que
   activa el venv y llama a la CLI.
3. Agregá los binds en tu config de Hyprland (en instalaciones con
   DankMaterialShell, normalmente en `~/.config/hypr/dms/binds.conf`;
   en una instalación estándar, en `~/.config/hypr/hyprland.conf`):
bind = SUPER, 1, exec, "/ruta/a/spotlight-key.sh" toggle
bind = SUPER, 2, exec, "/ruta/a/spotlight-key.sh" color 255 0 0
bind = SUPER, 3, exec, "/ruta/a/spotlight-key.sh" color 0 0 255

   **Importante:** si la ruta del proyecto tiene espacios, hay que
   encerrarla entre comillas dobles dentro del bind, o Hyprland corta el
   comando en el espacio y no ejecuta nada.

4. `hyprctl reload` para aplicar los cambios.

En GNOME/KDE (X11 o Wayland) el mecanismo es distinto: se configuran los
atajos desde la configuración de "Atajos de teclado personalizados" del
propio entorno, apuntando también al script. Pendiente de documentar en
detalle.

## Daemon en background (Linux / systemd)

Para que los atajos de teclado respondan instantáneamente (sin pagar el
costo de arrancar Python en cada uno), la app corre un daemon liviano
que escucha comandos por un socket Unix.

1. Copiá el archivo de servicio:
```bash
   mkdir -p ~/.config/systemd/user
   cp spotlight-key.service.example ~/.config/systemd/user/spotlight-key.service
```
2. Editá las rutas dentro del archivo para que apunten a tu instalación.
3. Activalo:
```bash
   systemctl --user daemon-reload
   systemctl --user enable --now spotlight-key.service
```

Los atajos de teclado (ver sección de arriba) deben apuntar a
`spotlight-key-client.sh` en vez de `spotlight-key.sh` para aprovechar
el daemon.

## Licencia

Por definir.
