from PyQt5.QtWidgets import QFrame, QVBoxLayout, QLabel,  QSizePolicy, QHBoxLayout
from PyQt5.QtCore import  pyqtSignal

from utils.ui_helpers import create_button, create_lineedit, create_check_box
from utils.layout_utils import create_hbox, create_vbox

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
        self._add_stimuli_stream = False

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

        self.lineedit_folder = create_lineedit(parent=self, w=200)
        self.lineedit_folder.setText(self.settings.records_folder)
        self.lineedit_record = create_lineedit(parent=self)                                         # record name

        self._create_filename_lineedits()

        self.button_nvx_record = create_button(text='Запись', disabled=False, parent=self)          # recorder.start()      <-> "Остановить"

    def _create_filename_lineedits(self):
        self.lineedit_number = create_lineedit(parent=self)
        self.lineedit_subject = create_lineedit(parent=self)                                   
        self.lineedit_spot = create_lineedit(parent=self) 
        self.lineedit_coil = create_lineedit(parent=self)       
        self.lineedit_yaw_angle = create_lineedit(parent=self)
        self.lineedit_power = create_lineedit(parent=self)
        self.lineedit_comments = create_lineedit(parent=self)

        self.checkbox_number = create_check_box(True, "#", parent=self)
        self.checkbox_subject = create_check_box(True, "subj", parent=self)
        self.checkbox_spot = create_check_box(True, "spot", parent=self)      
        self.checkbox_coil = create_check_box(False, "coil", parent=self)      
        self.checkbox_yaw_angle = create_check_box(False, "yaw_angle", parent=self)
        self.checkbox_power = create_check_box(True, "power", parent=self)       
        self.checkbox_comments = create_check_box(False, "comments", parent=self) 
                  

    # =======================
    # =====   LAYOUT    =====
    # =======================
    def _setup_layout(self):        

        layout_qml_control = create_hbox([self.button_nvx_control, QLabel("...")])
        layout_nvx_control = create_hbox([self.button_nvx_launch, self.button_nvx_stop, self.button_nvx_kill])
        
        layouts_label = []
        for (checkbox, lineedit) in zip([self.checkbox_number, self.checkbox_subject, self.checkbox_spot, self.checkbox_coil, self.checkbox_yaw_angle, self.checkbox_power, self.checkbox_comments], 
                                        [self.lineedit_number, self.lineedit_subject, self.lineedit_spot, self.lineedit_coil, self.lineedit_yaw_angle, self.lineedit_power, self.lineedit_comments]):
            layouts_label.append(create_vbox([checkbox, lineedit]))

        layout_record = QHBoxLayout()
        for layout_label in layouts_label:
            layout_record.addLayout(layout_label)

        layout_folder = create_hbox([QLabel("Путь:"), self.lineedit_folder])
        layout_record_final = create_hbox([self.lineedit_record, self.button_nvx_record])

                                                                # Vertical layout
        layout = QVBoxLayout(self)                              # +-----------------------|
        layout.addWidget(self._label_nvx)                       # | NVX control           |
        layout.addLayout(layout_qml_control)                    # | Контроль qml   ...    |
        layout.addWidget(self.button_check_impedance)           # | Проверить импеданс    |
        layout.addLayout(layout_nvx_control)                    # | start   stop    kill  |
        layout.addLayout(layout_folder)
        layout.addLayout(layout_record) 
        layout.addLayout(layout_record_final)                   # | record_name   Запись  |
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

        autofilename = True
        if autofilename:
            for (checkbox, lineedit) in zip([self.checkbox_number, self.checkbox_subject, self.checkbox_spot, self.checkbox_coil, self.checkbox_yaw_angle, self.checkbox_power, self.checkbox_comments], 
                                        [self.lineedit_number, self.lineedit_subject, self.lineedit_spot, self.lineedit_coil, self.lineedit_yaw_angle, self.lineedit_power, self.lineedit_comments]):
                lineedit.textChanged.connect(self.change_filename)
                checkbox.stateChanged.connect(self.change_filename)

    # =======================
    # =====   Логика    =====
    # =======================

    
    def change_filename(self):
        new_filename = "rec"
        for (checkbox, lineedit) in zip([self.checkbox_number, self.checkbox_subject, self.checkbox_spot, self.checkbox_coil, self.checkbox_yaw_angle, self.checkbox_power, self.checkbox_comments], 
                                        [self.lineedit_number, self.lineedit_subject, self.lineedit_spot, self.lineedit_coil, self.lineedit_yaw_angle, self.lineedit_power, self.lineedit_comments]):
            if checkbox.isChecked():
                new_filename = "" if new_filename == "rec" else new_filename + "_"
                new_filename += lineedit.text()
        full_filename = new_filename + ".hdf5" if new_filename != "" else "rec.hdf5"

        # def check_file(filename):
        #         folder = r"D:\Resonance\distro-dual\msvc\bin"
        #         full_name = os.path.join(folder, filename)
        #         return os.path.exists(full_name)
        # if check_file(full_filename):
        #     new_filename += "-$$$.hdf5"

        self.lineedit_record.setText(full_filename)

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

            comments = "true" if self._add_stimuli_stream else "false"

            filename = self.lineedit_record.text()
            folder = self.lineedit_folder.text()
            full_name = os.path.join(folder, filename)

            if os.path.exists(full_name):
                full_name = full_name[:-5] +"-$$$.hdf5"
            self.change_filename()
            
            self._service = self.resonance.getService(self.settings.service_name)     # Берем сервис
            self._service.sendTransition('start', stream=self.settings.stream_name, add_stimuli=comments, filename=full_name)

            # self._service_stimuli = self.resonance.getService("TEP_visual")     # Берем сервис
            # self._service_stimuli.sendTransition('start', stream="stimuli")

            self.recording.emit(True)
            
        else:                               # если запись уже идёт
            print("FINISH NVX136 RECORDING")
            self.record_in_progress = False

            self._service.sendTransition('stop')
            # self._service_stimuli.sendTransition('stop')
            self.change_filename()
            self.recording.emit(False)
        
        button_label = "Остановить" if self.record_in_progress else "Начать запись"
        self.button_nvx_record.setText(button_label)
    

    def change_record_status(self, stimuli=False):
        self._add_stimuli_stream = stimuli
        self._on_nvx_record_button_click()

    
