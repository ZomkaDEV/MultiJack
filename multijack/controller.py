# TODO: Use some other library that has support for something other than Linux :/

import logging
import sys

from PyQt6.QtCore import Qt, QThread, pyqtSignal

if sys.platform == "linux":
    from xbox360controller import Xbox360Controller

logger = logging.getLogger(__name__)


class ControllerListener(QThread):
    if sys.platform == "linux":
        hat_signal = pyqtSignal(int)
        button_signal = pyqtSignal()
        exit_signal = pyqtSignal()

        def __init__(self):
            super().__init__()
            self.controller = None

        def run(self):
            try:
                with Xbox360Controller(0, axis_threshold=0.2) as self.controller:
                    self.controller.button_a.when_pressed = self.select_env
                    self.controller.button_b.when_pressed = self.exit_launcher
                    self.controller.hat.when_moved = self.move_up_the_list

                    self.exec()
            except Exception as e:
                logger.error(f"Failed to initialize Xbox 360 controller: {e}")

    def select_env(self, button):
        self.button_signal.emit()

    def exit_launcher(self, button):
        self.exit_signal.emit()

    def move_up_the_list(self, hat):
        if hat.y == 1:
            self.hat_signal.emit(Qt.Key.Key_Up)
        elif hat.y == -1:
            self.hat_signal.emit(Qt.Key.Key_Down)
