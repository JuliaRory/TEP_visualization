from PyQt5.QtWidgets import QFrame, QVBoxLayout, QLabel,  QSizePolicy
from PyQt5.QtCore import  pyqtSignal

from utils.ui_helpers import create_button, create_lineedit
from utils.layout_utils import create_hbox

import os
import subprocess


class NVXControlPanel(QFrame):
    """ --- UI для контроля NVX136 через резонанс --- """

    recording = pyqtSignal(bool)
    def __init__(self, settings, resonance, parent=None):
        super().__init__(parent)

        # self.setObjectName("settings_panel")    # для привязки стиля
        self.setMinimumWidth(200)

        self.settings = settings                        # settings.nvx_control
        self.resonance = resonance                      # для управления резонансными модулями

        self._init_state()
        self._setup_ui()
        self._setup_layout()
        self._setup_connections()

    def _init_state(self):
        self.record_in_progress = False

        if self.settings.activate_bat:
            # Запуск батника с qml-файлом для управления резонансными модулями
            try:
                cwd = os.path.dirname(self.settings.bat_file) # cwd = папка с батником
                subprocess.Popen([self.settings.bat_file], cwd=cwd)
            except:
                cwd = os.path.dirname(self.settings.bat_file_home) # cwd = папка с батником
                subprocess.Popen([self.settings.bat_file_home], cwd=cwd)
    
    # =======================
    # =====     UI      =====
    # =======================
    def _setup_ui(self):
        
        # --- Управление NVX16 (запуск, запись и тд) ---
        self._label_nvx = QLabel("КОНТРОЛЬ NVX", self)
        self.button_nvx_control = create_button(text='Контроль qml', disabled=False, parent=self)   # запустить qml модуль для контроля над процессами
        self.button_check_impedance = create_button(text='Импеданс', disabled=True, parent=self)
        self.button_nvx_launch = create_button(text='Старт', disabled=False, parent=self)           # launch and/or start
        self.button_nvx_stop = create_button(text='Стоп', disabled=False, parent=self)              # stop
        self.button_nvx_kill = create_button(text='kill', disabled=False, parent=self)              # !terminate
        self.lineedit_record = create_lineedit(parent=self)                                         # record name
        self.button_nvx_record = create_button(text='Запись', disabled=False, parent=self)          # recorder.start()      <-> "Остановить"

        
    # =======================
    # =====   LAYOUT    =====
    # =======================
    def _setup_layout(self):        

        layout_qml_control = create_hbox([self.button_nvx_control, QLabel("...", self)])
        layout_nvx_control = create_hbox([self.button_nvx_launch, self.button_nvx_stop, self.button_nvx_kill])
        layout_record = create_hbox([self.lineedit_record, self.button_nvx_record])

                                                                # Vertical layout
        layout = QVBoxLayout(self)           # +-----------------------|
        layout.addWidget(self._label_nvx)                       # | NVX control           |
        layout.addLayout(layout_qml_control)                    # | Контроль qml   ...    |
        layout.addWidget(self.button_check_impedance)           # | Проверить импеданс    |
        layout.addLayout(layout_nvx_control)                    # | start   stop    kill  |
        layout.addLayout(layout_record)                         # | record_name   Запись  |
                                                                # +-----------------------+


        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

    # =======================
    # =====   Сигналы    ====
    # =======================
    def _setup_connections(self):
        self.button_nvx_control.clicked.connect(self._check_qml_contol_state)       # qml control state
        self.button_nvx_launch.clicked.connect(self._on_nvx_launch_button_click)    # launch or/and start nvx136
        self.button_nvx_stop.clicked.connect(self._on_nvx_stop_button_click)        # stop nvx136 
        self.button_nvx_kill.clicked.connect(self._on_nvx_kill_button_click)        # terminate nvx136

        self.button_nvx_record.clicked.connect(self._on_nvx_record_button_click)        # terminate nvx136

    # =======================
    # =====   Логика    =====
    # =======================
    def _check_qml_contol_state(self):
        service = self.resonance.getService("Resonance-control")     # Берем сервис
        service.checkState()
    
    def _on_nvx_launch_button_click(self):
        print("launch bat")

    
    def _on_nvx_stop_button_click(self):
        service = self.resonance.getService(self.settings.service_name)     # Берем сервис
        service.sendTransition("stop")
    
    def _on_nvx_kill_button_click(self):
        service = self.resonance.getService(self.settings.service_name)     # Берем сервис
        service.sendTransition("!terminate")
        
    def _on_nvx_record_button_click(self):
        
        if not self.record_in_progress:    # если запись не была начата
            print("START NVX136 RECORDING")
            self.record_in_progress = True
            
            self._service = self.resonance.getService(self.settings.service_name)     # Берем сервис
            self._service.sendTransition('start', stream=self.settings.stream_name)

            self._service_stimuli = self.resonance.getService("TEP_visual")     # Берем сервис
            self._service_stimuli.sendTransition('start', stream="stimuli")

            self.recording.emit(True)
            
        else:                               # если запись уже идёт
            print("FINISH NVX136 RECORDING")
            self.record_in_progress = False

            self._service.sendTransition('stop')
            self._service_stimuli.sendTransition('stop')

            self.recording.emit(False)
        
        button_label = "Остановить" if self.record_in_progress else "Начать запись"
        self.button_nvx_record.setText(button_label)
    

