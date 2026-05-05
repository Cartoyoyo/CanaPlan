# gui/star_dt_dialog.py
"""Dialogue d'import Star-DT : selection des types d'elements a importer."""

import os
from qgis.PyQt.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QCheckBox, QDialogButtonBox, QFileDialog, QGroupBox,
)


class StarDtDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Importer un fichier Star-DT")
        self.setMinimumWidth(520)

        layout = QVBoxLayout(self)

        # Fichier GML
        file_row = QHBoxLayout()
        file_row.addWidget(QLabel("Fichier GML :"))
        self.file_edit = QLineEdit()
        self.file_edit.setReadOnly(True)
        btn_browse = QPushButton("Parcourir...")
        btn_browse.clicked.connect(self._browse)
        file_row.addWidget(self.file_edit)
        file_row.addWidget(btn_browse)
        layout.addLayout(file_row)

        # Fichier GPKG de sortie
        out_row = QHBoxLayout()
        out_row.addWidget(QLabel("Sortie GPKG :"))
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
        btn_out = QPushButton("Parcourir...")
        btn_out.clicked.connect(self._browse_out)
        out_row.addWidget(self.out_edit)
        out_row.addWidget(btn_out)
        layout.addLayout(out_row)

        btn_scan = QPushButton("Analyser le fichier")
        btn_scan.clicked.connect(self._scan)
        layout.addWidget(btn_scan)

        # Types trouves
        self.types_group = QGroupBox("Types d'elements trouves")
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
        path, _ = QFileDialog.getOpenFileName(
            self, "Fichier Star-DT", start_dir,
            "Star-DT GML (*.gml *.xml);;Tous (*.*)")
        if path:
            self.file_edit.setText(path)
            # Sortie dans le repertoire du projet .bet si disponible
            try:
                from ..tools.projet_bet import project_dir
                proj_dir = project_dir()
            except Exception:
                proj_dir = ""
            out_dir = proj_dir if proj_dir else os.path.dirname(path)
            base = os.path.splitext(os.path.basename(path))[0]
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
            self, "GeoPackage de sortie",
            os.path.join(start_dir, os.path.basename(self.out_edit.text().strip())),
            "GeoPackage (*.gpkg)")
        if path:
            self.out_edit.setText(path)

    def _scan(self):
        path = self.file_edit.text().strip()
        if not path or not os.path.isfile(path):
            return

        from ..tools.star_dt_import import scan_star_dt
        counts = scan_star_dt(path)

        # Nettoyer l'affichage precedent
        for cb in self.checkboxes.values():
            self.types_layout.removeWidget(cb)
            cb.deleteLater()
        for lbl in self.count_labels.values():
            self.types_layout.removeWidget(lbl)
            lbl.deleteLater()
        self.checkboxes.clear()
        self.count_labels.clear()

        if not counts:
            label = QLabel("Aucun type d'element Star-DT detecte.")
            label.setStyleSheet("color: #888;")
            self.types_layout.addWidget(label)
            return

        from ..tools.star_dt_import import _OUTPUT_TYPE_ORDER
        for type_name in _OUTPUT_TYPE_ORDER:
            count = counts.get(type_name, 0)
            if count == 0:
                continue
            row = QHBoxLayout()
            cb = QCheckBox(type_name)
            cb.setChecked(True)
            lbl = QLabel(f"{count} element(s)")
            lbl.setStyleSheet("color: #888;")
            row.addWidget(cb)
            row.addStretch()
            row.addWidget(lbl)
            self.types_layout.addLayout(row)
            self.checkboxes[type_name] = cb
            self.count_labels[type_name] = lbl

    def get_selected_types(self):
        """Retourne la liste des types coches."""
        return [name for name, cb in self.checkboxes.items() if cb.isChecked()]

    def file_path(self):
        return self.file_edit.text().strip()

    def output_path(self):
        return self.out_edit.text().strip()
