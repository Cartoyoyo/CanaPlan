# gui/schemaep_panneau.py
"""Panneau de droite SchemAEP : propriétés de la pièce, point sélectionné et
choix de ses extrémités, contrôle des assemblages, nomenclature, légende.

Le panneau est reconstruit à chaque changement, comme la page HTML ; la
partie « propriétés » ne l'est que si la pièce ou ses valeurs ont changé,
pour ne pas perdre la saisie en cours.
"""
import json

from qgis.PyQt.QtCore import Qt, QByteArray, QRectF, QSize, QTimer, pyqtSignal
from qgis.PyQt.QtGui import QColor, QPainter, QPixmap
from qgis.PyQt.QtSvg import QSvgRenderer
from qgis.PyQt.QtWidgets import (QCheckBox, QComboBox, QDoubleSpinBox, QFrame, QGridLayout, QHBoxLayout,
                                 QHeaderView, QLabel, QLineEdit, QPushButton, QScrollArea, QSizePolicy,
                                 QTableWidget, QTableWidgetItem, QToolButton, QVBoxLayout, QWidget)

from ..tools import i18n
from ..tools.schemaep import catalogue as C
from ..tools.schemaep import moteur as M
from ..tools.schemaep import svg_qt
from ..tools.schemaep.langue import traduire

BLEU = '#0d47a1'


def pixmap_extremite(k, verrou, taille=QSize(44, 22)):
    """Symbole d'extrémité de la légende (trait + extrémité k)."""
    frag = '<path d="M0 0H30"/>' + C.mark({'x': 30, 'y': 0, 'd': 0, 'k': k}, verrou)
    doc = ('<svg xmlns="http://www.w3.org/2000/svg" viewBox="-2 -11 46 22">%s</svg>'
           % svg_qt.styler(frag, '#333333'))
    pm = QPixmap(taille * 2)
    pm.setDevicePixelRatio(2)
    pm.fill(Qt.GlobalColor.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    QSvgRenderer(QByteArray(doc.encode('utf-8'))).render(p, QRectF(0, 0, taille.width(), taille.height()))
    p.end()
    return pm


def _legende():
    """(type, verrouillé, libellé traduit) des extrémités."""
    return ([(k, False, traduire(txt)) for k, txt in C.ENDN.items()]
            + [('E', True, traduire('emboîtement verrouillé'))])


class _LigneLegende(QFrame):
    """Ligne de légende ; cliquable dans l'encadré du point sélectionné."""
    clic = pyqtSignal(str, bool)

    def __init__(self, k, verrou, txt, actif=False, cliquable=False):
        super().__init__()
        self.k, self.verrou, self.cliquable = k, verrou, cliquable
        h = QHBoxLayout(self)
        h.setContentsMargins(2, 0, 2, 0)
        h.setSpacing(4)
        ic = QLabel()
        ic.setPixmap(pixmap_extremite(k, verrou))
        lb = QLabel(txt)
        lb.setWordWrap(True)
        h.addWidget(ic)
        h.addWidget(lb, 1)
        fond = '#ffe0b2' if actif else 'transparent'
        survol = '#ffffff' if cliquable else fond
        self.setStyleSheet('_LigneLegende{background:%s;border-radius:3px} _LigneLegende:hover{background:%s}'
                           % (fond, survol))
        if cliquable:
            self.setCursor(Qt.CursorShape.PointingHandCursor)
            self.setToolTip(i18n.tr('se_appliquer_point'))

    def mousePressEvent(self, e):
        if self.cliquable and e.button() == Qt.MouseButton.LeftButton:
            self.clic.emit(self.k, self.verrou)


def _titre(txt):
    lb = QLabel(txt)
    lb.setStyleSheet('font-weight:bold;color:%s;border-bottom:1px solid #e0e5ee;padding:8px 0 3px 0' % BLEU)
    return lb


class Panneau(QScrollArea):
    """Panneau lié à un Canevas (schéma + rafraîchissement)."""

    montage = pyqtSignal()     # « ★ Montage » : enregistrer l'ensemble raccordé en favori

    def __init__(self, canevas, parent=None):
        super().__init__(parent)
        self.cv = canevas
        self.setWidgetResizable(True)
        self.setMinimumWidth(300)
        self.msg_point = ''
        self._sig_props = None
        self._props = None
        self._focus = None
        self._okd_ouvert = False
        self._construire()

    # ------------------------------------------------------------ construction
    def _construire(self):
        w = QWidget()
        self.lay = QVBoxLayout(w)
        self.lay.setContentsMargins(10, 6, 10, 20)
        self.zone_props = QVBoxLayout()
        self.zone_bas = QVBoxLayout()
        self.lay.addLayout(self.zone_props)
        self.lay.addLayout(self.zone_bas)
        self.lay.addStretch(1)
        self.setWidget(w)

    def rafraichir(self):
        S = self.cv.schema
        it = S.cur()
        sig = json.dumps([S.sel, it, self.msg_point], sort_keys=True, default=str)
        if sig != self._sig_props:
            self._sig_props = sig
            self._vider(self.zone_props)
            self.zone_props.addWidget(self._section_props())
            self._rendre_focus()
        self._vider(self.zone_bas)
        G = S.graphe()
        self.zone_bas.addWidget(self._section_controle(G))
        self.zone_bas.addWidget(self._section_nomenclature())
        self.zone_bas.addWidget(self._section_legende())

    @staticmethod
    def _vider(lay):
        while lay.count():
            w = lay.takeAt(0).widget()
            if w:
                w.hide()
                w.setParent(None)
                w.deleteLater()

    def _appliquer(self, fn):
        """Modifie le schéma puis redessine (différé : le widget à l'origine
        du signal peut être détruit par la reconstruction)."""
        fn()
        QTimer.singleShot(0, self.cv.rafraichir)

    # ------------------------------------------------------------ propriétés
    def _section_props(self):
        S = self.cv.schema
        it = S.cur()
        box = QWidget()
        v = QVBoxLayout(box)
        v.setContentsMargins(0, 0, 0, 0)
        if not it:
            v.addWidget(_titre(i18n.tr('se_mode_emploi_titre')))
            lb = QLabel(i18n.tr('se_mode_emploi'))
            lb.setWordWrap(True)
            v.addWidget(lb)
            return box
        t = C.T[it['t']]
        port = S.sel.get('port')
        if port is not None:
            ps = M.wp(it)
            if port < len(ps):
                v.addWidget(self._encadre_point(it, ps[port]))
        self.msg_point = ''
        v.addWidget(_titre('%s  <span style="color:#777;font-weight:normal">#%s</span>' % (C.esc(traduire(t.nom)), it['id'])))
        grille = QGridLayout()
        grille.setColumnStretch(1, 1)
        for r, f in enumerate(t.fields):
            grille.addWidget(QLabel(traduire(f['l'])), r, 0)
            grille.addWidget(self._champ(it, f), r, 1)
        v.addLayout(grille)
        v.addLayout(self._boutons(it))
        return box

    def _encadre_point(self, it, q):
        S = self.cv.schema
        fr = QFrame()
        fr.setStyleSheet('QFrame#pinfo{background:#fff3e0;border:1px solid #ffcc80;border-radius:4px}')
        fr.setObjectName('pinfo')
        v = QVBoxLayout(fr)
        v.setContentsMargins(6, 6, 6, 6)
        txt = i18n.tr('se_point_sel_html') % traduire(C.ENDN.get(q['k'], ''))
        if q.get('dn') and not q.get('any'):
            txt += ' – %s %s' % (C.fdn(q['mat'], q['dn']), traduire(C.MAT[q['mat']]['nom']))
        lb = QLabel(txt)
        lb.setWordWrap(True)
        v.addWidget(lb)
        g = QGridLayout()
        g.setSpacing(1)
        vr = bool(it['p'].get('verr'))
        for n_, (k, verrou, libelle) in enumerate(_legende()):
            actif = q['k'] == k and (verrou == vr if k == 'E' else True)
            ligne = _LigneLegende(k, verrou, libelle, actif, True)
            ligne.clic.connect(self._imposer)
            g.addWidget(ligne, n_ // 2, n_ % 2)
        v.addLayout(g)
        if (it.get('eo') or {}).get(str(S.sel['port'])):
            h = QLabel(i18n.tr('se_ext_imposee_html'))
            h.setWordWrap(True)
            h.linkActivated.connect(lambda _l: self._appliquer(S.revenir_catalogue))
            v.addWidget(h)
        aide = QLabel(i18n.tr('se_aide_raccorder_html'))
        aide.setWordWrap(True)
        v.addWidget(aide)
        if self.msg_point:
            m = QLabel(traduire(self.msg_point))
            m.setStyleSheet('color:#b71c1c')
            m.setWordWrap(True)
            v.addWidget(m)
        return fr

    def _imposer(self, k, verrou):
        S = self.cv.schema
        self.msg_point = S.imposer_extremite(k, verrou)
        self._sig_props = None
        QTimer.singleShot(0, self.cv.rafraichir)

    def _champ(self, it, f):
        S = self.cv.schema
        val = it['p'].get(f['k'])
        k = f['k']

        def fixer(v):
            self._focus = k
            self._appliquer(lambda: S.modifier(it, k, v))
        if f['t'] == 'chk':
            w = QCheckBox()
            w.setChecked(bool(val))
            w.toggled.connect(fixer)
        elif f['t'] in ('dn', 'sel', 'mat'):
            w = QComboBox()
            opts = C.opt_list(it['p'], f) or []
            for v_, lib in opts:
                w.addItem(traduire(str(lib)), v_)
            idx = next((i for i, (v_, _l) in enumerate(opts) if C.egal(v_, val)), -1)
            w.setCurrentIndex(idx)
            w.activated.connect(lambda i, w=w: fixer(w.itemData(i)))
        elif f['t'] == 'num':
            w = QDoubleSpinBox()
            w.setRange(0, 1e6)
            st = f.get('st') or 1
            w.setDecimals(2 if st < 0.1 else 1 if st < 1 else 2)
            w.setSingleStep(st)
            w.setKeyboardTracking(False)
            w.setValue(float(C.num(val)))
            w.valueChanged.connect(fixer)
        else:
            w = QLineEdit(str(val if val is not None else ''))
            w.editingFinished.connect(lambda w=w: w.text() != str(it['p'].get(k) or '') and fixer(w.text()))
        w.setProperty('champ', k)
        return w

    def _rendre_focus(self):
        if not self._focus:
            return
        for w in self.widget().findChildren(QWidget):
            if w.property('champ') == self._focus:
                w.setFocus()
                break
        self._focus = None

    def _boutons(self, it):
        S = self.cv.schema
        g = QGridLayout()
        g.setSpacing(4)
        defs = [('+90°', 'rot90', i18n.tr('se_piv90')),
                ('+45°', 'rot45', i18n.tr('se_piv45')),
                ('−90°', 'rotm90', i18n.tr('se_pivm90')),
                (i18n.tr('se_miroir'), 'flip', i18n.tr('se_miroir_tip')), (i18n.tr('se_dupliquer'), 'dup', None),
                (i18n.tr('se_montage'), 'fav', i18n.tr('se_montage_tip')),
                (i18n.tr('se_supprimer'), 'del', None)]
        if it.get('lo'):
            defs.append((i18n.tr('se_etiq_auto'), 'lblauto', i18n.tr('se_etiq_auto_tip')))
        for i, (txt, a, tip) in enumerate(defs):
            b = QPushButton(txt)
            if tip:
                b.setToolTip(tip)
            if a == 'del':
                b.setStyleSheet('color:#b71c1c')
            if a == 'fav':
                b.clicked.connect(self.montage.emit)
            else:
                b.clicked.connect(lambda _c=False, a=a: self._appliquer(lambda: S.action(a)))
            g.addWidget(b, i // 3, i % 3)
        return g

    # ------------------------------------------------------------ contrôle
    def _section_controle(self, G):
        S = self.cv.schema
        msgs, okd = S.defauts(G)
        box = QWidget()
        v = QVBoxLayout(box)
        v.setContentsMargins(0, 0, 0, 0)
        v.addWidget(_titre(i18n.tr('se_controle')))
        if msgs:
            for k, m, _x, _y in msgs:
                h = QHBoxLayout()
                lb = QLabel('⚠ ' + traduire(m))
                lb.setWordWrap(True)
                lb.setStyleSheet('color:#b71c1c')
                b = QPushButton(i18n.tr('se_valider'))
                b.setToolTip(i18n.tr('se_valider_tip'))
                b.setStyleSheet('color:#2e7d32')
                b.clicked.connect(lambda _c=False, k=k: self._appliquer(lambda: S.valider([k])))
                h.addWidget(lb, 1)
                h.addWidget(b, 0, Qt.AlignmentFlag.AlignTop)
                v.addLayout(h)
            if len(msgs) > 1:
                b = QPushButton(i18n.tr('se_valider_tous'))
                b.clicked.connect(lambda: self._appliquer(lambda: S.valider([k for k, _m, _x, _y in msgs])))
                v.addWidget(b)
        else:
            n_ = len(G.L)
            lb = QLabel(i18n.tr(('se_ok_non_valide' if okd else 'se_ok_detecte') + ('_n' if n_ > 1 else '_1'), n=n_))
            lb.setStyleSheet('color:#2e7d32')
            v.addWidget(lb)
        if okd:
            tb = QToolButton()
            tb.setText(i18n.tr('se_def_valide_n' if len(okd) > 1 else 'se_def_valide_1', n=len(okd)))
            tb.setCheckable(True)
            tb.setChecked(self._okd_ouvert)
            tb.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
            tb.setArrowType(Qt.ArrowType.DownArrow if self._okd_ouvert else Qt.ArrowType.RightArrow)
            tb.setStyleSheet('QToolButton{border:0;color:#2e7d32}')
            v.addWidget(tb)
            liste = QWidget()
            lv = QVBoxLayout(liste)
            lv.setContentsMargins(12, 0, 0, 0)
            for k, m, _x, _y in okd:
                h = QHBoxLayout()
                lb = QLabel('✔ ' + traduire(m))
                lb.setWordWrap(True)
                lb.setStyleSheet('color:#777')
                b = QPushButton(i18n.tr('se_annuler_validation'))
                b.clicked.connect(lambda _c=False, k=k: self._appliquer(lambda: S.valider([k], False)))
                h.addWidget(lb, 1)
                h.addWidget(b, 0, Qt.AlignmentFlag.AlignTop)
                lv.addLayout(h)
            liste.setVisible(self._okd_ouvert)
            v.addWidget(liste)

            def basculer(on):
                self._okd_ouvert = on
                liste.setVisible(on)
                tb.setArrowType(Qt.ArrowType.DownArrow if on else Qt.ArrowType.RightArrow)
            tb.toggled.connect(basculer)
        return box

    # ------------------------------------------------------------ nomenclature
    def _section_nomenclature(self):
        B = M.bom(self.cv.schema.items)
        box = QWidget()
        v = QVBoxLayout(box)
        v.setContentsMargins(0, 0, 0, 0)
        v.addWidget(_titre(i18n.tr('se_nomenclature')))
        if not B:
            lb = QLabel(i18n.tr('se_aucune_piece'))
            lb.setStyleSheet('color:#777')
            v.addWidget(lb)
            return box
        tab = _Tableau(len(B), 3)
        tab.setHorizontalHeaderLabels([i18n.tr('se_designation'), i18n.tr('se_qte'), 'U'])
        tab.verticalHeader().setVisible(False)
        tab.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        tab.setWordWrap(True)
        hh = tab.horizontalHeader()
        hh.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        hh.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        hh.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        for r, b in enumerate(B):
            tab.setItem(r, 0, QTableWidgetItem(b['d']))
            q = QTableWidgetItem(M.fq(b['q']))
            q.setTextAlignment(int(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter))
            tab.setItem(r, 1, q)
            tab.setItem(r, 2, QTableWidgetItem(b['u']))
        tab.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        tab.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        tab.setTextElideMode(Qt.TextElideMode.ElideNone)
        tab.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        v.addWidget(tab)
        return box

    # ------------------------------------------------------------ légende
    def _section_legende(self):
        box = QWidget()
        v = QVBoxLayout(box)
        v.setContentsMargins(0, 0, 0, 0)
        v.addWidget(_titre(i18n.tr('se_legende')))
        for k, verrou, txt in _legende():
            v.addWidget(_LigneLegende(k, verrou, txt))
        return box


class _Tableau(QTableWidget):
    """Tableau sans défilement propre : ses lignes s'adaptent à la largeur
    (désignations sur plusieurs lignes) et sa hauteur à son contenu."""

    def resizeEvent(self, e):
        super().resizeEvent(e)
        QTimer.singleShot(0, self._ajuster)

    def _ajuster(self):
        try:
            self.resizeRowsToContents()
            h = self.horizontalHeader().height() + sum(self.rowHeight(r) for r in range(self.rowCount())) + 4
            if h != self.height():
                self.setFixedHeight(h)
        except RuntimeError:     # tableau déjà remplacé
            pass
