import sys
import uuid

from PySide6.QtCore import Qt, Signal, QSize, QThread
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QStackedWidget,
    QVBoxLayout, QHBoxLayout, QGridLayout, QLabel, QPushButton,
    QFrame, QScrollArea, QSlider, QColorDialog, QMessageBox, QDialog,
    QListWidget, QListWidgetItem, QProgressBar, QLineEdit, QMenu, QInputDialog,
)

from core.config import (
    get_lights, get_light, add_or_update_light,
    get_rooms, get_room, add_or_update_room,
    get_lights_in_room, get_unassigned_lights, assign_light_to_room,
    get_favorite_colors, add_favorite_color, remove_favorite_color,
    rename_light, rename_room,
)
from core.device import Light, LightUnreachableError
from core.discovery import discover_lights
from core.rooms import get_room_status, toggle_room as toggle_room_status
from core.presets import WHITE_PRESETS
from gui.theme import STYLESHEET
from gui.icons import icon
from gui.workers import LightStatusWorker, RoomStatusWorker


# ---------------------------------------------------------------------------
# Tarjetas (focos y habitaciones)
# ---------------------------------------------------------------------------

class LightCard(QFrame):
    clicked = Signal(str)
    rename_requested = Signal(str)

    def __init__(self, light: dict, parent=None):
        super().__init__(parent)
        self.light_id = light["id"]
        self._light = light
        self.setObjectName("LightCard")
        self.setFixedSize(140, 140)
        self.setCursor(Qt.PointingHandCursor)
        self.setContextMenuPolicy(Qt.CustomContextMenu)
        self.customContextMenuRequested.connect(self._show_context_menu)

        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignCenter)

        self.icon_label = QLabel()
        self.icon_label.setAlignment(Qt.AlignCenter)
        self._set_icon("lightbulb-off")  # estado neutro hasta que llegue la respuesta real
        layout.addWidget(self.icon_label)

        self.name_label = QLabel(light.get("name") or light["ip"])
        self.name_label.setObjectName("LightName")
        self.name_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.name_label)

    def _set_icon(self, name: str):
        self.icon_label.setPixmap(icon(name).pixmap(48, 48))

    def set_name(self, name: str):
        self.name_label.setText(name)
        self._light["name"] = name

    def rename(self):
        current_name = self._light.get("name") or self._light["ip"]
        new_name, ok = QInputDialog.getText(
            self,
            "Renombrar foco",
            "Nombre del foco:",
            text=current_name,
        )
        if not ok:
            return
        cleaned = new_name.strip()
        if not cleaned:
            QMessageBox.warning(self, "Falta el nombre", "Ingresá un nombre para el foco.")
            return
        rename_light(self.light_id, cleaned)
        self.set_name(cleaned)
        self.rename_requested.emit(self.light_id)

    def _show_context_menu(self, pos):
        menu = QMenu(self)
        rename_action = menu.addAction("Renombrar")
        action = menu.exec(self.mapToGlobal(pos))
        if action == rename_action:
            self.rename()

    def set_state(self, is_on: bool | None):
        """is_on=None significa 'no responde'; se muestra apagado igual."""
        self._set_icon("lightbulb" if is_on else "lightbulb-off")

    def mousePressEvent(self, event):
        self.clicked.emit(self.light_id)
        super().mousePressEvent(event)


class RoomCard(QFrame):
    """
    Igual que LightCard, pero representa una Habitación: además del ícono
    on/off, muestra una barra con el brillo promedio de los focos
    encendidos (equivalente a la barra celeste de la app oficial de WiZ).
    """

    clicked = Signal(str)
    rename_requested = Signal(str)

    def __init__(self, room: dict, parent=None):
        super().__init__(parent)
        self.room_id = room["id"]
        self._room = room
        self.setObjectName("LightCard")  # reusa el mismo estilo que LightCard
        self.setFixedSize(140, 140)
        self.setCursor(Qt.PointingHandCursor)
        self.setContextMenuPolicy(Qt.CustomContextMenu)
        self.customContextMenuRequested.connect(self._show_context_menu)

        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignCenter)

        self.icon_label = QLabel()
        self.icon_label.setAlignment(Qt.AlignCenter)
        self._set_icon("lightbulb-off")
        layout.addWidget(self.icon_label)

        self.name_label = QLabel(room.get("name") or room["id"])
        self.name_label.setObjectName("LightName")
        self.name_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.name_label)

        self.brightness_bar = QProgressBar()
        self.brightness_bar.setRange(0, 255)
        self.brightness_bar.setTextVisible(False)
        self.brightness_bar.setFixedHeight(6)
        self.brightness_bar.setVisible(False)
        layout.addWidget(self.brightness_bar)

    def _set_icon(self, name: str):
        self.icon_label.setPixmap(icon(name).pixmap(48, 48))

    def set_name(self, name: str):
        self.name_label.setText(name)
        self._room["name"] = name

    def rename(self):
        current_name = self._room.get("name") or self._room["id"]
        new_name, ok = QInputDialog.getText(
            self,
            "Renombrar habitación",
            "Nombre de la habitación:",
            text=current_name,
        )
        if not ok:
            return
        cleaned = new_name.strip()
        if not cleaned:
            QMessageBox.warning(self, "Falta el nombre", "Ingresá un nombre para la habitación.")
            return
        rename_room(self.room_id, cleaned)
        self.set_name(cleaned)
        self.rename_requested.emit(self.room_id)

    def _show_context_menu(self, pos):
        menu = QMenu(self)
        rename_action = menu.addAction("Renombrar")
        action = menu.exec(self.mapToGlobal(pos))
        if action == rename_action:
            self.rename()

    def set_state(self, is_on: bool, avg_brightness: int | None):
        self._set_icon("lightbulb" if is_on else "lightbulb-off")
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
            f"border: 2px solid #444; border-radius: 8px; }}"
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


# ---------------------------------------------------------------------------
# Diálogos
# ---------------------------------------------------------------------------

class DiscoverDialog(QDialog):
    """
    Busca focos WiZ nuevos en la red y los agrega a la config, SIN
    asignarlos a ninguna habitación todavía (room_id queda ""). Se
    asignan después desde el botón "+ Agregar dispositivo" de una
    habitación (ver AssignLightDialog).
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
                "No hay focos sin asignar.\nUsá '+ Buscar focos' desde el inicio primero."
            )
            hint.setStyleSheet("color: gray;")
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


# ---------------------------------------------------------------------------
# Pantalla 1: Home (lista de Habitaciones)
# ---------------------------------------------------------------------------

class HomeScreen(QWidget):
    room_selected = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._status_thread: QThread | None = None
        self._status_worker: RoomStatusWorker | None = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 24)

        header = QHBoxLayout()
        user_icon = QLabel()
        user_icon.setPixmap(icon("user").pixmap(22, 22))
        header.addWidget(user_icon)
        header.addWidget(QLabel("Hola user", objectName="Header"))
        header.addStretch()
        discover_btn = QPushButton("+ Buscar focos")
        discover_btn.clicked.connect(self.open_discover)
        header.addWidget(discover_btn)
        new_room_btn = QPushButton("+ Nueva habitación")
        new_room_btn.setObjectName("Primary")
        new_room_btn.clicked.connect(self.open_create_room)
        header.addWidget(new_room_btn)
        layout.addLayout(header)

        title = QLabel("Habitaciones")
        title.setObjectName("ScreenTitle")
        layout.addWidget(title)

        self.grid = QGridLayout()
        self.grid.setSpacing(16)
        grid_container = QWidget()
        grid_container.setLayout(self.grid)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setWidget(grid_container)
        layout.addWidget(scroll)

        self.empty_label = QLabel("Ninguna habitación creada todavía.")
        self.empty_label.setAlignment(Qt.AlignCenter)
        self.empty_label.setStyleSheet("color: gray; margin-top: 40px;")
        layout.addWidget(self.empty_label)

        self.refresh()

    def refresh(self):
        while self.grid.count():
            item = self.grid.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        rooms = get_rooms()
        self.empty_label.setVisible(not rooms)

        cols = 3
        for i, room in enumerate(rooms):
            card = RoomCard(room)
            card.clicked.connect(self.room_selected.emit)
            card.rename_requested.connect(lambda _room_id=None, _card=card: self.refresh())
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
    room_renamed = Signal()

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

        rename_btn = QPushButton()
        rename_btn.setObjectName("IconButton")
        rename_btn.setIcon(icon("pencil"))
        rename_btn.setIconSize(QSize(20, 20))
        rename_btn.setToolTip("Renombrar habitación")
        rename_btn.clicked.connect(self.rename_room)
        header.addWidget(rename_btn)
        header.addStretch()

        self.room_toggle_btn = QPushButton()
        self.room_toggle_btn.setObjectName("IconButton")
        self.room_toggle_btn.setIcon(icon("power"))
        self.room_toggle_btn.setIconSize(QSize(24, 24))
        self.room_toggle_btn.setToolTip("Encender/apagar toda la habitación")
        self.room_toggle_btn.clicked.connect(self.on_toggle_room)
        header.addWidget(self.room_toggle_btn)
        layout.addLayout(header)

        add_btn = QPushButton("+ Agregar dispositivo")
        add_btn.setObjectName("Primary")
        add_btn.clicked.connect(self.open_assign_light)
        layout.addWidget(add_btn)

        self.grid = QGridLayout()
        self.grid.setSpacing(16)
        grid_container = QWidget()
        grid_container.setLayout(self.grid)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setWidget(grid_container)
        layout.addWidget(scroll)

        self.empty_label = QLabel("Ningún foco asignado a esta habitación todavía.")
        self.empty_label.setAlignment(Qt.AlignCenter)
        self.empty_label.setStyleSheet("color: gray; margin-top: 40px;")
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
            card.rename_requested.connect(lambda _light_id=None, _card=card: self.refresh())
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

    def rename_room(self):
        if self.room_id is None:
            return
        room = get_room(self.room_id)
        current_name = (room.get("name") if room else None) or self.room_id
        new_name, ok = QInputDialog.getText(
            self,
            "Renombrar habitación",
            "Nombre de la habitación:",
            text=current_name,
        )
        if not ok:
            return
        cleaned = new_name.strip()
        if not cleaned:
            QMessageBox.warning(self, "Falta el nombre", "Ingresá un nombre para la habitación.")
            return
        rename_room(self.room_id, cleaned)
        self.name_label.setText(cleaned)
        self.room_renamed.emit()

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
    light_renamed = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.light: Light | None = None
        self.light_id: str | None = None
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
        header.addStretch()
        layout.addLayout(header)

        header = QHBoxLayout()
        self.name_label = QLabel()
        self.name_label.setObjectName("ScreenTitle")
        header.addWidget(self.name_label)

        rename_btn = QPushButton()
        rename_btn.setObjectName("IconButton")
        rename_btn.setIcon(icon("pencil"))
        rename_btn.setIconSize(QSize(20, 20))
        rename_btn.setToolTip("Renombrar foco")
        rename_btn.clicked.connect(self.rename_light)
        header.addWidget(rename_btn)
        header.addStretch()
        layout.addLayout(header)

        self.state_icon = QLabel()
        self.state_icon.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.state_icon)

        toggle_row = QHBoxLayout()
        toggle_row.addStretch()
        self.toggle_btn = QPushButton()
        self.toggle_btn.setObjectName("IconButton")
        self.toggle_btn.setIconSize(QSize(40, 40))
        self.toggle_btn.clicked.connect(self.on_toggle)
        toggle_row.addWidget(self.toggle_btn)
        toggle_row.addStretch()
        layout.addLayout(toggle_row)

        layout.addWidget(QLabel("Brillo"))
        self.brightness_slider = QSlider(Qt.Horizontal)
        self.brightness_slider.setRange(0, 255)
        self.brightness_slider.sliderReleased.connect(self.on_brightness_changed)
        layout.addWidget(self.brightness_slider)

        layout.addWidget(QLabel("Temperatura de color"))
        self.temp_slider = QSlider(Qt.Horizontal)
        self.temp_slider.setRange(Light.MIN_COLOR_TEMP, Light.MAX_COLOR_TEMP)
        self.temp_slider.setValue(4000)  # blanco neutro como default visual
        self.temp_slider.sliderReleased.connect(self.on_temp_changed)
        layout.addWidget(self.temp_slider)

        # --- Presets "Blanco" (temperatura de color fija) ---
        layout.addWidget(QLabel("Blanco"))
        white_grid = QGridLayout()
        white_grid.setSpacing(8)
        for i, (key, preset) in enumerate(WHITE_PRESETS.items()):
            btn = QPushButton(preset["label"])
            kelvin = preset["kelvin"]
            btn.clicked.connect(lambda checked=False, k=kelvin: self.on_white_preset(k))
            white_grid.addWidget(btn, i // 2, i % 2)
        layout.addLayout(white_grid)

        # --- Favoritos (colores RGB guardados por el usuario) ---
        favorites_header = QHBoxLayout()
        favorites_header.addWidget(QLabel("Favoritos"))
        favorites_header.addStretch()
        add_favorite_btn = QPushButton("+ Guardar color")
        add_favorite_btn.clicked.connect(self.on_add_favorite)
        favorites_header.addWidget(add_favorite_btn)
        layout.addLayout(favorites_header)

        self.favorites_grid = QGridLayout()
        self.favorites_grid.setSpacing(8)
        self.favorites_grid.setAlignment(Qt.AlignLeft)
        layout.addLayout(self.favorites_grid)

        self.favorites_empty_label = QLabel("Todavía no guardaste ningún color.")
        self.favorites_empty_label.setStyleSheet("color: gray;")
        layout.addWidget(self.favorites_empty_label)

        color_btn = QPushButton("Elegir color...")
        color_btn.setObjectName("Primary")
        color_btn.clicked.connect(self.on_pick_color)
        layout.addWidget(color_btn)

        layout.addStretch()
        self.status_label = QLabel("Estado: —")
        layout.addWidget(self.status_label)

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

    def rename_light(self):
        if self.light_id is None:
            return
        data = get_light(self.light_id)
        current_name = (data.get("name") if data else None) or data["ip"] if data else self.light_id
        new_name, ok = QInputDialog.getText(
            self,
            "Renombrar foco",
            "Nombre del foco:",
            text=current_name,
        )
        if not ok:
            return
        cleaned = new_name.strip()
        if not cleaned:
            QMessageBox.warning(self, "Falta el nombre", "Ingresá un nombre para el foco.")
            return
        rename_light(self.light_id, cleaned)
        self.name_label.setText(cleaned)
        self.light_renamed.emit()

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
        self.state_icon.setPixmap(icon("lightbulb" if is_on else "lightbulb-off").pixmap(96, 96))
        self.toggle_btn.setIcon(icon("toggle-right" if is_on else "toggle-left"))

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
# Ventana principal: navegación Home -> Habitación -> Foco
# ---------------------------------------------------------------------------

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Spotlight-Key")
        self.setMinimumSize(480, 560)

        self.stack = QStackedWidget()
        self.setCentralWidget(self.stack)

        self.home = HomeScreen()
        self.room_detail = RoomDetailScreen()
        self.light_detail = LightDetailScreen()
        self.stack.addWidget(self.home)
        self.stack.addWidget(self.room_detail)
        self.stack.addWidget(self.light_detail)

        self.home.room_selected.connect(self.open_room)
        self.room_detail.back_requested.connect(self.open_home)
        self.room_detail.light_selected.connect(self.open_light)
        self.room_detail.room_renamed.connect(self.home.refresh)
        self.light_detail.back_requested.connect(self.open_room_from_light)
        self.light_detail.light_renamed.connect(self.room_detail.refresh)
        self.light_detail.light_renamed.connect(self.home.refresh)

    def open_room(self, room_id: str):
        self.room_detail.load_room(room_id)
        self.stack.setCurrentWidget(self.room_detail)

    def open_home(self):
        self.home.refresh()
        self.stack.setCurrentWidget(self.home)

    def open_light(self, light_id: str):
        self.light_detail.load_light(light_id)
        self.stack.setCurrentWidget(self.light_detail)

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
    app = QApplication(sys.argv)
    app.setStyleSheet(STYLESHEET)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
