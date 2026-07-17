"""
Wrapper sincrónico sobre pywizlight.

pywizlight es asíncrono (usa asyncio) porque espera respuestas UDP
con timeout. Esta clase esconde ese detalle: el resto de la app
(CLI, GUI, daemon, hotkeys) usa métodos normales, sin async/await.

También normaliza los errores: pywizlight puede tardar hasta ~13s
en reintentar antes de tirar su propia excepción cuando el foco no
responde (apagado de la llave, fuera de la red, IP vieja por DHCP,
etc). Acá lo acotamos a un timeout propio más corto y lo traducimos
a una única excepción (LightUnreachableError) fácil de manejar
desde el resto de la app.
"""

# core/device.py

import asyncio
import logging
from logging.handlers import RotatingFileHandler
from pywizlight import wizlight, PilotBuilder
from pywizlight.exceptions import WizLightConnectionError, WizLightTimeOutError

from core.config import get_log_path

logger = logging.getLogger("spotlight-key")
logger.setLevel(logging.WARNING)

if not logger.handlers:
    _handler = RotatingFileHandler(
        get_log_path(),
        maxBytes=1_000_000,  # ~1 MB por archivo
        backupCount=3,        # guarda hasta 3 archivos viejos (.log.1, .log.2, .log.3)
    )
    _handler.setFormatter(
        logging.Formatter("%(asctime)s %(levelname)s: %(message)s")
    )
    logger.addHandler(_handler)

DEFAULT_TIMEOUT = 6  # segundos que esperamos antes de darnos por vencidos


class LightUnreachableError(Exception):
    """El foco no respondió: puede estar apagado, sin red, con otra IP, o colgado."""

    def __init__(self, ip: str):
        self.ip = ip
        super().__init__(
            f"El foco ({ip}) no respondió. Probá esto en orden:\n"
            f"  1. Desenchufá el foco unos segundos y volvé a enchufarlo "
            f"(a veces el Wi-Fi del foco se cuelga y necesita reiniciar).\n"
            f"  2. Verificá que esté encendido con corriente y en la misma red.\n"
            f"  3. Si el problema persiste, puede que su IP haya cambiado — "
            f"probá 'discover' de nuevo."
        )


class Light:
    MIN_COLOR_TEMP = 2200
    MAX_COLOR_TEMP = 6500

    def __init__(self, ip: str, timeout: int = DEFAULT_TIMEOUT):
        self.ip = ip
        self.timeout = timeout


    def get_status(self) -> dict:
        """
        Devuelve el estado completo del foco: encendido/apagado, brillo
        y temperatura de color. brightness/colortemp pueden venir como
        None si el foco está en modo RGB puro (sin esos campos seteados)
        o si esta versión de pywizlight no expone ese dato.
        """
        state = asyncio.run(self._get_state())
        if state is None:
            raise LightUnreachableError(self.ip)

        return {
            "is_on": state.get_state(),
            "brightness": self._safe_state_read(state, "get_brightness"),
            "colortemp": self._safe_state_read(state, "get_colortemp"),
        }

    @staticmethod
    def _safe_state_read(state, method_name: str):
        method = getattr(state, method_name, None)
        if method is None:
            return None
        try:
            return method()
        except Exception:
            return None

    # --- Métodos internos, async ---

    async def _turn_on(self, **kwargs):
        bulb = wizlight(self.ip)
        await self._with_timeout(bulb.turn_on(PilotBuilder(**kwargs)))

    async def _turn_off(self):
        bulb = wizlight(self.ip)
        await self._with_timeout(bulb.turn_off())

    async def _get_state(self):
        bulb = wizlight(self.ip)
        result = await self._with_timeout(bulb.updateState())
        # En pywizlight >= 0.6.x, updateState() puede devolver una lista de
        # PilotParser (una respuesta por cada datagrama UDP enviado) en vez
        # de un único objeto. Nos quedamos con la última respuesta recibida.
        if isinstance(result, list):
            return result[-1] if result else None
        return result

    async def _with_timeout(self, coro):
        try:
            return await asyncio.wait_for(coro, timeout=self.timeout)
        except (asyncio.TimeoutError, WizLightTimeOutError, WizLightConnectionError):
            logger.warning(f"Foco {self.ip} no respondió (timeout tras {self.timeout}s)")
            raise LightUnreachableError(self.ip)

    # --- API pública, sincrónica ---

    def turn_on(self):
        """Enciende el foco con el último estado (color/brillo) que tenía."""
        asyncio.run(self._turn_on())

    def turn_off(self):
        asyncio.run(self._turn_off())

    def set_color(self, r: int, g: int, b: int):
        """Enciende el foco con un color RGB específico."""
        asyncio.run(self._turn_on(rgb=(r, g, b)))

    def set_brightness(self, brightness: int):
        """brightness: 0-255"""
        asyncio.run(self._turn_on(brightness=brightness))

    def set_warm_white(self, brightness: int = 255):
        """Luz blanca cálida, útil como 'modo normal'."""
        asyncio.run(self._turn_on(warm_white=brightness))

    def set_color_temp(self, kelvin: int):
        """
        kelvin: temperatura de color, entre MIN_COLOR_TEMP y MAX_COLOR_TEMP.
        Valores bajos = luz cálida (amarillenta); altos = luz fría (azulada).
        Al usar esto el foco sale del modo RGB, si es que estaba en uno.
        """
        kelvin = max(self.MIN_COLOR_TEMP, min(self.MAX_COLOR_TEMP, kelvin))
        asyncio.run(self._turn_on(colortemp=kelvin))

    def set_scene(self, scene_id: int):
        """
        Activa una escena nativa del foco (ver pywizlight.scenes.SCENES
        para la lista completa de IDs disponibles, o core/presets.py para
        los que usamos en la GUI). El foco enciende automáticamente al
        activar una escena.
        """
        asyncio.run(self._turn_on(scene=scene_id))

    def is_on(self) -> bool:
        state = asyncio.run(self._get_state())
        if state is None:
            raise LightUnreachableError(self.ip)
        return state.get_state()

    def __repr__(self):
        return f"Light(ip={self.ip!r})"
