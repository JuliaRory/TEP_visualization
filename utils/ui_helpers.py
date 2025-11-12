from PyQt5.QtWidgets import QPushButton, QSpinBox, QDoubleSpinBox, QCheckBox, QComboBox, QShortcut
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QStandardItemModel, QStandardItem, QKeySequence, QFont, QFontMetrics
from widgets.checkable_combo_box import CheckableComboBox

def create_button(text, callback=None, checkable=False, parent=None, w=None):
    btn = QPushButton(text, parent)
    btn.setCheckable(checkable)
    if w is not None:
        btn.setFixedWidth(w)
    if callback:
        btn.clicked.connect(callback)
    return btn

def spin_box(min, max, value, data_type = 'int', step=1, decimals=4, parent=None, w=None, h=None, function=None, disabled=False):
    if data_type == 'int':
        spin_box = QSpinBox(parent)
    else:
        spin_box = QDoubleSpinBox(parent)
        spin_box.setDecimals(decimals)
    spin_box.setRange(min, max)
    spin_box.setValue(value)
    spin_box.setSingleStep(step)
    if w is not None:
        spin_box.setFixedWidth(w)
    if h is not None:
        spin_box.setFixedHeight(h)
    if function is not None:
        spin_box.valueChanged.connect(function)
    spin_box.setDisabled(disabled)
    return spin_box

def check_box(state, text='', parent=None, function=None):
    check_box = QCheckBox(text, parent)
    if state:
        check_box.toggle()
    if function is not None:
        check_box.stateChanged.connect(function)
    return check_box

def checkable_combobox(channels, bad_channels, status=False, parent=None):
    combobox = CheckableComboBox(parent)
    for item in channels:
        checked = status if item in bad_channels else not status
        combobox.addItem(item, checked)
    return combobox

def combo_box(items, curr_item=None, curr_item_idx=None, parent=None):
    combo_box = QComboBox(parent)
    combo_box.addItems(items)
    if curr_item is not None:
        combo_box.setCurrentText(curr_item)
    if curr_item_idx is not None:
        combo_box.setCurrentIndex(curr_item_idx)
    return combo_box

def shortcut_button(keyword, function, enabled=True, parent=None):
    shortcut = QShortcut(QKeySequence(keyword), parent)
    shortcut.activated.connect(function)
    shortcut.setEnabled(enabled)
    return shortcut

def shortcut_scale(keyword, spin1, spin2, action, parent=None):
    shortcut = QShortcut(QKeySequence(keyword), parent)
    alpha = 1 if action == 'more' else -1
    shortcut.activated.connect(lambda: (spin1.setValue(spin1.value() + alpha * spin1.singleStep()),
                                        spin2.setValue(spin2.value() + (-1)*alpha * spin2.singleStep())))

# def spin_box_with_unit(unit, min, max, value, step=1, data_type='int', decimals=4, w=None, h=None, function=None, parent=None):
#         box = QWidget(parent)
#         layout = QGridLayout()
#         layout.setSpacing(0)
#         spin_box = self.spin_box(min, max, value, data_type, step, decimals, parent, w, h)
#         if function is not None:
#             spin_box.valueChanged[int].connect(function)
#         label_time = QLabel(unit, self)
#         layout.addWidget(spin_box, 0, 0, 1, 2)
#         layout.addWidget(label_time, 0, 2, 1, 1)
#         box.setLayout(layout)

#         return box

def fit_font_to_width_spinbox(spinbox):
        fs = 12

        font = QFont()
        font.setPointSize(fs)
        fm = QFontMetrics(font)

        text = spinbox.text()

        width = spinbox.width() * (1-.4)
        height = spinbox.height() * (1-.2)

        while (fm.horizontalAdvance(text) > width or fm.height() > height) and fs > 1:
            fs -= 1 
            font.setPointSize(fs)
            fm = QFontMetrics(font)
        
        spinbox.lineEdit().setFont(font)
