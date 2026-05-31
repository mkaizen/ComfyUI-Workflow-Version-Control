import sys
from PyQt6.QtWidgets import QApplication
from PyQt6.QtGui import QIcon
from comfyvc.gui.main_window import MainWindow


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("ComfyVC")
    app.setApplicationDisplayName("ComfyUI Workflow Version Control")

    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
