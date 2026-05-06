from qgis.PyQt.QtWidgets import QDialog, QVBoxLayout, QLabel, QPushButton, QFrame
from qgis.PyQt.QtCore import Qt
from qgis.PyQt.QtGui import QFont


class WelcomeDialog(QDialog):
    NEW    = 1
    OPEN   = 2
    CANCEL = 0

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("BET_HUMIDE – Réseau Assainissement")
        self.setModal(True)
        self.setMinimumWidth(380)
        self._chosen = self.CANCEL
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(10)

        title = QLabel("BET_HUMIDE")
        font = QFont()
        font.setPointSize(14)
        font.setBold(True)
        title.setFont(font)
        title.setAlignment(Qt.AlignCenter)
        layout.addWidget(title)

        sub = QLabel("Aucun projet n'est chargé.\nQue souhaitez-vous faire ?")
        sub.setAlignment(Qt.AlignCenter)
        layout.addWidget(sub)

        sep = QFrame()
        sep.setFrameShape(QFrame.HLine)
        sep.setFrameShadow(QFrame.Sunken)
        layout.addWidget(sep)

        btn_new = QPushButton("Nouveau projet")
        btn_new.setMinimumHeight(38)
        btn_new.setDefault(True)
        btn_new.clicked.connect(lambda: self._pick(self.NEW))
        layout.addWidget(btn_new)

        btn_open = QPushButton("Ouvrir un projet existant")
        btn_open.setMinimumHeight(38)
        btn_open.clicked.connect(lambda: self._pick(self.OPEN))
        layout.addWidget(btn_open)

        btn_cont = QPushButton("Continuer sans projet")
        btn_cont.clicked.connect(self.reject)
        layout.addWidget(btn_cont)

    def _pick(self, result):
        self._chosen = result
        self.accept()

    def chosen(self):
        return self._chosen
