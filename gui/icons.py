from pathlib import Path
from PySide6.QtGui import QIcon

ICONS_DIR = Path(__file__).resolve().parent.parent / "sources" / "SVG"


def icon(name: str) -> QIcon:
    """name sin extensión, ej: 'lightbulb', 'power-off'."""
    return QIcon(str(ICONS_DIR / f"{name}.svg"))