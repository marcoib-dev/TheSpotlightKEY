"""
Demonio de Spotlight-Key. Protocolo (una línea de texto por comando):

    list
    on <foco>
    off <foco>
    toggle <foco>
    color <foco> R G B
    brightness <foco> N
    status <foco>

<foco> es el id (MAC) o el nombre del foco (ver 'list' o config.toml).
"""

import asyncio
import os
from pathlib import Path

from core.config import get_lights, resolve_light
from core.device import Light


def _socket_path() -> Path:
    runtime_dir = os.environ.get("XDG_RUNTIME_DIR", f"/tmp/spotlight-key-{os.getuid()}")
    d = Path(runtime_dir)
    d.mkdir(parents=True, exist_ok=True)
    return d / "spotlight-key.sock"


class Daemon:
    async def handle_command(self, command: str) -> str:
        parts = command.strip().split()
        if not parts:
            return "ERROR: comando vacío"

        cmd = parts[0]

        if cmd == "list":
            entries = get_lights()
            if not entries:
                return "OK: sin focos configurados"
            return "OK: " + ";".join(
                f"{l['id']}|{l.get('name', '')}|{l['ip']}" for l in entries
            )

        if len(parts) < 2:
            return "ERROR: formato esperado '<comando> <foco> [args]'"

        foco_id, *args = parts[1:]
        light_data = resolve_light(foco_id)
        if light_data is None:
            return f"ERROR: no se encontró ningún foco que coincida con '{foco_id}'"

        light = Light(light_data["ip"])

        try:
            if cmd == "on":
                await light._turn_on()
                return "OK: encendido"
            elif cmd == "off":
                await light._turn_off()
                return "OK: apagado"
            elif cmd == "toggle":
                state = await light._get_state()
                is_on = state.get_state() if state else False
                await (light._turn_off() if is_on else light._turn_on())
                return f"OK: {'apagado' if is_on else 'encendido'}"
            elif cmd == "color":
                r, g, b = map(int, args)
                await light._turn_on(rgb=(r, g, b))
                return f"OK: color {r},{g},{b}"
            elif cmd == "brightness":
                await light._turn_on(brightness=int(args[0]))
                return f"OK: brillo {args[0]}"
            elif cmd == "status":
                state = await light._get_state()
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