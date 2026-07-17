"""
Presets que se muestran en el detalle de un foco (pestaña "Diario" del
spec de GUI, ver Image 3 de referencia).

Blanco: usa temperatura de color (Kelvin), vía Light.set_color_temp().
No depende de escenas del foco, es sólo un atajo a valores fijos.

Nota: los presets "Funcional" (escenas nativas de pywizlight.scenes,
Relax/Acogedor/etc.) se probaron y se sacaron — el foco de Marco no
reproduce esas escenas correctamente (parece un modelo tunable-white,
no RGB completo), así que la app usa colores favoritos guardados por el
usuario en su lugar (ver core/config.py: get_favorite_colors y afines).
Light.set_scene() se deja disponible en core/device.py por si en el
futuro se usa con otro foco que sí las soporte, pero no se llama desde
la GUI actual.
"""

WHITE_PRESETS = {
    "mas_calido":    {"label": "Más cálido",    "kelvin": 2200},
    "blanco_calido": {"label": "Blanco cálido", "kelvin": 2700},
    "luz_de_dia":    {"label": "Luz de día",    "kelvin": 4500},
    "blanco_frio":   {"label": "Blanco frío",   "kelvin": 6500},
}
