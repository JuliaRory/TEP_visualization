import sys, os

import vlc
import random

from PyQt5.QtWidgets import QApplication, QWidget, QVBoxLayout, QLabel
from PyQt5.QtCore import Qt, pyqtSignal, QTimer
from PyQt5.QtGui import QPixmap


# воспроизведение стимулов идёт через VLC плеер (https://www.videolan.org/vlc/) <-- он должен быть установлен на компьютер (!!!) 
# на питоне для этого устанавливается библиотека python-vlc (https://pypi.org/project/python-vlc/)
# его необходимо привязать к системному окну открываемого QWidget
# ┌─────────────────────────────────────────────┐
# │ StimuliPresentation : QWidget (fullscreen)  │
# │┌───────────────────────────────────────────┐│
# ││       VLC выводит сюда картинку           ││
# │└───────────────────────────────────────────┘│
# └─────────────────────────────────────────────┘
# сигнал об окончании видео и переключении на новое реализован через pyqtSignal(), чтобы вписывать событие в общий поток GUI:
#  ┌──────────────┐              ┌──────────────┐
#  │ VLC thread   │ --emit-->    │ Qt event loop│
#  │ end reached  │              │ (GUI thread) │
#  └──────────────┘              └──────────────┘
#                                   |
#                                   ↓
#                         _play_next_video()
# 
# закрытие окна (и остановка видео) происходит при нажатии на кнопку Escape или по окончании последовательности стимулов
# окончание последовательности стимулов вызывает сигнал stimuliFinished

class StimuliPresentation_one_by_one(QWidget):
    stimuliStarted = pyqtSignal()
    stimuliFinished = pyqtSignal()
    stimuliPaused = pyqtSignal()
    volumeChanged = pyqtSignal(int)
    playerIsMuted = pyqtSignal()
    currIdxChanged = pyqtSignal(int)
    _videoEnded = pyqtSignal()

    stimulus = pyqtSignal(str)
    
    def __init__(self, monitor=1, volume=80):
        super().__init__()  

        self._volume = volume

        # Настройка экрана
        screens = QApplication.instance().screens()
        target_monitor = screens[monitor - 1].geometry()
        self.setGeometry(target_monitor)
        self.showFullScreen()

        self._init_state()
    
    # ==================================
    # === предварительная подготовка ===
    # ==================================
    def _init_state(self):
        self._stopped = False               # остановлен через esc и сейчас закроется
        self._finished = False               # остановлен т.к. закончилась последовательность
        self._sequence_started = False      # последовательность началась
        self._is_paused = False             # и не на паузе
        
        self.intro_pic_path = os.path.join(r"resources\crossFigures", "cross_image_black_photomark.png")
        final_fig_files = os.listdir(r"resources\final_fig")
        self.final_pic_path = os.path.join(r"resources\final_fig", random.choice(final_fig_files))

        self._configure_player()
               
    def _configure_player(self):
        # VLC player
        self._instance = vlc.Instance(
            '--file-caching=100',
            '--no-video-title-show',
            '--quiet',
            '--no-sub-autodetect-file', 
            '--no-spu'
            )
        self._player = self._instance.media_player_new()

        # Привязка событий
        events = self._player.event_manager()
        events.event_attach(vlc.EventType.MediaPlayerEndReached, self._on_end_reached)

        # Видео виджет
        self._video_widget = QWidget(self)
        self._video_widget.setStyleSheet("background-color: black;")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0,0,0,0)
        layout.addWidget(self._video_widget)

        winid = int(self._video_widget.winId())
        self._player.set_hwnd(winid)
        
        # === Placeholder widget поверх всего ===
        self._placeholder_widget = QLabel(self)
                
        self._final_pic = QPixmap(self.final_pic_path).scaled(
                self.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation
            )
        
        self._intro_pic = QPixmap(self.intro_pic_path).scaled(
                self.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation
            )
        
        self._placeholder_widget.setPixmap(self._intro_pic)
        
        self._placeholder_widget.setGeometry(self.rect())
        self._placeholder_widget.setAlignment(Qt.AlignCenter)
        self._placeholder_widget.setStyleSheet("background-color: black;")
        self._placeholder_widget.show()

    def set_sequence(self, stimuli_sequence, seq_name=None):
        if seq_name is None:
            seq_name = "a new"
        print(f'[VLC player]: set {seq_name} stimuli sequence.')
        self._placeholder_widget.setPixmap(self._intro_pic)
        self._placeholder_widget.show()

        self._cross_dur_ms = stimuli_sequence["cross"]["dur_ms"]      # проигрвать крест 
        self.placeholder_path = os.path.join(r"resources\crossFigures", stimuli_sequence["cross"]["filename"])

        self._main_cross_pic = QPixmap(self.placeholder_path).scaled(
                self.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation
            )
        
        # Видео
        self.order = stimuli_sequence["order"]
        self.video_names = list(stimuli_sequence["set"].values())
        path = r"resources\videoSamples"
        full_video_names = [os.path.join(path, file) for file in self.video_names]
        self.video_files = [full_video_names[i-1] for i in self.order]

        # первый стимул
        self._current_index = 0
        self.currIdxChanged.emit(self._current_index)
        self.stimulus.emit(self.video_names[self.order[self._current_index]-1])

        # Запуск воспроизведения
        self._prepare_next_video()
        print('[VLC player]: press Space to start.')

    # ===============================
    # === цикл проигрывания видео ===
    # ===============================
    def _prepare_next_video(self):
        if self._current_index >= len(self.video_files):
            self._next_media = None
            return

        media = self._instance.media_new(self.video_files[self._current_index])
        media.parse_async()  # preload

        self._next_media = media    # Сохраняем для следующего проигрывания

    def _play_next_video(self):
        if self._stopped:
            print('[VLC player]: stimuli presentation has been stopped.')
            return
        
        if self._next_media is None:
            print("[VLC player]: stimuli sequence has ended.")
            self.stimuliFinished.emit()
            self._finished = True

            self._placeholder_widget.setPixmap(self._final_pic)         # показать финальную картинку
            self._placeholder_widget.show()
            return
        
        if self._current_index == 1:                                    # поменять на крест с белой фотометкой 
            self._placeholder_widget.setPixmap(self._main_cross_pic)

        self._placeholder_widget.show()
        
        # запустить следующее видео
        self.stimulus.emit(self.video_names[self.order[self._current_index]-1])

        self._player.set_media(self._next_media)
        self._player.audio_set_volume(self._volume)
        self._player.play()

        # подготовить следующее видео
        self._current_index += 1
        self.currIdxChanged.emit(self._current_index)
        # if self._current_index < len(self.order):
        #     self.stimulus.emit(self.video_names[self.order[self._current_index]-1])
        self._prepare_next_video()

        self._is_paused = False

        # Скрываем placeholder через 50ms после старта VLC
        delay = 50
        QTimer.singleShot(delay, self._placeholder_widget.hide)

        # Проверяем окончание видео каждые 50ms
        QTimer.singleShot(50, self._check_video_end)
    
    def _check_video_end(self):
        if self._stopped:
            return  # больше ничего не делаем
        if self._player.get_state() == vlc.State.Ended:
            # Сразу показываем placeholder перед следующим видео
            self._placeholder_widget.show()
            QTimer.singleShot(self._cross_dur_ms, self._play_next_video)
        else:
            QTimer.singleShot(50, self._check_video_end)
    
    # =======================
    # ===     события     ===
    # =======================
    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Space:         # start|stop regulation
            self._on_space_pressed()
        
        elif event.key() == Qt.Key_Escape:      # closing
            self.finish()
                    
        elif event.key() == Qt.Key_R:           # restart
            self.restart_sequence()             

                                                # volume regulation

        elif event.key() == Qt.Key_Up:                  # -- volume up
            new_value = min(100, self._volume + 1)
            self.update_volume(new_value)   
        
        elif event.key() == Qt.Key_Down:                # -- volume down
            new_value = max(0, self._volume - 1)
            self.update_volume(new_value)

        elif event.key() == Qt.Key_M:                   # -- mute
            self._player.audio_toggle_mute()
            self.playerIsMuted.emit()

        else:
            super().keyPressEvent(event)

    # ====================
    # ===    логика    ===
    # ====================

    # === показ стимулов ===
    def _on_space_pressed(self):
        # Последовательность ещё не запускалась -> начать показ стимулов
        if not self._sequence_started:
            print("[VLC player]: start the stimuli presentation.")
            self._sequence_started = True
            self.stimuliStarted.emit()
            self._is_paused = False
            self._play_next_video()
            return

        # Последовательность идёт -> остановить показ стимулов
        if not self._is_paused:
            print("[VLC player]: pause the stimuli presentation.")
            self._player.pause()
            self._is_paused = True
            self.stimuliPaused.emit()
            return

        # Показ стимулов на паузе -> продолжить
        if self._is_paused:
            print("[VLC player]: continue the stimuli presentation.")
            self._player.play()
            self._is_paused = False
            self.stimuliPaused.emit()

    def pause_video(self):
        # управление внешней кнопкой 
        self._on_space_pressed()

    def restart_sequence(self):
        print("[VLC player]: restart stimuli presentation.")
        self._player.stop()

        self._is_paused = False
        self._sequence_started = False
        self._stopped = False
        self._finished = False

        self._current_index = 0
        self.currIdxChanged.emit(self._current_index)
        # self.stimulus.emit(self.video_names[self.order[self._current_index]-1])

        self._prepare_next_video()
        self._placeholder_widget.show()
    
    def finish(self):
        print("[VLC player]: finish the stimuli presentation and close the player.")
        self._stopped = True           # ставим флаг остановки
        self._player.stop()
        self._player.release()
        self._instance.release()
        if not self._finished:
            self.stimuliFinished.emit()
        self.close()
    
    @property
    def is_paused(self):
        return self._is_paused

    def _on_end_reached(self, event):
        if self._is_paused:
            return  # если вдруг pause совпал с концом
        
        QTimer.singleShot(0, self._videoEnded.emit)
        
    # === управление звуком === 
    def update_volume(self, value):
        self._volume = value
        self._player.audio_set_volume(self._volume)
        self.volumeChanged.emit(self._volume)
        print("Volume:", self._volume)
    
    def get_last_volume(self):
        return self._volume

    

    
