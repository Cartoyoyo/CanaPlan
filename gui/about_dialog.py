import configparser
import os

from qgis.PyQt.QtCore import Qt
from qgis.PyQt.QtGui import QIcon
from qgis.PyQt.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QFrame,
)

from ..tools import i18n


class AboutDialog(QDialog):

    def __init__(self, plugin_dir, parent=None):
        super().__init__(parent)
        self.plugin_dir = plugin_dir
        self.setWindowTitle("%s CanaPlan" % i18n.tr('about'))
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
            "name": general.get("name", "CanaPlan"),
            "version": general.get("version", ""),
            "author": general.get("author", ""),
            "email": general.get("email", ""),
            "about": general.get("about", ""),
            "homepage": general.get("homepage", ""),
            "linkedin": general.get("linkedin", ""),
        }

    @staticmethod
    def _sep():
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setFrameShadow(QFrame.Shadow.Sunken)
        return sep

    def _texte_auteur(self):
        """Nom de l'auteur et lien vers le changelog, libellé traduit."""
        return ('<b>%s</b><br><a href="%s#-changelog">%s</a>'
                % (self._meta["author"], self._readme_url,
                   i18n.tr('ab_version', version=self._meta["version"])))

    def _build_ui(self):
        meta = self._read_metadata()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 24, 28, 20)
        layout.setSpacing(14)

        logo_path = os.path.join(self.plugin_dir, "icon", "logo-full.svg")
        if os.path.exists(logo_path):
            logo_label = QLabel()
            logo_label.setPixmap(QIcon(logo_path).pixmap(360, 94))
            logo_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            layout.addWidget(logo_label)

        # Badges : ce sont des rendus du service shields.io, rasterisés à
        # leur taille native (hauteur 20 px). Pour en ajouter ou en modifier
        # un, se reporter à la syntaxe et aux styles officiels :
        #   https://github.com/badges/shields
        # Encodage de l'URL : espace = %20, barre verticale = %7C,
        # tiret littéral = --, plus = %2B.
        # Le badge « langues » annonce l'interface du plugin, traduite en
        # FR / EN / ES / PT / DE ; un badge « docs » ne couvrirait que la
        # documentation.
        readme_url = f"{meta['homepage']}/blob/main/README.md" if meta["homepage"] else "README.md"
        icon_dir = os.path.join(self.plugin_dir, "icon")
        qgis_badge = os.path.join(icon_dir, "badge-qgis.png").replace("\\", "/")
        stareau_badge = os.path.join(icon_dir, "badge-stareau.png").replace("\\", "/")
        langue_badge = os.path.join(icon_dir, "badge-langue.png").replace("\\", "/")
        badges = QLabel(
            '<div style="line-height:220%">'
            f'<a href="https://qgis.org"><img src="{qgis_badge}"></a>&nbsp;&nbsp;'
            f'<a href="{readme_url}#-export-star-eau-cnig--astee-v2024"><img src="{stareau_badge}"></a>&nbsp;&nbsp;'
            f'<a href="{readme_url}"><img src="{langue_badge}"></a>'
            '</div>'
        )
        badges.setOpenExternalLinks(True)
        badges.setAlignment(Qt.AlignmentFlag.AlignCenter)
        badges.setWordWrap(True)
        layout.addWidget(badges)

        layout.addWidget(self._sep())

        # La description vient du dictionnaire de traduction ; metadata.txt
        # sert de repli et alimente encore le gestionnaire d'extensions de
        # QGIS, qui n'a pas de mécanisme de traduction.
        about = QLabel(i18n.tr('ab_description') or meta["about"])
        self.lbl_about = about
        about.setWordWrap(True)
        about.setAlignment(Qt.AlignmentFlag.AlignJustify)
        layout.addWidget(about)

        layout.addWidget(self._sep())

        self._meta = meta
        self._readme_url = readme_url
        author = QLabel(self._texte_auteur())
        self.lbl_author = author
        author.setOpenExternalLinks(True)
        author.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(author)

        github_badge = os.path.join(self.plugin_dir, "icon", "badge-github.png").replace("\\", "/")
        linkedin_badge = os.path.join(self.plugin_dir, "icon", "badge-linkedin.png").replace("\\", "/")
        badge_links = QLabel(
            f'<a href="https://github.com/Cartoyoyo/CanaPlan"><img src="{github_badge}"></a>'
            '&nbsp;&nbsp;'
            f'<a href="https://www.linkedin.com/in/ylaloux/"><img src="{linkedin_badge}"></a>'
        )
        badge_links.setOpenExternalLinks(True)
        badge_links.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(badge_links)

        layout.addWidget(self._sep())

        btn_close = QPushButton(i18n.tr('fermer'))
        self.btn_close = btn_close
        btn_close.setDefault(True)
        btn_close.setFixedWidth(100)
        btn_close.clicked.connect(self.accept)
        btn_row = QHBoxLayout()
        btn_row.addStretch()
        btn_row.addWidget(btn_close)
        btn_row.addStretch()
        layout.addLayout(btn_row)
