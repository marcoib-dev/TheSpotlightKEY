"""
Estado agregado de una Habitación (Room): combina el estado individual
de todos los focos que le pertenecen.

Consultar el estado de un foco por UDP puede tardar hasta
core.device.DEFAULT_TIMEOUT segundos si no responde. Para no sumar esos
tiempos foco por foco cuando una room tiene varios focos, las consultas
se hacen en paralelo con asyncio.gather en vez de una por una.
"""

import asyncio

from core.config import get_lights_in_room
from core.device import Light, LightUnreachableError


async def _get_light_state(light_data: dict) -> tuple[str, bool | None, int | None]:
    """
    Devuelve (light_id, is_on, brightness).
    is_on=None significa que el foco no respondió (LightUnreachableError),
    igual que ya hace LightStatusWorker en gui/workers.py para focos sueltos.
    """
    light = Light(light_data["ip"])
    try:
        state = await light._get_state()
    except LightUnreachableError:
        return light_data["id"], None, None

    if state is None:
        return light_data["id"], None, None

    is_on = state.get_state()
    brightness = Light._safe_state_read(state, "get_brightness")
    return light_data["id"], is_on, brightness


async def _get_room_state_async(room_id: str) -> dict:
    lights = get_lights_in_room(room_id)
    if not lights:
        return {"is_on": False, "avg_brightness": None, "lights": {}}

    results = await asyncio.gather(*(_get_light_state(l) for l in lights))

    per_light = {
        light_id: {"is_on": is_on, "brightness": brightness}
        for light_id, is_on, brightness in results
    }

    # Sólo cuentan para "está encendida" los focos que respondieron y están
    # prendidos. Uno que no responde no cuenta ni como prendido ni como
    # apagado: simplemente no aporta información.
    any_on = any(is_on for (_id, is_on, _b) in results if is_on is not None)

    on_brightnesses = [b for (_id, is_on, b) in results if is_on and b is not None]
    avg_brightness = round(sum(on_brightnesses) / len(on_brightnesses)) if on_brightnesses else None

    return {"is_on": any_on, "avg_brightness": avg_brightness, "lights": per_light}


def get_room_status(room_id: str) -> dict:
    """
    API pública sincrónica.

    Devuelve:
        {
            "is_on": bool,                  # True si al menos un foco responde encendido
            "avg_brightness": int | None,   # promedio de brillo de los focos ENCENDIDOS
            "lights": {light_id: {"is_on": bool | None, "brightness": int | None}}
        }
    """
    return asyncio.run(_get_room_state_async(room_id))


async def _toggle_room_async(room_id: str) -> bool:
    """
    Regla (igual que la app oficial de WiZ): si hay al menos un foco
    encendido, se apagan todos. Si están todos apagados (o no responden),
    se prenden todos. Devuelve el nuevo estado general (True = encendida).
    """
    status = await _get_room_state_async(room_id)
    turn_on = not status["is_on"]

    lights = get_lights_in_room(room_id)

    async def apply(light_data: dict):
        light = Light(light_data["ip"])
        try:
            if turn_on:
                await light._turn_on()
            else:
                await light._turn_off()
        except LightUnreachableError:
            # Un foco desconectado no debe frenar al resto de la habitación.
            pass

    await asyncio.gather(*(apply(l) for l in lights))
    return turn_on


def toggle_room(room_id: str) -> bool:
    """API pública sincrónica. Devuelve el nuevo estado (True = quedó encendida)."""
    return asyncio.run(_toggle_room_async(room_id))
