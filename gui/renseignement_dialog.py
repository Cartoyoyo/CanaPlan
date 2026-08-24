# gui/renseignement_dialog.py

from qgis.core import NULL, QgsPointXY
from qgis.PyQt.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout, QLineEdit,
    QComboBox, QDialogButtonBox, QLabel, QMessageBox, QPushButton,
)
from qgis.PyQt.QtGui import QFont, QRegExpValidator, QKeyEvent
from qgis.PyQt.QtCore import Qt, QTimer, QEvent, QLocale, QRegExp, pyqtSignal

from ..tools import i18n

import re

_NUM_TOKEN_RE = re.compile(r'[+-]?\d*\.?\d+')

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

ROLE_FIELDS = {
    'regard':      ['nom', 'tn', 'profondeur', 'fe_radier'],
    'tabouret':    ['nom', 'tn', 'profondeur', 'fe_entree'],
    'conduite':    ['diametre', 'materiau', 'longueur', 'pente'],
    'branchement': ['diametre', 'materiau', 'longueur', 'pente', 'cote_piquage'],
}

# Clés i18n, traduites à l'affichage
ROLE_LABELS = {
    'regard':      'col_regard',
    'tabouret':    'col_tabouret',
    'conduite':    'col_conduite',
    'branchement': 'col_branchement',
}


class NumericEdit(QLineEdit):
    """QLineEdit numérique : sélection auto au clic, pas de flèches."""

    committed = pyqtSignal()   # émis quand l'édition est terminée (Tab / Enter / perte de focus)

    def __init__(self, decimals=3, parent=None):
        super().__init__(parent)
        self._decimals = decimals
        self.setAlignment(Qt.AlignRight)
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

        self._fe_field = 'fe_radier' if role == 'regard' else 'fe_entree'

        self.setWindowTitle(
            i18n.tr('rens_titre',
                    type=i18n.tr(ROLE_LABELS.get(role, role)), nom=reseau)
        )
        self.setMinimumWidth(380)
        self._build_ui()

        if role in ('regard', 'tabouret'):
            self._connect_formula()

    # ----------------------------------------------------------------- UI

    def _build_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setSpacing(10)

        title = QLabel(i18n.tr('rens_sous_titre',
                       type=i18n.tr(ROLE_LABELS.get(self.role, self.role)),
                       reseau=self.reseau))
        font = QFont()
        font.setBold(True)
        font.setPointSize(10)
        title.setFont(font)
        main_layout.addWidget(title)

        form = QFormLayout()
        form.setLabelAlignment(Qt.AlignRight)
        form.setFieldGrowthPolicy(QFormLayout.ExpandingFieldsGrow)

        layer_fields = self.layer.fields()
        for name in ROLE_FIELDS.get(self.role, []):
            if layer_fields.indexFromName(name) < 0:
                continue
            cle_label, ftype, extra = FIELD_CONFIG[name]
            label_text = i18n.tr(cle_label)
            raw_val = self.feat[name]

            # Auto-remplissage longueur depuis la géométrie si vide
            if name == 'longueur' and self.role in ('conduite', 'branchement'):
                if raw_val is None or raw_val == NULL:
                    geom = self.feat.geometry()
                    if geom and not geom.isEmpty():
                        raw_val = round(geom.length(), 2)

            widget = self._make_widget(ftype, extra, raw_val)
            self.widgets[name] = widget

            if name == 'longueur' and self.role in ('conduite', 'branchement'):
                row = QHBoxLayout()
                row.addWidget(widget)
                btn = QPushButton("↺")
                btn.setFixedWidth(30)
                btn.setToolTip(i18n.tr('rens_recalculer'))
                btn.clicked.connect(self._recalculate_longueur)
                row.addWidget(btn)
                form.addRow(label_text, row)
            elif name == 'pente' and self.role in ('conduite', 'branchement'):
                row = QHBoxLayout()
                row.addWidget(widget)
                btn = QPushButton(i18n.tr('rens_calculer'))
                btn.setFixedWidth(70)
                btn.clicked.connect(self._calculate_pente)
                row.addWidget(btn)
                form.addRow(label_text, row)
            else:
                form.addRow(label_text, widget)

        main_layout.addLayout(form)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self._save)
        buttons.rejected.connect(self.reject)
        main_layout.addWidget(buttons)

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
            msg.addButton('Aucune',          QMessageBox.RejectRole)
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

    def _save(self):
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
