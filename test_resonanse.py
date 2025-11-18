import subprocess
import json
from pathlib import Path
import os

from drivers.resonance_foreign_driver import Driver
from utils.resonance_control import ResonanceAppProxy

from PyQt5.QtWidgets import QWidget
from utils.ui_helpers import create_button

from PyQt5.QtWidgets import QApplication
import sys

W=600
H=400

class MainWindow(QWidget):
    def __init__(self, controlSignal_stream, bat_file):
        super().__init__()

        self.resize(W, H)

        """Запуск батника с qml-файлом для управления резонансными модулями"""
        cwd = os.path.dirname(bat_file) # cwd = папка с батником
        subprocess.Popen([bat_file], cwd=cwd)

        self.sendmessage = controlSignal_stream
        self._setup_ui()
        self.show()

    def _setup_ui(self):
        button = create_button("play", callback=self._on_button_click, checkable=True, parent=self)
        button.move(W//2, H//2)

    def _on_button_click(self):
        # Создаем прокси
        resonance = ResonanceAppProxy(self.sendmessage)

        # Берем сервис 
        signalGenerator = resonance.getService("signalGenerator")

        # Меняем параметр
        # signalGenerator.sendParameter("channels", 4)
        signalGenerator.sendTransition('start')

        

app = QApplication(sys.argv) 

driver = Driver("Controller") 
controlSignal_stream = driver.outputMessageStream("controlSignal")           # создание входного потока данных типа Stream

bat_file = r"C:\Users\hodor\Documents\lab-MSU\Works\2025.10_TMS\dist_2024_11_13_imp\control.bat"

main = MainWindow(controlSignal_stream, bat_file)         # открыть Qt-окно приложения

# {"service": "impedance", "param": "axis_scale_max", "value": 200}


sys.exit(app.exec_())