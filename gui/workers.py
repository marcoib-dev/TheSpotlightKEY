"""
Trabajo en background para no congelar la GUI mientras se consulta
el estado de los focos o de las habitaciones (cada consulta puede tardar
hasta DEFAULT_TIMEOUT segundos por foco si no responde).
"""

from PySide6.QtCore import QObject, Signal

from core.device import Light, LightUnreachableError
from core.rooms import get_room_status


class LightStatusWorker(QObject):
    """
    Corre en un QThread aparte. Recibe la lista de focos (dicts con
    'id' e 'ip') y devuelve, vía señal, un dict {id: bool | None}.
    None significa "no respondió" (LightUnreachableError).
    """

    finished = Signal(dict)

    def __init__(self, lights: list[dict]):
        super().__init__()
        self.lights = lights

    def run(self):
        results: dict[str, bool | None] = {}
        for light in self.lights:
            try:
                results[light["id"]] = Light(light["ip"]).is_on()
            except LightUnreachableError:
                results[light["id"]] = None
        self.finished.emit(results)


class RoomStatusWorker(QObject):
    """
    Corre en un QThread aparte. Recibe la lista de habitaciones (dicts con
    'id') y devuelve, vía señal, un dict:
        {room_id: {"is_on": bool, "avg_brightness": int | None}}

    core.rooms.get_room_status ya consulta los focos de cada habitación en
    paralelo internamente (asyncio.gather), así que acá sólo se itera
    habitación por habitación, no foco por foco.
    """

    finished = Signal(dict)

    def __init__(self, rooms: list[dict]):
        super().__init__()
        self.rooms = rooms

    def run(self):
        results: dict[str, dict] = {}
        for room in self.rooms:
            status = get_room_status(room["id"])
            results[room["id"]] = {
                "is_on": status["is_on"],
                "avg_brightness": status["avg_brightness"],
            }
        self.finished.emit(results)
