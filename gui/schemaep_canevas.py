# gui/schemaep_canevas.py
"""Zone de dessin SchemAEP : scène Qt reconstruite depuis le schéma.

Comme la page HTML, la scène est entièrement redessinée après chaque
modification (quelques centaines d'éléments au plus). La souris est gérée
au niveau de la vue, pas des éléments : un élément peut donc être recréé en
plein glisser sans perdre la souris.

Souris : clic sur un point orange = point de raccordement ; clic sur une
pièce = sélection, glisser = déplacer l'ensemble raccordé (Alt : pièce seule,
Maj : sans grille), avec accroche sur l'extrémité libre la plus proche ;
glisser une étiquette = la déplacer, double-clic = placement automatique ;
glisser le fond = déplacer la vue ; molette = zoom ; rond rouge = valider le
défaut.
"""
import json
import math

from qgis.PyQt.QtCore import Qt, QRectF, QPointF, QByteArray, pyqtSignal
from qgis.PyQt.QtGui import (QBrush, QColor, QFont, QFontMetricsF, QPainter, QPainterPath,
                             QPainterPathStroker, QPen, QTransform)
from qgis.PyQt.QtSvg import QSvgRenderer
from qgis.PyQt.QtWidgets import (QGraphicsEllipseItem, QGraphicsItem, QGraphicsLineItem,
                                 QGraphicsScene, QGraphicsView)

from ..tools import i18n
from ..tools.schemaep import catalogue as C
from ..tools.schemaep import moteur as M
from ..tools.schemaep import svg_qt
from ..tools.schemaep.langue import definir_langue, traduire

# catalogue affiché dans la langue de CanaPlan (moteur et fichiers en français)
definir_langue(i18n.langue)

ROLE = 0          # clé de data() : ('piece', id) / ('port', id, n°) / ('defaut', clé) / ('etiq', id)
Z_REGARD, Z_PIECE, Z_ETIQ, Z_DEFAUT, Z_PORT = -10, 0, 10, 20, 30
ETENDUE = 2000    # demi-côté du viewBox des dessins de pièce
GRILLE = 20
ZMIN, ZMAX = 0.15, 5.0


def couleur(it):
    """Couleur d'une pièce : celle du matériau, sinon celle de sa famille."""
    m = it['p'].get('mat')
    if m and m in C.MAT:
        return C.MAT[m]['col']
    return C.FCOL.get(C.T[it['t']].fam, '#333333')


class Rendus:
    """Cache des dessins de pièces (QSvgRenderer) par apparence."""

    def __init__(self):
        self._c = {}

    def get(self, it, halo=False):
        cle = (it['t'], json.dumps(it['p'], sort_keys=True), json.dumps(it.get('eo') or {}, sort_keys=True), halo)
        r = self._c.get(cle)
        if r is None:
            if len(self._c) > 3000:
                self._c.clear()
            frag = svg_qt.dessin(it)
            doc = svg_qt.document(frag, '#ff9800' if halo else couleur(it), 4 if halo else 0)
            doc = doc.replace('viewBox="-500 -500 1000 1000"',
                              'viewBox="%d %d %d %d"' % (-ETENDUE, -ETENDUE, 2 * ETENDUE, 2 * ETENDUE))
            rend = QSvgRenderer(QByteArray(doc.encode('utf-8')))
            b = rend.boundsOnElement('g')
            if b.isEmpty():
                b = self._bornes_texte(it)
            r = (rend, b)
            self._c[cle] = r
        return r

    @staticmethod
    def _bornes_texte(it):
        """QSvgRenderer ignore les textes dans l'encombrement : estimation
        pour les pièces qui ne sont que du texte (note libre)."""
        p = it['p']
        sz = C.num(p.get('sz')) or 12
        w = max(10, len(str(p.get('txt') or '')) * sz * 0.55)
        return QRectF(-w / 2, -sz, w, sz * 1.3)


class _Piece(QGraphicsItem):
    def __init__(self, it, rendus, halo):
        super().__init__()
        self.it = it
        self.rend, self.b = rendus.get(it)
        self.halo = rendus.get(it, True)[0] if halo else None
        self.back = C.T[it['t']].back
        t = QTransform()
        t.translate(it['x'], it['y'])
        t.rotate(it['r'])
        if it.get('f', 1) < 0:
            t.scale(1, -1)
        self.setTransform(t)
        self.setZValue(Z_REGARD if self.back else Z_PIECE)
        self.setData(ROLE, ('piece', it['id']))

    def boundingRect(self):
        return self.b.adjusted(-8, -8, 8, 8)

    def shape(self):
        """Zone cliquable : l'encombrement + 5, ou seulement le bord pour un
        cadre de regard (on sélectionne ainsi ce qu'il contient)."""
        r = self.b.adjusted(-5, -5, 5, 5)
        p = QPainterPath()
        p.addRect(r)
        if self.back:
            s = QPainterPathStroker()
            s.setWidth(10)
            return s.createStroke(p)
        return p

    def paint(self, painter, option, widget=None):
        cadre = QRectF(-ETENDUE, -ETENDUE, 2 * ETENDUE, 2 * ETENDUE)
        if self.halo:
            self.halo.render(painter, cadre)
        self.rend.render(painter, cadre)


class _Etiquette(QGraphicsItem):
    """Texte avec liseré blanc (lisible sur les traits)."""

    def __init__(self, e, font):
        super().__init__()
        fm = QFontMetricsF(font)
        w = fm.horizontalAdvance(e['txt']) if hasattr(fm, 'horizontalAdvance') else fm.width(e['txt'])
        x = e['x'] - (0 if e['anc'] == 'start' else w if e['anc'] == 'end' else w / 2)
        self.path = QPainterPath()
        self.path.addText(QPointF(x, e['y']), font, e['txt'])
        self.man = e['man']
        self.setZValue(Z_ETIQ)
        self.setData(ROLE, ('etiq', e['id']))

    def boundingRect(self):
        return self.path.boundingRect().adjusted(-3, -3, 3, 3)

    def shape(self):
        p = QPainterPath()
        p.addRect(self.path.boundingRect().adjusted(-2, -2, 2, 2))
        return p

    def paint(self, painter, option, widget=None):
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        pen = QPen(QColor('#ffffff'), 3)
        pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
        painter.strokePath(self.path, pen)
        painter.fillPath(self.path, QBrush(QColor('#333333')))



def largeur_texte(police):
    fm = QFontMetricsF(police)
    if hasattr(fm, 'horizontalAdvance'):
        return fm.horizontalAdvance
    return fm.width


def construire_scene(sc, S, rendus, police, edition=True, etiquettes=True):
    """Remplit la scène sc avec le schéma S (moteur.Schema). edition=False
    (impression, export) : ni points orange, ni ronds rouges, ni halo de
    sélection. Renvoie les décalages d'étiquettes {id: (dx, dy)}."""
    sc.clear()
    G = S.graphe()
    sel = S.sel if edition else None
    obs = []
    for it in sorted(S.items, key=lambda i: 0 if C.T[i['t']].back else 1):
        est_sel = bool(sel and sel['id'] == it['id'])
        g = _Piece(it, rendus, est_sel and sel.get('port') is None)
        sc.addItem(g)
        if not C.T[it['t']].back:
            b = g.b
            obs.append(M.wbox(it, (b.x(), b.y(), b.width(), b.height())))
        if not edition:
            continue
        for q in M.wp(it):
            if G.libre(it, q):
                on = est_sel and sel.get('port') == q['i']
                r = 6.5 if on else 4.5
                e = QGraphicsEllipseItem(q['wx'] - r, q['wy'] - r, 2 * r, 2 * r)
                e.setPen(QPen(QColor('#e65100'), 1.5))
                e.setBrush(QColor('#ff9800' if on else '#ffffff'))
                e.setZValue(Z_PORT)
                e.setData(ROLE, ('port', it['id'], q['i']))
                e.setToolTip(i18n.tr('se_ext_libre') % traduire(C.ENDN.get(q['k'], '')))
                sc.addItem(e)
    if edition:
        for k, m, x, y in S.defauts(G)[0]:
            e = QGraphicsEllipseItem(x - 10, y - 10, 20, 20)
            e.setPen(QPen(QColor('#d50000'), 2))
            e.setBrush(QColor(0, 0, 0, 0))
            e.setZValue(Z_DEFAUT)
            e.setData(ROLE, ('defaut', k))
            e.setToolTip(traduire(m) + i18n.tr('se_cliquer_valider'))
            sc.addItem(e)
    pos = {}
    if etiquettes:
        for e in M.etiquettes(S.items, obs, largeur_texte(police)):
            pos[e['id']] = (e['dx'], e['dy'])
            if e['lien']:
                ax, ay, px, py = e['lien']
                ln = QGraphicsLineItem(ax, ay, px, py)
                ln.setPen(QPen(QColor('#8a8a8a'), 0.8))
                ln.setZValue(Z_ETIQ - 1)
                sc.addItem(ln)
                d = QGraphicsEllipseItem(ax - 1.6, ay - 1.6, 3.2, 3.2)
                d.setPen(QPen(Qt.PenStyle.NoPen))
                d.setBrush(QColor('#8a8a8a'))
                d.setZValue(Z_ETIQ - 1)
                sc.addItem(d)
            sc.addItem(_Etiquette(e, police))
    return pos


def bornes(sc):
    """Encombrement des pièces et étiquettes d'une scène (QRectF vide sinon)."""
    bb = QRectF()
    for g in sc.items():
        d = g.data(ROLE)
        if d and d[0] in ('piece', 'etiq'):
            bb = bb.united(g.sceneBoundingRect()) if not bb.isNull() else g.sceneBoundingRect()
    return bb


class Canevas(QGraphicsView):
    """Vue d'édition d'un moteur.Schema."""

    modifie = pyqtSignal()        # le schéma a changé (panneaux à rafraîchir)
    selection = pyqtSignal()      # la sélection a changé
    message = pyqtSignal(str)     # texte d'aide contextuel

    def __init__(self, schema=None, parent=None):
        super().__init__(parent)
        self.schema = schema or M.Schema()
        self.etiquettes_visibles = True
        self.rendus = Rendus()
        self.police = QFont('Arial')
        self.police.setPixelSize(11)
        self._etiq_pos = {}      # id → décalage affiché (départ d'un glisser d'étiquette)
        self._drag = None
        self.setScene(QGraphicsScene(self))
        self.scene().setSceneRect(-50000, -50000, 100000, 100000)
        self.setRenderHints(QPainter.RenderHint.Antialiasing | QPainter.RenderHint.TextAntialiasing
                            | QPainter.RenderHint.SmoothPixmapTransform)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setTransformationAnchor(QGraphicsView.ViewportAnchor.NoAnchor)
        self.setResizeAnchor(QGraphicsView.ViewportAnchor.AnchorViewCenter)
        self.setViewportUpdateMode(QGraphicsView.ViewportUpdateMode.FullViewportUpdate)
        self.setMouseTracking(True)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setBackgroundBrush(QColor('#ffffff'))
        self.centerOn(0, 0)

    # ------------------------------------------------------------ rendu
    def zoom(self):
        return self.transform().m11()

    def centre_vue(self):
        c = self.mapToScene(self.viewport().rect().center())
        return (round(c.x() / 10) * 10, round(c.y() / 10) * 10)

    def rafraichir(self, complet=True):
        """Reconstruit la scène. complet=False pendant un glisser : les
        panneaux ne sont pas prévenus."""
        self._etiq_pos = construire_scene(self.scene(), self.schema, self.rendus, self.police,
                                          edition=True, etiquettes=self.etiquettes_visibles)
        self.message.emit(self.aide())
        if complet:
            self.modifie.emit()

    def aide(self):
        S = self.schema
        if S.sel and S.sel.get('port') is not None:
            return i18n.tr('se_aide_point')
        if S.sel:
            return (i18n.tr('se_aide_sel'))
        return (i18n.tr('se_aide_vide'))

    def drawBackground(self, painter, rect):
        painter.fillRect(rect, QColor('#ffffff'))
        if self.zoom() * GRILLE < 6:
            return
        painter.setPen(QPen(QColor('#edf0f5'), 0))
        x = math.floor(rect.left() / GRILLE) * GRILLE
        while x < rect.right():
            painter.drawLine(QPointF(x, rect.top()), QPointF(x, rect.bottom()))
            x += GRILLE
        y = math.floor(rect.top() / GRILLE) * GRILLE
        while y < rect.bottom():
            painter.drawLine(QPointF(rect.left(), y), QPointF(rect.right(), y))
            y += GRILLE

    # ------------------------------------------------------------ vue
    def recentrer(self):
        """Cadre tout le schéma (zoom entre 0,15 et 2,5)."""
        bb = bornes(self.scene())
        if bb.isNull():
            self.setTransform(QTransform())
            self.centerOn(0, 0)
            return
        vw, vh = self.viewport().width(), self.viewport().height()
        z = min(2.5, max(ZMIN, min((vw - 80) / max(bb.width(), 1), (vh - 80) / max(bb.height(), 1))))
        self.setTransform(QTransform.fromScale(z, z))
        self.centerOn(bb.center())

    def wheelEvent(self, e):
        d = e.angleDelta().y()
        if not d:
            return
        z0 = self.zoom()
        z = min(ZMAX, max(ZMIN, z0 * math.exp(d * 0.0015)))
        p = _pos(e)
        avant = self.mapToScene(p.toPoint())
        self.setTransform(QTransform.fromScale(z, z))
        apres = self.mapToScene(p.toPoint())
        self._decaler(apres - avant)

    def _decaler(self, delta):
        """Déplace la vue pour que le point sous la souris reste en place."""
        c = self.mapToScene(self.viewport().rect().center())
        self.centerOn(c - delta)

    # ------------------------------------------------------------ souris
    def _cible(self, pos):
        for g in self.items(pos):
            d = g.data(ROLE)
            if d:
                return d
        return None

    def mousePressEvent(self, e):
        if e.button() != Qt.MouseButton.LeftButton:
            return super().mousePressEvent(e)
        S = self.schema
        pos = _pos(e).toPoint()
        w = self.mapToScene(pos)
        cible = self._cible(pos)
        if cible and cible[0] == 'port':
            S.sel = {'id': cible[1], 'port': cible[2]}
            self._drag = None
            self.rafraichir(False)
            self.selection.emit()
            return
        if cible and cible[0] == 'defaut':
            S.valider([cible[1]])
            self._drag = None
            self.rafraichir()
            return
        if cible and cible[0] == 'etiq':
            it = S.get(cible[1])
            if it:
                o = self._etiq_pos.get(it['id'], (0, 0))
                self._drag = {'m': 'lbl', 'it': it, 'sx': w.x(), 'sy': w.y(), 'ox': o[0], 'oy': o[1],
                              'moved': False, 'snap': json.dumps(S.s)}
            return
        if cible and cible[0] == 'piece':
            id_ = cible[1]
            S.sel = {'id': id_, 'port': None}
            G = S.graphe()
            alt = bool(e.modifiers() & Qt.KeyboardModifier.AltModifier)
            ids = {id_} if alt else M.comp([id_], None, G)
            # extrémités libres pour l'accroche : celles du groupe déplacé (mine) et des autres pièces (oth, en grille)
            tol = 12 / self.zoom()
            inner = set()
            for a, b in G.L:
                if (a[0]['id'] in ids) == (b[0]['id'] in ids):
                    inner.add(M.cle(*a))
                    inner.add(M.cle(*b))
            mine, oth = [], {}
            for it in S.items:
                for q in M.wp(it):
                    if M.cle(it, q) in inner:
                        continue
                    if it['id'] in ids:
                        mine.append(q)
                    else:
                        oth.setdefault((math.floor(q['wx'] / tol), math.floor(q['wy'] / tol)), []).append(q)
            self._drag = {'m': 'item', 'sx': w.x(), 'sy': w.y(),
                          'orig': [(i, i['x'], i['y']) for i in S.items if i['id'] in ids],
                          'moved': False, 'snap': json.dumps(S.s), 'tol': tol, 'mine': mine, 'oth': oth}
            self.rafraichir(False)
            self.selection.emit()
            return
        self._drag = {'m': 'pan', 'x': pos.x(), 'y': pos.y(), 'c': self.mapToScene(self.viewport().rect().center()),
                      'moved': False}

    def mouseMoveEvent(self, e):
        d = self._drag
        if not d:
            return super().mouseMoveEvent(e)
        pos = _pos(e)
        if d['m'] == 'pan':
            dx, dy = pos.x() - d['x'], pos.y() - d['y']
            if abs(dx) + abs(dy) > 3:
                d['moved'] = True
            z = self.zoom()
            self.centerOn(d['c'] - QPointF(dx / z, dy / z))
            return
        w = self.mapToScene(pos.toPoint())
        dx, dy = w.x() - d['sx'], w.y() - d['sy']
        S = self.schema
        if not d['moved']:
            if math.hypot(dx, dy) * self.zoom() < 3:
                return
            S.undo.append(d['snap'])
            if len(S.undo) > S.ANNUL_MAX:
                S.undo.pop(0)
            d['moved'] = True
        if d['m'] == 'lbl':
            d['it']['lo'] = [C.r1(d['ox'] + dx), C.r1(d['oy'] + dy)]
            self.rafraichir(False)
            return
        sn = self._accroche(dx, dy)
        if sn:
            dx, dy = sn
        elif not (e.modifiers() & Qt.KeyboardModifier.ShiftModifier):
            dx, dy = round(dx / 10) * 10, round(dy / 10) * 10
        for it, x, y in d['orig']:
            it['x'], it['y'] = x + dx, y + dy
        self.rafraichir(False)

    def _accroche(self, dx, dy):
        """Décalage qui amène une extrémité libre du groupe exactement sur le
        point libre le plus proche (None si aucun à portée)."""
        d = self._drag
        t = d['tol']
        best, bd = None, t
        for m in d['mine']:
            x, y = m['wx'] + dx, m['wy'] + dy
            cx, cy = math.floor(x / t), math.floor(y / t)
            for i in (-1, 0, 1):
                for j in (-1, 0, 1):
                    for o in d['oth'].get((cx + i, cy + j), ()):
                        dd = math.hypot(o['wx'] - x, o['wy'] - y)
                        if dd < bd:
                            bd, best = dd, (o['wx'] - m['wx'], o['wy'] - m['wy'])
        return best

    def mouseReleaseEvent(self, e):
        d, self._drag = self._drag, None
        if not d:
            return super().mouseReleaseEvent(e)
        S = self.schema
        if d['m'] == 'pan':
            if not d['moved']:
                S.sel = None
                self.rafraichir(False)
                self.selection.emit()
        elif d['moved']:
            self.rafraichir()
        elif d['m'] == 'lbl':     # simple clic sur une étiquette : sélectionne sa pièce
            S.sel = {'id': d['it']['id'], 'port': None}
            self.rafraichir(False)
            self.selection.emit()

    def mouseDoubleClickEvent(self, e):
        """Double-clic sur une étiquette : retour au placement automatique."""
        cible = self._cible(_pos(e).toPoint())
        if cible and cible[0] == 'etiq':
            it = self.schema.get(cible[1])
            if it and it.get('lo'):
                self.schema.snap()
                it.pop('lo')
                self.rafraichir()
            return
        self.mousePressEvent(e)

    # ------------------------------------------------------------ clavier
    def keyPressEvent(self, e):
        S = self.schema
        k = e.key()
        if k == Qt.Key.Key_Z and e.modifiers() & Qt.KeyboardModifier.ControlModifier:
            if S.annuler():
                self.rafraichir()
                self.selection.emit()
            return
        if not S.sel:
            return super().keyPressEvent(e)
        if k in (Qt.Key.Key_Delete, Qt.Key.Key_Backspace):
            S.action('del')
        elif k == Qt.Key.Key_R:
            S.action('rotm90' if e.modifiers() & Qt.KeyboardModifier.ShiftModifier else 'rot90')
        elif k == Qt.Key.Key_Escape:
            S.sel = None
            self.rafraichir(False)
            self.selection.emit()
            return
        else:
            return super().keyPressEvent(e)
        self.rafraichir()
        self.selection.emit()


def _pos(e):
    """Position de la souris dans la vue (Qt5 et Qt6)."""
    if hasattr(e, 'position'):
        return e.position()
    if hasattr(e, 'localPos'):
        return e.localPos()
    return QPointF(e.posF())
