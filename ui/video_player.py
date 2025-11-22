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
# 
# закрытие окна (и остановка видео) происходит при нажатии на кнопку Escape или по окончании последовательности стимулов
# окончание последовательности стимулов вызывает сигнал stimuliFinished


class StimuliPresentation(QWidget):
    """
    Класс для последовательного воспроизведения серии стимулов в указанном порядке.
    
    Args:
        video_files  (list[str]):    Пути к видеофайлам.
        order        (list[int]):    Порядок воспроизведения (индексы video_files).
        monitor      (int):          Номер монитора для полноэкранного вывода.
    
    Signals:
        _videoEnded (pyqtSignal):  
                Срабатывает, когда VLC заканчивает проигрывать очередное видео. 
                **Внутренний сигнал**: используется для связки видео в VLC-плеере. Не для внешнего использования.
        stimuliFinished (pyqtSignal):
                Срабатывает, когда все видео в последовательности стимулов проиграны. Для использования извне.
    
    Example:
        >>> widget = StimuliPresentation(
        ...     video_files=["a.mp4", "b.mp4", "c.mp4"],
        ...     order=[2, 0, 1],
        ...     monitor=1
        ... )
        >>> widget.show()
    """

    _videoEnded = pyqtSignal()      # сигнал окончания очередного видео
    stimuliFinished = pyqtSignal()  # сигнал окончания последовательности стимулов

    def __init__(self, video_files, order, monitor=1):

        super().__init__()

        # == Монитор и окно ==
        screens = QApplication.instance().screens()
        target_monitor = screens[monitor - 1].geometry()
        self.setGeometry(target_monitor)
        self.showFullScreen()                 

        # == Данные ==
        self.video_files = video_files
        self.order = order
        self._current_index = 0                  # индекс текущего видео в order

        # == VLC setup ==
        self._instance = vlc.Instance(
            '--file-caching=300',           # буферизация
            '--quiet'                       # минимизация логов
            )
        self._player = self.instance.media_player_new()

        # == Контейнер для вывода ==
        video_widget = QWidget(self)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0,0,0,0)
        layout.setSpacing(0)
        layout.addWidget(video_widget)

        # Привязываем видео к PyQt5 виджету
        if sys.platform.startswith("win"):
            self._player.set_hwnd(int(video_widget.winId()))        # сообщаем плееру ID системного окна
        elif sys.platform.startswith("linux"):
            self._player.set_xwindow(int(video_widget.winId()))
        elif sys.platform.startswith("darwin"):
            self._player.set_nsobject(int(video_widget.winId()))

        # == События VLC ==
        events = self._player.event_manager()
        events.event_attach(vlc.EventType.MediaPlayerEndReached, self._on_end_reached)

        # Подключаем сигнал окончания видео к запуску следующего видео
        self._videoEnded.connect(self._play_next_video)  

        # Запуск первого видео
        self._play_next_video()

    def _play_next_video(self):
        """
        Проигрывает следующее видео из списка order.
        Закрывает плеер, когда все видео из списка воспроизведены.
        """
        if self._current_index >= len(self.order):
            self.close()
            return

        video_idx = self.order[self._current_index]
        video_path = self.video_files[video_idx]

        # создаём новый экземпляр media для каждого видео
        media = self.instance.media_new(video_path)
        self._player.set_media(media)
        self._player.play()

        self._current_index += 1
       
    def _on_end_reached(self, event):
        """
        Вызывается, когда получает сигнал о завершении очередного видео. 
        Срабатывает :attr:`_videoEnded` для вызова функции запуска следующего видео  в GUI-потоке.
        """
        self._videoEnded.emit()

    def keyPressEvent(self, event: QKeyEvent):
        """
        Останавливает воспроизведение видео и закрывает окно по нажатию на esc.
        Срабатывает :attr:`stimuliFinished` для сообщения вовне о заверешении показа стимулов.
        Args:
            event (QKeyEvent): Key press event.
        """
        if event.key() == Qt.Key_Escape:
            if self._player is not None:
                self._player.stop()
            self.stimuliFinished.emit()
            self.close()
        else:
            super().keyPressEvent(event)

