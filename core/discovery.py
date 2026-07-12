"""
Descubrimiento automático de focos WiZ en la red local.

Funciona mandando un broadcast UDP (protocolo propio de WiZ, puerto 38899)
y esperando que los dispositivos en la red respondan. No requiere nube.
"""

import asyncio
from pywizlight.discovery import find_wizlights


async def _discover(wait: int = 5) -> list[dict]:
    """
    Devuelve una lista de dicts: [{"ip": "...", "mac": "..."}, ...]
    """
    bulbs = await find_wizlights(wait_time=wait)
    return [{"ip": b.ip_address, "mac": b.mac_address} for b in bulbs]


def discover_lights(wait: int = 5) -> list[dict]:
    """API pública sincrónica. wait: segundos a esperar respuestas."""
    return asyncio.run(_discover(wait))