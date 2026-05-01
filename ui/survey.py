import csv
import json
import os
from datetime import datetime

from PyQt5.QtCore import Qt, QSignalBlocker, pyqtSignal
from PyQt5.QtGui import QColor, QFont, QPainter, QPen
from PyQt5.QtWidgets import (
    QButtonGroup,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QRadioButton,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)


DEFAULT_SURVEY_PATH = os.path.join("resources", "survey_default.json")
DEFAULT_OUTPUT_DIR = os.path.join("data", "survey_responses")


def load_survey_config(path=DEFAULT_SURVEY_PATH):
    with open(path, "r", encoding="utf-8") as f:
        payload = json.load(f)

    if isinstance(payload, list):
        return {"title": "Опросник", "pages": [{"title": "", "questions": payload}]}
    if not isinstance(payload, dict):
        raise ValueError("Survey config must be a JSON object or a list of questions.")

    if "pages" in payload:
        pages = payload.get("pages")
        if not isinstance(pages, list) or not pages:
            raise ValueError("Survey config 'pages' must be a non-empty list.")
        for page in pages:
            questions = page.get("questions") if isinstance(page, dict) else None
            if not isinstance(questions, list) or not questions:
                raise ValueError("Each survey page must contain a non-empty 'questions' list.")
    else:
        questions = payload.get("questions")
        if not isinstance(questions, list) or not questions:
            raise ValueError("Survey config must contain a non-empty 'questions' list or 'pages' list.")
        payload["pages"] = [{"title": "", "questions": questions}]
    return payload


class AnalogScaleWidget(QWidget):
    valueChanged = pyqtSignal(int)

    def __init__(self, left_label="", right_label="", initial_value=None, parent=None):
        super().__init__(parent)
        self._left_label = left_label
        self._right_label = right_label
        self._value = initial_value
        self._left_margin = 28
        self._right_margin = 28
        self._line_y = 44
        self.setMinimumHeight(92)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.setMouseTracking(True)

    def value(self):
        return self._value

    def setValue(self, value):
        if value is None:
            self._value = None
        else:
            self._value = max(0, min(100, int(round(value))))
        self.valueChanged.emit(self._value if self._value is not None else -1)
        self.update()

    def _scale_bounds(self):
        left = self._left_margin
        right = max(left + 1, self.width() - self._right_margin)
        return left, right

    def _set_value_from_x(self, x):
        left, right = self._scale_bounds()
        x = max(left, min(right, x))
        self.setValue((x - left) / (right - left) * 100)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._set_value_from_x(event.x())

    def mouseMoveEvent(self, event):
        if event.buttons() & Qt.LeftButton:
            self._set_value_from_x(event.x())

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        left, right = self._scale_bounds()
        line_y = self._line_y

        painter.setPen(QPen(QColor("#9a9892"), 3, Qt.SolidLine, Qt.RoundCap))
        painter.drawLine(left, line_y, right, line_y)

        if self._value is not None:
            x = left + (right - left) * self._value / 100
            painter.setPen(QPen(QColor("#6a7b76"), 3))
            painter.setBrush(QColor("#a8c686"))
            painter.drawEllipse(int(x) - 8, line_y - 8, 16, 16)

        painter.setPen(QColor("#55524d"))
        painter.setFont(QFont("Helvetica", 9))
        painter.drawText(left, line_y + 24, (right - left) // 2 - 4, 24, Qt.AlignLeft | Qt.AlignTop, self._left_label)
        painter.drawText(
            left + (right - left) // 2 + 4,
            line_y + 24,
            (right - left) // 2,
            24,
            Qt.AlignRight | Qt.AlignTop,
            self._right_label,
        )


class DiscreteScaleWidget(QWidget):
    valueChanged = pyqtSignal(object)

    def __init__(self, labels, values=None, left_label="", right_label="", parent=None):
        super().__init__(parent)
        if not labels:
            raise ValueError("Discrete question requires at least one label.")

        self._labels = labels
        self._values = values or labels
        self._group = QButtonGroup(self)
        self._group.setExclusive(True)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        buttons_layout = QHBoxLayout()
        buttons_layout.setContentsMargins(0, 0, 0, 0)
        buttons_layout.setSpacing(8)

        for idx, label in enumerate(labels):
            btn = QRadioButton(str(label))
            btn.setCursor(Qt.PointingHandCursor)
            self._group.addButton(btn, idx)
            buttons_layout.addWidget(btn, 1, Qt.AlignCenter)

        layout.addLayout(buttons_layout)

        if left_label or right_label:
            anchors_layout = QHBoxLayout()
            anchors_layout.setContentsMargins(0, 0, 0, 0)
            anchors_layout.setSpacing(12)

            left = QLabel(left_label)
            left.setObjectName("survey_scale_anchor")
            left.setWordWrap(True)
            left.setAlignment(Qt.AlignLeft | Qt.AlignTop)

            right = QLabel(right_label)
            right.setObjectName("survey_scale_anchor")
            right.setWordWrap(True)
            right.setAlignment(Qt.AlignRight | Qt.AlignTop)

            anchors_layout.addWidget(left, 1)
            anchors_layout.addWidget(right, 1)
            layout.addLayout(anchors_layout)

        self._group.buttonClicked[int].connect(lambda _: self.valueChanged.emit(self.value()))

    def value(self):
        idx = self._group.checkedId()
        if idx < 0:
            return None
        return self._values[idx]

    def setValue(self, value):
        blocker = QSignalBlocker(self._group)
        matched_idx = None
        for idx, option_value in enumerate(self._values):
            if option_value == value or str(option_value) == str(value):
                matched_idx = idx
                break

        if matched_idx is None:
            self._group.setExclusive(False)
            checked = self._group.checkedButton()
            if checked is not None:
                checked.setChecked(False)
            self._group.setExclusive(True)
        else:
            button = self._group.button(matched_idx)
            if button is not None:
                button.setChecked(True)

        del blocker
        self.valueChanged.emit(self.value())


class TextAnswerWidget(QWidget):
    valueChanged = pyqtSignal(object)

    def __init__(self, placeholder="", parent=None):
        super().__init__(parent)
        self._input = QLineEdit()
        self._input.setPlaceholderText(placeholder)
        self._input.textChanged.connect(lambda _: self.valueChanged.emit(self.value()))

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._input)

    def value(self):
        text = self._input.text().strip()
        return text or None

    def setValue(self, value):
        self._input.setText("" if value is None else str(value))


class QuestionWidget(QFrame):
    def __init__(self, question, parent=None):
        super().__init__(parent)
        self.question = question
        self.question_id = question.get("id")
        self.required = bool(question.get("required", True))
        self.setObjectName("survey_question")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 16, 18, 16)
        layout.setSpacing(12)

        title = QLabel(question.get("text", ""))
        title.setWordWrap(True)
        title.setObjectName("survey_question_text")
        layout.addWidget(title)

        question_type = question.get("type")
        if question_type == "discrete":
            self.scale = DiscreteScaleWidget(
                labels=question.get("labels", []),
                values=question.get("values"),
                left_label=question.get("left", ""),
                right_label=question.get("right", ""),
                parent=self,
            )
        elif question_type == "analog":
            self.scale = AnalogScaleWidget(
                left_label=question.get("left", ""),
                right_label=question.get("right", ""),
                initial_value=question.get("initial"),
                parent=self,
            )
        elif question_type == "text":
            self.scale = TextAnswerWidget(question.get("placeholder", ""), parent=self)
        else:
            raise ValueError(f"Unsupported question type: {question_type}")

        layout.addWidget(self.scale)

    def value(self):
        return self.scale.value()

    def setValue(self, value):
        if hasattr(self.scale, "setValue"):
            self.scale.setValue(value)

    def mark_invalid(self, invalid):
        self.setProperty("invalid", invalid)
        self.style().unpolish(self)
        self.style().polish(self)


class QuestionnaireWindow(QWidget):
    submitted = pyqtSignal(dict)

    def __init__(self, config_path=DEFAULT_SURVEY_PATH, output_dir=DEFAULT_OUTPUT_DIR, participant_id=None, parent=None):
        super().__init__(parent)
        self.config_path = config_path
        self.output_dir = output_dir
        self.config = load_survey_config(config_path)
        self.pages = self.config["pages"]
        self.question_widgets = []
        self.page_question_widgets = []
        self.current_page_index = 0
        self._loading_answers = False
        self._dirty = False

        self.setWindowTitle(self.config.get("title", "Опросник"))
        self.resize(820, 720)
        self._setup_ui()
        self._apply_local_style()
        if participant_id:
            self.participant_input.setText(participant_id)
            self.load_saved_state_for_participant()

    def _setup_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(24, 20, 24, 20)
        root.setSpacing(14)

        title = QLabel(self.config.get("title", "Опросник"))
        title.setObjectName("survey_title")
        title.setWordWrap(True)
        root.addWidget(title)

        description_text = self.config.get("description")
        if description_text:
            description = QLabel(description_text)
            description.setObjectName("survey_description")
            description.setWordWrap(True)
            root.addWidget(description)

        participant_row = QHBoxLayout()
        participant_label = QLabel("ID испытуемого")
        self.participant_input = QLineEdit()
        self.participant_input.setPlaceholderText("например, S001")
        self.participant_input.editingFinished.connect(self.load_saved_state_for_participant)
        participant_row.addWidget(participant_label)
        participant_row.addWidget(self.participant_input, 1)
        root.addLayout(participant_row)

        self.page_label = QLabel("")
        self.page_label.setObjectName("survey_page_label")
        self.page_label.setWordWrap(True)
        root.addWidget(self.page_label)

        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QFrame.NoFrame)
        scroll_body = QWidget()
        self.scroll_layout = QVBoxLayout(scroll_body)
        self.scroll_layout.setContentsMargins(0, 0, 0, 0)
        self.scroll_layout.setSpacing(12)

        for page in self.pages:
            page_widgets = []
            for question in page["questions"]:
                widget = QuestionWidget(question)
                if hasattr(widget.scale, "valueChanged"):
                    widget.scale.valueChanged.connect(self._on_answer_changed)
                self.question_widgets.append(widget)
                page_widgets.append(widget)
                self.scroll_layout.addWidget(widget)
            self.page_question_widgets.append(page_widgets)

        self.scroll_layout.addStretch(1)
        self.scroll.setWidget(scroll_body)
        root.addWidget(self.scroll, 1)

        bottom_row = QHBoxLayout()
        self.status_label = QLabel("")
        self.status_label.setObjectName("survey_status")
        self.back_button = QPushButton("Назад")
        self.back_button.clicked.connect(self.go_to_previous_page)
        self.next_button = QPushButton("Дальше")
        self.next_button.clicked.connect(self.go_to_next_page)
        bottom_row.addWidget(self.status_label, 1)
        bottom_row.addWidget(self.back_button)
        bottom_row.addWidget(self.next_button)
        root.addLayout(bottom_row)
        self.show_page(0)

    def _on_answer_changed(self, value):
        if not self._loading_answers:
            self._dirty = True

    def show_page(self, page_index):
        page_index = max(0, min(page_index, len(self.pages) - 1))
        self.current_page_index = page_index

        for idx, page_widgets in enumerate(self.page_question_widgets):
            visible = idx == page_index
            for widget in page_widgets:
                widget.setVisible(visible)

        page = self.pages[page_index]
        page_title = page.get("title") or f"Страница {page_index + 1}"
        self.page_label.setText(f"{page_title} ({page_index + 1}/{len(self.pages)})")
        self.back_button.setEnabled(page_index > 0)
        self.next_button.setText("Завершить" if page_index == len(self.pages) - 1 else "Дальше")
        self.status_label.setText("")
        self.scroll.verticalScrollBar().setValue(0)

    def current_page_widgets(self):
        return self.page_question_widgets[self.current_page_index]

    def validate_widgets(self, widgets):
        missing = []
        for widget in widgets:
            widget.mark_invalid(False)
            if widget.required and widget.value() is None:
                widget.mark_invalid(True)
                missing.append(widget.question_id)
        return missing

    def go_to_previous_page(self):
        self.show_page(self.current_page_index - 1)

    def go_to_next_page(self):
        missing = self.validate_widgets(self.current_page_widgets())
        if missing:
            self.status_label.setText("Заполните обязательные вопросы на этой странице.")
            return

        if self.current_page_index == len(self.pages) - 1:
            self.submit()
        else:
            self.save_draft()
            self.show_page(self.current_page_index + 1)

    def collect_answers(self, validate_required=True):
        answers = {}
        missing = []

        for widget in self.question_widgets:
            value = widget.value()
            if validate_required:
                widget.mark_invalid(False)
            answers[widget.question_id] = value
            if validate_required and widget.required and value is None:
                widget.mark_invalid(True)
                missing.append(widget.question_id)

        return answers, missing

    def apply_answers(self, answers):
        self._loading_answers = True
        try:
            for widget in self.question_widgets:
                if widget.question_id in answers:
                    widget.setValue(answers[widget.question_id])
                    widget.mark_invalid(False)
        finally:
            self._loading_answers = False

    def survey_id(self):
        return self.config.get("id", "survey")

    def _safe_participant_id(self, participant_id):
        return "".join(ch if ch.isalnum() or ch in ("-", "_") else "_" for ch in participant_id)

    def _draft_dir(self):
        return os.path.join(self.output_dir, "_drafts")

    def _draft_path(self, participant_id):
        safe_participant = self._safe_participant_id(participant_id)
        return os.path.join(self._draft_dir(), f"{self.survey_id()}_{safe_participant}.json")

    def _latest_final_path(self, participant_id):
        if not os.path.isdir(self.output_dir):
            return None

        safe_participant = self._safe_participant_id(participant_id)
        prefix = f"{self.survey_id()}_{safe_participant}_"
        candidates = []
        for filename in os.listdir(self.output_dir):
            if filename.startswith(prefix) and filename.endswith(".json"):
                candidates.append(os.path.join(self.output_dir, filename))

        if not candidates:
            return None
        return max(candidates, key=os.path.getmtime)

    def load_saved_state_for_participant(self):
        if self._loading_answers:
            return

        participant_id = self.participant_input.text().strip()
        if not participant_id:
            return

        source_path = self._draft_path(participant_id)
        source_kind = "черновик"
        if not os.path.exists(source_path):
            source_path = self._latest_final_path(participant_id)
            source_kind = "последнее сохранение"

        if not source_path:
            self.status_label.setText("")
            return

        try:
            with open(source_path, "r", encoding="utf-8") as f:
                payload = json.load(f)
            self.apply_answers(payload.get("answers", {}))
            if payload.get("is_draft"):
                self.show_page(payload.get("current_page_index", 0))
            else:
                self.show_page(0)
            self._dirty = source_kind == "черновик"
            self.status_label.setText(f"Загружено: {source_kind}.")
        except (OSError, json.JSONDecodeError) as exc:
            self.status_label.setText(f"Не удалось загрузить сохранение: {exc}")

    def save_draft(self):
        participant_id = self.participant_input.text().strip()
        if not participant_id or not self._dirty:
            return None

        answers, _ = self.collect_answers(validate_required=False)
        if not any(value is not None for value in answers.values()):
            return None

        os.makedirs(self._draft_dir(), exist_ok=True)
        payload = {
            "participant_id": participant_id,
            "survey_id": self.survey_id(),
            "saved_at": datetime.now().isoformat(timespec="seconds"),
            "is_draft": True,
            "current_page_index": self.current_page_index,
            "answers": answers,
        }
        draft_path = self._draft_path(participant_id)
        with open(draft_path, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)
        return draft_path

    def remove_draft(self, participant_id):
        draft_path = self._draft_path(participant_id)
        if os.path.exists(draft_path):
            os.remove(draft_path)

    def submit(self):
        participant_id = self.participant_input.text().strip()
        if not participant_id:
            self.status_label.setText("Укажите ID испытуемого.")
            self.participant_input.setFocus()
            return

        answers, missing = self.collect_answers()
        if missing:
            self.status_label.setText("Заполните обязательные вопросы.")
            return

        payload = {
            "participant_id": participant_id,
            "survey_id": self.survey_id(),
            "saved_at": datetime.now().isoformat(timespec="seconds"),
            "answers": answers,
        }
        json_path, csv_path = self.save_payload(payload)
        self.remove_draft(participant_id)
        self._dirty = False
        self.status_label.setText(f"Сохранено: {os.path.basename(json_path)}")
        self.submitted.emit(payload)
        QMessageBox.information(self, "Опросник", f"Ответы сохранены:\n{json_path}\n{csv_path}")

    def save_payload(self, payload):
        os.makedirs(self.output_dir, exist_ok=True)
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        safe_participant = self._safe_participant_id(payload["participant_id"])
        basename = f"{payload['survey_id']}_{safe_participant}_{stamp}"
        json_path = os.path.join(self.output_dir, f"{basename}.json")
        csv_path = os.path.join(self.output_dir, f"{basename}.csv")

        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)

        row = {
            "participant_id": payload["participant_id"],
            "survey_id": payload["survey_id"],
            "saved_at": payload["saved_at"],
        }
        row.update(payload["answers"])
        with open(csv_path, "w", encoding="utf-8-sig", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=list(row.keys()))
            writer.writeheader()
            writer.writerow(row)

        return json_path, csv_path

    def closeEvent(self, event):
        try:
            self.save_draft()
        finally:
            super().closeEvent(event)

    def _apply_local_style(self):
        self.setStyleSheet(
            """
            QWidget {
                background-color: #f7f6f2;
                color: #2d2d2d;
                font-family: Helvetica, Arial, sans-serif;
                font-size: 11pt;
            }
            QLabel#survey_title {
                font-size: 22pt;
                font-weight: 600;
                color: #2b2e2e;
            }
            QLabel#survey_description {
                color: #55524d;
                line-height: 130%;
            }
            QLabel#survey_page_label {
                color: #2b2e2e;
                font-size: 13pt;
                font-weight: 600;
            }
            QFrame#survey_question {
                background-color: #fbfbfa;
                border: 1px solid #d1cfc9;
                border-radius: 8px;
            }
            QFrame#survey_question[invalid="true"] {
                border: 2px solid #b5646b;
            }
            QLabel#survey_question_text {
                font-size: 12pt;
                font-weight: 600;
            }
            QLabel#survey_scale_anchor {
                color: #55524d;
                font-size: 9pt;
            }
            QLineEdit {
                background-color: #ffffff;
                border: 1px solid #c7c2b8;
                border-radius: 6px;
                padding: 7px 9px;
            }
            QRadioButton {
                spacing: 8px;
            }
            QPushButton {
                background-color: #6a7b76;
                color: #f7f6f2;
                border: none;
                padding: 8px 16px;
                border-radius: 6px;
            }
            QPushButton:hover {
                background-color: #4b5754;
            }
            QLabel#survey_status {
                color: #8a4b52;
            }
            """
        )
