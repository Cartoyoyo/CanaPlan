# gui/coupe_transversale_dialog.py

import math
import datetime

from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure
import matplotlib.patches as mpatches

from qgis.PyQt.QtCore import Qt
from qgis.PyQt.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QPushButton,
    QComboBox, QLabel, QFileDialog, QSizePolicy,
)
from qgis.core import QgsProject


# ------------------------------------------------------------------ couleurs

MATERIAU_CONDUIT_COLORS = {
    'PVC':    '#4fc3f7',
    'Fonte':  '#90a4ae',
    'Beton':  '#b0bec5',
    'PEHD':   '#a5d6a7',
    'Acier':  '#ce93d8',
    'Gres':   '#ffcc80',
    '':       '#e0e0e0',
}

MATERIAU_REMBLAI_COLORS = {
    'Sable':              '#fff9c4',
    '2/6':               '#ffcc80',
    '0/31.5':            '#bcaaa4',
    'Tout-venant':       '#d7ccc8',
    'GB (Grave bitume)': '#546e7a',
    'GC (Grave ciment)': '#90a4ae',
    'Enrobé':            '#424242',
    '':                  '#f5f5f5',
}

RESEAU_EDGE_COLORS = {
    'EU': '#c62828',
    'EP': '#1565c0',
}

# ------------------------------------------------------------------ formats papier (mm, portrait)

PAPER_SIZES = {
    'A4 portrait':  (210, 297),
    'A4 paysage':   (297, 210),
    'A3 portrait':  (297, 420),
    'A3 paysage':   (420, 297),
}

_MARGIN_MM    = 10
_CARTOUCHE_MM = 18
_ANNOT_RESERVE_M = 1.4   # espace réservé à droite pour les cotes

_NICE_SCALES = [10, 20, 25, 50, 100, 200, 500, 1000, 2000, 5000]


def _nice_scale(raw):
    for s in _NICE_SCALES:
        if s >= raw:
            return s
    return int(math.ceil(raw / 1000) * 1000)


# ------------------------------------------------------------------ bornes de tranchée

def _trench_bounds(crossings):
    """Borne gauche/droite de chaque tranchée.

    La frontière entre deux conduites adjacentes est au milieu des bords
    extérieurs de leurs cylindres.
    """
    n      = len(crossings)
    bounds = []
    for i, c in enumerate(crossings):
        x_left = (c['x'] - c['width'] / 2 if i == 0
                  else (crossings[i-1]['x'] + crossings[i-1]['diam_m'] / 2
                        + c['x'] - c['diam_m'] / 2) / 2.0)
        x_right = (c['x'] + c['width'] / 2 if i == n - 1
                   else (c['x'] + c['diam_m'] / 2
                         + crossings[i+1]['x'] - crossings[i+1]['diam_m'] / 2) / 2.0)
        bounds.append((x_left, x_right))
    return bounds


# ------------------------------------------------------------------ pile de couches

def _layer_stack(config, fe, diam_m, tn):
    """Couches de bas en haut : (y_bas, y_haut, nom, épaisseur, matériau)."""
    ep_lit = config.get('ep_lit_pose', 0.10)
    ep_enr = config.get('ep_enrobage', 0.15)
    ch_inf = config.get('chaussee_inf', False)
    ep_inf = config.get('ep_chaussee_inf', 0.20)
    ch_sup = config.get('chaussee_sup', False)
    ep_sup = config.get('ep_chaussee_sup', 0.08)

    mat_lit = config.get('materiau_lit_pose', 'Sable')
    mat_enr = config.get('materiau_enrobage', 'Sable')
    mat_rem = config.get('materiau_remblai', '0/31.5')
    mat_ci  = config.get('materiau_chaussee_inf', 'GB (Grave bitume)')
    mat_cs  = config.get('materiau_chaussee_sup', 'Enrobé')

    y_bot     = fe - ep_lit
    y_enr_top = fe + diam_m + ep_enr

    y_fill_top = tn
    if ch_sup: y_fill_top -= ep_sup
    if ch_inf: y_fill_top -= ep_inf

    layers = [
        (y_bot,    fe,        "Lit de pose", ep_lit,           mat_lit),
        (fe,       y_enr_top, "Enrobage",   diam_m + ep_enr,   mat_enr),
    ]
    rem_h = y_fill_top - y_enr_top
    if rem_h > 0.005:
        layers.append((y_enr_top, y_fill_top, "Remblai", rem_h, mat_rem))
    if ch_inf:
        y_ci = tn - (ep_sup if ch_sup else 0) - ep_inf
        layers.append((y_ci, y_ci + ep_inf, "Chaussée inf.", ep_inf, mat_ci))
    if ch_sup:
        layers.append((tn - ep_sup, tn, "Chaussée sup.", ep_sup, mat_cs))
    return layers


# ------------------------------------------------------------------ dessin tranchée

def _draw_trench(ax, c, x_left, x_right, config):
    w      = x_right - x_left
    layers = _layer_stack(config, c['fe'], c['diam_m'], c['tn'])
    y_bot  = layers[0][0]

    for y0, y1, _nom, _ep, mat in layers:
        ax.add_patch(mpatches.Rectangle(
            (x_left, y0), w, y1 - y0,
            facecolor=MATERIAU_REMBLAI_COLORS.get(mat, '#f5f5f5'),
            edgecolor='#555555', linewidth=0.4, zorder=3))

    ax.add_patch(mpatches.Rectangle(
        (x_left, y_bot), w, c['tn'] - y_bot,
        facecolor='none', edgecolor='#222222', linewidth=0.8, zorder=4))


# ------------------------------------------------------------------ cotes d'épaisseur

def _draw_dim_annotations(ax, c, x_right, config):
    """Cotes d'épaisseur côté DROIT (dernière conduite, référence)."""
    layers   = _layer_stack(config, c['fe'], c['diam_m'], c['tn'])
    x_tick_r = x_right + 0.10
    x_arrow  = x_right + 0.12
    x_text   = x_right + 0.16

    boundaries = sorted({y for y0, y1, *_ in layers for y in (y0, y1)})
    for y_b in boundaries:
        ax.plot([x_right, x_tick_r], [y_b, y_b],
                color='#444444', linewidth=0.5, zorder=5)

    for y0, y1, nom, ep, mat in layers:
        if y1 - y0 < 0.005:
            continue
        y_mid = (y0 + y1) / 2
        ax.annotate('', xy=(x_arrow, y0), xytext=(x_arrow, y1),
                    arrowprops=dict(arrowstyle='<->', color='#333333',
                                    lw=0.7, mutation_scale=6), zorder=6)
        mat_short = mat if len(mat) <= 14 else mat[:14] + '.'
        ax.text(x_text, y_mid,
                f"e={ep:.2f} m  {nom}\n({mat_short})",
                ha='left', va='center', fontsize=4.8,
                color='#222222', linespacing=1.3, zorder=12, clip_on=False)


def _draw_dim_annotations_left(ax, c, x_left, config):
    """Cotes d'épaisseur côté GAUCHE (première conduite).

    La flèche est à gauche de la tranchée ; le texte part vers la droite
    (ha='left') pour rester dans la zone de coupe et ne pas télescoper l'axe NGF.
    """
    layers   = _layer_stack(config, c['fe'], c['diam_m'], c['tn'])
    x_tick_l = x_left - 0.08
    x_arrow  = x_left - 0.10
    x_text   = x_left - 0.12

    boundaries = sorted({y for y0, y1, *_ in layers for y in (y0, y1)})
    for y_b in boundaries:
        ax.plot([x_tick_l, x_left], [y_b, y_b],
                color='#444444', linewidth=0.5, zorder=5)

    for y0, y1, nom, ep, mat in layers:
        if y1 - y0 < 0.005:
            continue
        y_mid = (y0 + y1) / 2
        ax.annotate('', xy=(x_arrow, y0), xytext=(x_arrow, y1),
                    arrowprops=dict(arrowstyle='<->', color='#333333',
                                    lw=0.7, mutation_scale=6), zorder=6)
        mat_short = mat if len(mat) <= 14 else mat[:14] + '.'
        ax.text(x_text, y_mid,
                f"e={ep:.2f} m  {nom}\n({mat_short})",
                ha='right', va='center', fontsize=4.8,
                color='#222222', linespacing=1.3, zorder=12, clip_on=False)


def _draw_depth_annotation_right(ax, c, x_right, config):
    """Profondeur totale côté droit, décalée après les cotes d'épaisseur."""
    ep_lit = config.get('ep_lit_pose', 0.10)
    y_bot  = c['fe'] - ep_lit
    total  = c['tn'] - y_bot

    x_arrow = x_right + 0.62
    x_text  = x_right + 0.68
    for y_b in (y_bot, c['tn']):
        ax.plot([x_right, x_arrow + 0.02], [y_b, y_b],
                color='#555555', linewidth=0.5, zorder=5)

    ax.annotate('', xy=(x_arrow, y_bot), xytext=(x_arrow, c['tn']),
                arrowprops=dict(arrowstyle='<->', color='#555555',
                                lw=0.8, mutation_scale=7), zorder=6)
    ax.text(x_text, (y_bot + c['tn']) / 2,
            f"Prof.\ntotale\n{total:.2f} m",
            ha='left', va='center', fontsize=4.8,
            color='#444444', linespacing=1.3, zorder=12, clip_on=False)


def _draw_depth_annotation(ax, c, x_left, config, shifted=False):
    """Profondeur totale côté gauche.

    shifted=True : colonne extérieure (quand les cotes d'épaisseur occupent
    la colonne intérieure).
    """
    ep_lit = config.get('ep_lit_pose', 0.10)
    y_bot  = c['fe'] - ep_lit
    total  = c['tn'] - y_bot

    if shifted:
        x_arrow = x_left - 0.72
        x_text  = x_left - 0.75
        for y_b in (y_bot, c['tn']):
            ax.plot([x_arrow - 0.02, x_left], [y_b, y_b],
                    color='#555555', linewidth=0.5, zorder=5)
    else:
        x_arrow = x_left - 0.12
        x_text  = x_left - 0.16
        for y_b in (y_bot, c['tn']):
            ax.plot([x_left - 0.10, x_left], [y_b, y_b],
                    color='#555555', linewidth=0.5, zorder=5)

    ax.annotate('', xy=(x_arrow, y_bot), xytext=(x_arrow, c['tn']),
                arrowprops=dict(arrowstyle='<->', color='#555555',
                                lw=0.8, mutation_scale=7), zorder=6)
    ax.text(x_text, (y_bot + c['tn']) / 2,
            f"Prof.\ntotale\n{total:.2f} m",
            ha='right', va='center', fontsize=4.8,
            color='#444444', linespacing=1.3, zorder=12, clip_on=False)


# ------------------------------------------------------------------ noms pour titre / fichier

def _ordered_regard_names(crossings):
    seen, names = set(), []
    for c in crossings:
        for n in (c['nom_amont'], c['nom_aval']):
            if n and n not in seen:
                seen.add(n)
                names.append(n)
    return names


def _build_title(crossings):
    return "  ·  ".join(_ordered_regard_names(crossings)) or "Coupe transversale"


def _build_filename(crossings):
    parts = _ordered_regard_names(crossings)
    safe  = "_".join(p.replace(" ", "_").replace("/", "-") for p in parts)
    return f"{safe}_plan_de_coupe.pdf" if safe else "plan_de_coupe.pdf"


# ------------------------------------------------------------------ dialog

class CoupeTransversaleDialog(QDialog):

    def __init__(self, crossings, config, parent=None, cut_line_pts=None):
        super().__init__(parent)
        self.crossings      = crossings
        self.config         = config
        self._scale         = None
        self._cut_line_pts  = cut_line_pts or []

        self.setWindowTitle("Plan de coupe transversale")
        self.setMinimumSize(900, 580)
        self.resize(1100, 680)
        self.setAttribute(Qt.WA_DeleteOnClose, False)

        layout = QVBoxLayout(self)

        ctrl = QHBoxLayout()
        ctrl.addWidget(QLabel("Format :"))
        self.fmt_combo = QComboBox()
        for name in PAPER_SIZES:
            self.fmt_combo.addItem(name)
        self.fmt_combo.currentIndexChanged.connect(self._refresh)
        ctrl.addWidget(self.fmt_combo)
        ctrl.addSpacing(20)
        self.lbl_scale = QLabel("Échelle : —")
        ctrl.addWidget(self.lbl_scale)
        ctrl.addStretch()
        btn_pdf = QPushButton("Exporter PDF…")
        btn_pdf.clicked.connect(self._export_pdf)
        ctrl.addWidget(btn_pdf)
        layout.addLayout(ctrl)

        self.figure = Figure()
        self.canvas = FigureCanvas(self.figure)
        self.canvas.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        layout.addWidget(self.canvas)

        self._refresh()

    # ------------------------------------------------------------------ plan de situation

    def _render_situation_plan(self, ax_sit):
        """Rendu des couches QGIS visibles + trait de coupe dans ax_sit."""
        import os
        import tempfile
        from qgis.core import (QgsMapSettings, QgsMapRendererSequentialJob,
                               QgsRectangle, QgsProject)
        from qgis.PyQt.QtCore import QSize
        from qgis.PyQt.QtGui import QColor, QImage
        from matplotlib.image import imread

        pts = self._cut_line_pts
        if not pts:
            ax_sit.text(0.5, 0.5, "Trait de coupe non disponible",
                        ha='center', va='center', transform=ax_sit.transAxes,
                        fontsize=7, color='#888888')
            ax_sit.set_axis_off()
            return

        xs = [p.x() for p in pts]
        ys = [p.y() for p in pts]
        dx = max(xs) - min(xs)
        dy = max(ys) - min(ys)
        buf = max(max(dx, dy) * 2.0, 20.0)

        extent = QgsRectangle(
            min(xs) - buf, min(ys) - buf,
            max(xs) + buf, max(ys) + buf,
        )

        project = QgsProject.instance()
        root    = project.layerTreeRoot()
        visible_layers = []
        for layer in project.mapLayers().values():
            if not (hasattr(layer, 'isValid') and layer.isValid()):
                continue
            node = root.findLayer(layer.id())
            if node and node.isVisible():
                visible_layers.append(layer)

        if not visible_layers:
            ax_sit.text(0.5, 0.5, "Aucune couche visible",
                        ha='center', va='center', transform=ax_sit.transAxes,
                        fontsize=7, color='#888888')
            ax_sit.set_axis_off()
            return

        # Dimensions pixel proportionnelles à l'emprise géographique
        height_px = 400
        ratio     = extent.width() / extent.height() if extent.height() > 0 else 1.0
        width_px  = max(int(height_px * ratio), 10)

        settings = QgsMapSettings()
        settings.setLayers(visible_layers)
        settings.setExtent(extent)
        settings.setOutputSize(QSize(width_px, height_px))
        settings.setBackgroundColor(QColor(255, 255, 255))
        settings.setDestinationCrs(project.crs())

        job = QgsMapRendererSequentialJob(settings)
        job.start()
        job.waitForFinished()

        img = job.renderedImage()
        with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as f:
            tmp_path = f.name
        img.save(tmp_path)
        try:
            arr = imread(tmp_path)
        finally:
            try:
                os.unlink(tmp_path)
            except Exception:
                pass

        # Pas d'aspect dans imshow — l'axe gère les proportions
        ax_sit.imshow(arr,
                      extent=[extent.xMinimum(), extent.xMaximum(),
                               extent.yMinimum(), extent.yMaximum()],
                      origin='upper', zorder=1)

        # Trait de coupe en rouge
        ax_sit.plot(xs, ys, color='#e53935', linewidth=1.8, zorder=5)
        ax_sit.plot(xs[0],  ys[0],  'o', color='#43a047', markersize=5, zorder=6)
        ax_sit.plot(xs[-1], ys[-1], 's', color='#e53935', markersize=5, zorder=6)

        ax_sit.set_xlim(extent.xMinimum(), extent.xMaximum())
        ax_sit.set_ylim(extent.yMinimum(), extent.yMaximum())
        ax_sit.set_aspect('equal', adjustable='box')
        ax_sit.tick_params(labelbottom=False, labelleft=False,
                           labeltop=False, labelright=False)

    # ------------------------------------------------------------------ dessin

    def _refresh(self):
        fmt_name   = self.fmt_combo.currentText()
        w_mm, h_mm = PAPER_SIZES[fmt_name]
        draw_w_mm  = w_mm - 2 * _MARGIN_MM
        draw_h_mm  = h_mm - 2 * _MARGIN_MM - _CARTOUCHE_MM

        bounds = _trench_bounds(self.crossings)
        ep_lit = self.config.get('ep_lit_pose', 0.10)
        multi  = len(self.crossings) >= 2

        # Empilement X : tranchées collées selon leur largeur configurée.
        # La conduite est centrée dans sa tranchée.
        norm_bounds = []
        norm_cross  = list(self.crossings)
        cursor = 0.0
        for i, c in enumerate(self.crossings):
            w      = c['width']
            new_xl = cursor
            new_xr = cursor + w
            new_x  = cursor + w / 2.0   # conduite centrée
            norm_bounds.append((new_xl, new_xr))
            norm_cross[i] = {**c, 'x': new_x}
            cursor = new_xr

        x_min_data = norm_bounds[0][0]   # = 0
        x_max_data = norm_bounds[-1][1]
        y_min_data = min(c['fe'] - ep_lit for c in norm_cross)
        y_max_data = max(c['tn'] for c in norm_cross)

        x_left_reserve = 1.00 if multi else 0.30
        x_min = x_min_data - x_left_reserve
        x_max = x_max_data + _ANNOT_RESERVE_M
        y_min = y_min_data - 0.20
        y_max = y_max_data + 0.25

        raw_scale = max((x_max - x_min) / (draw_w_mm / 1000.0),
                        (y_max - y_min) / (draw_h_mm / 1000.0))
        scale = _nice_scale(raw_scale)
        self._scale = scale
        self.lbl_scale.setText(f"Échelle : 1:{scale}")

        self.figure.clear()

        # ── Profil de coupe (moitié droite) ──────────────────────────────
        ax = self.figure.add_axes([0.52, 0.16, 0.45, 0.66])
        ax.set_aspect('equal')
        ax.set_xlabel("Largeur de tranchée (m)", fontsize=7)
        ax.set_ylabel("Altitude NGF (m)", fontsize=7)
        ax.tick_params(labelsize=6)
        ax.grid(True, linestyle=':', alpha=0.4, linewidth=0.4)

        # Ligne TN
        tn_xs  = [c['x'] for c in norm_cross]
        tn_ys  = [c['tn'] for c in norm_cross]
        xs_ext = [x_min] + tn_xs + [x_max_data + 0.25]
        ys_ext = [tn_ys[0]] + tn_ys + [tn_ys[-1]]
        ax.plot(xs_ext, ys_ext, color='#6d4c41', linewidth=1.2, label='TN', zorder=6)
        ax.fill_between(xs_ext, ys_ext, y_max + 0.1,
                        color='#d7ccc8', alpha=0.25, zorder=1)

        # Tranchées
        for c, (xl, xr) in zip(norm_cross, norm_bounds):
            _draw_trench(ax, c, xl, xr, self.config)

        # Cotes d'épaisseur
        last = len(norm_cross) - 1
        for i, (c, (xl, xr)) in enumerate(zip(norm_cross, norm_bounds)):
            if i == last:
                _draw_dim_annotations(ax, c, xr, self.config)
                if multi:
                    _draw_depth_annotation_right(ax, c, xr, self.config)
            if i == 0:
                if multi:
                    _draw_dim_annotations_left(ax, c, xl, self.config)
                    _draw_depth_annotation(ax, c, xl, self.config, shifted=True)
                else:
                    _draw_depth_annotation(ax, c, xl, self.config, shifted=False)

        # Frontières verticales entre tranchées adjacentes
        for i in range(len(norm_cross) - 1):
            ax.axvline(x=norm_bounds[i][1], color='#999999',
                       linewidth=0.6, linestyle='--', zorder=5)

        # Cercles conduits + étiquettes
        for c in norm_cross:
            r  = c['diam_m'] / 2
            cy = c['fe'] + r
            fc = MATERIAU_CONDUIT_COLORS.get(c['materiau'], MATERIAU_CONDUIT_COLORS[''])
            ec = RESEAU_EDGE_COLORS.get(c['reseau'], '#333333')
            ax.add_patch(mpatches.Circle(
                (c['x'], cy), r,
                facecolor=fc, edgecolor=ec, linewidth=0.8, zorder=10))
            ax.text(c['x'], cy, str(int(c['diam_m'] * 1000)),
                    ha='center', va='center', fontsize=5, color='#111111', zorder=11)
            ax.text(c['x'], c['fe'] + c['diam_m'] + 0.04,
                    c['reseau'], ha='center', va='bottom', fontsize=5,
                    color=ec, zorder=11)

        # Cotes NGF
        for c in norm_cross:
            ax.text(c['x'], c['fe'] - ep_lit - 0.04,
                    f"{c['fe']:.2f}", ha='center', va='top',
                    fontsize=5, color='#1565c0', zorder=12)
            ax.text(c['x'] + 0.02, c['tn'] + 0.03,
                    f"{c['tn']:.2f}", ha='left', va='bottom',
                    fontsize=5, color='#6d4c41', zorder=12)

        ax.set_xlim(x_min, x_max)
        ax.set_ylim(y_min, y_max)

        # ── Cartouche (bas de page, pleine largeur) ───────────────────────
        project_name = QgsProject.instance().title() or "—"
        date_str     = datetime.date.today().strftime("%d/%m/%Y")
        ax_cart = self.figure.add_axes([0.02, 0.01, 0.96, 0.04])
        ax_cart.set_axis_off()
        ax_cart.add_patch(mpatches.Rectangle(
            (0, 0), 1, 1, transform=ax_cart.transAxes,
            facecolor='#f5f5f5', edgecolor='#555555', linewidth=0.8, zorder=0))
        ax_cart.text(
            0.5, 0.5,
            f"Projet : {project_name}     Échelle : 1:{scale}     Date : {date_str}",
            ha='center', va='center', fontsize=6.5, color='#333333',
            transform=ax_cart.transAxes)

        # ── Titre (haut de page, simple, noir gras, sans encadrement) ─────
        title_txt = _build_title(self.crossings)
        self.figure.text(
            0.5, 0.965,
            f"PLAN DE COUPE  —  {title_txt}",
            ha='center', va='center', fontsize=9,
            fontweight='bold', color='black')

        # ── Cadres centrés entre cartouche (top=0.05) et titre (y=0.965) ──
        # centre = (0.05 + 0.93) / 2 = 0.49 ; hauteur 0.66 → bottom = 0.49 - 0.33 = 0.16
        ax_sit = self.figure.add_axes([0.02, 0.16, 0.46, 0.66])
        self._render_situation_plan(ax_sit)

        self.canvas.draw()

    # ------------------------------------------------------------------ export PDF

    def _export_pdf(self):
        default_name = _build_filename(self.crossings)
        path, _ = QFileDialog.getSaveFileName(
            self, "Enregistrer le plan de coupe en PDF",
            default_name, "PDF (*.pdf)")
        if not path:
            return

        fmt_name   = self.fmt_combo.currentText()
        w_mm, h_mm = PAPER_SIZES[fmt_name]

        old_size = self.figure.get_size_inches()
        self.figure.set_size_inches(w_mm / 25.4, h_mm / 25.4)
        self.figure.savefig(path, format='pdf', dpi=150, bbox_inches=None)
        self.figure.set_size_inches(*old_size)
        self.canvas.draw()

        from qgis.PyQt.QtWidgets import QMessageBox
        QMessageBox.information(
            self, "Export PDF",
            f"Plan de coupe exporté :\n{path}")
