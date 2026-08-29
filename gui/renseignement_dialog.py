# -*- coding: utf-8 -*-
# gui/renseignement_dialog.py

from qgis.core import NULL, QgsPointXY
from qgis.PyQt.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout, QLineEdit,
    QComboBox, QDialogButtonBox, QLabel, QMessageBox, QPushButton,
    QGroupBox, QFrame, QWidget, QSizePolicy,
)
from qgis.PyQt.QtGui import QFont, QRegExpValidator, QKeyEvent
from qgis.PyQt.QtCore import Qt, QTimer, QEvent, QLocale, QRegExp, pyqtSignal

from ..tools import i18n
from .quick_config_widgets import NETWORK_COLORS

import re

_NUM_TOKEN_RE = re.compile(r'[+-]?\d*\.?\d+')

# Sépare « Longueur (m) » en libellé + unité, dans toutes les langues.
_UNIT_RE = re.compile(r'^(.*?)\s*\(([^()]*)\)\s*$')

# label, type, (decimals,) ou liste de suggestions
FIELD_CONFIG = {
    'nom':        ('col_nom',         'str',   None),
    'tn':         ('col_tn',          'num',   3),
    'fe_radier':  ('col_fe_radier',   'num',   3),
    'fe_entree':  ('col_fe_entree',   'num',   3),
    'profondeur': ('col_profondeur',  'num',   2),
    'diametre':   ('col_diametre',    'num',   0),
    'materiau':   ('col_materiau',    'combo', ['PVC', 'Beton', 'Fonte', 'Gres',
                                                'PEHD', 'Amiante-ciment', 'Acier']),
    'longueur':      ('col_longueur',      'num', 2),
    'pente':         ('col_pente',         'num', 3),
    'cote_piquage':  ('col_cote_piquage',  'num', 3),
}

# Regroupement des champs par rôle : (clé i18n du cadre, champs du cadre).
# L'ordre de lecture donne l'ordre de saisie (Tab).
ROLE_SECTIONS = {
    'regard': [
        ('rens_sec_identification', ['nom']),
        ('rens_sec_altimetrie',     ['tn', 'profondeur', 'fe_radier']),
    ],
    'tabouret': [
        ('rens_sec_identification', ['nom']),
        ('rens_sec_altimetrie',     ['tn', 'profondeur', 'fe_entree']),
    ],
    'conduite': [
        ('rens_sec_caracteristiques', ['diametre', 'materiau']),
        ('rens_sec_trace',            ['longueur', 'pente']),
    ],
    'branchement': [
        ('rens_sec_caracteristiques', ['diametre', 'materiau']),
        ('rens_sec_trace',            ['longueur', 'pente', 'cote_piquage']),
    ],
}

# Champs saisis pour chaque rôle, à plat — dérivé de ROLE_SECTIONS pour que
# les deux ne puissent pas diverger.
ROLE_FIELDS = {
    role: [name for _, noms in sections for name in noms]
    for role, sections in ROLE_SECTIONS.items()
}

# Clés i18n, traduites à l'affichage
ROLE_LABELS = {
    'regard':      'col_regard',
    'tabouret':    'col_tabouret',
    'conduite':    'col_conduite',
    'branchement': 'col_branchement',
}


def _split_unit(label):
    """« Longueur (m) » → ('Longueur', 'm'). Sans parenthèses → (label, '')."""
    m = _UNIT_RE.match(label)
    if m:
        return m.group(1), m.group(2)
    return label, ''


class NumericEdit(QLineEdit):
    """QLineEdit numérique : sélection auto au clic, pas de flèches."""

    committed = pyqtSignal()   # émis quand l'édition est terminée (Tab / Enter / perte de focus)

    def __init__(self, decimals=3, parent=None):
        super().__init__(parent)
        self._decimals = decimals
        self.setAlignment(Qt.AlignRight)
        self.setPlaceholderText('—')
        # Accepte chiffres, point, virgule, +, -, espaces — l'évaluation
        # additive est faite dans value(). Permet ex: "1-0.25" → 0.75.
        validator = QRegExpValidator(QRegExp(r'[\d+\-.,\s]*'))
        self.setValidator(validator)
        self.editingFinished.connect(self._normalize)

    # Sélectionne tout au focus (clic ou Tab) — QTimer pour survivre au mouseReleaseEvent
    def focusInEvent(self, event):
        super().focusInEvent(event)
        QTimer.singleShot(0, self.selectAll)

    def keyPressEvent(self, event):
        if event.text() == ',':
            event = QKeyEvent(QEvent.KeyPress, Qt.Key_Period, event.modifiers(), '.')
        super().keyPressEvent(event)

    def value(self):
        txt = self.text().replace(',', '.').replace(' ', '')
        if not txt:
            return None
        tokens = _NUM_TOKEN_RE.findall(txt)
        if not tokens:
            return None
        try:
            return sum(float(t) for t in tokens)
        except ValueError:
            return None

    def setValue(self, v):
        if v is None or v == NULL:
            self.setText('')
        else:
            fmt = f'{{:.{self._decimals}f}}'
            self.setText(fmt.format(float(v)))

    def _normalize(self):
        v = self.value()
        if v is not None:
            fmt = f'{{:.{self._decimals}f}}'
            self.blockSignals(True)
            self.setText(fmt.format(v))
            self.blockSignals(False)
        self.committed.emit()


class RenseignementDialog(QDialog):

    def __init__(self, role, feat, layer, reseau, couches=None, parent=None):
        super().__init__(parent)
        self.role     = role
        self.feat     = feat
        self.layer    = layer
        self.reseau   = reseau
        self.couches  = couches
        self.widgets  = {}
        self._updating = False
        self._accent  = NETWORK_COLORS.get(reseau, '#555555')

        self._fe_field = 'fe_radier' if role == 'regard' else 'fe_entree'

        self.setWindowTitle(
            i18n.tr('rens_titre',
                    type=i18n.tr(ROLE_LABELS.get(role, role)), nom=reseau)
        )
        self.setMinimumWidth(420)
        self._build_ui()

        if role in ('regard', 'tabouret'):
            self._connect_formula()

    # ----------------------------------------------------------------- UI

    def _build_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        main_layout.addWidget(self._make_header())

        corps = QWidget()
        corps_layout = QVBoxLayout(corps)
        corps_layout.setContentsMargins(14, 12, 14, 12)
        corps_layout.setSpacing(10)

        layer_fields = self.layer.fields()
        for cle_section, noms in ROLE_SECTIONS.get(self.role, []):
            group = self._make_section(cle_section, noms, layer_fields)
            if group is not None:
                corps_layout.addWidget(group)

        corps_layout.addStretch()
        main_layout.addWidget(corps)

        main_layout.addWidget(self._make_separator())
        main_layout.addWidget(self._make_buttons())

        # Le libellé de l'en-tête suit le nom pendant la saisie.
        nom_w = self.widgets.get('nom')
        if isinstance(nom_w, QLineEdit):
            nom_w.textChanged.connect(lambda _: self._refresh_header())

    def _make_header(self):
        """Bandeau coloré : type d'ouvrage, nom, pastille du réseau."""
        header = QFrame()
        header.setStyleSheet(f"QFrame {{ background-color: {self._accent}; }}")

        lay = QHBoxLayout(header)
        lay.setContentsMargins(14, 10, 14, 10)
        lay.setSpacing(10)

        self.lbl_header = QLabel()
        font = QFont()
        font.setBold(True)
        font.setPointSize(11)
        self.lbl_header.setFont(font)
        self.lbl_header.setStyleSheet("color: #FFFFFF; background: transparent;")
        self.lbl_header.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        lay.addWidget(self.lbl_header)

        badge = QLabel(self.reseau)
        badge_font = QFont()
        badge_font.setBold(True)
        badge.setFont(badge_font)
        badge.setAlignment(Qt.AlignCenter)
        badge.setStyleSheet(
            "QLabel {"
            "  background-color: #FFFFFF;"
            f" color: {self._accent};"
            "  border-radius: 9px; padding: 2px 10px;"
            "}"
        )
        lay.addWidget(badge, 0, Qt.AlignRight)

        self._refresh_header()
        return header

    def _refresh_header(self):
        type_label = i18n.tr(ROLE_LABELS.get(self.role, self.role))

        nom_w = self.widgets.get('nom')
        nom = nom_w.text().strip() if isinstance(nom_w, QLineEdit) else ''
        if not nom and self.layer.fields().indexFromName('nom') >= 0:
            raw = self.feat['nom']
            if raw is not None and raw != NULL:
                nom = str(raw).strip()
        if not nom:
            nom = f"#{self.feat.id()}"

        self.lbl_header.setText(f"{type_label}  {nom}")

    def _make_section(self, cle_section, noms, layer_fields):
        """Cadre regroupant les champs présents dans la couche, ou None."""
        group = QGroupBox(i18n.tr(cle_section))
        form = QFormLayout(group)
        form.setLabelAlignment(Qt.AlignRight | Qt.AlignVCenter)
        form.setFieldGrowthPolicy(QFormLayout.ExpandingFieldsGrow)
        form.setHorizontalSpacing(10)
        form.setVerticalSpacing(7)

        lignes = 0
        for name in noms:
            if layer_fields.indexFromName(name) < 0:
                continue
            cle_label, ftype, extra = FIELD_CONFIG[name]
            label_text, unite = _split_unit(i18n.tr(cle_label))
            raw_val = self.feat[name]

            # Auto-remplissage longueur depuis la géométrie si vide
            if name == 'longueur' and self.role in ('conduite', 'branchement'):
                if raw_val is None or raw_val == NULL:
                    geom = self.feat.geometry()
                    if geom and not geom.isEmpty():
                        raw_val = round(geom.length(), 2)

            widget = self._make_widget(ftype, extra, raw_val)
            self.widgets[name] = widget

            extras = []
            if name == 'longueur' and self.role in ('conduite', 'branchement'):
                extras.append(self._make_action_button(
                    "↺", i18n.tr('rens_recalculer'),
                    self._recalculate_longueur, largeur=30))
            elif name == 'pente' and self.role in ('conduite', 'branchement'):
                extras.append(self._make_action_button(
                    i18n.tr('rens_calculer'), i18n.tr('rens_calcul_pente'),
                    self._calculate_pente, largeur=76))

            form.addRow(label_text, self._make_field_row(widget, unite, extras))
            lignes += 1

        if lignes == 0:
            group.deleteLater()
            return None
        return group

    def _make_field_row(self, widget, unite, extras):
        """Champ + suffixe d'unité + boutons d'action, alignés."""
        row = QWidget()
        lay = QHBoxLayout(row)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(6)
        lay.addWidget(widget, 1)

        if unite:
            lbl = QLabel(unite)
            lbl.setStyleSheet("color: palette(mid);")
            lbl.setMinimumWidth(42)
            lay.addWidget(lbl, 0)
        elif extras:
            # Réserve la même gouttière pour que les boutons restent alignés
            spacer = QLabel('')
            spacer.setMinimumWidth(42)
            lay.addWidget(spacer, 0)

        for btn in extras:
            lay.addWidget(btn, 0)
        return row

    def _make_action_button(self, texte, tooltip, slot, largeur):
        btn = QPushButton(texte)
        btn.setFixedWidth(largeur)
        btn.setToolTip(tooltip)
        btn.setCursor(Qt.PointingHandCursor)
        # Sans cela, Entrée dans un champ déclencherait ce bouton au lieu d'OK.
        btn.setAutoDefault(False)
        btn.setDefault(False)
        btn.setStyleSheet(
            "QPushButton {"
            f" border: 1px solid {self._accent}; color: {self._accent};"
            "  background: transparent; border-radius: 3px;"
            "  padding: 3px 6px; font-weight: bold;"
            "}"
            f"QPushButton:hover   {{ background-color: {self._accent}; color: #FFFFFF; }}"
            f"QPushButton:pressed {{ background-color: {self._accent}; color: #FFFFFF; }}"
        )
        btn.clicked.connect(slot)
        return btn

    def _make_separator(self):
        sep = QFrame()
        sep.setFrameShape(QFrame.HLine)
        sep.setFrameShadow(QFrame.Sunken)
        return sep

    def _make_buttons(self):
        pied = QWidget()
        lay = QHBoxLayout(pied)
        lay.setContentsMargins(14, 10, 14, 12)

        buttons = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Apply | QDialogButtonBox.Cancel
        )

        btn_ok = buttons.button(QDialogButtonBox.Ok)
        btn_ok.setDefault(True)
        btn_ok.setAutoDefault(True)
        btn_ok.setCursor(Qt.PointingHandCursor)
        btn_ok.setStyleSheet(
            "QPushButton {"
            f" background-color: {self._accent}; color: #FFFFFF;"
            "  font-weight: bold; border: none; border-radius: 3px;"
            "  padding: 6px 18px;"
            "}"
            "QPushButton:hover   { background-color: palette(highlight); }"
            "QPushButton:pressed { background-color: palette(dark); }"
        )

        btn_apply = buttons.button(QDialogButtonBox.Apply)
        btn_apply.setText(i18n.tr('appliquer'))
        btn_apply.setAutoDefault(False)
        btn_apply.clicked.connect(self._apply)

        buttons.button(QDialogButtonBox.Cancel).setAutoDefault(False)

        buttons.accepted.connect(self._save)
        buttons.rejected.connect(self.reject)
        lay.addWidget(buttons)
        return pied

    def _make_widget(self, ftype, extra, raw_val):
        if ftype == 'num':
            w = NumericEdit(decimals=extra)
            w.setValue(raw_val)
            return w

        if ftype == 'combo':
            w = QComboBox()
            w.setEditable(True)
            w.addItems(extra)
            val = '' if raw_val is None or raw_val == NULL else str(raw_val)
            idx = w.findText(val)
            if idx >= 0:
                w.setCurrentIndex(idx)
            else:
                w.setEditText(val)
            return w

        # str
        w = QLineEdit()
        if raw_val is not None and raw_val != NULL:
            w.setText(str(raw_val))
        return w

    # ----------------------------------------------------------------- formule TN / P / FE

    def _connect_formula(self):
        for name in ('tn', 'profondeur', self._fe_field):
            w = self.widgets.get(name)
            if isinstance(w, NumericEdit):
                w.committed.connect(lambda n=name: self._on_committed(n))

    def _on_committed(self, changed):
        if self._updating:
            return

        tn_w = self.widgets.get('tn')
        p_w  = self.widgets.get('profondeur')
        fe_w = self.widgets.get(self._fe_field)
        if not tn_w or not p_w or not fe_w:
            return

        tn_empty = tn_w.value() is None
        p_empty  = p_w.value()  is None
        fe_empty = fe_w.value() is None
        null_count = sum([tn_empty, p_empty, fe_empty])

        if null_count == 1:
            # Deux valeurs connues → calcule la troisième
            if tn_empty:
                self._set(tn_w, fe_w.value() + p_w.value())
            elif p_empty:
                self._set(p_w, tn_w.value() - fe_w.value())
            else:
                self._set(fe_w, tn_w.value() - p_w.value())

        elif null_count == 0 and changed == 'profondeur':
            # Toutes renseignées + P modifié → demander laquelle recalculer
            fe_label = i18n.tr('col_fe_radier_court' if self.role == 'regard'
                               else 'col_fe_entree_court')
            msg = QMessageBox(self)
            msg.setWindowTitle(i18n.tr('rens_p_modifie'))
            msg.setText(i18n.tr('rens_p_question'))
            btn_fe = msg.addButton(fe_label, QMessageBox.YesRole)
            btn_tn = msg.addButton('TN',     QMessageBox.NoRole)
            msg.addButton(i18n.tr('rens_aucune'), QMessageBox.RejectRole)
            msg.exec_()
            clicked = msg.clickedButton()
            if clicked == btn_fe:
                self._set(fe_w, tn_w.value() - p_w.value())
            elif clicked == btn_tn:
                self._set(tn_w, fe_w.value() + p_w.value())

    def _set(self, widget, value):
        self._updating = True
        widget.setValue(value)
        self._updating = False

    # ----------------------------------------------------------------- save

    def _apply(self):
        """Écrit les valeurs saisies dans la couche, sans fermer la fenêtre."""
        if not self.layer.isEditable():
            self.layer.startEditing()

        fid    = self.feat.id()
        fields = self.layer.fields()

        for name, widget in self.widgets.items():
            idx = fields.indexFromName(name)
            if idx < 0:
                continue

            if isinstance(widget, NumericEdit):
                val = widget.value()          # None si vide
            elif isinstance(widget, QComboBox):
                val = widget.currentText().strip() or None
            else:
                val = widget.text().strip() or None

            self.layer.changeAttributeValue(fid, idx, val)

        self.layer.commitChanges()

        # Recharge l'entité : « Appliquer » puis « OK » doivent repartir de
        # valeurs à jour, pas d'une référence périmée.
        fresh = self.layer.getFeature(fid)
        if fresh.isValid():
            self.feat = fresh

    def _save(self):
        self._apply()
        self.accept()

    # ----------------------------------------------------------------- longueur géométrique

    def _recalculate_longueur(self):
        geom = self.feat.geometry()
        if geom is None or geom.isEmpty():
            return
        longueur_w = self.widgets.get('longueur')
        if longueur_w:
            longueur_w.setValue(round(geom.length(), 2))

    # ----------------------------------------------------------------- calcul pente

    def _calculate_pente(self):
        """Calcule la pente : (FE_amont − FE_aval) / longueur × 100."""
        if self.couches is None:
            QMessageBox.warning(self, i18n.tr('rens_calcul_pente'),
                                i18n.tr('rens_couches_absentes'))
            return

        geom = self.feat.geometry()
        if geom.isEmpty():
            return
        line = geom.asPolyline()
        if len(line) < 2:
            return

        fe_start = self._fe_at(QgsPointXY(line[0]))
        fe_end   = self._fe_at(QgsPointXY(line[-1]))

        if fe_start is None or fe_end is None:
            QMessageBox.warning(self, i18n.tr('rens_calcul_pente'),
                                i18n.tr('rens_fe_introuvables'))
            return

        if self.role == 'branchement':
            cote_piquage_w = self.widgets.get('cote_piquage')
            if cote_piquage_w:
                cote_piquage_w.setValue(fe_start)

        longueur_w = self.widgets.get('longueur')
        longueur = longueur_w.value() if longueur_w else None
        if not longueur:
            QMessageBox.warning(self, i18n.tr('rens_calcul_pente'),
                                i18n.tr('rens_longueur_requise'))
            return

        pente = (fe_start - fe_end) / longueur * 100
        pente_w = self.widgets.get('pente')
        if pente_w:
            pente_w.setValue(pente)

    def _fe_at(self, point, tolerance=0.01):
        """Retourne la valeur FE de l'ouvrage (regard ou tabouret) le plus proche du point."""
        fe_fields = {'regard': 'fe_radier', 'tabouret': 'fe_entree'}
        best_val, best_dist = None, float('inf')
        for role, fe_field in fe_fields.items():
            layer = self.couches.get(role)
            if layer is None:
                continue
            for feat in layer.getFeatures():
                g = feat.geometry()
                if g.isEmpty():
                    continue
                dist = point.distance(QgsPointXY(g.asPoint()))
                if dist <= tolerance and dist < best_dist:
                    val = feat[fe_field]
                    if val is not None and val != NULL:
                        best_val = float(val)
                        best_dist = dist
        return best_val
