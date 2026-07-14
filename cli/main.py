"""
CLI de Spotlight-Key.

Uso:
    python -m cli list
    python -m cli discover
    python -m cli add <ip> <mac> [--name "Foco escritorio"]
    python -m cli rename <foco> <nombre_nuevo>
    python -m cli remove <foco>

    python -m cli on <foco>
    python -m cli off <foco>
    python -m cli toggle <foco>
    python -m cli color <foco> 255 0 0
    python -m cli brightness <foco> 150
    python -m cli status <foco>

<foco> puede ser el id (MAC) o el nombre del foco (ver 'list').
"""

import argparse
import sys

from core.config import (
    get_lights,
    resolve_light,
    add_or_update_light,
    rename_light,
    remove_light,
)
from core.device import Light, LightUnreachableError
from core.discovery import discover_lights


def _resolve_or_exit(identifier: str) -> dict:
    light = resolve_light(identifier)
    if light is not None:
        return light

    lights = get_lights()
    if lights:
        options = "\n".join(
            f"  - {l.get('name') or '(sin nombre)'} ({l['id']})" for l in lights
        )
        print(f"No se encontró ningún foco que coincida con '{identifier}'. Focos configurados:\n{options}")
    else:
        print("No hay ningún foco configurado todavía. Corré 'python -m cli discover' y 'python -m cli add'.")
    sys.exit(1)


def _run_safe(action):
    try:
        action()
    except LightUnreachableError as e:
        print(f"⚠ {e}")
        sys.exit(1)


def cmd_list(args):
    lights = get_lights()
    if not lights:
        print("No hay ningún foco configurado todavía.")
        return
    for l in lights:
        print(f"  {l.get('name') or '(sin nombre)'}  id={l['id']}  ip={l['ip']}")


def cmd_discover(args):
    print(f"Buscando focos WiZ en la red ({args.wait}s)...")
    found = discover_lights(wait=args.wait)
    if not found:
        print("No se encontró ningún foco. Revisá que esté en la misma red.")
        return
    for i, l in enumerate(found, 1):
        print(f"  {i}. IP: {l['ip']}  MAC: {l['mac']}")


def cmd_add(args):
    add_or_update_light(light_id=args.mac, ip=args.ip, name=args.name or "")
    print(f"Guardado: {args.ip} (id={args.mac}, nombre={args.name or 'sin nombre'})")


def cmd_rename(args):
    light = _resolve_or_exit(args.foco)
    rename_light(light["id"], args.nombre)
    print(f"Renombrado a '{args.nombre}'.")


def cmd_remove(args):
    light = _resolve_or_exit(args.foco)
    remove_light(light["id"])
    print(f"Eliminado {light.get('name') or light['id']}.")


def cmd_on(args):
    light = Light(_resolve_or_exit(args.foco)["ip"])
    _run_safe(light.turn_on)
    print("Foco encendido.")


def cmd_off(args):
    light = Light(_resolve_or_exit(args.foco)["ip"])
    _run_safe(light.turn_off)
    print("Foco apagado.")


def cmd_toggle(args):
    light = Light(_resolve_or_exit(args.foco)["ip"])

    def action():
        if light.is_on():
            light.turn_off()
            print("Foco apagado.")
        else:
            light.turn_on()
            print("Foco encendido.")

    _run_safe(action)


def cmd_color(args):
    light = Light(_resolve_or_exit(args.foco)["ip"])
    _run_safe(lambda: light.set_color(args.r, args.g, args.b))
    print(f"Color seteado a RGB({args.r}, {args.g}, {args.b}).")


def cmd_brightness(args):
    light = Light(_resolve_or_exit(args.foco)["ip"])
    _run_safe(lambda: light.set_brightness(args.value))
    print(f"Brillo seteado a {args.value}.")


def cmd_status(args):
    light = Light(_resolve_or_exit(args.foco)["ip"])
    try:
        state = "encendido" if light.is_on() else "apagado"
        print(f"Foco: {state}")
    except LightUnreachableError as e:
        print(f"⚠ {e}")
        sys.exit(1)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="spotlight-key", description="Control de focos WiZ")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("list", help="Ver focos configurados").set_defaults(func=cmd_list)

    p_disc = sub.add_parser("discover", help="Buscar focos WiZ en la red local")
    p_disc.add_argument("--wait", type=int, default=5)
    p_disc.set_defaults(func=cmd_discover)

    p_add = sub.add_parser("add", help="Agregar o actualizar un foco")
    p_add.add_argument("ip")
    p_add.add_argument("mac")
    p_add.add_argument("--name", default="")
    p_add.set_defaults(func=cmd_add)

    p_rename = sub.add_parser("rename", help="Renombrar un foco")
    p_rename.add_argument("foco")
    p_rename.add_argument("nombre")
    p_rename.set_defaults(func=cmd_rename)

    p_remove = sub.add_parser("remove", help="Eliminar un foco de la config")
    p_remove.add_argument("foco")
    p_remove.set_defaults(func=cmd_remove)

    for name, func, help_text in [
        ("on", cmd_on, "Encender un foco"),
        ("off", cmd_off, "Apagar un foco"),
        ("toggle", cmd_toggle, "Prender si está apagado, apagar si está prendido"),
        ("status", cmd_status, "Ver estado actual"),
    ]:
        p = sub.add_parser(name, help=help_text)
        p.add_argument("foco", help="Id (MAC) o nombre del foco")
        p.set_defaults(func=func)

    p_color = sub.add_parser("color", help="Setear color RGB (0-255 cada uno)")
    p_color.add_argument("foco")
    p_color.add_argument("r", type=int)
    p_color.add_argument("g", type=int)
    p_color.add_argument("b", type=int)
    p_color.set_defaults(func=cmd_color)

    p_bright = sub.add_parser("brightness", help="Setear brillo (0-255)")
    p_bright.add_argument("foco")
    p_bright.add_argument("value", type=int)
    p_bright.set_defaults(func=cmd_brightness)

    return parser


def main():
    parser = build_parser()
    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()