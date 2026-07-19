"""
Atajos de teclado GLOBALES para Windows: funcionan sin importar qué
ventana tenga el foco. Usa la librería 'keyboard', que en Windows no
necesita permisos de administrador para uso normal (algunas apps
elevadas en primer plano pueden bloquearlo, es una limitación del SO,
no de este código).

Corre como un hilo de background dentro de otro proceso que ya esté
vivo (hoy: el tray, ver tray/tray.py) — no tiene sentido como proceso
aparte porque de todos modos hace falta algo corriendo todo el tiempo
para que los atajos funcionen.

Linux queda pendiente (ver hotkeys/linux.py, todavía vacío): en Wayland
la mayoría de las libs de captura global no funcionan por seguridad del
protocolo, así que la solución ahí es distinta (atajos configurados
desde el propio compositor apuntando a la CLI, ver README). No se toca
en este archivo.
"""

import sys
import threading
import time

from core.config import get_hotkeys
from core.hotkeys import run_hotkey_action

RELOAD_INTERVAL = 5  # segundos entre chequeos de cambios en la config


def _normalize_keys(keys: str) -> str:
    """
    QKeySequenceEdit (la GUI) genera strings tipo 'Ctrl+Alt+A'. La
    librería 'keyboard' espera minúsculas y algunos nombres distintos
    para teclas especiales. Esto traduce lo más común; si aparece una
    combinación rara que no matchea, el registro de ESE atajo puntual
    falla en silencio (ver _register_all) sin tumbar a los demás.
    """
    replacements = {
        "return": "enter",
        "esc": "escape",
    }
    parts = keys.lower().split("+")
    return "+".join(replacements.get(p, p) for p in parts)


class HotkeyManager:
    """
    Mantiene registrados en 'keyboard' los atajos que hay en config.toml,
    agregando/sacando sólo lo que cambió en cada chequeo (no usa
    unhook_all_hotkeys(): esa función de la librería asume que ya se
    registró algo antes de poder "limpiar todo" y revienta si se la
    llama en el primer ciclo sin nada registrado todavía).
    """

    def __init__(self):
        self._handles: dict[str, object] = {}  # hotkey_id -> handle de keyboard.add_hotkey
        self._stop = False

    def _register_all(self):
        import keyboard  # import diferido: sólo hace falta en Windows

        current = get_hotkeys()
        current_by_id = {h["id"]: h for h in current}

        # Sacar los que ya no están en la config.
        for hotkey_id in list(self._handles.keys()):
            if hotkey_id not in current_by_id:
                try:
                    keyboard.remove_hotkey(self._handles[hotkey_id])
                except (KeyError, ValueError):
                    pass
                del self._handles[hotkey_id]

        # Agregar los que faltan (los que ya estaban registrados se dejan
        # como están, no hace falta reconstruirlos).
        for hotkey_id, hotkey in current_by_id.items():
            if hotkey_id in self._handles:
                continue
            try:
                normalized = _normalize_keys(hotkey["keys"])
                handle = keyboard.add_hotkey(normalized, run_hotkey_action, args=(hotkey,))
                self._handles[hotkey_id] = handle
            except Exception:
                # Combinación inválida o ya tomada por otra app; se
                # ignora ese atajo puntual, no debe tumbar al resto.
                continue

    def _loop(self):
        while not self._stop:
            self._register_all()
            time.sleep(RELOAD_INTERVAL)

    def start(self):
        if sys.platform != "win32":
            return  # por ahora sólo Windows, ver docstring del módulo
        threading.Thread(target=self._loop, daemon=True).start()


def start_hotkey_manager() -> HotkeyManager:
    manager = HotkeyManager()
    manager.start()
    return manager