from PyQt5.QtWidgets import (
    QFrame, QGridLayout, QHBoxLayout, QVBoxLayout, QLabel, QScrollArea, QSizePolicy, QSlider
)
from PyQt5.QtGui import QFont, QFontMetrics
from PyQt5.QtCore import Qt, pyqtSignal

import json

from utils.ui_helpers import (
    create_button, create_spin_box, create_check_box, create_combo_box, create_checkable_combobox, create_lineedit
)
from utils.layout_utils import create_hbox, create_vbox
from utils.logic_helpers import are_equal



class SettingsPanel(QFrame):
    
    """ Панель с настройками."""

    def __init__(self, settings, settings_handler, channels, control_nvx_panel, control_stimuli_panel, parent=None):
        super().__init__(parent)

        self.setObjectName("settings_panel")    # для привязки стиля
        self.setMinimumWidth(150)

        self.settings = settings
        self.settings_handler = settings_handler 
        self.channels = channels

        self.control_nvx_panel = control_nvx_panel
        self.control_stimuli_panel = control_stimuli_panel

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

        # --- Режим: усреднение или одиночные пробы ---
        self.combo_box_mode_data = create_combo_box(items=["Новые данные", "Загруженные"], 
                                        curr_item_idx=self.settings.curr_mode_data_idx, parent=self)
        
        # --- Управление эпохами (сохранение, загрузка и тд) ---
        self.button_show_epoch = create_button('Show #', disabled=True, parent=self)
        self.spin_box_show_epoch = create_spin_box(0, 0, 0, parent=self)
        self.button_remove_epoch = create_button('Delete #', disabled=True, parent=self)
        self.spin_box_remove_epoch =create_spin_box(0, 0, 0, parent=self)

        self.button_load = create_button(text='Load', disabled=False, parent=self)
        self.button_save = create_button(text='Save', disabled=True, parent=self)
        self.button_restart = create_button(text='ОЧИСТИТЬ', disabled=False, parent=self)
               

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

        layout = QVBoxLayout(self)
        layout.addWidget(self._epochs_manager_frame)
        layout.addWidget(self.control_nvx_panel)
        layout.addWidget(self.control_stimuli_panel)
        
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

    def _setup_epochs_frame(self):
        layout_show_epoch = create_hbox([self.button_show_epoch, self.spin_box_show_epoch])
        layout_delete_epoch = create_hbox([self.button_remove_epoch, self.spin_box_remove_epoch])
        layout_data = create_hbox([self.combo_box_mode_data])
        layout_records = create_hbox([self.button_load, self.button_save])
        layout_clear_history = create_hbox([self.button_restart])

                                                                # Vertical layout
        layout = QVBoxLayout(self._epochs_manager_frame)        # +------------------+
        layout.addWidget(QLabel("ПРОСМОТР ЭПОХ", self))         # | ПРОСМОТР ЭПОХ    |
        layout.addLayout(layout_show_epoch)                     # | Show   #         |
        layout.addLayout(layout_delete_epoch)                   # | Delete   #       |
        layout.addLayout(layout_data)                           # | Новые/Загрузить  |
        layout.addLayout(layout_records)                        # | Load   Save      |
        layout.addLayout(layout_clear_history)                  # | Clear            |
                                                                # +------------------+
    

    # =======================
    # =====   Сигналы    ====
    # =======================
    

    # =======================
    # =====   Логика    =====
    # =======================

    

