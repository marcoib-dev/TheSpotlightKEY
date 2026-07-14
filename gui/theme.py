BLACK = "#1A1A1A"
BLACK_SOFT = "#2B2B2B"
YELLOW = "#FFC72C"
WHITE = "#F5F5F5"

STYLESHEET = f"""
QMainWindow, QWidget {{
    background-color: {BLACK};
    color: {WHITE};
    font-family: "Inter", "Segoe UI", sans-serif;
}}
QLabel#Header {{ font-size: 18px; font-weight: 600; }}
QLabel#ScreenTitle {{ font-size: 26px; font-weight: 700; color: {YELLOW}; }}
QLabel#LightName {{ font-size: 13px; }}
QPushButton {{
    background-color: {BLACK_SOFT};
    color: {WHITE};
    border: none;
    border-radius: 8px;
    padding: 8px 14px;
}}
QPushButton:hover {{ background-color: #3A3A3A; }}
QPushButton#Primary {{ background-color: {YELLOW}; color: {BLACK}; font-weight: 600; }}
QPushButton#Primary:hover {{ background-color: #FFD75E; }}
QPushButton#IconButton {{ background-color: transparent; border-radius: 24px; }}
QPushButton#IconButton:hover {{ background-color: {BLACK_SOFT}; }}
QFrame#LightCard {{ background-color: {BLACK_SOFT}; border-radius: 16px; }}
QFrame#LightCard:hover {{ background-color: #333333; }}
QSlider::groove:horizontal {{ height: 6px; background: {BLACK_SOFT}; border-radius: 3px; }}
QSlider::handle:horizontal {{
    background: {YELLOW}; width: 18px; height: 18px; margin: -6px 0; border-radius: 9px;
}}
QSlider::sub-page:horizontal {{ background: {YELLOW}; border-radius: 3px; }}
"""