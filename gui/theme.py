BLACK = "#16130F"          # fondo principal, negro con un pelín de calidez
SURFACE = "#221F1A"        # tarjetas, paneles
SURFACE_HOVER = "#2C2717"  # hover de tarjetas y botones
BORDER = "#332D22"         # borde sutil por defecto
BORDER_ACCENT = "#4A3D1A"  # borde de una tarjeta en estado "encendido"
TOGGLE_ON_BG = "#3A3120"   # fondo del botón de power cuando está encendido
YELLOW = "#FFC72C"
YELLOW_HOVER = "#FFD75E"
YELLOW_PRESSED = "#E6A800"
WHITE = "#F5F1EA"
TEXT_SECONDARY = "#8A8478"  # etiquetas, texto de apoyo

STYLESHEET = f"""
QMainWindow, QWidget {{
    background-color: {BLACK};
    color: {WHITE};
    font-family: "Inter", "Segoe UI", sans-serif;
}}
QLabel {{ background-color: transparent; }}
QLabel#Header {{ font-size: 18px; font-weight: 600; }}
QLabel#ScreenTitle {{ font-size: 26px; font-weight: 700; color: {YELLOW}; }}
QLabel#SectionLabel {{ font-size: 11px; font-weight: 600; color: {TEXT_SECONDARY}; }}
QLabel#LightName {{ font-size: 13px; }}

QProgressBar {{ background-color: transparent; border: none; }}
QProgressBar::chunk {{ background-color: {YELLOW}; border-radius: 3px; }}

QFrame#LightCard {{
    background-color: {SURFACE};
    border-radius: 16px;
    border: 1px solid transparent;
}}
QFrame#LightCard:hover {{ background-color: {SURFACE_HOVER}; }}
QFrame#LightCard[on="true"] {{ border: 1px solid {BORDER_ACCENT}; }}

QFrame#HeroPanel {{
    background-color: {SURFACE};
    border-radius: 20px;
}}

QFrame#HotkeyRow {{
    background-color: {SURFACE};
    border-radius: 10px;
}}

QPushButton {{
    background-color: {SURFACE};
    color: {WHITE};
    border: 1px solid transparent;
    border-radius: 10px;
    padding: 8px 14px;
}}
QPushButton:hover {{ background-color: {SURFACE_HOVER}; }}

QPushButton#Primary {{ background-color: {YELLOW}; color: {BLACK}; font-weight: 600; }}
QPushButton#Primary:hover {{ background-color: {YELLOW_HOVER}; }}
QPushButton#Primary:pressed {{ background-color: {YELLOW_PRESSED}; }}

QPushButton#Secondary {{
    background-color: transparent;
    color: {WHITE};
    border: 1px solid {BORDER};
}}
QPushButton#Secondary:hover {{ background-color: {SURFACE}; }}

QPushButton#CompactAdd {{
    background-color: {YELLOW};
    color: {BLACK};
    font-weight: 700;
    border-radius: 14px;
    padding: 4px 12px;
}}
QPushButton#CompactAdd:hover {{ background-color: {YELLOW_HOVER}; }}
QPushButton#CompactAdd:pressed {{ background-color: {YELLOW_PRESSED}; }}

QPushButton#IconButton {{ background-color: transparent; border: none; border-radius: 24px; }}
QPushButton#IconButton:hover {{ background-color: {SURFACE}; }}

QPushButton#PowerToggleButton {{
    background-color: transparent;
    border: none;
    border-radius: 22px;
    padding: 0;
}}
QPushButton#PowerToggleButton:hover {{ background-color: {TOGGLE_ON_BG}; }}
QPushButton#PowerToggleButton[on="true"] {{ background-color: {TOGGLE_ON_BG}; }}
QPushButton#PowerToggleButton[on="true"]:hover {{ background-color: {BORDER_ACCENT}; }}

QToolButton#PresetButton {{
    background-color: {SURFACE};
    color: {WHITE};
    border: 1px solid transparent;
    border-radius: 14px;
    padding: 22px 8px;
    min-height: 60px;
    font-size: 13px;
}}
QToolButton#PresetButton:hover {{
    background-color: {SURFACE_HOVER};
    border: 1px solid {BORDER_ACCENT};
}}
QToolButton#PresetButton:pressed {{ background-color: {YELLOW_PRESSED}; color: {BLACK}; }}

QSlider::groove:horizontal {{ height: 6px; background: {SURFACE}; border-radius: 3px; }}
QSlider::handle:horizontal {{
    background: {YELLOW}; width: 18px; height: 18px; margin: -6px 0; border-radius: 9px;
}}
QSlider::sub-page:horizontal {{ background: {YELLOW}; border-radius: 3px; }}
"""