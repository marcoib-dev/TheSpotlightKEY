"""
Ejecuta la acción asociada a un atajo de teclado configurado por el
usuario. No sabe nada de teclado en sí (eso lo maneja hotkeys/windows.py,
y más adelante hotkeys/linux.py) — sólo traduce "qué acción hacer" en
llamadas a core/device.py y core/rooms.py, reusando la misma lógica que
ya usan la GUI y el tray.
"""

from core.config import get_light, get_favorite_colors
from core.device import Light, LightUnreachableError
from core.rooms import toggle_room as toggle_room_status


def run_hotkey_action(hotkey: dict) -> None:
    action = hotkey.get("action")
    target_id = hotkey.get("target_id")

    try:
        if action == "toggle_light":
            light_data = get_light(target_id)
            if light_data is None:
                return
            light = Light(light_data["ip"])
            (light.turn_off() if light.is_on() else light.turn_on())

        elif action == "toggle_room":
            toggle_room_status(target_id)

        elif action == "apply_favorite_color":
            light_data = get_light(target_id)
            if light_data is None:
                return
            favorites = get_favorite_colors(target_id)
            index = hotkey.get("favorite_index", -1)
            if 0 <= index < len(favorites):
                color = favorites[index]
                Light(light_data["ip"]).set_color(color["r"], color["g"], color["b"])

    except LightUnreachableError:
        # Un atajo de teclado no tiene forma de mostrar un error sin
        # interrumpir lo que el usuario esté haciendo en otra ventana;
        # se ignora en silencio, igual que el toggle del tray.
        pass
