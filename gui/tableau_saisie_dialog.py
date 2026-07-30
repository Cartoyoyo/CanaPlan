# gui/tableau_saisie_dialog.py

import re
from collections import deque

from qgis.core import NULL, QgsPointXY, QgsRectangle
from qgis.gui import QgsMapCanvas
from qgis.PyQt.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QTabWidget, QTableWidget,
    QTableWidgetItem, QPushButton, QComboBox, QLabel, QLineEdit,
    QWidget, QAbstractItemView, QApplication, QGroupBox, QSplitter,
)
from qgis.PyQt.QtCore import Qt
from qgis.PyQt.QtGui import QColor, QKeySequence

from ..tools.spatial_utils import nearest_point_feature
from .chain_profile_widget import ChainProfileWidget

_MATERIAUX = ['PVC', 'Beton', 'Fonte', 'Gres', 'PEHD', 'Amiante-ciment', 'Acier']
_SNAP_TOL = 0.5  # m : tolérance de proximité regard/tabouret <-> extrémité conduite

_NUM_TOKEN_RE = re.compile(r'[+-]?\d*\.?\d+')

_COLOR_MISSING = QColor(181, 50, 42)
_COLOR_DERIVED = QColor(128, 128, 128)


def _fnum(val):
    """Extrait un float depuis une valeur QGIS (gère NULL)."""
    if val is None or val == NULL:
        return None
    try:
        return float(val)
    except (TypeError, ValueError):
        return None


def _parse_num(text):
    """Parse un texte de cellule en float (accepte virgule, sommes type '1-0.25')."""
    if text is None:
        return None
    txt = text.replace(',', '.').replace(' ', '').strip()
    if not txt:
        return None
    tokens = _NUM_TOKEN_RE.findall(txt)
    if not tokens:
        return None
    try:
        return sum(float(t) for t in tokens)
    except ValueError:
        return None


def _fmt(val, decimals=2):
    return '' if val is None else f'{val:.{decimals}f}'


def _sval(val, default='—'):
    if val is None or val == NULL:
        return default
    s = str(val).strip()
    return s if s else default


# ── Définition des colonnes par rôle ────────────────────────────────────────
# (nom_champ, libellé, decimales_ou_None)  ; nom_champ commençant par '__' = colonne calculée/non liée
REGARD_COLS = [
    ('nom',        'Nom',                None),
    ('tn',         'TN (m NGF)',         3),
    ('profondeur', 'Profondeur (m)',     2),
    ('fe_radier',  'FE radier (m NGF)',  3),
    ('diametre',   'Diamètre (mm)',      0),
]
TABOURET_COLS = [
    ('nom',        'Nom',                None),
    ('tn',         'TN (m NGF)',         3),
    ('profondeur', 'Profondeur (m)',     2),
    ('fe_entree',  'FE entrée (m NGF)',  3),
    ('diametre',   'Diamètre (mm)',      0),
]
_FE_FIELD = {'regard': 'fe_radier', 'tabouret': 'fe_entree'}


class TableauSaisieDialog(QDialog):
    """
    Tableau de saisie groupée : tous les regards, tabourets, conduites et
    branchements d'un réseau (EU ou EP) dans une seule fenêtre, éditables
    cellule par cellule. Onglets par type d'ouvrage.
    """

    ROLE_LABELS = {
        'regard': 'Regards', 'tabouret': 'Tabourets',
        'conduite': 'Conduites', 'branchement': 'Branchements',
    }

    def __init__(self, couches_eu, couches_ep, iface=None, parent=None):
        super().__init__(parent)
        self.iface = iface
        self.couches = {'EU': couches_eu, 'EP': couches_ep}
        self.reseau = 'EU'
        self._updating = False
        self._undoing = False
        self._item_registry = {}   # (role, fid, fname) -> QTableWidgetItem
        self._combo_registry = {}  # (role, fid) -> QComboBox (matériau)
        self._col_index = {}       # role -> {fname: col}
        self._cond_state = {}      # fid conduite -> état (mode, amont, aval, items...)
        self._branch_state = {}    # fid branchement -> état (mode, dep, items...)
        self._sort_state = {}      # role -> (col, ascendant)
        self._undo_stack = []      # [{'layer','role','fid','fname','old'}]
        self._batch_items = []
        self._batch_table = None
        self._chain_nodes = None      # [(role, fid), ...] regard1 -> ... -> regard2
        self._chain_segments = []     # longueurs des tronçons entre noeuds consécutifs
        self._chain_conduites = []    # fid de la conduite de chaque tronçon

        self.setWindowTitle("Tableau de saisie - pente")
        self.setAttribute(Qt.WA_DeleteOnClose, False)
        self.setWindowFlags(self.windowFlags()
                             | Qt.WindowMaximizeButtonHint
                             | Qt.WindowMinimizeButtonHint)
        self.resize(1350, 600)
        self._build_ui()
        self._set_mini_map_layers()
        self._reload_all()

    # ------------------------------------------------------------------ UI

    def _build_ui(self):
        outer = QHBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        splitter = QSplitter(Qt.Horizontal)

        left_widget = QWidget()
        layout = QVBoxLayout(left_widget)
        layout.setContentsMargins(0, 0, 0, 0)

        top = QHBoxLayout()
        top.addWidget(QLabel("Réseau :"))
        self.btn_eu = QPushButton("EU")
        self.btn_ep = QPushButton("EP")
        for btn, r in ((self.btn_eu, 'EU'), (self.btn_ep, 'EP')):
            btn.setCheckable(True)
            btn.clicked.connect(lambda _c, rr=r: self._set_reseau(rr))
            top.addWidget(btn)
        self.btn_eu.setChecked(True)
        top.addStretch()

        self.search = QLineEdit()
        self.search.setPlaceholderText("Filtrer par nom…")
        self.search.setFixedWidth(180)
        self.search.textChanged.connect(self._apply_filter)
        top.addWidget(self.search)

        btn_next_missing = QPushButton("⏭ Valeur manquante suivante")
        btn_next_missing.setToolTip("Sélectionne la prochaine cellule en rouge (valeur manquante).")
        btn_next_missing.clicked.connect(self._goto_next_missing)
        top.addWidget(btn_next_missing)
        layout.addLayout(top)

        self.tabs = QTabWidget()
        self.tables = {}
        for role in ('regard', 'tabouret', 'conduite', 'branchement'):
            table = QTableWidget()
            table.setAlternatingRowColors(True)
            table.setSelectionBehavior(QAbstractItemView.SelectItems)
            table.setSelectionMode(QAbstractItemView.ExtendedSelection)
            table.setEditTriggers(QAbstractItemView.DoubleClicked
                                   | QAbstractItemView.EditKeyPressed
                                   | QAbstractItemView.AnyKeyPressed)
            if role == 'conduite':
                table.itemChanged.connect(self._handle_conduite_edit)
            elif role == 'branchement':
                table.itemChanged.connect(self._handle_branchement_edit)
            else:
                table.itemChanged.connect(
                    lambda item, r=role: self._handle_cell_edit(r, item))
            table.itemSelectionChanged.connect(
                lambda t=table: self._on_selection_changed(t))
            table.itemDoubleClicked.connect(
                lambda item, r=role: self._zoom_to_item(r, item))
            header = table.horizontalHeader()
            header.setSectionsClickable(True)
            header.sectionClicked.connect(
                lambda col, r=role: self._sort_by_column(r, col))
            self.tables[role] = table
            self.tabs.addTab(table, self.ROLE_LABELS[role])

        self._build_chain_tab()
        layout.addWidget(self.tabs)

        # Barre d'édition groupée (Ctrl+clic)
        self.batch_bar = QWidget()
        bl = QHBoxLayout(self.batch_bar)
        bl.setContentsMargins(0, 4, 0, 0)
        self.batch_label = QLabel()
        self.batch_input = QLineEdit()
        self.batch_input.setFixedWidth(120)
        self.batch_input.setPlaceholderText("valeur…")
        self.batch_input.returnPressed.connect(self._apply_batch)
        btn_apply = QPushButton("Appliquer à toutes")
        btn_apply.clicked.connect(self._apply_batch)
        btn_cancel = QPushButton("Annuler")
        btn_cancel.clicked.connect(self._clear_selection)
        bl.addWidget(self.batch_label)
        bl.addWidget(self.batch_input)
        bl.addWidget(btn_apply)
        bl.addWidget(btn_cancel)
        bl.addStretch()
        self.batch_bar.setVisible(False)
        layout.addWidget(self.batch_bar)

        bottom = QHBoxLayout()
        self.lbl_status = QLabel()
        bottom.addWidget(self.lbl_status)
        bottom.addStretch()
        btn_undo = QPushButton("↶ Annuler la saisie (Ctrl+Z)")
        btn_undo.clicked.connect(self._undo)
        bottom.addWidget(btn_undo)
        btn_close = QPushButton("Fermer")
        btn_close.clicked.connect(self.accept)
        bottom.addWidget(btn_close)
        layout.addLayout(bottom)

        splitter.addWidget(left_widget)

        right_widget = QWidget()
        right = QVBoxLayout(right_widget)
        right.setContentsMargins(0, 0, 0, 0)
        right.addWidget(QLabel("Aperçu carte"))
        self.mini_canvas = QgsMapCanvas()
        self.mini_canvas.setCanvasColor(QColor(255, 255, 255))
        self.mini_canvas.setMinimumWidth(150)
        right.addWidget(self.mini_canvas)
        splitter.addWidget(right_widget)

        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 1)
        splitter.setSizes([1050, 300])
        outer.addWidget(splitter)

    # ------------------------------------------------------------------ chargement

    def _set_reseau(self, reseau):
        self.reseau = reseau
        self.btn_eu.setChecked(reseau == 'EU')
        self.btn_ep.setChecked(reseau == 'EP')
        self.setWindowTitle(f"Tableau de saisie - pente — Réseau {reseau}")
        self._clear_selection()
        self._chain_nodes = None
        self._chain_segments = []
        self._chain_conduites = []
        if hasattr(self, 'chain_table'):
            self.chain_table.setRowCount(0)
        if hasattr(self, 'chain_profile'):
            self.chain_profile.set_data([])
        if hasattr(self, 'chain_status'):
            self._chain_set_status(
                "Sélectionnez 2 regards puis cliquez sur « Rechercher la chaîne ».", 'info')
            self._chain_set_actions_enabled(False)
        self._set_mini_map_layers()
        self._reload_all()

    def _reload_all(self):
        self._item_registry = {}
        self._cond_state = {}
        self._branch_state = {}
        self._load_regard_tabouret('regard')
        self._load_regard_tabouret('tabouret')
        self._load_conduites()
        self._load_branchements()
        self._update_status()
        self._apply_filter(self.search.text())
        self._populate_chain_combos()

    def _load_regard_tabouret(self, role):
        cols = REGARD_COLS if role == 'regard' else TABOURET_COLS
        layer = self.couches[self.reseau][role]
        table = self.tables[role]

        self._col_index[role] = {name: i for i, (name, _l, _d) in enumerate(cols)}

        table.blockSignals(True)
        table.clear()
        table.setColumnCount(len(cols))
        table.setHorizontalHeaderLabels([c[1] for c in cols])

        feats = list(layer.getFeatures())
        sort = self._sort_state.get(role)
        if sort:
            col, ascending = sort
            sfname, _slabel, sdecimals = cols[col]
            if sdecimals is None:
                feats.sort(key=lambda f: _sval(f[sfname], '').lower(), reverse=not ascending)
            else:
                feats.sort(key=lambda f: (_fnum(f[sfname]) is None, _fnum(f[sfname]) or 0.0),
                           reverse=not ascending)
        else:
            feats.sort(key=lambda f: _sval(f['nom'], ''))
        table.setRowCount(len(feats))

        for row, feat in enumerate(feats):
            fid = feat.id()
            for col, (fname, _label, decimals) in enumerate(cols):
                raw = feat[fname] if layer.fields().indexOf(fname) >= 0 else None
                item = self._make_item(raw, decimals, fid, fname)
                table.setItem(row, col, item)
                self._item_registry[(role, fid, fname)] = item

        table.blockSignals(False)
        table.resizeColumnsToContents()

    def _load_conduites(self):
        layer = self.couches[self.reseau]['conduite']
        regard_layer = self.couches[self.reseau]['regard']
        tabouret_layer = self.couches[self.reseau]['tabouret']
        table = self.tables['conduite']

        headers = ['Tronçon', 'Longueur (m)', 'Diamètre (mm)', 'Matériau',
                   'FE amont (m NGF)', 'Pente (%)', 'FE aval (m NGF)', 'Sens calcul']

        table.blockSignals(True)
        table.clear()
        table.setColumnCount(len(headers))
        table.setHorizontalHeaderLabels(headers)

        feats = self._sort_feats('conduite', list(layer.getFeatures()),
                                  {1: 'longueur', 2: 'diametre',
                                   3: ('materiau', True), 5: 'pente'})
        table.setRowCount(len(feats))

        for row, feat in enumerate(feats):
            fid = feat.id()
            geom = feat.geometry()
            amont_ref = aval_ref = None
            nom_amont = nom_aval = '—'

            if geom and not geom.isEmpty():
                line = geom.asPolyline()
                if len(line) >= 2:
                    amont_ref = self._find_ouvrage(
                        regard_layer, tabouret_layer, QgsPointXY(line[0]))
                    aval_ref = self._find_ouvrage(
                        regard_layer, tabouret_layer, QgsPointXY(line[-1]))
                    if amont_ref:
                        nom_amont = amont_ref[3]
                    if aval_ref:
                        nom_aval = aval_ref[3]

            item0 = QTableWidgetItem(f"{nom_amont} → {nom_aval}")
            item0.setFlags(item0.flags() & ~Qt.ItemIsEditable)
            item0.setData(Qt.UserRole, fid)
            table.setItem(row, 0, item0)

            longueur = _fnum(feat['longueur'])
            if longueur is None and geom and not geom.isEmpty():
                longueur = geom.length()
                self._write_attr(layer, fid, 'longueur', round(longueur, 2),
                                  role='conduite', record_undo=False)
            it_long = self._make_item(longueur, 2, fid, 'longueur')
            it_long.setFlags(it_long.flags() & ~Qt.ItemIsEditable)
            it_long.setForeground(_COLOR_DERIVED)
            it_long.setToolTip("Longueur définie par le tracé — non modifiable ici.")
            table.setItem(row, 1, it_long)
            self._item_registry[('conduite', fid, 'longueur')] = it_long

            it_diam = self._make_item(_fnum(feat['diametre']), 0, fid, 'diametre')
            table.setItem(row, 2, it_diam)
            self._item_registry[('conduite', fid, 'diametre')] = it_diam

            combo = QComboBox()
            combo.setEditable(True)
            combo.addItems(_MATERIAUX)
            cur = _sval(feat['materiau'], '')
            idx = combo.findText(cur)
            if idx >= 0:
                combo.setCurrentIndex(idx)
            else:
                combo.setEditText(cur)
            combo.currentTextChanged.connect(
                lambda text, f=fid: self._write_attr(
                    self.couches[self.reseau]['conduite'], f, 'materiau',
                    text or None, role='conduite'))
            table.setCellWidget(row, 3, combo)
            self._combo_registry[('conduite', fid)] = combo

            fe_amont_val = _fnum(amont_ref[2]) if amont_ref else None
            it_fea = self._make_item(fe_amont_val, 3, fid, '__fe_amont')
            if amont_ref is None:
                it_fea.setFlags(it_fea.flags() & ~Qt.ItemIsEditable)
            it_fea.setForeground(_COLOR_DERIVED)
            table.setItem(row, 4, it_fea)

            fe_aval_val = _fnum(aval_ref[2]) if aval_ref else None
            pente_val = None
            if fe_amont_val is not None and fe_aval_val is not None and longueur:
                pente_val = (fe_amont_val - fe_aval_val) / longueur * 100
            else:
                pente_val = _fnum(feat['pente'])
            it_pente = self._make_item(pente_val, 2, fid, 'pente')
            table.setItem(row, 5, it_pente)
            self._item_registry[('conduite', fid, 'pente')] = it_pente

            it_feav = self._make_item(fe_aval_val, 3, fid, '__fe_aval')
            if aval_ref is None:
                it_feav.setFlags(it_feav.flags() & ~Qt.ItemIsEditable)
            it_feav.setForeground(_COLOR_DERIVED)
            table.setItem(row, 6, it_feav)

            btn = QPushButton()
            btn.clicked.connect(lambda _c, f=fid: self._toggle_cond_mode(f))
            table.setCellWidget(row, 7, btn)

            self._cond_state[fid] = {
                'mode': 'fe',
                'amont': amont_ref, 'aval': aval_ref,
                'longueur_item': it_long, 'pente_item': it_pente,
                'fe_amont_item': it_fea, 'fe_aval_item': it_feav,
                'sens_btn': btn,
            }
            self._apply_cond_mode_style(fid)

        table.blockSignals(False)
        table.resizeColumnsToContents()

    def _load_branchements(self):
        layer = self.couches[self.reseau]['branchement']
        regard_layer = self.couches[self.reseau]['regard']
        tabouret_layer = self.couches[self.reseau]['tabouret']
        table = self.tables['branchement']

        # Colonnes : Branchement | Longueur | Diamètre | Matériau |
        # Cote piquage | Pente | FE tabouret | Sens calcul
        headers = ['Branchement', 'Longueur (m)', 'Diamètre (mm)', 'Matériau',
                   'Cote piquage (m NGF)', 'Pente (%)', 'FE tabouret (m NGF)',
                   'Sens calcul']

        table.blockSignals(True)
        table.clear()
        table.setColumnCount(len(headers))
        table.setHorizontalHeaderLabels(headers)

        feats = self._sort_feats('branchement', list(layer.getFeatures()),
                                  {1: 'longueur', 2: 'diametre',
                                   3: ('materiau', True), 5: 'pente'})
        table.setRowCount(len(feats))

        for row, feat in enumerate(feats):
            fid = feat.id()
            geom = feat.geometry()
            dep_ref = None
            nom_dep, nom_arr = '—', '—'
            if geom and not geom.isEmpty():
                line = geom.asPolyline()
                if line:
                    dep_ref = self._find_ouvrage(
                        regard_layer, tabouret_layer, QgsPointXY(line[0]))
                    arr_ref = self._find_ouvrage(
                        regard_layer, tabouret_layer, QgsPointXY(line[-1]))
                    if dep_ref:
                        nom_dep = dep_ref[3]
                    if arr_ref:
                        nom_arr = arr_ref[3]

            item0 = QTableWidgetItem(f"{nom_dep} → {nom_arr}")
            item0.setFlags(item0.flags() & ~Qt.ItemIsEditable)
            item0.setData(Qt.UserRole, fid)
            table.setItem(row, 0, item0)

            longueur = _fnum(feat['longueur'])
            if longueur is None and geom and not geom.isEmpty():
                longueur = geom.length()
                self._write_attr(layer, fid, 'longueur', round(longueur, 2),
                                  role='branchement', record_undo=False)
            it_long = self._make_item(longueur, 2, fid, 'longueur')
            it_long.setFlags(it_long.flags() & ~Qt.ItemIsEditable)
            it_long.setForeground(_COLOR_DERIVED)
            it_long.setToolTip("Longueur définie par le tracé — non modifiable ici.")
            table.setItem(row, 1, it_long)
            self._item_registry[('branchement', fid, 'longueur')] = it_long

            it_diam = self._make_item(_fnum(feat['diametre']), 0, fid, 'diametre')
            table.setItem(row, 2, it_diam)
            self._item_registry[('branchement', fid, 'diametre')] = it_diam

            combo = QComboBox()
            combo.setEditable(True)
            combo.addItems(_MATERIAUX)
            cur = _sval(feat['materiau'], '')
            idx = combo.findText(cur)
            if idx >= 0:
                combo.setCurrentIndex(idx)
            else:
                combo.setEditText(cur)
            combo.currentTextChanged.connect(
                lambda text, f=fid: self._write_attr(
                    self.couches[self.reseau]['branchement'], f, 'materiau',
                    text or None, role='branchement'))
            table.setCellWidget(row, 3, combo)
            self._combo_registry[('branchement', fid)] = combo

            fe_dep_val = _fnum(dep_ref[2]) if dep_ref else None

            cote_val = _fnum(feat['cote_piquage'])
            it_cote = self._make_item(cote_val, 3, fid, 'cote_piquage')
            table.setItem(row, 4, it_cote)
            self._item_registry[('branchement', fid, 'cote_piquage')] = it_cote

            pente_val = None
            if fe_dep_val is not None and cote_val is not None and longueur:
                pente_val = (fe_dep_val - cote_val) / longueur * 100
            else:
                pente_val = _fnum(feat['pente'])
            it_pente = self._make_item(pente_val, 2, fid, 'pente')
            table.setItem(row, 5, it_pente)
            self._item_registry[('branchement', fid, 'pente')] = it_pente

            it_fe = self._make_item(fe_dep_val, 3, fid, '__fe_tabouret')
            if dep_ref is None:
                it_fe.setFlags(it_fe.flags() & ~Qt.ItemIsEditable)
            it_fe.setForeground(_COLOR_DERIVED)
            table.setItem(row, 6, it_fe)

            btn = QPushButton()
            btn.clicked.connect(lambda _c, f=fid: self._toggle_branch_mode(f))
            table.setCellWidget(row, 7, btn)

            self._branch_state[fid] = {
                'mode': 'fe',
                'dep': dep_ref,
                'longueur_item': it_long, 'pente_item': it_pente,
                'fe_item': it_fe, 'cote_item': it_cote,
                'sens_btn': btn,
            }
            self._apply_branch_mode_style(fid)

        table.blockSignals(False)
        table.resizeColumnsToContents()

    # ------------------------------------------------------------------ helpers cellules

    def _make_item(self, raw_val, decimals, fid, fname):
        if decimals is None:
            item = QTableWidgetItem('' if raw_val in (None, NULL) else str(raw_val))
        else:
            val = raw_val if isinstance(raw_val, (int, float)) else _fnum(raw_val)
            item = QTableWidgetItem(_fmt(val, decimals))
            item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            if val is None:
                item.setForeground(_COLOR_MISSING)
        item.setFlags(item.flags() | Qt.ItemIsEditable)
        item.setData(Qt.UserRole, fid)
        item.setData(Qt.UserRole + 1, fname)
        item.setData(Qt.UserRole + 2, decimals)
        return item

    def _find_ouvrage(self, regard_layer, tabouret_layer, point):
        """Retourne (role, fid, fe_value, nom, fe_field) de l'ouvrage le plus
        proche du point (regard prioritaire), ou None."""
        feat, _dist = nearest_point_feature(regard_layer, point, _SNAP_TOL)
        if feat is not None:
            return ('regard', feat.id(), feat['fe_radier'],
                    _sval(feat['nom'], f"#{feat.id()}"), 'fe_radier')
        feat, _dist = nearest_point_feature(tabouret_layer, point, _SNAP_TOL)
        if feat is not None:
            return ('tabouret', feat.id(), feat['fe_entree'],
                    _sval(feat['nom'], f"#{feat.id()}"), 'fe_entree')
        return None

    def _role_for_layer(self, layer):
        for role, l in self.couches[self.reseau].items():
            if l is layer:
                return role
        return None

    def _write_attr(self, layer, fid, fname, value, role=None, record_undo=True):
        idx = layer.fields().indexOf(fname)
        if idx < 0:
            return
        if record_undo and not self._undoing:
            feat = layer.getFeature(fid)
            old = feat[fname] if feat.isValid() else None
            old = None if old == NULL else old
            self._undo_stack.append({
                'layer': layer, 'role': role or self._role_for_layer(layer),
                'fid': fid, 'fname': fname, 'old': old,
            })
            if len(self._undo_stack) > 200:
                self._undo_stack.pop(0)
        if not layer.isEditable():
            layer.startEditing()
        layer.changeAttributeValue(fid, idx, value)
        layer.commitChanges()

    def _sort_feats(self, role, feats, attr_map):
        """Trie `feats` (liste de QgsFeature) selon self._sort_state[role].

        `attr_map` associe col -> nom_champ (tri numérique) ou
        col -> (nom_champ, True) pour un tri alphabétique."""
        sort = self._sort_state.get(role)
        if not sort:
            return feats
        col, ascending = sort
        spec = attr_map.get(col)
        if not spec:
            return feats
        attr, is_text = spec if isinstance(spec, tuple) else (spec, False)
        if is_text:
            feats.sort(key=lambda f: _sval(f[attr], '').lower(), reverse=not ascending)
        else:
            feats.sort(key=lambda f: (_fnum(f[attr]) is None, _fnum(f[attr]) or 0.0),
                       reverse=not ascending)
        return feats

    # ------------------------------------------------------------------ édition regard/tabouret/branchement

    def _handle_cell_edit(self, role, item):
        if self._updating:
            return
        fid = item.data(Qt.UserRole)
        fname = item.data(Qt.UserRole + 1)
        decimals = item.data(Qt.UserRole + 2)
        if fid is None or fname is None:
            return

        layer = self.couches[self.reseau][role]

        if decimals is None:
            value = item.text().strip() or None
        else:
            value = _parse_num(item.text())
            self._updating = True
            item.setText(_fmt(value, decimals))
            item.setForeground(_COLOR_MISSING if value is None else QColor(0, 0, 0))
            self._updating = False

        self._write_attr(layer, fid, fname, value)

        if role in ('regard', 'tabouret') and fname in ('tn', 'profondeur', _FE_FIELD[role]):
            table = self.tables[role]
            self._autofill_row(role, table, item.row())
            self._refresh_conduite_refs(role, fid)
            self._refresh_branchement_refs(role, fid)

        self._update_status()

    def _handle_conduite_edit(self, item):
        """Cellule éditée dans le tableau des conduites : Longueur, Pente,
        ou directement FE amont / FE aval (Diamètre passe aussi par ici ;
        Matériau est un combo à part)."""
        if self._updating:
            return
        fid = item.data(Qt.UserRole)
        fname = item.data(Qt.UserRole + 1)
        decimals = item.data(Qt.UserRole + 2)
        if fid is None or fname is None:
            return

        value = _parse_num(item.text())

        self._updating = True
        item.setText(_fmt(value, decimals))
        self._updating = False

        st = self._cond_state.get(fid)

        if fname in ('__fe_amont', '__fe_aval'):
            # Édition directe du FE amont/aval : on écrit sur l'ouvrage lié,
            # puis on propage (rafraîchit son onglet + recalcule les conduites
            # connectées, dont potentiellement celle-ci selon le sens actif).
            if not st:
                return
            ref = st['amont'] if fname == '__fe_amont' else st['aval']
            if ref is None:
                return
            role, ouvrage_fid, _old_fe, _nom, fe_field = ref
            self._write_attr(self.couches[self.reseau][role], ouvrage_fid,
                              fe_field, value)
            self._refresh_ouvrage_item(role, ouvrage_fid, fe_field, value)
            self._refresh_conduite_refs(role, ouvrage_fid)
            self._update_status()
            return

        layer = self.couches[self.reseau]['conduite']

        if fname == 'pente':
            # La pente n'est écrite directement en base que si elle pilote le
            # calcul (mode 'pente_aval' ou 'pente_amont') ; en mode 'fe' elle
            # reste une valeur dérivée réécrite par _recalc_cond_row.
            if st and st['mode'] in ('pente_aval', 'pente_amont'):
                self._write_attr(layer, fid, fname, value)
        else:
            self._write_attr(layer, fid, fname, value)

        if st:
            self._recalc_cond_row(fid)

        self._update_status()

    def _autofill_row(self, role, table, row):
        fe_field = _FE_FIELD[role]
        idx = self._col_index[role]
        tn_it = table.item(row, idx['tn'])
        p_it = table.item(row, idx['profondeur'])
        fe_it = table.item(row, idx[fe_field])
        if tn_it is None or p_it is None or fe_it is None:
            return

        tn = _parse_num(tn_it.text())
        p = _parse_num(p_it.text())
        fe = _parse_num(fe_it.text())
        n_none = sum(v is None for v in (tn, p, fe))
        if n_none != 1:
            return

        layer = self.couches[self.reseau][role]
        fid = tn_it.data(Qt.UserRole)

        self._updating = True
        try:
            if tn is None:
                tn = fe + p
                tn_it.setText(_fmt(tn, 3))
                tn_it.setForeground(QColor(0, 0, 0))
                self._write_attr(layer, fid, 'tn', round(tn, 3))
            elif p is None:
                p = tn - fe
                p_it.setText(_fmt(p, 2))
                p_it.setForeground(QColor(0, 0, 0))
                self._write_attr(layer, fid, 'profondeur', round(p, 2))
            else:
                fe = tn - p
                fe_it.setText(_fmt(fe, 3))
                fe_it.setForeground(QColor(0, 0, 0))
                self._write_attr(layer, fid, fe_field, round(fe, 3))
        finally:
            self._updating = False

    # ------------------------------------------------------------------ conduites : sens de calcul

    _COND_MODES = ('fe', 'pente_aval', 'pente_amont')
    _COND_MODE_LABELS = {
        'fe':          "🔒 FE amont + aval",
        'pente_aval':  "🔒 Pente → FE aval",
        'pente_amont': "🔒 Pente → FE amont",
    }
    _COND_MODE_TOOLTIPS = {
        'fe':          "FE amont et FE aval connus → la pente est calculée.",
        'pente_aval':  "FE amont + pente connus → FE aval est calculé et "
                       "appliqué au regard/tabouret aval.",
        'pente_amont': "FE aval + pente connus → FE amont est calculé et "
                       "appliqué au regard/tabouret amont.",
    }

    def _apply_cond_mode_style(self, fid):
        st = self._cond_state[fid]
        pente_item = st['pente_item']
        flags = pente_item.flags()
        mode = st['mode']
        if mode == 'fe':
            pente_item.setFlags(flags & ~Qt.ItemIsEditable)
            pente_item.setBackground(QColor(240, 240, 240))
            pente_item.setForeground(_COLOR_DERIVED)
        else:
            pente_item.setFlags(flags | Qt.ItemIsEditable)
            pente_item.setBackground(QColor(255, 247, 205))
            pente_item.setForeground(QColor(0, 0, 0))
        st['sens_btn'].setText(self._COND_MODE_LABELS[mode])
        st['sens_btn'].setToolTip(self._COND_MODE_TOOLTIPS[mode])

    def _toggle_cond_mode(self, fid):
        st = self._cond_state.get(fid)
        if not st:
            return
        i = self._COND_MODES.index(st['mode'])
        st['mode'] = self._COND_MODES[(i + 1) % len(self._COND_MODES)]
        self._apply_cond_mode_style(fid)
        self._recalc_cond_row(fid)

    def _current_ouvrage_fe(self, role, fid):
        fe_field = _FE_FIELD[role]
        item = self._item_registry.get((role, fid, fe_field))
        if item is None:
            return None
        return _parse_num(item.text())

    def _recalc_cond_row(self, fid):
        st = self._cond_state.get(fid)
        if not st:
            return
        amont, aval = st['amont'], st['aval']
        longueur = _parse_num(st['longueur_item'].text())
        mode = st['mode']

        if amont is None or aval is None or not longueur:
            return

        if mode == 'pente_aval':
            # FE amont + pente connus -> FE aval calculé et appliqué au regard aval
            pente = _parse_num(st['pente_item'].text())
            fe_amont_val = self._current_ouvrage_fe(amont[0], amont[1])
            if pente is None or fe_amont_val is None:
                return
            fe_aval_new = fe_amont_val - (pente / 100.0) * longueur

            aval_role, aval_fid, _fe, nom_aval, fe_field = aval
            self._write_attr(self.couches[self.reseau][aval_role],
                              aval_fid, fe_field, round(fe_aval_new, 3))

            self._updating = True
            st['fe_amont_item'].setText(_fmt(fe_amont_val, 3))
            st['fe_aval_item'].setText(_fmt(fe_aval_new, 3))
            self._updating = False
            st['aval'] = (aval_role, aval_fid, fe_aval_new, nom_aval, fe_field)

            self._refresh_ouvrage_item(aval_role, aval_fid, fe_field, fe_aval_new)

        elif mode == 'pente_amont':
            # FE aval + pente connus -> FE amont calculé et appliqué au regard amont
            pente = _parse_num(st['pente_item'].text())
            fe_aval_val = self._current_ouvrage_fe(aval[0], aval[1])
            if pente is None or fe_aval_val is None:
                return
            fe_amont_new = fe_aval_val + (pente / 100.0) * longueur

            amont_role, amont_fid, _fe, nom_amont, fe_field = amont
            self._write_attr(self.couches[self.reseau][amont_role],
                              amont_fid, fe_field, round(fe_amont_new, 3))

            self._updating = True
            st['fe_amont_item'].setText(_fmt(fe_amont_new, 3))
            st['fe_aval_item'].setText(_fmt(fe_aval_val, 3))
            self._updating = False
            st['amont'] = (amont_role, amont_fid, fe_amont_new, nom_amont, fe_field)

            self._refresh_ouvrage_item(amont_role, amont_fid, fe_field, fe_amont_new)

        else:
            # mode 'fe' : FE amont et FE aval connus -> pente dérivée
            fe_amont_val = self._current_ouvrage_fe(amont[0], amont[1])
            fe_aval_val = self._current_ouvrage_fe(aval[0], aval[1])
            if fe_amont_val is None or fe_aval_val is None:
                return
            pente = (fe_amont_val - fe_aval_val) / longueur * 100

            self._updating = True
            st['pente_item'].setText(_fmt(pente, 2))
            st['fe_amont_item'].setText(_fmt(fe_amont_val, 3))
            st['fe_aval_item'].setText(_fmt(fe_aval_val, 3))
            self._updating = False
            self._write_attr(self.couches[self.reseau]['conduite'],
                              fid, 'pente', round(pente, 3))

    def _refresh_ouvrage_item(self, role, fid, fname, value):
        """Met à jour l'affichage de l'onglet Regards/Tabourets si la ligne est chargée,
        et relance le calcul TN/Profondeur/FE de cette ligne."""
        item = self._item_registry.get((role, fid, fname))
        if item is None:
            return
        self._updating = True
        item.setText(_fmt(value, 3))
        item.setForeground(QColor(0, 0, 0))
        self._updating = False
        table = item.tableWidget()
        if table is not None:
            self._autofill_row(role, table, item.row())

    def _refresh_conduite_refs(self, role, fid):
        """Quand un TN/P/FE d'ouvrage change, met à jour les conduites qui le référencent."""
        for cfid, st in list(self._cond_state.items()):
            amont, aval = st['amont'], st['aval']
            touched = False
            if amont and amont[0] == role and amont[1] == fid:
                new_val = self._current_ouvrage_fe(role, fid)
                st['amont'] = (amont[0], amont[1], new_val, amont[3], amont[4])
                touched = True
            if aval and aval[0] == role and aval[1] == fid:
                new_val = self._current_ouvrage_fe(role, fid)
                st['aval'] = (aval[0], aval[1], new_val, aval[3], aval[4])
                touched = True
            if touched:
                self._recalc_cond_row(cfid)

    # ------------------------------------------------------------------ branchements : édition + sens de calcul

    def _handle_branchement_edit(self, item):
        """Cellule éditée dans le tableau des branchements : Diamètre, Pente,
        Cote piquage, ou directement FE tabouret."""
        if self._updating:
            return
        fid = item.data(Qt.UserRole)
        fname = item.data(Qt.UserRole + 1)
        decimals = item.data(Qt.UserRole + 2)
        if fid is None or fname is None:
            return

        value = _parse_num(item.text())

        self._updating = True
        item.setText(_fmt(value, decimals))
        self._updating = False

        st = self._branch_state.get(fid)

        if fname == '__fe_tabouret':
            # Édition directe de la FE tabouret : on écrit sur l'ouvrage lié,
            # puis on propage (rafraîchit son onglet + recalcule les branchements
            # connectés).
            if not st or st['dep'] is None:
                return
            role, ouvrage_fid, _old_fe, _nom, fe_field = st['dep']
            self._write_attr(self.couches[self.reseau][role], ouvrage_fid,
                              fe_field, value)
            self._refresh_ouvrage_item(role, ouvrage_fid, fe_field, value)
            self._refresh_branchement_refs(role, ouvrage_fid)
            self._update_status()
            return

        layer = self.couches[self.reseau]['branchement']

        if fname == 'pente':
            # La pente n'est écrite directement en base que si elle pilote le
            # calcul (mode 'pente_aval' ou 'pente_amont') ; en mode 'fe' elle
            # reste une valeur dérivée réécrite par _recalc_branch_row.
            if st and st['mode'] in ('pente_aval', 'pente_amont'):
                self._write_attr(layer, fid, fname, value)
        else:
            self._write_attr(layer, fid, fname, value)

        if st:
            self._recalc_branch_row(fid)

        self._update_status()

    _BRANCH_MODES = ('fe', 'pente_aval', 'pente_amont')
    _BRANCH_MODE_LABELS = {
        'fe':          "🔒 FE + cote piquage",
        'pente_aval':  "🔒 Pente → cote piquage",
        'pente_amont': "🔒 Pente → FE tabouret",
    }
    _BRANCH_MODE_TOOLTIPS = {
        'fe':          "FE tabouret et cote piquage connus → la pente est calculée.",
        'pente_aval':  "FE tabouret + pente connus → la cote piquage est calculée.",
        'pente_amont': "Cote piquage + pente connus → FE tabouret est calculé et "
                       "appliqué au tabouret/regard.",
    }

    def _apply_branch_mode_style(self, fid):
        st = self._branch_state[fid]
        pente_item = st['pente_item']
        flags = pente_item.flags()
        mode = st['mode']
        if mode == 'fe':
            pente_item.setFlags(flags & ~Qt.ItemIsEditable)
            pente_item.setBackground(QColor(240, 240, 240))
            pente_item.setForeground(_COLOR_DERIVED)
        else:
            pente_item.setFlags(flags | Qt.ItemIsEditable)
            pente_item.setBackground(QColor(255, 247, 205))
            pente_item.setForeground(QColor(0, 0, 0))
        st['sens_btn'].setText(self._BRANCH_MODE_LABELS[mode])
        st['sens_btn'].setToolTip(self._BRANCH_MODE_TOOLTIPS[mode])

    def _toggle_branch_mode(self, fid):
        st = self._branch_state.get(fid)
        if not st:
            return
        i = self._BRANCH_MODES.index(st['mode'])
        st['mode'] = self._BRANCH_MODES[(i + 1) % len(self._BRANCH_MODES)]
        self._apply_branch_mode_style(fid)
        self._recalc_branch_row(fid)

    def _recalc_branch_row(self, fid):
        st = self._branch_state.get(fid)
        if not st:
            return
        dep = st['dep']
        longueur = _parse_num(st['longueur_item'].text())
        mode = st['mode']

        if dep is None or not longueur:
            return

        if mode == 'pente_aval':
            # FE tabouret + pente connus -> cote piquage calculée
            pente = _parse_num(st['pente_item'].text())
            fe_val = self._current_ouvrage_fe(dep[0], dep[1])
            if pente is None or fe_val is None:
                return
            cote_new = fe_val - (pente / 100.0) * longueur

            layer = self.couches[self.reseau]['branchement']
            self._write_attr(layer, fid, 'cote_piquage', round(cote_new, 3))

            self._updating = True
            st['fe_item'].setText(_fmt(fe_val, 3))
            st['cote_item'].setText(_fmt(cote_new, 3))
            self._updating = False

        elif mode == 'pente_amont':
            # Cote piquage + pente connus -> FE tabouret calculé et appliqué au tabouret/regard
            pente = _parse_num(st['pente_item'].text())
            cote_val = _parse_num(st['cote_item'].text())
            if pente is None or cote_val is None:
                return
            fe_new = cote_val + (pente / 100.0) * longueur

            role, ouvrage_fid, _fe, nom, fe_field = dep
            self._write_attr(self.couches[self.reseau][role], ouvrage_fid,
                              fe_field, round(fe_new, 3))

            self._updating = True
            st['fe_item'].setText(_fmt(fe_new, 3))
            st['cote_item'].setText(_fmt(cote_val, 3))
            self._updating = False
            st['dep'] = (role, ouvrage_fid, fe_new, nom, fe_field)

            self._refresh_ouvrage_item(role, ouvrage_fid, fe_field, fe_new)

        else:
            # mode 'fe' : FE tabouret + cote piquage connus -> pente dérivée
            fe_val = self._current_ouvrage_fe(dep[0], dep[1])
            cote_val = _parse_num(st['cote_item'].text())
            if fe_val is None or cote_val is None:
                return
            pente = (fe_val - cote_val) / longueur * 100

            self._updating = True
            st['pente_item'].setText(_fmt(pente, 2))
            st['fe_item'].setText(_fmt(fe_val, 3))
            self._updating = False
            self._write_attr(self.couches[self.reseau]['branchement'],
                              fid, 'pente', round(pente, 3))

    def _refresh_branchement_refs(self, role, fid):
        """Quand un TN/P/FE d'ouvrage change, met à jour les branchements qui le référencent."""
        for bfid, st in list(self._branch_state.items()):
            dep = st['dep']
            if dep and dep[0] == role and dep[1] == fid:
                new_val = self._current_ouvrage_fe(role, fid)
                st['dep'] = (dep[0], dep[1], new_val, dep[3], dep[4])
                self._recalc_branch_row(bfid)

    # ------------------------------------------------------------------ sélection multiple / édition groupée

    def _on_selection_changed(self, table):
        items = [it for it in table.selectedItems() if it.flags() & Qt.ItemIsEditable]
        if len(items) > 1:
            self._batch_items = items
            self._batch_table = table
            self.batch_label.setText(f"{len(items)} cellules sélectionnées :")
            self.batch_bar.setVisible(True)
        else:
            self.batch_bar.setVisible(False)
            self._batch_items = []
            self._batch_table = None
        self._update_mini_map(table)

    def _apply_batch(self):
        val = self.batch_input.text().strip()
        if not val or not self._batch_items:
            return
        table = self._batch_table
        items = list(self._batch_items)
        table.blockSignals(True)
        for item in items:
            item.setText(val)
        table.blockSignals(False)

        role = self._role_of_table(table)
        for item in items:
            self._dispatch_cell_edit(role, item)

        self.batch_input.clear()
        self._clear_selection()

    def _dispatch_cell_edit(self, role, item):
        if role == 'conduite':
            self._handle_conduite_edit(item)
        elif role == 'branchement':
            self._handle_branchement_edit(item)
        else:
            self._handle_cell_edit(role, item)

    def _clear_selection(self):
        if self._batch_table is not None:
            self._batch_table.clearSelection()
        self.batch_bar.setVisible(False)
        self._batch_items = []
        self._batch_table = None

    def _role_of_table(self, table):
        for role, t in self.tables.items():
            if t is table:
                return role
        return None

    # ------------------------------------------------------------------ filtre / status

    def _apply_filter(self, text):
        text = text.strip().lower()
        for table in self.tables.values():
            for row in range(table.rowCount()):
                item0 = table.item(row, 0)
                match = (not text) or (item0 is not None and text in item0.text().lower())
                table.setRowHidden(row, not match)

    def _update_status(self):
        counts = {role: self.tables[role].rowCount() for role in self.tables}
        n_missing = 0
        for table in self.tables.values():
            for row in range(table.rowCount()):
                for col in range(table.columnCount()):
                    it = table.item(row, col)
                    if it is not None and it.foreground().color() == _COLOR_MISSING:
                        n_missing += 1
        self.lbl_status.setText(
            f"{counts['regard']} regards · {counts['tabouret']} tabourets · "
            f"{counts['conduite']} conduites · {counts['branchement']} branchements "
            f"— réseau {self.reseau} — {n_missing} valeur(s) manquante(s)")

    # ------------------------------------------------------------------ lien carte

    def _select_feature(self, role, fid):
        layer = self.couches[self.reseau][role]
        layer.removeSelection()
        layer.select(fid)

    def _feature_bbox(self, role, fid):
        layer = self.couches[self.reseau][role]
        feat = layer.getFeature(fid)
        if not feat.isValid():
            return None
        geom = feat.geometry()
        if geom is None or geom.isEmpty():
            return None
        return QgsRectangle(geom.boundingBox())

    def _zoom_to_item(self, role, item):
        fid = item.data(Qt.UserRole)
        if fid is None:
            return
        self._select_feature(role, fid)
        self._mini_map_zoom(role, fid)

        if self.iface is None:
            return
        bbox = self._feature_bbox(role, fid)
        if bbox is None:
            return
        if bbox.width() == 0 and bbox.height() == 0:
            bbox.grow(5.0)
        else:
            bbox.scale(1.3)
        canvas = self.iface.mapCanvas()
        canvas.setExtent(bbox)
        canvas.refresh()

    # ------------------------------------------------------------------ mini-carte d'aperçu

    def _set_mini_map_layers(self):
        c = self.couches[self.reseau]
        network_layers = [c['regard'], c['tabouret'], c['conduite'], c['branchement']]

        fond_layers = []
        if self.iface is not None:
            main_canvas = self.iface.mapCanvas()
            fond_layers = [l for l in main_canvas.layers() if l not in network_layers]
            self.mini_canvas.setDestinationCrs(main_canvas.mapSettings().destinationCrs())
        else:
            self.mini_canvas.setDestinationCrs(network_layers[0].crs())

        self.mini_canvas.setLayers(network_layers + fond_layers)

        ext = None
        for l in network_layers:
            e = l.extent()
            if e.isNull():
                continue
            if ext is None:
                ext = QgsRectangle(e)
            else:
                ext.combineExtentWith(e)
        if ext is not None:
            if ext.width() == 0 and ext.height() == 0:
                ext.grow(15.0)
            else:
                ext.scale(1.1)
            self.mini_canvas.setExtent(ext)
        self.mini_canvas.refresh()

    def _update_mini_map(self, table):
        items = table.selectedItems()
        if not items:
            return
        fid = items[0].data(Qt.UserRole)
        if table is getattr(self, 'chain_table', None):
            row = items[0].row()
            if not self._chain_nodes or row >= len(self._chain_nodes):
                return
            role = self._chain_nodes[row][0]
        else:
            role = self._role_of_table(table)
        if fid is None or role is None:
            return
        self._select_feature(role, fid)
        self._mini_map_zoom(role, fid)

    def _mini_map_zoom(self, role, fid):
        bbox = self._feature_bbox(role, fid)
        if bbox is None:
            return
        if bbox.width() == 0 and bbox.height() == 0:
            bbox.grow(15.0)
        else:
            bbox.scale(2.5)
        self.mini_canvas.setExtent(bbox)
        self.mini_canvas.refresh()

    # ------------------------------------------------------------------ tri

    def _sort_by_column(self, role, col):
        prev = self._sort_state.get(role)
        ascending = not (prev and prev[0] == col and prev[1])
        self._sort_state[role] = (col, ascending)
        if role in ('regard', 'tabouret'):
            self._load_regard_tabouret(role)
        elif role == 'conduite':
            self._load_conduites()
        else:
            self._load_branchements()
        self._apply_filter(self.search.text())

    # ------------------------------------------------------------------ navigation valeurs manquantes

    def _goto_next_missing(self):
        role = self._role_of_table(self.tabs.currentWidget())
        order = ['regard', 'tabouret', 'conduite', 'branchement']
        start_idx = order.index(role) if role in order else 0
        current_table = self.tabs.currentWidget()
        cur_row, cur_col = current_table.currentRow(), current_table.currentColumn()

        for offset in range(len(order) + 1):
            r = order[(start_idx + offset) % len(order)]
            table = self.tables[r]
            for row in range(table.rowCount()):
                for col in range(table.columnCount()):
                    if offset == 0 and (row, col) <= (cur_row, cur_col):
                        continue
                    it = table.item(row, col)
                    if it is not None and it.foreground().color() == _COLOR_MISSING \
                            and not table.isRowHidden(row):
                        self.tabs.setCurrentWidget(table)
                        table.setCurrentCell(row, col)
                        table.scrollToItem(it)
                        return

    # ------------------------------------------------------------------ copier / coller

    def _copy_selection(self):
        table = self.tabs.currentWidget()
        if not isinstance(table, QTableWidget):
            return
        ranges = table.selectedRanges()
        if not ranges:
            return
        rng = ranges[0]
        rows = range(rng.topRow(), rng.bottomRow() + 1)
        cols = range(rng.leftColumn(), rng.rightColumn() + 1)
        lines = []
        for row in rows:
            cells = []
            for col in cols:
                it = table.item(row, col)
                cells.append(it.text() if it is not None else '')
            lines.append('\t'.join(cells))
        QApplication.clipboard().setText('\n'.join(lines))

    def _paste_selection(self):
        table = self.tabs.currentWidget()
        if not isinstance(table, QTableWidget):
            return
        text = QApplication.clipboard().text()
        if not text:
            return
        role = self._role_of_table(table)
        start_row = max(table.currentRow(), 0)
        start_col = max(table.currentColumn(), 0)

        grid = [line.split('\t') for line in text.splitlines() if line != '']
        touched = []
        table.blockSignals(True)
        for dr, cells in enumerate(grid):
            row = start_row + dr
            if row >= table.rowCount():
                break
            for dc, value in enumerate(cells):
                col = start_col + dc
                if col >= table.columnCount():
                    continue
                it = table.item(row, col)
                if it is None or not (it.flags() & Qt.ItemIsEditable):
                    continue
                it.setText(value.strip())
                touched.append(it)
        table.blockSignals(False)

        for it in touched:
            self._dispatch_cell_edit(role, it)

    # ------------------------------------------------------------------ annuler (Ctrl+Z)

    def _undo(self):
        if not self._undo_stack:
            return
        entry = self._undo_stack.pop()
        self._undoing = True
        try:
            self._write_attr(entry['layer'], entry['fid'], entry['fname'],
                              entry['old'], role=entry['role'], record_undo=False)
            self._refresh_after_write(entry['role'], entry['fid'], entry['fname'], entry['old'])
        finally:
            self._undoing = False

    def _refresh_after_write(self, role, fid, fname, value):
        """Répercute dans l'UI une écriture faite hors édition directe de cellule
        (utilisé par l'annulation)."""
        if fname == 'materiau':
            combo = self._combo_registry.get((role, fid))
            if combo is not None:
                self._updating = True
                idx = combo.findText(value or '')
                if idx >= 0:
                    combo.setCurrentIndex(idx)
                else:
                    combo.setEditText(value or '')
                self._updating = False
        else:
            item = self._item_registry.get((role, fid, fname))
            if item is not None:
                decimals = item.data(Qt.UserRole + 2)
                self._updating = True
                if decimals is None:
                    item.setText('' if value in (None, NULL) else str(value))
                else:
                    fval = _fnum(value)
                    item.setText(_fmt(fval, decimals))
                    item.setForeground(_COLOR_MISSING if fval is None else QColor(0, 0, 0))
                self._updating = False

        if role in ('regard', 'tabouret'):
            item = self._item_registry.get((role, fid, fname))
            if item is not None:
                table = item.tableWidget()
                if table is not None:
                    self._autofill_row(role, table, item.row())
            self._refresh_conduite_refs(role, fid)
            self._refresh_branchement_refs(role, fid)
        elif role == 'conduite':
            self._recalc_cond_row(fid)
        elif role == 'branchement':
            self._recalc_branch_row(fid)

        self._update_status()

    # ------------------------------------------------------------------ chaîne entre 2 regards

    def _build_chain_tab(self):
        tab = QWidget()
        v = QVBoxLayout(tab)

        sel_row = QHBoxLayout()
        sel_row.addWidget(QLabel("Regard de départ :"))
        self.combo_regard1 = QComboBox()
        self.combo_regard1.setToolTip("Le regard à partir duquel la chaîne est parcourue.")
        self.combo_regard1.setMinimumWidth(140)
        sel_row.addWidget(self.combo_regard1)

        btn_swap = QPushButton("⇄")
        btn_swap.setToolTip("Inverser le regard de départ et le regard d'arrivée.")
        btn_swap.setFixedWidth(32)
        btn_swap.clicked.connect(self._chain_swap_regards)
        sel_row.addWidget(btn_swap)

        sel_row.addWidget(QLabel("Regard d'arrivée :"))
        self.combo_regard2 = QComboBox()
        self.combo_regard2.setToolTip("Le regard où la chaîne doit s'arrêter.")
        self.combo_regard2.setMinimumWidth(140)
        sel_row.addWidget(self.combo_regard2)

        btn_detect = QPushButton("🔍 Rechercher la chaîne")
        btn_detect.setToolTip(
            "Retrouve automatiquement tous les regards, tabourets et conduites "
            "entre les deux regards choisis.")
        btn_detect.clicked.connect(self._detect_chain)
        sel_row.addWidget(btn_detect)
        sel_row.addStretch()
        v.addLayout(sel_row)

        self.chain_status = QLabel(
            "Sélectionnez 2 regards puis cliquez sur « Rechercher la chaîne ».")
        self.chain_status.setWordWrap(True)
        self._chain_set_status(self.chain_status.text(), 'info')
        v.addWidget(self.chain_status)

        self.chain_profile = ChainProfileWidget()
        v.addWidget(self.chain_profile)

        self.chain_table = QTableWidget()
        self.chain_table.setColumnCount(7)
        self.chain_table.setHorizontalHeaderLabels([
            'Ouvrage', 'Type', 'TN (m NGF)', 'Profondeur (m)',
            'FE (m NGF)', 'Longueur cumulée (m)', 'Pente vers suivant (%)'])
        self.chain_table.setToolTip(
            "Double-cliquez une cellule pour la modifier. Les valeurs se "
            "recalculent automatiquement le long de la chaîne.\n"
            "Double-clic sur une ligne : zoom sur l'ouvrage dans QGIS.")
        self.chain_table.setAlternatingRowColors(True)
        self.chain_table.setSelectionBehavior(QAbstractItemView.SelectItems)
        self.chain_table.setEditTriggers(QAbstractItemView.DoubleClicked
                                          | QAbstractItemView.EditKeyPressed
                                          | QAbstractItemView.AnyKeyPressed)
        self.chain_table.itemChanged.connect(self._handle_chain_edit)
        self.chain_table.itemSelectionChanged.connect(
            lambda: self._update_mini_map(self.chain_table))
        self.chain_table.itemDoubleClicked.connect(self._chain_zoom_to_item)
        v.addWidget(self.chain_table)

        actions_row = QHBoxLayout()

        grp1 = QGroupBox("① Pente constante")
        grp1.setToolTip(
            "Choisissez une pente à la main : elle sera appliquée sur toute la "
            "chaîne en partant du regard de départ, en recalculant chaque FE "
            "(et profondeur) en cascade.")
        l1 = QHBoxLayout(grp1)
        self.chain_pente_input = QLineEdit()
        self.chain_pente_input.setPlaceholderText("ex : 0.5")
        self.chain_pente_input.setFixedWidth(70)
        self.chain_pente_input.returnPressed.connect(self._chain_apply_pente_imposee)
        l1.addWidget(self.chain_pente_input)
        l1.addWidget(QLabel("%"))
        self.btn_chain_action1 = QPushButton("Appliquer")
        self.btn_chain_action1.clicked.connect(self._chain_apply_pente_imposee)
        l1.addWidget(self.btn_chain_action1)
        actions_row.addWidget(grp1)

        grp2 = QGroupBox("② Pente calculée")
        grp2.setToolTip(
            "Calcule automatiquement la pente moyenne à partir des altitudes (FE) "
            "connues du regard de départ et du regard d'arrivée, puis l'applique "
            "sur toute la chaîne — utile quand seuls ces 2 points sont connus.")
        l2 = QHBoxLayout(grp2)
        self.btn_chain_action2 = QPushButton("Calculer et appliquer")
        self.btn_chain_action2.clicked.connect(self._chain_apply_pente_calculee)
        l2.addWidget(self.btn_chain_action2)
        actions_row.addWidget(grp2)

        grp3 = QGroupBox("③ Profondeur fixe")
        grp3.setToolTip(
            "Applique la même profondeur (ex : 1,00 m) à tous les regards/tabourets "
            "de la chaîne. Le FE est recalculé automatiquement si le TN est connu.")
        l3 = QHBoxLayout(grp3)
        self.chain_prof_input = QLineEdit("1.00")
        self.chain_prof_input.setFixedWidth(70)
        self.chain_prof_input.returnPressed.connect(self._chain_apply_profondeur_fixe)
        l3.addWidget(self.chain_prof_input)
        l3.addWidget(QLabel("m"))
        self.btn_chain_action3 = QPushButton("Appliquer")
        self.btn_chain_action3.clicked.connect(self._chain_apply_profondeur_fixe)
        l3.addWidget(self.btn_chain_action3)
        actions_row.addWidget(grp3)

        v.addLayout(actions_row)

        self._chain_set_actions_enabled(False)

        self.tabs.addTab(tab, "Chaîne regards")

    def _chain_set_actions_enabled(self, enabled):
        for btn in (self.btn_chain_action1, self.btn_chain_action2, self.btn_chain_action3):
            btn.setEnabled(enabled)

    def _chain_set_status(self, text, kind='info'):
        colors = {
            'info':    '#555',
            'success': '#1a7a1a',
            'error':   '#b5322a',
        }
        self.chain_status.setStyleSheet(
            f"color: {colors.get(kind, '#555')}; font-weight: {'bold' if kind != 'info' else 'normal'};")
        self.chain_status.setText(text)

    def _chain_swap_regards(self):
        i1, i2 = self.combo_regard1.currentIndex(), self.combo_regard2.currentIndex()
        self.combo_regard1.setCurrentIndex(i2)
        self.combo_regard2.setCurrentIndex(i1)

    def _populate_chain_combos(self):
        if not hasattr(self, 'combo_regard1'):
            return
        layer = self.couches[self.reseau]['regard']
        noms = sorted(_sval(f['nom'], f"#{f.id()}") for f in layer.getFeatures())
        for combo in (self.combo_regard1, self.combo_regard2):
            cur = combo.currentText()
            combo.blockSignals(True)
            combo.clear()
            combo.addItems(noms)
            idx = combo.findText(cur)
            if idx >= 0:
                combo.setCurrentIndex(idx)
            combo.blockSignals(False)

    def _find_regard_by_nom(self, nom):
        layer = self.couches[self.reseau]['regard']
        for f in layer.getFeatures():
            if _sval(f['nom'], f"#{f.id()}") == nom:
                return f
        return None

    def _build_graph(self):
        """Graphe non orienté regards/tabourets <-> conduites du réseau actif :
        {(role, fid): [((role, fid), conduite_fid, longueur), ...]}"""
        regard_layer = self.couches[self.reseau]['regard']
        tabouret_layer = self.couches[self.reseau]['tabouret']
        conduite_layer = self.couches[self.reseau]['conduite']
        adj = {}
        for feat in conduite_layer.getFeatures():
            geom = feat.geometry()
            if geom is None or geom.isEmpty():
                continue
            line = geom.asPolyline()
            if len(line) < 2:
                continue
            a = self._find_ouvrage(regard_layer, tabouret_layer, QgsPointXY(line[0]))
            b = self._find_ouvrage(regard_layer, tabouret_layer, QgsPointXY(line[-1]))
            if a is None or b is None:
                continue
            longueur = _fnum(feat['longueur']) or geom.length()
            ka, kb = (a[0], a[1]), (b[0], b[1])
            adj.setdefault(ka, []).append((kb, feat.id(), longueur))
            adj.setdefault(kb, []).append((ka, feat.id(), longueur))
        return adj

    def _find_chain(self, key1, key2):
        """Plus court chemin (en nb de tronçons) entre 2 noeuds. Retourne une liste
        [(depuis, vers, conduite_fid, longueur), ...] ou None si pas de chemin."""
        adj = self._build_graph()
        visited = {key1: None}
        queue = deque([key1])
        while queue:
            cur = queue.popleft()
            if cur == key2:
                break
            for neigh, cfid, longueur in adj.get(cur, []):
                if neigh not in visited:
                    visited[neigh] = (cur, cfid, longueur)
                    queue.append(neigh)
        if key2 not in visited:
            return None
        path = []
        node = key2
        while node != key1:
            prev, cfid, longueur = visited[node]
            path.append((prev, node, cfid, longueur))
            node = prev
        path.reverse()
        return path

    def _detect_chain(self):
        nom1 = self.combo_regard1.currentText()
        nom2 = self.combo_regard2.currentText()
        if not nom1 or not nom2 or nom1 == nom2:
            self._chain_set_status("Choisissez deux regards différents.", 'error')
            self._chain_set_actions_enabled(False)
            return
        feat1 = self._find_regard_by_nom(nom1)
        feat2 = self._find_regard_by_nom(nom2)
        if feat1 is None or feat2 is None:
            self._chain_set_status("Regard introuvable.", 'error')
            self._chain_set_actions_enabled(False)
            return
        key1, key2 = ('regard', feat1.id()), ('regard', feat2.id())
        path = self._find_chain(key1, key2)
        if path is None:
            self._chain_nodes = None
            self._chain_conduites = []
            self.chain_table.setRowCount(0)
            self.chain_profile.set_data([])
            self._chain_set_status(
                f"Aucune chaîne trouvée entre {nom1} et {nom2}. "
                "Vérifiez qu'un tracé de conduites les relie bien.", 'error')
            self._chain_set_actions_enabled(False)
            return
        self._chain_nodes = [key1] + [step[1] for step in path]
        self._chain_segments = [step[3] for step in path]
        self._chain_conduites = [step[2] for step in path]
        self._chain_force_fe_mode()
        self._chain_set_status(
            f"✓ Chaîne trouvée : {len(self._chain_nodes)} ouvrages, "
            f"{sum(self._chain_segments):.1f} m au total. Vous pouvez modifier "
            "le tableau ci-dessous ou utiliser une des 3 actions.", 'success')
        self._chain_set_actions_enabled(True)
        self._refresh_chain_table()
        self._chain_zoom_whole()

    def _chain_zoom_to_item(self, item):
        row = item.row()
        if not self._chain_nodes or row >= len(self._chain_nodes):
            return
        role, _fid = self._chain_nodes[row]
        self._zoom_to_item(role, item)

    def _chain_zoom_whole(self):
        """Zoome la carte principale et la mini-carte sur l'ensemble de la chaîne
        (ouvrages + conduites), et sélectionne ces entités."""
        if not self._chain_nodes:
            return
        ext = None
        for role, fid in self._chain_nodes:
            bbox = self._feature_bbox(role, fid)
            if bbox is None:
                continue
            if ext is None:
                ext = QgsRectangle(bbox)
            else:
                ext.combineExtentWith(bbox)

        conduite_layer = self.couches[self.reseau]['conduite']
        for cfid in self._chain_conduites:
            feat = conduite_layer.getFeature(cfid)
            if not feat.isValid():
                continue
            geom = feat.geometry()
            if geom is None or geom.isEmpty():
                continue
            bbox = geom.boundingBox()
            if ext is None:
                ext = QgsRectangle(bbox)
            else:
                ext.combineExtentWith(bbox)

        if ext is None:
            return
        if ext.width() == 0 and ext.height() == 0:
            ext.grow(15.0)
        else:
            ext.scale(1.3)

        self.mini_canvas.setExtent(ext)
        self.mini_canvas.refresh()
        if self.iface is not None:
            canvas = self.iface.mapCanvas()
            canvas.setExtent(ext)
            canvas.refresh()

        regard_layer = self.couches[self.reseau]['regard']
        tabouret_layer = self.couches[self.reseau]['tabouret']
        regard_layer.removeSelection()
        tabouret_layer.removeSelection()
        conduite_layer.removeSelection()
        for role, fid in self._chain_nodes:
            self.couches[self.reseau][role].select(fid)
        for cfid in self._chain_conduites:
            conduite_layer.select(cfid)

    def _chain_force_fe_mode(self):
        """Force le mode 'FE amont + aval' (dérive la pente) sur les conduites de la
        chaîne, pour que la cascade FE se propage de façon cohérente avec l'onglet
        Conduites après une modification depuis cet onglet."""
        for cfid in getattr(self, '_chain_conduites', []):
            st = self._cond_state.get(cfid)
            if st and st['mode'] != 'fe':
                st['mode'] = 'fe'
                self._apply_cond_mode_style(cfid)

    def _refresh_chain_table(self):
        if not self._chain_nodes:
            return
        table = self.chain_table
        table.blockSignals(True)
        table.setRowCount(len(self._chain_nodes))
        cum = 0.0
        fe_values = []
        profile_data = []
        for i, (role, fid) in enumerate(self._chain_nodes):
            layer = self.couches[self.reseau][role]
            feat = layer.getFeature(fid)
            if i > 0:
                cum += self._chain_segments[i - 1]
            fe_field = _FE_FIELD[role]
            tn = _fnum(feat['tn'])
            profondeur = _fnum(feat['profondeur'])
            fe = _fnum(feat[fe_field])
            fe_values.append(fe)
            profile_data.append({
                'nom': _sval(feat['nom'], f"#{fid}"),
                'cum': cum, 'tn': tn, 'profondeur': profondeur, 'fe': fe,
            })

            it0 = QTableWidgetItem(_sval(feat['nom'], f"#{fid}"))
            it0.setFlags(it0.flags() & ~Qt.ItemIsEditable)
            it0.setData(Qt.UserRole, fid)
            table.setItem(i, 0, it0)

            it1 = QTableWidgetItem('Regard' if role == 'regard' else 'Tabouret')
            it1.setFlags(it1.flags() & ~Qt.ItemIsEditable)
            it1.setData(Qt.UserRole, fid)
            table.setItem(i, 1, it1)

            table.setItem(i, 2, self._make_item(tn, 3, fid, 'tn'))
            table.setItem(i, 3, self._make_item(profondeur, 2, fid, 'profondeur'))
            table.setItem(i, 4, self._make_item(fe, 3, fid, fe_field))

            it_cum = QTableWidgetItem(_fmt(cum, 2))
            it_cum.setFlags(it_cum.flags() & ~Qt.ItemIsEditable)
            it_cum.setForeground(_COLOR_DERIVED)
            it_cum.setData(Qt.UserRole, fid)
            table.setItem(i, 5, it_cum)

        n = len(self._chain_nodes)
        for i in range(n - 1):
            longueur = self._chain_segments[i]
            fe_a, fe_b = fe_values[i], fe_values[i + 1]
            pente = None
            if fe_a is not None and fe_b is not None and longueur:
                pente = (fe_a - fe_b) / longueur * 100
            it_pente = QTableWidgetItem(_fmt(pente, 3))
            it_pente.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            it_pente.setFlags(it_pente.flags() | Qt.ItemIsEditable)
            it_pente.setForeground(_COLOR_MISSING if pente is None else QColor(0, 0, 0))
            table.setItem(i, 6, it_pente)

        it_last = QTableWidgetItem('')
        it_last.setFlags(it_last.flags() & ~Qt.ItemIsEditable)
        table.setItem(n - 1, 6, it_last)

        table.blockSignals(False)
        table.resizeColumnsToContents()

        self.chain_profile.set_data(profile_data)

    def _handle_chain_edit(self, item):
        if self._updating or not self._chain_nodes:
            return
        row, col = item.row(), item.column()
        if row >= len(self._chain_nodes):
            return

        if col == 6:
            self._chain_edit_pente(row, item)
            return
        if col not in (2, 3, 4):
            return

        role, fid = self._chain_nodes[row]
        fname = item.data(Qt.UserRole + 1)
        decimals = item.data(Qt.UserRole + 2)
        value = _parse_num(item.text())
        self._updating = True
        item.setText(_fmt(value, decimals))
        item.setForeground(_COLOR_MISSING if value is None else QColor(0, 0, 0))
        self._updating = False

        layer = self.couches[self.reseau][role]
        self._write_attr(layer, fid, fname, value, role=role)
        self._refresh_after_write(role, fid, fname, value)
        self._chain_derive_third(role, fid, fname, value)

        self._chain_cascade_from(row)
        self._refresh_chain_table()
        self._update_status()

    def _chain_derive_third(self, role, fid, fname, value):
        """TN, Profondeur et FE sont liés par TN = Profondeur + FE : modifier l'un
        des trois recalcule toujours un des deux autres (Profondeur = valeur
        dérivée par défaut, sauf si c'est elle qu'on vient d'éditer)."""
        fe_field = _FE_FIELD[role]
        layer = self.couches[self.reseau][role]
        feat = layer.getFeature(fid)
        tn = _fnum(feat['tn'])
        fe = _fnum(feat[fe_field])

        if fname == fe_field:
            if tn is None:
                return
            new_prof = round(tn - value, 2) if value is not None else None
            self._write_attr(layer, fid, 'profondeur', new_prof, role=role)
            self._refresh_after_write(role, fid, 'profondeur', new_prof)
        elif fname == 'profondeur':
            if tn is None:
                return
            new_fe = round(tn - value, 3) if value is not None else None
            self._write_attr(layer, fid, fe_field, new_fe, role=role)
            self._refresh_after_write(role, fid, fe_field, new_fe)
        elif fname == 'tn':
            if fe is None:
                return
            new_prof = round(value - fe, 2) if value is not None else None
            self._write_attr(layer, fid, 'profondeur', new_prof, role=role)
            self._refresh_after_write(role, fid, 'profondeur', new_prof)

    def _chain_edit_pente(self, row, item):
        if row >= len(self._chain_nodes) - 1:
            self._updating = True
            item.setText('')
            self._updating = False
            return
        pente = _parse_num(item.text())
        self._updating = True
        item.setText(_fmt(pente, 3))
        self._updating = False
        if pente is None:
            return
        self._chain_cascade_from(row)
        self._refresh_chain_table()
        self._update_status()

    def _chain_cascade_from(self, start_row):
        """Recalcule le FE (et la profondeur si TN connu) des noeuds situés après
        `start_row`, tronçon par tronçon, à partir de la pente actuellement affichée
        pour chaque tronçon. S'arrête au premier tronçon dont la pente est inconnue."""
        if not self._chain_nodes:
            return
        self._chain_force_fe_mode()

        role0, fid0 = self._chain_nodes[start_row]
        fe_prev = self._get_fe(role0, fid0)
        if fe_prev is None:
            return

        for i in range(start_row, len(self._chain_nodes) - 1):
            pente_item = self.chain_table.item(i, 6)
            pente = _parse_num(pente_item.text()) if pente_item is not None else None
            if pente is None:
                break
            longueur = self._chain_segments[i]
            fe_next = fe_prev - (pente / 100.0) * longueur

            role_n, fid_n = self._chain_nodes[i + 1]
            layer_n = self.couches[self.reseau][role_n]
            fe_field_n = _FE_FIELD[role_n]
            fe_next_r = round(fe_next, 3)
            self._write_attr(layer_n, fid_n, fe_field_n, fe_next_r, role=role_n)
            self._refresh_after_write(role_n, fid_n, fe_field_n, fe_next_r)

            feat_n = layer_n.getFeature(fid_n)
            tn_n = _fnum(feat_n['tn'])
            if tn_n is not None:
                prof_n = round(tn_n - fe_next, 2)
                self._write_attr(layer_n, fid_n, 'profondeur', prof_n, role=role_n)
                self._refresh_after_write(role_n, fid_n, 'profondeur', prof_n)

            fe_prev = fe_next

    def _get_fe(self, role, fid):
        layer = self.couches[self.reseau][role]
        feat = layer.getFeature(fid)
        if not feat.isValid():
            return None
        return _fnum(feat[_FE_FIELD[role]])

    def _chain_cascade_pente(self, pente):
        """Applique `pente` (%) depuis le 1er noeud de la chaîne vers le dernier,
        en recalculant le FE (et la profondeur si TN connu) de chaque noeud suivant."""
        role0, fid0 = self._chain_nodes[0]
        layer0 = self.couches[self.reseau][role0]
        fe_prev = _fnum(layer0.getFeature(fid0)[_FE_FIELD[role0]])
        if fe_prev is None:
            self._chain_set_status(
                f"Le FE de {self.combo_regard1.currentText()} est inconnu — "
                "renseignez-le d'abord (dans le tableau ou l'onglet Regards).", 'error')
            return False

        for i in range(1, len(self._chain_nodes)):
            role, fid = self._chain_nodes[i]
            longueur = self._chain_segments[i - 1]
            fe_new = fe_prev - (pente / 100.0) * longueur
            layer = self.couches[self.reseau][role]
            fe_field = _FE_FIELD[role]
            self._write_attr(layer, fid, fe_field, round(fe_new, 3), role=role)

            feat = layer.getFeature(fid)
            tn = _fnum(feat['tn'])
            if tn is not None:
                self._write_attr(layer, fid, 'profondeur', round(tn - fe_new, 2), role=role)

            fe_prev = fe_new

        self._reload_all()
        self._refresh_chain_table()
        return True

    def _chain_apply_pente_imposee(self):
        if not self._chain_nodes:
            self._chain_set_status("Recherchez d'abord la chaîne.", 'error')
            return
        pente = _parse_num(self.chain_pente_input.text())
        if pente is None:
            self._chain_set_status(
                "Pente invalide — saisissez un nombre, ex : 0.5", 'error')
            return
        if self._chain_cascade_pente(pente):
            self._chain_set_status(
                f"✓ Pente de {pente:.3f} % appliquée depuis "
                f"{self.combo_regard1.currentText()}.", 'success')

    def _chain_apply_pente_calculee(self):
        if not self._chain_nodes or len(self._chain_nodes) < 2:
            self._chain_set_status("Recherchez d'abord la chaîne.", 'error')
            return
        role0, fid0 = self._chain_nodes[0]
        role1, fid1 = self._chain_nodes[-1]
        fe0 = _fnum(self.couches[self.reseau][role0].getFeature(fid0)[_FE_FIELD[role0]])
        fe1 = _fnum(self.couches[self.reseau][role1].getFeature(fid1)[_FE_FIELD[role1]])
        total = sum(self._chain_segments)
        if fe0 is None or fe1 is None or not total:
            self._chain_set_status(
                "Le FE du regard de départ et/ou d'arrivée est manquant "
                "(ou la longueur totale est nulle) — impossible de calculer la pente.",
                'error')
            return
        pente = (fe0 - fe1) / total * 100
        if self._chain_cascade_pente(pente):
            self._chain_set_status(
                f"✓ Pente calculée = {pente:.3f} % (sur {total:.1f} m), appliquée.",
                'success')

    def _chain_apply_profondeur_fixe(self):
        if not self._chain_nodes:
            self._chain_set_status("Recherchez d'abord la chaîne.", 'error')
            return
        prof = _parse_num(self.chain_prof_input.text())
        if prof is None:
            self._chain_set_status(
                "Profondeur invalide — saisissez un nombre, ex : 1.00", 'error')
            return

        n_skipped = 0
        for role, fid in self._chain_nodes:
            layer = self.couches[self.reseau][role]
            feat = layer.getFeature(fid)
            self._write_attr(layer, fid, 'profondeur', round(prof, 2), role=role)
            tn = _fnum(feat['tn'])
            if tn is not None:
                fe_field = _FE_FIELD[role]
                self._write_attr(layer, fid, fe_field, round(tn - prof, 3), role=role)
            else:
                n_skipped += 1

        self._reload_all()
        self._refresh_chain_table()
        msg = f"✓ Profondeur {prof:.2f} m appliquée à {len(self._chain_nodes)} ouvrage(s)."
        if n_skipped:
            msg += f" ({n_skipped} sans TN connu — FE non recalculé)"
        self._chain_set_status(msg, 'success')

    # ------------------------------------------------------------------ raccourcis clavier

    def keyPressEvent(self, event):
        if event.matches(QKeySequence.Undo):
            self._undo()
            return
        if event.matches(QKeySequence.Copy):
            self._copy_selection()
            return
        if event.matches(QKeySequence.Paste):
            self._paste_selection()
            return
        super().keyPressEvent(event)
