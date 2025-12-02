import sys, os, time, tempfile, subprocess
import time

import subprocess

from PyQt5.QtWidgets import (
    QFrame, QGridLayout, QHBoxLayout, QVBoxLayout, QLabel, QScrollArea, QSizePolicy
)
from PyQt5.QtGui import QFont, QFontMetrics
from PyQt5.QtCore import Qt

from utils.ui_helpers import create_button, spin_box, check_box, combo_box, create_lineedit
from utils.layout_utils import create_hbox, create_vbox

from PyQt5.QtWidgets import QApplication, QWidget, QVBoxLayout
from PyQt5.QtCore import Qt, pyqtSignal, QTimer
from PyQt5.QtCore import Qt, QPoint, QEvent
from PyQt5.QtGui import QKeyEvent

from utils.video_helpers import *
from utils.add_to_json import save_sequence_to_json
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
        self._finilize()

    def _init(self):
        self._stimulus_labels = []
        # For selecting multiple labels
        self.selected = []

        # Две зоны
        self.top_zone_y = 40
        self.bottom_zone_y = 150

        self.top_line = [] # стимулы-заготовки
        self.bottom_line = [] # рабочая последовательность

        self._stimuli_filename = r"resources/saved_stimuli.json"

    def _setup_ui(self):
        self._label_load_sequence = QLabel("Загрузить существующую последовательность стимулов", self)

        # --- ComboBox для выбора последовательности ---
        self._sequence_combo = combo_box([], parent=self)
        self._button_load_sequence = create_button("Загрузить", parent=self)
        self._layout_load_sequence = create_hbox([self._sequence_combo, self._button_load_sequence])

        # --- Метки для отображения ---
        self._set_label = QLabel("")
        self._order_label = QLabel("")
        self._layout_loaded_sequence = create_vbox([self._set_label, self._order_label])


        self._label_new_stimuli_sequence = QLabel("Создать новую последовательность стимулов", self)
        self._label_instruction = QLabel(
            "Инструкция:\n"+
            "1. Стимулы должны лежать в resources/videoSamples.\n"+
            "2. Добавьте стимулы в рабочее поле (выбрать стимул -> добавить).\n"+
            "3. Составьте из стимулов желаемую последовательность, перенося их в нижний ряд.\n"+
            "4. Нажатие правой кнопкой мыши на стимул позволит задать количество его повторений.", 
            self)

        label = QLabel("Выбрать стимул:", self)
        self._combo_box_choose_stimulus = combo_box(items=os.listdir(r"resources/videoSamples"), 
                                        curr_item_idx=1, parent=self)
        self._button_add_stimulus = create_button("Добавить", parent=self)

        # ------------------
        self._make_group_button = create_button("Сделать группой", disabled=True, parent=self)
        self._button_check_sound = create_button("Проверить стимул", parent=self)
        self._label_stimulus_status = QLabel("", self)
        self._button_add_sound = create_button("Добавить пустую звуковую дорожку", parent=self)
        self._layout_choose_stimulus = create_hbox([label, 
                                                    self._combo_box_choose_stimulus, self._button_add_stimulus, self._make_group_button,
                                                    self._button_check_sound, self._label_stimulus_status, self._button_add_sound])
        # ------------------

        # Рабочая область
        self.workspace = QFrame()
        self.workspace.setStyleSheet("background-color: white; border: 1px solid gray;")
        self.workspace.setFrameShape(QFrame.Box)
        self.workspace.setMinimumHeight(200)

        label = QLabel("Название набора стимулов:")
        self._lineedit_sequence_name = create_lineedit(parent=self)
        self._button_create_sequence = create_button("Создать набор", parent=self)
        self._layout_create_sequence = create_hbox([label, self._lineedit_sequence_name, self._button_create_sequence])

        
    def _setup_layout(self):
        layout = QVBoxLayout(self)
        layout.addWidget(self._label_load_sequence)
        layout.addLayout(self._layout_load_sequence)
        layout.addLayout(self._layout_loaded_sequence)
        layout.addWidget(self._label_new_stimuli_sequence)          # Надпись блока: Создать новую последовательность стимулов
        layout.addWidget(self._label_instruction)
        layout.addLayout(self._layout_choose_stimulus)              # Добавление нового стимула
        layout.addWidget(self.workspace)
        layout.addLayout(self._layout_create_sequence)

        
    def _setup_connections(self):
        self._button_load_sequence.clicked.connect(self._on_load_selected_sequence_button_click)
        self._button_add_stimulus.clicked.connect(self._on_add_stimulus_button_click)
        self._button_check_sound.clicked.connect(self._on_check_stimulus_button_click)
        self._button_add_sound.clicked.connect(self._on_add_sound_button_click)
        self._make_group_button.clicked.connect(self._on_make_group_button_click)
        self._button_create_sequence.clicked.connect(self._on_create_sequence_button_click)

    def _on_load_selected_sequence_button_click(self):
        seq_name = self._sequence_combo.currentText()
        if not seq_name:
            return

        try:
            with open(self._stimuli_filename, "r", encoding="utf-8") as f:
                data = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            data = {}

        sequence = data.get(seq_name)
        if not sequence:
            self._set_label.setText("Последовательность не найдена")
            self._order_label.setText("")
            return

        # Формируем текст для set
        set_text = "Набор стимулов:\n"
        for num, stim in sequence["set"].items():
            set_text += f"{num}: {stim}\n"
        self._set_label.setText(set_text)

        # Формируем текст для order
        order_text = "Порядок предъявления:\n" + ", ".join(map(str, sequence["order"]))
        self._order_label.setText(order_text)

        # --- Полностью очищаем нижнюю линию и все её виджеты ---
        for lbl in getattr(self, "bottom_line", []):
            lbl.deleteLater()
        self.bottom_line = []

        # --- Создаём объекты для уникальных стимулов ---
        stim_objects = {}
        x_offset = 20
        margin = 10
        y = self.bottom_zone_y

        for num, stim_name in sequence["set"].items():
            lbl = DraggableLabel(stim_name, self.workspace)
            lbl.zone = "bottom"
            lbl.move(x_offset, y)
            lbl.show()
            stim_objects[num] = lbl
            self.bottom_line.append(lbl)
            x_offset += lbl.width() + margin

        # --- Устанавливаем repeats по количеству вхождений в order ---
        from collections import Counter
        order_counts = Counter(sequence["order"])
        for idx, lbl in stim_objects.items():
            lbl.repeats = order_counts[int(idx)] if int(idx) in order_counts else 1
            lbl.update()

        # --- Перераспределяем стимулы по нижней линии красиво ---
        self.realign_lines()
        self.update_order()

        self._lineedit_sequence_name.setText(seq_name)

    def _on_create_sequence_button_click(self):
        stimulus_sequnce = self.update_order(get_order=True)
        sequence_name = self._lineedit_sequence_name.text()
       
        save_sequence_to_json(self._stimuli_filename, sequence_name, stimulus_sequnce)
        self._update_sequence_combo()


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
        # -----------------------------------------------
        # add stimulus in workspace
        # -----------------------------------------------
        curr_stimulus = self._combo_box_choose_stimulus.currentText()
        lbl = DraggableLabel(curr_stimulus, self.workspace)
        # lbl.installEventFilter(self)
        
        lbl.zone = "top"
        lbl.move(20 + len(self.top_line) * 120, self.top_zone_y)
        lbl.show()
        self.top_line.append(lbl)
        self.update_order()

    def _update_sequence_combo(self):
        self._sequence_combo.clear()
        try:
            with open(self._stimuli_filename, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, dict):
                    self._sequence_combo.addItems(data.keys())
        except (FileNotFoundError, json.JSONDecodeError):
            print("файл пока пустой")
            pass  # файл пока пустой



    def handle_relocate(self, label):
        x = label.x()
        y = label.y()

        # если ниже порога — значит нижняя линия
        if y > 100:
            if label.zone == "top":
                self.move_top_to_bottom(label)
        else:
            if label.zone == "bottom":
                self.move_bottom_to_top(label)


        self.realign_lines()
        self.update_order()


    def move_top_to_bottom(self, label):
        if label in self.top_line:
            self.top_line.remove(label)
        if label not in self.bottom_line:
            self.bottom_line.append(label)
        label.zone = "bottom"


    def move_bottom_to_top(self, label):
        if label in self.bottom_line:
            self.bottom_line.remove(label)
        if label not in self.top_line:
            self.top_line.append(label)
        label.zone = "top"


    def return_to_top(self, label):
        self.move_bottom_to_top(label)
        self.realign_lines()
        self.update_order()
    
    def realign_lines(self):
    # ------------------------
    # Красиво выстраиваем линии
    # ------------------------
        # сортировка по текущему порядку (слева направо) на основе X-координаты
        self.top_line.sort(key=lambda lbl: lbl.x())
        self.bottom_line.sort(key=lambda lbl: lbl.x())

        # аккуратное выстраивание без наложений
        x_offset = 20
        margin = 10
        for lbl in self.top_line:
            lbl.move(x_offset, self.top_zone_y)
            x_offset += lbl.width() + margin


        x_offset = 20
        for lbl in self.bottom_line:
            lbl.move(x_offset, self.bottom_zone_y)
            x_offset += lbl.width() + margin
   
    def update_order(self, get_order=False):
        order = []
        for lbl in self.bottom_line:
            order.extend([lbl.base_text] * lbl.repeats)
        print("Текущий порядок (нижняя линия):", order)
        if get_order:
            return order

    
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
    
    def _finilize(self):
        self._update_sequence_combo()
    
    # def eventFilter(self, obj, event):
    #     # ловим отпускание кнопки мыши меткой, чтобы обновить порядок
    #     if isinstance(obj, DraggableLabel) and event.type() == QEvent.MouseButtonRelease:
    #         self.update_order()
    #     return super().eventFilter(obj, event)

    
    # def eventFilter(self, obj, event):
    # # -----------------------------------------------
    # # Track clicks to select items
    # # -----------------------------------------------
    #     if isinstance(obj, DraggableLabel):
    #         if event.type() == QEvent.MouseButtonPress:
    #             if obj in self.selected:
    #                 self.selected.remove(obj)
    #                 obj.setStyleSheet("background-color: lightgray; border: 1px solid black; padding: 5px;")
    #             else:
    #                 self.selected.append(obj)
    #                 obj.setStyleSheet("background-color: yellow; border: 2px solid orange; padding: 5px;")
    #         if event.type() == QEvent.MouseButtonRelease:
    #             self.update_order()


        # return super().eventFilter(obj, event)



if __name__ == '__main__':
    app = QApplication(sys.argv) 
    main = StimuliCreation()         # открыть Qt-окно приложения
    main.show()

    sys.exit(app.exec_())
