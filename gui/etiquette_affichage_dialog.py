# gui/etiquette_affichage_dialog.py

from qgis.PyQt.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QGridLayout,
    QGroupBox, QCheckBox, QDialogButtonBox, QLabel,
    QPushButton, QTabWidget, QWidget,
)
from qgis.PyQt.QtGui import QFont, QColor
from qgis.PyQt.QtCore import Qt

_ROLES   = ('regard', 'tabouret', 'conduite', 'branchement')
_RESEAUX = ('EU', 'EP')

_ROLE_LABELS = {
    'regard':      'Regards',
    'tabouret':    'Tabourets',
    'conduite':    'Conduites',
    'branchement': 'Branchements',
}

# Champs disponibles par rôle : (clé, libellé affiché)
ROLE_FIELDS_AVAIL = {
    'regard': [
        ('nom',        'Nom'),
        ('tn',         'TN (m NGF)'),
        ('fe_radier',  'FE radier (m NGF)'),
        ('profondeur', 'Profondeur (m)'),
    ],
    'tabouret': [
        ('nom',        'Nom'),
        ('tn',         'TN (m NGF)'),
        ('fe_entree',  'FE entrée (m NGF)'),
        ('profondeur', 'Profondeur (m)'),
    ],
    'conduite': [
        ('materiau',  'Matériau'),
        ('diametre',  'Diamètre (mm)'),
        ('longueur',  'Longueur (m)'),
        ('pente',     'Pente (%)'),
    ],
    'branchement': [
        ('materiau',    'Matériau'),
        ('diametre',    'Diamètre (mm)'),
        ('longueur',    'Longueur (m)'),
        ('pente',       'Pente (%)'),
        ('cote_piquage','Cote piquage (m NGF)'),
    ],
}

# Préférences par défaut : tout visible, tous les champs
DEFAULT_FIELDS = {
    role: {f: True for f, _ in fields}
    for role, fields in ROLE_FIELDS_AVAIL.items()
}
DEFAULT_VISIBILITY = {
    reseau: {role: True for role in _ROLES}
    for reseau in _RESEAUX
}


def prefs_from_dict(d):
    """Reconstruit des prefs complètes depuis un dict partiel (compatibilité)."""
    # Ancien format : {reseau: {role: bool}} → migrer vers nouveau format
    if d and 'EU' in d and isinstance(d.get('EU'), dict) and 'visibility' not in d:
        visibility = {r: dict(d.get(r, {})) for r in _RESEAUX}
        for r in _RESEAUX:
            for role in _ROLES:
                visibility[r].setdefault(role, True)
        return {'visibility': visibility, 'fields': _copy_default_fields()}

    prefs = {
        'visibility': {r: {role: True for role in _ROLES} for r in _RESEAUX},
        'fields':     _copy_default_fields(),
    }
    if not d:
        return prefs

    vis = d.get('visibility', {})
    for reseau in _RESEAUX:
        for role in _ROLES:
            try:
                prefs['visibility'][reseau][role] = bool(vis[reseau][role])
            except (KeyError, TypeError):
                pass

    flds = d.get('fields', {})
    for role, avail in ROLE_FIELDS_AVAIL.items():
        for f, _ in avail:
            try:
                prefs['fields'][role][f] = bool(flds[role][f])
            except (KeyError, TypeError):
                pass

    return prefs


def _copy_default_fields():
    return {role: dict(fields) for role, fields in DEFAULT_FIELDS.items()}


class EtiquetteAffichageDialog(QDialog):

    def __init__(self, prefs=None, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Gestion de l'affichage des étiquettes")
        self.setMinimumWidth(480)
        self._prefs = prefs_from_dict(prefs)
        self._vis_checks  = {}   # (reseau, role) → QCheckBox
        self._field_checks = {}  # (role, field)  → QCheckBox
        self._build_ui()

    # ------------------------------------------------------------------ UI

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(10)

        # ── Titre ────────────────────────────────────────────────────────
        title = QLabel("Visibilité et contenu des étiquettes")
        f = QFont(); f.setBold(True); f.setPointSize(10)
        title.setFont(f)
        layout.addWidget(title)

        # ── Section 1 : Visibilité ────────────────────────────────────────
        grp_vis = QGroupBox("Visibilité par réseau et par type")
        grid = QGridLayout(grp_vis)
        grid.setSpacing(6)

        # En-têtes colonnes
        for col, role in enumerate(_ROLES):
            lbl = QLabel(_ROLE_LABELS[role])
            lbl.setAlignment(Qt.AlignCenter)
            f2 = QFont(); f2.setBold(True)
            lbl.setFont(f2)
            grid.addWidget(lbl, 0, col + 1)

        # Lignes EU / EP
        for row, reseau in enumerate(_RESEAUX):
            color = "#cc0000" if reseau == "EU" else "#0000cc"
            lbl = QLabel(f"<b><font color='{color}'>■ {reseau}</font></b>")
            grid.addWidget(lbl, row + 1, 0)
            for col, role in enumerate(_ROLES):
                cb = QCheckBox()
                cb.setChecked(self._prefs['visibility'][reseau][role])
                cb.setToolTip(f"Étiquettes {_ROLE_LABELS[role]} – {reseau}")
                self._vis_checks[(reseau, role)] = cb
                grid.addWidget(cb, row + 1, col + 1, alignment=Qt.AlignCenter)

        # Boutons rapides visibilité
        btn_row = QHBoxLayout()
        for label, state in [("Tout afficher", True), ("Tout masquer", False)]:
            btn = QPushButton(label)
            btn.clicked.connect(lambda _, s=state: self._set_all_vis(s))
            btn_row.addWidget(btn)
        btn_row.addStretch()
        vis_col = QVBoxLayout()
        vis_col.addWidget(grp_vis)
        vis_col.addLayout(btn_row)
        layout.addLayout(vis_col)

        # ── Section 2 : Contenu des étiquettes ───────────────────────────
        grp_fields = QGroupBox("Informations affichées dans les étiquettes")
        tab_layout = QVBoxLayout(grp_fields)

        tabs = QTabWidget()
        for role in _ROLES:
            tab = QWidget()
            vbox = QVBoxLayout(tab)
            vbox.setSpacing(4)
            avail = ROLE_FIELDS_AVAIL[role]
            for field, label in avail:
                cb = QCheckBox(label)
                cb.setChecked(self._prefs['fields'][role].get(field, True))
                self._field_checks[(role, field)] = cb
                vbox.addWidget(cb)
            vbox.addStretch()

            # Boutons rapides par onglet
            row2 = QHBoxLayout()
            for lbl2, st2 in [("Tout", True), ("Aucun", False)]:
                b = QPushButton(lbl2)
                b.setFixedWidth(55)
                b.clicked.connect(lambda _, r=role, s=st2: self._set_role_fields(r, s))
                row2.addWidget(b)
            row2.addStretch()
            vbox.addLayout(row2)

            tabs.addTab(tab, _ROLE_LABELS[role])

        tab_layout.addWidget(tabs)
        layout.addWidget(grp_fields)

        # ── Boutons OK / Annuler ──────────────────────────────────────────
        btns = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        btns.accepted.connect(self.accept)
        btns.rejected.connect(self.reject)
        layout.addWidget(btns)

    # ------------------------------------------------------------------ slots

    def _set_all_vis(self, state):
        for cb in self._vis_checks.values():
            cb.setChecked(state)

    def _set_role_fields(self, role, state):
        for (r, f), cb in self._field_checks.items():
            if r == role:
                cb.setChecked(state)

    # ------------------------------------------------------------------ résultat

    def get_prefs(self):
        return {
            'visibility': {
                reseau: {
                    role: self._vis_checks[(reseau, role)].isChecked()
                    for role in _ROLES
                }
                for reseau in _RESEAUX
            },
            'fields': {
                role: {
                    field: self._field_checks[(role, field)].isChecked()
                    for field, _ in ROLE_FIELDS_AVAIL[role]
                }
                for role in _ROLES
            },
        }
