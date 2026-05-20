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

        self.record_on = False
        self.sendmessage = controlSignal_stream
        self._setup_ui()
        self.show()

    def _setup_ui(self):
        self.button = create_button("play", callback=self._on_button_click, parent=self)
        self.button.move(W//2, H//2)

    def _on_button_click(self):
        resonance = ResonanceAppProxy(self.sendmessage)

        signalGenerator = resonance.getService("signalGenerator")

        if ~self.record_on:
            full_name = r"record-$$$.hdf"
            signalGenerator.sendTransition('start', filename=full_name)
            self.button.setText("stop")
        else:
            signalGenerator.sendTransition('stop')
            self.button.setText("play")

        self.record_on = ~self.record_on



app = QApplication(sys.argv) 

driver = Driver("Controller") 
controlSignal_stream = driver.outputMessageStream("controlSignal")           # создание выходного потока данных типа Stream

bat_file = r"C:\Users\hodor\Documents\lab-MSU\Works\2025.10_TMS\dist_2024_11_13_imp\control.bat"        # <-- YOUR PATH

main = MainWindow(controlSignal_stream, bat_file)         

# {"service": "impedance", "param": "axis_scale_max", "value": 200}


sys.exit(app.exec_())