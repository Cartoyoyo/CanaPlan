# -*- coding: utf-8 -*-
from qgis.PyQt.QtCore import QSettings, Qt, QRectF
from qgis.PyQt.QtWidgets import (
    QDialog, QVBoxLayout, QGroupBox, QFormLayout,
    QComboBox, QSpinBox, QDoubleSpinBox, QDialogButtonBox, QTabWidget, QWidget,
    QCheckBox, QHBoxLayout, QLabel,
)
from qgis.PyQt.QtGui import QFont, QPainter, QColor, QPen, QBrush
from qgis.core import QgsProject, QgsWkbTypes, QgsSettings

from ..tools.stareau_values import materiaux_labels as _materiaux_labels

SKETCHES_PREFIX = "BET_HUMIDE/"
SETTINGS_KEY = SKETCHES_PREFIX + "default"

# Materiaux de conduite : liste partagee avec le Tableau de saisie et l'export
# StaR-Eau (tools/stareau_values.MATERIAUX_CONDUITE). Les materiaux de remblai
# ci-dessous en sont volontairement separes : ils ne sont pas des materiaux de
# canalisation et n'ont rien a faire dans une combo de conduite.
MATERIAUX = [""] + _materiaux_labels()

# Materiaux de remblai et de chaussee : lit de pose, enrobage, remblai,
# chaussees inferieure et superieure. Sans rapport avec les materiaux de
# canalisation ci-dessus, et hors du perimetre de l'export StaR-Eau.
MATERIAUX_REMBLAI = ["", "Sable", "2/6", "0/31.5", "Tout-venant",
                     "GB (Grave bitume)", "GC (Grave ciment)", "Enrobé"]

INITIAL_DEFAULTS = {
    "conduite_eu":      (200, "PVC"),
    "conduite_ep":      (315, "PVC"),
    "branchement_eu":   (160, "PVC"),
    "branchement_ep":   (160, "PVC"),
}

ROLES = {
    'conduite':    QgsWkbTypes.LineGeometry,
    'branchement': QgsWkbTypes.LineGeometry,
    'regard':      QgsWkbTypes.PointGeometry,
    'tabouret':    QgsWkbTypes.PointGeometry,
}

LABELS = {
    'conduite':    "Conduites",
    'branchement': "Branchements",
    'regard':      "Regards",
    'tabouret':    "Tabourets",
}


def get_default_params():
    """Retourne un dict {key: {'diametre': int, 'materiau': str}}."""
    s = QgsSettings()
    result = {}
    for key, (diam, mat) in INITIAL_DEFAULTS.items():
        result[key] = {
            "diametre":  s.value(f"{SETTINGS_KEY}/{key}_diametre", diam, int),
            "materiau":  s.value(f"{SETTINGS_KEY}/{key}_materiau", mat, str),
        }
    return result


def get_cubature_config():
    s = QgsSettings()
    p = "BET_HUMIDE/cubature"
    return {
        'ep_lit_pose': s.value(f"{p}/ep_lit_pose", 0.10, float),
        'largeur_conduite_eu': s.value(f"{p}/larg_cond_eu", 0.80, float),
        'largeur_conduite_ep': s.value(f"{p}/larg_cond_ep", 0.80, float),
        'largeur_branchement_eu': s.value(f"{p}/larg_branch_eu", 0.60, float),
        'largeur_branchement_ep': s.value(f"{p}/larg_branch_ep", 0.60, float),
        # remblai
        'ep_enrobage': s.value(f"{p}/ep_enrobage", 0.15, float),
        'materiau_lit_pose': s.value(f"{p}/materiau_lit_pose", "Sable", str),
        'materiau_enrobage': s.value(f"{p}/materiau_enrobage", "Sable", str),
        'materiau_remblai': s.value(f"{p}/materiau_remblai", "0/31.5", str),
        'chaussee_inf': s.value(f"{p}/chaussee_inf", False, bool),
        'ep_chaussee_inf': s.value(f"{p}/ep_chaussee_inf", 0.20, float),
        'materiau_chaussee_inf': s.value(f"{p}/materiau_chaussee_inf", "GB (Grave bitume)", str),
        'chaussee_sup': s.value(f"{p}/chaussee_sup", False, bool),
        'ep_chaussee_sup': s.value(f"{p}/ep_chaussee_sup", 0.08, float),
        'materiau_chaussee_sup': s.value(f"{p}/materiau_chaussee_sup", "Enrobé", str),
    }


class TrenchSchemaWidget(QWidget):
    """Widget de dessin dynamique pour la coupe de la tranchée."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumHeight(250)
        self.setMinimumWidth(350)
        self.data = {
            'mat_lit': '', 'mat_enr': '', 'mat_rem': '',
            'mat_ci': '', 'mat_cs': '',
            'show_inf': False, 'show_sup': False,
            'ep_enr': ''
        }

    def update_schema(self, data):
        self.data = data
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        w = self.width()
        h = self.height()

        margin_x = 20
        margin_y = 10
        draw_w = w - 2 * margin_x
        draw_h = h - 2 * margin_y

        weights = []
        if self.data.get('show_sup'):
            weights.append(('cs', 1.2, "Chaussée sup.", self.data.get('ep_cs', ''), self.data.get('mat_cs', '')))
        if self.data.get('show_inf'):
            weights.append(('ci', 1.5, "Chaussée inf.", self.data.get('ep_ci', ''), self.data.get('mat_ci', '')))

        weights.append(('rem', 2.5, "Remblai", "(var.)", self.data.get('mat_rem', '')))
        weights.append(('enr', 3, "Zone d'enrobage", self.data.get('ep_enr', ''), self.data.get('mat_enr', '')))
        weights.append(('lit', 1.2, "Lit de pose", self.data.get('ep_lit', ''), self.data.get('mat_lit', '')))

        total_weight = sum(weight for _, weight, _, _, _ in weights)
        if total_weight == 0:
            return

        current_y = margin_y

        def get_color(mat):
            mat_lower = mat.lower() if mat else ""
            if 'sable' in mat_lower: return QColor(245, 235, 175)
            if '2/6' in mat_lower: return QColor(210, 210, 210)
            if '0/31.5' in mat_lower or 'tout-venant' in mat_lower: return QColor(175, 175, 175)
            if 'gb' in mat_lower or 'bitume' in mat_lower: return QColor(100, 100, 100)
            if 'gc' in mat_lower or 'ciment' in mat_lower: return QColor(180, 180, 185)
            if 'enrobé' in mat_lower: return QColor(50, 50, 50)
            return QColor(220, 220, 220)

        original_font = painter.font()

        for layer_id, weight, label, ep_str, mat in weights:
            layer_h = (weight / total_weight) * draw_h
            rect = QRectF(margin_x, current_y, draw_w, layer_h)

            color = get_color(mat)
            painter.setBrush(QBrush(color))
            painter.setPen(QPen(Qt.black, 1))
            painter.drawRect(rect)

            lum = color.red() * 0.299 + color.green() * 0.587 + color.blue() * 0.114
            text_color = Qt.black if lum > 128 else Qt.white

            if layer_id == 'enr':
                diam = min(layer_h * 0.55, draw_w * 0.3)
                radius = diam / 2
                cx = margin_x + draw_w / 2
                cy = current_y + layer_h - radius

                painter.setBrush(QBrush(QColor(255, 255, 255)))
                painter.setPen(QPen(Qt.black, 2))
                painter.drawEllipse(int(cx - radius), int(cy - radius), int(radius * 2), int(radius * 2))

                dim_x = cx
                painter.setPen(QPen(text_color, 1, Qt.DashLine))
                painter.drawLine(int(dim_x), int(cy - radius), int(margin_x + draw_w - 10), int(cy - radius))

                arrow_x = margin_x + draw_w - 25
                painter.setPen(QPen(text_color, 1, Qt.SolidLine))
                painter.drawLine(int(arrow_x), int(current_y), int(arrow_x), int(cy - radius))
                painter.drawLine(int(arrow_x - 3), int(current_y), int(arrow_x + 3), int(current_y))
                painter.drawLine(int(arrow_x - 3), int(cy - radius), int(arrow_x + 3), int(cy - radius))

            painter.setPen(text_color)
            font = QFont(original_font)

            font.setBold(True)
            painter.setFont(font)
            text_rect_left = QRectF(margin_x + 10, current_y, 110, layer_h)
            painter.drawText(text_rect_left, int(Qt.AlignVCenter | Qt.AlignLeft), label)

            font.setBold(False)
            painter.setFont(font)

            if ep_str:
                if layer_id == 'enr':
                    text_rect_ep = QRectF(margin_x + 125, current_y, 60, (cy - radius) - current_y)
                else:
                    text_rect_ep = QRectF(margin_x + 125, current_y, 60, layer_h)
                painter.drawText(text_rect_ep, int(Qt.AlignVCenter | Qt.AlignLeft), ep_str)

            if layer_id == 'enr':
                text_rect_right = QRectF(margin_x + draw_w / 2 + 10, cy - radius, draw_w / 2 - 20, 2 * radius)
            else:
                text_rect_right = QRectF(margin_x + draw_w / 2 + 10, current_y, draw_w / 2 - 20, layer_h)
            painter.drawText(text_rect_right, int(Qt.AlignVCenter | Qt.AlignRight), mat)

            current_y += layer_h


class CubatureSchemaWidget(QWidget):
    """Widget de dessin dynamique pour la largeur de la tranchée."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumHeight(180)
        self.setMinimumWidth(350)
        self.val = 0.8
        self.label = "Conduite EU"

    def update_schema(self, val, label):
        self.val = val
        self.label = label
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        w = self.width()
        h = self.height()

        margin_x = 20
        margin_y = 30
        draw_w = w - 2 * margin_x
        draw_h = h - margin_y - 20

        trench_w = min(draw_w * 0.85, max(draw_w * 0.2, self.val * (draw_w / 2.0)))

        cx = w / 2
        trench_left = cx - trench_w / 2
        trench_right = cx + trench_w / 2
        trench_top = margin_y + 20
        trench_bottom = h - 20

        painter.setPen(Qt.NoPen)
        painter.setBrush(QBrush(QColor(185, 155, 115)))

        painter.drawRect(QRectF(margin_x, trench_top, trench_left - margin_x, trench_bottom - trench_top))
        painter.drawRect(QRectF(trench_right, trench_top, margin_x + draw_w - trench_right, trench_bottom - trench_top))

        painter.setPen(QPen(QColor(110, 80, 50), 2))
        painter.drawLine(int(margin_x), int(trench_top), int(trench_left), int(trench_top))
        painter.drawLine(int(trench_right), int(trench_top), int(margin_x + draw_w), int(trench_top))
        painter.drawLine(int(trench_left), int(trench_top), int(trench_left), int(trench_bottom))
        painter.drawLine(int(trench_right), int(trench_top), int(trench_right), int(trench_bottom))
        painter.drawLine(int(trench_left), int(trench_bottom), int(trench_right), int(trench_bottom))

        radius = min(trench_w * 0.3, (trench_bottom - trench_top) * 0.25)
        painter.setBrush(QBrush(QColor(240, 240, 240)))
        painter.setPen(QPen(Qt.black, 1))
        painter.drawEllipse(int(cx - radius), int(trench_bottom - radius * 2 - 5), int(radius * 2), int(radius * 2))

        cote_y = margin_y
        painter.setPen(QPen(Qt.black, 1))
        painter.drawLine(int(trench_left), int(cote_y), int(trench_right), int(cote_y))
        painter.drawLine(int(trench_left), int(cote_y - 5), int(trench_left), int(trench_top))
        painter.drawLine(int(trench_right), int(cote_y - 5), int(trench_right), int(trench_top))

        text = f"{self.val:.2f} m"
        font = painter.font()
        font.setBold(True)
        painter.setFont(font)
        fm = painter.fontMetrics()
        tw = fm.horizontalAdvance(text)

        text_bg = QRectF(cx - tw / 2 - 5, cote_y - 10, tw + 10, 20)
        painter.fillRect(text_bg, self.palette().window())

        painter.setPen(Qt.black)
        painter.drawText(text_bg, int(Qt.AlignCenter), text)


class NetworkSchemaWidget(QWidget):
    """Widget pour visualiser les conduites et branchements par défaut."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumHeight(130)
        self.setMinimumWidth(200)
        self.data = {
            'diam_cond': 200, 'mat_cond': 'PVC',
            'diam_branch': 160, 'mat_branch': 'PVC',
            'reseau_name': 'EU'
        }

    def update_schema(self, data):
        self.data = data
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        w = self.width()
        h = self.height()

        margin_x = 20
        margin_y = 10
        draw_w = w - 2 * margin_x
        draw_h = h - margin_y - 35

        def get_pipe_color(mat):
            mat_low = mat.lower() if mat else ""
            if 'pvc' in mat_low: return QColor(225, 120, 50)
            if 'fonte' in mat_low: return QColor(60, 60, 60)
            if 'beton' in mat_low or 'béton' in mat_low: return QColor(190, 190, 190)
            if 'pehd' in mat_low: return QColor(30, 30, 30)
            if 'acier' in mat_low: return QColor(110, 140, 160)
            if 'gres' in mat_low or 'grès' in mat_low: return QColor(160, 70, 40)
            return QColor(150, 150, 150)

        diam_c = self.data.get('diam_cond', 200)
        diam_b = self.data.get('diam_branch', 160)

        max_diam_val = max(diam_c, diam_b, 100)
        scale = (draw_h * 0.8) / max_diam_val

        r_c = diam_c * scale / 2
        r_b = diam_b * scale / 2

        cx_c = margin_x + draw_w * 0.3
        cy_c = margin_y + draw_h / 2

        cx_b = margin_x + draw_w * 0.7
        cy_b = margin_y + draw_h / 2

        painter.setPen(QPen(QColor(200, 200, 200), 1, Qt.DashLine))
        painter.drawLine(int(margin_x), int(cy_c + r_c + 5), int(margin_x + draw_w), int(cy_c + r_c + 5))

        painter.setBrush(QBrush(get_pipe_color(self.data.get('mat_cond', ''))))
        painter.setPen(QPen(Qt.black, 2))
        painter.drawEllipse(int(cx_c - r_c), int(cy_c - r_c), int(r_c * 2), int(r_c * 2))

        inner_r_c = max(2, r_c * 0.85)
        painter.setBrush(QBrush(QColor(255, 255, 255)))
        painter.setPen(QPen(Qt.black, 1))
        painter.drawEllipse(int(cx_c - inner_r_c), int(cy_c - inner_r_c), int(inner_r_c * 2), int(inner_r_c * 2))

        painter.setBrush(QBrush(get_pipe_color(self.data.get('mat_branch', ''))))
        painter.setPen(QPen(Qt.black, 2))
        painter.drawEllipse(int(cx_b - r_b), int(cy_b - r_b), int(r_b * 2), int(r_b * 2))

        inner_r_b = max(2, r_b * 0.85)
        painter.setBrush(QBrush(QColor(255, 255, 255)))
        painter.setPen(QPen(Qt.black, 1))
        painter.drawEllipse(int(cx_b - inner_r_b), int(cy_b - inner_r_b), int(inner_r_b * 2), int(inner_r_b * 2))

        font = painter.font()
        painter.setPen(Qt.black)

        font.setBold(True)
        painter.setFont(font)
        painter.drawText(QRectF(cx_c - 100, cy_c + r_c + 10, 200, 20), int(Qt.AlignCenter), f"Conduite: {diam_c} mm")
        font.setBold(False)
        painter.setFont(font)
        painter.drawText(QRectF(cx_c - 100, cy_c + r_c + 25, 200, 20), int(Qt.AlignCenter), self.data.get('mat_cond', ''))

        font.setBold(True)
        painter.setFont(font)
        painter.drawText(QRectF(cx_b - 100, cy_b + r_b + 10, 200, 20), int(Qt.AlignCenter), f"Branch.: {diam_b} mm")
        font.setBold(False)
        painter.setFont(font)
        painter.drawText(QRectF(cx_b - 100, cy_b + r_b + 25, 200, 20), int(Qt.AlignCenter), self.data.get('mat_branch', ''))


class ConfigDialog(QDialog):
    def __init__(self, iface, parent=None):
        super().__init__(parent or iface.mainWindow())
        self.iface = iface
        self.setWindowTitle("Configuration rapide")
        self.setMinimumWidth(450)

        self.combos = {}
        self._def_widgets = {}
        self._cub_widgets = {}
        self._remblai_widgets = {}
        self._remblai_mat = {}
        self._remblai_cb = {}
        self._network_schemas = {}
        self._build_ui()
        self._load_settings()

    def _build_ui(self):
        main_layout = QVBoxLayout(self)

        tabs = QTabWidget()

        # ── Onglet 1 : Réseau par défaut ────────────────────────────────
        tab_defauts = QWidget()
        defauts_layout = QVBoxLayout(tab_defauts)

        for reseau in ("EU", "EP"):
            group = QGroupBox(f"Réseau {reseau}")
            group_layout = QVBoxLayout()

            form = QFormLayout()
            for role in ("conduite", "branchement"):
                key = f"{role}_{reseau.lower()}"
                spin = QSpinBox()
                spin.setRange(0, 3000)
                spin.setSuffix(" mm")
                mat_combo = QComboBox()
                mat_combo.setEditable(True)
                mat_combo.addItems(MATERIAUX)
                self._def_widgets[key] = (spin, mat_combo)

                spin.valueChanged.connect(self._refresh_network_schemas)
                mat_combo.currentTextChanged.connect(self._refresh_network_schemas)

                form.addRow(f"{LABELS[role]} — Diamètre :", spin)
                form.addRow(f"{LABELS[role]} — Matériau :", mat_combo)

            group_layout.addLayout(form)

            schema = NetworkSchemaWidget()
            self._network_schemas[reseau] = schema
            group_layout.addWidget(schema)

            group.setLayout(group_layout)
            defauts_layout.addWidget(group)

        defauts_layout.addStretch()
        tabs.addTab(tab_defauts, "Réseau par défaut")

        # ── Onglet 2 : Couches ──────────────────────────────────────────
        tab_couches = QWidget()
        couches_layout = QVBoxLayout(tab_couches)

        for reseau in ("EU", "EP"):
            group = QGroupBox(f"Réseau {reseau}")
            form = QFormLayout()
            for role, geom_type in ROLES.items():
                combo = QComboBox()
                combo.addItem("-- non configuré --", None)
                self._populate_combo(combo, geom_type)
                key = f"{role}_{reseau.lower()}"
                self.combos[key] = combo
                form.addRow(f"{LABELS[role]} :", combo)
            group.setLayout(form)
            couches_layout.addWidget(group)

        couches_layout.addStretch()
        tabs.addTab(tab_couches, "Couches")

        # ── Onglet 3 : Cubature ──────────────────────────────────────────
        tab_cubature = QWidget()
        cub_layout = QVBoxLayout(tab_cubature)

        group_tranchee = QGroupBox("Paramètres de cubature de tranchées")
        form = QFormLayout()

        ep_lit = QDoubleSpinBox()
        ep_lit.setRange(0.0, 2.0)
        ep_lit.setDecimals(3)
        ep_lit.setSuffix(" m")
        ep_lit.setSingleStep(0.05)
        ep_lit.setValue(0.10)
        self._cub_widgets['ep_lit_pose'] = ep_lit
        form.addRow("Épaisseur lit de pose :", ep_lit)

        for key, label, default in [
            ('larg_cond_eu',    "Largeur tranchée Conduite EU :",    0.80),
            ('larg_cond_ep',    "Largeur tranchée Conduite EP :",    0.80),
            ('larg_branch_eu',  "Largeur tranchée Branchement EU :", 0.60),
            ('larg_branch_ep',  "Largeur tranchée Branchement EP :", 0.60),
        ]:
            spin = QDoubleSpinBox()
            spin.setRange(0.1, 5.0)
            spin.setDecimals(2)
            spin.setSuffix(" m")
            spin.setSingleStep(0.10)
            spin.setValue(default)
            self._cub_widgets[key] = spin
            spin.valueChanged.connect(self._refresh_cubature_schema)
            form.addRow(label, spin)

        group_tranchee.setLayout(form)
        cub_layout.addWidget(group_tranchee)

        schema_group = QGroupBox("Aperçu de la largeur")
        schema_layout = QVBoxLayout()

        schema_top_layout = QHBoxLayout()
        schema_top_layout.addWidget(QLabel("Visualiser la largeur pour :"))
        self._cubature_combo = QComboBox()
        self._cubature_combo.addItems([
            "Conduite EU", "Conduite EP", "Branchement EU", "Branchement EP"
        ])
        self._cubature_combo.currentIndexChanged.connect(self._refresh_cubature_schema)
        schema_top_layout.addWidget(self._cubature_combo)
        schema_top_layout.addStretch()
        schema_layout.addLayout(schema_top_layout)

        self._cubature_schema_widget = CubatureSchemaWidget()
        schema_layout.addWidget(self._cubature_schema_widget)
        schema_group.setLayout(schema_layout)
        cub_layout.addWidget(schema_group)

        self._cubature_mapping = {
            0: ('larg_cond_eu', "Conduite EU"),
            1: ('larg_cond_ep', "Conduite EP"),
            2: ('larg_branch_eu', "Branchement EU"),
            3: ('larg_branch_ep', "Branchement EP"),
        }
        self._refresh_cubature_schema()

        cub_layout.addStretch()
        tabs.addTab(tab_cubature, "Cubature")

        # ── Onglet 4 : Remblai ──────────────────────────────────────────
        tab_remblai = QWidget()
        remblai_layout = QVBoxLayout(tab_remblai)

        self._schema_widget = TrenchSchemaWidget()
        remblai_layout.addWidget(self._schema_widget)

        group_remblai = QGroupBox("Paramètres de remblai et chaussée")
        form_remblai = QFormLayout()

        mat_lit = QComboBox()
        mat_lit.setEditable(True)
        mat_lit.addItems(MATERIAUX_REMBLAI)
        self._remblai_mat['materiau_lit_pose'] = mat_lit
        form_remblai.addRow("Matériau lit de pose :", mat_lit)

        ep_enrobage = QDoubleSpinBox()
        ep_enrobage.setRange(0.0, 1.0)
        ep_enrobage.setDecimals(2)
        ep_enrobage.setSuffix(" m")
        ep_enrobage.setSingleStep(0.05)
        ep_enrobage.setValue(0.15)
        self._remblai_widgets['ep_enrobage'] = ep_enrobage
        mat_enrobage = QComboBox()
        mat_enrobage.setEditable(True)
        mat_enrobage.addItems(MATERIAUX_REMBLAI)
        self._remblai_mat['materiau_enrobage'] = mat_enrobage
        row_enr = QHBoxLayout()
        row_enr.addWidget(ep_enrobage)
        row_enr.addWidget(mat_enrobage)
        form_remblai.addRow("Enrobage (ép. + mat.) :", row_enr)

        mat_remblai = QComboBox()
        mat_remblai.setEditable(True)
        mat_remblai.addItems(MATERIAUX_REMBLAI)
        self._remblai_mat['materiau_remblai'] = mat_remblai
        form_remblai.addRow("Matériau remblai :", mat_remblai)

        cb_inf = QCheckBox("Partie inférieure chaussée")
        self._remblai_cb['chaussee_inf'] = cb_inf
        ep_inf = QDoubleSpinBox()
        ep_inf.setRange(0.0, 1.0)
        ep_inf.setDecimals(2)
        ep_inf.setSuffix(" m")
        ep_inf.setSingleStep(0.05)
        ep_inf.setValue(0.20)
        ep_inf.setEnabled(False)
        self._remblai_widgets['ep_chaussee_inf'] = ep_inf
        mat_inf = QComboBox()
        mat_inf.setEditable(True)
        mat_inf.addItems(MATERIAUX_REMBLAI)
        mat_inf.setEnabled(False)
        self._remblai_mat['materiau_chaussee_inf'] = mat_inf
        cb_inf.toggled.connect(ep_inf.setEnabled)
        cb_inf.toggled.connect(mat_inf.setEnabled)
        form_remblai.addRow(cb_inf)
        row_inf = QHBoxLayout()
        row_inf.addWidget(ep_inf)
        row_inf.addWidget(mat_inf)
        form_remblai.addRow("Ép. + matériau :", row_inf)

        cb_sup = QCheckBox("Partie supérieure chaussée")
        self._remblai_cb['chaussee_sup'] = cb_sup
        ep_sup = QDoubleSpinBox()
        ep_sup.setRange(0.0, 0.50)
        ep_sup.setDecimals(2)
        ep_sup.setSuffix(" m")
        ep_sup.setSingleStep(0.01)
        ep_sup.setValue(0.08)
        ep_sup.setEnabled(False)
        self._remblai_widgets['ep_chaussee_sup'] = ep_sup
        mat_sup = QComboBox()
        mat_sup.setEditable(True)
        mat_sup.addItems(MATERIAUX_REMBLAI)
        mat_sup.setEnabled(False)
        self._remblai_mat['materiau_chaussee_sup'] = mat_sup
        cb_sup.toggled.connect(ep_sup.setEnabled)
        cb_sup.toggled.connect(mat_sup.setEnabled)
        form_remblai.addRow(cb_sup)
        row_sup = QHBoxLayout()
        row_sup.addWidget(ep_sup)
        row_sup.addWidget(mat_sup)
        form_remblai.addRow("Ép. + matériau :", row_sup)

        group_remblai.setLayout(form_remblai)
        remblai_layout.addWidget(group_remblai)
        remblai_layout.addStretch()

        for w in list(self._remblai_mat.values()) + list(self._remblai_widgets.values()) + list(self._remblai_cb.values()):
            if hasattr(w, 'currentTextChanged'):
                w.currentTextChanged.connect(self._refresh_schema)
            elif hasattr(w, 'valueChanged'):
                w.valueChanged.connect(self._refresh_schema)
            elif hasattr(w, 'toggled'):
                w.toggled.connect(self._refresh_schema)

        if 'ep_lit_pose' in self._cub_widgets:
            self._cub_widgets['ep_lit_pose'].valueChanged.connect(self._refresh_schema)

        self._refresh_schema()

        tabs.addTab(tab_remblai, "Remblai")

        main_layout.addWidget(tabs)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self._save_and_accept)
        buttons.rejected.connect(self.reject)
        main_layout.addWidget(buttons)

        self._refresh_network_schemas()

    def _refresh_network_schemas(self):
        if not hasattr(self, '_network_schemas'):
            return

        for reseau in ("EU", "EP"):
            if reseau not in self._network_schemas:
                continue

            key_c = f"conduite_{reseau.lower()}"
            key_b = f"branchement_{reseau.lower()}"

            spin_c, mat_c = self._def_widgets.get(key_c, (None, None))
            spin_b, mat_b = self._def_widgets.get(key_b, (None, None))

            diam_c = spin_c.value() if spin_c else 200
            mat_c_str = mat_c.currentText() if mat_c else "PVC"

            diam_b = spin_b.value() if spin_b else 160
            mat_b_str = mat_b.currentText() if mat_b else "PVC"

            self._network_schemas[reseau].update_schema({
                'diam_cond': diam_c, 'mat_cond': mat_c_str,
                'diam_branch': diam_b, 'mat_branch': mat_b_str,
                'reseau_name': reseau
            })

    def _refresh_cubature_schema(self):
        if not hasattr(self, '_cubature_schema_widget'):
            return
        idx = self._cubature_combo.currentIndex()
        key, label = self._cubature_mapping.get(idx, ('larg_cond_eu', "Conduite EU"))

        spin = self._cub_widgets.get(key)
        val = spin.value() if spin else 0.8

        self._cubature_schema_widget.update_schema(val, label)

    def _refresh_schema(self):
        lit = self._remblai_mat.get('materiau_lit_pose')
        enr = self._remblai_mat.get('materiau_enrobage')
        rem = self._remblai_mat.get('materiau_remblai')
        ch_inf = self._remblai_mat.get('materiau_chaussee_inf')
        ch_sup = self._remblai_mat.get('materiau_chaussee_sup')
        cb_inf = self._remblai_cb.get('chaussee_inf')
        cb_sup = self._remblai_cb.get('chaussee_sup')

        def _txt(combo, fallback):
            if combo is None:
                return fallback
            t = combo.currentText().strip()
            return t if t else fallback

        show_inf = cb_inf.isChecked() if cb_inf else False
        show_sup = cb_sup.isChecked() if cb_sup else False

        ep_enr = self._remblai_widgets.get('ep_enrobage')
        ep_val = f"{ep_enr.value():.2f} m" if ep_enr else "0.15 m"

        ep_ci = self._remblai_widgets.get('ep_chaussee_inf')
        ep_ci_val = f"{ep_ci.value():.2f} m" if ep_ci else "0.20 m"

        ep_cs = self._remblai_widgets.get('ep_chaussee_sup')
        ep_cs_val = f"{ep_cs.value():.2f} m" if ep_cs else "0.08 m"

        ep_lit = self._cub_widgets.get('ep_lit_pose')
        ep_lit_val = f"{ep_lit.value():.2f} m" if ep_lit else "0.10 m"

        data = {
            'mat_lit': _txt(lit, "Sable"),
            'mat_enr': _txt(enr, "Sable"),
            'mat_rem': _txt(rem, "0/31.5"),
            'mat_ci': _txt(ch_inf, "GB/GC"),
            'mat_cs': _txt(ch_sup, "Enrobé"),
            'show_inf': show_inf,
            'show_sup': show_sup,
            'ep_enr': ep_val,
            'ep_ci': ep_ci_val,
            'ep_cs': ep_cs_val,
            'ep_lit': ep_lit_val
        }

        if hasattr(self, '_schema_widget'):
            self._schema_widget.update_schema(data)

    def _populate_combo(self, combo, geom_type):
        for layer in QgsProject.instance().mapLayers().values():
            if not hasattr(layer, 'geometryType'):
                continue
            if layer.geometryType() == geom_type:
                combo.addItem(layer.name(), layer.id())

    def _load_settings(self):
        s = QSettings()
        for key, combo in self.combos.items():
            saved_id = s.value(SKETCHES_PREFIX + f"couche_{key}")
            if saved_id:
                idx = combo.findData(saved_id)
                if idx >= 0:
                    combo.setCurrentIndex(idx)

        gs = QgsSettings()
        for key, (spin, mat_combo) in self._def_widgets.items():
            init_diam, init_mat = INITIAL_DEFAULTS.get(key, (0, ""))
            diam = gs.value(f"{SETTINGS_KEY}/{key}_diametre", init_diam, int)
            mat  = gs.value(f"{SETTINGS_KEY}/{key}_materiau", init_mat, str)
            spin.setValue(diam)
            if mat:
                idx = mat_combo.findText(mat)
                if idx >= 0:
                    mat_combo.setCurrentIndex(idx)
                else:
                    mat_combo.setCurrentText(mat)

        for key, widget in self._cub_widgets.items():
            defaults = {
                'ep_lit_pose': 0.10, 'larg_cond_eu': 0.80, 'larg_cond_ep': 0.80,
                'larg_branch_eu': 0.60, 'larg_branch_ep': 0.60,
            }
            val = gs.value(f"BET_HUMIDE/cubature/{key}", defaults.get(key, 0), float)
            widget.setValue(val)

        p = "BET_HUMIDE/cubature"
        for key, widget in self._remblai_widgets.items():
            defaults = {
                'ep_enrobage': 0.15, 'ep_chaussee_inf': 0.20, 'ep_chaussee_sup': 0.08,
            }
            val = gs.value(f"{p}/{key}", defaults.get(key, 0), float)
            widget.setValue(val)
        mat_defaults = {
            'materiau_lit_pose': "Sable",
            'materiau_enrobage': "Sable",
            'materiau_remblai': "0/31.5",
            'materiau_chaussee_inf': "GB (Grave bitume)",
            'materiau_chaussee_sup': "Enrobé",
        }
        for key, widget in self._remblai_mat.items():
            mat = gs.value(f"{p}/{key}", mat_defaults.get(key, ""), str)
            if mat:
                idx = widget.findText(mat)
                if idx >= 0:
                    widget.setCurrentIndex(idx)
                else:
                    widget.setCurrentText(mat)
        for key, widget in self._remblai_cb.items():
            defaults = {'chaussee_inf': False, 'chaussee_sup': False}
            widget.setChecked(gs.value(f"{p}/{key}", defaults.get(key, False), bool))

    def _save_and_accept(self):
        s = QSettings()
        for key, combo in self.combos.items():
            layer_id = combo.currentData()
            if layer_id:
                s.setValue(SKETCHES_PREFIX + f"couche_{key}", layer_id)
            else:
                s.remove(SKETCHES_PREFIX + f"couche_{key}")

        gs = QgsSettings()
        for key, (spin, mat_combo) in self._def_widgets.items():
            gs.setValue(f"{SETTINGS_KEY}/{key}_diametre", spin.value())
            gs.setValue(f"{SETTINGS_KEY}/{key}_materiau", mat_combo.currentText())

        for key, widget in self._cub_widgets.items():
            gs.setValue(f"BET_HUMIDE/cubature/{key}", widget.value())

        p = "BET_HUMIDE/cubature"
        for key, widget in self._remblai_widgets.items():
            gs.setValue(f"{p}/{key}", widget.value())
        for key, widget in self._remblai_mat.items():
            gs.setValue(f"{p}/{key}", widget.currentText())
        for key, widget in self._remblai_cb.items():
            gs.setValue(f"{p}/{key}", widget.isChecked())

        self.accept()
