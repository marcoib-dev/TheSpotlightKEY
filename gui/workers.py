"""
Trabajo en background para no congelar la GUI mientras se consulta
el estado de los focos (cada consulta puede tardar hasta DEFAULT_TIMEOUT
segundos si el foco no responde).
"""

from PySide6.QtCore import QObject, Signal

from core.device import Light, LightUnreachableError


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