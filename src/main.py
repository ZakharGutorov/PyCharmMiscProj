import sys
from PyQt5.QtWidgets import QApplication
from app import SystemMonitorApp

if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setStyle('Fusion')
    window = SystemMonitorApp()
    window.show()
    sys.exit(app.exec_())