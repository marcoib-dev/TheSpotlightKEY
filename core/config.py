"""
Configuración persistente de la app (IP del foco, atajos de teclado, etc.).

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


DEFAULT_CONFIG = {
    "light": {
        "ip": "",
        "name": "",
    },
    "hotkeys": {},
}


def _config_path() -> Path:
    if sys.platform == "win32":
        base = Path.home() / "AppData" / "Roaming"
    else:
        base = Path.home() / ".config"
    config_dir = base / "spotlight-key"
    config_dir.mkdir(parents=True, exist_ok=True)
    return config_dir / "config.toml"


def load_config() -> dict:
    path = _config_path()
    if not path.exists():
        return dict(DEFAULT_CONFIG)
    with open(path, "rb") as f:
        return tomllib.load(f)


def save_config(config: dict) -> None:
    if tomli_w is None:
        raise RuntimeError(
            "Falta 'tomli_w' para guardar TOML. Instalalo con: pip install tomli_w"
        )
    path = _config_path()
    with open(path, "wb") as f:
        tomli_w.dump(config, f)


def get_light_ip() -> str | None:
    config = load_config()
    ip = config.get("light", {}).get("ip", "")
    return ip or None


def set_light_ip(ip: str, name: str = "") -> None:
    config = load_config()
    config.setdefault("light", {})
    config["light"]["ip"] = ip
    config["light"]["name"] = name
    save_config(config)