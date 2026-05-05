from qgis.PyQt.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QPushButton,
    QFileDialog, QSizePolicy, QMessageBox,
    QCheckBox, QLabel, QFrame, QComboBox, QScrollArea,
)
from qgis.PyQt.QtCore import Qt
from qgis.PyQt.QtWidgets import QApplication

# ── Formats papier paysage (largeur × hauteur en mm) ─────────────────────────
# A2 et au-delà : hauteur plafonnée à A3 (297 mm), seule la largeur grandit.
_A3_H_MM = 297.0
PAPER_SIZES = {
    'A4': (297.0,  210.0),
    'A3': (420.0,  297.0),
    'A2': (594.0,  _A3_H_MM),
    'A1': (841.0,  _A3_H_MM),
    'A0': (1189.0, _A3_H_MM),
}
_EXPORT_DPI = {'A4': 150, 'A3': 150, 'A2': 120, 'A1': 100, 'A0': 80}

try:
    from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
    from matplotlib.figure import Figure
    from matplotlib.gridspec import GridSpec
    HAS_MPL = True
except ImportError:
    HAS_MPL = False

try:
    from qgis.core import NULL as QGIS_NULL
except ImportError:
    QGIS_NULL = None


# ─────────────────────────────────────────────────────────────────────────────
#  Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _fval(feat_or_val, key=None):
    """Extrait un float depuis une feature QGIS ou une valeur brute."""
    val = feat_or_val[key] if key is not None else feat_or_val
    if val is None or (QGIS_NULL is not None and val == QGIS_NULL):
        return None
    try:
        return float(val)
    except (TypeError, ValueError):
        return None


def _sval(feat, key):
    """Extrait une string depuis une feature QGIS, retourne '—' si vide."""
    try:
        v = feat[key]
    except (KeyError, TypeError):
        return '—'
    if v is None or (QGIS_NULL is not None and v == QGIS_NULL):
        return '—'
    s = str(v).strip()
    return s if s else '—'


def _fmt(val, fmt='{:.2f}'):
    return fmt.format(val) if val is not None else '—'


# ─────────────────────────────────────────────────────────────────────────────
#  Options dialog
# ─────────────────────────────────────────────────────────────────────────────

class ProfilOptionsDialog(QDialog):
    """Fenêtre de choix des éléments à afficher dans le profil en long."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Options du profil en long")
        self.setFixedWidth(340)
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowContextHelpButtonHint)

        layout = QVBoxLayout(self)
        layout.setSpacing(8)

        lbl = QLabel("Éléments à afficher :")
        lbl.setStyleSheet("font-weight: bold;")
        layout.addWidget(lbl)

        sep = QFrame()
        sep.setFrameShape(QFrame.HLine)
        sep.setFrameShadow(QFrame.Sunken)
        layout.addWidget(sep)

        self.cb_cartouche  = QCheckBox("Tableau de valeurs")
        self.cb_fleches    = QCheckBox("Emplacement des piquages (flèches)")
        self.cb_noms       = QCheckBox("Noms des piquages")
        self.cb_distances  = QCheckBox("Distance de piquage")

        for cb in (self.cb_cartouche, self.cb_fleches, self.cb_noms, self.cb_distances):
            cb.setChecked(True)
            layout.addWidget(cb)

        # désactiver noms+distances si fleches décoché
        self.cb_fleches.toggled.connect(self._on_fleches_toggled)

        sep2 = QFrame()
        sep2.setFrameShape(QFrame.HLine)
        sep2.setFrameShadow(QFrame.Sunken)
        layout.addWidget(sep2)

        fmt_row = QHBoxLayout()
        fmt_row.addWidget(QLabel("Format papier :"))
        self.cb_format = QComboBox()
        for f in PAPER_SIZES:
            self.cb_format.addItem(f)
        self.cb_format.setCurrentText('A3')
        fmt_row.addStretch()
        fmt_row.addWidget(self.cb_format)
        layout.addLayout(fmt_row)

        sep3 = QFrame()
        sep3.setFrameShape(QFrame.HLine)
        sep3.setFrameShadow(QFrame.Sunken)
        layout.addWidget(sep3)

        btn_row = QHBoxLayout()
        btn_row.addStretch()
        btn_ok     = QPushButton("Tracer le profil")
        btn_cancel = QPushButton("Annuler")
        btn_ok.setDefault(True)
        btn_ok.clicked.connect(self.accept)
        btn_cancel.clicked.connect(self.reject)
        btn_row.addWidget(btn_cancel)
        btn_row.addWidget(btn_ok)
        layout.addLayout(btn_row)

    def _on_fleches_toggled(self, checked):
        for cb in (self.cb_noms, self.cb_distances):
            cb.setEnabled(checked)
            if not checked:
                cb.setChecked(False)

    def options(self):
        return {
            'cartouche':          self.cb_cartouche.isChecked(),
            'fleches_piquages':   self.cb_fleches.isChecked(),
            'noms_piquages':      self.cb_noms.isChecked(),
            'distances_piquages': self.cb_distances.isChecked(),
            'format_papier':      self.cb_format.currentText(),
        }


# ─────────────────────────────────────────────────────────────────────────────
#  Dialog
# ─────────────────────────────────────────────────────────────────────────────

class ProfilDialog(QDialog):
    """
    Fenêtre profil en long style Covadis.
    Bande supérieure : noms des regards.
    Bande intermédiaire : noms des piquages (tabouret, amont, distance).
    Graphique : TN, FE radier, corps de conduite, cheminées, flèches de piquage.
    Cartouche tabulaire : abscisses, TN, FE, profondeur, Ø, matériau, pente.
    """

    _ROWS = [
        ('Regard',          'regard'),
        ('Abscisse (m)',    'abscisse'),
        ('TN (m NGF)',      'tn'),
        ('FE radier (m)',   'fe'),
        ('Prof. (m)',       'prof'),
        ('Longueur (m)',    'longueur'),
        ('Ø (mm)',          'diametre'),
        ('Matériau',        'materiau'),
        ('Pente (%)',       'pente'),
        ('L. cumulée (m)',  'longueur_cum'),
    ]
    _SEP_AFTER = 4   # ligne épaisse après la ligne index 4 ('prof')

    def __init__(self, data, options=None, parent=None):
        super().__init__(parent)
        self.data = data
        self.opts = options or {
            'cartouche': True,
            'fleches_piquages': True,
            'noms_piquages': True,
            'distances_piquages': True,
        }

        self.color = '#CC0000' if data['reseau'] == 'EU' else '#0055CC'

        nom_dep = _sval(data['regards'][0],  'nom')
        nom_arr = _sval(data['regards'][-1], 'nom')
        self.setWindowTitle(
            f"Profil en long – {data['reseau']}  ·  {nom_dep} → {nom_arr}")
        self.setMinimumSize(600, 400)
        self.setAttribute(Qt.WA_DeleteOnClose, False)

        if not HAS_MPL:
            QMessageBox.critical(
                self, "matplotlib manquant",
                "matplotlib est nécessaire pour afficher le profil.\n"
                "Installez-le via : pip install matplotlib")
            return

        self._build_ui()
        self._draw()

    # ------------------------------------------------------------------ UI

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(4)

        fmt       = self.opts.get('format_papier', 'A3')
        w_mm, h_mm = PAPER_SIZES.get(fmt, PAPER_SIZES['A3'])
        w_in, h_in = w_mm / 25.4, h_mm / 25.4

        self.figure = Figure(facecolor='white')
        self.figure.set_size_inches(w_in, h_in)

        self.canvas = FigureCanvas(self.figure)
        px_w = int(w_in * self.figure.dpi)
        px_h = int(h_in * self.figure.dpi)
        self.canvas.setFixedSize(px_w, px_h)

        scroll = QScrollArea()
        scroll.setWidget(self.canvas)
        scroll.setWidgetResizable(False)
        scroll.setAlignment(Qt.AlignCenter)
        layout.addWidget(scroll, stretch=1)

        # Taille fenêtre = paper limité à l'écran disponible
        screen = QApplication.primaryScreen().availableGeometry()
        dlg_w  = min(px_w + 40,  screen.width()  - 60)
        dlg_h  = min(px_h + 80,  screen.height() - 60)
        self.resize(dlg_w, dlg_h)

        btn_row = QHBoxLayout()
        btn_row.addStretch()
        for label, fmt in [("Exporter PNG", "png"), ("Exporter PDF", "pdf")]:
            btn = QPushButton(label)
            btn.clicked.connect(lambda _checked, f=fmt: self._export(f))
            btn_row.addWidget(btn)
        layout.addLayout(btn_row)

    # ------------------------------------------------------------------ dessin principal

    def _draw(self):
        d         = self.data
        regards   = d['regards']
        conduites = d['conduites']
        abscisses = d['abscisses']
        piquages  = d['piquages']   # {idx: [{abscisse, nom}]}

        n_reg  = len(regards)
        n_cond = len(conduites)

        # Valeurs regards
        noms      = [_sval(r, 'nom')       for r in regards]
        tn_vals   = [_fval(r, 'tn')        for r in regards]
        fe_vals   = [_fval(r, 'fe_radier') for r in regards]
        prof_vals = [_fval(r, 'profondeur')for r in regards]

        valid_y = [v for v in tn_vals + fe_vals if v is not None]
        y_min   = (min(valid_y) - 0.5)  if valid_y else 0.0
        y_max   = (max(valid_y) + 1.5)  if valid_y else 10.0
        total_l = abscisses[-1]         if abscisses[-1] > 0 else 1.0
        x_margin = total_l * 0.05

        n_rows = len(self._ROWS)

        titre = (f"Profil en long – Réseau {d['reseau']}"
                 f"  ·  {noms[0]} → {noms[-1]}")
        self.figure.suptitle(titre, fontsize=9, fontweight='bold', y=0.99,
                             ha='center', va='top')

        avec_cartouche = self.opts.get('cartouche', True)
        if avec_cartouche:
            gs = GridSpec(
                4, 1, figure=self.figure,
                height_ratios=[0.6, 1.0, 5.6, 3],
                hspace=0.02,
                left=0.11, right=0.97,
                top=0.92, bottom=0.05,
            )
            ax_r = self.figure.add_subplot(gs[0])
            ax_q = self.figure.add_subplot(gs[1])
            ax_p = self.figure.add_subplot(gs[2])
            ax_c = self.figure.add_subplot(gs[3])
        else:
            gs = GridSpec(
                3, 1, figure=self.figure,
                height_ratios=[0.6, 1.0, 8.6],
                hspace=0.02,
                left=0.11, right=0.97,
                top=0.92, bottom=0.05,
            )
            ax_r = self.figure.add_subplot(gs[0])
            ax_q = self.figure.add_subplot(gs[1])
            ax_p = self.figure.add_subplot(gs[2])
            ax_c = None

        self._draw_regard_band(ax_r, noms, abscisses, total_l, x_margin)
        self._draw_piquage_band(ax_q, piquages, abscisses, noms, total_l, x_margin)
        self._draw_profile(ax_p, n_reg, n_cond,
                           noms, tn_vals, fe_vals, prof_vals,
                           abscisses, piquages,
                           y_min, y_max, total_l, x_margin)
        if ax_c is not None:
            self._draw_cartouche(ax_c, n_reg, n_cond, n_rows,
                                 noms, tn_vals, fe_vals, prof_vals,
                                 abscisses, conduites, total_l, x_margin)
        self.canvas.draw()

    # ------------------------------------------------------------------ bandes

    def _draw_regard_band(self, ax, noms, abscisses, total_l, x_margin):
        """Bande supérieure : noms des regards en rotation 45°, alternés haut/bas."""
        ax.set_xlim(-x_margin, total_l + x_margin)
        ax.set_ylim(0, 1)
        for spine in ax.spines.values():
            spine.set_visible(False)
        ax.tick_params(left=False, bottom=False, labelleft=False, labelbottom=False)
        ax.set_facecolor('#FAFAFA')
        for i, (nom, abs_) in enumerate(zip(noms, abscisses)):
            txt = ax.text(abs_, 0.05, nom, rotation=45, ha='left', va='bottom',
                          fontsize=6.5, color='#111111')
            txt.set_clip_on(True)
            txt.set_clip_path(ax.patch)
        ax.axhline(0, color='#333333', linewidth=1.0)

    def _draw_piquage_band(self, ax, piquages, abscisses, noms, total_l, x_margin):
        """Bande intermédiaire : 3 infos piquage en rotation 45° (tabouret / amont / dist)."""
        ax.set_xlim(-x_margin, total_l + x_margin)
        ax.set_ylim(0, 1)
        for spine in ax.spines.values():
            spine.set_visible(False)
        ax.tick_params(left=False, bottom=False, labelleft=False, labelbottom=False)
        ax.set_facecolor('#FAFAFA')
        show_noms = self.opts.get('noms_piquages', True)
        show_dist = self.opts.get('distances_piquages', True)
        for idx, piq_list in piquages.items():
            abs0 = abscisses[idx]
            nom_amon = noms[idx] if idx < len(noms) else '—'
            for piq in piq_list:
                nom_tab = piq['nom']
                if not nom_tab or not show_noms:
                    continue
                abs_piq = piq['abscisse']
                dist_am = abs_piq - abs0
                if show_dist:
                    label = f"{nom_tab} {dist_am:.1f}m"
                else:
                    label = nom_tab
                txt = ax.text(abs_piq, 0.05, label, rotation=45, ha='left', va='bottom',
                              fontsize=5.5, color='#006600')
                txt.set_clip_on(True)
                txt.set_clip_path(ax.patch)
        ax.axhline(0, color='#333333', linewidth=1.0)

    # ------------------------------------------------------------------ profil

    def _draw_profile(self, ax, n_reg, n_cond,
                      noms, tn_vals, fe_vals, prof_vals,
                      abscisses, piquages,
                      y_min, y_max, total_l, x_margin=0.0):

        ax.set_ylabel("Altitude (m NGF)", fontsize=8)
        ax.set_xlim(-x_margin, total_l + x_margin)
        ax.set_ylim(y_min, y_max)
        ax.grid(True, linestyle=':', linewidth=0.4, alpha=0.5, zorder=0)
        ax.tick_params(labelbottom=False, labelsize=7)

        conduites = self.data['conduites']

        # Terrain naturel
        tn_pts = [(abscisses[i], v) for i, v in enumerate(tn_vals) if v is not None]
        if len(tn_pts) >= 2:
            xs, ys = zip(*tn_pts)
            ax.plot(xs, ys, '--', color='#666666', linewidth=1.2,
                    label='TN', zorder=2)

        # Corps des conduites (bande remplie entre FE et FE+diam)
        for i in range(n_cond):
            fe0, fe1 = fe_vals[i], fe_vals[i + 1]
            if fe0 is None or fe1 is None:
                continue
            diam   = _fval(conduites[i], 'diametre')
            diam_m = (diam / 1000.0) if diam else 0.3
            x0, x1 = abscisses[i], abscisses[i + 1]
            ax.fill(
                [x0, x1, x1, x0, x0],
                [fe0, fe1, fe1 + diam_m, fe0 + diam_m, fe0],
                color=self.color, alpha=0.18, zorder=2)
            ax.plot([x0, x1], [fe0 + diam_m, fe1 + diam_m],
                    '--', color=self.color, linewidth=0.7,
                    alpha=0.5, zorder=3)

        # Fil d'eau radier
        fe_pts = [(abscisses[i], v) for i, v in enumerate(fe_vals) if v is not None]
        if len(fe_pts) >= 2:
            xs, ys = zip(*fe_pts)
            ax.plot(xs, ys, '-', color=self.color, linewidth=2.0,
                    label='FE radier', zorder=4)

        # Regards (cheminées, sans les noms)
        w      = total_l * 0.006   # demi-largeur du fût
        w_hat  = w * 2.5           # demi-largeur du chapeau (tampon) au niveau TN

        def _gen_sup(i):
            fe = fe_vals[i]
            if fe is None:
                return None
            diams = []
            if i > 0:
                d = _fval(conduites[i - 1], 'diametre')
                if d:
                    diams.append(d)
            if i < n_cond:
                d = _fval(conduites[i], 'diametre')
                if d:
                    diams.append(d)
            diam_m = (max(diams) / 1000.0) if diams else 0.3
            return fe + diam_m

        for i in range(n_reg):
            abs_ = abscisses[i]
            fe   = fe_vals[i]
            tn   = tn_vals[i]
            gs   = _gen_sup(i)
            if fe is not None and tn is not None and gs is not None:
                # Fût
                xs_fill = [abs_ - w, abs_ - w, abs_ + w, abs_ + w, abs_ - w]
                ys_fill = [gs, tn, tn, gs, gs]
                ax.fill(xs_fill, ys_fill, color=self.color, alpha=0.18, zorder=4)
                # Parois
                ax.plot([abs_ - w, abs_ - w, abs_ + w, abs_ + w],
                        [gs,       tn,       tn,       gs],
                        '-', color=self.color, linewidth=1.2, zorder=5)
                # Chapeau
                ax.plot([abs_ - w_hat, abs_ + w_hat], [tn, tn],
                        '-', color='#333333', linewidth=2.5, zorder=6)
            elif fe is not None:
                ax.plot(abs_, fe, 'o', color='#333333', markersize=5, zorder=5)

        # Piquages (flèches uniquement, sans texte)
        if not self.opts.get('fleches_piquages', True):
            return
        y_arrow_top = y_max
        for idx, piq_list in piquages.items():
            fe0 = fe_vals[idx] if idx < len(fe_vals) else None
            fe1 = fe_vals[idx + 1] if idx + 1 < len(fe_vals) else fe0
            abs0 = abscisses[idx]
            seg  = (abscisses[idx + 1] - abs0) if idx + 1 < len(abscisses) else 1.0
            for piq in piq_list:
                abs_piq = piq['abscisse']
                if fe0 is not None and fe1 is not None and seg > 0:
                    t      = (abs_piq - abs0) / seg
                    fe_piq = fe0 + t * (fe1 - fe0)
                else:
                    fe_piq = y_min
                ax.annotate(
                    '', xy=(abs_piq, fe_piq),
                    xytext=(abs_piq, y_arrow_top),
                    arrowprops=dict(
                        arrowstyle='->', color='#009900', linewidth=1.1),
                    zorder=5)


    # ------------------------------------------------------------------ cartouche

    def _draw_cartouche(self, ax, n_reg, n_cond, n_rows,
                        noms, tn_vals, fe_vals, prof_vals,
                        abscisses, conduites, total_l, x_margin=0.0):

        ax.set_xlim(-x_margin, total_l + x_margin)
        ax.set_ylim(0, n_rows)
        ax.set_facecolor('#FAFAFA')

        # Y-tick labels = noms des lignes
        ax.set_yticks([n_rows - i - 0.5 for i in range(n_rows)])
        ax.set_yticklabels([row[0] for row in self._ROWS], fontsize=6.5)
        ax.tick_params(left=False, bottom=False, labelbottom=False, labelsize=6.5)
        for spine in ax.spines.values():
            spine.set_visible(False)

        # Fond alterné par ligne
        for i in range(n_rows):
            if i % 2 == 1:
                ax.axhspan(i, i + 1, color='#F0F0F0', zorder=0)

        # Lignes horizontales
        for row_idx in range(n_rows + 1):
            is_border = row_idx in (0, n_rows)
            is_sep    = row_idx == self._SEP_AFTER + 1
            lw  = 1.0 if (is_border or is_sep) else 0.4
            col = '#333333' if (is_border or is_sep) else '#AAAAAA'
            ax.axhline(row_idx, color=col, linewidth=lw, zorder=2)

        # Lignes verticales (regards)
        for abs_ in abscisses:
            ax.axvline(abs_, color='#BBBBBB', linewidth=0.5, zorder=2)

        # Valeurs regards (positionnées à l'abscisse du regard)
        def reg_cell(i, key):
            if   key == 'regard':   return noms[i]
            elif key == 'abscisse': return _fmt(abscisses[i])
            elif key == 'tn':       return _fmt(tn_vals[i],   '{:.3f}')
            elif key == 'fe':       return _fmt(fe_vals[i],   '{:.3f}')
            elif key == 'prof':     return _fmt(prof_vals[i], '{:.2f}')
            return ''

        for i in range(n_reg):
            abs_ = abscisses[i]
            for row_idx, (_, key) in enumerate(self._ROWS):
                val = reg_cell(i, key)
                if not val:
                    continue
                ax.text(abs_, n_rows - row_idx - 0.5, val,
                        ha='center', va='center',
                        fontsize=6.5, color='#111111', zorder=3)

        # Valeurs conduites (positionnées au milieu du segment)
        def cond_cell(i, key):
            c = conduites[i]
            if   key == 'longueur':     return _fmt(_fval(c, 'longueur'))
            elif key == 'longueur_cum': return _fmt(abscisses[i + 1])
            elif key == 'diametre':     return _fmt(_fval(c, 'diametre'), '{:.0f}')
            elif key == 'materiau':     return _sval(c, 'materiau')
            elif key == 'pente':        return _fmt(_fval(c, 'pente'), '{:.2f}')
            return ''

        for i in range(n_cond):
            mid = (abscisses[i] + abscisses[i + 1]) / 2
            for row_idx, (_, key) in enumerate(self._ROWS):
                val = cond_cell(i, key)
                if not val or val == '—':
                    continue
                ax.text(mid, n_rows - row_idx - 0.5, val,
                        ha='center', va='center',
                        fontsize=6.5, color='#111111', zorder=3)

        # Axe X visible en bas du cartouche
        ax.xaxis.set_visible(True)
        ax.tick_params(bottom=True, labelbottom=True, labelsize=7)
        ax.set_xlabel("Abscisse (m)", fontsize=8, labelpad=2)

    # ------------------------------------------------------------------ export

    def _export(self, fmt):
        nom_dep = _sval(self.data['regards'][0],  'nom')
        nom_arr = _sval(self.data['regards'][-1], 'nom')
        # Nettoie les caractères interdits dans un nom de fichier
        def _safe(s):
            return ''.join(c for c in s if c not in r'\/:*?"<>|').strip()
        default_name = f"profil_{_safe(nom_dep)}_{_safe(nom_arr)}.{fmt}"
        from ..tools.projet_bet import project_dir
        import os
        start_dir = project_dir() or os.path.expanduser("~")
        path, _ = QFileDialog.getSaveFileName(
            self,
            f"Exporter le profil en {fmt.upper()}",
            os.path.join(start_dir, default_name),
            f"Fichier {fmt.upper()} (*.{fmt})")
        if path:
            fmt_papier = self.opts.get('format_papier', 'A3')
            dpi = _EXPORT_DPI.get(fmt_papier, 150)
            self.figure.savefig(path, format=fmt, dpi=dpi)

    # ------------------------------------------------------------------ close

    def closeEvent(self, event):
        self.figure.clf()
        super().closeEvent(event)
