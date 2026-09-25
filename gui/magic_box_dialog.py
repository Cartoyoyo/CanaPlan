# gui/magic_box_dialog.py
"""Magic Box : fonctions automatiques, pilotées à coups de tuiles.

Branchements automatiques, tout à la souris :
    1. Quoi ?        → À la parcelle / Au bâti / Au numéro de rue ;
    2. Quel côté ?   → Les deux côtés / Gauche / Droite ;
    3. clic sur les tronçons (le réseau est celui de la conduite cliquée) ;
    4. aperçu en pointillés, puis Tracer ou Annuler.
Les branchements prennent le diamètre et le matériau standard du réseau.
"""

from qgis.core import Qgis, QgsGeometry, QgsPointXY, QgsWkbTypes
from qgis.gui import QgsMapTool, QgsRubberBand
from qgis.PyQt.QtCore import Qt, QSize, pyqtSignal
from qgis.PyQt.QtGui import QColor, QFont
from qgis.PyQt.QtWidgets import (
    QDialog, QDialogButtonBox, QGridLayout, QHBoxLayout, QLabel, QMessageBox, QPushButton,
    QStackedWidget, QTextEdit, QToolButton, QVBoxLayout, QWidget,
)

from ..tools import i18n
from ..tools import magic_branchements as MB
from ..tools.qt_exec import exec_dialog
from ..tools.spatial_utils import nearest_line_feature
from .quick_config_widgets import NETWORK_COLORS

DISTANCE_MAX = 10.0      # m, conduite → limite de parcelle


# Ambiance boîte à rythmes (Launchpad / MPC) : panneau noir, pads carrés à
# bord néon qui s'allument au survol et flashent à la frappe.
_FOND = "#141414"
_STYLE_PANNEAU = (
    "QDialog { background: %s; } "
    "QLabel { color: #E0E0E0; } "
    "QPushButton { background: #262626; color: #E0E0E0; border: 1px solid #444; "
    "border-radius: 6px; padding: 4px 10px; } "
    "QPushButton:hover { border-color: #888; } "
    "QPushButton:checked { background: #333; } "
    "QTextEdit { background: #1E1E1E; color: #CCCCCC; border: 1px solid #333; }"
    % _FOND)


def _habiller(dialogue):
    dialogue.setStyleSheet(_STYLE_PANNEAU)


def _police_ecran(taille, gras=True):
    """Police des sérigraphies de l'appareil : chasse fixe."""
    f = QFont("Consolas", taille)
    f.setStyleHint(QFont.StyleHint.Monospace)
    f.setBold(gras)
    f.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing, 1.0)
    return f


def _tuile(emoji, texte, couleur, tip="", taille=(140, 140)):
    """Pad de boîte à rythmes : gros emoji au-dessus, libellé en capitales
    dessous, sur deux lignes au besoin. Les étiquettes laissent passer la
    souris : c'est le bouton qui reçoit survol et frappe."""
    b = QToolButton()
    b.setToolTip(tip)
    b.setFixedSize(QSize(*taille))
    b.setCursor(Qt.CursorShape.PointingHandCursor)
    c = QColor(couleur)
    lueur = "rgba(%d, %d, %d, 70)" % (c.red(), c.green(), c.blue())
    b.setStyleSheet(
        "QToolButton { background: #232323; border: 3px solid %s; "
        "border-radius: 10px; } "
        "QToolButton:hover { background: %s; border: 4px solid %s; } "
        "QToolButton:pressed { background: %s; } "
        "QToolButton:disabled { border-color: #333; }"
        % (couleur, lueur, c.lighter(130).name(), couleur))

    pile = QVBoxLayout(b)
    pile.setContentsMargins(6, 8, 6, 8)
    pile.setSpacing(4)
    haut = taille[1] >= 120
    icone = QLabel(emoji)
    fi = QFont(); fi.setPointSize(30 if haut else 20)
    icone.setFont(fi)
    libelle = QLabel(texte.upper())
    libelle.setFont(_police_ecran(9))
    libelle.setWordWrap(True)
    for lbl, style in ((icone, "background: transparent;"),
                       (libelle, "background: transparent; color: %s;"
                                 % c.lighter(130).name())):
        if lbl is icone:
            # Les glyphes (flèches, ▶ ■) prennent la couleur du pad ; les
            # emojis en couleur gardent la leur.
            style += " color: %s;" % c.lighter(130).name()
        lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lbl.setStyleSheet(style)
        lbl.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        pile.addWidget(lbl)
    return b


def _pad_vide():
    """Pad éteint : emplacement des prochaines fonctions."""
    b = QToolButton()
    b.setFixedSize(QSize(140, 140))
    b.setEnabled(False)
    b.setStyleSheet("QToolButton { background: #1C1C1C; border: 2px solid #2C2C2C; "
                    "border-radius: 10px; }")
    return b


def _leds(i, n):
    """Voyants de progression : vert allumé jusqu'à l'étape courante."""
    return "&nbsp;&nbsp;".join(
        "<span style='color:%s; font-size:16pt'>●</span>"
        % ("#00E676" if k <= i else "#3A3A3A") for k in range(n))


def _majuscule(texte):
    return texte[:1].upper() + texte[1:]


# ── Fenêtre d'accueil ───────────────────────────────────────────────────────

class MagicBoxDialog(QDialog):
    """Une tuile par fonction automatique. `choix()` après exec."""

    FONCTIONS = (
        ('branchements_auto', "🔌", 'mb_branchements_court', 'mb_branchements_auto_tip'),
    )
    COLONNES, LIGNES = 2, 2

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle(i18n.tr('magic_box'))
        _habiller(self)
        self._choix = None
        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        titre = QLabel("🪄 MAGIC BOX")
        titre.setFont(_police_ecran(18))
        titre.setStyleSheet("color: #E040FB;")
        titre.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(titre)
        aide = QLabel(i18n.tr('mb_aide').upper())
        aide.setFont(_police_ecran(8, gras=False))
        aide.setStyleSheet("color: #888;")
        aide.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(aide)

        grille = QGridLayout()
        grille.setSpacing(10)
        for k in range(self.COLONNES * self.LIGNES):
            if k < len(self.FONCTIONS):
                cle, emoji, cle_libelle, cle_tip = self.FONCTIONS[k]
                b = _tuile(emoji, i18n.tr(cle_libelle), "#E040FB",
                           i18n.tr(cle_tip))
                b.clicked.connect(lambda _=False, c=cle: self._choisir(c))
            else:
                b = _pad_vide()
            grille.addWidget(b, k // self.COLONNES, k % self.COLONNES)
        layout.addLayout(grille)

        btns = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        btns.rejected.connect(self.reject)
        layout.addWidget(btns)

    def _choisir(self, cle):
        self._choix = cle
        self.accept()

    def choix(self):
        return self._choix


# ── Assistant à tuiles ──────────────────────────────────────────────────────

class BranchementsAutoDialog(QDialog):
    """Quoi ? → Quel côté ? Chaque clic de tuile avance d'un écran ; la
    tuile du côté ferme la fenêtre et lance la sélection des tronçons."""

    _EMOJIS_MODE = {'parcelle': "🏡", 'bati': "🏠", 'numero': "🔢"}
    _COULEURS_MODE = {'parcelle': "#00E676", 'bati': "#FF9100", 'numero': "#E040FB"}
    _EMOJIS_COTE = {'deux': "◀ ▶", 'gauche': "◀", 'droite': "▶"}
    _QUESTIONS = ('mb_etape_mode', 'mb_etape_cote')

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("🪄 " + i18n.tr('mb_branchements_auto'))
        _habiller(self)
        self._choix = {'mode': None, 'cote': None}

        layout = QVBoxLayout(self)
        entete = QHBoxLayout()
        self._retour = QPushButton("◀ " + i18n.tr('mb_retour'))
        self._retour.clicked.connect(lambda: self._afficher(0))
        entete.addWidget(self._retour)
        entete.addStretch()
        self._progression = QLabel()
        entete.addWidget(self._progression)
        layout.addLayout(entete)

        self._question = QLabel()
        self._question.setFont(_police_ecran(13))
        self._question.setStyleSheet("color: #FFD600;")
        self._question.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self._question)

        self._pages = QStackedWidget()
        self._pages.addWidget(self._page_tuiles([
            (self._EMOJIS_MODE[m], _majuscule(i18n.tr('mb_mode_%s' % m)),
             self._COULEURS_MODE[m], i18n.tr('mb_mode_%s_tip' % m),
             lambda _=False, m=m: self._choisir_mode(m))
            for m in MB.MODES]))
        self._pages.addWidget(self._page_tuiles([
            (self._EMOJIS_COTE[c], i18n.tr('mb_cote_%s' % c), "#00B0FF", "",
             lambda _=False, c=c: self._choisir_cote(c))
            for c in MB.COTES]))
        layout.addWidget(self._pages)
        self._afficher(0)

    def _page_tuiles(self, tuiles):
        page = QWidget()
        ligne = QHBoxLayout(page)
        ligne.setSpacing(10)
        ligne.addStretch()
        for emoji, texte, couleur, tip, action in tuiles:
            b = _tuile(emoji, texte, couleur, tip)
            b.clicked.connect(action)
            ligne.addWidget(b)
        ligne.addStretch()
        return page

    def _afficher(self, i):
        self._pages.setCurrentIndex(i)
        self._question.setText(i18n.tr(self._QUESTIONS[i]))
        self._progression.setText(_leds(i, len(self._QUESTIONS)))
        self._retour.setVisible(i > 0)

    def _choisir_mode(self, mode):
        manquantes = MB.couches_manquantes(mode)
        if manquantes:
            QMessageBox.warning(self, self.windowTitle(),
                                i18n.tr('mb_couches_manquantes',
                                        noms=", ".join(manquantes)))
            return
        self._choix['mode'] = mode
        self._afficher(1)

    def _choisir_cote(self, cote):
        self._choix['cote'] = cote
        self.accept()

    def parametres(self):
        return dict(self._choix)


# ── Sélection des tronçons ──────────────────────────────────────────────────

class SelectionConduitesTool(QgsMapTool):
    """Clic = ajoute/retire une conduite ; clic droit ou Entrée = valide.

    Le réseau est celui de la première conduite cliquée ; les conduites d'un
    autre réseau sont ensuite ignorées (avec un message).
    """

    valide = pyqtSignal(str, list)
    annule = pyqtSignal()

    def __init__(self, canvas, couches_par_reseau):
        super().__init__(canvas)
        self.canvas = canvas
        self.couches = couches_par_reseau     # {reseau: jeu de couches}
        self.reseau = None
        self._bandes = {}      # fid -> QgsRubberBand
        self._fini = False

    def activate(self):
        super().activate()
        self.canvas.setCursor(Qt.CursorShape.PointingHandCursor)
        self._message(i18n.tr('mb_aide_selection'), Qgis.MessageLevel.Info, 0)

    def deactivate(self):
        from qgis.utils import iface
        iface.messageBar().clearWidgets()
        self._effacer()
        if not self._fini:
            self._fini = True
            self.annule.emit()
        super().deactivate()

    def _message(self, texte, niveau, duree):
        from qgis.utils import iface
        iface.messageBar().pushMessage("🪄 " + i18n.tr('magic_box'), texte,
                                       level=niveau, duration=duree)

    def _effacer(self):
        for b in self._bandes.values():
            self.canvas.scene().removeItem(b)
        self._bandes.clear()

    def _conduite_proche(self, pt):
        """(reseau, feature) de la conduite la plus proche du clic."""
        tol = 10 * self.canvas.mapUnitsPerPixel()
        meilleur = (None, None, float('inf'))
        for reseau, jeu in self.couches.items():
            feat, _p, d = nearest_line_feature(jeu['conduite'], pt, tol)
            if feat is not None and d < meilleur[2]:
                meilleur = (reseau, feat, d)
        return meilleur[0], meilleur[1]

    def canvasReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.RightButton:
            self._valider()
            return
        if event.button() != Qt.MouseButton.LeftButton:
            return
        reseau, feat = self._conduite_proche(
            QgsPointXY(self.toMapCoordinates(event.pos())))
        if feat is None:
            return
        if self.reseau is not None and reseau != self.reseau:
            self._message(i18n.tr('mb_autre_reseau', reseau=self.reseau),
                          Qgis.MessageLevel.Warning, 3)
            return
        fid = feat.id()
        if fid in self._bandes:
            self.canvas.scene().removeItem(self._bandes.pop(fid))
            if not self._bandes:
                self.reseau = None
            return
        self.reseau = reseau
        b = QgsRubberBand(self.canvas, QgsWkbTypes.GeometryType.LineGeometry)
        b.setColor(QColor(255, 140, 0, 200))
        b.setWidth(6)
        b.setToGeometry(feat.geometry(), self.couches[reseau]['conduite'])
        self._bandes[fid] = b

    def keyPressEvent(self, event):
        if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            self._valider()
        elif event.key() == Qt.Key.Key_Escape:
            self._fini = True
            self.annule.emit()

    def _valider(self):
        if not self._bandes:
            self._message(i18n.tr('mb_aucune_conduite'),
                          Qgis.MessageLevel.Warning, 3)
            return
        self._fini = True
        self.valide.emit(self.reseau, list(self._bandes.keys()))


# ── Aperçu ──────────────────────────────────────────────────────────────────

class ApercuDialog(QDialog):
    """Fenêtre non modale : la carte reste navigable pendant l'aperçu."""

    def __init__(self, n, reseau, ecartes, parent=None):
        super().__init__(parent)
        self.setWindowTitle("🪄 " + i18n.tr('mb_apercu'))
        self.setModal(False)
        self.setMinimumWidth(380)
        _habiller(self)
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel(i18n.tr('mb_apercu_resume', n=n, reseau=reseau,
                                        e=len(ecartes))))
        if ecartes:
            detail = QTextEdit()
            detail.setReadOnly(True)
            detail.setPlainText("\n".join(
                "• %s : %s" % (e.get("cible") or "?", e["cause"]) for e in ecartes))
            detail.setMaximumHeight(140)
            detail.setVisible(False)
            bouton = QPushButton(i18n.tr('mb_details'))
            bouton.setCheckable(True)
            bouton.toggled.connect(detail.setVisible)
            layout.addWidget(bouton)
            layout.addWidget(detail)

        ligne = QHBoxLayout()
        tracer = _tuile("▶", i18n.tr('mb_tracer'), "#00E676", taille=(140, 90))
        tracer.setEnabled(n > 0)
        tracer.clicked.connect(self.accept)
        annuler = _tuile("■", i18n.tr('mb_annuler'), "#FF1744", taille=(140, 90))
        annuler.clicked.connect(self.reject)
        ligne.addStretch()
        ligne.addWidget(tracer)
        ligne.addWidget(annuler)
        ligne.addStretch()
        layout.addLayout(ligne)


# ── Enchaînement ────────────────────────────────────────────────────────────

class MagicBranchements:
    """Pilote tuiles → sélection → aperçu → tracé."""

    def __init__(self, plugin):
        self.plugin = plugin
        self.iface = plugin.iface
        self.canvas = self.iface.mapCanvas()
        self.params = None
        self.reseau = None
        self.couches = None
        self.propositions = []
        self._bandes = []
        self._apercu = None
        self._outil = None

    def demarrer(self):
        dlg = BranchementsAutoDialog(self.iface.mainWindow())
        if exec_dialog(dlg) != QDialog.DialogCode.Accepted:
            return
        self.params = dlg.parametres()
        couches = {r: self.plugin._get_couches(r)
                   for r in self.plugin.reseaux_actifs()}
        self._outil = SelectionConduitesTool(self.canvas, couches)
        self._outil.valide.connect(self._sur_selection)
        self._outil.annule.connect(self._fin_outil)
        self.plugin._activate_tool('magic_box', self._outil)

    def _fin_outil(self):
        if self._outil is not None and self.canvas.mapTool() is self._outil:
            self.plugin._deactivate_current()
        self._outil = None

    def _sur_selection(self, reseau, fids):
        self._fin_outil()
        self.reseau = reseau
        self.couches = self.plugin._get_couches(reseau)
        p = self.params
        res = MB.calculer(self.couches, fids, p['mode'], DISTANCE_MAX, p['cote'])
        self.propositions = res['propositions']
        if not self.propositions and not res['ecartes']:
            self.iface.messageBar().pushMessage(
                "🪄 " + i18n.tr('magic_box'), i18n.tr('mb_rien'),
                level=Qgis.MessageLevel.Warning, duration=5)
            return
        self._dessiner_apercu()
        self._apercu = ApercuDialog(len(self.propositions), reseau,
                                    res['ecartes'], self.iface.mainWindow())
        self._apercu.accepted.connect(self._tracer)
        self._apercu.rejected.connect(self._effacer_apercu)
        self._apercu.show()

    def _dessiner_apercu(self):
        self._effacer_apercu()
        couleur = QColor(NETWORK_COLORS.get(self.reseau, '#7B1FA2'))
        lignes = QgsRubberBand(self.canvas, QgsWkbTypes.GeometryType.LineGeometry)
        lignes.setColor(couleur)
        lignes.setWidth(3)
        lignes.setLineStyle(Qt.PenStyle.DashLine)
        points = QgsRubberBand(self.canvas, QgsWkbTypes.GeometryType.PointGeometry)
        points.setColor(couleur)
        points.setIconSize(9)
        points.setIcon(QgsRubberBand.IconType.ICON_BOX)
        couche = self.couches['conduite']
        for p in self.propositions:
            lignes.addGeometry(QgsGeometry.fromPolylineXY([p['pa'], p['pb']]), couche)
            points.addPoint(QgsPointXY(p['pb']))
        self._bandes = [lignes, points]
        self.canvas.refresh()

    def _effacer_apercu(self):
        for b in self._bandes:
            self.canvas.scene().removeItem(b)
        self._bandes = []

    def _tracer(self):
        self._effacer_apercu()
        # Diamètre et matériau : les valeurs standard du réseau.
        res = MB.tracer(self.canvas, self.reseau, self.couches, self.propositions)
        self.canvas.refresh()
        self.iface.messageBar().pushMessage(
            "🪄 " + i18n.tr('magic_box'),
            "🎉 " + i18n.tr('mb_resultat', n=res['faits'], reseau=self.reseau),
            level=Qgis.MessageLevel.Success, duration=6)
        if res['echecs']:
            QMessageBox.warning(
                self.iface.mainWindow(), i18n.tr('magic_box'),
                i18n.tr('mb_echecs', n=len(res['echecs'])) + "\n" + "\n".join(
                    "• %s : %s" % (e.get('cible') or "?", e['cause'])
                    for e in res['echecs']))


def ouvrir_magic_box(plugin):
    """Point d'entrée du bouton Magic Box."""
    dlg = MagicBoxDialog(plugin.iface.mainWindow())
    if exec_dialog(dlg) != QDialog.DialogCode.Accepted:
        return
    if dlg.choix() == 'branchements_auto':
        # Gardé sur le plugin : l'aperçu non modal survit à cette fonction.
        plugin._magic_branchements = MagicBranchements(plugin)
        plugin._magic_branchements.demarrer()
