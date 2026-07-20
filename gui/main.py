import ctypes
import sys
import uuid

from PySide6.QtCore import Qt, Signal, QSize, QThread
from PySide6.QtGui import QColor, QIcon, QKeySequence, QPainter, QPixmap
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QStackedWidget,
    QVBoxLayout, QHBoxLayout, QGridLayout, QLabel, QPushButton,
    QFrame, QScrollArea, QSlider, QColorDialog, QMessageBox, QDialog,
    QListWidget, QListWidgetItem, QProgressBar, QLineEdit, QMenu,
    QGraphicsDropShadowEffect, QToolButton, QSizePolicy, QComboBox,
    QKeySequenceEdit,
)

from core.config import (
    get_lights, get_light, add_or_update_light,
    get_rooms, get_room, add_or_update_room,
    get_lights_in_room, get_unassigned_lights, assign_light_to_room,
    get_favorite_colors, add_favorite_color, remove_favorite_color,
    get_hotkeys, add_hotkey, remove_hotkey,
)
from core.device import Light, LightUnreachableError
from core.discovery import discover_lights
from core.rooms import get_room_status, toggle_room as toggle_room_status
from core.presets import WHITE_PRESETS
from gui.theme import STYLESHEET, YELLOW, WHITE
from gui.icons import icon
from gui.workers import LightStatusWorker, RoomStatusWorker
from core.hotkeys import BRIGHTNESS_STEP_PERCENT
from gui.theme import STYLESHEET, YELLOW, WHITE, TEXT_SECONDARY
# Nombres de archivo tal cual los bajó Marco de SvgRepo (ver sources/SVG/).
# Si en algún momento se renombran a algo más prolijo (ej: "bulb-on.svg" /
# "bulb-off.svg"), sólo hay que actualizar estas dos constantes.
BULB_ON_ICON = "bulb-on-svgrepo-com"
BULB_OFF_ICON = "bulb-svgrepo-com"


# ---------------------------------------------------------------------------
# Helpers de estilo
# ---------------------------------------------------------------------------

def _section_label(text: str) -> QLabel:
    """Etiqueta chica en mayúscula para encabezar una sección (Brillo,
    Blanco, Favoritos...). QSS no soporta letter-spacing, así que el
    'aire' entre letras del mockup no se replica exactamente, pero el
    tamaño/color/mayúscula sí dan el mismo aire prolijo."""
    label = QLabel(text.upper())
    label.setObjectName("SectionLabel")
    return label


def _make_glow(blur: int = 24) -> QGraphicsDropShadowEffect:
    """
    Resplandor amarillo, apagado por defecto. Cada widget necesita su
    propia instancia (un QGraphicsEffect no se puede compartir entre
    varios widgets), por eso esto es una función fábrica, no un objeto
    único. Se prende/apaga con .setEnabled() según el estado on/off.
    """
    effect = QGraphicsDropShadowEffect()
    effect.setBlurRadius(blur)
    effect.setOffset(0, 0)
    effect.setColor(QColor(255, 199, 44, 160))
    effect.setEnabled(False)
    return effect


def _refresh_style(widget: QWidget):
    """
    Fuerza a Qt a reevaluar los selectores QSS que dependen de una
    propiedad dinámica (ej: QFrame#LightCard[on="true"]). Sin esto,
    cambiar setProperty() en tiempo real no repinta el widget.
    """
    widget.style().unpolish(widget)
    widget.style().polish(widget)


def _tinted_icon(name: str, color: str, size: int = 28) -> QIcon:
    """
    Recolorea un ícono monocromático (blanco, como power.svg) al color
    indicado, sin necesitar un segundo archivo .svg. Funciona porque
    esos íconos son sólo trazo sobre fondo transparente: se pinta el
    color encima respetando la forma (alpha) del ícono original.
    """
    base = icon(name).pixmap(size, size)
    tinted = QPixmap(base.size())
    tinted.fill(Qt.transparent)
    painter = QPainter(tinted)
    painter.drawPixmap(0, 0, base)
    painter.setCompositionMode(QPainter.CompositionMode_SourceIn)
    painter.fillRect(tinted.rect(), QColor(color))
    painter.end()
    return QIcon(tinted)


def _describe_hotkey(hotkey: dict) -> str:
    """Texto legible de qué hace un atajo, para listarlo en Atajos de teclado."""
    action = hotkey.get("action")
    target_id = hotkey.get("target_id")

    if action == "toggle_light":
        light = get_light(target_id)
        name = (light.get("name") or light["ip"]) if light else "(foco eliminado)"
        return f"Encender/apagar — {name}"

    if action == "toggle_room":
        room = get_room(target_id)
        name = (room.get("name") if room else None) or "(habitación eliminada)"
        return f"Encender/apagar habitación — {name}"

    if action == "apply_favorite_color":
        light = get_light(target_id)
        name = (light.get("name") or light["ip"]) if light else "(foco eliminado)"
        idx = hotkey.get("favorite_index", -1)
        return f"Color favorito #{idx + 1} — {name}"

    if action == "adjust_brightness":
        light = get_light(target_id)
        name = (light.get("name") or light["ip"]) if light else "(foco eliminado)"
        verb = "Subir" if hotkey.get("direction") == "up" else "Bajar"
        return f"{verb} brillo ({BRIGHTNESS_STEP_PERCENT}%) — {name}"

    if action == "apply_white_preset":
        light = get_light(target_id)
        name = (light.get("name") or light["ip"]) if light else "(foco eliminado)"
        preset = WHITE_PRESETS.get(hotkey.get("preset_key", ""))
        label = preset["label"] if preset else "(preset eliminado)"
        return f"Preset '{label}' — {name}"

    if action == "turn_off_all":
        return "Apagar todos los focos"

    return "Acción desconocida"


# ---------------------------------------------------------------------------
# Tarjetas (focos y habitaciones)
# ---------------------------------------------------------------------------

class LightCard(QFrame):
    clicked = Signal(str)

    def __init__(self, light: dict, parent=None):
        super().__init__(parent)
        self.light_id = light["id"]
        self.setObjectName("LightCard")
        self.setProperty("on", False)
        self.setFixedSize(140, 140)
        self.setCursor(Qt.PointingHandCursor)

        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignCenter)

        self.icon_label = QLabel()
        self.icon_label.setAlignment(Qt.AlignCenter)
        self._glow = _make_glow()
        self.icon_label.setGraphicsEffect(self._glow)
        self._set_icon(BULB_OFF_ICON)  # estado neutro hasta que llegue la respuesta real
        layout.addWidget(self.icon_label)

        name_label = QLabel(light.get("name") or light["ip"])
        name_label.setObjectName("LightName")
        name_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(name_label)

    def _set_icon(self, name: str):
        self.icon_label.setPixmap(icon(name).pixmap(48, 48))

    def set_state(self, is_on: bool | None):
        """is_on=None significa 'no responde'; se muestra apagado igual."""
        self._set_icon(BULB_ON_ICON if is_on else BULB_OFF_ICON)
        self._glow.setEnabled(bool(is_on))
        self.setProperty("on", bool(is_on))
        _refresh_style(self)

    def mousePressEvent(self, event):
        self.clicked.emit(self.light_id)
        super().mousePressEvent(event)


class RoomCard(QFrame):
    """
    Igual que LightCard, pero representa una Habitación: además del ícono
    on/off (con resplandor + borde dorado si hay algo prendido), muestra
    una barra con el brillo promedio de los focos encendidos. Es más
    grande que LightCard a propósito (2 por fila en vez de 3).
    """

    clicked = Signal(str)

    def __init__(self, room: dict, parent=None):
        super().__init__(parent)
        self.room_id = room["id"]
        self.setObjectName("LightCard")  # reusa el mismo estilo que LightCard
        self.setProperty("on", False)
        self.setFixedSize(200, 200)
        self.setCursor(Qt.PointingHandCursor)

        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignCenter)

        self.icon_label = QLabel()
        self.icon_label.setAlignment(Qt.AlignCenter)
        self._glow = _make_glow()
        self.icon_label.setGraphicsEffect(self._glow)
        self._set_icon(BULB_OFF_ICON)
        layout.addWidget(self.icon_label)

        name_label = QLabel(room.get("name") or room["id"])
        name_label.setObjectName("LightName")
        name_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(name_label)

        self.brightness_bar = QProgressBar()
        self.brightness_bar.setRange(0, 255)
        self.brightness_bar.setTextVisible(False)
        self.brightness_bar.setFixedHeight(6)
        self.brightness_bar.setVisible(False)
        layout.addWidget(self.brightness_bar)

    def _set_icon(self, name: str):
        self.icon_label.setPixmap(icon(name).pixmap(64, 64))

    def set_state(self, is_on: bool, avg_brightness: int | None):
        self._set_icon(BULB_ON_ICON if is_on else BULB_OFF_ICON)
        self._glow.setEnabled(bool(is_on))
        self.setProperty("on", bool(is_on))
        _refresh_style(self)
        if is_on and avg_brightness is not None:
            self.brightness_bar.setValue(avg_brightness)
            self.brightness_bar.setVisible(True)
        else:
            self.brightness_bar.setVisible(False)

    def mousePressEvent(self, event):
        self.clicked.emit(self.room_id)
        super().mousePressEvent(event)


class ColorSwatchButton(QPushButton):
    """
    Cuadradito de color favorito. Click izquierdo = aplicar ese color al
    foco. Click derecho = menú contextual con "Eliminar".

    Se identifica por su posición (index) dentro de la lista de favoritos
    de ese foco, ver core.config.get_favorite_colors/remove_favorite_color.
    """

    remove_requested = Signal(int)

    def __init__(self, index: int, r: int, g: int, b: int, parent=None):
        super().__init__(parent)
        self.index = index
        self.setFixedSize(36, 36)
        self.setToolTip(f"RGB({r}, {g}, {b}) — click derecho para eliminar")
        self.setCursor(Qt.PointingHandCursor)
        self.setStyleSheet(
            f"QPushButton {{ background-color: rgb({r},{g},{b}); "
            f"border: 2px solid #332D22; border-radius: 8px; }}"
            f"QPushButton:hover {{ border: 2px solid #FFC72C; }}"
        )
        self.setContextMenuPolicy(Qt.CustomContextMenu)
        self.customContextMenuRequested.connect(self._show_context_menu)

    def _show_context_menu(self, pos):
        menu = QMenu(self)
        remove_action = menu.addAction("Eliminar")
        chosen = menu.exec(self.mapToGlobal(pos))
        if chosen == remove_action:
            self.remove_requested.emit(self.index)


class HotkeyRow(QFrame):
    """Fila que muestra un atajo configurado: combinación + qué hace + eliminar."""

    remove_requested = Signal(str)

    def __init__(self, hotkey: dict, parent=None):
        super().__init__(parent)
        self.hotkey_id = hotkey["id"]
        self.setObjectName("HotkeyRow")

        layout = QHBoxLayout(self)
        layout.setContentsMargins(14, 10, 10, 10)

        keys_label = QLabel(hotkey.get("keys", ""))
        keys_label.setStyleSheet(f"color: {YELLOW}; font-weight: 600;")
        keys_label.setMinimumWidth(120)
        layout.addWidget(keys_label)

        desc_label = QLabel(_describe_hotkey(hotkey))
        layout.addWidget(desc_label)
        layout.addStretch()

        remove_btn = QPushButton("Eliminar")
        remove_btn.setObjectName("Secondary")
        remove_btn.clicked.connect(lambda: self.remove_requested.emit(self.hotkey_id))
        layout.addWidget(remove_btn)

class SettingsRow(QFrame):
    """Fila clickeable de la pantalla Hub de Configuración: ícono +
    título/subtítulo + badge opcional (contador o versión) + chevron."""

    clicked = Signal()

    def __init__(self, icon_name: str, title: str, subtitle: str,
                 count: int | None = None, version: str | None = None,
                 clickable: bool = True, parent=None):
        super().__init__(parent)
        self.setObjectName("SettingsRow")
        self.setProperty("clickable", clickable)
        self._clickable = clickable
        self.setCursor(Qt.PointingHandCursor if clickable else Qt.ArrowCursor)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(14, 12, 14, 12)
        layout.setSpacing(14)

        badge = QFrame()
        badge.setObjectName("RowIconBadge")
        badge.setFixedSize(40, 40)
        badge_layout = QVBoxLayout(badge)
        badge_layout.setContentsMargins(0, 0, 0, 0)
        badge_layout.setAlignment(Qt.AlignCenter)
        icon_label = QLabel()
        icon_label.setPixmap(_tinted_icon(icon_name, YELLOW, size=20).pixmap(20, 20))
        badge_layout.addWidget(icon_label)
        layout.addWidget(badge)

        text_col = QVBoxLayout()
        text_col.setSpacing(2)
        text_col.addWidget(self._label(title, "RowTitle"))
        text_col.addWidget(self._label(subtitle, "RowSubtitle"))
        layout.addLayout(text_col, 1)

        self.count_label = None
        if count is not None:
            self.count_label = self._label(str(count), "RowCount")
            layout.addWidget(self.count_label)

        if version is not None:
            layout.addWidget(self._label(version, "VersionPill"))

        if clickable:
            layout.addWidget(self._label("\u203a", "RowChevron"))

    @staticmethod
    def _label(text: str, object_name: str) -> QLabel:
        label = QLabel(text)
        label.setObjectName(object_name)
        return label

    def set_count(self, count: int):
        if self.count_label is not None:
            self.count_label.setText(str(count))

    def mousePressEvent(self, event):
        if self._clickable:
            self.clicked.emit()
        super().mousePressEvent(event)

# ---------------------------------------------------------------------------
# Diálogos
# ---------------------------------------------------------------------------

class DiscoverDialog(QDialog):
    """
    Busca focos WiZ nuevos en la red y los agrega a la config, SIN
    asignarlos a ninguna habitación todavía (room_id queda ""). Se
    asignan después desde el botón "+ Agregar" de una habitación (ver
    AssignLightDialog).
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Buscar focos")
        self.setMinimumWidth(360)
        layout = QVBoxLayout(self)

        self.list_widget = QListWidget()
        layout.addWidget(self.list_widget)

        btn_row = QHBoxLayout()
        search_btn = QPushButton("Buscar")
        search_btn.clicked.connect(self.on_search)
        add_btn = QPushButton("Agregar seleccionado")
        add_btn.setObjectName("Primary")
        add_btn.clicked.connect(self.on_add)
        btn_row.addWidget(search_btn)
        btn_row.addWidget(add_btn)
        layout.addLayout(btn_row)

    def on_search(self):
        self.list_widget.clear()
        devices = discover_lights(wait=5)
        for d in devices:
            item = QListWidgetItem(f"{d['ip']}  (MAC: {d['mac']})")
            item.setData(Qt.UserRole, d)
            self.list_widget.addItem(item)
        if not devices:
            QMessageBox.information(self, "Sin resultados", "No se encontró ningún foco.")

    def on_add(self):
        item = self.list_widget.currentItem()
        if not item:
            return
        d = item.data(Qt.UserRole)
        add_or_update_light(light_id=d["mac"], ip=d["ip"])
        self.accept()


class CreateRoomDialog(QDialog):
    """Crea una habitación nueva. El id interno se genera acá, el usuario
    sólo ve/elige el nombre."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Nueva habitación")
        self.setMinimumWidth(320)
        layout = QVBoxLayout(self)

        layout.addWidget(QLabel("Nombre de la habitación:"))
        self.name_input = QLineEdit()
        self.name_input.setPlaceholderText("Ej: Dormitorio, Living...")
        layout.addWidget(self.name_input)

        btn_row = QHBoxLayout()
        cancel_btn = QPushButton("Cancelar")
        cancel_btn.clicked.connect(self.reject)
        create_btn = QPushButton("Crear")
        create_btn.setObjectName("Primary")
        create_btn.clicked.connect(self.on_create)
        btn_row.addWidget(cancel_btn)
        btn_row.addWidget(create_btn)
        layout.addLayout(btn_row)

    def on_create(self):
        name = self.name_input.text().strip()
        if not name:
            QMessageBox.warning(self, "Falta el nombre", "Ingresá un nombre para la habitación.")
            return
        room_id = uuid.uuid4().hex[:8]
        add_or_update_room(room_id, name)
        self.accept()


class AssignLightDialog(QDialog):
    """Asigna un foco ya configurado (pero sin habitación) a esta room."""

    def __init__(self, room_id: str, parent=None):
        super().__init__(parent)
        self.room_id = room_id
        self.setWindowTitle("Agregar dispositivo")
        self.setMinimumWidth(360)
        layout = QVBoxLayout(self)

        self.list_widget = QListWidget()
        unassigned = get_unassigned_lights()
        for light in unassigned:
            item = QListWidgetItem(light.get("name") or light["ip"])
            item.setData(Qt.UserRole, light["id"])
            self.list_widget.addItem(item)
        layout.addWidget(self.list_widget)

        if not unassigned:
            hint = QLabel(
                "No hay focos sin asignar.\nUsá 'Buscar focos' desde el inicio primero."
            )
            hint.setStyleSheet("color: #8A8478;")
            layout.addWidget(hint)

        btn_row = QHBoxLayout()
        cancel_btn = QPushButton("Cancelar")
        cancel_btn.clicked.connect(self.reject)
        add_btn = QPushButton("Asignar")
        add_btn.setObjectName("Primary")
        add_btn.clicked.connect(self.on_assign)
        btn_row.addWidget(cancel_btn)
        btn_row.addWidget(add_btn)
        layout.addLayout(btn_row)

    def on_assign(self):
        item = self.list_widget.currentItem()
        if not item:
            return
        assign_light_to_room(item.data(Qt.UserRole), self.room_id)
        self.accept()


class AddHotkeyDialog(QDialog):
    """
    Flujo: 1) elegir qué hace el atajo, 2) elegir el foco/habitación (y
    el color favorito, si aplica), 3) grabar la combinación de teclas.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Nuevo atajo de teclado")
        self.setMinimumWidth(360)
        layout = QVBoxLayout(self)

        layout.addWidget(QLabel("Acción:"))
        self.action_combo = QComboBox()
        self.action_combo.addItem("Encender/apagar un foco", "toggle_light")
        self.action_combo.addItem("Encender/apagar una habitación", "toggle_room")
        self.action_combo.addItem("Aplicar un color favorito", "apply_favorite_color")
        self.action_combo.addItem("Subir brillo", "brightness_up")
        self.action_combo.addItem("Bajar brillo", "brightness_down")
        self.action_combo.addItem("Aplicar preset de temperatura", "apply_white_preset")
        self.action_combo.addItem("Apagar todos los focos", "turn_off_all")
        self.action_combo.currentIndexChanged.connect(self._rebuild_target_options)
        layout.addWidget(self.action_combo)

        self.target_label = QLabel("Destino:")
        layout.addWidget(self.target_label)
        self.target_combo = QComboBox()
        self.target_combo.currentIndexChanged.connect(self._rebuild_favorite_options)
        layout.addWidget(self.target_combo)

        self.favorite_label = QLabel("Color favorito:")
        self.favorite_combo = QComboBox()
        layout.addWidget(self.favorite_label)
        layout.addWidget(self.favorite_combo)

        self.preset_label = QLabel("Ajustes Predeterminados:")
        self.preset_combo = QComboBox()
        for key, preset in WHITE_PRESETS.items():
            self.preset_combo.addItem(preset["label"], key)
        layout.addWidget(self.preset_label)
        layout.addWidget(self.preset_combo)

        layout.addWidget(QLabel("Combinación de teclas (hacé click y apretá las teclas):"))
        self.key_edit = QKeySequenceEdit()
        layout.addWidget(self.key_edit)

        btn_row = QHBoxLayout()
        cancel_btn = QPushButton("Cancelar")
        cancel_btn.clicked.connect(self.reject)
        save_btn = QPushButton("Guardar")
        save_btn.setObjectName("Primary")
        save_btn.clicked.connect(self.on_save)
        btn_row.addWidget(cancel_btn)
        btn_row.addWidget(save_btn)
        layout.addLayout(btn_row)

        self._rebuild_target_options()

    def _rebuild_target_options(self):
        self.target_combo.clear()
        action = self.action_combo.currentData()

        needs_target = action != "turn_off_all"
        self.target_label.setVisible(needs_target)
        self.target_combo.setVisible(needs_target)

        if action == "toggle_room":
            for room in get_rooms():
                self.target_combo.addItem(room.get("name") or room["id"], room["id"])
        elif needs_target:
            for light in get_lights():
                self.target_combo.addItem(light.get("name") or light["ip"], light["id"])

        self._rebuild_favorite_options()
        self._rebuild_preset_options()

    def _rebuild_favorite_options(self):
        action = self.action_combo.currentData()
        show_favorites = action == "apply_favorite_color"
        self.favorite_label.setVisible(show_favorites)
        self.favorite_combo.setVisible(show_favorites)

        if not show_favorites:
            return

        self.favorite_combo.clear()
        light_id = self.target_combo.currentData()
        if not light_id:
            return
        for i, color in enumerate(get_favorite_colors(light_id)):
            self.favorite_combo.addItem(f"RGB({color['r']}, {color['g']}, {color['b']})", i)

    def _rebuild_preset_options(self):
        show_preset = self.action_combo.currentData() == "apply_white_preset"
        self.preset_label.setVisible(show_preset)
        self.preset_combo.setVisible(show_preset)

    def on_save(self):
        action = self.action_combo.currentData()
        target_id = self.target_combo.currentData() if action != "turn_off_all" else ""
        keys = self.key_edit.keySequence().toString(QKeySequence.PortableText)

        if action != "turn_off_all" and not target_id:
            QMessageBox.warning(self, "Falta el destino", "Elegí un foco o habitación.")
            return
        if not keys:
            QMessageBox.warning(self, "Falta la combinación", "Grabá una combinación de teclas.")
            return

        favorite_index = -1
        if action == "apply_favorite_color":
            favorite_index = self.favorite_combo.currentData()
            if favorite_index is None:
                QMessageBox.warning(
                    self, "Sin favoritos",
                    "Ese foco todavía no tiene colores favoritos guardados."
                )
                return

        preset_key = ""
        if action == "apply_white_preset":
            preset_key = self.preset_combo.currentData()

        direction = ""
        stored_action = action
        if action in ("brightness_up", "brightness_down"):
            stored_action = "adjust_brightness"
            direction = "up" if action == "brightness_up" else "down"

        add_hotkey(
            keys=keys, action=stored_action, target_id=target_id,
            favorite_index=favorite_index, direction=direction, preset_key=preset_key,
        )
        self.accept()


# ---------------------------------------------------------------------------
# Pantalla 1: Home (lista de Habitaciones)
# ---------------------------------------------------------------------------

class HomeScreen(QWidget):
    room_selected = Signal(str)
    settings_requested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._status_thread: QThread | None = None
        self._status_worker: RoomStatusWorker | None = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 24)

        # Fila 1: saludo + configuración.
        greeting_row = QHBoxLayout()
        user_icon = QLabel()
        user_icon.setPixmap(icon("user").pixmap(22, 22))
        greeting_row.addWidget(user_icon)
        greeting_row.addWidget(QLabel("Bienvenido", objectName="Header"))
        greeting_row.addStretch()

        settings_btn = QPushButton()
        settings_btn.setObjectName("IconButton")
        settings_btn.setIcon(icon("settings"))
        settings_btn.setIconSize(QSize(20, 20))
        settings_btn.setToolTip("Configuración")
        settings_btn.clicked.connect(self.settings_requested.emit)
        greeting_row.addWidget(settings_btn)
        layout.addLayout(greeting_row)

        # Fila 2: título + acciones, a la misma altura.
        title_row = QHBoxLayout()
        title = QLabel("Habitaciones")
        title.setObjectName("ScreenTitle")
        title_row.addWidget(title)
        title_row.addStretch()

        discover_btn = QPushButton()
        discover_btn.setObjectName("IconButton")
        discover_btn.setIcon(icon("search"))
        discover_btn.setIconSize(QSize(20, 20))
        discover_btn.setToolTip("Buscar focos nuevos en la red")
        discover_btn.clicked.connect(self.open_discover)
        title_row.addWidget(discover_btn)

        new_room_btn = QPushButton("+ Nueva habitación")
        new_room_btn.setObjectName("Primary")
        new_room_btn.clicked.connect(self.open_create_room)
        title_row.addWidget(new_room_btn)
        layout.addLayout(title_row)

        self.grid = QGridLayout()
        self.grid.setSpacing(16)
        self.grid.setAlignment(Qt.AlignTop | Qt.AlignHCenter)
        grid_container = QWidget()
        grid_container.setLayout(self.grid)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setWidget(grid_container)
        layout.addWidget(scroll)

        self.empty_label = QLabel("Ninguna habitación creada todavía.")
        self.empty_label.setAlignment(Qt.AlignCenter)
        self.empty_label.setStyleSheet("color: #8A8478; margin-top: 40px;")
        layout.addWidget(self.empty_label)

        self.refresh()

    def refresh(self):
        while self.grid.count():
            item = self.grid.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        rooms = get_rooms()
        self.empty_label.setVisible(not rooms)

        cols = 2
        for i, room in enumerate(rooms):
            card = RoomCard(room)
            card.clicked.connect(self.room_selected.emit)
            self.grid.addWidget(card, i // cols, i % cols)

        if rooms:
            self._start_status_check(rooms)

    def _start_status_check(self, rooms: list[dict]):
        if self._status_thread is not None and self._status_thread.isRunning():
            return

        self._status_thread = QThread()
        self._status_worker = RoomStatusWorker(rooms)
        self._status_worker.moveToThread(self._status_thread)

        self._status_thread.started.connect(self._status_worker.run)
        self._status_worker.finished.connect(self._on_status_ready)
        self._status_worker.finished.connect(self._status_thread.quit)
        self._status_worker.finished.connect(self._status_worker.deleteLater)
        self._status_thread.finished.connect(self._status_thread.deleteLater)
        self._status_thread.finished.connect(self._clear_status_thread_ref)

        self._status_thread.start()

    def _clear_status_thread_ref(self):
        self._status_thread = None
        self._status_worker = None

    def _on_status_ready(self, results: dict):
        for i in range(self.grid.count()):
            widget = self.grid.itemAt(i).widget()
            if isinstance(widget, RoomCard) and widget.room_id in results:
                r = results[widget.room_id]
                widget.set_state(r["is_on"], r["avg_brightness"])

    def open_discover(self):
        DiscoverDialog(self).exec()
        # No hace falta refresh(): un foco recién descubierto no tiene
        # room todavía, así que no aparece en este grid de habitaciones.

    def open_create_room(self):
        if CreateRoomDialog(self).exec() == QDialog.Accepted:
            self.refresh()


# ---------------------------------------------------------------------------
# Pantalla 2: Detalle de Habitación (lista de focos de esa room)
# ---------------------------------------------------------------------------

class RoomDetailScreen(QWidget):
    back_requested = Signal()
    light_selected = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.room_id: str | None = None
        self._status_thread: QThread | None = None
        self._status_worker: LightStatusWorker | None = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 24)

        header = QHBoxLayout()
        back_btn = QPushButton()
        back_btn.setObjectName("IconButton")
        back_btn.setIcon(icon("chevron-left"))
        back_btn.setIconSize(QSize(24, 24))
        back_btn.setToolTip("Volver")
        back_btn.clicked.connect(self.back_requested.emit)
        header.addWidget(back_btn)

        self.name_label = QLabel()
        self.name_label.setObjectName("ScreenTitle")
        header.addWidget(self.name_label)
        header.addStretch()

        add_btn = QPushButton("+ Agregar")
        add_btn.setObjectName("CompactAdd")
        add_btn.setToolTip("Agregar un dispositivo a esta habitación")
        add_btn.clicked.connect(self.open_assign_light)
        header.addWidget(add_btn)

        self.room_toggle_btn = QPushButton()
        self.room_toggle_btn.setObjectName("IconButton")
        self.room_toggle_btn.setIcon(icon("power"))
        self.room_toggle_btn.setIconSize(QSize(22, 22))
        self.room_toggle_btn.setToolTip("Encender/apagar toda la habitación")
        self.room_toggle_btn.clicked.connect(self.on_toggle_room)
        header.addWidget(self.room_toggle_btn)
        layout.addLayout(header)

        self.grid = QGridLayout()
        self.grid.setSpacing(16)
        self.grid.setAlignment(Qt.AlignTop | Qt.AlignLeft)
        grid_container = QWidget()
        grid_container.setLayout(self.grid)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setWidget(grid_container)
        layout.addWidget(scroll)

        self.empty_label = QLabel("Ningún foco asignado a esta habitación todavía.")
        self.empty_label.setAlignment(Qt.AlignCenter)
        self.empty_label.setStyleSheet("color: #8A8478; margin-top: 40px;")
        layout.addWidget(self.empty_label)

    def load_room(self, room_id: str):
        self.room_id = room_id
        room = get_room(room_id)
        self.name_label.setText((room.get("name") if room else None) or room_id)
        self.refresh()

    def refresh(self):
        if self.room_id is None:
            return

        while self.grid.count():
            item = self.grid.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        lights = get_lights_in_room(self.room_id)
        self.empty_label.setVisible(not lights)

        cols = 3
        for i, light in enumerate(lights):
            card = LightCard(light)
            card.clicked.connect(self.light_selected.emit)
            self.grid.addWidget(card, i // cols, i % cols)

        if lights:
            self._start_status_check(lights)

    def _start_status_check(self, lights: list[dict]):
        if self._status_thread is not None and self._status_thread.isRunning():
            return

        self._status_thread = QThread()
        self._status_worker = LightStatusWorker(lights)
        self._status_worker.moveToThread(self._status_thread)

        self._status_thread.started.connect(self._status_worker.run)
        self._status_worker.finished.connect(self._on_status_ready)
        self._status_worker.finished.connect(self._status_thread.quit)
        self._status_worker.finished.connect(self._status_worker.deleteLater)
        self._status_thread.finished.connect(self._status_thread.deleteLater)
        self._status_thread.finished.connect(self._clear_status_thread_ref)

        self._status_thread.start()

    def _clear_status_thread_ref(self):
        self._status_thread = None
        self._status_worker = None

    def _on_status_ready(self, results: dict):
        for i in range(self.grid.count()):
            widget = self.grid.itemAt(i).widget()
            if isinstance(widget, LightCard) and widget.light_id in results:
                widget.set_state(results[widget.light_id])

    def on_toggle_room(self):
        if self.room_id is None:
            return
        try:
            toggle_room_status(self.room_id)
        finally:
            # Se refresca aunque algún foco haya tirado LightUnreachableError
            # (ver core/rooms.py: un foco caído no frena a los demás).
            self.refresh()

    def open_assign_light(self):
        if self.room_id is None:
            return
        if AssignLightDialog(self.room_id, self).exec() == QDialog.Accepted:
            self.refresh()


# ---------------------------------------------------------------------------
# Pantalla 3: Detalle de Dispositivo
# ---------------------------------------------------------------------------

class LightDetailScreen(QWidget):
    back_requested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.light: Light | None = None
        self.light_id: str | None = None

        outer_layout = QVBoxLayout(self)
        outer_layout.setContentsMargins(0, 0, 0, 0)
        outer_layout.setSpacing(0)

        # --- Header fijo (no scrollea) ---
        header_container = QWidget()
        header_layout = QHBoxLayout(header_container)
        header_layout.setContentsMargins(24, 20, 24, 8)
        back_btn = QPushButton()
        back_btn.setObjectName("IconButton")
        back_btn.setIcon(icon("chevron-left"))
        back_btn.setIconSize(QSize(24, 24))
        back_btn.setToolTip("Volver")
        back_btn.clicked.connect(self.back_requested.emit)
        header_layout.addWidget(back_btn)
        header_layout.addStretch()
        outer_layout.addWidget(header_container)

        # --- Contenido scrolleable ---
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        outer_layout.addWidget(scroll)

        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setContentsMargins(24, 0, 24, 24)
        layout.setSpacing(14)
        scroll.setWidget(content)

        self.name_label = QLabel()
        self.name_label.setObjectName("ScreenTitle")
        layout.addWidget(self.name_label)

        # --- Panel "hero": ícono + toggle principal ---
        hero = QFrame()
        hero.setObjectName("HeroPanel")
        hero_layout = QVBoxLayout(hero)
        hero_layout.setContentsMargins(20, 24, 20, 20)
        hero_layout.setAlignment(Qt.AlignCenter)

        self.state_icon = QLabel()
        self.state_icon.setAlignment(Qt.AlignCenter)
        self._state_glow = _make_glow(blur=36)
        self.state_icon.setGraphicsEffect(self._state_glow)
        hero_layout.addWidget(self.state_icon)

        toggle_row = QHBoxLayout()
        toggle_row.addStretch()
        self.toggle_btn = QPushButton()
        self.toggle_btn.setObjectName("PowerToggleButton")
        self.toggle_btn.setProperty("on", False)
        self.toggle_btn.setIconSize(QSize(24, 24))
        self.toggle_btn.setFixedSize(44, 44)
        self.toggle_btn.clicked.connect(self.on_toggle)
        toggle_row.addWidget(self.toggle_btn)
        toggle_row.addStretch()
        hero_layout.addLayout(toggle_row)

        layout.addWidget(hero)

        layout.addWidget(_section_label("Brillo"))
        self.brightness_slider = QSlider(Qt.Horizontal)
        self.brightness_slider.setRange(0, 255)
        self.brightness_slider.sliderReleased.connect(self.on_brightness_changed)
        layout.addWidget(self.brightness_slider)

        layout.addWidget(_section_label("Temperatura de color"))
        self.temp_slider = QSlider(Qt.Horizontal)
        self.temp_slider.setRange(Light.MIN_COLOR_TEMP, Light.MAX_COLOR_TEMP)
        self.temp_slider.setValue(4000)  # blanco neutro como default visual
        self.temp_slider.sliderReleased.connect(self.on_temp_changed)
        layout.addWidget(self.temp_slider)

        # --- Presets "ajustes predefinidos" (ícono arriba, texto abajo) ---
        layout.addWidget(_section_label("ajustes predefinidos"))
        white_grid = QGridLayout()
        white_grid.setSpacing(8)
        white_grid.setColumnStretch(0, 1)
        white_grid.setColumnStretch(1, 1)
        for i, (key, preset) in enumerate(WHITE_PRESETS.items()):
            btn = QToolButton()
            btn.setObjectName("PresetButton")
            btn.setText(preset["label"])
            btn.setIcon(icon(preset["icon"]))
            btn.setIconSize(QSize(26, 26))
            btn.setToolButtonStyle(Qt.ToolButtonTextUnderIcon)
            btn.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
            btn.setCursor(Qt.PointingHandCursor)
            kelvin = preset["kelvin"]
            btn.clicked.connect(lambda checked=False, k=kelvin: self.on_white_preset(k))
            white_grid.addWidget(btn, i // 2, i % 2)
        layout.addLayout(white_grid)

        # --- Favoritos (colores RGB guardados por el usuario) ---
        favorites_header = QHBoxLayout()
        favorites_header.addWidget(_section_label("Favoritos"))
        favorites_header.addStretch()
        add_favorite_btn = QPushButton("+ Guardar color")
        add_favorite_btn.setObjectName("CompactAdd")
        add_favorite_btn.clicked.connect(self.on_add_favorite)
        favorites_header.addWidget(add_favorite_btn)
        layout.addLayout(favorites_header)

        self.favorites_grid = QGridLayout()
        self.favorites_grid.setSpacing(8)
        self.favorites_grid.setAlignment(Qt.AlignLeft)
        layout.addLayout(self.favorites_grid)

        self.favorites_empty_label = QLabel("Todavía no guardaste ningún color.")
        self.favorites_empty_label.setStyleSheet("color: #8A8478;")
        layout.addWidget(self.favorites_empty_label)

        color_btn = QPushButton("Elegir color...")
        color_btn.setObjectName("Primary")
        color_btn.clicked.connect(self.on_pick_color)
        layout.addWidget(color_btn)

        self.status_label = QLabel("Estado: —")
        self.status_label.setStyleSheet("color: #8A8478;")
        layout.addWidget(self.status_label)

        layout.addStretch()

    def load_light(self, light_id: str):
        data = get_light(light_id)
        if data is None:
            return
        self.light_id = light_id
        self.light = Light(data["ip"])
        self.name_label.setText(data.get("name") or data["ip"])
        self.refresh_status()
        self.refresh_favorites()

    def refresh_status(self):
        try:
            status = self.light.get_status()
        except LightUnreachableError as e:
            self.status_label.setText("Estado: no responde")
            QMessageBox.warning(self, "Foco no responde", str(e))
            return

        self._apply_state(status["is_on"])
        self.status_label.setText(f"Estado: {'encendido' if status['is_on'] else 'apagado'}")

        if status["brightness"] is not None:
            self.brightness_slider.setValue(status["brightness"])

        if status["colortemp"] is not None:
            self.temp_slider.setValue(status["colortemp"])

    def refresh_favorites(self):
        while self.favorites_grid.count():
            item = self.favorites_grid.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        favorites = get_favorite_colors(self.light_id) if self.light_id else []
        self.favorites_empty_label.setVisible(not favorites)

        cols = 8
        for i, color in enumerate(favorites):
            swatch = ColorSwatchButton(i, color["r"], color["g"], color["b"])
            swatch.clicked.connect(
                lambda checked=False, c=color: self.on_apply_favorite(c["r"], c["g"], c["b"])
            )
            swatch.remove_requested.connect(self.on_remove_favorite)
            self.favorites_grid.addWidget(swatch, i // cols, i % cols)

    def _apply_state(self, is_on: bool):
        self.state_icon.setPixmap(icon(BULB_ON_ICON if is_on else BULB_OFF_ICON).pixmap(96, 96))
        self._state_glow.setEnabled(bool(is_on))

        # El power.svg es blanco fijo, así que para que se vea amarillo
        # cuando está prendido lo reteñimos por código (ver _tinted_icon)
        # en vez de necesitar un segundo archivo .svg.
        self.toggle_btn.setIcon(_tinted_icon("power", YELLOW if is_on else WHITE, size=24))
        self.toggle_btn.setProperty("on", bool(is_on))
        _refresh_style(self.toggle_btn)

    def on_toggle(self):
        try:
            (self.light.turn_off() if self.light.is_on() else self.light.turn_on())
            self.refresh_status()
        except LightUnreachableError as e:
            QMessageBox.warning(self, "Foco no responde", str(e))

    def on_brightness_changed(self):
        try:
            self.light.set_brightness(self.brightness_slider.value())
        except LightUnreachableError as e:
            QMessageBox.warning(self, "Foco no responde", str(e))

    def on_temp_changed(self):
        try:
            self.light.set_color_temp(self.temp_slider.value())
            self.refresh_status()
        except LightUnreachableError as e:
            QMessageBox.warning(self, "Foco no responde", str(e))

    def on_pick_color(self):
        color = QColorDialog.getColor()
        if not color.isValid():
            return
        try:
            self.light.set_color(color.red(), color.green(), color.blue())
            self.refresh_status()
        except LightUnreachableError as e:
            QMessageBox.warning(self, "Foco no responde", str(e))

    def on_white_preset(self, kelvin: int):
        try:
            self.light.set_color_temp(kelvin)
            self.refresh_status()
        except LightUnreachableError as e:
            QMessageBox.warning(self, "Foco no responde", str(e))

    def on_add_favorite(self):
        """
        Abre el mismo color picker que 'Elegir color...': el color elegido
        se guarda como favorito Y se aplica al foco de una vez (evita tener
        que elegirlo dos veces si el usuario ya lo quiere ver puesto).
        """
        if self.light_id is None:
            return
        color = QColorDialog.getColor()
        if not color.isValid():
            return

        add_favorite_color(self.light_id, color.red(), color.green(), color.blue())
        self.refresh_favorites()

        try:
            self.light.set_color(color.red(), color.green(), color.blue())
            self.refresh_status()
        except LightUnreachableError as e:
            QMessageBox.warning(self, "Foco no responde", str(e))

    def on_apply_favorite(self, r: int, g: int, b: int):
        try:
            self.light.set_color(r, g, b)
            self.refresh_status()
        except LightUnreachableError as e:
            QMessageBox.warning(self, "Foco no responde", str(e))

    def on_remove_favorite(self, index: int):
        if self.light_id is None:
            return
        remove_favorite_color(self.light_id, index)
        self.refresh_favorites()


# ---------------------------------------------------------------------------
# Pantalla 4: Configuración (por ahora: atajos de teclado de Windows)
# ---------------------------------------------------------------------------

class SettingsScreen(QWidget):
    """Hub de Configuración: entrada a cada sub-sección."""

    back_requested = Signal()
    hotkeys_requested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 24)
        layout.setSpacing(6)

        header = QHBoxLayout()
        back_btn = QPushButton()
        back_btn.setObjectName("IconButton")
        back_btn.setIcon(icon("chevron-left"))
        back_btn.setIconSize(QSize(24, 24))
        back_btn.setToolTip("Volver")
        back_btn.clicked.connect(self.back_requested.emit)
        header.addWidget(back_btn)
        header.addStretch()
        layout.addLayout(header)

        title = QLabel("Configuración")
        title.setObjectName("ScreenTitle")
        layout.addWidget(title)
        layout.addSpacing(6)

        layout.addWidget(_section_label("Control"))
        self.hotkeys_row = SettingsRow(
            "keyboard", "Atajos de teclado", "Combinaciones globales — Windows",
        )
        self.hotkeys_row.clicked.connect(self.hotkeys_requested.emit)
        layout.addWidget(self.hotkeys_row)

        layout.addSpacing(10)
        layout.addWidget(_section_label("Información"))
        about_row = SettingsRow(
            "info", "Spotlight-Key", "Control local de focos WiZ",
            version="v0.4.0", clickable=False,
        )
        layout.addWidget(about_row)

        layout.addStretch()
        self.refresh()

    def refresh(self):
        self.hotkeys_row.set_count(len(get_hotkeys()))


class HotkeysScreen(QWidget):
    """Ex-contenido de SettingsScreen: gestión de atajos, ahora su propia pantalla."""

    back_requested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 24)
        layout.setSpacing(12)

        header = QHBoxLayout()
        back_btn = QPushButton()
        back_btn.setObjectName("IconButton")
        back_btn.setIcon(icon("chevron-left"))
        back_btn.setIconSize(QSize(24, 24))
        back_btn.setToolTip("Volver a Configuración")
        back_btn.clicked.connect(self.back_requested.emit)
        header.addWidget(back_btn)

        title = QLabel("Atajos de teclado")
        title.setObjectName("ScreenTitle")
        header.addWidget(title)
        header.addStretch()

        add_hotkey_btn = QPushButton("+ Agregar atajo")
        add_hotkey_btn.setObjectName("CompactAdd")
        add_hotkey_btn.clicked.connect(self.open_add_hotkey)
        header.addWidget(add_hotkey_btn)
        layout.addLayout(header)

        note = QLabel(
            "Funcionan mientras el ícono de la bandeja esté activo "
            "(python -m tray). En Linux se configuran distinto, desde el "
            "propio compositor — todavía no implementado acá."
        )
        note.setObjectName("PlatformNote")
        note.setWordWrap(True)
        layout.addWidget(note)

        self.hotkeys_list = QVBoxLayout()
        self.hotkeys_list.setSpacing(8)
        layout.addLayout(self.hotkeys_list)

        self.empty_label = QLabel("Todavía no configuraste ningún atajo.")
        self.empty_label.setStyleSheet(f"color: {TEXT_SECONDARY};")
        layout.addWidget(self.empty_label)

        layout.addStretch()
        self.refresh()

    def refresh(self):
        while self.hotkeys_list.count():
            item = self.hotkeys_list.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        hotkeys = get_hotkeys()
        self.empty_label.setVisible(not hotkeys)

        for hotkey in hotkeys:
            row = HotkeyRow(hotkey)
            row.remove_requested.connect(self.on_remove_hotkey)
            self.hotkeys_list.addWidget(row)

    def open_add_hotkey(self):
        if AddHotkeyDialog(self).exec() == QDialog.Accepted:
            self.refresh()

    def on_remove_hotkey(self, hotkey_id: str):
        remove_hotkey(hotkey_id)
        self.refresh()

# ---------------------------------------------------------------------------
# Ventana principal: navegación Home -> Habitación -> Foco / Configuración
# ---------------------------------------------------------------------------

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Spotlight-Key")
        self.setMinimumSize(420, 600)
        self.setWindowIcon(icon(BULB_ON_ICON))
        self.resize(520, 780)  # tamaño inicial cómodo; sin esto Qt abre en el mínimo

        self.stack = QStackedWidget()
        self.setCentralWidget(self.stack)

        self.home = HomeScreen()
        self.room_detail = RoomDetailScreen()
        self.light_detail = LightDetailScreen()
        self.settings = SettingsScreen()
        self.hotkeys_screen = HotkeysScreen()          
        self.stack.addWidget(self.home)
        self.stack.addWidget(self.room_detail)
        self.stack.addWidget(self.light_detail)
        self.stack.addWidget(self.settings)
        self.stack.addWidget(self.hotkeys_screen)     

        self.home.room_selected.connect(self.open_room)
        self.home.settings_requested.connect(self.open_settings)
        self.room_detail.back_requested.connect(self.open_home)
        self.room_detail.light_selected.connect(self.open_light)
        self.light_detail.back_requested.connect(self.open_room_from_light)
        self.settings.back_requested.connect(self.open_home)
        self.settings.hotkeys_requested.connect(self.open_hotkeys)  
        self.hotkeys_screen.back_requested.connect(self.open_settings)  

    def open_hotkeys(self):
        self.hotkeys_screen.refresh()
        self.stack.setCurrentWidget(self.hotkeys_screen)

    def open_room(self, room_id: str):
        self.room_detail.load_room(room_id)
        self.stack.setCurrentWidget(self.room_detail)

    def open_home(self):
        self.home.refresh()
        self.stack.setCurrentWidget(self.home)

    def open_light(self, light_id: str):
        self.light_detail.load_light(light_id)
        self.stack.setCurrentWidget(self.light_detail)

    def open_settings(self):
        self.settings.refresh()
        self.stack.setCurrentWidget(self.settings)

    def open_room_from_light(self):
        # Vuelve a la habitación desde la que se entró al detalle del foco.
        # Si por algún motivo no hay una room cargada (no debería pasar en
        # el flujo normal), vuelve al Home como fallback seguro.
        if self.room_detail.room_id:
            self.room_detail.refresh()
            self.stack.setCurrentWidget(self.room_detail)
        else:
            self.open_home()


def main():
    if sys.platform == "win32":
        # Sin esto, la barra de tareas de Windows sigue mostrando el
        # ícono genérico de python.exe aunque la ventana tenga el suyo
        # propio (ver setWindowIcon en MainWindow) — Windows la agrupa
        # por este id, no por el ícono. Tiene que llamarse ANTES de
        # crear la QApplication.
        try:
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(
                "spotlightkey.spotlightkey.app.1"
            )
        except Exception:
            pass

    app = QApplication(sys.argv)
    app.setWindowIcon(icon(BULB_ON_ICON))
    app.setStyleSheet(STYLESHEET)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()