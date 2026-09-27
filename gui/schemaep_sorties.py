# gui/schemaep_sorties.py
"""Sorties SchemAEP : SVG autonome, impression, pages PDF.

Tout part d'une scène construite hors écran sans les aides d'édition
(points orange, ronds rouges, halo) : `construire_scene(..., edition=False)`.
Les dessins sur QPainter travaillent en pixels du périphérique ; mm() convertit
les millimètres selon sa résolution.
"""
from datetime import date

from qgis.PyQt.QtCore import Qt, QRectF, QPointF, QSizeF, QMarginsF
from qgis.PyQt.QtGui import QColor, QFont, QFontMetricsF, QPageLayout, QPageSize, QPainter, QPen
from qgis.PyQt.QtPrintSupport import QPrinter
from qgis.PyQt.QtWidgets import QGraphicsScene

from ..tools import i18n
from ..tools.schemaep import catalogue as C
from ..tools.schemaep import moteur as M
from ..tools.schemaep import svg_qt
from .schemaep_canevas import Rendus, construire_scene, bornes, couleur, largeur_texte

MARGE_SCENE = 12


def _schema(s):
    return s if isinstance(s, M.Schema) else M.Schema(M.normalize(s))


def _police():
    f = QFont('Arial')
    f.setPixelSize(11)
    return f


def scene_hors_ecran(schema, etiquettes=True):
    """(scène, cadre) d'un schéma, sans aides d'édition."""
    sc = QGraphicsScene()
    construire_scene(sc, _schema(schema), Rendus(), _police(), edition=False, etiquettes=etiquettes)
    bb = bornes(sc)
    if not bb.isNull():
        bb = bb.adjusted(-MARGE_SCENE, -MARGE_SCENE, MARGE_SCENE, MARGE_SCENE)
    return sc, bb


# ---------------------------------------------------------------- SVG
def svg_schema(schema):
    """SVG autonome d'un schéma (pièces, étiquettes, traits de rappel, fond
    blanc), lisible par un navigateur, Inkscape ou une mise en page QGIS."""
    S = _schema(schema)
    rendus = Rendus()
    police = _police()
    obs, corps = [], []
    for it in sorted(S.items, key=lambda i: 0 if C.T[i['t']].back else 1):
        _r, b = rendus.get(it)
        if not C.T[it['t']].back:
            obs.append(M.wbox(it, (b.x(), b.y(), b.width(), b.height())))
        tr = 'translate(%s %s) rotate(%s)%s' % (C.n(C.r1(it['x'])), C.n(C.r1(it['y'])), C.n(it['r']),
                                               ' scale(1 -1)' if it.get('f', 1) < 0 else '')
        corps.append('<g transform="%s">%s</g>' % (tr, svg_qt.styler(svg_qt.dessin(it), couleur(it))))
    for e in M.etiquettes(S.items, obs, largeur_texte(police)):
        if e['lien']:
            ax, ay, px, py = (C.n(C.r1(v)) for v in e['lien'])
            corps.append('<path d="M%s %sL%s %s" style="fill:none;stroke:#8a8a8a;stroke-width:0.8"/>'
                         '<circle cx="%s" cy="%s" r="1.6" style="fill:#8a8a8a"/>' % (ax, ay, px, py, ax, ay))
        # attributs explicites (pas de raccourci « font: » ni de paint-order, ignorés
        # par une partie des logiciels) : liseré blanc dessous, texte dessus
        pos = 'x="%s" y="%s" text-anchor="%s" font-family="Arial, sans-serif" font-size="11"' % (
            C.n(C.r1(e['x'])), C.n(C.r1(e['y'])), e['anc'])
        corps.append('<text %s fill="none" stroke="#ffffff" stroke-width="3" stroke-linejoin="round">%s</text>'
                     '<text %s fill="#333333">%s</text>' % (pos, C.esc(e['txt']), pos, C.esc(e['txt'])))
    _sc, bb = scene_hors_ecran(S)
    if bb.isNull():
        bb = QRectF(-50, -50, 100, 100)
    vb = '%s %s %s %s' % tuple(C.n(C.r1(v)) for v in (bb.x(), bb.y(), bb.width(), bb.height()))
    return ('<svg xmlns="http://www.w3.org/2000/svg" viewBox="%s" width="%d" height="%d">'
            '<rect x="%s" y="%s" width="%s" height="%s" fill="#fff"/>%s</svg>') % (
        vb, round(bb.width()), round(bb.height()),
        C.n(C.r1(bb.x())), C.n(C.r1(bb.y())), C.n(C.r1(bb.width())), C.n(C.r1(bb.height())), ''.join(corps))


# ---------------------------------------------------------------- dessin
class Page:
    """Aide au dessin sur un périphérique (imprimante, PDF) en millimètres."""

    def __init__(self, painter):
        self.p = painter
        dev = painter.device()
        self.k = dev.logicalDpiX() / 25.4

    def mm(self, v):
        return v * self.k

    def police(self, pt, gras=False):
        f = QFont('Arial')
        f.setPointSizeF(pt)
        f.setBold(gras)
        self.p.setFont(f)
        return f

    def metriques(self, pt):
        """Mesures de texte à la résolution du périphérique (et non de l'écran)."""
        return QFontMetricsF(self.police(pt), self.p.device())

    def texte(self, rect, txt, pt=9, gras=False, align=Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
              couleur='#222222'):
        self.police(pt, gras)
        self.p.setPen(QColor(couleur))
        self.p.drawText(rect, int(align | Qt.TextFlag.TextWordWrap), txt)


def dessiner_schema(painter, rect, schema, echelle_max=None):
    """Schéma cadré et centré dans rect (proportions gardées). echelle_max :
    agrandissement maximal (pixels du périphérique par unité de dessin), pour
    que les petits schémas gardent des textes à la même taille que les
    autres. Faux si le schéma est vide."""
    sc, bb = scene_hors_ecran(schema)
    if bb.isNull():
        return False
    s = min(rect.width() / bb.width(), rect.height() / bb.height())
    if echelle_max:
        s = min(s, echelle_max)
    w, h = bb.width() * s, bb.height() * s
    cible = QRectF(rect.center().x() - w / 2, rect.center().y() - h / 2, w, h)
    painter.save()
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    sc.render(painter, cible, bb, Qt.AspectRatioMode.KeepAspectRatio)
    painter.restore()
    return True


def dessiner_nomenclature(pg, rect, lignes, debut=0, pt=8):
    """Tableau Désignation / Qté / U à partir de la ligne debut ; renvoie
    l'indice de la première ligne qui n'a pas tenu (len(lignes) si tout)."""
    p = pg.p
    fm = pg.metriques(pt)
    h_min = fm.height() + pg.mm(1.2)
    wq, wu = pg.mm(16), pg.mm(10)
    wd = rect.width() - wq - wu
    y = rect.top()
    p.setPen(QPen(QColor('#bbbbbb'), 0))

    def ligne(y, d, q, u, entete=False):
        br = fm.boundingRect(QRectF(0, 0, wd - pg.mm(2), 1e6), int(Qt.TextFlag.TextWordWrap), d)
        h = max(h_min, br.height() + pg.mm(1.2))
        if entete:
            p.fillRect(QRectF(rect.left(), y, rect.width(), h), QColor('#eef2f8'))
        cellules = ((rect.left(), wd, d, Qt.AlignmentFlag.AlignLeft),
                    (rect.left() + wd, wq, q, Qt.AlignmentFlag.AlignRight),
                    (rect.left() + wd + wq, wu, u, Qt.AlignmentFlag.AlignLeft))
        for x, w, t, al in cellules:
            r = QRectF(x, y, w, h)
            p.setPen(QPen(QColor('#bbbbbb'), 0))
            p.drawRect(r)
            pg.texte(r.adjusted(pg.mm(1), 0, -pg.mm(1), 0), t, pt, entete, al | Qt.AlignmentFlag.AlignVCenter)
        return h

    y += ligne(y, i18n.tr('se_designation'), i18n.tr('se_qte'), 'U', True)
    i = debut
    while i < len(lignes):
        b = lignes[i]
        br = fm.boundingRect(QRectF(0, 0, wd - pg.mm(2), 1e6), int(Qt.TextFlag.TextWordWrap), b['d'])
        if y + max(h_min, br.height() + pg.mm(1.2)) > rect.bottom():
            break
        y += ligne(y, b['d'], M.fq(b['q']), b['u'])
        i += 1
    return i


def page_impression(painter, titre, schema):
    """Page d'impression d'un schéma : titre, dessin, nomenclature, pied."""
    pg = Page(painter)
    vp = QRectF(painter.viewport())
    m = pg.mm(10)
    zone = vp.adjusted(m, m, -m, -m)
    pg.texte(QRectF(zone.left(), zone.top(), zone.width(), pg.mm(8)), titre or i18n.tr('se_schema_aep'), 13, True)
    haut = zone.top() + pg.mm(10)
    lignes = M.bom(_schema(schema).items)
    paysage = zone.width() > zone.height()
    if paysage:
        wn = zone.width() * 0.38
        r_s = QRectF(zone.left(), haut, zone.width() - wn - pg.mm(6), zone.bottom() - haut - pg.mm(8))
        r_n = QRectF(r_s.right() + pg.mm(6), haut, wn, r_s.height())
    else:
        r_s = QRectF(zone.left(), haut, zone.width(), (zone.bottom() - haut) * 0.55)
        r_n = QRectF(zone.left(), r_s.bottom() + pg.mm(6), zone.width(), zone.bottom() - r_s.bottom() - pg.mm(14))
    dessiner_schema(painter, r_s, schema, pg.mm(0.6))
    if lignes:
        dessiner_nomenclature(pg, r_n, lignes)
    pg.texte(QRectF(zone.left(), zone.bottom() - pg.mm(6), zone.width(), pg.mm(6)),
             'SchemAEP – %s' % date.today().strftime('%d/%m/%Y'), 7,
             align=Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter, couleur='#777777')


# ---------------------------------------------------------------- PDF « 6 par page »
def _imprimante_pdf(chemin, paysage=False):
    pr = QPrinter(QPrinter.PrinterMode.HighResolution)
    pr.setOutputFormat(QPrinter.OutputFormat.PdfFormat)
    pr.setOutputFileName(chemin)
    pr.setPageLayout(QPageLayout(QPageSize(QPageSize.PageSizeId.A4),
                                 QPageLayout.Orientation.Landscape if paysage else QPageLayout.Orientation.Portrait,
                                 QMarginsF(0, 0, 0, 0)))
    pr.setFullPage(True)
    return pr


def pdf_schemas(chemin, entrees, projet=''):
    """PDF A4 portrait : 6 schémas par page (2 × 3), puis la nomenclature de
    chaque nœud et le listing total des pièces. entrees : [(titre,
    sous-titre, schéma dict)]. Renvoie le nombre de pages."""
    if not entrees:
        return 0
    pr = _imprimante_pdf(chemin)
    painter = QPainter(pr)
    pg = Page(painter)
    W, H = pg.mm(210), pg.mm(297)
    m = pg.mm(10)
    pages = [0]
    jour = date.today().strftime('%d/%m/%Y')

    def pied():
        pages[0] += 1
        pg.texte(QRectF(m, H - m - pg.mm(5), W - 2 * m, pg.mm(5)),
                 i18n.tr('se_pied') % (projet or i18n.tr('se_projet'), jour), 7, couleur='#777777')
        pg.texte(QRectF(m, H - m - pg.mm(5), W - 2 * m, pg.mm(5)), i18n.tr('se_page') % pages[0], 7,
                 align=Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter, couleur='#777777')

    def nouvelle():
        if pages[0]:
            pr.newPage()

    zone = QRectF(m, m, W - 2 * m, H - 2 * m - pg.mm(8))
    cw, ch = zone.width() / 2, zone.height() / 3
    for n0 in range(0, len(entrees), 6):
        nouvelle()
        for k, (titre, sous, s) in enumerate(entrees[n0:n0 + 6]):
            c = QRectF(zone.left() + (k % 2) * cw, zone.top() + (k // 2) * ch, cw, ch).adjusted(
                pg.mm(2), pg.mm(2), -pg.mm(2), -pg.mm(2))
            painter.setPen(QPen(QColor('#9aa0b0'), 0))
            painter.drawRect(c)
            pg.texte(QRectF(c.left() + pg.mm(2), c.top() + pg.mm(1), c.width() - pg.mm(4), pg.mm(6)), titre, 10, True)
            pg.texte(QRectF(c.left() + pg.mm(2), c.top() + pg.mm(6.5), c.width() - pg.mm(4), pg.mm(5)), sous, 8,
                     couleur='#555555')
            dessiner_schema(painter, c.adjusted(pg.mm(2), pg.mm(12), -pg.mm(2), -pg.mm(2)), s, pg.mm(0.3))
        pied()
    def section(titre_section, groupes):
        """Nouvelle page, titre, puis tableaux enchaînés ; groupes :
        [(titre, sous-titre, lignes de nomenclature)]."""
        nouvelle()
        y = zone.top()
        pg.texte(QRectF(m, y, zone.width(), pg.mm(8)), titre_section, 13, True)
        y += pg.mm(11)
        for titre, sous, lignes in groupes:
            i = 0
            while True:
                if y > zone.bottom() - pg.mm(20):
                    pied()
                    pr.newPage()
                    y = zone.top()
                pg.texte(QRectF(m, y, zone.width(), pg.mm(6)), titre + (i18n.tr('se_suite') if i else '') + ('  –  ' + sous if sous else ''), 10, True)
                y += pg.mm(7)
                if not lignes:
                    pg.texte(QRectF(m, y, zone.width(), pg.mm(5)), i18n.tr('se_aucune_piece'), 8, couleur='#777777')
                    y += pg.mm(8)
                    break
                r = QRectF(m, y, zone.width(), zone.bottom() - y)
                j = dessiner_nomenclature(pg, r, lignes, i)
                if j >= len(lignes):
                    y += _hauteur_tableau(pg, zone.width(), lignes[i:j]) + pg.mm(6)
                    break
                i = j
                y = zone.bottom() + 1     # page suivante
        pied()

    # nomenclature par nœud, tableaux enchaînés
    section(i18n.tr('se_nomenc_par_noeud'),
            [(titre, sous, M.bom(_schema(s).items)) for titre, sous, s in entrees])
    # listing total : toutes les pièces de tous les nœuds, regroupées
    tout = [it for _t, _s, s in entrees for it in _schema(s).items]
    n = len(entrees)
    section(i18n.tr('se_listing_total'),
            [(i18n.tr('se_total'), i18n.tr('se_n_noeud_n' if n > 1 else 'se_n_noeud_1', n=n), M.bom(tout))])
    painter.end()
    return pages[0]


def _hauteur_tableau(pg, largeur, lignes, pt=8):
    fm = pg.metriques(pt)
    h_min = fm.height() + pg.mm(1.2)
    wd = largeur - pg.mm(26) - pg.mm(2)
    h = h_min
    for b in lignes:
        br = fm.boundingRect(QRectF(0, 0, wd, 1e6), int(Qt.TextFlag.TextWordWrap), b['d'])
        h += max(h_min, br.height() + pg.mm(1.2))
    return h
