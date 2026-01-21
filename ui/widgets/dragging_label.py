import sys
from PyQt5.QtWidgets import QApplication, QHBoxLayout, QLabel, QFrame, QMenu, QAction, QInputDialog
from PyQt5.QtCore import Qt, QPoint
from PyQt5.QtGui import QColor, QPainter, QFont

class DraggableLabel(QLabel):
    # def mouseDoubleClickEvent(self, event):
    #     # блокируем двойной клик, чтобы исключить 'пропадание' элемента
    #     event.ignore()
    # fixed_y = 50 # фиксированная горизонтальная линия
    
    def __init__(self, text, parent=None):
        super().__init__(text, parent)
        self.setStyleSheet("background-color: lightgray; border: 1px solid black; padding: 5px;")
        self.setFrameShape(QFrame.Panel)
        self.setFrameShadow(QFrame.Raised)
        self.setLineWidth(2)
        self.dragging = False
        self.offset = QPoint(0, 0)
        self.zone = "top" # "top" – зона заготовок, "bottom" – рабочая последовательность

        self.base_text = text  # исходный текст
        self.repeats = 1       # количество повторений
    
    # ----------------------------
    # paintEvent с бейджем повторений
    # ----------------------------
    def paintEvent(self, event):
        super().paintEvent(event)
        if self.repeats > 1:
            painter = QPainter(self)
            painter.setRenderHint(QPainter.Antialiasing)
            badge_text = f"x{self.repeats}"
            font = QFont("Arial", 10)
            painter.setFont(font)

            metrics = painter.fontMetrics()
            w = metrics.width(badge_text) + 8
            h = metrics.height() + 4

            x = self.width() - w - 4
            y = self.height() - h - 4

            painter.setBrush(QColor(255, 200, 150))
            painter.setPen(Qt.NoPen)
            painter.drawRoundedRect(x, y, w, h, 6, 6)

            painter.setPen(Qt.black)
            painter.drawText(x, y, w, h, Qt.AlignCenter, badge_text)

    # ----------------------------
    # установить количество повторений
    # ----------------------------
    def set_repeats(self, value: int):
        self.repeats = max(1, int(value))
        self.update()

        top = self.window()
        if hasattr(top, "update_order"):
            top.update_order()

    # ----------------------------
    # контекстное меню правой кнопкой
    # ----------------------------
    def contextMenuEvent(self, event):
        menu = QMenu(self)
        set_rep = QAction("Установить повторения…", self)
        menu.addAction(set_rep)
        action = menu.exec_(event.globalPos())
        if action == set_rep:
            val, ok = QInputDialog.getInt(
                self,
                "Повторения",
                f"Введите количество повторений для «{self.base_text}»:",
                value=self.repeats,
                min=1,
                max=999
            )
            if ok:
                self.set_repeats(val)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            modifiers = QApplication.keyboardModifiers()
            # если Ctrl зажат — выделяем стимул
            if modifiers == Qt.ControlModifier:
                self.selected = not getattr(self, "selected", False)
                if self.selected:
                    self.setStyleSheet("background-color: yellow; border: 2px solid red; padding: 5px;")
                else:
                    self.setStyleSheet("background-color: lightgray; border: 1px solid black; padding: 5px;")
                event.accept()
            else:
                # проверяем: если стимул внутри группы — не начинаем drag
                if isinstance(self.parent(), StimulusGroup):
                    # просто передаём событие родителю, чтобы группа могла его обработать
                    event.ignore()
                else:
                    # обычное перемещение стимулов вне группы
                    self.dragging = True
                    self.offset = event.pos()
                    event.accept()
        else:
            super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self.dragging:
            # свободное перемещение по X и Y в пределах workspace
            new_pos = self.mapToParent(event.pos() - self.offset)

            parent = self.parent()
            if parent is not None:
                # ограничиваем, чтобы не выйти за пределы workspace
                max_x = max(0, parent.width() - self.width())
                max_y = max(0, parent.height() - self.height())
                new_x = max(0, min(new_pos.x(), max_x))
                new_y = max(0, min(new_pos.y(), max_y))
                self.move(new_x, new_y)
            else:
                self.move(new_pos)
            event.accept()
        else:
            super().mouseMoveEvent(event)


    def mouseDoubleClickEvent(self, event):
        # двойной клик — вернуть наверх через безопасный вызов
        top = self.window()
        if hasattr(top, "return_to_top"):
            top.return_to_top(self)
        event.accept()

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.dragging = False
            # безопасно найти верхний виджет-окно и вызвать handle_relocate, если он есть
            top = self.window()
            if hasattr(top, "handle_relocate"):
                top.handle_relocate(self)
            event.accept()
        else:
            super().mouseReleaseEvent(event)

class StimulusGroup(QFrame):
    def __init__(self, stimuli_list, parent=None):
        super().__init__(parent)
        self.setFrameShape(QFrame.Panel)
        self.setFrameShadow(QFrame.Raised)
        self.setStyleSheet("background-color: lightblue; border: 2px solid black;")
        self.layout = QHBoxLayout(self)
        self.layout.setContentsMargins(5, 5, 5, 5)
        self.layout.setSpacing(5)
        self.layout.setAlignment(Qt.AlignTop)

        self.stimuli = []
        for stim in stimuli_list:
            stim.setParent(self)
            stim.zone = "bottom"
            stim.selected = False
            stim.setStyleSheet("background-color: lightgray; border: 1px solid black; padding: 5px;")
            self.layout.addWidget(stim)
            self.stimuli.append(stim)
        
        self.dragging = False
        self.offset = QPoint(0, 0)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.dragging = True
            self.offset = event.pos()
            event.accept()
        else:
            super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self.dragging:
            new_pos = self.mapToParent(event.pos() - self.offset)
            parent = self.parent()
            if parent:
                max_x = max(0, parent.width() - self.width())
                max_y = max(0, parent.height() - self.height())
                new_x = max(0, min(new_pos.x(), max_x))
                new_y = max(0, min(new_pos.y(), max_y))
                self.move(new_x, new_y)
            else:
                self.move(new_pos)
            event.accept()
        else:
            super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.dragging = False
            if hasattr(self.parent(), "update_order"):
                self.parent().update_order()
            event.accept()
        else:
            super().mouseReleaseEvent(event)

    def get_order(self):
        order = []
        for stim in self.stimuli:
            repeats = getattr(stim, "repeats", 1)
            order.extend([stim.base_text] * repeats)
        return order