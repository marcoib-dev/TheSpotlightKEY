import sys

from PySide6.QtCore import Qt, Signal, QSize
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QStackedWidget,
    QVBoxLayout, QHBoxLayout, QGridLayout, QLabel, QPushButton,
    QFrame, QScrollArea, QSlider, QColorDialog, QMessageBox, QDialog,
    QListWidget, QListWidgetItem,
)

from core.config import get_lights, get_light, add_or_update_light
from core.device import Light, LightUnreachableError
from core.discovery import discover_lights
from gui.theme import STYLESHEET
from gui.icons import icon


class LightCard(QFrame):
    clicked = Signal(str)

    def __init__(self, light: dict, parent=None):
        super().__init__(parent)
        self.light_id = light["id"]
        self.setObjectName("LightCard")
        self.setFixedSize(140, 140)
        self.setCursor(Qt.PointingHandCursor)

        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignCenter)

        self.icon_label = QLabel()
        self.icon_label.setAlignment(Qt.AlignCenter)
        self._set_icon("lightbulb-off")  # estado neutro hasta que llegue la respuesta real
        layout.addWidget(self.icon_label)

        name_label = QLabel(light.get("name") or light["ip"])
        name_label.setObjectName("LightName")
        name_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(name_label)

    def _set_icon(self, name: str):
        self.icon_label.setPixmap(icon(name).pixmap(48, 48))

    def set_state(self, is_on: bool | None):
        """is_on=None significa 'no responde'; se muestra apagado igual."""
        self._set_icon("lightbulb" if is_on else "lightbulb-off")

    def mousePressEvent(self, event):
        self.clicked.emit(self.light_id)
        super().mousePressEvent(event)


class DiscoverDialog(QDialog):
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


from gui.workers import LightStatusWorker
from PySide6.QtCore import QThread

class HomeScreen(QWidget):
    light_selected = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._status_thread: QThread | None = None
        self._status_worker: LightStatusWorker | None = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 24)

        header = QHBoxLayout()
        user_icon = QLabel()
        user_icon.setPixmap(icon("user").pixmap(22, 22))
        header.addWidget(user_icon)
        header.addWidget(QLabel("Hola user", objectName="Header"))
        header.addStretch()
        discover_btn = QPushButton("+ Buscar focos")
        discover_btn.setObjectName("Primary")
        discover_btn.clicked.connect(self.open_discover)
        header.addWidget(discover_btn)
        layout.addLayout(header)

        title = QLabel("Luces")
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

        self.empty_label = QLabel("Ningún foco configurado todavía.")
        self.empty_label.setAlignment(Qt.AlignCenter)
        self.empty_label.setStyleSheet("color: gray; margin-top: 40px;")
        layout.addWidget(self.empty_label)

        self.refresh()

    def refresh(self):
        while self.grid.count():
            item = self.grid.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        lights = get_lights()
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
        self._status_thread.finished.connect(self._clear_status_thread_ref)  # ← nueva línea

        self._status_thread.start()

    def _clear_status_thread_ref(self):
        """
        Se ejecuta cuando el QThread termina. deleteLater() destruye el
        objeto C++ en la próxima vuelta del loop de eventos, pero la
        referencia de Python (self._status_thread) sigue apuntando ahí
        si no la limpiamos: la próxima llamada a refresh() intentaría
        usar un objeto ya borrado y explotaría con RuntimeError.
        """
        self._status_thread = None
        self._status_worker = None

    def _on_status_ready(self, results: dict):
        for i in range(self.grid.count()):
            widget = self.grid.itemAt(i).widget()
            if isinstance(widget, LightCard) and widget.light_id in results:
                widget.set_state(results[widget.light_id])

    def open_discover(self):
        dialog = DiscoverDialog(self)
        if dialog.exec() == QDialog.Accepted:
            self.refresh()


class LightDetailScreen(QWidget):
    back_requested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.light: Light | None = None
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

        self.name_label = QLabel()
        self.name_label.setObjectName("ScreenTitle")
        layout.addWidget(self.name_label)

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
        self.light = Light(data["ip"])
        self.name_label.setText(data.get("name") or data["ip"])
        self.refresh_status()

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
            self._show_error(e) if hasattr(self, "_show_error") else QMessageBox.warning(self, "Foco no responde", str(e))

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


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Spotlight-Key")
        self.setMinimumSize(480, 560)

        self.stack = QStackedWidget()
        self.setCentralWidget(self.stack)

        self.home = HomeScreen()
        self.detail = LightDetailScreen()
        self.stack.addWidget(self.home)
        self.stack.addWidget(self.detail)

        self.home.light_selected.connect(self.open_detail)
        self.detail.back_requested.connect(self.open_home)

    def open_detail(self, light_id: str):
        self.detail.load_light(light_id)
        self.stack.setCurrentWidget(self.detail)

    def open_home(self):
        self.home.refresh()
        self.stack.setCurrentWidget(self.home)


def main():
    app = QApplication(sys.argv)
    app.setStyleSheet(STYLESHEET)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()