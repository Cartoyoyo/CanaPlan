import configparser
import os

from qgis.PyQt.QtCore import Qt
from qgis.PyQt.QtGui import QIcon
from qgis.PyQt.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QFrame,
)


class AboutDialog(QDialog):

    def __init__(self, plugin_dir, parent=None):
        super().__init__(parent)
        self.plugin_dir = plugin_dir
        self.setWindowTitle("À propos de BET Humide")
        self.setModal(True)
        self.setMinimumWidth(420)
        icon_path = os.path.join(self.plugin_dir, "icon", "icon.png")
        if os.path.exists(icon_path):
            self.setWindowIcon(QIcon(icon_path))
        self._build_ui()

    def _read_metadata(self):
        config = configparser.ConfigParser()
        config.read(os.path.join(self.plugin_dir, "metadata.txt"), encoding="utf-8")
        general = config["general"] if "general" in config else {}
        return {
            "name": general.get("name", "BET Humide"),
            "version": general.get("version", ""),
            "author": general.get("author", ""),
            "email": general.get("email", ""),
            "about": general.get("about", ""),
            "homepage": general.get("homepage", ""),
            "linkedin": general.get("linkedin", ""),
        }

    def _build_ui(self):
        meta = self._read_metadata()
        layout = QVBoxLayout(self)
        layout.setSpacing(10)

        header = QVBoxLayout()
        logo_path = os.path.join(self.plugin_dir, "icon", "logo-full.svg")
        if os.path.exists(logo_path):
            logo_label = QLabel()
            logo_pixmap = QIcon(logo_path).pixmap(360, 94)
            logo_label.setPixmap(logo_pixmap)
            logo_label.setAlignment(Qt.AlignCenter)
            header.addWidget(logo_label)

        version = QLabel(f"Version {meta['version']}")
        version.setAlignment(Qt.AlignCenter)
        header.addWidget(version)
        layout.addLayout(header)

        sep = QFrame()
        sep.setFrameShape(QFrame.HLine)
        sep.setFrameShadow(QFrame.Sunken)
        layout.addWidget(sep)

        about = QLabel(meta["about"])
        about.setWordWrap(True)
        layout.addWidget(about)

        if meta["linkedin"]:
            author = QLabel(f'Auteur : <a href="{meta["linkedin"]}">{meta["author"]}</a>')
        else:
            author = QLabel(f"Auteur : {meta['author']} ({meta['email']})")
        author.setOpenExternalLinks(True)
        author.setWordWrap(True)
        layout.addWidget(author)

        if meta["homepage"]:
            homepage = QLabel(f'<a href="{meta["homepage"]}">{meta["homepage"]}</a>')
            homepage.setOpenExternalLinks(True)
            layout.addWidget(homepage)

        btn_close = QPushButton("Fermer")
        btn_close.setDefault(True)
        btn_close.clicked.connect(self.accept)
        layout.addWidget(btn_close, alignment=Qt.AlignRight)
