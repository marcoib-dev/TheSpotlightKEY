"""
CLI de Spotlight-Key.

Uso:
    python -m cli on
    python -m cli off
    python -m cli color 255 0 0
    python -m cli brightness 150
    python -m cli status
    python -m cli discover
    python -m cli set-ip 192.168.0.26 --name "Foco escritorio"
"""

import argparse
import sys

from core.config import get_light_ip, set_light_ip
from core.device import Light
from core.discovery import discover_lights


def _get_light() -> Light:
    """Obtiene el Light configurado, o corta la ejecución con un mensaje claro."""
    ip = get_light_ip()
    if not ip:
        print(
            "No hay ningún foco configurado todavía.\n"
            "Corré 'python -m cli discover' para buscarlo, "
            "y 'python -m cli set-ip <IP>' para guardarlo."
        )
        sys.exit(1)
    return Light(ip)


def cmd_on(args):
    _get_light().turn_on()
    print("Foco encendido.")


def cmd_off(args):
    _get_light().turn_off()
    print("Foco apagado.")

def cmd_toggle(args):
    light = _get_light()
    if light.is_on():
        light.turn_off()
        print("Foco apagado.")
    else:
        light.turn_on()
        print("Foco encendido.")


def cmd_color(args):
    _get_light().set_color(args.r, args.g, args.b)
    print(f"Color seteado a RGB({args.r}, {args.g}, {args.b}).")


def cmd_brightness(args):
    _get_light().set_brightness(args.value)
    print(f"Brillo seteado a {args.value}.")


def cmd_status(args):
    light = _get_light()
    state = "encendido" if light.is_on() else "apagado"
    print(f"Foco ({light.ip}): {state}")


def cmd_discover(args):
    print(f"Buscando focos WiZ en la red ({args.wait}s)...")
    lights = discover_lights(wait=args.wait)
    if not lights:
        print("No se encontró ningún foco. Revisá que esté en la misma red.")
        return
    for i, l in enumerate(lights, 1):
        print(f"  {i}. IP: {l['ip']}  MAC: {l['mac']}")


def cmd_set_ip(args):
    set_light_ip(args.ip, name=args.name or "")
    print(f"Guardado: {args.ip} ({args.name or 'sin nombre'})")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="spotlight-key", description="Control de focos WiZ")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("on", help="Encender el foco").set_defaults(func=cmd_on)
    sub.add_parser("off", help="Apagar el foco").set_defaults(func=cmd_off)
    sub.add_parser("status", help="Ver estado actual").set_defaults(func=cmd_status)
    sub.add_parser("toggle", help="Prender si está apagado, apagar si está prendido").set_defaults(func=cmd_toggle)

     
    p_color = sub.add_parser("color", help="Setear color RGB (0-255 cada uno)")
    p_color.add_argument("r", type=int)
    p_color.add_argument("g", type=int)
    p_color.add_argument("b", type=int)
    p_color.set_defaults(func=cmd_color)

    p_bright = sub.add_parser("brightness", help="Setear brillo (0-255)")
    p_bright.add_argument("value", type=int)
    p_bright.set_defaults(func=cmd_brightness)

    p_disc = sub.add_parser("discover", help="Buscar focos WiZ en la red local")
    p_disc.add_argument("--wait", type=int, default=5, help="Segundos a esperar respuestas")
    p_disc.set_defaults(func=cmd_discover)

    p_setip = sub.add_parser("set-ip", help="Guardar la IP del foco a usar")
    p_setip.add_argument("ip")
    p_setip.add_argument("--name", default="")
    p_setip.set_defaults(func=cmd_set_ip)

    return parser


def main():
    parser = build_parser()
    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()