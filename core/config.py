"""
Configuración persistente de la app: lista de focos, habitaciones, colores
favoritos por foco, atajos de teclado, etc.

Se guarda en config.toml, en el directorio de configuración estándar del
usuario (no en el repo — ver .gitignore).
"""

import sys
import tomllib
import uuid
from pathlib import Path

try:
    import tomli_w
except ImportError:
    tomli_w = None  # se valida al guardar


def _config_path() -> Path:
    if sys.platform == "win32":
        base = Path.home() / "AppData" / "Roaming"
    else:
        base = Path.home() / ".config"
    config_dir = base / "spotlight-key"
    config_dir.mkdir(parents=True, exist_ok=True)
    return config_dir / "config.toml"


def get_log_path() -> Path:
    return _config_path().parent / "spotlight-key.log"


def load_config() -> dict:
    path = _config_path()
    if not path.exists():
        return {"lights": [], "hotkeys": [], "rooms": []}
    with open(path, "rb") as f:
        config = tomllib.load(f)
    config.setdefault("lights", [])
    config.setdefault("rooms", [])
    # Migración: versiones viejas guardaban "hotkeys" como tabla vacía
    # ({}), nunca se usó de verdad. Si no es una lista, se resetea.
    if not isinstance(config.get("hotkeys"), list):
        config["hotkeys"] = []
    return config


def save_config(config: dict) -> None:
    if tomli_w is None:
        raise RuntimeError(
            "Falta 'tomli_w' para guardar TOML. Instalalo con: pip install tomli_w"
        )
    with open(_config_path(), "wb") as f:
        tomli_w.dump(config, f)


# --- API de focos (multi-dispositivo, identificados por MAC) ---

def get_lights() -> list[dict]:
    return load_config().get("lights", [])


def get_light(light_id: str) -> dict | None:
    for light in get_lights():
        if light.get("id") == light_id:
            return light
    return None


def add_or_update_light(light_id: str, ip: str, name: str = "", room_id: str = "") -> dict:
    """
    Agrega un foco nuevo o actualiza su IP si ya existía (mismo id/MAC).
    Se usa tanto al descubrir un foco nuevo como al refrescar uno existente
    cuya IP cambió por DHCP.

    room_id es opcional: si no se pasa, un foco nuevo queda sin asignar
    ("") y uno existente conserva la room que ya tenía (no se pisa).
    """
    config = load_config()
    lights = config.setdefault("lights", [])

    for light in lights:
        if light.get("id") == light_id:
            light["ip"] = ip
            if name:
                light["name"] = name
            if room_id:
                light["room_id"] = room_id
            light.setdefault("room_id", "")
            save_config(config)
            return light

    new_light = {"id": light_id, "ip": ip, "name": name, "room_id": room_id}
    lights.append(new_light)
    save_config(config)
    return new_light


def rename_light(light_id: str, name: str) -> None:
    config = load_config()
    for light in config.get("lights", []):
        if light.get("id") == light_id:
            light["name"] = name
            save_config(config)
            return
    raise ValueError(f"No existe ningún foco con id {light_id!r}")


def remove_light(light_id: str) -> None:
    config = load_config()
    config["lights"] = [l for l in config.get("lights", []) if l.get("id") != light_id]
    save_config(config)


def resolve_light(identifier: str) -> dict | None:
    """
    Busca un foco por id (MAC) o por nombre (case-insensitive).
    Pensado para CLI/daemon, donde conviene escribir un nombre corto
    ("escritorio") en vez de la MAC completa.

    Si hay más de un foco con el mismo nombre, se considera ambiguo
    y no matchea ninguno (mejor forzar a usar el id en ese caso).
    """
    identifier_lower = identifier.lower()
    lights = get_lights()

    for light in lights:
        if light.get("id", "").lower() == identifier_lower:
            return light

    matches = [l for l in lights if l.get("name", "").lower() == identifier_lower]
    return matches[0] if len(matches) == 1 else None


# --- API de colores favoritos (por foco) ---
#
# Cada foco puede guardar una lista de colores RGB elegidos por el usuario
# (vía el color picker de la GUI), para no tener que buscarlos de nuevo.
# Se identifican por posición (índice) dentro de la lista de ese foco, no
# tienen un id propio: alcanza para esto, no hace falta más.

def get_favorite_colors(light_id: str) -> list[dict]:
    light = get_light(light_id)
    if light is None:
        return []
    return light.get("favorite_colors", [])


def add_favorite_color(light_id: str, r: int, g: int, b: int) -> dict:
    config = load_config()
    for light in config.get("lights", []):
        if light.get("id") == light_id:
            favorites = light.setdefault("favorite_colors", [])
            new_color = {"r": r, "g": g, "b": b}
            favorites.append(new_color)
            save_config(config)
            return new_color
    raise ValueError(f"No existe ningún foco con id {light_id!r}")


def remove_favorite_color(light_id: str, index: int) -> None:
    """index es la posición dentro de la lista que devuelve get_favorite_colors."""
    config = load_config()
    for light in config.get("lights", []):
        if light.get("id") == light_id:
            favorites = light.get("favorite_colors", [])
            if 0 <= index < len(favorites):
                favorites.pop(index)
                save_config(config)
            return
    raise ValueError(f"No existe ningún foco con id {light_id!r}")


# --- API de habitaciones (agrupan focos, sólo para la GUI/organización) ---

def get_rooms() -> list[dict]:
    return load_config().get("rooms", [])


def get_room(room_id: str) -> dict | None:
    for room in get_rooms():
        if room.get("id") == room_id:
            return room
    return None


def add_or_update_room(room_id: str, name: str) -> dict:
    """
    Agrega una habitación nueva o renombra una existente (mismo id).
    room_id lo decide quien llama (ver gui: uuid4().hex o un slug del
    nombre); acá no se genera solo para mantener esta capa simple y
    testeable sin depender de una lib de uuids en particular.
    """
    config = load_config()
    rooms = config.setdefault("rooms", [])

    for room in rooms:
        if room.get("id") == room_id:
            room["name"] = name
            save_config(config)
            return room

    new_room = {"id": room_id, "name": name}
    rooms.append(new_room)
    save_config(config)
    return new_room


def rename_room(room_id: str, name: str) -> None:
    config = load_config()
    for room in config.get("rooms", []):
        if room.get("id") == room_id:
            room["name"] = name
            save_config(config)
            return
    raise ValueError(f"No existe ninguna habitación con id {room_id!r}")


def remove_room(room_id: str) -> None:
    """
    Borra la habitación. Los focos que apuntaban a ella NO se borran,
    quedan sin asignar (room_id = "") para no perder configuración de
    focos por accidente.
    """
    config = load_config()
    config["rooms"] = [r for r in config.get("rooms", []) if r.get("id") != room_id]

    for light in config.get("lights", []):
        if light.get("room_id") == room_id:
            light["room_id"] = ""

    save_config(config)


def resolve_room(identifier: str) -> dict | None:
    """
    Análogo a resolve_light: busca por id o por nombre (case-insensitive).
    """
    identifier_lower = identifier.lower()
    rooms = get_rooms()

    for room in rooms:
        if room.get("id", "").lower() == identifier_lower:
            return room

    matches = [r for r in rooms if r.get("name", "").lower() == identifier_lower]
    return matches[0] if len(matches) == 1 else None


def get_lights_in_room(room_id: str) -> list[dict]:
    return [l for l in get_lights() if l.get("room_id") == room_id]


def get_unassigned_lights() -> list[dict]:
    """Focos que no pertenecen a ninguna habitación todavía."""
    return [l for l in get_lights() if not l.get("room_id")]


def assign_light_to_room(light_id: str, room_id: str) -> None:
    """
    room_id = "" desasigna el foco (lo deja "sin habitación").
    No valida que room_id exista para permitir desasignar con "" sin
    tener que resolver una room primero; sí valida que el foco exista.
    """
    config = load_config()
    for light in config.get("lights", []):
        if light.get("id") == light_id:
            light["room_id"] = room_id
            save_config(config)
            return
    raise ValueError(f"No existe ningún foco con id {light_id!r}")


# --- API de atajos de teclado ---
#
# Cada atajo asocia una combinación de teclas con una acción concreta.
# El id se genera acá mismo (a diferencia de rooms, donde lo decide quien
# llama) porque no hay ningún flujo que necesite controlarlo desde afuera.
#
# favorite_index usa -1 como "sin valor" en vez de None: TOML no tiene
# null, así que None rompería al guardar (tomli_w no sabe serializarlo).

def get_hotkeys() -> list[dict]:
    return load_config().get("hotkeys", [])


def add_hotkey(keys: str, action: str, target_id: str, favorite_index: int = -1) -> dict:
    """
    action: "toggle_light" | "toggle_room" | "apply_favorite_color"
    target_id: id del foco o de la habitación, según la acción
    favorite_index: sólo para "apply_favorite_color" (posición en la
                    lista de favoritos de ese foco)
    """
    config = load_config()
    hotkeys = config.setdefault("hotkeys", [])
    new_hotkey = {
        "id": uuid.uuid4().hex[:8],
        "keys": keys,
        "action": action,
        "target_id": target_id,
        "favorite_index": favorite_index,
    }
    hotkeys.append(new_hotkey)
    save_config(config)
    return new_hotkey


def remove_hotkey(hotkey_id: str) -> None:
    config = load_config()
    config["hotkeys"] = [h for h in config.get("hotkeys", []) if h.get("id") != hotkey_id]
    save_config(config)
