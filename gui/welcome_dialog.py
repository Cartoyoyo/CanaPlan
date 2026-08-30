from qgis.PyQt.QtWidgets import QDialog, QVBoxLayout, QLabel, QPushButton, QFrame
from qgis.PyQt.QtCore import Qt
from qgis.PyQt.QtGui import QFont

from ..tools import i18n


class WelcomeDialog(QDialog):
    NEW    = 1
    OPEN   = 2
    CANCEL = 0

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle(i18n.tr('acc_titre'))
        self.setModal(True)
        self.setMinimumWidth(380)
        self._chosen = self.CANCEL
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(10)

        title = QLabel("CanaPlan")
        font = QFont()
        font.setPointSize(14)
        font.setBold(True)
        title.setFont(font)
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)

        sub = QLabel(i18n.tr('acc_question'))
        sub.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(sub)

        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setFrameShadow(QFrame.Shadow.Sunken)
        layout.addWidget(sep)

        btn_new = QPushButton(i18n.tr('acc_assistant'))
        btn_new.setMinimumHeight(38)
        btn_new.setDefault(True)
        btn_new.clicked.connect(lambda: self._pick(self.NEW))
        layout.addWidget(btn_new)

        btn_open = QPushButton(i18n.tr('acc_ouvrir'))
        btn_open.setMinimumHeight(38)
        btn_open.clicked.connect(lambda: self._pick(self.OPEN))
        layout.addWidget(btn_open)

        btn_cont = QPushButton(i18n.tr('acc_continuer'))
        btn_cont.clicked.connect(self.reject)
        layout.addWidget(btn_cont)

    def _pick(self, result):
        self._chosen = result
        self.accept()

    def chosen(self):
        return self._chosen
