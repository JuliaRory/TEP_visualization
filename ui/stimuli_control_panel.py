from PyQt5.QtWidgets import QFrame, QVBoxLayout, QHBoxLayout, QLabel, QWidget, QSizePolicy
from PyQt5.QtCore import  pyqtSignal

import json
import os

from utils.ui_helpers import create_button, create_spin_box, create_check_box, create_combo_box
from utils.layout_utils import create_hbox, create_vbox

from .video_player import StimuliPresentation_one_by_one
from .stimuli_window import StimuliCreation
from ui.widgets.slider_with_labels import VerticalSliderWithLabel, HorizontalSliderWithLabel
from .audio_player import AudioPlayer

PLAY_LABEL = "▶"
STOP_LABEL = "⏸"

 # ▶  ⏸

class StimuliControlPanel(QFrame):
    """ --- UI для контроля за стимулами --- """

    stimuliPresentation = pyqtSignal(bool)      # -> stimuli presentation is on
    def __init__(self, settings,  output_stream, parent=None):
        super().__init__(parent)

        # self.setObjectName("settings_panel")    # для привязки стиля
        self.setMinimumWidth(200)

        self.settings = settings                        # settings.stimuli_control
        self.output_stream = output_stream

        self._init_state()
        self._setup_ui()
        self._setup_layout()
        self._setup_connections()
        self._finilize()

    def _init_state(self):
        self._restart_stimuli = False
        self._player_window = None

        # Создаем аудиоплеер
        audio_file = os.path.join(r"resources\noise", "TAAC_CN2_coil_42MSO.wav")  # Укажите путь к вашему файлу
        self._audio_player = AudioPlayer(audio_file, initial_volume=self.settings.noise_volume)

    # =======================
    # =====     UI      =====
    # =======================
    def _setup_ui(self):
        
        self._settings_panel = QFrame(self)
        self.button_create_stimuli = create_button(text='Создать', disabled=False, parent=self, w=100)

        self.combo_box_stimuli = create_combo_box([], parent=self, tooltips=True)
        self._button_update_stimuli = create_button(text='⟳', disabled=False, parent=self, w=30)

        self.spin_box_monitor = create_spin_box(1, 3, self.settings.monitor, parent=self)
        
        self.check_box_stimuli_record = create_check_box(self.settings.stimuli_with_record, 'Запись NVX', parent=self)

        self.check_box_noise = create_check_box(self.settings.use_noise, 'Шум', parent=self)
        self.button_noise = create_button(text=PLAY_LABEL, disabled=False, parent=self)

        self.button_stimuli = create_button(text='Запуск', disabled=False, parent=self, w=100)

        self.button_stimuli_restart = create_button(text='Заново', disabled=True)
        self.button_stimuli_pause = create_button(text=PLAY_LABEL, disabled=True, parent=self)

        self.label_stimuli_idx = QLabel("", self)

        self.stimuli_volume_slider = VerticalSliderWithLabel("S")
        self.stimuli_volume_slider.slider.setValue(self.settings.stimuli_volume)

        self.noise_volume_slider = VerticalSliderWithLabel("N")
        self.noise_volume_slider.slider.setValue(self.settings.noise_volume)

    # =======================
    # =====   LAYOUT    =====
    # =======================
    def _setup_layout(self):        

        layout_stimuli_creation = create_vbox([QLabel("СТИМУЛЫ", self), self.button_create_stimuli])
        layout_stimuli = create_hbox([self.combo_box_stimuli, self._button_update_stimuli])
        layout_monitor = create_hbox([QLabel("монитор", self), self.spin_box_monitor])
        layout_nvx = create_hbox([self.check_box_stimuli_record])
        layout_noise = create_hbox([self.check_box_noise, self.button_noise])
        layout_stimuli_launch = create_hbox([self.button_stimuli])
        layout_stimuli_control = create_hbox([self.button_stimuli_pause, self.button_stimuli_restart, self.label_stimuli_idx])

        layout_volume = create_hbox([self.stimuli_volume_slider, self.noise_volume_slider])

        layout_params = QVBoxLayout()
        layout_params.addLayout(layout_noise)                          # | _ шум  вкл/выкл   |
        layout_params.addLayout(layout_monitor)                        # | Монитор __        |
        layout_params.addLayout(layout_nvx)                            # | _запись nvx       |
        layout_params.addLayout(layout_stimuli_launch)                 # | Запуск            |
        layout_params.addLayout(layout_stimuli_control)                # | Пауза  Заново #__ |

        layout_center = QHBoxLayout()
        layout_center.addLayout(layout_params)
        layout_center.addLayout(layout_volume)

                                                                # Vertical layout
        layout = QVBoxLayout(self._settings_panel)              # +-------------------+
        layout.addLayout(layout_stimuli_creation)               # | Стимулы           | 
                                                                # | Создать           |
        layout.addLayout(layout_stimuli)                        # |  __________ ⟳    |
        layout.addLayout(layout_center)                         # | 

        layout = QHBoxLayout(self)
        layout.addWidget(self._settings_panel)
        # layout.addWidget(self.stimuli_volume_slider)            # добавляем справа слайдер для регуляции звука

        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

    # =======================
    # =====   Сигналы    ====
    # =======================
    def _setup_connections(self):
        self.button_create_stimuli.clicked.connect(self._on_create_stimuli_button_click)        # Открыть окно с конструктором стимульной последовательности
        self.button_stimuli.clicked.connect(self._on_stimuli_button_click)                      # Открыть окно для показа стимулов
        self.button_stimuli_pause.clicked.connect(self._on_pause_stimuli_button_click)
        self.button_stimuli_restart.clicked.connect(self._on_restart_stimuli_presentation)

        self.button_noise.clicked.connect(self._on_noise_button_click)

        self.stimuli_volume_slider.valueChanged.connect(self._on_change_stimuli_volume)
        self.noise_volume_slider.valueChanged.connect(self._on_change_noise_volume)

        self._button_update_stimuli.clicked.connect(self._update_combo_box_stimuli)
    
    def _update_connections(self):
        """установление связей после открытия окна с презентацией стимулов"""
        self._player_window.stimuliStarted.connect(self._on_start_stimuli)
        self._player_window.stimuliPaused.connect(self._change_button_pause_stimuli_text)
        self._player_window.stimuliFinished.connect(self._on_finish_stimuli)    

        self._player_window.currIdxChanged.connect(self._on_stimuli_idx_changed)
        self._player_window.stimulus.connect(self._on_stimuli_order_changed)

        self._player_window.volumeChanged.connect(self._on_player_volume_changed)
        self._player_window.playerIsMuted.connect(self._on_player_muted)

    # =======================
    # =====   Логика    =====
    # =======================
    def _on_create_stimuli_button_click(self):
        """Open new window with stimuli constructor"""
        self._create_stimuli_window = StimuliCreation()
        self._create_stimuli_window.show()
    
    def _on_stimuli_button_click(self):
        # если стимул-презентейшн уже открыт -> хотим закрыть
        pw = getattr(self, "_player_window", None)
        if isinstance(pw, QWidget) and not pw.isHidden() and not self._restart_stimuli:
            self.button_stimuli.setText("Запуск")               # опять можно начать презентацию
            self.button_stimuli_restart.setEnabled(True)        # опять нельзя начать заново
            self._player_window.finish()           
                                         # like Escape
        # если не открыт -> хотим начать презентацию и возможно запись nvx
        else:
            if not self._restart_stimuli:   # если первый запуск окна с показом стимулов
                self._player_window = StimuliPresentation_one_by_one(
                                                                    monitor=self.spin_box_monitor.value(), 
                                                                    volume=self.stimuli_volume_slider.slider.value()
                                                                    )
                self._player_window.show()
                self._player_window.raise_()

                self._update_connections()      # устанавливаем связи с новым окном
            
            seq_name = self.combo_box_stimuli.currentText()
            sequence = self._get_sequence(seq_name)

            self._player_window.set_sequence(sequence, seq_name)    # установить новую последовательность стимулов
            self._player_window.restart_sequence()

            self.button_stimuli_pause.setEnabled(True)              # кнопка пауза доступна
            self.button_stimuli_pause.setText(PLAY_LABEL)
            self.button_stimuli.setText("Закрыть")                # меняем надпись на кнопке "старт"

            self._restart_stimuli = False                           
    
    def _on_noise_button_click(self):
        new_label = STOP_LABEL
        if self._audio_player.is_active:
            self._audio_player.pause()
            new_label = PLAY_LABEL
        elif self._audio_player.is_paused:
            self._audio_player.resume()
        else:
            self._audio_player.start_playback()

        self.button_noise.setText(new_label)

    # === изменения состояния кнопок === 
    def _change_button_pause_stimuli_text(self):
        status = PLAY_LABEL if self._player_window.is_paused else STOP_LABEL
        self.button_stimuli_pause.setText(status)
        self.button_stimuli_restart.setEnabled(self._player_window.is_paused)        # можно начать заново

        if self.check_box_noise.isChecked() and self._player_window.is_paused and self._audio_player.is_active:
            self._on_noise_button_click()   # остановить проигрывание шума
        
        if self.check_box_noise.isChecked() and not self._player_window.is_paused and self._audio_player.is_paused:
            self._on_noise_button_click()   # включить проигрывание шума

    def _on_pause_stimuli_button_click(self):
        pw = getattr(self, "_player_window", None)
        if isinstance(pw, QWidget) and not pw.isHidden():
            self._player_window.pause_video()
            self._change_button_pause_stimuli_text()
       
        
    def _on_restart_stimuli_presentation(self):
        self._restart_stimuli = True
        self._on_stimuli_button_click()

    def _on_finish_stimuli(self):
        self.stimuliPresentation.emit(False)

        self.button_stimuli.setText("Запуск")
        self.label_stimuli_idx.setText(f"")
        self.button_stimuli_pause.setText(PLAY_LABEL)
        self.button_stimuli_restart.setEnabled(True)

        if self.check_box_noise.isChecked() and self._audio_player.is_active:
            self._on_noise_button_click()   # остановить проигрывание шума
    
    def _on_start_stimuli(self):
        if self.check_box_stimuli_record:
            self.stimuliPresentation.emit(True)

        self.button_stimuli_pause.setText(STOP_LABEL)
        self.button_stimuli_restart.setEnabled(False)        # можно начать заново

        if self.check_box_noise.isChecked() and not self._audio_player.is_active:
            self._on_noise_button_click()   # начать проигрывание шума
    
    # === отметки о текущем стимуле === 
    def _on_stimuli_idx_changed(self, idx):
        self.label_stimuli_idx.setText(f"#{idx}")

    def _on_stimuli_order_changed(self, filename):
        message = {"stimulus": filename}
        self.output_stream(json.dumps(message))

    # === изменения звука === 
    def _on_player_volume_changed(self, value):
        """изменения от горячих клавиш стрелок вверх-вниз"""
        self.stimuli_volume_slider.slider.setValue(value)
    
    def _on_player_muted(self):
        cur_volume = self.stimuli_volume_slider.slider.value()
        volume = self._player_window.get_last_volume() if cur_volume == 0 else 0
        self.stimuli_volume_slider.slider.setValue(volume)

    def _on_change_stimuli_volume(self, value):
        """изменения от положения слайдера"""
        # если открыто окно со стимулами, поменять там громкость !!! не работает :( !!!
        pw = getattr(self, "_player_window", None)
        if isinstance(pw, QWidget) and not pw.isHidden():
            self._player_window.update_volume(value)
    
    def _on_change_noise_volume(self, value):
        """изменения от положения слайдера"""
        # если открыто окно со стимулами, поменять там громкость !!! не работает :( !!!
        self._audio_player.set_volume(value)

    # === получение последовательности стимулов === 
    def _get_sequence(self, seq_name):
        if not seq_name:
                return
        try:
            with open(self.settings.stimuli_filename, "r", encoding="utf-8") as f:
                data = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            data = {}

        return data.get(seq_name)

    def _update_combo_box_stimuli(self):
        self.combo_box_stimuli.clear()
        try:
            with open(self.settings.stimuli_filename, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, dict):
                    self.combo_box_stimuli.addItems(data.keys())
        except (FileNotFoundError, json.JSONDecodeError):
            print("файл пока пустой")
        
    def _finilize(self):
        self._update_combo_box_stimuli()