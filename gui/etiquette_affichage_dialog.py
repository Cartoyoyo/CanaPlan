# gui/etiquette_affichage_dialog.py

from qgis.PyQt.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QGridLayout,
    QGroupBox, QCheckBox, QDialogButtonBox, QLabel,
    QPushButton, QTabWidget, QWidget,
)
from qgis.PyQt.QtGui import QFont, QColor
from qgis.PyQt.QtCore import Qt

from ..tools import i18n
from ..tools import errlog

_ROLES   = ('regard', 'tabouret', 'conduite', 'branchement')
_RESEAUX = ('EU', 'EP')

# Clés i18n, traduites à l'affichage
_ROLE_LABELS = {
    'regard':      'qc_regards',
    'tabouret':    'qc_tabourets',
    'conduite':    'qc_conduites',
    'branchement': 'qc_branchements',
}

# Champs disponibles par rôle : (clé, libellé affiché)
ROLE_FIELDS_AVAIL = {
    'regard': [
        ('nom',        'col_nom'),
        ('tn',         'col_tn'),
        ('fe_radier',  'col_fe_radier'),
        ('profondeur', 'col_profondeur'),
    ],
    'tabouret': [
        ('nom',        'col_nom'),
        ('tn',         'col_tn'),
        ('fe_entree',  'col_fe_entree'),
        ('profondeur', 'col_profondeur'),
    ],
    'conduite': [
        ('materiau',  'col_materiau'),
        ('diametre',  'col_diametre'),
        ('longueur',  'col_longueur'),
        ('pente',     'col_pente'),
    ],
    'branchement': [
        ('materiau',    'col_materiau'),
        ('diametre',    'col_diametre'),
        ('longueur',    'col_longueur'),
        ('pente',       'col_pente'),
        ('cote_piquage','col_cote_piquage'),
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
            except (KeyError, TypeError) as _err:
                errlog.ignored(_err, "etiquette_affichage_dialog.prefs_from_dict:87")

    flds = d.get('fields', {})
    for role, avail in ROLE_FIELDS_AVAIL.items():
        for f, _ in avail:
            try:
                prefs['fields'][role][f] = bool(flds[role][f])
            except (KeyError, TypeError) as _err:
                errlog.ignored(_err, "etiquette_affichage_dialog.prefs_from_dict:95")

    return prefs


def _copy_default_fields():
    return {role: dict(fields) for role, fields in DEFAULT_FIELDS.items()}


class EtiquetteAffichageDialog(QDialog):

    def __init__(self, prefs=None, parent=None):
        super().__init__(parent)
        self.setWindowTitle(i18n.tr('ea_titre'))
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
        title = QLabel(i18n.tr('ea_visibilite_contenu'))
        f = QFont(); f.setBold(True); f.setPointSize(10)
        title.setFont(f)
        layout.addWidget(title)

        # ── Section 1 : Visibilité ────────────────────────────────────────
        grp_vis = QGroupBox(i18n.tr('ea_visibilite_reseau'))
        grid = QGridLayout(grp_vis)
        grid.setSpacing(6)

        # En-têtes colonnes
        for col, role in enumerate(_ROLES):
            lbl = QLabel(i18n.tr(_ROLE_LABELS[role]))
            lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
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
                cb.setToolTip(i18n.tr('ea_etiquettes_role', role=i18n.tr(_ROLE_LABELS[role]),
                                       reseau=reseau))
                self._vis_checks[(reseau, role)] = cb
                grid.addWidget(cb, row + 1, col + 1, alignment=Qt.AlignmentFlag.AlignCenter)

        # Boutons rapides visibilité
        btn_row = QHBoxLayout()
        for cle, state in [('ea_tout_afficher', True),
                           ('ea_tout_masquer', False)]:
            btn = QPushButton(i18n.tr(cle))
            btn.clicked.connect(lambda _, s=state: self._set_all_vis(s))
            btn_row.addWidget(btn)
        btn_row.addStretch()
        vis_col = QVBoxLayout()
        vis_col.addWidget(grp_vis)
        vis_col.addLayout(btn_row)
        layout.addLayout(vis_col)

        # ── Section 2 : Contenu des étiquettes ───────────────────────────
        grp_fields = QGroupBox(i18n.tr('ea_infos_affichees'))
        tab_layout = QVBoxLayout(grp_fields)

        tabs = QTabWidget()
        for role in _ROLES:
            tab = QWidget()
            vbox = QVBoxLayout(tab)
            vbox.setSpacing(4)
            avail = ROLE_FIELDS_AVAIL[role]
            for field, cle_label in avail:
                cb = QCheckBox(i18n.tr(cle_label))
                cb.setChecked(self._prefs['fields'][role].get(field, True))
                self._field_checks[(role, field)] = cb
                vbox.addWidget(cb)
            vbox.addStretch()

            # Boutons rapides par onglet
            row2 = QHBoxLayout()
            for cle2, st2 in [('ea_tout', True), ('ea_aucun', False)]:
                b = QPushButton(i18n.tr(cle2))
                b.setFixedWidth(55)
                b.clicked.connect(lambda _, r=role, s=st2: self._set_role_fields(r, s))
                row2.addWidget(b)
            row2.addStretch()
            vbox.addLayout(row2)

            tabs.addTab(tab, i18n.tr(_ROLE_LABELS[role]))

        tab_layout.addWidget(tabs)
        layout.addWidget(grp_fields)

        # ── Boutons OK / Annuler ──────────────────────────────────────────
        btns = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
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
