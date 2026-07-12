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
├── tray/           # Ícono de bandeja del sistema (multiplataforma, pystray).
├── hotkeys/         # Atajos de teclado, implementación específica por SO.
│   ├── windows.py
│   └── linux.py
└── tests/
```

La idea central: `core/` no sabe nada de teclado, bandeja ni CLI. Todo lo
demás consume `core/` como una librería interna.

### Nota sobre atajos de teclado en Linux

En Windows los atajos globales son directos. En Linux depende del entorno:
funciona razonablemente en X11, pero en **Wayland** la mayoría de las libs de
captura global no funcionan por seguridad del protocolo. Por eso la app
expone siempre una CLI — en Wayland, el atajo "global" se configura desde
el propio entorno de escritorio (GNOME/KDE) apuntando a un comando de la CLI.

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
