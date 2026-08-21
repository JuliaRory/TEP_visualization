from PyQt5.QtWidgets import (
    QFrame, QGridLayout, QHBoxLayout, QVBoxLayout, QLabel, QScrollArea, QSizePolicy, QSlider, QFileDialog
)
from PyQt5.QtGui import QFont, QFontMetrics
from PyQt5.QtCore import Qt, pyqtSignal, QSignalBlocker
from dataclasses import fields
from pathlib import Path

import json

from utils.ui_helpers import (
    create_button, create_spin_box, create_check_box, create_combo_box, create_checkable_combobox, create_lineedit
)
from utils.layout_utils import create_hbox, create_vbox
from utils.logic_helpers import are_equal
from logic.sources.file import list_record_files



class SettingsPanel(QFrame):
    speedApplyRequested = pyqtSignal()
    
    """ Панель с настройками."""

    def __init__(self, settings, settings_handler, channels, control_nvx_panel, control_stimuli_panel, survey_panel=None, parent=None):
        super().__init__(parent)

        self.setObjectName("settings_panel")    # для привязки стиля
        self.setMinimumWidth(150)

        self.settings = settings
        self.settings_handler = settings_handler 
        self.channels = channels

        self.control_nvx_panel = control_nvx_panel
        self.control_stimuli_panel = control_stimuli_panel
        self.survey_panel = survey_panel

        self._init_ui()

    def _init_ui(self):   

        self._setup_ui()
        self._setup_layout()
        # self._setup_connections()
        # self._finilize()

        # Добавляем скролл-обёртку
        self.scroll = QScrollArea()
        self.scroll.setWidget(self)
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QFrame.NoFrame)

    
    # =======================
    # =====     UI      =====
    # =======================
    def _setup_ui(self):
        self._epochs_manager_frame = QFrame(self)
        self._speed_frame = QFrame(self)
        self._speed_widgets = {}
        self._speed_syncing = False
        self._speed_presets = self._load_speed_presets()

        # --- Режим: усреднение или одиночные пробы ---
        self.combo_box_mode_data = create_combo_box(items=["Новые данные", "Загруженные"], 
                                        curr_item_idx=self.settings.curr_mode_data_idx, parent=self)
        
        # --- Управление эпохами (сохранение, загрузка и тд) ---
        self.button_show_epoch = create_button('Show #', disabled=True, parent=self)
        self.spin_box_show_epoch = create_spin_box(0, 0, 0, parent=self)
        self.button_remove_epoch = create_button('Delete #', disabled=True, parent=self)
        self.spin_box_remove_epoch =create_spin_box(0, 0, 0, parent=self)

        self.button_load = create_button(text='Load', disabled=True, parent=self)
        self.button_save = create_button(text='Save', disabled=False, parent=self)
        self.combo_box_record_file = create_combo_box(items=list_record_files(), parent=self)
        self.button_next_record_epoch = create_button(
            text='Next epoch',
            disabled=True, #(self.combo_box_record_file.count() == 0),
            parent=self
        )
        self.button_restart = create_button(text='ОЧИСТИТЬ', disabled=False, parent=self)
               
        self._update_record_file_tooltips()
        self._setup_speed_ui()

    # =======================
    # =====   LAYOUT    =====
    # =======================
    def _setup_layout(self):
        # Vertical layout
        # +------------------|
        # | EPOCHS manager   |           
        # +------------------+
        # | NVX control      |
        # +------------------+
        # | STIMULI manager  |
        # +------------------+

        self._setup_epochs_frame()

        top_layout = QHBoxLayout()
        top_layout.addWidget(self._epochs_manager_frame, 1)
        if self.survey_panel is not None:
            top_layout.addWidget(self.survey_panel, 1)

        layout = QVBoxLayout(self)
        layout.addLayout(top_layout)
        layout.addWidget(self.control_nvx_panel)
        layout.addWidget(self.control_stimuli_panel)
        layout.addWidget(self._speed_frame)
        
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

    def _setup_epochs_frame(self):
        layout_show_epoch = create_hbox([self.button_show_epoch, self.spin_box_show_epoch])
        layout_delete_epoch = create_hbox([self.button_remove_epoch, self.spin_box_remove_epoch])
        layout_data = create_hbox([self.combo_box_mode_data])
        layout_records = create_hbox([self.button_load, self.button_save])
        layout_record_epoch_step = create_hbox([self.combo_box_record_file, self.button_next_record_epoch])
        layout_clear_history = create_hbox([self.button_restart])

                                                                # Vertical layout
        layout = QVBoxLayout(self._epochs_manager_frame)        # +------------------+
        layout.addWidget(QLabel("ПРОСМОТР ЭПОХ", self))         # | ПРОСМОТР ЭПОХ    |
        layout.addLayout(layout_show_epoch)                     # | Show   #         |
        layout.addLayout(layout_delete_epoch)                   # | Delete   #       |
        layout.addLayout(layout_data)                           # | Новые/Загрузить  |
        layout.addLayout(layout_records)                        # | Load   Save      |
        layout.addLayout(layout_record_epoch_step)
        layout.addLayout(layout_clear_history)                  # | Clear            |
                                                                # +------------------+

    def _setup_speed_ui(self):
        self.button_speed_apply = create_button("Применить", parent=self._speed_frame)
        self.button_speed_apply.clicked.connect(self._on_speed_apply_clicked)
        self.lineedit_speed_settings_path = create_lineedit(parent=self._speed_frame)
        self.lineedit_speed_settings_path.setText(getattr(self.settings, "speed_settings_export_path", ""))
        self.lineedit_speed_settings_path.textChanged.connect(self._on_speed_path_changed)
        self.button_speed_settings_browse = create_button("Browse", parent=self._speed_frame)
        self.button_speed_settings_browse.clicked.connect(self._on_speed_browse_clicked)
        self.combo_box_speed_preset = create_combo_box(
            items=["Custom"] + list(self._speed_presets.keys()),
            parent=self,
        )
        self.combo_box_speed_preset.currentTextChanged.connect(self._on_speed_preset_changed)

        layout = QGridLayout(self._speed_frame)
        layout.addWidget(QLabel("SPEED", self._speed_frame), 0, 0)
        layout.addWidget(self.button_speed_apply, 0, 1)
        layout.addWidget(QLabel("preset", self._speed_frame), 1, 0)
        layout.addWidget(self.combo_box_speed_preset, 1, 1, 1, 2)
        layout.addWidget(QLabel("path", self._speed_frame), 2, 0)
        layout.addWidget(self.lineedit_speed_settings_path, 2, 1)
        layout.addWidget(self.button_speed_settings_browse, 2, 2)

        row = 3
        for name in self._speed_field_names():
            label = QLabel(name, self._speed_frame)
            widget = self._create_speed_widget(name)
            self._speed_widgets[name] = widget
            layout.addWidget(label, row, 0)
            layout.addWidget(widget, row, 1)
            row += 1

        self.sync_speed_ui_from_settings()

    def _create_speed_widget(self, name):
        value = getattr(self.settings.speed, name, 0)
        if isinstance(value, bool):
            return create_check_box(value, parent=self._speed_frame, function=self._on_speed_ui_changed)

        if name in {"low_freq", "high_freq", "artifact_start", "artifact_end"}:
            return create_spin_box(
                min=-10000,
                max=100000,
                value=float(value),
                data_type="float",
                step=0.01 if name in {"low_freq", "artifact_start", "artifact_end"} else 1,
                decimals=4,
                parent=self._speed_frame,
                function=self._on_speed_ui_changed,
            )

        ranges = {
            "bit": (0, 128, 1),
            "window_start": (-10000, 10000, 10),
            "window_end": (-10000, 10000, 10),
            "notch_fr": (0, 1000, 1),
            "Fs_orig": (1, 100000, 250),
            "Fs": (1, 100000, 250),
        }
        minimum, maximum, step = ranges.get(name, (-10000, 100000, 1))
        return create_spin_box(
            min=minimum,
            max=maximum,
            value=int(value),
            step=step,
            parent=self._speed_frame,
            function=self._on_speed_ui_changed,
        )

    def _speed_field_names(self):
        names = [field.name for field in fields(self.settings.speed)]
        preset_names = []
        for preset in self._speed_presets.values():
            if isinstance(preset, dict):
                preset_names.extend(preset.keys())
        return list(dict.fromkeys(names + preset_names))

    def _load_speed_presets(self):
        path = Path("resources/speed_presets.json")
        if not path.exists():
            return {}
        with path.open("r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}

    def _on_speed_preset_changed(self, preset_name):
        if self._speed_syncing or preset_name == "Custom":
            return
        preset = self._speed_presets.get(preset_name)
        if not isinstance(preset, dict):
            return

        self._speed_syncing = True
        try:
            for key, value in preset.items():
                if hasattr(self.settings.speed, key):
                    setattr(self.settings.speed, key, value)
            self.sync_speed_ui_from_settings(update_preset=False)
        finally:
            self._speed_syncing = False

    def _on_speed_ui_changed(self, *args):
        if self._speed_syncing:
            return
        self.sync_speed_settings_from_ui()
        if self.combo_box_speed_preset.currentText() != "Custom":
            blocker = QSignalBlocker(self.combo_box_speed_preset)
            self.combo_box_speed_preset.setCurrentText("Custom")
            del blocker

    def _on_speed_apply_clicked(self):
        self.sync_speed_settings_from_ui()
        self._sync_speed_path_from_ui()
        self.speedApplyRequested.emit()

    def _on_speed_path_changed(self, path):
        self._sync_speed_path_from_ui()
        self.lineedit_speed_settings_path.setToolTip(path)

    def _on_speed_browse_clicked(self):
        current_path = self.lineedit_speed_settings_path.text().strip()
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Выберите файл SPEED_settings.json",
            current_path,
            "JSON Files (*.json);;All Files (*)",
        )
        if file_path:
            self.lineedit_speed_settings_path.setText(file_path)

    def _sync_speed_path_from_ui(self):
        if hasattr(self.settings, "speed_settings_export_path"):
            self.settings.speed_settings_export_path = self.lineedit_speed_settings_path.text().strip()

    def sync_speed_ui_from_settings(self, update_preset=True):
        self._speed_syncing = True
        try:
            if hasattr(self, "lineedit_speed_settings_path"):
                path = getattr(self.settings, "speed_settings_export_path", "")
                blocker = QSignalBlocker(self.lineedit_speed_settings_path)
                self.lineedit_speed_settings_path.setText(path)
                self.lineedit_speed_settings_path.setToolTip(path)
                del blocker

            for name, widget in self._speed_widgets.items():
                value = getattr(self.settings.speed, name, None)
                if value is None:
                    continue
                if hasattr(widget, "setChecked"):
                    widget.setChecked(bool(value))
                elif hasattr(widget, "setValue"):
                    widget.setValue(value)

            if update_preset:
                blocker = QSignalBlocker(self.combo_box_speed_preset)
                self.combo_box_speed_preset.setCurrentText(self._matching_speed_preset_name())
                del blocker
        finally:
            self._speed_syncing = False

    def sync_speed_settings_from_ui(self):
        self._sync_speed_path_from_ui()
        for name, widget in self._speed_widgets.items():
            if not hasattr(self.settings.speed, name):
                continue
            if hasattr(widget, "isChecked"):
                value = widget.isChecked()
            else:
                value = widget.value()
                if name in {"bit", "window_start", "window_end", "notch_fr", "Fs_orig", "Fs"}:
                    value = int(value)
            setattr(self.settings.speed, name, value)

    def _matching_speed_preset_name(self):
        for name, preset in self._speed_presets.items():
            if not isinstance(preset, dict):
                continue
            if all(
                hasattr(self.settings.speed, key)
                and are_equal(getattr(self.settings.speed, key), value)
                for key, value in preset.items()
            ):
                return name
        return "Custom"
    

    # =======================
    # =====   Сигналы    ====
    # =======================
    

    # =======================
    # =====   Логика    =====
    # =======================

    def _update_record_file_tooltips(self):
        combo = self.combo_box_record_file
        for i in range(combo.count()):
            filename = combo.itemText(i)
            combo.setItemData(i, filename, Qt.ToolTipRole)
        combo.setToolTip(combo.currentText())

