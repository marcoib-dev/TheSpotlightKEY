import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from gui.main import LightCard, RoomCard


class CardRenameTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_light_card_supports_rename(self):
        card = LightCard({"id": "light-1", "ip": "192.168.1.10", "name": "Luz de prueba"})
        self.assertTrue(hasattr(card, "rename"))
        self.assertTrue(hasattr(card, "set_name"))

    def test_room_card_supports_rename(self):
        card = RoomCard({"id": "room-1", "name": "Dormitorio"})
        self.assertTrue(hasattr(card, "rename"))
        self.assertTrue(hasattr(card, "set_name"))


if __name__ == "__main__":
    unittest.main()
