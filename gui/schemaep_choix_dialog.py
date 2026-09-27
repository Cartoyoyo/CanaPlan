# gui/schemaep_choix_dialog.py
"""Lancement de SchemAEP depuis CanaPlan : choix du nœud AEP.

Une liste des nœuds AEP et des regards compteur (nom, type, schéma existant)
permet de choisir le nœud, ou de le cliquer sur la carte. Un nœud est repéré
par sa clé (rôle de la couche, fid) : ('regard', fid) ou ('tabouret', fid). Le schéma rangé sur le nœud est rouvert ;
sinon un schéma de départ est construit depuis les conduites raccordées.
Les schémas vivent sur le plugin (stockage.Magasin) et partent dans le .bet
à son enregistrement.

La boîte est non modale : on peut naviguer dans la carte pendant le choix.
"""
import hashlib
import json
import os
import tempfile

from qgis.core import QgsPointXY, QgsRectangle
from qgis.gui import QgsMapTool, QgsRubberBand
from qgis.PyQt import sip
from qgis.PyQt.QtCore import QEvent, QRectF, Qt, QTimer, QUrl, pyqtSignal
from qgis.PyQt.QtGui import QColor, QKeySequence, QPainter, QPen, QPixmap
from qgis.PyQt.QtWidgets import (QAbstractItemView, QAction, QDialog, QFileDialog, QHBoxLayout, QHeaderView, QInputDialog,
                                 QLabel, QLineEdit, QMenu, QMessageBox,
                                 QPushButton, QTableWidget, QTableWidgetItem, QToolTip, QTreeWidget, QTreeWidgetItem,
                                 QVBoxLayout)

from ..tools import i18n
from ..tools import reseaux as R
from ..tools.schemaep import moteur as M
from ..tools.schemaep import prefill as PF
from ..tools.schemaep import stockage as ST
from ..tools.qt_exec import exec_dialog

TITRE = 'SchemAEP'
APERCU_L, APERCU_H = 320, 240       # vignette au survol de la date (pixels affichés)
ROLE = Qt.ItemDataRole.UserRole           # fid
ROLE_COUCHE = Qt.ItemDataRole.UserRole + 1   # rôle de la couche ('regard', 'tabouret')


def magasin(plugin):
    """Schémas du projet. S'ils ne sont pas en mémoire (plugin rechargé,
    projet ouvert autrement que par CanaPlan), ils sont relus dans le
    GeoPackage d'où viennent les nœuds : sans cela, le prochain
    enregistrement du .bet réécrirait une table vide."""
    m = getattr(plugin, '_schemas_aep', None)
    if m is None:
        m = ST.Magasin()
        couches, noeuds = _noeuds(plugin)
        if noeuds is not None and noeuds.providerType() == 'ogr':
            chemin = noeuds.source().split('|')[0]
            if os.path.isfile(chemin):
                m = ST.lire_gpkg(chemin, couches)
        plugin._schemas_aep = m
    return m


def libelle_noeud(feat, role='regard'):
    nom = feat['nom'] if 'nom' in feat.fields().names() else None
    nom = '' if nom is None or str(nom) == 'NULL' else str(nom)
    if nom:
        return nom
    return '%s #%s' % (R.libelle_type(type_noeud(feat, role)), feat.id())


def type_noeud(feat, role='regard'):
    typ = feat['type'] if 'type' in feat.fields().names() else None
    if typ is None or str(typ) in ('', 'NULL'):
        return R.AEP_TERMINAL_TYPE_DEFAUT if role == 'tabouret' else R.AEP_NOEUD_TYPE_DEFAUT
    return str(typ)


# ---------------------------------------------------------------- lancement
def ouvrir_schemaep(plugin):
    """Action « SchemAEP » du panneau : boîte de choix du nœud."""
    couches = plugin._couches_si_presentes('AEP')
    if not couches:
        if QMessageBox.question(plugin.iface.mainWindow(), TITRE,
                                i18n.tr('se_pas_aep')) \
                == QMessageBox.StandardButton.Yes:
            ouvrir_fenetre(plugin, None, None)
        return
    dlg = getattr(plugin, '_schemaep_choix', None)
    if dlg is None or sip.isdeleted(dlg):
        dlg = ChoixNoeudDialog(plugin, couches, plugin.iface.mainWindow())
        plugin._schemaep_choix = dlg
    else:
        dlg.couches = couches
        dlg.remplir()
    dlg.show()
    dlg.raise_()
    dlg.activateWindow()


def ouvrir_fenetre(plugin, couches, fid):
    """Ouvre la fenêtre SchemAEP sur le nœud de clé fid = (rôle, fid)
    (None : schéma libre). Un fid seul désigne un nœud de la couche des nœuds."""
    if fid is not None and not isinstance(fid, tuple):
        fid = ('regard', fid)
    from .schemaep_fenetre import Favoris, Fenetre
    carte = PF.satellites(couches) if fid is not None and couches else {}
    if fid in carte and magasin(plugin).get(fid) is None:
        fid = carte[fid][0]       # vanne d'un carrefour : c'est le schéma du carrefour
    fen = getattr(plugin, '_schemaep_fen', None)
    if fen is not None and not sip.isdeleted(fen) and fen.isVisible():
        if fen.noeud and fen.noeud['fid'] == fid:
            fen.raise_()
            fen.activateWindow()
            return fen
        if not fen.confirmer_abandon():
            return None
        fen._reference = None
        fen.close()
        fen.deleteLater()
    mag = magasin(plugin)
    schema, noeud, enreg = None, None, None
    if fid is not None and couches:
        feat = ST.entite(couches, fid)
        if feat is None:
            return None
        lib = libelle_noeud(feat, fid[0])
        entree = mag.get(fid)
        if entree:
            schema = M.normalize(entree['schema'])
        else:
            schema = schema_defaut(plugin, couches, fid, carte, Favoris().montages())
            if schema is None:
                return None
        noeud = {'fid': fid, 'libelle': lib}

        def enreg(sd, svg):
            # fid lu au moment d'enregistrer : l'enregistrement du .bet le renouvelle
            magasin(plugin).mettre(noeud['fid'], sd, svg)
            d = getattr(plugin, '_schemaep_choix', None)
            if d is not None and not sip.isdeleted(d):
                d.remplir()
    fen = Fenetre(plugin.iface.mainWindow(), schema, noeud, enreg)
    plugin._schemaep_fen = fen
    fen.show()
    fen.raise_()
    fen.activateWindow()
    return fen


_POINTS = ['nord', 'nord-est', 'est', 'sud-est', 'sud', 'sud-ouest', 'ouest', 'nord-ouest']


def _demander_branche(parent, lib, racc, idx):
    """Vanne posée sur un angle : sur quelle conduite se trouve-t-elle ?
    Indice dans racc, ou None si l'utilisateur annule."""
    choix = []
    for i in idx:
        r = racc[i]
        cote = _POINTS[int(((r['az'] % 360) + 22.5) // 45) % 8]
        choix.append(i18n.tr('se_cote_voisin') % (r['voisin'], cote) if r['voisin'] else i18n.tr('se_cote') % cote)
    txt, ok = QInputDialog.getItem(
        parent, TITRE, i18n.tr('se_vanne_angle') % lib, choix, 0, False)
    return idx[choix.index(txt)] if ok and txt in choix else None


def schema_defaut(plugin, couches, cle, carte, montages, parent=None):
    """Schéma de départ du nœud cle (vannes du carrefour comprises). Vanne
    posée sur un angle : la branche est demandée ; None si l'on annule."""
    feat = ST.entite(couches, cle)
    if feat is None:
        return None
    lib = libelle_noeud(feat, cle[0])
    typ = type_noeud(feat, cle[0])
    racc = PF.racc_carrefour(QgsPointXY(feat.geometry().asPoint()), couches, cle, carte)
    angle = PF.vanne_en_angle(typ, racc)
    if angle:
        b = _demander_branche(parent or plugin.iface.mainWindow(), lib, racc, angle)
        if b is None:
            return None
        racc[b]['vanne'] = True
        racc[b]['rep'] = PF.nom_reel(feat)
        typ = 'coude'
    return PF.schema_noeud(typ, racc, lib, montages)


def entree_schema(plugin, couches, cle, carte=None):
    """Schéma rangé sur le nœud, ou celui de son carrefour pour une vanne
    satellite sans schéma propre."""
    mag = magasin(plugin)
    e = mag.get(cle)
    if e is None:
        carte = PF.satellites(couches) if carte is None else carte
        if cle in carte:
            e = mag.get(carte[cle][0])
    return e


def _noeuds(plugin):
    couches = plugin._couches_si_presentes('AEP')
    return couches, (couches or {}).get('regard')


def avant_enregistrement(plugin):
    """Enregistrement du .bet, avant le retrait des couches : instantané des
    schémas (nom et position des nœuds) et du nœud de la fenêtre ouverte."""
    couches, _n = _noeuds(plugin)
    mag = magasin(plugin)
    fen = getattr(plugin, '_schemaep_fen', None)
    fen_infos = None
    if fen is not None and not sip.isdeleted(fen) and fen.noeud:
        fen_infos = ST.infos_noeud(couches, fen.noeud['fid'])
    # orphelins compris, même sans schéma rattaché : ils sont réécrits tels quels
    return {'entrees': ST.instantane(mag, couches), 'fen': fen_infos}


def ecrire_table(etat, gpkg_path, contexte):
    """Table schema_aep dans le GPKG en cours d'écriture ; message d'erreur ou ''."""
    return ST.ecrire_gpkg(etat['entrees'], gpkg_path, contexte) if etat else ''


def apres_rechargement(plugin, gpkg_path, etat=None):
    """Couches rechargées (fid renouvelés) : schémas relus et rattachés aux
    nouveaux fid, fenêtre et boîte de choix raccrochées. etat=None : ouverture
    d'un .bet, fenêtres fermées."""
    couches, noeuds = _noeuds(plugin)
    if etat is None:
        fermer(plugin)
    plugin._schemas_aep = ST.lire_gpkg(gpkg_path, couches) if noeuds is not None else ST.Magasin()
    fen = getattr(plugin, '_schemaep_fen', None)
    if fen is not None and not sip.isdeleted(fen) and fen.noeud and etat:
        nouveau = ST.retrouver(couches, etat.get('fen'))
        if nouveau is None:
            fen.noeud = None      # nœud disparu : le schéma reste ouvert, comme schéma libre
            fen._enregistrer_noeud = None
            fen._titre()
        else:
            fen.noeud['fid'] = nouveau
    dlg = getattr(plugin, '_schemaep_choix', None)
    if dlg is not None and not sip.isdeleted(dlg):
        if couches:
            dlg.couches = couches
            dlg.remplir()
        else:
            dlg.close()


def fermer(plugin):
    """Ferme fenêtre et boîte (déchargement du plugin, projet fermé)."""
    for att in ('_schemaep_fen', '_schemaep_choix'):
        w = getattr(plugin, att, None)
        if w is not None and not sip.isdeleted(w):
            if hasattr(w, '_reference'):
                w._reference = None      # pas de question : le projet s'en va
            w.close()
            w.deleteLater()
        setattr(plugin, att, None)


# ---------------------------------------------------------------- choix sur la carte
class _ChoixNoeudTool(QgsMapTool):
    """Clic sur un nœud AEP ou un regard compteur (12 pixels de tolérance)."""
    choisi = pyqtSignal(object)     # clé (rôle, fid)
    annule = pyqtSignal()

    def __init__(self, canvas, couches):
        super().__init__(canvas)
        self.couches = couches
        self._fini = False
        self.rb = QgsRubberBand(canvas)
        self.rb.setColor(QColor(255, 140, 0, 200))
        self.rb.setWidth(3)
        self.setCursor(Qt.CursorShape.CrossCursor)

    def _noeud(self, e):
        """(rôle, entité) la plus proche du clic parmi les nœuds et les
        regards compteur, ou None."""
        tol = 12 * self.canvas().mapUnitsPerPixel()
        best, best_d = None, float('inf')
        for role in ST.ROLES:
            couche = self.couches.get(role)
            if couche is None:
                continue
            pt = QgsPointXY(self.toLayerCoordinates(couche, e.pos()))
            rect = QgsRectangle(pt.x() - tol, pt.y() - tol, pt.x() + tol, pt.y() + tol)
            for f in couche.getFeatures(rect):
                g = f.geometry()
                if g.isEmpty() or not ST.porte_schema(role, f):
                    continue
                d = pt.distance(QgsPointXY(g.asPoint()))
                if d <= tol and d < best_d:
                    best, best_d = (role, f), d
        return best

    def canvasMoveEvent(self, e):
        r = self._noeud(e)
        self.rb.reset()
        if r is not None:
            role, f = r
            self.rb.setToGeometry(f.geometry().buffer(12 * self.canvas().mapUnitsPerPixel(), 12),
                                  self.couches[role])

    def canvasReleaseEvent(self, e):
        if e.button() == Qt.MouseButton.RightButton:
            self.canvas().unsetMapTool(self)
            return
        r = self._noeud(e)
        if r is not None:
            self._fini = True
            self.choisi.emit((r[0], r[1].id()))

    def deactivate(self):
        self.rb.reset()
        if not self._fini:
            self.annule.emit()
        super().deactivate()


# ---------------------------------------------------------------- boîte de choix
class ChoixNoeudDialog(QDialog):
    def __init__(self, plugin, couches, parent=None):
        super().__init__(parent)
        self.plugin, self.couches = plugin, couches
        self.setWindowTitle(i18n.tr('se_titre_choix'))
        self.resize(640, 580)
        v = QVBoxLayout(self)
        v.addWidget(QLabel(i18n.tr('se_intro_choix')))
        v.itemAt(0).widget().setWordWrap(True)
        self.recherche = QLineEdit()
        self.recherche.setPlaceholderText(i18n.tr('se_rech_nom_type'))
        self.recherche.setClearButtonEnabled(True)
        self.recherche.textChanged.connect(self._filtrer)
        v.addWidget(self.recherche)
        self.liste = QTreeWidget()
        self.liste.setHeaderLabels([i18n.tr('se_col_noeud'), i18n.tr('se_col_type'), i18n.tr('se_col_schema')])
        self.liste.setRootIsDecorated(False)
        self.liste.setSortingEnabled(True)
        self.liste.header().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self.liste.header().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.liste.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.liste.currentItemChanged.connect(self._courant)
        self.liste.itemSelectionChanged.connect(self._courant)
        # différé : l'ouverture peut reconstruire cette liste pendant le clic (voir fenêtre)
        self.liste.itemDoubleClicked.connect(lambda *_a: QTimer.singleShot(0, self._ouvrir))
        v.addWidget(self.liste, 1)
        h = QHBoxLayout()
        self.b_carte = QPushButton(i18n.tr('se_choisir_carte'))
        self.b_carte.clicked.connect(self._choisir_carte)
        self.b_copier = QPushButton(i18n.tr('se_copier_schema'))
        self.b_copier.setToolTip(i18n.tr('se_copier_schema_tip'))
        self.b_copier.clicked.connect(self._copier)
        self.b_coller = QPushButton(i18n.tr('se_coller_sel'))
        self.b_coller.setToolTip(i18n.tr('se_coller_sel_tip'))
        self.b_coller.clicked.connect(self._coller)
        self.b_suppr = QPushButton(i18n.tr('se_suppr_schema'))
        self.b_suppr.clicked.connect(self._supprimer)
        for b in (self.b_carte, self.b_copier, self.b_coller, self.b_suppr):
            h.addWidget(b)
        h.addStretch(1)
        v.addLayout(h)
        self.lbl_copie = QLabel()
        self.lbl_copie.setStyleSheet('color:#555')
        v.addWidget(self.lbl_copie)
        h = QHBoxLayout()
        b_libre = QPushButton(i18n.tr('se_schema_libre'))
        b_libre.setToolTip(i18n.tr('se_schema_libre_tip'))
        b_libre.clicked.connect(lambda: ouvrir_fenetre(self.plugin, None, None))
        b_nom = QPushButton(i18n.tr('se_nomenc_tous'))
        b_nom.clicked.connect(self._nomenclature)
        self.b_ouvrir = QPushButton(i18n.tr('se_ouvrir_le_schema'))
        self.b_ouvrir.setDefault(True)
        self.b_ouvrir.clicked.connect(self._ouvrir)
        b_fermer = QPushButton(i18n.tr('se_fermer'))
        b_fermer.clicked.connect(self.close)
        h.addWidget(b_libre)
        h.addWidget(b_nom)
        h.addStretch(1)
        h.addWidget(self.b_ouvrir)
        h.addWidget(b_fermer)
        v.addLayout(h)
        self._apercus = {}      # empreinte du schéma → PNG de la vignette
        self.liste.viewport().installEventFilter(self)
        # clic droit : ouvrir / copier / coller sur la sélection / supprimer ;
        # Ctrl+C et Ctrl+V dans la liste
        self.a_ouvrir = QAction(i18n.tr('se_ouvrir_le_schema'), self.liste)
        self.a_ouvrir.triggered.connect(self._ouvrir)
        self.a_copier = QAction(i18n.tr('se_copier_schema'), self.liste)
        self.a_copier.setShortcut(QKeySequence(QKeySequence.StandardKey.Copy))
        self.a_copier.triggered.connect(lambda: self.b_copier.isEnabled() and self._copier())
        self.a_coller = QAction(i18n.tr('se_coller_sel'), self.liste)
        self.a_coller.setShortcut(QKeySequence(QKeySequence.StandardKey.Paste))
        self.a_coller.triggered.connect(lambda: self.b_coller.isEnabled() and self._coller())
        self.a_realigner = QAction(i18n.tr('se_realigner'), self.liste)
        self.a_realigner.setToolTip(i18n.tr('se_realigner_tip'))
        self.a_realigner.triggered.connect(self._realigner)
        self.a_recreer = QAction(i18n.tr('se_recreer'), self.liste)
        self.a_recreer.setToolTip(i18n.tr('se_recreer_tip'))
        self.a_recreer.triggered.connect(self._recreer)
        self.a_suppr = QAction(i18n.tr('se_suppr_schema'), self.liste)
        self.a_suppr.triggered.connect(self._supprimer)
        for a in (self.a_copier, self.a_coller):
            a.setShortcutContext(Qt.ShortcutContext.WidgetShortcut)
            self.liste.addAction(a)
        self.liste.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.liste.customContextMenuRequested.connect(self._menu)
        self.remplir()

    def _menu(self, pos):
        """Menu contextuel de la liste : mêmes actions que les boutons, sur
        la ligne cliquée ou la sélection (Ctrl+clic, Maj+clic)."""
        if self.liste.itemAt(pos) is None:
            return
        self._courant()
        self.a_ouvrir.setEnabled(self.b_ouvrir.isEnabled())
        self.a_copier.setEnabled(self.b_copier.isEnabled())
        self.a_coller.setEnabled(self.b_coller.isEnabled())
        self.a_coller.setText(self.b_coller.text())
        self.a_suppr.setEnabled(self.b_suppr.isEnabled())
        self.a_suppr.setText(self.b_suppr.text())
        menu = QMenu(self)
        menu.addAction(self.a_ouvrir)
        menu.addSeparator()
        menu.addAction(self.a_copier)
        menu.addAction(self.a_coller)
        menu.addSeparator()
        n_ = len(self._a_supprimer())
        self.a_realigner.setEnabled(n_ > 0)
        self.a_realigner.setText(i18n.tr('se_realigner') + (' (%d)' % n_ if n_ > 1 else ''))
        cibles = self._cibles_recreer()
        self.a_recreer.setEnabled(bool(cibles))
        self.a_recreer.setText(i18n.tr('se_recreer') + (' (%d)' % len(cibles) if len(cibles) > 1 else ''))
        menu.addAction(self.a_realigner)
        menu.addAction(self.a_recreer)
        menu.addSeparator()
        menu.addAction(self.a_suppr)
        menu.exec(self.liste.viewport().mapToGlobal(pos))

    # --- aperçu au survol de la date
    def _apercu(self, schema):
        """Chemin du PNG de la vignette du schéma ('' s'il est vide). Rendu
        en double définition, mis en cache par contenu du schéma."""
        from .schemaep_sorties import dessiner_schema
        cle = hashlib.blake2b(json.dumps(schema, sort_keys=True).encode('utf-8'), digest_size=16).hexdigest()
        chemin = self._apercus.get(cle)
        if chemin is not None and (not chemin or os.path.isfile(chemin)):
            return chemin
        dossier = os.path.join(tempfile.gettempdir(), 'canaplan_schemaep_apercu')
        os.makedirs(dossier, exist_ok=True)
        chemin = os.path.join(dossier, cle + '.png')
        if not os.path.isfile(chemin):
            pm = QPixmap(APERCU_L * 2, APERCU_H * 2)
            pm.fill(QColor('white'))
            painter = QPainter(pm)
            ok = dessiner_schema(painter, QRectF(16, 16, pm.width() - 32, pm.height() - 32), schema)
            painter.setPen(QPen(QColor('#bbbbbb'), 2))
            painter.drawRect(QRectF(1, 1, pm.width() - 2, pm.height() - 2))
            painter.end()
            if not ok or not pm.save(chemin, 'PNG'):
                chemin = ''
        self._apercus[cle] = chemin
        return chemin

    def eventFilter(self, obj, ev):
        if obj is self.liste.viewport() and ev.type() == QEvent.Type.ToolTip:
            it = self.liste.itemAt(ev.pos())
            if it is None or self.liste.columnAt(ev.pos().x()) != 2:
                return super().eventFilter(obj, ev)
            e = entree_schema(self.plugin, self.couches, self._cle(it), self._sats)
            if not e:
                QToolTip.hideText()
                return True
            titre = '<b>%s</b> – %s' % (it.text(0).replace('<', '&lt;'), e.get('date') or '')
            chemin = self._apercu(e['schema'])
            if chemin:
                html = '%s<br><img src="%s" width="%d" height="%d">' % (
                    titre, QUrl.fromLocalFile(chemin).toString(), APERCU_L, APERCU_H)
            else:
                html = titre + i18n.tr('se_schema_vide_html')
            QToolTip.showText(ev.globalPos(), html, self.liste.viewport())
            return True
        return super().eventFilter(obj, ev)

    # --- liste
    def remplir(self):
        mag = magasin(self.plugin)
        courant = self._fid()
        self._sats = PF.satellites(self.couches)
        self.liste.setSortingEnabled(False)
        self.liste.clear()
        for role in ST.ROLES:
            couche = self.couches.get(role)
            if couche is None:
                continue
            for f in couche.getFeatures():
                if not ST.porte_schema(role, f):
                    continue
                cle = (role, f.id())
                e = mag.get(cle)
                typ = type_noeud(f, role)
                sat = self._sats.get(cle) if e is None else None
                if sat:
                    cr = ST.entite(self.couches, sat[0])
                    txt = '→ %s' % (libelle_noeud(cr) if cr is not None else '?')
                else:
                    txt = ('✔ ' + (e.get('date') or '')) if e else ''
                it = QTreeWidgetItem([libelle_noeud(f, role), R.libelle_type(typ), txt])
                it.setData(0, ROLE, f.id())
                it.setData(0, ROLE_COUCHE, role)
                if e:
                    it.setForeground(2, QColor('#2e7d32'))
                elif sat:
                    it.setForeground(2, QColor('#777777'))
                    it.setToolTip(2, i18n.tr('se_vanne_carrefour') % sat[1])
                if typ == 'vanne' and not sat and PF.est_carrefour(
                        PF.raccordements(QgsPointXY(f.geometry().asPoint()), self.couches)):
                    it.setText(1, it.text(1) + ' ⚠')
                    it.setForeground(1, QColor('#c62828'))
                    it.setToolTip(1, i18n.tr('se_vanne_angle_tip'))
                self.liste.addTopLevelItem(it)
                if cle == courant:
                    self.liste.setCurrentItem(it)
        self.liste.setSortingEnabled(True)
        self.liste.sortByColumn(0, Qt.SortOrder.AscendingOrder)
        self._filtrer(self.recherche.text())
        self._courant()

    def _filtrer(self, txt):
        v = M.sans_accents(txt.strip())
        for i in range(self.liste.topLevelItemCount()):
            it = self.liste.topLevelItem(i)
            it.setHidden(bool(v) and v not in M.sans_accents(it.text(0) + ' ' + it.text(1)))

    @staticmethod
    def _cle(it):
        return (it.data(0, ROLE_COUCHE), it.data(0, ROLE))

    def _fid(self):
        """Clé (rôle, fid) du nœud courant, ou None."""
        it = self.liste.currentItem()
        return self._cle(it) if it else None

    def selectionner(self, fid):
        for i in range(self.liste.topLevelItemCount()):
            it = self.liste.topLevelItem(i)
            if self._cle(it) == fid:
                it.setHidden(False)
                self.liste.setCurrentItem(it)
                self.liste.scrollToItem(it)
                return

    def _selection(self):
        """Clés des nœuds sélectionnés (visibles)."""
        return [self._cle(it) for it in self.liste.selectedItems() if not it.isHidden()]

    def _courant(self, *_a):
        from .schemaep_fenetre import PRESSE
        fid = self._fid()
        mag = magasin(self.plugin)
        sel = self._selection()
        self.b_ouvrir.setEnabled(fid is not None)
        a_suppr = self._a_supprimer()
        self.b_suppr.setEnabled(bool(a_suppr))
        self.b_suppr.setText(i18n.tr('se_suppr_schemas_n') % len(a_suppr) if len(a_suppr) > 1
                             else i18n.tr('se_suppr_schema'))
        self.b_copier.setEnabled(fid is not None and mag.get(fid) is not None)
        self.b_coller.setEnabled(bool(PRESSE['schema']) and bool(sel))
        self.b_coller.setText(i18n.tr('se_coller_sel_n') % len(sel) if len(sel) > 1 else i18n.tr('se_coller_sel'))
        self.lbl_copie.setText((i18n.tr('se_schema_copie_lbl') % PRESSE['source']) if PRESSE['schema']
                               else i18n.tr('se_aucun_copie'))
        if fid is not None:
            self.plugin.iface.mapCanvas().flashFeatureIds(self.couches[fid[0]], [fid[1]])

    # --- actions
    def _ouvrir(self):
        fid = self._fid()
        if fid is not None:
            ouvrir_fenetre(self.plugin, self.couches, fid)

    def _copier(self):
        from .schemaep_fenetre import copier_schema
        fid = self._fid()
        e = magasin(self.plugin).get(fid) if fid is not None else None
        if not e:
            return
        f = ST.entite(self.couches, fid)
        copier_schema(e['schema'], libelle_noeud(f, fid[0]) if f is not None else '', fid)
        self._courant()

    def _coller(self):
        """Colle le schéma copié sur les nœuds sélectionnés (le nœud d'origine
        est ignoré) ; confirmation si certains ont déjà un schéma."""
        from .schemaep_fenetre import PRESSE, schema_copie
        from .schemaep_sorties import svg_schema
        mag = magasin(self.plugin)
        cibles = [fid for fid in self._selection() if fid != PRESSE['fid'] and fid not in self._sats]
        if not PRESSE['schema'] or not cibles:
            return
        deja = [fid for fid in cibles if mag.get(fid)]
        if deja and QMessageBox.question(
                self, TITRE, i18n.tr('se_deja_schema')
                % (len(deja), PRESSE['source'])) != QMessageBox.StandardButton.Yes:
            return
        fen = getattr(self.plugin, '_schemaep_fen', None)
        fen_ouverte = fen if fen is not None and not sip.isdeleted(fen) and fen.isVisible() and fen.noeud else None
        ignores = []
        for fid in cibles:
            if fen_ouverte and fen_ouverte.noeud['fid'] == fid and fen_ouverte.modifie_non_enregistre():
                ignores.append(fen_ouverte.noeud['libelle'])   # modifications en cours : on n'y touche pas
                continue
            s = M.normalize(schema_copie())
            f = ST.entite(self.couches, fid)
            s['nom'] = libelle_noeud(f, fid[0]) if f is not None else ''
            mag.mettre(fid, s, svg_schema(s))
            if fen_ouverte and fen_ouverte.noeud['fid'] == fid:
                fen_ouverte.canevas.schema.charger(s)
                fen_ouverte.canevas.rafraichir()
                fen_ouverte.canevas.recentrer()
                fen_ouverte._marquer_enregistre()
        self.remplir()
        n = len(cibles) - len(ignores)
        msg = i18n.tr('se_colle_n' if n > 1 else 'se_colle_1', source=PRESSE['source'], n=n)
        if ignores:
            msg += i18n.tr('se_non_colle') \
                   % ', '.join(ignores)
        msg += i18n.tr('se_pensez')
        QMessageBox.information(self, TITRE, msg)

    def _fenetre_modifiee(self, cle):
        """Libellé du nœud si son schéma est ouvert avec des modifications non
        enregistrées (on n'y touche pas), sinon ''."""
        fen = getattr(self.plugin, '_schemaep_fen', None)
        if fen is not None and not sip.isdeleted(fen) and fen.isVisible() and fen.noeud \
                and fen.noeud['fid'] == cle and fen.modifie_non_enregistre():
            return fen.noeud['libelle']
        return ''

    def _recharger_fenetre(self, cle, s):
        fen = getattr(self.plugin, '_schemaep_fen', None)
        if fen is not None and not sip.isdeleted(fen) and fen.isVisible() and fen.noeud and fen.noeud['fid'] == cle:
            fen.canevas.schema.charger(s)
            fen.canevas.rafraichir()
            fen.canevas.recentrer()
            fen._marquer_enregistre()

    def _realigner(self):
        """Tourne les schémas sélectionnés au quart de tour le plus proche."""
        from .schemaep_sorties import svg_schema
        mag = magasin(self.plugin)
        faits, ignores = 0, []
        for cle in self._a_supprimer():
            if self._fenetre_modifiee(cle):
                ignores.append(self._fenetre_modifiee(cle))
                continue
            s = M.normalize(mag.get(cle)['schema'])
            if PF.realigner(s):
                mag.mettre(cle, s, svg_schema(s))
                self._recharger_fenetre(cle, s)
                faits += 1
        self.remplir()
        msg = i18n.tr('se_realigne_n' if faits > 1 else 'se_realigne_1', n=faits)
        if ignores:
            msg += i18n.tr('se_non_modifie') % ', '.join(ignores)
        QMessageBox.information(self, TITRE, msg + i18n.tr('se_pensez'))

    def _cibles_recreer(self):
        """Nœuds sélectionnés pouvant recevoir un schéma par défaut (pas les
        vannes dessinées dans le schéma de leur carrefour)."""
        mag = magasin(self.plugin)
        cles = self._selection() or ([self._fid()] if self._fid() is not None else [])
        return [c for c in cles if c not in self._sats or mag.get(c) is not None]

    def _recreer(self):
        """Remplace les schémas sélectionnés par le schéma calculé depuis la
        carte et les favoris (confirmation si certains existent)."""
        from .schemaep_fenetre import Favoris
        from .schemaep_sorties import svg_schema
        mag = magasin(self.plugin)
        cles = self._cibles_recreer()
        if not cles:
            return
        deja = [c for c in cles if mag.get(c)]
        if deja and QMessageBox.question(
                self, TITRE, i18n.tr('se_remplaces_defaut') % len(deja)) \
                != QMessageBox.StandardButton.Yes:
            return
        montages = Favoris().montages()
        carte = self._sats
        faits, ignores = 0, []
        for cle in cles:
            if self._fenetre_modifiee(cle):
                ignores.append(self._fenetre_modifiee(cle))
                continue
            s = schema_defaut(self.plugin, self.couches, cle, carte, montages, self)
            if s is None:
                continue
            s = M.normalize(s)
            mag.mettre(cle, s, svg_schema(s))
            self._recharger_fenetre(cle, s)
            faits += 1
        self.remplir()
        msg = i18n.tr('se_recree_n' if faits > 1 else 'se_recree_1', n=faits)
        if ignores:
            msg += i18n.tr('se_non_modifie') % ', '.join(ignores)
        QMessageBox.information(self, TITRE, msg + i18n.tr('se_pensez'))

    def _a_supprimer(self):
        """Clés des nœuds sélectionnés qui ont un schéma (à défaut de
        sélection : le nœud courant)."""
        mag = magasin(self.plugin)
        cles = self._selection() or ([self._fid()] if self._fid() is not None else [])
        return [c for c in cles if mag.get(c) is not None]

    def _supprimer(self):
        cles = self._a_supprimer()
        if not cles:
            return
        question = (i18n.tr('se_suppr_schemas_q') % len(cles) if len(cles) > 1
                    else i18n.tr('se_suppr_schema_q'))
        if QMessageBox.question(self, TITRE, question) != QMessageBox.StandardButton.Yes:
            return
        mag = magasin(self.plugin)
        for cle in cles:
            mag.supprimer(cle)
        fen = getattr(self.plugin, '_schemaep_fen', None)
        if fen is not None and not sip.isdeleted(fen) and fen.noeud and fen.noeud['fid'] in cles:
            fen._reference = None
            fen.close()
        self.remplir()

    def _choisir_carte(self):
        canvas = self.plugin.iface.mapCanvas()
        tool = _ChoixNoeudTool(canvas, self.couches)

        def fin(fid=None):
            self.plugin._deactivate_current()
            self.show()
            self.raise_()
            if fid is not None:
                self.selectionner(fid)
        tool.choisi.connect(lambda fid: fin(fid))
        tool.annule.connect(lambda: self.isHidden() and fin())
        self.hide()
        self.plugin._activate_tool('schemaep', tool)

    def _nomenclature(self):
        exec_dialog(NomenclatureChantier(self.plugin, self.couches, self))


class NomenclatureChantier(QDialog):
    """Total des pièces de tous les schémas de nœuds du projet."""

    def __init__(self, plugin, couches, parent=None):
        super().__init__(parent)
        self.setWindowTitle(i18n.tr('se_titre_nomenc'))
        self.resize(720, 560)
        tous = magasin(plugin).tous(couches)
        lignes = {}
        for cle, e, infos in tous:
            nom = infos.get('nom') or '#%s' % cle[1]
            for b in M.bom(M.normalize(e['schema'])['items']):
                k = (b['d'], b['u'])
                L = lignes.setdefault(k, {'d': b['d'], 'u': b['u'], 'q': 0, 'n': []})
                L['q'] += b['q']
                if nom not in L['n']:
                    L['n'].append(nom)
        self.lignes = sorted(lignes.values(), key=lambda b: M.cle_tri(b['d']))
        v = QVBoxLayout(self)
        v.addWidget(QLabel(i18n.tr('se_nb_schemas_n' if len(tous) > 1 else 'se_nb_schemas_1', n=len(tous))))
        t = QTableWidget(len(self.lignes), 4)
        t.setHorizontalHeaderLabels([i18n.tr('se_designation'), i18n.tr('se_qte'), 'U', i18n.tr('se_col_noeuds')])
        t.verticalHeader().setVisible(False)
        t.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        for r, b in enumerate(self.lignes):
            t.setItem(r, 0, QTableWidgetItem(b['d']))
            q = QTableWidgetItem(M.fq(b['q']))
            q.setTextAlignment(int(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter))
            t.setItem(r, 1, q)
            t.setItem(r, 2, QTableWidgetItem(b['u']))
            t.setItem(r, 3, QTableWidgetItem(', '.join(b['n'])))
        t.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        for c in (1, 2, 3):
            t.horizontalHeader().setSectionResizeMode(c, QHeaderView.ResizeMode.ResizeToContents)
        v.addWidget(t, 1)
        h = QHBoxLayout()
        b = QPushButton(i18n.tr('se_exporter_csv'))
        b.clicked.connect(self._csv)
        f = QPushButton(i18n.tr('se_fermer'))
        f.clicked.connect(self.accept)
        h.addWidget(b)
        h.addStretch(1)
        h.addWidget(f)
        v.addLayout(h)

    def _csv(self):
        f, _ = QFileDialog.getSaveFileName(self, i18n.tr('se_nomenc_schemas'), 'nomenclature-schemas-aep.csv',
                                           i18n.tr('se_filtre_csv'))
        if not f:
            return
        out = ['\ufeff' + i18n.tr('se_csv_entete')]
        for b in self.lignes:
            out.append('"%s";%s;%s;"%s"' % (b['d'].replace('"', '""'), M.n(M.r1(b['q'])).replace('.', ','),
                                            b['u'], ', '.join(b['n'])))
        with open(f, 'w', encoding='utf-8', newline='') as h:
            h.write('\n'.join(out))
