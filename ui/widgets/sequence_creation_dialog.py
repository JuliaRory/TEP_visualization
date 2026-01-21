import sys
import random
from PyQt5.QtWidgets import QVBoxLayout, QHBoxLayout, QPushButton, QLabel,  QLineEdit, QDialog, QFormLayout, QSpinBox
from PyQt5.QtCore import Qt


# ============================
# Диалог генерации последовательности
# ============================
class SequenceDialog(QDialog):
    def __init__(self, stimuli, set, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Создать последовательность")
        self.stimuli = stimuli
        self.set = set

        n_set = [int([key for key, value in self.set.items() if value == stim.base_text][0]) for stim in self.stimuli]

        layout = QVBoxLayout(self)

        # Форма для повторений
        form_layout = QFormLayout()
        self.spin_boxes = {}
        for i, stim in enumerate(self.stimuli):
            spin = QSpinBox()
            spin.setRange(1, 100)
            spin.setValue(stim.repeats)
            form_layout.addRow(f"#{n_set[i]}: " + stim.base_text, spin)
            self.spin_boxes[stim.base_text] = spin
        layout.addLayout(form_layout)

        # Seed
        seed_layout = QHBoxLayout()
        seed_layout.addWidget(QLabel("Seed:"))
        self.seed_edit = QLineEdit("42")  # по умолчанию
        seed_layout.addWidget(self.seed_edit)
        layout.addLayout(seed_layout)

        # Поле для последовательности
        layout.addWidget(QLabel("Сгенерированная последовательность (можно редактировать):"))
        self.sequence_edit = QLineEdit()
        layout.addWidget(self.sequence_edit)

        # Кнопки
        buttons_layout = QHBoxLayout()
        self.generate_btn = QPushButton("Генерировать")
        self.ok_btn = QPushButton("Ок")
        self.cancel_btn = QPushButton("Отмена")
        buttons_layout.addWidget(self.generate_btn)
        buttons_layout.addWidget(self.ok_btn)
        buttons_layout.addWidget(self.cancel_btn)
        layout.addLayout(buttons_layout)

        # Сигналы
        self.generate_btn.clicked.connect(self.generate_sequence)
        self.ok_btn.clicked.connect(self.accept)
        self.cancel_btn.clicked.connect(self.reject)

    def generate_sequence(self):
        # Обновляем repeats
        for stim in self.stimuli:
            stim.repeats = self.spin_boxes[stim.base_text].value()

        # Создаём mapping: номер -> стимул

        n_set = [int([key for key, value in self.set.items() if value == stim.base_text][0]) for stim in self.stimuli]
        self.stim_map ={n_set[i]: stim for i, stim in enumerate(self.stimuli)}

        # Список номеров с учётом повторений
        seq_numbers = []
        for num, stim in self.stim_map.items():
            seq_numbers.extend([num]*stim.repeats)

        # Seed
        try:
            seed_val = int(self.seed_edit.text())
        except ValueError:
            seed_val = 42
        rng = random.Random(seed_val)
        rng.shuffle(seq_numbers)

        self.sequence_numbers = seq_numbers
        self.sequence_edit.setText(", ".join(map(str, seq_numbers)))

    def get_sequence_numbers(self):
        # Считываем из lineedit
        text = self.sequence_edit.text()
        nums = [int(s.strip()) for s in text.split(",") if s.strip()]
        return nums
