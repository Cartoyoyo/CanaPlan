# -*- coding: utf-8 -*-
import csv
import os

from qgis.PyQt.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QPushButton,
    QTableWidget, QTableWidgetItem, QHeaderView,
    QFileDialog, QMessageBox, QLabel, QApplication,
    QRadioButton, QButtonGroup, QCheckBox, QGroupBox, QDialogButtonBox,
)
from qgis.core import QgsProject
from qgis.PyQt.QtCore import Qt, QUrl
from qgis.PyQt.QtGui import QColor, QDesktopServices


class CubatureDialog(QDialog):

    _COLUMNS = [
        "ID", "Réseau", "Type", "Matériau", "Ø (mm)", "Nom début", "Nom fin",
        "Long. 2D (m)", "Long. 3D (m)", "Pente (%)",
        "Prof. moy. (m)", "Largeur (m)", "Surf. ouv. (m²)",
        "Vol. lit pose (m³)", "Vol. enrobage (m³)", "Vol. conduite (m³)",
        "Vol. chaussée inf (m³)", "Vol. chaussée sup (m³)",
        "Vol. remblai (m³)", "Déblai (m³)",
    ]

    # Colonnes de détail du remblai : n'existent qu'en mode show_remblai,
    # et certaines sont en plus conditionnées à un flag de config (chaussée).
    _VOL_BREAKDOWN = [
        dict(key='lit_pose', field='vol_lit_pose', csv_label='Vol. lit pose (m³)',
             pdf_label='Lit pose', recap_label='Lit pose (m³)', pdf_width=9, recap_width=20),
        dict(key='enrobage', field='vol_enrobage', csv_label='Vol. enrobage (m³)',
             pdf_label='Enrobage', recap_label='Enrobage (m³)', pdf_width=9, recap_width=20),
        dict(key='conduite', field='vol_conduite', csv_label='Vol. conduite (m³)',
             pdf_label='Conduite', recap_label='Conduite (m³)', pdf_width=9, recap_width=20),
        dict(key='ch_inf', field='vol_chaussee_inf', csv_label='Vol. chaussée inf (m³)',
             pdf_label='Ch.inf', recap_label='Ch. inf (m³)', pdf_width=8, recap_width=18,
             cfg_flag='chaussee_inf'),
        dict(key='ch_sup', field='vol_chaussee_sup', csv_label='Vol. chaussée sup (m³)',
             pdf_label='Ch.sup', recap_label='Ch. sup (m³)', pdf_width=8, recap_width=18,
             cfg_flag='chaussee_sup'),
        dict(key='remblai', field='vol_remblai', csv_label='Vol. remblai (m³)',
             pdf_label='Remblai', recap_label='Vol. remblai (m³)', pdf_width=10, recap_width=22),
    ]

    def _active_vol_cols(self):
        """Colonnes de détail du remblai actives pour ce rapport (vide en mode cubature simple)."""
        if not self.show_remblai:
            return []
        return [c for c in self._VOL_BREAKDOWN
                if not c.get('cfg_flag') or self.config.get(c['cfg_flag'], False)]

    @staticmethod
    def _avg(values):
        """Moyenne des valeurs non None, ou None si aucune valeur valide."""
        vals = [v for v in values if v is not None]
        return sum(vals) / len(vals) if vals else None

    def _synthese_data(self):
        """Données de synthèse par réseau (EU/EP) : tronçons et branchements
        groupés par matériau + diamètre (nb + linéaire), et comptage des
        regards/tabourets référencés dans le rapport en cours."""
        def _groupes(items):
            groups = {}
            for r in items:
                key = (r.get('materiau') or '—', r.get('diametre'))
                g = groups.setdefault(key, {'cnt': 0, 'long': 0.0})
                g['cnt'] += 1
                g['long'] += r.get('l3d') or 0.0
            return sorted(groups.items(), key=lambda kv: (kv[0][0], -(kv[0][1] or 0)))

        data = []
        for r_name in ('EU', 'EP'):
            reseau_results = [r for r in self.results if r.get('reseau') == r_name]
            if not reseau_results:
                continue

            troncons = [r for r in reseau_results if r.get('type') == 'Conduite']
            branchements = [r for r in reseau_results if r.get('type') == 'Branchement']

            regards = {r.get('nom_debut') for r in troncons} | {r.get('nom_fin') for r in troncons}
            regards.discard(None); regards.discard('')
            tabourets = {r.get('nom_fin') for r in branchements if r.get('nom_fin')}

            data.append(dict(
                reseau=r_name,
                troncons_groupes=_groupes(troncons),
                troncons_total=(len(troncons), sum(r.get('l3d') or 0.0 for r in troncons)),
                branchements_groupes=_groupes(branchements),
                branchements_total=(len(branchements), sum(r.get('l3d') or 0.0 for r in branchements)),
                nb_regards=len(regards),
                nb_tabourets=len(tabourets),
            ))
        return data

    def __init__(self, results, config, parent=None, bfs_prefix=None, show_remblai=False):
        super().__init__(parent)
        self.results = results
        self.config = config
        self.bfs_prefix = bfs_prefix  # ex: "REP01_REP04" pour le mode BFS
        self.show_remblai = show_remblai
        self.setWindowTitle("Cubature des tranchées")
        self.setWindowFlags(
            self.windowFlags()
            | Qt.WindowMinimizeButtonHint
            | Qt.WindowMaximizeButtonHint
            | Qt.WindowSystemMenuHint
        )
        self.setMinimumSize(1000, 450)
        self.setAttribute(Qt.WA_DeleteOnClose, False)

        self._build_ui()
        self._update_info_label()
        self._populate_table()
        self._adjust_size_to_content()

    def _adjust_size_to_content(self):
        """Redimensionne la fenêtre pour montrer un maximum de lignes et de
        colonnes visibles sans scroll, dans la limite de l'écran disponible.
        Appelé à l'ouverture et à chaque bascule du détail remblai (le nombre
        de colonnes visibles change alors)."""
        self.table.resizeRowsToContents()
        self.table.resizeColumnsToContents()

        header_h = self.table.horizontalHeader().height()
        rows_h = sum(self.table.rowHeight(i) for i in range(self.table.rowCount()))
        frame_h = 2 * self.table.frameWidth()
        chrome_h = (
            self.info.sizeHint().height()
            + self.cb_remblai.sizeHint().height()
            + self.total_label.sizeHint().height()
            + 90  # boutons d'export + marges de layout
        )
        ideal_h = header_h + rows_h + frame_h + chrome_h

        cols_w = sum(self.table.columnWidth(c) for c in range(self.table.columnCount())
                     if not self.table.isColumnHidden(c))
        v_scrollbar_w = self.table.verticalScrollBar().sizeHint().width()
        frame_w = 2 * self.table.frameWidth()
        ideal_w = cols_w + v_scrollbar_w + frame_w + 30  # marges de layout

        screen = QApplication.primaryScreen()
        avail = screen.availableGeometry() if screen else None
        max_h = int(avail.height() * 0.9) if avail else 900
        max_w = int(avail.width() * 0.9) if avail else 1400

        width = min(max(ideal_w, 1000), max_w)
        height = min(max(ideal_h, 450), max_h)
        self.resize(width, height)

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)

        # Info config
        self.info = QLabel()
        self.info.setWordWrap(True)
        self.info.setStyleSheet("color: #555; font-size: 10px; padding: 2px;")
        layout.addWidget(self.info)

        # Option remblai
        self.cb_remblai = QCheckBox(
            "Afficher le détail remblai (lit de pose, enrobage, chaussée...)")
        self.cb_remblai.setChecked(self.show_remblai)
        self.cb_remblai.toggled.connect(self._on_toggle_remblai)
        layout.addWidget(self.cb_remblai)

        # Table
        self.table = QTableWidget()
        self.table.setColumnCount(len(self._COLUMNS))
        self.table.setHorizontalHeaderLabels(self._COLUMNS)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Interactive)
        self.table.setAlternatingRowColors(True)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        layout.addWidget(self.table, 1)

        # Total
        self.total_label = QLabel()
        self.total_label.setStyleSheet(
            "font-weight: bold; font-size: 13px; padding: 6px;"
        )
        layout.addWidget(self.total_label)

        # Boutons export
        btn_row = QHBoxLayout()
        btn_row.addStretch()

        btn_csv = QPushButton("Exporter CSV")
        btn_csv.clicked.connect(self._export_csv)
        btn_row.addWidget(btn_csv)

        btn_pdf = QPushButton("Exporter PDF")
        btn_pdf.clicked.connect(self._export_pdf)
        btn_row.addWidget(btn_pdf)

        try:
            import openpyxl
            btn_xlsx = QPushButton("Exporter Excel (.xlsx)")
            btn_xlsx.clicked.connect(self._export_xlsx)
            btn_row.addWidget(btn_xlsx)
        except ImportError:
            pass

        layout.addLayout(btn_row)

    def _on_toggle_remblai(self, checked):
        self.show_remblai = checked
        self._update_info_label()
        self._populate_table()
        self._adjust_size_to_content()

    def _update_info_label(self):
        cfg = self.config
        lines = [
            f"Ép. lit de pose = {cfg.get('ep_lit_pose', 0.10):.2f} m  |  "
            f"Larg. cond. EU = {cfg.get('largeur_conduite_eu', 0.80):.2f} m  |  "
            f"Larg. cond. EP = {cfg.get('largeur_conduite_ep', 0.80):.2f} m  |  "
            f"Larg. branch. EU = {cfg.get('largeur_branchement_eu', 0.60):.2f} m  |  "
            f"Larg. branch. EP = {cfg.get('largeur_branchement_ep', 0.60):.2f} m",
        ]
        if self.show_remblai:
            lines += [
                f"Lit pose : {cfg.get('materiau_lit_pose', 'Sable')}",
                f"Enrobage : {cfg.get('ep_enrobage', 0.15):.2f} m — {cfg.get('materiau_enrobage', 'Sable')}",
                f"Remblai : {cfg.get('materiau_remblai', '0/31.5')}",
            ]
            if cfg.get('chaussee_inf', False):
                lines.append(
                    f"Chaussée inf. : {cfg.get('ep_chaussee_inf', 0.20):.2f} m"
                    + (f" — {cfg['materiau_chaussee_inf']}" if cfg.get('materiau_chaussee_inf') else ""))
            if cfg.get('chaussee_sup', False):
                lines.append(
                    f"Chaussée sup. : {cfg.get('ep_chaussee_sup', 0.08):.2f} m"
                    + (f" — {cfg['materiau_chaussee_sup']}" if cfg.get('materiau_chaussee_sup') else ""))
        self.info.setText("  |  ".join(lines))

    def _populate_table(self):
        eu_results = [r for r in self.results if r.get('reseau') == 'EU']
        ep_results = [r for r in self.results if r.get('reseau') == 'EP']

        self.table.setRowCount(0)
        row = 0

        total_volume = 0.0
        total_surface = 0.0
        total_count = 0

        for reseau_name, reseau_results, color_hex in [
            ('EU', eu_results, '#CC0000'),
            ('EP', ep_results, '#0044CC'),
        ]:
            if not reseau_results:
                continue

            # Ligne de groupe
            self.table.insertRow(row)
            item = QTableWidgetItem(f"Réseau {reseau_name} — Eaux {'Usées' if reseau_name == 'EU' else 'Pluviales'}")
            item.setBackground(QColor(color_hex))
            item.setForeground(QColor('white'))
            font = item.font()
            font.setBold(True)
            item.setFont(font)
            self.table.setItem(row, 0, item)
            self.table.setSpan(row, 0, 1, len(self._COLUMNS))
            row += 1

            sous_total = 0.0
            sous_surface = 0.0
            sous_l2d = 0.0
            sous_l3d = 0.0
            sous_vol = {c['key']: 0.0 for c in self._VOL_BREAKDOWN}
            for r in reseau_results:
                self.table.insertRow(row)
                self._set_row(row, r)
                if r.get('volume') is not None:
                    sous_total += r['volume']
                if r.get('surface') is not None:
                    sous_surface += r['surface']
                sous_l2d += r.get('l2d') or 0.0
                sous_l3d += r.get('l3d') or 0.0
                for c in self._VOL_BREAKDOWN:
                    sous_vol[c['key']] += r.get(c['field']) or 0.0
                row += 1

            # Ligne sous-total : label sur ID..Nom fin, puis un sous-total
            # par colonne numérique (m, m², m³).
            self.table.insertRow(row)
            color_lighter = QColor(color_hex).lighter(185)
            label_item = QTableWidgetItem(f"Sous-total {reseau_name}")
            label_item.setBackground(color_lighter)
            font = label_item.font()
            font.setBold(True)
            label_item.setFont(font)
            self.table.setItem(row, 0, label_item)
            self.table.setSpan(row, 0, 1, 7)  # ID, Réseau, Type, Matériau, Ø, Nom début, Nom fin

            subtotal_vals = {7: sous_l2d, 8: sous_l3d, 12: sous_surface}
            for i, c in enumerate(self._VOL_BREAKDOWN):
                subtotal_vals[13 + i] = sous_vol[c['key']]
            subtotal_vals[len(self._COLUMNS) - 1] = sous_total

            for col in range(1, len(self._COLUMNS)):
                text = f"{subtotal_vals[col]:.2f}" if col in subtotal_vals else ""
                cell = QTableWidgetItem(text)
                cell.setFont(font)
                cell.setBackground(color_lighter)
                if text:
                    cell.setTextAlignment(Qt.AlignCenter)
                self.table.setItem(row, col, cell)
            row += 1

            total_volume += sous_total
            total_surface += sous_surface
            total_count += len(reseau_results)

        label_text = f"{total_count} élément(s)  —  Surf. ouv. totale : {total_surface:.2f} m²  —  Déblai total : {total_volume:.2f} m³"
        self.total_label.setText(label_text)
        self.table.resizeColumnsToContents()

        # Afficher/masquer les colonnes remblai (Vol. lit pose .. Vol. remblai)
        # selon la case à cocher, en réévaluant l'état à chaque appel : il faut
        # explicitement les ré-afficher quand show_remblai repasse à True, sinon
        # elles restent masquées depuis le dernier appel avec show_remblai=False.
        active_keys = {c['key'] for c in self._active_vol_cols()}
        for i, c in enumerate(self._VOL_BREAKDOWN):
            self.table.setColumnHidden(13 + i, c['key'] not in active_keys)

    def _set_row(self, row, data):
        diam = data.get('diametre')
        vals = [
            str(data.get('id', '—')),
            data.get('reseau', ''),
            data.get('type', '—'),
            data.get('materiau', '—') or '—',
            f"{diam:.0f}" if diam is not None else '—',
            data.get('nom_debut', '—'),
            data.get('nom_fin', '—'),
            f"{data.get('l2d', 0):.2f}",
            f"{data.get('l3d', 0):.2f}",
            f"{data.get('pente_pct', 0):.2f}" if data.get('pente_pct') is not None else '—',
            f"{data.get('prof_moy', 0):.2f}" if data.get('prof_moy') is not None else 'Absence FE',
            f"{data.get('largeur', 0):.2f}",
            f"{data.get('surface', 0):.2f}" if data.get('surface') is not None else '—',
            f"{data.get('vol_lit_pose', 0):.2f}" if data.get('vol_lit_pose') is not None else '—',
            f"{data.get('vol_enrobage', 0):.2f}" if data.get('vol_enrobage') is not None else '—',
            f"{data.get('vol_conduite', 0):.2f}" if data.get('vol_conduite') is not None else '—',
            f"{data.get('vol_chaussee_inf', 0):.2f}" if data.get('vol_chaussee_inf') is not None else '—',
            f"{data.get('vol_chaussee_sup', 0):.2f}" if data.get('vol_chaussee_sup') is not None else '—',
            f"{data.get('vol_remblai', 0):.2f}" if data.get('vol_remblai') is not None else '—',
            f"{data.get('volume', 0):.2f}" if data.get('volume') is not None else '—',
        ]
        grey = data.get('err_debut') or data.get('err_fin')
        for col, val in enumerate(vals):
            item = QTableWidgetItem(val)
            item.setTextAlignment(Qt.AlignCenter if col >= 7 else Qt.AlignLeft | Qt.AlignVCenter)
            if grey:
                item.setForeground(QColor('#999999'))
            self.table.setItem(row, col, item)

    # ------------------------------------------------------------------ exports

    def _open_folder(self, path):
        folder = os.path.dirname(os.path.abspath(path))
        QDesktopServices.openUrl(QUrl.fromLocalFile(folder))

    def _default_filename(self, ext):
        prefix = "remblai" if self.show_remblai else "cubature"
        if self.bfs_prefix:
            return f"{self.bfs_prefix}_{prefix}_tranchee.{ext}"
        return f"{prefix}_tranchees.{ext}"

    def _export_csv(self):
        path, _ = QFileDialog.getSaveFileName(
            self, "Exporter en CSV", self._default_filename("csv"),
            "Fichier CSV (*.csv)")
        if not path:
            return
        try:
            vol_cols = self._active_vol_cols()
            with open(path, 'w', newline='', encoding='utf-8-sig') as f:
                writer = csv.writer(f)
                header = [
                    "ID", "Réseau", "Type", "Matériau", "Ø (mm)", "Nom début", "Nom fin",
                    "Long. 2D (m)", "Long. 3D (m)", "Pente (%)",
                    "Prof. moy. (m)", "Largeur (m)", "Surf. ouv. (m²)",
                ]
                header += [c['csv_label'] for c in vol_cols]
                header.append("Déblai (m³)")
                writer.writerow(header)

                for r in self.results:
                    row = [
                        r.get('id'), r.get('reseau'), r.get('type'),
                        r.get('materiau'),
                        r.get('diametre') if r.get('diametre') is not None else '',
                        r.get('nom_debut'), r.get('nom_fin'),
                        r.get('l2d'), r.get('l3d'),
                        r.get('pente_pct') if r.get('pente_pct') is not None else '',
                        r.get('prof_moy') if r.get('prof_moy') is not None else '',
                        r.get('largeur'),
                        r.get('surface') if r.get('surface') is not None else '',
                    ]
                    row += [r.get(c['field']) if r.get(c['field']) is not None else '' for c in vol_cols]
                    row.append(r.get('volume') if r.get('volume') is not None else '')
                    writer.writerow(row)
            self._open_folder(path)
        except Exception as e:
            QMessageBox.critical(self, "Erreur export CSV", str(e))

    def _export_pdf(self):
        path, _ = QFileDialog.getSaveFileName(
            self, "Exporter en PDF", self._default_filename("pdf"),
            "Fichier PDF (*.pdf)")
        if not path:
            return
        try:
            self._export_pdf_reportlab(path)
        except ImportError:
            try:
                import subprocess, sys
                QApplication.setOverrideCursor(Qt.WaitCursor)
                subprocess.check_call(
                    [sys.executable, "-m", "pip", "install", "reportlab"],
                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                QApplication.restoreOverrideCursor()
                self._export_pdf_reportlab(path)
            except Exception as e:
                QApplication.restoreOverrideCursor()
                QMessageBox.critical(
                    self, "Export PDF",
                    f"Impossible d'installer reportlab automatiquement.\n\n"
                    f"Installez-le manuellement : pip install reportlab\n\n"
                    f"Erreur : {e}")
        except Exception as e:
            QMessageBox.critical(self, "Erreur export PDF", str(e))

    def _export_pdf_reportlab(self, path):
        from reportlab.lib.pagesizes import A4, landscape
        from reportlab.lib import colors
        from reportlab.lib.units import cm, mm
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.platypus import (
            SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, PageBreak,
        )
        from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
        from reportlab.platypus.flowables import HRFlowable
        from datetime import date

        # Styles
        styles = getSampleStyleSheet()
        title_style = ParagraphStyle(
            'Title2', parent=styles['Title'],
            fontSize=16, spaceAfter=2*mm, textColor=colors.HexColor('#1a1a1a'),
        )
        subtitle_style = ParagraphStyle(
            'SubTitle2', parent=styles['Normal'],
            fontSize=9, textColor=colors.HexColor('#555555'), spaceAfter=1*mm,
        )
        h3_style = ParagraphStyle(
            'H3', parent=styles['Heading3'],
            fontSize=11, spaceBefore=4*mm, spaceAfter=2*mm,
        )
        param_style = ParagraphStyle(
            'Param', parent=styles['Normal'],
            fontSize=8, textColor=colors.HexColor('#444444'),
        )
        footer_style = ParagraphStyle(
            'Footer', parent=styles['Normal'],
            fontSize=7, textColor=colors.HexColor('#999999'),
        )
        cell_style = ParagraphStyle(
            'Cell', parent=styles['Normal'],
            fontSize=7, leading=9, alignment=TA_CENTER,
        )
        cell_left = ParagraphStyle(
            'CellLeft', parent=cell_style, alignment=TA_LEFT,
        )
        total_style = ParagraphStyle(
            'Total', parent=styles['Normal'],
            fontSize=10, textColor=colors.HexColor('#222222'),
            alignment=TA_RIGHT,
        )

        # Projet
        projet = QgsProject.instance()
        projet_nom = "Projet BET"
        if projet:
            base = projet.baseName() or projet.fileName()
            if base:
                projet_nom = base

        # Orientation paysage pour le mode remblai (plus de colonnes)
        page_size = landscape(A4) if self.show_remblai else A4
        doc = SimpleDocTemplate(
            path, pagesize=page_size,
            leftMargin=15*mm, rightMargin=15*mm,
            topMargin=12*mm, bottomMargin=15*mm,
        )
        story = []

        # ── En-tête ──────────────────────────────────────────────
        report_type = "Remblai de tranchées" if self.show_remblai else "Cubature de tranchées"
        story.append(Paragraph(f"Projet BET — {report_type}", title_style))
        story.append(Paragraph(
            f"Projet : {projet_nom}  |  Date : {date.today().strftime('%d/%m/%Y')}",
            subtitle_style,
        ))
        story.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor('#CC0000')))
        story.append(Spacer(1, 3*mm))

        # ── Paramètres ───────────────────────────────────────────
        story.append(Paragraph("Paramètres de calcul", h3_style))
        cfg = self.config
        params_text = (
            f"Ép. lit de pose = {cfg.get('ep_lit_pose', 0.10):.2f} m"
            + (f" ({cfg['materiau_lit_pose']})" if cfg.get('materiau_lit_pose') else "")
            + f" &nbsp;|&nbsp;"
            f"Larg. cond. EU = {cfg.get('largeur_conduite_eu', 0.80):.2f} m &nbsp;|&nbsp;"
            f"Larg. cond. EP = {cfg.get('largeur_conduite_ep', 0.80):.2f} m &nbsp;|&nbsp;"
            f"Larg. branch. EU = {cfg.get('largeur_branchement_eu', 0.60):.2f} m &nbsp;|&nbsp;"
            f"Larg. branch. EP = {cfg.get('largeur_branchement_ep', 0.60):.2f} m<br/>"
            f"Enrobage : {cfg.get('ep_enrobage', 0.15):.2f} m"
            + (f" ({cfg['materiau_enrobage']})" if cfg.get('materiau_enrobage') else "")
            + f" &nbsp;|&nbsp;"
            f"Remblai : {cfg.get('materiau_remblai', '0/31.5')}"
        )
        if cfg.get('chaussee_inf', False):
            params_text += (
                f"&nbsp;|&nbsp;Chaussée inf. : {cfg.get('ep_chaussee_inf', 0.20):.2f} m"
                + (f" ({cfg['materiau_chaussee_inf']})" if cfg.get('materiau_chaussee_inf') else ""))
        if cfg.get('chaussee_sup', False):
            params_text += (
                f"&nbsp;|&nbsp;Chaussée sup. : {cfg.get('ep_chaussee_sup', 0.08):.2f} m"
                + (f" ({cfg['materiau_chaussee_sup']})" if cfg.get('materiau_chaussee_sup') else ""))
        story.append(Paragraph(params_text, param_style))
        story.append(Spacer(1, 4*mm))

        # ── Tableaux par réseau ──────────────────────────────────
        eu_results = [r for r in self.results if r.get('reseau') == 'EU']
        ep_results = [r for r in self.results if r.get('reseau') == 'EP']

        # Styles pour sous-groupes
        sousgroupe_style = ParagraphStyle(
            'SousGroupe', parent=styles['Normal'],
            fontSize=8, textColor=colors.HexColor('#444444'),
            spaceBefore=3*mm, spaceAfter=1*mm,
            leftIndent=2*mm,
        )
        total_reseau_style = ParagraphStyle(
            'TotalReseau', parent=styles['Normal'],
            fontSize=9, textColor=colors.HexColor('#222222'),
            alignment=TA_RIGHT, spaceBefore=2*mm, spaceAfter=1*mm,
        )

        recap_data = []  # liste de (reseau, total, count, color, {type: (count, vol)})
        grand_total = 0.0
        grand_count = 0

        for reseau_name, reseau_results, color_hex, color_light in [
            ('EU', eu_results, '#CC0000', '#FFECEC'),
            ('EP', ep_results, '#0044CC', '#ECF0FF'),
        ]:
            if not reseau_results:
                continue

            story.append(Paragraph(
                f"Réseau {reseau_name} — Eaux {'Usées' if reseau_name == 'EU' else 'Pluviales'}",
                ParagraphStyle(
                    'ReseauTitle', parent=styles['Heading3'],
                    fontSize=10, textColor=colors.HexColor(color_hex),
                    spaceBefore=5*mm, spaceAfter=2*mm,
                ),
            ))

            vol_cols = self._active_vol_cols()
            pdf_cols = ["ID", "Type", "Mat.", "Ø mm", "Début", "Fin",
                        "L.2D", "L.3D", "Pente%", "Prof.moy", "Larg.", "Surf."]
            col_widths = [9*mm, 14*mm, 10*mm, 9*mm, 16*mm, 16*mm,
                         11*mm, 11*mm, 10*mm, 14*mm, 10*mm, 12*mm]
            pdf_cols += [c['pdf_label'] for c in vol_cols]
            col_widths += [c['pdf_width']*mm for c in vol_cols]
            pdf_cols.append("Vol.")
            col_widths.append(13*mm)
            n_total = len(pdf_cols)  # nombre total de colonnes
            header_color = colors.HexColor(color_hex)
            cell_bg = colors.HexColor(color_light)

            reseau_total = 0.0
            reseau_surface = 0.0
            reseau_count = 0
            reseau_detail = {}  # {type: (count, vol, bd, surface)}

            for sous_type, sous_label in [('Conduite', 'Conduites'), ('Branchement', 'Branchements')]:
                sous_results = [r for r in reseau_results if r.get('type') == sous_type]
                if not sous_results:
                    reseau_detail[sous_type] = (0, 0.0, None, 0.0)
                    continue

                story.append(Paragraph(
                    f"▸ {sous_label}",
                    sousgroupe_style,
                ))

                table_data = [pdf_cols]
                sous_total = 0.0
                sous_surface = 0.0
                sous_bd = None  # breakdown des volumes
                for r in sous_results:
                    diam = r.get('diametre')
                    row_data = [
                        Paragraph(str(r.get('id', '—')), cell_style),
                        Paragraph(r.get('type', '—'), cell_style),
                        Paragraph(r.get('materiau', '—') or '—', cell_style),
                        Paragraph(f"{diam:.0f}" if diam is not None else '—', cell_style),
                        Paragraph(r.get('nom_debut', '—'), cell_style),
                        Paragraph(r.get('nom_fin', '—'), cell_style),
                        Paragraph(f"{r.get('l2d', 0):.2f}", cell_style),
                        Paragraph(f"{r.get('l3d', 0):.2f}", cell_style),
                        Paragraph(f"{r.get('pente_pct', 0):.2f}" if r.get('pente_pct') is not None else '—', cell_style),
                        Paragraph(f"{r.get('prof_moy', 0):.2f}" if r.get('prof_moy') is not None else 'Abs.FE', cell_style),
                        Paragraph(f"{r.get('largeur', 0):.2f}", cell_style),
                        Paragraph(f"{r.get('surface', 0):.2f}" if r.get('surface') is not None else '—', cell_style),
                    ]
                    row_data += [
                        Paragraph(f"{r.get(c['field'], 0):.2f}" if r.get(c['field']) is not None else '—', cell_style)
                        for c in vol_cols
                    ]
                    row_data.append(Paragraph(f"{r.get('volume', 0):.2f}" if r.get('volume') is not None else '—', cell_style))
                    table_data.append(row_data)
                    if r.get('volume') is not None:
                        sous_total += r['volume']
                        if r.get('surface') is not None:
                            sous_surface += r['surface']
                        if vol_cols:
                            if sous_bd is None:
                                sous_bd = {c['key']: 0.0 for c in vol_cols}
                            for c in vol_cols:
                                sous_bd[c['key']] += r.get(c['field'], 0) or 0.0

                # Ligne sous-total du sous-groupe
                n_empty = n_total - 2  # label + volume
                table_data.append(
                    [Paragraph(f"<b>Sous-total {sous_label} {reseau_name}</b>", cell_left)]
                    + [''] * n_empty
                    + [Paragraph(f"<b>{sous_total:.2f}</b>", cell_style)]
                )
                reseau_total += sous_total
                reseau_surface += sous_surface
                reseau_count += len(sous_results)

                tbl = Table(table_data, colWidths=col_widths, repeatRows=1)
                tbl.setStyle(TableStyle([
                    ('BACKGROUND', (0, 0), (-1, 0), header_color),
                    ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
                    ('FONTSIZE', (0, 0), (-1, 0), 7),
                    ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                    ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
                    ('BOTTOMPADDING', (0, 0), (-1, 0), 4),
                    ('BACKGROUND', (0, 1), (-1, -2), cell_bg),
                    ('GRID', (0, 0), (-1, -1), 0.4, colors.HexColor('#CCCCCC')),
                    ('ROWBACKGROUNDS', (0, 1), (-1, -2), [cell_bg, colors.white]),
                    ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                    ('TOPPADDING', (0, 0), (-1, -1), 2),
                    ('BOTTOMPADDING', (0, 0), (-1, -1), 2),
                    ('BACKGROUND', (0, -1), (-1, -1), colors.HexColor('#EEEEEE')),
                    ('LINEABOVE', (0, -1), (-1, -1), 1, header_color),
                ]))
                story.append(tbl)
                story.append(Spacer(1, 1*mm))
                reseau_detail[sous_type] = (len(sous_results), sous_total, sous_bd, sous_surface)

            # Total réseau
            story.append(Paragraph(
                f"Total Réseau {reseau_name} : <b>{reseau_surface:.2f} m²</b>  —  <b>{reseau_total:.2f} m³</b>  ({reseau_count} élément(s))",
                total_reseau_style,
            ))

            recap_data.append((reseau_name, reseau_total, reseau_count, color_hex, reseau_detail, reseau_surface))
            grand_total += reseau_total
            grand_count += reseau_count

        # ── Récapitulatif projet ─────────────────────────────────
        story.append(Spacer(1, 5*mm))
        story.append(HRFlowable(width="100%", thickness=1.5, color=colors.HexColor('#333333')))
        story.append(Spacer(1, 3*mm))
        story.append(Paragraph("Récapitulatif projet", ParagraphStyle(
            'RecapTitle', parent=styles['Heading2'],
            fontSize=12, spaceAfter=3*mm, textColor=colors.HexColor('#222222'),
        )))

        vol_cols = self._active_vol_cols()
        vol_keys = [c['key'] for c in vol_cols]

        recap_cols = ["", "Nb", "Prof. moy. (m)", "Largeur (m)"] + \
            [c['recap_label'] for c in vol_cols] + ["Surf. ouv. (m²)", "Déblai (m³)"]
        if vol_cols:
            recap_widths = [46*mm, 10*mm, 15*mm, 13*mm] + \
                [c['recap_width']*mm for c in vol_cols] + [17*mm, 20*mm]
        else:
            recap_widths = [70*mm, 15*mm, 18*mm, 15*mm, 25*mm, 27*mm]
        n_recap = len(recap_cols)

        recap_rows = [recap_cols]
        sous_total_rows = []
        grand_bd = {k: 0.0 for k in vol_keys}

        for r_name, r_vol, r_count, r_color, r_detail, r_surf in recap_data:
            reseau_label = f"{r_name} — Eaux {'Usées' if r_name == 'EU' else 'Pluviales'}"
            recap_rows.append([Paragraph(f"<b>{reseau_label}</b>", cell_left)] + [''] * (n_recap - 1))

            reseau_bd = {k: 0.0 for k in vol_keys}
            for sous_type, sous_label in [('Conduite', 'Conduites'), ('Branchement', 'Branchements')]:
                cnt, vol, bd, surf = r_detail.get(sous_type, (0, 0.0, None, 0.0))
                sous_results = [r for r in self.results
                                if r.get('reseau') == r_name and r.get('type') == sous_type]
                profmoy_avg = self._avg([r.get('prof_moy') for r in sous_results])
                largeur_avg = self._avg([r.get('largeur') for r in sous_results])
                row_data = [Paragraph(f"&nbsp;&nbsp;&nbsp;{sous_label}", cell_left),
                            Paragraph(str(cnt), cell_style),
                            Paragraph(f"{profmoy_avg:.2f}" if profmoy_avg is not None else '—', cell_style),
                            Paragraph(f"{largeur_avg:.2f}" if largeur_avg is not None else '—', cell_style)]
                for key in vol_keys:
                    val = bd.get(key, 0.0) if bd else 0.0
                    row_data.append(Paragraph(f"{val:.2f}" if (cnt > 0 and bd) else '—', cell_style))
                    if bd:
                        reseau_bd[key] += val
                row_data.append(Paragraph(f"{surf:.2f}" if cnt > 0 else '—', cell_style))
                row_data.append(Paragraph(f"{vol:.2f}" if cnt > 0 else '—', cell_style))
                recap_rows.append(row_data)

            # Sous-total réseau
            reseau_results_r = [r for r in self.results if r.get('reseau') == r_name]
            reseau_profmoy_avg = self._avg([r.get('prof_moy') for r in reseau_results_r])
            reseau_largeur_avg = self._avg([r.get('largeur') for r in reseau_results_r])
            st_row = [Paragraph(f"<i>Sous-total {r_name}</i>", cell_left),
                      Paragraph(f"<b>{r_count}</b>", cell_style),
                      Paragraph(f"<b>{reseau_profmoy_avg:.2f}</b>" if reseau_profmoy_avg is not None else '—', cell_style),
                      Paragraph(f"<b>{reseau_largeur_avg:.2f}</b>" if reseau_largeur_avg is not None else '—', cell_style)]
            for key in vol_keys:
                st_row.append(Paragraph(f"<b>{reseau_bd[key]:.2f}</b>", cell_style))
                grand_bd[key] += reseau_bd[key]
            st_row.append(Paragraph(f"<b>{r_surf:.2f}</b>", cell_style))
            st_row.append(Paragraph(f"<b>{r_vol:.2f}</b>", cell_style))
            recap_rows.append(st_row)
            sous_total_rows.append(len(recap_rows) - 1)

        # TOTAL PROJET
        grand_surf = sum(r[5] for r in recap_data)  # reseau_surface
        grand_profmoy_avg = self._avg([r.get('prof_moy') for r in self.results])
        grand_largeur_avg = self._avg([r.get('largeur') for r in self.results])
        total_row_data = [Paragraph("<b>TOTAL PROJET</b>", cell_left),
                          Paragraph(f"<b>{grand_count}</b>", cell_style),
                          Paragraph(f"<b>{grand_profmoy_avg:.2f}</b>" if grand_profmoy_avg is not None else '—', cell_style),
                          Paragraph(f"<b>{grand_largeur_avg:.2f}</b>" if grand_largeur_avg is not None else '—', cell_style)]
        for key in vol_keys:
            total_row_data.append(Paragraph(f"<b>{grand_bd[key]:.2f}</b>", cell_style))
        total_row_data.append(Paragraph(f"<b>{grand_surf:.2f}</b>", cell_style))
        total_row_data.append(Paragraph(f"<b>{grand_total:.2f}</b>", cell_style))
        recap_rows.append(total_row_data)
        total_row = len(recap_rows) - 1

        style_cmds = [
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#333333')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 7 if vol_cols else 8),
            ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 4),
            ('GRID', (0, 0), (-1, -1), 0.4, colors.HexColor('#CCCCCC')),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('TOPPADDING', (0, 0), (-1, -1), 2),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 2),
            ('BACKGROUND', (0, total_row), (-1, total_row), colors.HexColor('#E8E8E8')),
            ('LINEABOVE', (0, total_row), (-1, total_row), 1.5, colors.HexColor('#333333')),
        ]
        for st_row in sous_total_rows:
            style_cmds.append(('BACKGROUND', (0, st_row), (-1, st_row), colors.HexColor('#EEEEEE')))
            style_cmds.append(('LINEABOVE', (0, st_row), (-1, st_row), 0.8, colors.HexColor('#666666')))

        recap_tbl = Table(recap_rows, colWidths=recap_widths)
        recap_tbl.setStyle(TableStyle(style_cmds))

        story.append(recap_tbl)

        # ── Synthèse des ouvrages ──────────────────────────────────
        story.append(PageBreak())
        story.append(Paragraph("Synthèse des ouvrages", ParagraphStyle(
            'SynthTitle', parent=styles['Heading2'],
            fontSize=12, spaceAfter=3*mm, textColor=colors.HexColor('#222222'),
        )))

        def _synth_table(groupes, total, label_total):
            rows = [["Matériau", "Ø (mm)", "Long. totale (m)"]]
            for (mat, diam), g in groupes:
                rows.append([
                    Paragraph(mat, cell_left),
                    Paragraph(f"{diam:.0f}" if diam is not None else '—', cell_style),
                    Paragraph(f"{g['long']:.2f}", cell_style),
                ])
            _cnt_total, long_total = total
            rows.append([
                Paragraph(f"<b>{label_total}</b>", cell_left), '',
                Paragraph(f"<b>{long_total:.2f}</b>", cell_style),
            ])
            tbl = Table(rows, colWidths=[55*mm, 25*mm, 35*mm])
            tbl.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#333333')),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, 0), 8),
                ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
                ('GRID', (0, 0), (-1, -1), 0.4, colors.HexColor('#CCCCCC')),
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                ('TOPPADDING', (0, 0), (-1, -1), 2),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 2),
                ('BACKGROUND', (0, -1), (-1, -1), colors.HexColor('#EEEEEE')),
                ('LINEABOVE', (0, -1), (-1, -1), 1, colors.HexColor('#333333')),
            ]))
            return tbl

        for d in self._synthese_data():
            synth_color = '#CC0000' if d['reseau'] == 'EU' else '#0044CC'
            reseau_label = f"{d['reseau']} — Eaux {'Usées' if d['reseau'] == 'EU' else 'Pluviales'}"
            story.append(Paragraph(reseau_label, ParagraphStyle(
                'SynthReseau', parent=styles['Heading3'],
                fontSize=10, textColor=colors.HexColor(synth_color),
                spaceBefore=4*mm, spaceAfter=2*mm,
            )))
            story.append(Paragraph("▸ Tronçons", sousgroupe_style))
            story.append(_synth_table(d['troncons_groupes'], d['troncons_total'], "Total tronçons"))
            story.append(Spacer(1, 2*mm))
            story.append(Paragraph("▸ Branchements", sousgroupe_style))
            story.append(_synth_table(d['branchements_groupes'], d['branchements_total'], "Total branchements"))
            story.append(Spacer(1, 2*mm))
            story.append(Paragraph(
                f"Regards : <b>{d['nb_regards']}</b> &nbsp;&nbsp;|&nbsp;&nbsp; "
                f"Tabourets : <b>{d['nb_tabourets']}</b>",
                param_style,
            ))
            story.append(Spacer(1, 5*mm))

        # ── Pied de page ─────────────────────────────────────────
        def add_page_number(canvas, doc):
            canvas.saveState()
            canvas.setFont('Helvetica', 7)
            canvas.setFillColor(colors.HexColor('#999999'))
            canvas.drawString(15*mm, 10*mm, f"Projet BET — {report_type}")
            canvas.drawRightString(page_size[0] - 15*mm, 10*mm, f"Page {canvas.getPageNumber()}")
            canvas.restoreState()

        doc.build(story, onFirstPage=add_page_number, onLaterPages=add_page_number)
        self._open_folder(path)

    def _export_xlsx(self):
        path, _ = QFileDialog.getSaveFileName(
            self, "Exporter en Excel", self._default_filename("xlsx"),
            "Fichier Excel (*.xlsx)")
        if not path:
            return
        try:
            import openpyxl
            from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
            from openpyxl.utils import get_column_letter

            wb = openpyxl.Workbook()

            # ── Feuille 1 : Récapitulatif ─────────────────────────
            ws_recap = wb.active
            ws_recap.title = "Récapitulatif"

            title_font = Font(bold=True, size=14, color='1a1a1a')
            h2_font = Font(bold=True, size=11, color='333333')
            header_font = Font(bold=True, color='FFFFFF', size=10)
            header_fill = PatternFill(start_color='333333', end_color='333333', fill_type='solid')
            bold_font = Font(bold=True, size=10)
            normal_font = Font(size=10)
            thin_border = Border(
                left=Side(style='thin'), right=Side(style='thin'),
                top=Side(style='thin'), bottom=Side(style='thin'),
            )
            bottom_border = Border(
                bottom=Side(style='medium'),
            )
            subtotal_fill = PatternFill(start_color='EEEEEE', end_color='EEEEEE', fill_type='solid')
            total_fill = PatternFill(start_color='E8E8E8', end_color='E8E8E8', fill_type='solid')
            red_fill = PatternFill(start_color='FFECEC', end_color='FFECEC', fill_type='solid')
            blue_fill = PatternFill(start_color='ECF0FF', end_color='ECF0FF', fill_type='solid')

            def apply_border(ws, row, cols, extra_border=None):
                for c in range(1, cols + 1):
                    cell = ws.cell(row=row, column=c)
                    cell.border = thin_border

            # Titre
            report_type = "Remblai de tranchées" if self.show_remblai else "Cubature de tranchées"
            ws_recap.merge_cells('A1:D1')
            c = ws_recap.cell(row=1, column=1, value=f"Projet BET — {report_type}")
            c.font = title_font
            c.alignment = Alignment(horizontal='left')

            from datetime import date
            ws_recap.merge_cells('A2:D2')
            projet = QgsProject.instance()
            projet_nom = "Projet BET"
            if projet:
                base = projet.baseName() or projet.fileName()
                if base:
                    projet_nom = base
            c = ws_recap.cell(row=2, column=1,
                value=f"Projet : {projet_nom}  |  Date : {date.today().strftime('%d/%m/%Y')}")
            c.font = Font(size=9, color='555555')

            # Paramètres
            ws_recap.merge_cells('A4:D4')
            c = ws_recap.cell(row=4, column=1, value="Paramètres de calcul")
            c.font = h2_font
            cfg = self.config
            params = (
                f"Ép. lit de pose = {cfg.get('ep_lit_pose', 0.10):.2f} m"
                + (f" ({cfg['materiau_lit_pose']})" if cfg.get('materiau_lit_pose') else "")
                + f"  |  "
                f"Larg. cond. EU = {cfg.get('largeur_conduite_eu', 0.80):.2f} m  |  "
                f"Larg. cond. EP = {cfg.get('largeur_conduite_ep', 0.80):.2f} m  |  "
                f"Larg. branch. EU = {cfg.get('largeur_branchement_eu', 0.60):.2f} m  |  "
                f"Larg. branch. EP = {cfg.get('largeur_branchement_ep', 0.60):.2f} m  |  "
                f"Enrobage : {cfg.get('ep_enrobage', 0.15):.2f} m"
                + (f" ({cfg['materiau_enrobage']})" if cfg.get('materiau_enrobage') else "")
                + f"  |  "
                f"Remblai : {cfg.get('materiau_remblai', '0/31.5')}"
            )
            if cfg.get('chaussee_inf', False):
                params += (
                    f"  |  Chaussée inf. : {cfg.get('ep_chaussee_inf', 0.20):.2f} m"
                    + (f" ({cfg['materiau_chaussee_inf']})" if cfg.get('materiau_chaussee_inf') else ""))
            if cfg.get('chaussee_sup', False):
                params += (
                    f"  |  Chaussée sup. : {cfg.get('ep_chaussee_sup', 0.08):.2f} m"
                    + (f" ({cfg['materiau_chaussee_sup']})" if cfg.get('materiau_chaussee_sup') else ""))
            c = ws_recap.cell(row=5, column=1, value=params)
            c.font = Font(size=8, color='444444')

            # Tableau récap
            vol_cols = self._active_vol_cols()
            vol_keys = [c['key'] for c in vol_cols]
            vol_field = {c['key']: c['field'] for c in vol_cols}

            recap_cols = ["", "Nb", "Prof. moy. (m)", "Largeur (m)"] + \
                [c['recap_label'] for c in vol_cols] + ["Surf. ouv. (m²)", "Déblai (m³)"]
            n_recap = len(recap_cols)

            recap_header_row = 7
            for col_idx, col_name in enumerate(recap_cols, 1):
                cell = ws_recap.cell(row=recap_header_row, column=col_idx, value=col_name)
                cell.font = header_font
                cell.fill = header_fill
                cell.alignment = Alignment(horizontal='center')
                cell.border = thin_border

            eu_results = [r for r in self.results if r.get('reseau') == 'EU']
            ep_results = [r for r in self.results if r.get('reseau') == 'EP']
            grand_total = 0.0
            grand_surface = 0.0
            grand_count = 0
            grand_bd = {k: 0.0 for k in vol_keys}

            row = recap_header_row + 1
            for r_name, reseau_results, color_hex in [
                ('EU', eu_results, 'CC0000'),
                ('EP', ep_results, '0044CC'),
            ]:
                fill = red_fill if r_name == 'EU' else blue_fill
                reseau_label = f"{r_name} — Eaux {'Usées' if r_name == 'EU' else 'Pluviales'}"
                ws_recap.merge_cells(start_row=row, start_column=1, end_row=row, end_column=n_recap)
                c = ws_recap.cell(row=row, column=1, value=reseau_label)
                c.font = Font(bold=True, size=10)
                c.fill = fill
                for cc in range(1, n_recap + 1):
                    ws_recap.cell(row=row, column=cc).border = thin_border
                row += 1

                reseau_total = 0.0
                reseau_surface = 0.0
                reseau_count = 0
                reseau_bd = {k: 0.0 for k in vol_keys}

                for sous_type, sous_label in [('Conduite', 'Conduites'), ('Branchement', 'Branchements')]:
                    sous_results = [r for r in reseau_results if r.get('type') == sous_type]
                    cnt = len(sous_results)
                    vol = sum(r.get('volume', 0.0) or 0.0 for r in sous_results)
                    surf = sum(r.get('surface', 0.0) or 0.0 for r in sous_results)
                    profmoy_avg = self._avg([r.get('prof_moy') for r in sous_results])
                    largeur_avg = self._avg([r.get('largeur') for r in sous_results])

                    c = ws_recap.cell(row=row, column=1, value=f"   {sous_label}")
                    c.font = normal_font; c.border = thin_border
                    c = ws_recap.cell(row=row, column=2, value=cnt)
                    c.font = normal_font; c.alignment = Alignment(horizontal='center'); c.border = thin_border
                    c = ws_recap.cell(row=row, column=3, value=round(profmoy_avg, 2) if profmoy_avg is not None else '—')
                    c.font = normal_font; c.alignment = Alignment(horizontal='center'); c.border = thin_border
                    c = ws_recap.cell(row=row, column=4, value=round(largeur_avg, 2) if largeur_avg is not None else '—')
                    c.font = normal_font; c.alignment = Alignment(horizontal='center'); c.border = thin_border

                    col = 5
                    for key in vol_keys:
                        v = sum(r.get(vol_field[key], 0.0) or 0.0 for r in sous_results) if cnt > 0 else None
                        c = ws_recap.cell(row=row, column=col, value=round(v, 2) if v is not None else '—')
                        c.font = normal_font; c.alignment = Alignment(horizontal='center'); c.border = thin_border
                        if v is not None:
                            reseau_bd[key] += v
                        col += 1
                    c = ws_recap.cell(row=row, column=col, value=round(surf, 2) if cnt > 0 else '—'); col += 1
                    c.font = normal_font; c.alignment = Alignment(horizontal='center'); c.border = thin_border
                    c = ws_recap.cell(row=row, column=col, value=round(vol, 2) if cnt > 0 else '—')
                    c.font = normal_font; c.alignment = Alignment(horizontal='center'); c.border = thin_border

                    row += 1
                    reseau_total += vol
                    reseau_surface += surf
                    reseau_count += cnt

                # Sous-total réseau
                for cc in range(1, n_recap + 1):
                    ws_recap.cell(row=row, column=cc).fill = subtotal_fill
                    ws_recap.cell(row=row, column=cc).border = Border(
                        top=Side(style='thin'), bottom=Side(style='thin'),
                        left=Side(style='thin'), right=Side(style='thin'))
                reseau_profmoy_avg = self._avg([r.get('prof_moy') for r in reseau_results])
                reseau_largeur_avg = self._avg([r.get('largeur') for r in reseau_results])
                c = ws_recap.cell(row=row, column=1, value=f"Sous-total {r_name}")
                c.font = Font(bold=True, size=10, italic=True); c.fill = subtotal_fill
                c = ws_recap.cell(row=row, column=2, value=reseau_count)
                c.font = Font(bold=True, size=10); c.fill = subtotal_fill; c.alignment = Alignment(horizontal='center')
                c = ws_recap.cell(row=row, column=3, value=round(reseau_profmoy_avg, 2) if reseau_profmoy_avg is not None else '—')
                c.font = Font(bold=True, size=10); c.fill = subtotal_fill; c.alignment = Alignment(horizontal='center')
                c = ws_recap.cell(row=row, column=4, value=round(reseau_largeur_avg, 2) if reseau_largeur_avg is not None else '—')
                c.font = Font(bold=True, size=10); c.fill = subtotal_fill; c.alignment = Alignment(horizontal='center')

                col = 5
                for key in vol_keys:
                    c = ws_recap.cell(row=row, column=col, value=round(reseau_bd[key], 2))
                    c.font = Font(bold=True, size=10); c.fill = subtotal_fill; c.alignment = Alignment(horizontal='center')
                    grand_bd[key] += reseau_bd[key]
                    col += 1
                c = ws_recap.cell(row=row, column=col, value=round(reseau_surface, 2)); col += 1
                c.font = Font(bold=True, size=10); c.fill = subtotal_fill; c.alignment = Alignment(horizontal='center')
                c = ws_recap.cell(row=row, column=col, value=round(reseau_total, 2))
                c.font = Font(bold=True, size=10); c.fill = subtotal_fill; c.alignment = Alignment(horizontal='center')
                row += 1
                grand_total += reseau_total
                grand_surface += reseau_surface
                grand_count += reseau_count

            # TOTAL PROJET
            for cc in range(1, n_recap + 1):
                ws_recap.cell(row=row, column=cc).fill = total_fill
                ws_recap.cell(row=row, column=cc).border = Border(
                    top=Side(style='medium'), bottom=Side(style='thin'),
                    left=Side(style='thin'), right=Side(style='thin'))
            grand_profmoy_avg = self._avg([r.get('prof_moy') for r in self.results])
            grand_largeur_avg = self._avg([r.get('largeur') for r in self.results])
            c = ws_recap.cell(row=row, column=1, value="TOTAL PROJET")
            c.font = Font(bold=True, size=11); c.fill = total_fill
            c = ws_recap.cell(row=row, column=2, value=grand_count)
            c.font = Font(bold=True, size=11); c.fill = total_fill; c.alignment = Alignment(horizontal='center')
            c = ws_recap.cell(row=row, column=3, value=round(grand_profmoy_avg, 2) if grand_profmoy_avg is not None else '—')
            c.font = Font(bold=True, size=11); c.fill = total_fill; c.alignment = Alignment(horizontal='center')
            c = ws_recap.cell(row=row, column=4, value=round(grand_largeur_avg, 2) if grand_largeur_avg is not None else '—')
            c.font = Font(bold=True, size=11); c.fill = total_fill; c.alignment = Alignment(horizontal='center')

            col = 5
            for key in vol_keys:
                c = ws_recap.cell(row=row, column=col, value=round(grand_bd[key], 2))
                c.font = Font(bold=True, size=11); c.fill = total_fill; c.alignment = Alignment(horizontal='center')
                col += 1
            c = ws_recap.cell(row=row, column=col, value=round(grand_surface, 2)); col += 1
            c.font = Font(bold=True, size=11); c.fill = total_fill; c.alignment = Alignment(horizontal='center')
            c = ws_recap.cell(row=row, column=col, value=round(grand_total, 2))
            c.font = Font(bold=True, size=11); c.fill = total_fill; c.alignment = Alignment(horizontal='center')

            ws_recap.column_dimensions['A'].width = 40
            if vol_cols:
                for col_idx in range(2, n_recap + 1):
                    ws_recap.column_dimensions[get_column_letter(col_idx)].width = 16
            else:
                ws_recap.column_dimensions['B'].width = 12
                ws_recap.column_dimensions['C'].width = 16
                ws_recap.column_dimensions['D'].width = 14
                ws_recap.column_dimensions['E'].width = 18
                ws_recap.column_dimensions['F'].width = 18

            # ── Feuille 2 : Données détaillées ─────────────────────
            ws_data = wb.create_sheet("Données détaillées")

            header_fill = PatternFill(start_color='4472C4', end_color='4472C4', fill_type='solid')
            for col_idx, col_name in enumerate(self._COLUMNS, 1):
                cell = ws_data.cell(row=1, column=col_idx, value=col_name)
                cell.font = header_font
                cell.fill = header_fill
                cell.alignment = Alignment(horizontal='center')
                cell.border = thin_border

            grey_font = Font(color='999999')

            for row_idx, r in enumerate(self.results, 2):
                row_fill = red_fill if r.get('reseau') == 'EU' else blue_fill
                diam = r.get('diametre')
                vals = [
                    r.get('id'), r.get('reseau'), r.get('type'),
                    r.get('materiau') or '',
                    diam if diam is not None else '',
                    r.get('nom_debut'), r.get('nom_fin'),
                    r.get('l2d'), r.get('l3d'),
                    r.get('pente_pct') if r.get('pente_pct') is not None else '',
                    r.get('prof_moy') if r.get('prof_moy') is not None else 'Absence FE',
                    r.get('largeur'),
                    r.get('surface') if r.get('surface') is not None else '',
                    r.get('vol_lit_pose') if r.get('vol_lit_pose') is not None else '',
                    r.get('vol_enrobage') if r.get('vol_enrobage') is not None else '',
                    r.get('vol_conduite') if r.get('vol_conduite') is not None else '',
                    r.get('vol_chaussee_inf') if r.get('vol_chaussee_inf') is not None else '',
                    r.get('vol_chaussee_sup') if r.get('vol_chaussee_sup') is not None else '',
                    r.get('vol_remblai') if r.get('vol_remblai') is not None else '',
                    r.get('volume') if r.get('volume') is not None else '',
                ]
                grey = r.get('err_debut') or r.get('err_fin')
                for col_idx, val in enumerate(vals, 1):
                    cell = ws_data.cell(row=row_idx, column=col_idx, value=val)
                    cell.fill = row_fill
                    cell.border = thin_border
                    cell.alignment = Alignment(horizontal='center')
                    if grey:
                        cell.font = grey_font

            for col_idx in range(1, len(self._COLUMNS) + 1):
                ws_data.column_dimensions[get_column_letter(col_idx)].width = 14

            # Activer autofilter sur la feuille données
            last_data_row = len(self.results) + 1
            ws_data.auto_filter.ref = f"A1:{get_column_letter(len(self._COLUMNS))}{last_data_row}"

            # Masquer colonnes selon mode
            if not self.show_remblai:
                for c in range(14, 19):  # colonnes remblai (N..R)
                    ws_data.column_dimensions[get_column_letter(c)].hidden = True
            else:
                if not self.config.get('chaussee_inf', False):
                    ws_data.column_dimensions[get_column_letter(16)].hidden = True
                if not self.config.get('chaussee_sup', False):
                    ws_data.column_dimensions[get_column_letter(17)].hidden = True

            # ── Ligne sous-total avec formules SUBTOTAL ──────────────
            subtotal_row = last_data_row + 2  # saute une ligne
            subtotal_fill_xl = PatternFill(start_color='D9E2F3', end_color='D9E2F3', fill_type='solid')
            subtotal_font = Font(bold=True, size=10)

            # Fusion A-G : "Sous-total lignes affichées"
            ws_data.merge_cells(start_row=subtotal_row, start_column=1, end_row=subtotal_row, end_column=7)
            c = ws_data.cell(row=subtotal_row, column=1, value="Sous-total lignes affichées")
            c.font = subtotal_font; c.fill = subtotal_fill_xl
            c.alignment = Alignment(horizontal='right')
            for cc in range(1, 8):
                ws_data.cell(row=subtotal_row, column=cc).fill = subtotal_fill_xl
                ws_data.cell(row=subtotal_row, column=cc).border = Border(
                    top=Side(style='medium'), bottom=Side(style='thin'),
                    left=Side(style='thin'), right=Side(style='thin'))

            # Colonnes numériques avec SUBTOTAL (109=SUM, 101=AVERAGE)
            sum_cols = {8: 'H', 9: 'I', 13: 'M', 14: 'N', 15: 'O', 16: 'P',
                        17: 'Q', 18: 'R', 19: 'S', 20: 'T'}
            avg_cols = {10: 'J', 11: 'K', 12: 'L'}

            for col_idx_1based, col_letter in {**sum_cols, **avg_cols}.items():
                c = ws_data.cell(row=subtotal_row, column=col_idx_1based)
                c.font = subtotal_font; c.fill = subtotal_fill_xl
                c.alignment = Alignment(horizontal='center')
                c.border = Border(
                    top=Side(style='medium'), bottom=Side(style='thin'),
                    left=Side(style='thin'), right=Side(style='thin'))

            for col_idx_1based, col_letter in sum_cols.items():
                ws_data.cell(row=subtotal_row, column=col_idx_1based).value = \
                    f"=SUBTOTAL(109,{col_letter}2:{col_letter}{last_data_row})"

            for col_idx_1based, col_letter in avg_cols.items():
                ws_data.cell(row=subtotal_row, column=col_idx_1based).value = \
                    f"=SUBTOTAL(101,{col_letter}2:{col_letter}{last_data_row})"

            # ── Feuille 3 : Synthèse ouvrages (tronçons/branchements par Ø/matériau, regards, tabourets) ──
            ws_synth = wb.create_sheet("Synthèse ouvrages")
            ws_synth.merge_cells('A1:C1')
            c = ws_synth.cell(row=1, column=1, value="Synthèse des ouvrages")
            c.font = title_font
            c.alignment = Alignment(horizontal='left')

            def _write_groupes_table(row_s, groupes, total, label_total):
                for col_idx, h in enumerate(["Matériau", "Ø (mm)", "Long. totale (m)"], 1):
                    cell = ws_synth.cell(row=row_s, column=col_idx, value=h)
                    cell.font = header_font; cell.fill = header_fill
                    cell.alignment = Alignment(horizontal='center'); cell.border = thin_border
                row_s += 1
                for (mat, diam), g in groupes:
                    ws_synth.cell(row=row_s, column=1, value=mat).border = thin_border
                    c = ws_synth.cell(row=row_s, column=2, value=round(diam, 1) if diam is not None else '—')
                    c.alignment = Alignment(horizontal='center'); c.border = thin_border
                    c = ws_synth.cell(row=row_s, column=3, value=round(g['long'], 2))
                    c.alignment = Alignment(horizontal='center'); c.border = thin_border
                    row_s += 1
                _cnt_total, long_total = total
                c = ws_synth.cell(row=row_s, column=1, value=label_total)
                c.font = Font(bold=True); c.border = thin_border
                ws_synth.cell(row=row_s, column=2).border = thin_border
                c = ws_synth.cell(row=row_s, column=3, value=round(long_total, 2))
                c.font = Font(bold=True); c.alignment = Alignment(horizontal='center'); c.border = thin_border
                return row_s + 2

            row_s = 3
            for d in self._synthese_data():
                fill = red_fill if d['reseau'] == 'EU' else blue_fill
                reseau_label = f"{d['reseau']} — Eaux {'Usées' if d['reseau'] == 'EU' else 'Pluviales'}"

                ws_synth.merge_cells(start_row=row_s, start_column=1, end_row=row_s, end_column=3)
                c = ws_synth.cell(row=row_s, column=1, value=reseau_label)
                c.font = Font(bold=True, size=11)
                c.fill = fill
                for cc in range(1, 4):
                    ws_synth.cell(row=row_s, column=cc).border = thin_border
                row_s += 1

                row_s = _write_groupes_table(row_s, d['troncons_groupes'], d['troncons_total'],
                                              "Total tronçons")
                row_s = _write_groupes_table(row_s, d['branchements_groupes'], d['branchements_total'],
                                              "Total branchements")

                for label, value in [
                    ("Nombre de regards", d['nb_regards']),
                    ("Nombre de tabourets", d['nb_tabourets']),
                ]:
                    c = ws_synth.cell(row=row_s, column=1, value=label)
                    c.font = normal_font
                    c = ws_synth.cell(row=row_s, column=3, value=value)
                    c.font = Font(bold=True); c.alignment = Alignment(horizontal='center')
                    row_s += 1

                row_s += 2

            ws_synth.column_dimensions['A'].width = 22
            ws_synth.column_dimensions['B'].width = 12
            ws_synth.column_dimensions['C'].width = 18

            wb.save(path)
            self._open_folder(path)
        except Exception as e:
            QMessageBox.critical(self, "Erreur export Excel", str(e))


class CubatureOptionsDialog(QDialog):
    """Dialogue d'accueil : périmètre, types d'ouvrages, mode BFS ou axe."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Cubature de tranchées")
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)

        # ── Périmètre ────────────────────────────────────────────
        group_perim = QGroupBox("Périmètre")
        perim_layout = QVBoxLayout()
        self.rb_tout = QRadioButton("Tout le projet (EU + EP)")
        self.rb_eu = QRadioButton("EU seulement")
        self.rb_ep = QRadioButton("EP seulement")
        self.rb_tout.setChecked(True)
        self._perim_group = QButtonGroup(self)
        self._perim_group.addButton(self.rb_tout, 0)
        self._perim_group.addButton(self.rb_eu, 1)
        self._perim_group.addButton(self.rb_ep, 2)
        perim_layout.addWidget(self.rb_tout)
        perim_layout.addWidget(self.rb_eu)
        perim_layout.addWidget(self.rb_ep)
        group_perim.setLayout(perim_layout)
        layout.addWidget(group_perim)

        # ── Types d'ouvrages ─────────────────────────────────────
        group_types = QGroupBox("Types d'ouvrages")
        types_layout = QVBoxLayout()
        self.cb_conduites = QCheckBox("Conduites")
        self.cb_conduites.setChecked(True)
        self.cb_branchements = QCheckBox("Branchements")
        self.cb_branchements.setChecked(True)
        types_layout.addWidget(self.cb_conduites)
        types_layout.addWidget(self.cb_branchements)
        group_types.setLayout(types_layout)
        layout.addWidget(group_types)

        # ── Mode de sélection ─────────────────────────────────────
        group_mode = QGroupBox("Mode de sélection")
        mode_layout = QVBoxLayout()
        self.cb_bfs = QCheckBox("Sélectionner 2 regards (parcours BFS)")
        self.cb_axe = QCheckBox("Tracer un axe (capture buffer 3 m)")
        self.cb_bfs.toggled.connect(lambda checked: self.cb_axe.setEnabled(not checked))
        self.cb_axe.toggled.connect(lambda checked: self.cb_bfs.setEnabled(not checked))
        mode_layout.addWidget(self.cb_bfs)
        mode_layout.addWidget(self.cb_axe)
        group_mode.setLayout(mode_layout)
        layout.addWidget(group_mode)

        # ── Boutons ──────────────────────────────────────────────
        btns = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        btns.accepted.connect(self._validate_and_accept)
        btns.rejected.connect(self.reject)
        layout.addWidget(btns)

    def _validate_and_accept(self):
        if not self.cb_conduites.isChecked() and not self.cb_branchements.isChecked():
            QMessageBox.warning(
                self, "Cubature tranchées",
                "Veuillez sélectionner au moins un type d'ouvrage.")
            return
        self.accept()

    def options(self):
        """Retourne le dict d'options choisies."""
        perim_id = self._perim_group.checkedId()
        perim_map = {0: 'tout', 1: 'EU', 2: 'EP'}
        return {
            'perimetre': perim_map.get(perim_id, 'tout'),
            'conduites': self.cb_conduites.isChecked(),
            'branchements': self.cb_branchements.isChecked(),
            'bfs': self.cb_bfs.isChecked(),
            'axe': self.cb_axe.isChecked(),
        }
