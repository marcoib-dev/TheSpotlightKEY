"""
Interfaz gráfica de Spotlight-Key (PySide6).

Pensada para usuarios no programadores: buscar el foco, seleccionarlo,
y controlarlo (encender/apagar, brillo, color) sin tocar la terminal.

Nota de diseño: las llamadas a core/ son sincrónicas y bloquean el hilo
principal mientras esperan respuesta de red. Para esta primera versión
es aceptable (la mayoría de las operaciones son rápidas), pero el
descubrimiento de dispositivos tarda varios segundos a propósito y
va a congelar la ventana durante ese tiempo. Pendiente: mover esas
llamadas a un QThread para no bloquear la UI.
"""

import sys

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QApplication,
    QMainWindow,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QListWidget,
    QListWidgetItem,
    QSlider,
    QColorDialog,
    QMessageBox,
    QGroupBox,
)

from core.config import get_light_ip, set_light_ip, load_config
from core.device import Light
from core.discovery import discover_lights


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Spotlight-Key")
        self.setMinimumWidth(400)

        self.light: Light | None = None

        root = QWidget()
        self.setCentralWidget(root)
        layout = QVBoxLayout(root)

        # --- Sección: foco configurado ---
        self.configured_label = QLabel()
        layout.addWidget(self.configured_label)

        # --- Sección: descubrimiento ---
        discover_box = QGroupBox("Buscar focos en la red")
        discover_layout = QVBoxLayout(discover_box)

        self.discover_btn = QPushButton("Buscar")
        self.discover_btn.clicked.connect(self.on_discover_clicked)
        discover_layout.addWidget(self.discover_btn)

        self.devices_list = QListWidget()
        self.devices_list.itemDoubleClicked.connect(self.on_device_selected)
        discover_layout.addWidget(self.devices_list)

        discover_hint = QLabel("Doble clic sobre un foco para seleccionarlo.")
        discover_hint.setStyleSheet("color: gray; font-size: 11px;")
        discover_layout.addWidget(discover_hint)

        layout.addWidget(discover_box)

        # --- Sección: controles ---
        controls_box = QGroupBox("Control")
        controls_layout = QVBoxLayout(controls_box)

        onoff_row = QHBoxLayout()
        self.on_btn = QPushButton("Encender")
        self.on_btn.clicked.connect(self.on_turn_on)
        self.off_btn = QPushButton("Apagar")
        self.off_btn.clicked.connect(self.on_turn_off)
        onoff_row.addWidget(self.on_btn)
        onoff_row.addWidget(self.off_btn)
        controls_layout.addLayout(onoff_row)

        controls_layout.addWidget(QLabel("Brillo:"))
        self.brightness_slider = QSlider(Qt.Horizontal)
        self.brightness_slider.setRange(0, 255)
        self.brightness_slider.setValue(255)
        self.brightness_slider.sliderReleased.connect(self.on_brightness_changed)
        controls_layout.addWidget(self.brightness_slider)

        self.color_btn = QPushButton("Elegir color...")
        self.color_btn.clicked.connect(self.on_pick_color)
        controls_layout.addWidget(self.color_btn)

        layout.addWidget(controls_box)

        # --- Sección: estado ---
        status_row = QHBoxLayout()
        self.status_label = QLabel("Estado: —")
        self.refresh_btn = QPushButton("Actualizar estado")
        self.refresh_btn.clicked.connect(self.on_refresh_status)
        status_row.addWidget(self.status_label)
        status_row.addWidget(self.refresh_btn)
        layout.addLayout(status_row)

        self._load_configured_light()
        self._update_controls_enabled()

    # --- Helpers internos ---

    def _load_configured_light(self):
        ip = get_light_ip()
        if ip:
            config = load_config()
            name = config.get("light", {}).get("name", "")
            self.light = Light(ip)
            self.configured_label.setText(f"Foco configurado: {name or ip} ({ip})")
        else:
            self.light = None
            self.configured_label.setText("Ningún foco configurado todavía. Buscá uno abajo.")

    def _update_controls_enabled(self):
        enabled = self.light is not None
        for w in (self.on_btn, self.off_btn, self.brightness_slider, self.color_btn, self.refresh_btn):
            w.setEnabled(enabled)

    def _require_light(self) -> Light | None:
        if self.light is None:
            QMessageBox.warning(self, "Sin foco", "Primero seleccioná un foco de la lista.")
            return None
        return self.light

    def _show_error(self, e: Exception):
        QMessageBox.critical(self, "Error", f"No se pudo completar la acción:\n{e}")

    # --- Handlers ---

    def on_discover_clicked(self):
        self.devices_list.clear()
        self.discover_btn.setEnabled(False)
        self.discover_btn.setText("Buscando... (unos segundos)")
        QApplication.processEvents()  # deja repintar el botón antes de bloquear

        try:
            devices = discover_lights(wait=5)
        except Exception as e:
            self._show_error(e)
            devices = []
        finally:
            self.discover_btn.setEnabled(True)
            self.discover_btn.setText("Buscar")

        if not devices:
            QMessageBox.information(self, "Sin resultados", "No se encontró ningún foco en la red.")
            return

        for d in devices:
            item = QListWidgetItem(f"{d['ip']}  (MAC: {d['mac']})")
            item.setData(Qt.UserRole, d["ip"])
            self.devices_list.addItem(item)

    def on_device_selected(self, item: QListWidgetItem):
        ip = item.data(Qt.UserRole)
        set_light_ip(ip, name="")
        self._load_configured_light()
        self._update_controls_enabled()
        QMessageBox.information(self, "Foco seleccionado", f"Se guardó {ip} como foco a controlar.")

    def on_turn_on(self):
        light = self._require_light()
        if not light:
            return
        try:
            light.turn_on()
            self.on_refresh_status()
        except Exception as e:
            self._show_error(e)

    def on_turn_off(self):
        light = self._require_light()
        if not light:
            return
        try:
            light.turn_off()
            self.on_refresh_status()
        except Exception as e:
            self._show_error(e)

    def on_brightness_changed(self):
        light = self._require_light()
        if not light:
            return
        try:
            light.set_brightness(self.brightness_slider.value())
        except Exception as e:
            self._show_error(e)

    def on_pick_color(self):
        light = self._require_light()
        if not light:
            return
        color = QColorDialog.getColor()
        if not color.isValid():
            return
        try:
            light.set_color(color.red(), color.green(), color.blue())
        except Exception as e:
            self._show_error(e)

    def on_refresh_status(self):
        light = self._require_light()
        if not light:
            return
        try:
            state = "Encendido" if light.is_on() else "Apagado"
            self.status_label.setText(f"Estado: {state}")
        except Exception as e:
            self._show_error(e)


def main():
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()