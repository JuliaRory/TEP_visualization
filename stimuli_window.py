import sys, os, time, tempfile, subprocess
import time

import subprocess

from PyQt5.QtWidgets import (
    QFrame, QGridLayout, QHBoxLayout, QVBoxLayout, QLabel, QScrollArea, QSizePolicy
)
from PyQt5.QtGui import QFont, QFontMetrics
from PyQt5.QtCore import Qt

from utils.ui_helpers import create_button, spin_box, check_box, combo_box, checkable_combobox
from utils.layout_utils import create_hbox, create_vbox

from PyQt5.QtWidgets import QApplication, QWidget, QVBoxLayout
from PyQt5.QtCore import Qt, pyqtSignal, QTimer
from PyQt5.QtCore import Qt, QPoint, QEvent
from PyQt5.QtGui import QKeyEvent

from utils.video_helpers import *
from widgets.dragging_label import DraggableLabel, LabelGroup

class StimuliCreation(QWidget):
    """
    Должен быть установлен отсюда ffmpeg: https://www.gyan.dev/ffmpeg/builds/ и добавлен в переменные среды (папка bin из скаченного архива).
    Проигрывает интро и затем стимулы в заданном порядке на указанном мониторе.
    Входные стимулы должны иметь аудиодорожку.

    Args:
        intro_file (str): путь к интро-видео
        stimuli_files (list[str]): список стимульных видео
        order (list[int]): порядок воспроизведения стимулов
        monitor (int): номер монитора

    Signals:
        stimuliFinished (pyqtSignal): срабатывает после окончания всего воспроизведения
    """

    def __init__(self):
        super().__init__()

        self.resize(600, 500)

        self._init()
        self._setup_ui()
        self._setup_layout()
        self._setup_connections()

    def _init(self):
        self._stimulus_labels = []
        # For selecting multiple labels
        self.selected = []

    def _setup_ui(self):
        self._label_new_stimuli_sequence = QLabel("Создать новую последовательность стимулов", self)

        label = QLabel("Выберите стимул:", self)
        self._combo_box_choose_stimulus = combo_box(items=os.listdir(r"resources/videoSamples"), 
                                        curr_item_idx=1, parent=self)
        self._button_add_stimulus = create_button("Добавить", parent=self)
        self._make_group_button = create_button("Сделать группой", parent=self)
        self._button_check_sound = create_button("Проверить стимул", parent=self)
        self._label_stimulus_status = QLabel("", self)
        self._button_add_sound = create_button("Добавить пустую звуковую дорожку", parent=self)
        self._layout_choose_stimulus = create_hbox([label, 
                                                    self._combo_box_choose_stimulus, self._button_add_stimulus, self._make_group_button,
                                                    self._button_check_sound, self._label_stimulus_status, self._button_add_sound])


        # Рабочая область
        self.workspace = QFrame()
        self.workspace.setStyleSheet("background-color: white; border: 1px solid gray;")
        self.workspace.setFrameShape(QFrame.Box)
        self.workspace.setMinimumHeight(200)

        
        
        
        
    def _setup_layout(self):
        layout = QVBoxLayout(self)
        layout.addWidget(self._label_new_stimuli_sequence)          # Надпись блока: Создать новую последовательность стимулов
        layout.addLayout(self._layout_choose_stimulus)              # Добавление нового стимула

        layout.addWidget(self.workspace)

        
    def _setup_connections(self):
        self._button_add_stimulus.clicked.connect(self._on_add_stimulus_button_click)
        self._button_check_sound.clicked.connect(self._on_check_stimulus_button_click)
        self._button_add_sound.clicked.connect(self._on_add_sound_button_click)
        self._make_group_button.clicked.connect(self._on_make_group_button_click)

    def _on_make_group_button_click(self):
        # -----------------------------------------------
        # Create group from selected labels
        # -----------------------------------------------

        if len(self.selected) < 2:
            print("Выберите минимум два элемента для группы")
            return


        group = LabelGroup(self.selected, self.workspace)
        group.move(50, LabelGroup.fixed_y)
        group.show()


        for lbl in self.selected:
            lbl.removeEventFilter(self)

        self.selected = []
        self.update_order()

    def _on_add_stimulus_button_click(self):
        curr_stimulus = self._combo_box_choose_stimulus.currentText()
        lbl = DraggableLabel(curr_stimulus, self.workspace)
        lbl.move(20, 20) # начальная позиция
        lbl.show()
        lbl.installEventFilter(self)
        self.update_order()
    
    def _on_check_stimulus_button_click(self):
        curr_stimulus = self._combo_box_choose_stimulus.currentText()
        path_stimulus = os.path.join(r"resources/videoSamples", curr_stimulus)
        text = "Существует" if has_audio(path_stimulus) else "Нету.."
        self._label_stimulus_status.setText(text)
    
    def _on_add_sound_button_click(self):
        curr_stimulus = self._combo_box_choose_stimulus.currentText()
        path_stimulus = os.path.join(r"resources/videoSamples", curr_stimulus)
        output_video = os.path.join(r"resources/videoSamples", f"audio_{curr_stimulus}")
        add_silent_audio(path_stimulus, output_video)
        self._combo_box_choose_stimulus.addItem(f"audio_{curr_stimulus}")
    
    def eventFilter(self, obj, event):
        # ловим отпускание кнопки мыши меткой, чтобы обновить порядок
        if isinstance(obj, DraggableLabel) and event.type() == QEvent.MouseButtonRelease:
            self.update_order()
        return super().eventFilter(obj, event)

    # -----------------------------------------------
    # Track clicks to select items
    # -----------------------------------------------
    def eventFilter(self, obj, event):
        if isinstance(obj, DraggableLabel):
            if event.type() == QEvent.MouseButtonPress:
                if obj in self.selected:
                    self.selected.remove(obj)
                    obj.setStyleSheet("background-color: lightgray; border: 1px solid black; padding: 5px;")
                else:
                    self.selected.append(obj)
                    obj.setStyleSheet("background-color: yellow; border: 2px solid orange; padding: 5px;")
            if event.type() == QEvent.MouseButtonRelease:
                self.update_order()


        return super().eventFilter(obj, event)

    # -----------------------------------------------
    # Update left-to-right order print
    # -----------------------------------------------
    def update_order(self):
        elements = [w for w in self.workspace.children() if isinstance(w, (DraggableLabel, LabelGroup))]
        elements_sorted = sorted(elements, key=lambda x: x.x())

        names = []
        for el in elements_sorted:
            if isinstance(el, DraggableLabel):
                names.append(el.text())
            else:
                group_items = [child.text() for child in el.findChildren(QLabel)]
                names.append(f"Группа({', '.join(group_items)})")

        print("Порядок:", names)

if __name__ == '__main__':
    app = QApplication(sys.argv) 
    main = StimuliCreation()         # открыть Qt-окно приложения
    main.show()

    sys.exit(app.exec_())
