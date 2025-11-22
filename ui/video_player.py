import sys

import vlc

from PyQt5.QtWidgets import QApplication, QWidget, QVBoxLayout
from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QKeyEvent


# воспроизведение стимулов идёт через VLC плеер (https://pypi.org/project/python-vlc/)
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


class StimuliPresentation(QWidget):
    videoEnded = pyqtSignal()  # сигнал окончания видео

    def __init__(self, video_files, order, monitor=1):
        """
        :param video_files: список путей к видеофайлам
        :param order: список индексов video_files, определяющий порядок воспроизведения
        :param monitor: номер монитора для воспроизведения
        """
        super().__init__()

        # Настройка окна на нужный монитор
        screens = QApplication.instance().screens()
        target_monitor = screens[monitor - 1].geometry()
        self.setGeometry(target_monitor)

        self.showFullScreen()                   # полноэкранный режим

        self.video_files = video_files
        self.order = order
        self.current_index = 0                  # индекс текущего видео в order

        # --- VLC setup ---
        self.instance = vlc.Instance(
            '--file-caching=300',           # буферизация
            '--quiet'                       # минимизация логов
            )
        self.player = self.instance.media_player_new()

        # Основной виджет для видео
        self.video_widget = QWidget(self)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0,0,0,0)
        layout.setSpacing(0)
        layout.addWidget(self.video_widget)

        # Привязываем видео к PyQt5 виджету
        if sys.platform.startswith("win"):
            self.player.set_hwnd(int(self.video_widget.winId()))        # сообщаем плееру ID системного окна
        elif sys.platform.startswith("linux"):
            self.player.set_xwindow(int(self.video_widget.winId()))
        elif sys.platform.startswith("darwin"):
            self.player.set_nsobject(int(self.video_widget.winId()))

        # VLC событие окончания видео
        events = self.player.event_manager()
        events.event_attach(vlc.EventType.MediaPlayerEndReached, self._on_end_reached)

        # Подключаем сигнал окончания видео к запуску следующего видео
        self.videoEnded.connect(self._play_next_video) 

        self._play_next_video()

    def _play_next_video(self):
        """Проигрываем следующее видео из списка order"""
        if self.current_index >= len(self.order):
            self.close()
            return

        video_idx = self.order[self.current_index]
        video_path = self.video_files[video_idx]

        # создаём новый экземпляр media для каждого видео
        media = self.instance.media_new(video_path)
        self.player.set_media(media)
        self.player.play()

        self.current_index += 1
       
    def _on_end_reached(self, event):
        """Испускаем сигнал, который вызовет следующий видеофайл в GUI-потоке"""
        self.videoEnded.emit()

    def keyPressEvent(self, event: QKeyEvent):
        """Escape останавливает видео и закрывает окно"""
        if event.key() == Qt.Key_Escape:
            if self.player is not None:
                self.player.stop()
            self.close()
        else:
            super().keyPressEvent(event)

