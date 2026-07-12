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

## Uso

_(pendiente, se documentará a medida que exista la CLI)_

## Licencia

Por definir.
