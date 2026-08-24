# gui/profil_groupe_dialog.py

from qgis.PyQt.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QPushButton,
    QFileDialog, QSizePolicy, QMessageBox,
    QCheckBox, QLabel, QFrame, QScrollArea, QApplication,
)
from qgis.PyQt.QtCore import Qt

from ..tools import i18n
from .profil_dialog import PAPER_SIZES, _EXPORT_DPI

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


def _fval(v):
    if v is None or (QGIS_NULL is not None and v == QGIS_NULL):
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _sval(feat, key):
    try:
        v = feat[key]
    except (KeyError, TypeError):
        return '—'
    if v is None or (QGIS_NULL is not None and v == QGIS_NULL):
        return '—'
    s = str(v).strip()
    return s if s else '—'


def _fmt(val, spec='{:.2f}'):
    return spec.format(val) if val is not None else '—'


_EU_COLORS = ['#CC0000', '#E03535', '#FF5555', '#AA1111', '#FF2222',
              '#DD3333', '#BB0000', '#EE4444', '#993300', '#FF6600']
_EP_COLORS = ['#0044CC', '#1166DD', '#3388EE', '#0022AA', '#2255FF',
              '#1144BB', '#003399', '#4477EE', '#005599', '#0077CC']

# 5 lignes partagées : libellé regard / libellé conduite
_N_ROWS = 5
# (clé du libellé regard, clé du libellé conduite) ; '—' n'a rien à traduire
_ROW_LABEL_KEYS = [
    ('col_nom',          'col_diametre_court'),
    ('col_abscisse',     'col_long_court'),
    ('col_tn_court',     'col_materiau'),
    ('col_fe_rad_court', 'col_pente'),
    ('col_prof_court',   None),
]

_FONT_CART  = 6.8
_FONT_LABEL = 6.8


class ProfilGroupeDialog(QDialog):
    """
    Profil groupé EU + EP.

    Bandes supérieures : noms des regards et piquages.
    Graphique altimétrique avec cheminées (sans texte).
    Bas (opt.) : un cartouche par réseau, en chaîne R1–C1–R2–C2–…
                 5 lignes partagées regard / conduite.
    """

    def __init__(self, data, parent=None, options=None):
        super().__init__(parent)
        self.data = data
        self.opts = options or {
            'cartouche': True,
            'fleches_piquages': True,
            'noms_piquages': True,
            'distances_piquages': True,
        }
        self.setWindowTitle(i18n.tr('pg_titre'))
        self.setMinimumSize(600, 400)
        self.setAttribute(Qt.WA_DeleteOnClose, False)

        if not HAS_MPL:
            QMessageBox.critical(
                self, i18n.tr('pf_matplotlib_titre'),
                i18n.tr('pf_matplotlib_msg'))
            return

        self._build_ui()
        self._draw()

    # ------------------------------------------------------------------ UI

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(4)

        fmt        = self.opts.get('format_papier', 'A3')
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

        screen = QApplication.primaryScreen().availableGeometry()
        dlg_w  = min(px_w + 40,  screen.width()  - 60)
        dlg_h  = min(px_h + 80,  screen.height() - 60)
        self.resize(dlg_w, dlg_h)

        btn_row = QHBoxLayout()
        btn_row.addStretch()
        for cle, fmt in [('ct_export_png', "png"), ('ct_export_pdf', "pdf")]:
            btn = QPushButton(i18n.tr(cle).rstrip('…'))
            btn.clicked.connect(lambda _c, f=fmt: self._export(f))
            btn_row.addWidget(btn)
        layout.addLayout(btn_row)

    # ------------------------------------------------------------------ dessin principal

    def _draw(self):
        conduites = self.data['conduites']
        ref_len   = self.data['ref_length']

        _EU_C = _EU_COLORS[0]
        _EP_C = _EP_COLORS[0]
        colors = [_EU_C if c['reseau'] == 'EU' else _EP_C for c in conduites]

        all_y = []
        for c in conduites:
            for v in (c['fe0'], c['fe1'], c['tn0'], c['tn1']):
                if v is not None:
                    all_y.append(v)

        y_min    = (min(all_y) - 0.5) if all_y else 0.0
        y_max    = (max(all_y) + 1.5) if all_y else 10.0
        x_margin = ref_len * 0.03

        conduites_eu = [(c, col) for c, col in zip(conduites, colors)
                        if c['reseau'] == 'EU']
        conduites_ep = [(c, col) for c, col in zip(conduites, colors)
                        if c['reseau'] == 'EP']
        has_eu = bool(conduites_eu)
        has_ep = bool(conduites_ep)

        # Regards uniques ordonnés par abscisse (pour la bande noms)
        regard_entries = []
        seen_reg = set()
        for c in conduites:
            for x, nom in [(c['x0'], c['nom_r0']), (c['x1'], c['nom_r1'])]:
                key = (nom or '', round(x, 2))
                if key not in seen_reg:
                    seen_reg.add(key)
                    regard_entries.append({'x': x, 'nom': nom or '—'})
        regard_entries.sort(key=lambda r: r['x'])

        self.figure.clear()

        # ── Titre figure : EU (gauche) | titre (centre) | EP (droite) ────────
        def _chain_ends(reseau_name):
            pairs = [(c, col) for c, col in zip(conduites, colors)
                     if c['reseau'] == reseau_name]
            if not pairs:
                return None, None, None
            s     = sorted(pairs, key=lambda t: t[0]['x0'])
            start = s[0][0]['nom_r0']
            x0s   = {round(c['x0'], 2) for c, _ in s}
            terms = [c for c, _ in s if round(c['x1'], 2) not in x0s]
            end_c = max(terms, key=lambda c: c['x1']) if terms else s[-1][0]
            return start, end_c['nom_r1'], s[0][1]

        eu_s, eu_e, eu_c = _chain_ends('EU')
        ep_s, ep_e, ep_c = _chain_ends('EP')

        self.figure.text(0.5, 0.99, i18n.tr('pg_titre'),
                         fontsize=9, fontweight='bold',
                         ha='center', va='top', color='black')
        if eu_s and eu_s != '—':
            self.figure.text(0.11, 0.99, f"EU : {eu_s} → {eu_e}",
                             fontsize=8, fontweight='bold',
                             ha='left', va='top', color=eu_c)
        if ep_s and ep_s != '—':
            self.figure.text(0.97, 0.99, f"EP : {ep_s} → {ep_e}",
                             fontsize=8, fontweight='bold',
                             ha='right', va='top', color=ep_c)

        avec_cartouche = self.opts.get('cartouche', True)

        if not avec_cartouche:
            gs = GridSpec(
                3, 1, figure=self.figure,
                height_ratios=[0.6, 1.0, 8.4],
                hspace=0.02,
                left=0.11, right=0.97,
                top=0.92, bottom=0.05,
            )
            ax_r = self.figure.add_subplot(gs[0])
            ax_q = self.figure.add_subplot(gs[1])
            ax_p = self.figure.add_subplot(gs[2])

            self._draw_regard_band(ax_r, regard_entries, ref_len, x_margin)
            self._draw_piquage_band(ax_q, regard_entries, ref_len, x_margin)
            self._draw_profile(ax_p, conduites, colors, ref_len,
                               y_min, y_max, x_margin)
            ax_p.tick_params(labelbottom=True)
            ax_p.set_xlabel(i18n.tr('pf_distance_projetee'), fontsize=8)
            self.canvas.draw()
            return

        n_cart = (1 if has_eu else 0) + (1 if has_ep else 0)
        ratios = [0.6, 1.0, 5.4] + [2] * n_cart
        gs = GridSpec(
            3 + n_cart, 1, figure=self.figure,
            height_ratios=ratios,
            hspace=0.06,
            left=0.13, right=0.97,
            top=0.92, bottom=0.04,
        )

        ax_r = self.figure.add_subplot(gs[0])
        ax_q = self.figure.add_subplot(gs[1])
        ax_p = self.figure.add_subplot(gs[2])

        self._draw_regard_band(ax_r, regard_entries, ref_len, x_margin)
        self._draw_piquage_band(ax_q, regard_entries, ref_len, x_margin)
        self._draw_profile(ax_p, conduites, colors, ref_len,
                           y_min, y_max, x_margin)

        cart_idx = 3
        if has_eu:
            ax_eu = self.figure.add_subplot(gs[cart_idx])
            show_x = not has_ep
            self._draw_cartouche_reseau(
                ax_eu, conduites_eu, '#CC0000', 'EU',
                ref_len, x_margin, show_xaxis=show_x)
            cart_idx += 1
        if has_ep:
            ax_ep = self.figure.add_subplot(gs[cart_idx])
            self._draw_cartouche_reseau(
                ax_ep, conduites_ep, '#0044CC', 'EP',
                ref_len, x_margin, show_xaxis=True)

        self.canvas.draw()

    # ------------------------------------------------------------------ bandes

    def _draw_regard_band(self, ax, regard_entries, ref_len, x_margin):
        ax.set_xlim(-x_margin, ref_len + x_margin)
        ax.set_ylim(0, 1)
        for spine in ax.spines.values():
            spine.set_visible(False)
        ax.tick_params(left=False, bottom=False, labelleft=False, labelbottom=False)
        ax.set_facecolor('#FAFAFA')
        for r in regard_entries:
            txt = ax.text(r['x'], 0.05, r['nom'], rotation=45,
                          ha='left', va='bottom', fontsize=6.5, color='#111111')
            txt.set_clip_on(True)
            txt.set_clip_path(ax.patch)
        ax.axhline(0, color='#333333', linewidth=1.0)

    def _draw_piquage_band(self, ax, regard_entries, ref_len, x_margin):
        ax.set_xlim(-x_margin, ref_len + x_margin)
        ax.set_ylim(0, 1)
        for spine in ax.spines.values():
            spine.set_visible(False)
        ax.tick_params(left=False, bottom=False, labelleft=False, labelbottom=False)
        ax.set_facecolor('#FAFAFA')
        if not self.opts.get('noms_piquages', True):
            ax.axhline(0, color='#333333', linewidth=1.0)
            return
        show_dist = self.opts.get('distances_piquages', True)
        _PIQ_COLOR = {'EU': _EU_COLORS[0], 'EP': _EP_COLORS[0]}
        reg_xs = sorted(r['x'] for r in regard_entries)
        for piq in self.data.get('piquages', []):
            nom = piq.get('nom', '')
            if not nom:
                continue
            x_piq  = piq['x']
            reseau = piq.get('reseau', 'EU')
            if show_dist:
                prev = max((rx for rx in reg_xs if rx <= x_piq), default=None)
                if prev is not None:
                    label = f"{nom} {x_piq - prev:.1f}m"
                else:
                    label = nom
            else:
                label = nom
            txt = ax.text(x_piq, 0.05, label, rotation=45,
                          ha='left', va='bottom', fontsize=5.5,
                          color=_PIQ_COLOR.get(reseau, _EU_COLORS[0]))
            txt.set_clip_on(True)
            txt.set_clip_path(ax.patch)
        ax.axhline(0, color='#333333', linewidth=1.0)

    # ------------------------------------------------------------------ profil graphique

    def _draw_profile(self, ax, conduites, colors, ref_len,
                      y_min, y_max, x_margin):

        ax.set_ylabel(i18n.tr('pf_altitude'), fontsize=8)
        ax.set_xlim(-x_margin, ref_len + x_margin)
        ax.set_ylim(y_min, y_max)
        ax.grid(True, linestyle=':', linewidth=0.4, alpha=0.5, zorder=0)
        ax.tick_params(labelbottom=False, labelsize=7)

        for c, color in zip(conduites, colors):
            feat       = c['feat']
            x0, x1    = c['x0'], c['x1']
            fe0, fe1  = c['fe0'], c['fe1']

            diam   = _fval(feat['diametre'])
            diam_m = (diam / 1000.0) if diam else 0.3

            if fe0 is not None and fe1 is not None:
                ax.fill(
                    [x0, x1, x1, x0, x0],
                    [fe0, fe1, fe1 + diam_m, fe0 + diam_m, fe0],
                    color=color, alpha=0.15, zorder=2)
                ax.plot([x0, x1], [fe0, fe1],
                        '-', color=color, linewidth=2.2, zorder=4)
                ax.plot(
                    [x0, x1], [fe0 + diam_m, fe1 + diam_m],
                    '--', color=color, linewidth=0.8, alpha=0.55, zorder=3)
            elif fe0 is not None:
                ax.plot(x0, fe0, 'o', color=color, markersize=6, zorder=4)
            elif fe1 is not None:
                ax.plot(x1, fe1, 'o', color=color, markersize=6, zorder=4)

        # Cheminées des regards (uniques) — couleur = première conduite qui référence le regard
        regards_by_x = {}
        for c, color in zip(conduites, colors):
            diam   = _fval(c['feat']['diametre'])
            diam_m = (diam / 1000.0) if diam else 0.3
            for x, nom, tn, fe in [
                (c['x0'], c['nom_r0'], c['tn0'], c['fe0']),
                (c['x1'], c['nom_r1'], c['tn1'], c['fe1']),
            ]:
                key = round(x, 2)
                if key not in regards_by_x:
                    regards_by_x[key] = {'x': x, 'nom': nom, 'tn': tn,
                                         'fe': fe, 'diam_m': diam_m,
                                         'color': color}
                else:
                    r = regards_by_x[key]
                    if fe is not None and (r['fe'] is None or fe < r['fe']):
                        r['fe'] = fe
                    if tn is not None and r['tn'] is None:
                        r['tn'] = tn
                    if diam_m > r['diam_m']:
                        r['diam_m'] = diam_m

        w       = min(ref_len * 0.006, 0.6)   # demi-largeur fût plafonnée à 0.6 m
        w_hat   = w * 2.5

        for r in regards_by_x.values():
            x, fe, tn, nom = r['x'], r['fe'], r['tn'], r['nom']
            diam_m         = r['diam_m']
            rc             = r['color']

            if fe is not None and tn is not None:
                gs = fe + 0.9 * diam_m   # accroche juste sous la génératrice sup.
                # Fût depuis gs jusqu'au TN — évite de couper la conduite
                ax.fill([x-w, x-w, x+w, x+w, x-w],
                        [gs,  tn,  tn,  gs,  gs],
                        color=rc, alpha=0.22, zorder=4)
                ax.plot([x-w, x-w, x+w, x+w],
                        [gs,  tn,  tn,  gs],
                        '-', color=rc, linewidth=1.2, zorder=5)
                # Chapeau (tampon) au niveau TN
                ax.plot([x-w_hat, x+w_hat], [tn, tn],
                        '-', color=rc, linewidth=2.5, zorder=6)
            elif fe is not None:
                ax.plot(x, fe, 'o', color=rc, markersize=5, zorder=5)

            # nom dans la bande supérieure, plus ici

        # Piquages (branchements) — flèches uniquement, texte dans la bande
        _PIQ_COLOR = {'EU': _EU_COLORS[0], 'EP': _EP_COLORS[0]}
        if self.opts.get('fleches_piquages', True):
            y_arrow_top = y_max
            for piq in self.data.get('piquages', []):
                x_piq  = piq['x']
                fe_piq = piq['fe'] if piq['fe'] is not None else y_min
                reseau = piq.get('reseau', 'EU')
                pcol   = _PIQ_COLOR.get(reseau, _EU_COLORS[0])
                ax.annotate(
                    '', xy=(x_piq, fe_piq),
                    xytext=(x_piq, y_arrow_top),
                    arrowprops=dict(arrowstyle='->', color=pcol, linewidth=1.1),
                    zorder=5)

    # ------------------------------------------------------------------ cartouche par réseau

    def _draw_cartouche_reseau(self, ax, conduites_col, color, reseau,
                               ref_len, x_margin, show_xaxis=False):
        """
        Cartouche en chaîne : R1 — C1 — R2 — C2 — … — Rn
        5 lignes partagées : regard (gauche) / conduite (droite).
        """
        n_rows = _N_ROWS

        # Trie les conduites par abscisse projetée amont
        cc = sorted(conduites_col, key=lambda t: t[0]['x0'])

        # Construit la liste ordonnée des colonnes
        # Chaque élément : ('R', x, regard_data) ou ('C', x, feat)
        cols   = []
        seen_r = {}   # (nom, round(x,2)) → True  pour éviter les doublons

        def _add_regard(x, nom, tn, fe):
            key = (nom or '', round(x, 2))
            if key in seen_r:
                return
            seen_r[key] = True
            prof = ((tn - fe) if (tn is not None and fe is not None) else None)
            cols.append(('R', x, {
                'nom':  nom or '—',
                'abs':  x,
                'tn':   tn,
                'fe':   fe,
                'prof': prof,
            }))

        for c, _col in cc:
            _add_regard(c['x0'], c['nom_r0'], c['tn0'], c['fe0'])
            mid = (c['x0'] + c['x1']) / 2.0
            cols.append(('C', mid, c['feat']))

        # Regards terminaux : tout x1 qui n'est le x0 d'aucune autre conduite
        x0_set = {round(c['x0'], 2) for c, _ in cc}
        for c, _ in cc:
            if round(c['x1'], 2) not in x0_set:
                _add_regard(c['x1'], c['nom_r1'], c['tn1'], c['fe1'])

        # Réordonne par x (les regards intercalés peuvent être hors ordre)
        cols.sort(key=lambda t: t[1])

        # ── Axes ──────────────────────────────────────────────────────────
        ax.set_xlim(-x_margin, ref_len + x_margin)
        ax.set_ylim(0, n_rows)
        ax.set_facecolor('#FAFAFA')
        ax.tick_params(left=False, bottom=False,
                       labelbottom=False, labelsize=_FONT_LABEL)
        for spine in ax.spines.values():
            spine.set_visible(False)

        # Titre réseau (à gauche, dans l'espace des y-labels)

        # Labels Y : regard (gras, couleur) en haut de cellule
        #            conduite (normal, gris)  en bas  de cellule — jamais superposés
        ax.set_yticks([n_rows - i - 0.5 for i in range(n_rows)])
        ax.set_yticklabels([''] * n_rows)
        trans = ax.get_yaxis_transform()   # x = fraction axes, y = données
        for i, (cle_rl, cle_cl) in enumerate(_ROW_LABEL_KEYS):
            rl = i18n.tr(cle_rl)
            cl = i18n.tr(cle_cl) if cle_cl else '—'
            y_mid = n_rows - i - 0.5
            has_cond = cl and cl != '—'
            y_r = y_mid + (0.15 if has_cond else 0.0)
            y_c = y_mid - 0.15
            ax.text(-0.01, y_r, rl, transform=trans,
                    ha='right', va='center', fontsize=_FONT_CART,
                    fontweight='bold', color=color, clip_on=False)
            if has_cond:
                ax.text(-0.01, y_c, cl, transform=trans,
                        ha='right', va='center', fontsize=_FONT_CART - 0.8,
                        fontweight='normal', color='#777777', clip_on=False)

        # ── Fonds alternés par ligne ───────────────────────────────────────
        for i in range(n_rows):
            if i % 2 == 1:
                ax.axhspan(i, i + 1, color='#F0F0F0', zorder=0)

        # ── Bandes colorées pour les conduites ────────────────────────────
        cond_bg = '#FFECEC' if reseau == 'EU' else '#ECF0FF'
        for c, _col in cc:
            ax.axvspan(c['x0'], c['x1'], alpha=0.18, color=cond_bg, zorder=1)

        # ── Lignes horizontales ───────────────────────────────────────────
        for row_idx in range(n_rows + 1):
            is_border = row_idx in (0, n_rows)
            lw  = 1.0 if is_border else 0.35
            col = '#333333' if is_border else '#CCCCCC'
            ax.axhline(row_idx, color=col, linewidth=lw, zorder=2)

        # ── Nudge anti-chevauchement pour les regards proches ────────────
        tol = max(ref_len * 0.04, 0.5)   # 4 % de la longueur, min 0.5 m
        r_indices = [(i, t[1]) for i, t in enumerate(cols) if t[0] == 'R']
        nudge = {i: 0.0 for i, _ in r_indices}

        j = 0
        while j < len(r_indices):
            grp = [r_indices[j]]
            while (j + 1 < len(r_indices) and
                   abs(r_indices[j + 1][1] - r_indices[j][1]) < tol):
                j += 1
                grp.append(r_indices[j])
            n = len(grp)
            if n > 1:
                spread = tol * 0.55
                step   = spread / (n - 1)
                for k, (idx, _) in enumerate(grp):
                    nudge[idx] = (k - (n - 1) / 2.0) * step
            j += 1

        # ── Lignes verticales aux positions des regards ───────────────────
        for i, (typ, x, _) in enumerate(cols):
            if typ == 'R':
                xd = x + nudge.get(i, 0.0)
                ax.axvline(xd, color='#AAAAAA', linewidth=0.6,
                           linestyle='--', zorder=2)

        # ── Valeurs — deux passes : regards en priorité ───────────────────
        # Passe 1 : regards (priorité) → on mémorise les cases occupées
        occupied = set()   # (round(xd, 1), row_idx)

        for i, (typ, x, data) in enumerate(cols):
            if typ != 'R':
                continue
            xd = x + nudge.get(i, 0.0)
            vals = [
                data['nom'],
                _fmt(xd),
                _fmt(data['tn'],   '{:.3f}'),
                _fmt(data['fe'],   '{:.3f}'),
                _fmt(data['prof'], '{:.2f}'),
            ]
            for row_idx, val in enumerate(vals):
                if not val or val == '—':
                    continue
                ax.text(xd, n_rows - row_idx - 0.5, val,
                        ha='center', va='center',
                        fontsize=_FONT_CART, color=color,
                        fontweight='bold', zorder=3, clip_on=True)
                occupied.add((round(xd, 1), row_idx))

        # Passe 2 : conduites — saute les cases déjà occupées par un regard
        for i, (typ, x, data) in enumerate(cols):
            if typ != 'C':
                continue
            feat = data
            vals = [
                _fmt(_fval(feat['diametre']), '{:.0f}'),
                _fmt(_fval(feat['longueur'])),
                _sval(feat, 'materiau'),
                _fmt(_fval(feat['pente']), '{:.2f}'),
                '',
            ]
            for row_idx, val in enumerate(vals):
                if not val or val == '—':
                    continue
                if (round(x, 1), row_idx) in occupied:
                    continue
                ax.text(x, n_rows - row_idx - 0.5, val,
                        ha='center', va='center',
                        fontsize=_FONT_CART, color='#444444',
                        zorder=3, clip_on=True)

        # Axe X sur le dernier cartouche uniquement
        if show_xaxis:
            ax.xaxis.set_visible(True)
            ax.tick_params(bottom=True, labelbottom=True, labelsize=_FONT_LABEL)
            ax.set_xlabel(i18n.tr('pf_distance_projetee'), fontsize=8, labelpad=2)
        else:
            ax.xaxis.set_visible(False)

    # ------------------------------------------------------------------ export

    def _export(self, fmt):
        try:
            from ..tools.projet_bet import project_dir
            import os
            start_dir = project_dir() or os.path.expanduser("~")
        except Exception:
            import os
            start_dir = os.path.expanduser("~")

        conduites = self.data['conduites']

        def _ends(reseau):
            c_list = [c for c in conduites if c['reseau'] == reseau]
            if not c_list:
                return None, None
            start_c = min(c_list, key=lambda c: c['x0'])
            end_c   = max(c_list, key=lambda c: c['x1'])
            s = start_c.get('nom_r0', '')
            e = end_c.get('nom_r1', '')
            return s.replace(' ', '_') if s else None, e.replace(' ', '_') if e else None

        ep_s, ep_e = _ends('EP')
        eu_s, eu_e = _ends('EU')

        parts = []
        for val in (eu_s, eu_e, ep_s, ep_e):
            if val:
                parts.append(val)
        if not parts:
            parts = ['profil_groupe']
        default_name = '_'.join(parts) + f'_PROFIL.{fmt}'

        path, _ = QFileDialog.getSaveFileName(
            self,
            i18n.tr('pg_exporter_en', format=fmt.upper()),
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
