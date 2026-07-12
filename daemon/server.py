"""
Demonio de Spotlight-Key: corre en segundo plano con el event loop de
asyncio ya activo, escuchando comandos por un socket Unix. Evita el
costo de arrancar Python + importar dependencias en cada atajo de teclado.

Protocolo: una línea de texto por comando (mismo vocabulario que la CLI):
    toggle | on | off | color R G B | brightness N | status

Responde una línea de texto con el resultado.
"""

import asyncio
import os
from pathlib import Path

from core.config import get_light_ip
from core.device import Light


def _socket_path() -> Path:
    runtime_dir = os.environ.get("XDG_RUNTIME_DIR", f"/tmp/spotlight-key-{os.getuid()}")
    d = Path(runtime_dir)
    d.mkdir(parents=True, exist_ok=True)
    return d / "spotlight-key.sock"


class Daemon:
    def __init__(self):
        self.light: Light | None = None
        self._reload_light()

    def _reload_light(self):
        ip = get_light_ip()
        self.light = Light(ip) if ip else None

    async def handle_command(self, command: str) -> str:
        # Por si cambiaste la IP desde la GUI mientras el daemon ya corría.
        self._reload_light()
        if self.light is None:
            return "ERROR: no hay foco configurado"

        parts = command.strip().split()
        if not parts:
            return "ERROR: comando vacío"

        cmd, *args = parts
        try:
            if cmd == "on":
                await self.light._turn_on()
                return "OK: encendido"
            elif cmd == "off":
                await self.light._turn_off()
                return "OK: apagado"
            elif cmd == "toggle":
                state = await self.light._get_state()
                is_on = state.get_state() if state else False
                if is_on:
                    await self.light._turn_off()
                    return "OK: apagado"
                await self.light._turn_on()
                return "OK: encendido"
            elif cmd == "color":
                r, g, b = map(int, args)
                await self.light._turn_on(rgb=(r, g, b))
                return f"OK: color {r},{g},{b}"
            elif cmd == "brightness":
                value = int(args[0])
                await self.light._turn_on(brightness=value)
                return f"OK: brillo {value}"
            elif cmd == "status":
                state = await self.light._get_state()
                is_on = state.get_state() if state else False
                return f"OK: {'encendido' if is_on else 'apagado'}"
            else:
                return f"ERROR: comando desconocido '{cmd}'"
        except Exception as e:
            return f"ERROR: {e}"

    async def _handle_client(self, reader, writer):
        data = await reader.readline()
        response = await self.handle_command(data.decode())
        writer.write((response + "\n").encode())
        await writer.drain()
        writer.close()

    async def run(self):
        sock_path = _socket_path()
        if sock_path.exists():
            sock_path.unlink()

        server = await asyncio.start_unix_server(self._handle_client, path=str(sock_path))
        print(f"Spotlight-Key daemon escuchando en {sock_path}")
        async with server:
            await server.serve_forever()


def main():
    asyncio.run(Daemon().run())


if __name__ == "__main__":
    main()