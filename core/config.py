"""
Configuración persistente de la app: lista de focos, atajos de teclado, etc.

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
        return {"lights": [], "hotkeys": {}}
    with open(path, "rb") as f:
        config = tomllib.load(f)
    config.setdefault("lights", [])
    config.setdefault("hotkeys", {})
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


def add_or_update_light(light_id: str, ip: str, name: str = "") -> dict:
    """
    Agrega un foco nuevo o actualiza su IP si ya existía (mismo id/MAC).
    Se usa tanto al descubrir un foco nuevo como al refrescar uno existente
    cuya IP cambió por DHCP.
    """
    config = load_config()
    lights = config.setdefault("lights", [])

    for light in lights:
        if light.get("id") == light_id:
            light["ip"] = ip
            if name:
                light["name"] = name
            save_config(config)
            return light

    new_light = {"id": light_id, "ip": ip, "name": name}
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