# gui/star_dt_dialog.py
"""Dialogue d'import Star-DT : selection des types d'elements a importer."""

import os

from ..tools import i18n
from qgis.PyQt.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QCheckBox, QDialogButtonBox, QFileDialog, QGroupBox,
)

_ACCEPTED_EXT = (".gml", ".xml")


class StarDtDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle(i18n.tr('sdt_titre'))
        self.setMinimumWidth(520)
        self.setAcceptDrops(True)

        self._files = []  # chemins des fichiers Star-DT selectionnes

        layout = QVBoxLayout(self)

        # Fichier(s) GML
        file_row = QHBoxLayout()
        file_row.addWidget(QLabel(i18n.tr('sdt_fichier_gml')))
        self.file_edit = QLineEdit()
        self.file_edit.setReadOnly(True)
        self.file_edit.setPlaceholderText(
            i18n.tr('sdt_deposer'))
        # Laisse le drop remonter au dialogue plutot que d'etre avale par le champ
        self.file_edit.setAcceptDrops(False)
        btn_browse = QPushButton(i18n.tr('parcourir'))
        btn_browse.clicked.connect(self._browse)
        file_row.addWidget(self.file_edit)
        file_row.addWidget(btn_browse)
        layout.addLayout(file_row)

        # Fichier GPKG de sortie
        out_row = QHBoxLayout()
        out_row.addWidget(QLabel(i18n.tr('sdt_sortie_gpkg')))
        self.out_edit = QLineEdit()
        # Repertoire par defaut = repertoire du projet .bet
        proj_dir = ""
        try:
            from ..tools.projet_bet import project_dir
            proj_dir = project_dir()
        except Exception:
            pass
        if proj_dir:
            self.out_edit.setText(os.path.join(proj_dir, ""))
        self.out_edit.setAcceptDrops(False)
        btn_out = QPushButton(i18n.tr('parcourir'))
        btn_out.clicked.connect(self._browse_out)
        out_row.addWidget(self.out_edit)
        out_row.addWidget(btn_out)
        layout.addLayout(out_row)

        btn_scan = QPushButton(i18n.tr('sdt_analyser'))
        btn_scan.clicked.connect(self._scan)
        layout.addWidget(btn_scan)

        # Types trouves
        self.types_group = QGroupBox(i18n.tr('sdt_types_trouves'))
        self.types_layout = QVBoxLayout(self.types_group)
        layout.addWidget(self.types_group)

        self.checkboxes = {}  # type_name -> QCheckBox
        self.count_labels = {}  # type_name -> QLabel

        # Boutons
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _browse(self):
        # Ouvrir le navigateur dans le repertoire du projet
        start_dir = ""
        try:
            from ..tools.projet_bet import project_dir
            start_dir = project_dir() or ""
        except Exception:
            pass
        paths, _ = QFileDialog.getOpenFileNames(
            self, i18n.tr('sdt_choisir_fichiers'), start_dir,
            i18n.tr('fic_star_dt'))
        if paths:
            self._set_files(paths)

    # ---- Glisser-deposer ----

    def dragEnterEvent(self, event):
        if self._paths_from_mime(event.mimeData()):
            event.acceptProposedAction()
        else:
            event.ignore()

    def dragMoveEvent(self, event):
        if self._paths_from_mime(event.mimeData()):
            event.acceptProposedAction()
        else:
            event.ignore()

    def dropEvent(self, event):
        paths = self._paths_from_mime(event.mimeData())
        if not paths:
            event.ignore()
            return
        event.acceptProposedAction()
        self._set_files(paths)

    @staticmethod
    def _paths_from_mime(mime):
        """Retourne les fichiers .gml/.xml presents dans un drop."""
        if not mime.hasUrls():
            return []
        paths = []
        for url in mime.urls():
            path = url.toLocalFile()
            if not path or not os.path.isfile(path):
                continue
            if path.lower().endswith(_ACCEPTED_EXT):
                paths.append(path)
        return paths

    # ---- Selection ----

    def _set_files(self, paths):
        """Enregistre la selection, met a jour l'affichage, la sortie et le scan."""
        # Dedoublonnage en conservant l'ordre
        seen = set()
        files = []
        for path in paths:
            key = os.path.normcase(os.path.abspath(path))
            if key not in seen:
                seen.add(key)
                files.append(path)
        if not files:
            return

        self._files = files

        if len(files) == 1:
            self.file_edit.setText(files[0])
        else:
            noms = ", ".join(os.path.basename(p) for p in files)
            self.file_edit.setText(i18n.tr('sdt_nb_fichiers', nb=len(files), noms=noms))
        self.file_edit.setToolTip("\n".join(files))
        self.file_edit.setCursorPosition(0)

        # Sortie dans le repertoire du projet .bet si disponible
        try:
            from ..tools.projet_bet import project_dir
            proj_dir = project_dir()
        except Exception:
            proj_dir = ""
        out_dir = proj_dir if proj_dir else os.path.dirname(files[0])
        if len(files) == 1:
            base = os.path.splitext(os.path.basename(files[0]))[0]
        else:
            base = "star_dt_import"
        self.out_edit.setText(os.path.join(out_dir, base + ".gpkg"))

        self._scan()

    def _browse_out(self):
        start_dir = os.path.dirname(self.out_edit.text().strip())
        if not start_dir:
            try:
                from ..tools.projet_bet import project_dir
                start_dir = project_dir() or ""
            except Exception:
                start_dir = ""
        path, _ = QFileDialog.getSaveFileName(
            self, i18n.tr('sdt_gpkg_sortie'),
            os.path.join(start_dir, os.path.basename(self.out_edit.text().strip())),
            i18n.tr('fic_gpkg'))
        if path:
            self.out_edit.setText(path)

    def _scan(self):
        files = [p for p in self._files if os.path.isfile(p)]
        if not files:
            return

        from ..tools.star_dt_import import scan_star_dt
        counts = scan_star_dt(files)

        # Nettoyer l'affichage precedent (widgets et sous-layouts)
        self._clear_types_layout()
        self.checkboxes.clear()
        self.count_labels.clear()

        if not counts:
            label = QLabel(i18n.tr('sdt_aucun_type'))
            label.setStyleSheet("color: #888;")
            self.types_layout.addWidget(label)
            return

        from ..tools.star_dt_import import sort_output_types
        for type_name in sort_output_types(counts.keys()):
            count = counts.get(type_name, 0)
            if count == 0:
                continue
            row = QHBoxLayout()
            cb = QCheckBox(type_name)
            cb.setChecked(True)
            lbl = QLabel(i18n.tr('sdt_nb_elements', nb=count))
            lbl.setStyleSheet("color: #888;")
            row.addWidget(cb)
            row.addStretch()
            row.addWidget(lbl)
            self.types_layout.addLayout(row)
            self.checkboxes[type_name] = cb
            self.count_labels[type_name] = lbl

    def _clear_types_layout(self):
        """Vide le groupe des types (widgets et lignes imbriquees)."""
        while self.types_layout.count():
            item = self.types_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
                continue
            sub = item.layout()
            if sub is not None:
                while sub.count():
                    sub_item = sub.takeAt(0)
                    sub_widget = sub_item.widget()
                    if sub_widget is not None:
                        sub_widget.deleteLater()
                sub.deleteLater()

    def get_selected_types(self):
        """Retourne la liste des types coches."""
        return [name for name, cb in self.checkboxes.items() if cb.isChecked()]

    def file_paths(self):
        """Liste des fichiers Star-DT selectionnes."""
        return list(self._files)

    def file_path(self):
        """Premier fichier selectionne (compatibilite)."""
        return self._files[0] if self._files else ""

    def output_path(self):
        return self.out_edit.text().strip()
