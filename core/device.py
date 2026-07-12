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

import asyncio
from pywizlight import wizlight, PilotBuilder
from pywizlight.exceptions import WizLightConnectionError, WizLightTimeOutError

DEFAULT_TIMEOUT = 6  # segundos que esperamos antes de darnos por vencidos


class LightUnreachableError(Exception):
    """El foco no respondió: puede estar apagado, sin red, o con otra IP."""

    def __init__(self, ip: str):
        self.ip = ip
        super().__init__(
            f"El foco ({ip}) no respondió. Verificá que esté encendido "
            f"(con corriente) y en la misma red. Si el problema persiste, "
            f"puede que su IP haya cambiado — probá 'discover' de nuevo."
        )


class Light:
    def __init__(self, ip: str, timeout: int = DEFAULT_TIMEOUT):
        self.ip = ip
        self.timeout = timeout

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

    def is_on(self) -> bool:
        state = asyncio.run(self._get_state())
        if state is None:
            raise LightUnreachableError(self.ip)
        return state.get_state()

    def __repr__(self):
        return f"Light(ip={self.ip!r})"