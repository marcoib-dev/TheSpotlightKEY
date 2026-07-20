"""
Resuelve rutas a assets (íconos SVG, etc.) tanto corriendo desde el
código fuente (dev) como ya empaquetado con PyInstaller (.exe).

El problema que esto resuelve: en dev, un path relativo a __file__
apunta correctamente a sources/SVG/ porque el .py vive en el repo,
junto a esa carpeta. Pero PyInstaller, en modo --onefile, extrae los
assets empaquetados a una carpeta temporal distinta en tiempo de
ejecución (sys._MEIPASS) — la ruta relativa al .py deja de servir y
QIcon() falla en silencio (no tira excepción, sólo devuelve un ícono
vacío), que es exactamente lo que estaba pasando.

Uso (acepta uno o varios segmentos, como os.path.join):
    from core.resources import resource_path
    ICONS_DIR = resource_path("sources", "SVG")
    ICONS_DIR = resource_path("sources/SVG")  # también válido
"""

import sys
from pathlib import Path


def resource_path(*parts: str) -> Path:
    """
    parts: uno o más segmentos de ruta relativos a la raíz del proyecto,
    ej: resource_path("sources", "SVG") o resource_path("sources/SVG").

    - En dev: raíz del proyecto = 2 niveles arriba de este archivo
      (core/resources.py -> core/ -> raíz).
    - Empaquetado (PyInstaller): raíz = sys._MEIPASS, la carpeta temporal
      donde PyInstaller extrae todo lo declarado con --add-data.
    """
    if hasattr(sys, "_MEIPASS"):
        base = Path(sys._MEIPASS)
    else:
        base = Path(__file__).resolve().parent.parent

    return base.joinpath(*parts)