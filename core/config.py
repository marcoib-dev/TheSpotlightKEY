"""
Configuración persistente de la app: lista de focos, habitaciones, colores
favoritos por foco, atajos de teclado, etc.

Se guarda en config.toml, en el directorio de configuración estándar del
usuario (no en el repo — ver .gitignore).
"""

import sys
import tomllib
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
        return {"lights": [], "hotkeys": {}, "rooms": []}
    with open(path, "rb") as f:
        config = tomllib.load(f)
    config.setdefault("lights", [])
    config.setdefault("hotkeys", {})
    config.setdefault("rooms", [])
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
