# Spotlight-Key

Spotlight-Key es una aplicación multiplataforma (Linux/Windows) para controlar
dispositivos WiZ (focos inteligentes) directamente desde la PC, sin depender
de la app de celular ni de la nube.


## Objetivo

Ofrecer control rápido del foco WiZ desde la PC:

- Organización de focos por **habitaciones**, con control individual y
  agrupado.
- Interfaz gráfica (PySide6) con paleta negro/amarillo propia.
- Ícono en la bandeja del sistema para encendido/apagado rápido sin abrir la
  GUI, con estado visual (ícono e indicadores por foco).
- Atajos de teclado globales (Windows) configurables desde la propia GUI.
- Interfaz de línea de comandos (`spotlight-key on|off|color ...`).
- Descubrimiento automático de dispositivos en la red local.
- Control 100% local (sin nube), vía protocolo UDP directo al foco.
- Configuración persistente (focos, habitaciones, colores favoritos, atajos).
- Empaquetado como ejecutable de Windows (PyInstaller) — no requiere Python
  instalado para usarla.

## Estado

✅ Funcional para uso diario en Windows (foco de referencia probado: modelo
tunable-white, sin soporte de escenas RGB completas). Empaquetado como `.exe`
y en uso real. Pendiente: atajos de teclado en Linux (ver sección aparte),
distribución para Linux (AppImage/Flatpak).

## Arquitectura

```
spotlight-key/
├── core/               # Lógica pura: conexión al foco, config, habitaciones.
│   ├── device.py           # Wrapper sincrónico sobre pywizlight (async por dentro).
│   ├── discovery.py        # Búsqueda de focos WiZ en la red local.
│   ├── config.py           # Carga/guardado de configuración persistente.
│   ├── rooms.py             # Estado agregado de una habitación (on/off, brillo).
│   ├── presets.py           # Presets de temperatura de color ("Blanco").
│   ├── hotkeys.py           # Traduce un atajo configurado en la acción real.
│   └── resources.py         # Resuelve rutas a assets (dev y ya empaquetado).
├── cli/                # Interfaz de línea de comandos.
├── gui/                # Interfaz gráfica (PySide6): configuración y uso.
│   ├── main.py              # Pantallas: Home, Habitación, Foco, Configuración.
│   ├── theme.py              # Paleta de colores y estilos (QSS).
│   ├── workers.py            # Consultas de estado en background (QThread).
│   └── icons.py              # Carga de íconos SVG.
├── tray/               # Ícono de bandeja del sistema (multiplataforma, pystray).
├── hotkeys/            # Atajos de teclado globales, implementación por SO.
│   ├── windows.py           # Implementado (librería 'keyboard').
│   └── linux.py             # Pendiente (ver sección de atajos más abajo).
├── daemon/             # Daemon liviano por socket Unix (atajos en Linux).
└── tests/              # Tests.
```

La idea central: `core/` no sabe nada de teclado, bandeja, CLI ni GUI. Todo lo
demás (`cli/`, `gui/`, `tray/`, `hotkeys/`) consume `core/` como una librería
interna.

### Interfaz gráfica

Navegación de 3 niveles: **Home** (lista de habitaciones) → **Detalle de
habitación** (focos de esa habitación, toggle general) → **Detalle de foco**
(brillo, temperatura de color, presets de blanco con ícono, colores
favoritos guardados por el usuario). Una cuarta pantalla de **Configuración**
concentra los atajos de teclado.

Implementada con **PySide6** (Qt) por verse nativa y prolija en Windows y
Linux. Paleta propia negro cálido + amarillo,
con un resplandor sutil alrededor del ícono de cualquier foco/habitación
encendida.

### Colores favoritos

Cada foco guarda su propia lista de colores RGB elegidos por el usuario
(vía el selector de color de la GUI). Click para aplicar, click derecho para
eliminar. Pensado para no tener que buscar el mismo color dos veces.

### Nota sobre atajos de teclado

**Windows**: implementado. Se configuran desde la GUI (pantalla de
Configuración → "+ Agregar atajo"): elegís la acción (encender/apagar un
foco o una habitación, o aplicar un color favorito), el destino, y grabás la
combinación de teclas con el propio teclado. Funcionan de forma global
(sin importar qué ventana tenga el foco) mientras el **ícono de la bandeja
esté corriendo** — es el proceso que los mantiene activos en segundo plano,
así que conviene dejarlo configurado para que arranque solo con Windows
(ver sección de instalación).

**Linux**: en Wayland la mayoría de las libs de captura global no funcionan
por seguridad del protocolo. Por eso la app expone siempre una CLI — en
Wayland, el atajo "global" se configura desde el propio entorno de
escritorio (GNOME/KDE/Hyprland) apuntando a un comando de la CLI, ver más
abajo. Integrar esto a la pantalla de Configuración de la GUI queda
pendiente.

### Distribución (Windows)

Empaquetada con **PyInstaller** en dos ejecutables independientes:

- `SpotlightKey-Tray.exe` — el ícono de bandeja. Pensado para arrancar solo
  con Windows.
- `SpotlightKey.exe` — la GUI completa. Se abre bajo demanda (desde el menú
  del tray, o directamente) y se puede cerrar sin afectar al tray.

```bash
pip install pyinstaller
build.bat
```

Los ejecutables quedan en `dist\SpotlightKey-Tray\` y `dist\SpotlightKey\`.
Para que el tray arranque solo al iniciar sesión: `Win + R` → `shell:startup`
→ crear ahí un acceso directo a `SpotlightKey-Tray.exe`.

Pendiente: distribución para Linux (AppImage/Flatpak).

## Dependencias principales

- [`pywizlight`](https://github.com/sbidy/pywizlight) — comunicación con los
  focos WiZ (UDP local).
- `PySide6` — interfaz gráfica.
- `pystray` — ícono de bandeja multiplataforma.
- `keyboard` — atajos de teclado globales en Windows.
- `pyinstaller` — empaquetado como ejecutable (sólo en build, no en runtime).

## Instalación (desarrollo)

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
   `python -m cli add`).
2. Usá o adaptá el script `spotlight-key.sh` de la raíz del proyecto, que
   activa el venv y llama a la CLI.
3. Agregá los binds en tu config de Hyprland (en instalaciones con
   DankMaterialShell, normalmente en `~/.config/hypr/dms/binds.conf`;
   en una instalación estándar, en `~/.config/hypr/hyprland.conf`):
```
bind = SUPER, 1, exec, "/ruta/a/spotlight-key.sh" toggle
bind = SUPER, 2, exec, "/ruta/a/spotlight-key.sh" color 255 0 0
bind = SUPER, 3, exec, "/ruta/a/spotlight-key.sh" color 0 0 255
```

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
