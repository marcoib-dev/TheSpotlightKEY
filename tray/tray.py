"""
Ícono de bandeja del sistema para Spotlight-Key.

Pensado para el uso del día a día (ver README): encender/apagar focos
sin tener que abrir la GUI completa. La GUI queda para configuración
(habitaciones, colores favoritos, atajos de teclado, etc.), esto es
sólo control rápido.

También es responsable de mantener vivos los atajos de teclado
globales de Windows (ver hotkeys/windows.py) — necesitan algún proceso
corriendo todo el tiempo, y el tray ya cumple ese rol. Pensado para
correr solo al iniciar Windows (ver instrucciones de la carpeta de
inicio), no hace falta abrirlo a mano.

Corre su propio loop de eventos (pystray.Icon.run()), separado del de la
GUI (PySide6). Se lanza como proceso aparte: `python -m tray` en
desarrollo, o SpotlightKey-Tray.exe una vez empaquetado.
"""

import io
import subprocess
import sys
import threading
import time
from pathlib import Path

import pystray
from PIL import Image
from PySide6 import QtSvg  # noqa: F401  (fuerza el registro del plugin SVG de Qt)
from PySide6.QtCore import QBuffer, QIODevice, Qt
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import QApplication

from core.config import get_lights
from core.device import Light, LightUnreachableError
from core.resources import resource_path
from hotkeys.windows import start_hotkey_manager

ICONS_DIR = resource_path("sources", "SVG")

STATUS_REFRESH_INTERVAL = 25  # segundos entre chequeos de estado en background

# Estado de cada foco, cacheado en memoria: {light_id: bool | None}.
# None = no se consultó todavía o no respondió. Lo actualiza el hilo de
# background (_status_loop) y también cada acción de toggle, así el menú
# nunca tiene que bloquear consultando UDP en el momento de abrirse.
_status_cache: dict[str, bool | None] = {}
_status_lock = threading.Lock()

# QPixmap necesita una QApplication viva para renderizar SVG, aunque no
# vayamos a mostrar ninguna ventana. La creamos una sola vez acá.
_qt_app = QApplication.instance() or QApplication([])


def _svg_to_pil(svg_path: Path, size: int = 64) -> Image.Image:
    """
    Rasteriza un ícono .svg a una imagen PIL usando el renderizador de Qt.
    Reusa los mismos íconos que ya tiene la GUI (gui/icons.py) en vez de
    generar un placeholder o depender de una librería nueva.
    """
    pixmap = QPixmap(str(svg_path))
    pixmap = pixmap.scaled(size, size, Qt.KeepAspectRatio, Qt.SmoothTransformation)

    buffer = QBuffer()
    buffer.open(QIODevice.ReadWrite)
    pixmap.save(buffer, "PNG")
    data = bytes(buffer.data())
    buffer.close()

    return Image.open(io.BytesIO(data)).convert("RGBA")


def _refresh_status_cache():
    """Consulta todos los focos por UDP y actualiza la caché. Se corre en
    un hilo de background, nunca en el hilo del menú."""
    lights = get_lights()
    new_cache: dict[str, bool | None] = {}
    for light in lights:
        try:
            new_cache[light["id"]] = Light(light["ip"]).is_on()
        except LightUnreachableError:
            new_cache[light["id"]] = None
    with _status_lock:
        _status_cache.clear()
        _status_cache.update(new_cache)


def _build_icon_image() -> Image.Image:
    """Ícono prendido si al menos un foco está encendido según la caché;
    apagado si todos están apagados o si todavía no hay datos."""
    with _status_lock:
        any_on = any(state for state in _status_cache.values() if state)
    icon_name = "lightbulb" if any_on else "lightbulb-off"
    return _svg_to_pil(ICONS_DIR / f"{icon_name}.svg")


def _status_dot(light_id: str) -> str:
    with _status_lock:
        state = _status_cache.get(light_id)
    if state is True:
        return "●"
    if state is False:
        return "○"
    return "?"


def _toggle_light(light_data: dict):
    """
    Devuelve un callback de pystray (recibe icon, item) para un foco
    puntual. Falla en silencio si no responde: no hay una forma linda de
    mostrar un error desde el menú de bandeja sin bloquearlo; si el
    usuario necesita el detalle, lo ve al abrir la GUI.
    """
    def action(icon, item):
        light = Light(light_data["ip"])
        try:
            is_on = light.is_on()
            (light.turn_off() if is_on else light.turn_on())
            with _status_lock:
                _status_cache[light_data["id"]] = not is_on
        except LightUnreachableError:
            with _status_lock:
                _status_cache[light_data["id"]] = None

        icon.icon = _build_icon_image()
        icon.update_menu()

    return action


def _open_gui(icon, item):
    """
    En desarrollo, lanza la GUI vía el intérprete de Python del venv.
    Ya empaquetado (sys.frozen), no hay garantía de que exista un Python
    instalable en la máquina — busca el .exe de la GUI al lado del
    ejecutable del tray (dist/SpotlightKey-Tray/ y dist/SpotlightKey/
    quedan como carpetas hermanas dentro de dist/, ver build.bat).
    """
    if getattr(sys, "frozen", False):
        exe_dir = Path(sys.executable).resolve().parent
        gui_exe = exe_dir.parent / "SpotlightKey" / "SpotlightKey.exe"
        if gui_exe.exists():
            subprocess.Popen([str(gui_exe)])
            return
    subprocess.Popen([sys.executable, "-m", "gui"])


def _quit(icon, item):
    icon.stop()


def _build_menu_items():
    """
    Generador de ítems del menú. Se le pasa a pystray.Menu SIN llamarlo
    (pystray lo invoca solo cada vez que se abre el menú), así el menú
    siempre refleja los focos configurados y su último estado conocido.
    """
    lights = get_lights()

    if not lights:
        yield pystray.MenuItem("Sin focos configurados", None, enabled=False)
    else:
        for light in lights:
            label = f"{_status_dot(light['id'])}  {light.get('name') or light['ip']}"
            yield pystray.MenuItem(label, _toggle_light(light))

    yield pystray.Menu.SEPARATOR
    yield pystray.MenuItem("Abrir Spotlight-Key", _open_gui, default=True)
    yield pystray.MenuItem("Salir", _quit)


def _start_status_loop(icon: pystray.Icon):
    """
    Corre como 'setup' de pystray: arranca apenas el ícono está listo
    para mostrarse. Arranca dos cosas en paralelo:
      1. El refresco periódico del estado de los focos (ícono + menú).
      2. El listener de atajos de teclado (no-op en Linux por ahora,
         ver hotkeys/windows.py).
    """
    icon.visible = True

    def loop():
        while True:
            _refresh_status_cache()
            icon.icon = _build_icon_image()
            icon.update_menu()
            time.sleep(STATUS_REFRESH_INTERVAL)

    threading.Thread(target=loop, daemon=True).start()
    start_hotkey_manager()


def main():
    icon = pystray.Icon(
        "spotlight-key",
        icon=_build_icon_image(),  # arranca "apagado": la caché todavía está vacía
        title="Spotlight-Key",
        menu=pystray.Menu(_build_menu_items),
    )
    icon.run(setup=_start_status_loop)


if __name__ == "__main__":
    main()