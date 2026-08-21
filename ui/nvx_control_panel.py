from PyQt5.QtWidgets import QFrame, QVBoxLayout, QLabel,  QSizePolicy, QHBoxLayout
from PyQt5.QtCore import  pyqtSignal

from utils.ui_helpers import create_button, create_lineedit, create_check_box
from utils.layout_utils import create_hbox, create_vbox

import os
import re
import subprocess


class NVXControlPanel(QFrame):
    """ --- UI для контроля NVX136 через резонанс --- """

    recording = pyqtSignal(bool)
    recordingFileChanged = pyqtSignal(bool, str)
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
        self._current_record_path = ""

        if self.settings.activate_bat:
            # Запуск батника с qml-файлом для управления резонансными модулями
            self._launch_control_bat()


    # =======================
    # =====     UI      =====
    # =======================
    def _setup_ui(self):
        
        # --- Управление NVX16 (запуск, запись и тд) ---
        self._label_nvx = QLabel("ЗАПИСЬ", self)
        self.button_nvx_control = create_button(text='Контроль qml', disabled=False)   # запустить qml модуль для контроля над процессами
        self.button_check_impedance = create_button(text='Импеданс', disabled=True)
        self.button_nvx_launch = create_button(text='Старт', disabled=False)           # launch and/or start
        self.button_nvx_stop = create_button(text='Стоп', disabled=False)              # stop
        self.button_nvx_kill = create_button(text='kill', disabled=False)              # !terminate

        self.lineedit_folder = create_lineedit(parent=self, w=200)
        self.lineedit_folder.setText(self.settings.records_folder)
        self.button_recorder = create_button(text='recorder', disabled=False, parent=self)
        self.lineedit_record = create_lineedit(parent=self, w=250)                                  # record name

        self._create_filename_lineedits()

        self.button_nvx_record = create_button(text='Запись', disabled=False, parent=self)          # recorder.start()      <-> "Остановить"

    def _create_filename_lineedits(self):
        self.lineedit_number = create_lineedit(parent=self)
        self.lineedit_subject = create_lineedit(parent=self)                                   
        self.lineedit_spot = create_lineedit(parent=self) 
        self.lineedit_yaw_angle = create_lineedit(parent=self)
        self.lineedit_power = create_lineedit(parent=self)
        self.lineedit_comments = create_lineedit(parent=self)

        self.checkbox_number = create_check_box(True, "#", parent=self)
        self.checkbox_subject = create_check_box(True, "subj", parent=self)
        self.checkbox_spot = create_check_box(True, "spot", parent=self)      
        self.checkbox_yaw_angle = create_check_box(False, "yaw_angle", parent=self)
        self.checkbox_power = create_check_box(True, "power", parent=self)       
        self.checkbox_comments = create_check_box(False, "comments", parent=self) 

    def _filename_fields(self):
        return [
            ("number", self.checkbox_number, self.lineedit_number),
            ("subject", self.checkbox_subject, self.lineedit_subject),
            ("spot", self.checkbox_spot, self.lineedit_spot),
            ("yaw_angle", self.checkbox_yaw_angle, self.lineedit_yaw_angle),
            ("power", self.checkbox_power, self.lineedit_power),
            ("comments", self.checkbox_comments, self.lineedit_comments),
        ]
                  

    # =======================
    # =====   LAYOUT    =====
    # =======================
    def _setup_layout(self):        

        layout_qml_control = create_hbox([self.button_nvx_control, QLabel("...")])
        layout_nvx_control = create_hbox([self.button_nvx_launch, self.button_nvx_stop, self.button_nvx_kill])
        
        layouts_label = []
        for (_field_name, checkbox, lineedit) in self._filename_fields():
            layouts_label.append(create_vbox([checkbox, lineedit]))

        layout_record = QHBoxLayout()
        for layout_label in layouts_label:
            layout_record.addLayout(layout_label)

        layout_folder = create_hbox([QLabel("Путь:"), self.lineedit_folder])
        layout_folder.insertWidget(2, self.button_recorder)
        layout_record_final = create_hbox([self.lineedit_record, self.button_nvx_record])

                                                                # Vertical layout
        layout = QVBoxLayout(self)                              # +-----------------------|
        layout.addWidget(self._label_nvx)                       # | NVX control           |
        # layout.addLayout(layout_qml_control)                    # | Контроль qml   ...    |
        # layout.addWidget(self.button_check_impedance)           # | Проверить импеданс    |
        # layout.addLayout(layout_nvx_control)                    # | start   stop    kill  |
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
        self.button_recorder.clicked.connect(self._on_recorder_button_click)

        autofilename = True
        if autofilename:
            for (_field_name, checkbox, lineedit) in self._filename_fields():
                lineedit.textChanged.connect(self.change_filename)
                checkbox.stateChanged.connect(self.change_filename)
            self.lineedit_folder.textChanged.connect(self._on_records_folder_changed)

    # =======================
    # =====   Логика    =====
    # =======================

    def _launch_control_bat(self):
        candidates = [
            getattr(self.settings, "bat_file", ""),
            getattr(self.settings, "bat_file_home", ""),
        ]
        seen = set()

        for bat_file in candidates:
            if not bat_file or bat_file in seen:
                continue
            seen.add(bat_file)

            if not os.path.exists(bat_file):
                print(f"Control bat file does not exist: {bat_file}")
                continue

            try:
                cwd = os.path.dirname(bat_file)
                subprocess.Popen(["cmd.exe", "/c", bat_file], cwd=cwd)
                return
            except OSError as exc:
                print(f"Failed to launch control bat file {bat_file}: {exc}")

        print("Control service was not launched: no configured bat file could be started.")

    
    def change_filename(self, *_args):
        new_filename = "rec"
        for (field_name, checkbox, lineedit) in self._filename_fields():
            if checkbox.isChecked():
                value = lineedit.text().strip()
                if field_name == "power":
                    value = self._format_power(value)
                if not value:
                    continue
                new_filename = "" if new_filename == "rec" else new_filename + "_"
                new_filename += value
        full_filename = new_filename + ".hdf5" if new_filename != "" else "rec.hdf5"

        # def check_file(filename):
        #         folder = r"D:\Resonance\distro-dual\msvc\bin"
        #         full_name = os.path.join(folder, filename)
        #         return os.path.exists(full_name)
        # if check_file(full_filename):
        #     new_filename += "-$$$.hdf5"

        self.lineedit_record.setText(full_filename)

    def _on_records_folder_changed(self, *_args):
        self.update_next_record_number()

    def update_next_record_number(self):
        next_number = self._get_next_record_number(self.lineedit_folder.text())
        if self.lineedit_number.text() == next_number:
            self.change_filename()
            return

        blocked = self.lineedit_number.blockSignals(True)
        self.lineedit_number.setText(next_number)
        self.lineedit_number.blockSignals(blocked)
        self.change_filename()

    def _get_next_record_number(self, folder):
        numbers = []
        widths = []
        try:
            filenames = os.listdir(folder)
        except OSError:
            return "00"

        for filename in filenames:
            match = re.match(r"^(\d+)(?=_|\.|$)", filename)
            if match:
                value = match.group(1)
                numbers.append(int(value))
                widths.append(len(value))

        if not numbers:
            return "00"

        width = max(2, max(widths))
        return f"{max(numbers) + 1:0{width}d}"

    @staticmethod
    def _format_power(value):
        value = value.strip()
        if not value:
            return ""
        return value if value.upper().endswith("MSO") else f"{value}MSO"

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
        
    def _on_recorder_button_click(self):
        recorder_bat_file = getattr(
            self.settings,
            "recorder_bat_file",
            "C:/Users/hodor/Documents/lab-MSU/Works/2025.10_TMS/msvc64/recorderService_nvxstream.bat",
        )
        if not os.path.exists(recorder_bat_file):
            print(f"Recorder bat file does not exist: {recorder_bat_file}")
            return

        cwd = os.path.dirname(recorder_bat_file)
        subprocess.Popen(["cmd.exe", "/c", recorder_bat_file], cwd=cwd)

    def _on_nvx_record_button_click(self, *_args, command="start"):
        if command == "start_rec":
            self._toggle_legacy_recording()
            return

        self._toggle_recorder_recording()

    def _prepare_recording_start(self):
        self.record_in_progress = True
        self.update_next_record_number()

        filename = self.lineedit_record.text()
        folder = self.lineedit_folder.text()
        full_name = os.path.join(folder, filename)

        if os.path.exists(full_name):
            full_name = full_name[:-5] + "-$$$.hdf5"

        self._current_record_path = full_name
        self.change_filename()
        self.recordingFileChanged.emit(True, self._current_record_path)
        self.recording.emit(True)
        self._update_record_button_label()
        return full_name

    def _finish_recording(self):
        self.record_in_progress = False
        self.change_filename()
        self.recording.emit(False)
        self.recordingFileChanged.emit(False, self._current_record_path)
        self.update_next_record_number()
        self._update_record_button_label()

    def _toggle_recorder_recording(self):
        recorder_service_name = getattr(self.settings, "recorder_service_name", "Recorder")

        if not self.record_in_progress:
            print("START RECORDER RECORDING")
            full_name = self._prepare_recording_start()
            self._service = self.resonance.getService(recorder_service_name)
            self._service.sendParameter("fileName", full_name)
            self._service.sendTransition("start")
            return

        print("FINISH RECORDER RECORDING")
        service = getattr(self, "_service", None) or self.resonance.getService(recorder_service_name)
        service.sendTransition("stop")
        self._finish_recording()

    def _toggle_legacy_recording(self):
        recorder_service_name = getattr(self.settings, "recorder_service_name", "Recorder")

        if not self.record_in_progress:
            print("START RECORDER RECORDING (start_rec)")
            full_name = self._prepare_recording_start()
            self._service = self.resonance.getService(recorder_service_name)
            self._service.sendParameter("fileName", full_name)
            self._service.sendTransition("start_rec")
            return

        print("FINISH RECORDER RECORDING (start_rec)")
        service = getattr(self, "_service", None) or self.resonance.getService(recorder_service_name)
        service.sendTransition("stop")
        self._finish_recording()

    def _update_record_button_label(self):
        button_label = "Остановить" if self.record_in_progress else "Начать запись"
        self.button_nvx_record.setText(button_label)
    

    def start_rec(self):
        self._on_nvx_record_button_click(command="start_rec")

    def change_record_status(self, stimuli=False, command="start"):
        self._add_stimuli_stream = stimuli
        self._on_nvx_record_button_click(command=command)

    
