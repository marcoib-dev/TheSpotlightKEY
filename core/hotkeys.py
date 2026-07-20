"""
Ejecuta la acción asociada a un atajo de teclado configurado por el
usuario. No sabe nada de teclado en sí (eso lo maneja hotkeys/windows.py,
y más adelante hotkeys/linux.py) — sólo traduce "qué acción hacer" en
llamadas a core/device.py y core/rooms.py, reusando la misma lógica que
ya usan la GUI y el tray.
"""

import asyncio

from core.config import get_light, get_lights, get_favorite_colors
from core.device import Light, LightUnreachableError
from core.presets import WHITE_PRESETS
from core.rooms import toggle_room as toggle_room_status

BRIGHTNESS_STEP_PERCENT = 10  # ver core/device.py: Light.step_brightness


async def _turn_off_all_async() -> None:
    """
    Apaga TODOS los focos configurados, sin importar habitación (a
    diferencia de core.rooms.toggle_room, que opera sólo dentro de una
    room). En paralelo con asyncio.gather, igual que core/rooms.py: un
    foco que no responde no debe frenar al resto.
    """
    async def _off(light_data: dict):
        try:
            await Light(light_data["ip"])._turn_off()
        except LightUnreachableError:
            pass

    await asyncio.gather(*(_off(l) for l in get_lights()))


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

        elif action == "adjust_brightness":
            light_data = get_light(target_id)
            if light_data is None:
                return
            direction = hotkey.get("direction", "up")
            Light(light_data["ip"]).step_brightness(direction, BRIGHTNESS_STEP_PERCENT)

        elif action == "apply_white_preset":
            light_data = get_light(target_id)
            if light_data is None:
                return
            preset = WHITE_PRESETS.get(hotkey.get("preset_key", ""))
            if preset is None:
                return
            Light(light_data["ip"]).set_color_temp(preset["kelvin"])

        elif action == "turn_off_all":
            asyncio.run(_turn_off_all_async())

    except LightUnreachableError:
        # Un atajo de teclado no tiene forma de mostrar un error sin
        # interrumpir lo que el usuario esté haciendo en otra ventana;
        # se ignora en silencio, igual que el toggle del tray.
        pass