# gui/schemaep_fenetre.py
"""Fenêtre SchemAEP : palette de pièces et favoris, zone de dessin,
panneau de propriétés, barre d'outils.

Fenêtre indépendante et non bloquante : QGIS reste utilisable à côté.
Les favoris (pièces, montages personnels, montages types masqués) sont
gardés dans les réglages QGIS.
"""
import copy
import json
import os
import time

from qgis.core import QgsSettings
from qgis.PyQt.QtCore import Qt, QRectF, QByteArray, QSize, QTimer
from qgis.PyQt.QtGui import QIcon, QPainter, QPixmap, QColor, QKeySequence
from qgis.PyQt.QtSvg import QSvgRenderer
from qgis.PyQt.QtWidgets import (QAction, QFileDialog, QInputDialog, QLabel, QLineEdit, QMainWindow,
                                 QMessageBox, QSplitter, QToolBar, QTreeWidget, QTreeWidgetItem,
                                 QVBoxLayout, QWidget, QHeaderView)

from ..tools import i18n
from ..tools.qt_exec import exec_dialog
from ..tools.schemaep import catalogue as C
from ..tools.schemaep import moteur as M
from ..tools.schemaep import montages as MT
from ..tools.schemaep import svg_qt
from .schemaep_canevas import Canevas, couleur
from .schemaep_panneau import Panneau

TITRE = 'SchemAEP'
CLE_FAVORIS = 'CanaPlan/schemaep_favoris'

# Presse-papiers SchemAEP : commun aux fenêtres et à la liste des nœuds, pour
# copier le schéma d'un nœud et le coller sur d'autres.
PRESSE = {'schema': None, 'source': '', 'fid': None}


def copier_schema(schema, source, fid=None):
    PRESSE.update(schema=json.loads(json.dumps(schema)), source=source or 'schéma', fid=fid)


def schema_copie():
    """Copie indépendante du schéma du presse-papiers (None si vide)."""
    return json.loads(json.dumps(PRESSE['schema'])) if PRESSE['schema'] else None
ROLE = Qt.ItemDataRole.UserRole


def apercu(items, taille=QSize(34, 24)):
    """Pixmap d'aperçu (palette) d'une ou plusieurs pièces posées."""
    frags = []
    for it in items:
        tr = 'translate(%s %s) rotate(%s)%s' % (C.n(C.r1(it['x'])), C.n(C.r1(it['y'])), C.n(it['r']),
                                               ' scale(1 -1)' if it.get('f', 1) < 0 else '')
        frags.append('<g transform="%s">%s</g>' % (tr, svg_qt.styler(svg_qt.dessin(it), couleur(it))))
    doc = '<svg xmlns="http://www.w3.org/2000/svg" viewBox="-2000 -2000 4000 4000"><g id="g">%s</g></svg>' % ''.join(frags)
    r = QSvgRenderer(QByteArray(doc.encode('utf-8')))
    b = r.boundsOnElement('g').adjusted(-4, -4, 4, 4)
    pm = QPixmap(taille * 2)
    pm.setDevicePixelRatio(2)
    pm.fill(Qt.GlobalColor.transparent)
    if b.width() <= 0 or b.height() <= 0:
        return pm
    p = QPainter(pm)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    s = min(taille.width() / b.width(), taille.height() / b.height())
    p.translate(taille.width() / 2, taille.height() / 2)
    p.scale(s, s)
    p.translate(-b.center())
    r.render(p, QRectF(-2000, -2000, 4000, 4000))
    p.end()
    return pm


def piece_type(tid):
    """Pièce type (paramètres par défaut) pour l'aperçu de la palette."""
    t = C.T[tid]
    p = copy.deepcopy(t.p)
    if tid == 'tuyau':
        p['dl'] = 50
    if tid == 'regard':
        p.update(w=60, h=40, txt='')
    return {'id': 1, 't': tid, 'x': 0, 'y': 0, 'r': t.r0(p) if t.r0 else 0, 'f': 1, 'p': p}


class Favoris:
    """Pièces favorites (p), montages personnels (m), montages types masqués (hid)."""

    def __init__(self):
        self.p, self.m, self.hid = [], [], []
        try:
            d = json.loads(QgsSettings().value(CLE_FAVORIS, '') or 'null')
        except (TypeError, ValueError):
            d = None
        if isinstance(d, dict):
            self.p = [t for t in d.get('p') or [] if t in C.T]
            self.m = [m for m in d.get('m') or [] if isinstance(m, dict) and m.get('id') and isinstance(m.get('items'), list)]
            self.hid = [h for h in d.get('hid') or [] if isinstance(h, str)]

    def enregistrer(self):
        QgsSettings().setValue(CLE_FAVORIS, json.dumps({'p': self.p, 'm': self.m, 'hid': self.hid}, ensure_ascii=False))

    def montages(self):
        return [m for m in MT.MONTAGES if m['id'] not in self.hid] + self.m

    def montage(self, id_):
        return next((m for m in self.montages() if m['id'] == id_), None)


class Fenetre(QMainWindow):
    """noeud : {'fid', 'libelle'} quand le schéma est rattaché à un nœud AEP ;
    enregistrer_noeud(schema_dict, svg) range alors le schéma dans le projet."""

    def __init__(self, parent=None, schema=None, noeud=None, enregistrer_noeud=None):
        super().__init__(parent)
        self.setWindowFlags(self.windowFlags() | Qt.WindowType.Window)
        self.resize(1320, 840)
        self.fichier = None
        self.fav = Favoris()
        self.noeud = noeud
        self._enregistrer_noeud = enregistrer_noeud
        self._reference = None

        self.canevas = Canevas(M.Schema(schema) if schema else None, self)
        self.canevas.message.connect(self._aide)
        self.canevas.modifie.connect(self._modifie)
        self.canevas.selection.connect(self._selection)

        # palette
        pal = QWidget()
        lp = QVBoxLayout(pal)
        lp.setContentsMargins(4, 4, 4, 4)
        self.recherche = QLineEdit()
        self.recherche.setPlaceholderText(i18n.tr('se_rechercher_piece'))
        self.recherche.setClearButtonEnabled(True)
        self.recherche.textChanged.connect(self._filtrer)
        self.palette = QTreeWidget()
        self.palette.setColumnCount(2)
        self.palette.setHeaderHidden(True)
        self.palette.setIconSize(QSize(34, 24))
        self.palette.setIndentation(10)
        self.palette.header().setStretchLastSection(False)
        self.palette.header().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.palette.header().setSectionResizeMode(1, QHeaderView.ResizeMode.Fixed)
        self.palette.setColumnWidth(1, 24)
        self.palette.itemClicked.connect(self._clic_palette)
        lp.addWidget(self.recherche)
        lp.addWidget(self.palette)

        self.panneau = Panneau(self.canevas)
        self.panneau.montage.connect(lambda: self.enregistrer_montage(False))

        sp = QSplitter()
        sp.addWidget(pal)
        sp.addWidget(self.canevas)
        sp.addWidget(self.panneau)
        sp.setStretchFactor(1, 1)
        sp.setSizes([270, 700, 350])
        self.setCentralWidget(sp)
        self._barre()
        self.statusBar()
        self._remplir_palette()
        self.canevas.rafraichir()
        self.canevas.recentrer()
        self._marquer_enregistre()

    # ------------------------------------------------------------ liaison au nœud
    def _etat(self):
        return json.dumps(self.canevas.schema.s, sort_keys=True)

    def _marquer_enregistre(self):
        self._reference = self._etat()

    def modifie_non_enregistre(self):
        return self._reference is not None and self._etat() != self._reference

    def enregistrer_dans_projet(self):
        """Range le schéma (JSON + SVG) sur son nœud, dans le projet."""
        if not self._enregistrer_noeud:
            return False
        from .schemaep_sorties import svg_schema
        s = self.canevas.schema.s
        self._enregistrer_noeud(json.loads(json.dumps(s)), svg_schema(s))
        self._marquer_enregistre()
        self.statusBar().showMessage(i18n.tr('se_range_noeud')
                                     % self.noeud['libelle'], 8000)
        return True

    def confirmer_abandon(self):
        """Vrai si l'on peut quitter ce schéma (enregistré, ignoré ou pas modifié)."""
        if not self.noeud or not self.modifie_non_enregistre():
            return True
        r = QMessageBox.question(
            self, TITRE, i18n.tr('se_modifie_enregistrer') % self.noeud['libelle'],
            QMessageBox.StandardButton.Save | QMessageBox.StandardButton.Discard | QMessageBox.StandardButton.Cancel)
        if r == QMessageBox.StandardButton.Save:
            return self.enregistrer_dans_projet()
        return r == QMessageBox.StandardButton.Discard

    def showEvent(self, e):
        super().showEvent(e)
        if not getattr(self, '_cadre', False):
            # la vue n'a sa vraie taille qu'une fois la fenêtre affichée
            self._cadre = True
            from qgis.PyQt.QtCore import QTimer
            QTimer.singleShot(0, self.canevas.recentrer)

    def closeEvent(self, e):
        if self.confirmer_abandon():
            e.accept()
        else:
            e.ignore()

    # ------------------------------------------------------------ barre d'outils
    def _barre(self):
        tb = QToolBar('SchemAEP')
        tb.setMovable(False)
        self.addToolBar(tb)

        def act(txt, fn, tip=None):
            a = QAction(txt, self)
            a.triggered.connect(fn)
            if tip:
                a.setToolTip(tip)
            tb.addAction(a)
            return a
        self.nom = QLineEdit()
        self.nom.setPlaceholderText(i18n.tr('se_nom_projet'))
        self.nom.setMaximumWidth(200)
        self.nom.textEdited.connect(self._nommer)
        tb.addWidget(self.nom)
        if self.noeud:
            a = act(i18n.tr('se_enr_projet'), self.enregistrer_dans_projet,
                    i18n.tr('se_enr_projet_tip') % self.noeud['libelle'])
            f = a.font()
            f.setBold(True)
            a.setFont(f)
            tb.addSeparator()
        act(i18n.tr('se_nouveau'), self.nouveau)
        act(i18n.tr('se_annuler'), self.annuler, i18n.tr('se_annuler_tip'))
        act(i18n.tr('se_effacer_tout'), self.effacer_tout,
            i18n.tr('se_effacer_tout_tip'))
        act(i18n.tr('se_copier'), self.copier,
            i18n.tr('se_copier_tip'))
        act(i18n.tr('se_coller'), self.coller,
            i18n.tr('se_coller_tip'))
        act(i18n.tr('se_ouvrir'), self.ouvrir)
        act(i18n.tr('se_enregistrer'), self.enregistrer)
        act(i18n.tr('se_export_svg'), self.exporter_svg, i18n.tr('se_export_svg_tip'))
        act(i18n.tr('se_nomenc_csv'), self.exporter_csv, i18n.tr('se_nomenc_csv_tip'))
        act(i18n.tr('se_imprimer'), self.imprimer, i18n.tr('se_imprimer_tip'))
        act(i18n.tr('se_schema_favori'), lambda: self.enregistrer_montage(True),
            i18n.tr('se_schema_favori_tip'))
        tb.addSeparator()
        tb.addWidget(QLabel(i18n.tr('se_lbl_schema')))
        act('−90°', lambda: self._tourner(-90), i18n.tr('se_tourner_m90_tip'))
        act('+90°', lambda: self._tourner(90), i18n.tr('se_tourner_p90_tip'))
        act('180°', lambda: self._tourner(180), i18n.tr('se_tourner_180_tip'))
        tb.addSeparator()
        self.a_etiq = act(i18n.tr('se_etiquettes'), self._basculer_etiquettes, i18n.tr('se_etiquettes_tip'))
        self.a_etiq.setCheckable(True)
        self.a_etiq.setChecked(True)
        act(i18n.tr('se_recentrer'), self.canevas.recentrer)

    def _aide(self, txt):
        self.statusBar().showMessage(txt)

    def _modifie(self):
        nom = self.canevas.schema.s.get('nom') or ''
        if self.nom.text() != nom:
            self.nom.setText(nom)
        self._titre()
        self.panneau.rafraichir()

    def _titre(self):
        nom = self.canevas.schema.s.get('nom') or ''
        t = (nom + ' – ' if nom else '') + TITRE
        if self.noeud:
            t += i18n.tr('se_titre_noeud') % self.noeud['libelle']
        self.setWindowTitle(t)

    def _selection(self):
        self.panneau.rafraichir()

    def _nommer(self, txt):
        self.canevas.schema.s['nom'] = txt
        self._titre()

    # ------------------------------------------------------------ palette
    def _remplir_palette(self):
        ouverts = {self.palette.topLevelItem(i).text(0): self.palette.topLevelItem(i).isExpanded()
                   for i in range(self.palette.topLevelItemCount())}
        self.palette.clear()
        fav = QTreeWidgetItem(self.palette, [i18n.tr('se_favoris')])
        fav.setForeground(0, QColor('#e65100'))
        for m in self.fav.montages():
            its = M.normalize({'items': m['items']})['items']
            e = QTreeWidgetItem(fav, [m['nom'], '✕'])
            e.setIcon(0, QIcon(apercu(its)))
            e.setData(0, ROLE, ('montage', m['id']))
            e.setToolTip(0, m['nom'])
            e.setToolTip(1, i18n.tr('se_retirer_favoris'))
            e.setForeground(1, QColor('#9aa0b0'))
        for tid in self.fav.p:
            e = QTreeWidgetItem(fav, [C.T[tid].nom, '✕'])
            e.setIcon(0, QIcon(apercu([piece_type(tid)])))
            e.setData(0, ROLE, ('piece', tid))
            e.setToolTip(1, i18n.tr('se_retirer_favoris'))
            e.setForeground(1, QColor('#9aa0b0'))
        if not fav.childCount():
            e = QTreeWidgetItem(fav, [i18n.tr('se_favoris_vide')])
            e.setForeground(0, QColor('#777777'))
        if self.fav.hid:
            e = QTreeWidgetItem(fav, [i18n.tr('se_retablir')])
            e.setForeground(0, QColor('#1565c0'))
            e.setData(0, ROLE, ('retablir', None))
        for fam in C.FAM:
            g = QTreeWidgetItem(self.palette, [fam])
            g.setForeground(0, QColor('#0d47a1'))
            for tid, t in C.T.items():
                if t.fam != fam:
                    continue
                on = tid in self.fav.p
                e = QTreeWidgetItem(g, [t.nom, '★' if on else '☆'])
                e.setIcon(0, QIcon(apercu([piece_type(tid)])))
                e.setData(0, ROLE, ('piece', tid))
                e.setToolTip(0, t.nom)
                e.setToolTip(1, i18n.tr('se_retirer_favoris' if on else 'se_ajouter_favoris'))
                e.setForeground(1, QColor('#f9a825' if on else '#9aa0b0'))
        for i in range(self.palette.topLevelItemCount()):
            g = self.palette.topLevelItem(i)
            g.setExpanded(ouverts.get(g.text(0), True))
        self._filtrer(self.recherche.text())

    def _filtrer(self, txt):
        v = M.sans_accents(txt.strip())
        for i in range(self.palette.topLevelItemCount()):
            g = self.palette.topLevelItem(i)
            vis = 0
            for j in range(g.childCount()):
                e = g.child(j)
                d = e.data(0, ROLE)
                if d and d[0] == 'piece':
                    t = C.T[d[1]]
                    s = '%s %s %s' % (t.nom, t.kw, t.fam)
                elif d and d[0] == 'montage':
                    s = e.text(0) + ' montage'
                else:
                    s = ''
                ok = not v or (s and v in M.sans_accents(s))
                e.setHidden(not ok)
                vis += bool(ok)
            g.setHidden(bool(v) and vis == 0)
            if v:
                g.setExpanded(True)

    def _clic_palette(self, e, col):
        # Traitement différé : il peut reconstruire la palette (étoile, ✕,
        # « Rétablir ») ou ouvrir une question, alors que Qt n'a pas fini de
        # traiter le clic sur la ligne — la supprimer à ce moment fait planter
        # QGIS (violation d'accès dans QAbstractItemView::mouseReleaseEvent).
        d = e.data(0, ROLE)
        if not d:
            return
        dans_favoris = e.parent() is not None and e.parent().text(0) == i18n.tr('se_favoris')
        QTimer.singleShot(0, lambda: self._traiter_clic(d, col, dans_favoris))

    def _traiter_clic(self, d, col, dans_favoris):
        if d[0] == 'retablir':
            self.fav.hid = []
            self.fav.enregistrer()
            self._remplir_palette()
            return
        if col == 1:
            self._basculer_favori(d, dans_favoris)
            return
        S = self.canevas.schema
        if d[0] == 'piece':
            S.ajouter(d[1], self.canevas.centre_vue())
        else:
            m = self.fav.montage(d[1])
            if m:
                S.poser_montage(m, self.canevas.centre_vue())
        self.canevas.rafraichir()
        self.canevas.setFocus()

    def _basculer_favori(self, d, dans_favoris):
        kind, cle = d
        if kind == 'piece':
            if cle in self.fav.p:
                self.fav.p.remove(cle)
            else:
                self.fav.p.append(cle)
        elif any(m['id'] == cle for m in MT.MONTAGES):
            self.fav.hid.append(cle)
        else:
            m = next((m for m in self.fav.m if m['id'] == cle), None)
            if m and QMessageBox.question(self, TITRE, i18n.tr('se_suppr_montage') % m['nom']) \
                    != QMessageBox.StandardButton.Yes:
                return
            self.fav.m = [m for m in self.fav.m if m['id'] != cle]
        self.fav.enregistrer()
        self._remplir_palette()

    def enregistrer_montage(self, tout):
        """Enregistre en favori l'ensemble raccordé à la pièce sélectionnée,
        ou tout le schéma."""
        S = self.canevas.schema
        it = S.cur()
        if not tout and not it:
            return
        if not S.items:
            QMessageBox.information(self, TITRE, i18n.tr('se_schema_vide'))
            return
        mt = S.montage_depuis(it, tout)
        if not mt:
            return
        n_ = len(mt['items'])
        if tout:
            defaut = S.s.get('nom') or i18n.tr('se_defaut_nom_schema') % n_
        else:
            defaut = C.T[it['t']].nom + (i18n.tr('se_plus_piece_n' if n_ > 2 else 'se_plus_piece_1', n=n_ - 1) if n_ > 1 else '')
        nom, ok = QInputDialog.getText(self, TITRE, i18n.tr('se_nom_favori_schema') if tout else i18n.tr('se_nom_montage'),
                                       QLineEdit.EchoMode.Normal, defaut)
        if not ok or not nom.strip():
            return
        mt.update(id='u%d' % int(time.time() * 1000), nom=nom.strip())
        self.fav.m.append(mt)
        self.fav.enregistrer()
        self._remplir_palette()

    # ------------------------------------------------------------ commandes
    def nouveau(self):
        S = self.canevas.schema
        if S.items and QMessageBox.question(self, TITRE, i18n.tr('se_effacer_en_cours')) != QMessageBox.StandardButton.Yes:
            return
        S.nouveau()
        self.fichier = None
        self.canevas.rafraichir()
        self.canevas.recentrer()

    def copier(self):
        S = self.canevas.schema
        if not S.items:
            self.statusBar().showMessage(i18n.tr('se_rien_a_copier'), 5000)
            return
        source = self.noeud['libelle'] if self.noeud else (S.s.get('nom') or i18n.tr('se_schema_libre_source'))
        copier_schema(S.s, source, self.noeud['fid'] if self.noeud else None)
        self.statusBar().showMessage(i18n.tr('se_copie_ok') % source, 8000)

    def coller(self):
        s = schema_copie()
        if not s:
            QMessageBox.information(self, TITRE, i18n.tr('se_aucun_copie_info'))
            return
        S = self.canevas.schema
        if S.items and QMessageBox.question(
                self, TITRE, i18n.tr('se_remplacer_copie') % PRESSE['source']) \
                != QMessageBox.StandardButton.Yes:
            return
        nom = S.s.get('nom') or ''
        S.charger(s)
        S.s['nom'] = nom             # le schéma garde le nom de son nœud
        self.canevas.rafraichir()
        self.canevas.recentrer()

    def effacer_tout(self):
        S = self.canevas.schema
        if not S.items:
            return
        if QMessageBox.question(self, TITRE, i18n.tr('se_effacer_toutes')) \
                != QMessageBox.StandardButton.Yes:
            return
        S.effacer_tout()
        self.canevas.rafraichir()
        self.canevas.recentrer()

    def annuler(self):
        if self.canevas.schema.annuler():
            self.canevas.rafraichir()

    def _tourner(self, d):
        self.canevas.schema.tourner_tout(d)
        self.canevas.rafraichir()
        self.canevas.recentrer()

    def _basculer_etiquettes(self):
        self.canevas.etiquettes_visibles = self.a_etiq.isChecked()
        self.canevas.rafraichir(False)

    def ouvrir(self):
        f, _ = QFileDialog.getOpenFileName(self, i18n.tr('se_ouvrir_schema'), os.path.dirname(self.fichier or ''),
                                           i18n.tr('se_filtre_json'))
        if not f:
            return
        try:
            with open(f, encoding='utf-8') as h:
                s = M.charger_json(h.read())
        except (OSError, ValueError) as err:
            QMessageBox.warning(self, TITRE, i18n.tr('se_illisible') % err)
            return
        self.canevas.schema.charger(s)
        self.fichier = f
        self.canevas.rafraichir()
        self.canevas.recentrer()

    def enregistrer(self):
        S = self.canevas.schema
        defaut = self.fichier or ((S.s.get('nom') or 'schema-aep') + '.json')
        f, _ = QFileDialog.getSaveFileName(self, i18n.tr('se_enr_schema'), defaut, i18n.tr('se_filtre_json'))
        if not f:
            return
        with open(f, 'w', encoding='utf-8') as h:
            h.write(M.vers_json(S.s))
        self.fichier = f

    # ------------------------------------------------------------ sorties
    def _nom_fichier(self, ext, defaut):
        base = self.canevas.schema.s.get('nom') or (self.noeud and 'schema_' + self.noeud['libelle']) or defaut
        d = os.path.dirname(self.fichier) if self.fichier else ''
        return os.path.join(d, '%s.%s' % (base, ext))

    def exporter_svg(self):
        from .schemaep_sorties import svg_schema
        f, _ = QFileDialog.getSaveFileName(self, i18n.tr('se_exporter_svg'), self._nom_fichier('svg', 'schema-aep'), i18n.tr('se_filtre_svg'))
        if f:
            with open(f, 'w', encoding='utf-8') as h:
                h.write(svg_schema(self.canevas.schema.s))

    def exporter_csv(self):
        f, _ = QFileDialog.getSaveFileName(self, i18n.tr('se_nomenc_csv'), self._nom_fichier('csv', 'nomenclature-aep'),
                                           i18n.tr('se_filtre_csv'))
        if f:
            with open(f, 'w', encoding='utf-8', newline='') as h:
                h.write(M.csv_nomenclature(self.canevas.schema.items))

    def imprimer(self):
        from qgis.PyQt.QtPrintSupport import QPrintDialog, QPrinter
        from qgis.PyQt.QtGui import QPageLayout
        from .schemaep_sorties import page_impression
        pr = QPrinter(QPrinter.PrinterMode.HighResolution)
        pr.setPageOrientation(QPageLayout.Orientation.Landscape)
        dlg = QPrintDialog(pr, self)
        if exec_dialog(dlg):
            p = QPainter(pr)
            S = self.canevas.schema.s
            titre = S.get('nom') or (i18n.tr('se_noeud_titre') % self.noeud['libelle'] if self.noeud else i18n.tr('se_schema_aep'))
            page_impression(p, titre, S)
            p.end()
