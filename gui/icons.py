from PySide6.QtGui import QIcon

from core.resources import resource_path

ICONS_DIR = resource_path("sources/SVG")


def icon(name: str) -> QIcon:
    """name sin extensión, ej: 'lightbulb', 'power-off'."""
    return QIcon(str(ICONS_DIR / f"{name}.svg"))
