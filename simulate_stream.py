import json 
import numpy as np
import sys
import h5py
import os
import time

from PyQt5.QtWidgets import QApplication
from PyQt5.QtCore import Qt, QTimer, pyqtSignal,  QEvent, QPoint
from PyQt5.QtGui import QFont, QFontMetrics, QMouseEvent
from PyQt5.QtWidgets import (QWidget, QGridLayout,QLabel, qApp, QFrame, QHBoxLayout, QSizePolicy, QSplitter, QApplication)

from utils.dispatcher import CallDispatcher
from drivers.resonance_foreign_driver import Driver

from utils.ui_helpers import create_button

W=600
H=400
class MainWindow(QWidget):

    def __init__(self, create_output):
        super().__init__()
        self.create_output = create_output

        self.cur_pos = 0
        self.cur_block_ind = 0

        self._play = False
        self._end_ind = 100
        self.Fs = 25000

        self.samples2seconds = lambda x: x / self.Fs

        self.setWindowTitle("simulator")
        self.resize(W, H)

        self._load_file()

        self._setup_ui()
        self.show()
    
    def _setup_ui(self):
        button = create_button("play", callback=self._play_stream, checkable=True, parent=self)
        button.move(W//2, H//2)

    def _play_stream(self):
        self._play = True
        while self._play:
            n_samples = self.blocks[self.cur_block_ind]
            next_block = self.data[self.cur_pos:self.cur_pos+n_samples, 0]
            self.cur_pos += n_samples
            self.cur_block_ind += 1
            
            create_output(json.dumps(next_block.tolist()))
            if self.cur_block_ind >= self._end_ind:
                self._play = False
                print('the end')
            if self.cur_block_ind >= self._max_ind:
                self._play = False
                print('end of the file')
            time.sleep(self.samples2seconds(n_samples))
            print('send')

    
    def _load_file(self):
        folder = r"data"
        filename = os.path.join(folder, "02_tms_mi_60_short.h5")
        with h5py.File(filename, "r") as h5f:
            self.blocks = h5f['eeg/blocks'][:]["samples"]
            self.data = h5f['eeg/data'][:]
        self._max_ind = self.blocks.shape[0]



app = QApplication(sys.argv) 

driver = Driver("simulator")
create_output = driver.outputMessageStream("stream")

# driver.loadConfig(r'resonance_settings_simulator.json')          # вгрузить настройки с потоком в резонансе

main = MainWindow(create_output)         # открыть Qt-окно приложения

sys.exit(app.exec_())
