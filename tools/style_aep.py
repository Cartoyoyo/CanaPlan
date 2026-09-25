# tools/style_aep.py
"""Symbologie des nœuds et terminaux AEP, pilotée par le champ `type`.

Les symboles d'appareils sont ceux du géostandard StaR-Eau (collection
« eau_potable » du dépôt github.com/cnigfr/StaR-Eau, ASTEE / CNIG, Licence
Ouverte Etalab 2.0), embarqués dans icon/stareau_aep/. Ce sont des SVG
paramétrables : QGIS les teinte à la couleur du réseau.

Les tailles sont en unités carte, comme les regards et tabourets EU/EP : leur
emprise au sol ne dépend pas du zoom, et le plan au 1/200 garde les
proportions de l'écran.

Vannes et régulateurs sont orientés le long de la conduite qui les porte ;
l'extrémité libre d'un branchement, perpendiculairement à son dernier
segment. Les identifiants des couches conduite et branchement sont lus dans
des variables de projet à l'évaluation, pas figés dans le style : les couches
peuvent être recréées ou rechargées depuis le .bet.

Nœuds muets (coude, té, réduction, bouchon) : ils portent la topologie mais
ne se dessinent pas sur le plan. Un point discret les montre seulement plus
près que le 1/150, pour pouvoir les saisir ; il disparaît à toute échelle
d'impression courante.

Affleurants (bouches à clé) : la BAC n'est pas un objet de la donnée. Elle
s'affiche en surimpression sur les vannes et robinets de branchement quand la
variable de projet `canaplan_aep_affleurants` vaut 1 — pure règle de rendu.
"""
import os

from qgis.core import (
    Qgis, QgsRuleBasedRenderer, QgsSymbol, QgsSimpleMarkerSymbolLayer,
    QgsSvgMarkerSymbolLayer, QgsWkbTypes, QgsProperty, QgsSymbolLayer,
    QgsProject, QgsExpressionContextUtils,
)
from qgis.PyQt.QtCore import QPointF
from qgis.PyQt.QtGui import QColor

from . import reseaux as R

VAR_AFFLEURANTS = 'canaplan_aep_affleurants'
_ECHELLE_MUETS = 150          # dénominateur : muets visibles plus près que 1/150

_DOSSIER_SVG = os.path.join(os.path.dirname(os.path.dirname(__file__)),
                            'icon', 'stareau_aep')
SOURCE_SYMBOLES = "Symboles StaR-Eau (ASTEE / CNIG), Licence Ouverte Etalab 2.0"

# code: (fichier SVG StaR-Eau, taille en m, orienté sur la conduite, ancrage)
#
# Orienté : le symbole tourne avec la conduite qui porte le nœud (vanne et
# régulateur dans l'axe ; vidange, dessinée sur un axe vertical,
# lui devient perpendiculaire).
# Ancrage : point du dessin posé sur le nœud, en fraction de la taille depuis
# le centre (vers le bas positif), None = centré.
#
# Vidange : la conduite arrive au centre du rond, la flèche part vers
# l'extérieur. Plutôt qu'un décalage (le SVG StaR-Eau n'est pas carré, 99,2 x
# 136,9, et un décalage tourne mal avec le symbole), on utilise une variante
# recadrée sur le centre du rond, AEP_PURGE_CENTRE_ROND.svg : 136 unités de
# côté au lieu de 99,2 de large, d'où le facteur d'échelle pour garder la
# même taille de dessin.
_ECHELLE_PURGE = 136.0 / 99.213
_SVG_NOEUDS = {
    'vanne':              ('AEP_VANNES_RESEAU.svg',             0.9, True,  None),
    'ventouse':           ('AEP_VENTOUSE.svg',                  1.0, False, None),
    'vidange':            ('AEP_PURGE_CENTRE_ROND.svg', 1.5 * _ECHELLE_PURGE, True, None),
    'poteau_incendie':    ('AEP_POTEAU_INCENDIE.svg',           1.2, False, None),
    'bouche_incendie':    ('AEP_BOUCHE_INCENDIE.svg',           1.0, False, None),
    'reducteur_pression': ('AEP_REGULATEUR_DEBIT_PRESSION.svg', 1.0, True,  None),
    'compteur':           ('AEP_COMPTEUR_DEBIT.svg',            1.0, False, None),
}
# Symboles bicolores : le SVG StaR-Eau oppose le remplissage (param fill) au
# trait (param outline). Teints d'une seule couleur, ils perdent leur dessin —
# le poteau incendie, disque à moitié plein, devenait un disque uni.
_FONDS_SVG = {'poteau_incendie': QColor(255, 255, 255)}

# Le rond du SVG ne couvre que 53 % du cadre : à 1.05 il mesure ~0.56 m,
# soit plus gros que le robinet de branchement (_TAILLE_ROBINET).
_SVG_TERMINAL_COMPTEUR = ('AEP_COMPTEUR_BRANCHEMENT.svg', 1.05)
# Azimut de la flèche dans le SVG du compteur (centre du rond → pointe),
# en degrés depuis le nord : sert à la faire pivoter vers le branchement.
_AZIMUT_FLECHE_COMPTEUR = 47.7


def _chemin_svg(nom):
    return os.path.join(_DOSSIER_SVG, nom)


def _svg(nom, taille, couleur, angle_expr=None, ancre=None, fond=None):
    sl = QgsSvgMarkerSymbolLayer(_chemin_svg(nom), taille)
    if ancre:
        # Décalage appliqué avant la rotation : l'ancre suit la conduite.
        sl.setOffset(QPointF(0.0, -ancre * taille))
        sl.setOffsetUnit(Qgis.RenderUnit.MapUnits)
    sl.setSizeUnit(Qgis.RenderUnit.MapUnits)
    sl.setFillColor(fond if fond is not None else couleur)
    sl.setStrokeColor(couleur)
    sl.setStrokeWidth(0.05)
    sl.setStrokeWidthUnit(Qgis.RenderUnit.MapUnits)
    if angle_expr:
        sl.setDataDefinedProperty(QgsSymbolLayer.Property.PropertyAngle,
                                  QgsProperty.fromExpression(angle_expr))
    return sl


def _marker(forme, taille, couleur, fond=None, trait=0.08, angle_expr=None):
    ml = QgsSimpleMarkerSymbolLayer(forme, taille)
    ml.setSizeUnit(Qgis.RenderUnit.MapUnits)
    ml.setColor(fond if fond is not None else couleur)
    ml.setStrokeColor(couleur)
    ml.setStrokeWidth(trait)
    ml.setStrokeWidthUnit(Qgis.RenderUnit.MapUnits)
    if angle_expr:
        ml.setDataDefinedProperty(QgsSymbolLayer.Property.PropertyAngle,
                                  QgsProperty.fromExpression(angle_expr))
    return ml


def _symbole(*couches):
    sym = QgsSymbol.defaultSymbol(QgsWkbTypes.GeometryType.PointGeometry)
    sym.deleteSymbolLayer(0)
    for c in couches:
        sym.appendSymbolLayer(c)
    return sym


# Orientation : lue dans deux champs de la couche elle-même, calculés en
# Python par aep_topo.recalculer_orientations après chaque enregistrement.
# Surtout pas de overlay_nearest() sur les couches conduite ou branchement :
# ces fonctions lisent une AUTRE couche depuis les fils de rendu, et QGIS
# plante quand cette couche est modifiée au même moment (dessin d'un
# branchement). Constaté le 21/09/2026.
#   sym_angle : nœud = azimut de la conduite − 90 (SVG dessinés à l'horizontale
#               pour la vanne, à la verticale pour la vidange) ;
#               compteur = azimut du dernier segment du branchement + 90
#               (sa flèche est ensuite tournée vers le branchement).
#   sym_dir   : nœud = azimut du branchement qui en part (robinet), sinon NULL.

def _expr_axe_conduite():
    return 'coalesce("sym_angle", 0)'


def _expr_angle_branchement():
    return 'coalesce("sym_angle", 0)'


def _expr_angle_compteur():
    """Rotation du compteur : flèche pointée vers le branchement.

    sym_angle = azimut du dernier segment du branchement + 90 ; la direction
    compteur → branchement est cet azimut + 180, soit sym_angle + 90. Sans
    branchement raccordé, le symbole garde son dessin d'origine.
    """
    return ('if("sym_angle" IS NULL, 0, '
            f'"sym_angle" + 90 - {_AZIMUT_FLECHE_COMPTEUR})')


_TAILLE_ROBINET = 0.37        # m, plus petit que le rond du compteur
_DECALAGE_ROBINET = 0.35      # m, vers le branchement


def _expr_decalage_robinet():
    """Décalage « x,y » du robinet vers son branchement.

    Le nœud reste sur la conduite (c'est lui qui porte la topologie) ; seul
    le symbole glisse de _DECALAGE_ROBINET dans la direction du branchement
    (champ sym_dir), pour ne pas se confondre avec la conduite principale.
    En unités carte, l'axe y du décalage pointe vers le bas : d'où le signe
    de la composante nord. Sans direction connue, le symbole reste centré.
    """
    d = _DECALAGE_ROBINET
    return (
        "if(\"sym_dir\" IS NULL, '0,0', "
        f"concat(to_string(sin(radians(\"sym_dir\")) * {d}), ',', "
        f"to_string(-cos(radians(\"sym_dir\")) * {d})))"
    )


def _regle(racine, symbole, filtre, libelle, echelle_max=0):
    racine.appendChild(
        QgsRuleBasedRenderer.Rule(symbole, 0, echelle_max, filtre, libelle))


def appliquer_style_aep(layer, role, couleur):
    """Pose le rendu par règles sur une couche de nœuds ('regard') ou de
    terminaux ('tabouret') AEP."""
    racine = QgsRuleBasedRenderer.Rule(None)
    M = Qgis.MarkerShape

    if role == 'regard':
        for code, (nom, taille, oriente, ancre) in _SVG_NOEUDS.items():
            angle = _expr_axe_conduite() if oriente else None
            _regle(racine, _symbole(_svg(nom, taille, couleur, angle, ancre,
                                         _FONDS_SVG.get(code))),
                   f"\"type\" = '{code}'", R.libelle_type(code))
        # Pas de symbole StaR-Eau pour ces deux-là : le robinet de branchement
        # est un rond plein (spécification), le raccordement une croix.
        robinet = _marker(M.Circle, _TAILLE_ROBINET, couleur)
        robinet.setOffsetUnit(Qgis.RenderUnit.MapUnits)
        robinet.setDataDefinedProperty(
            QgsSymbolLayer.Property.PropertyOffset,
            QgsProperty.fromExpression(_expr_decalage_robinet()))
        _regle(racine, _symbole(robinet),
               "\"type\" = 'robinet_branchement'",
               R.libelle_type('robinet_branchement'))
        _regle(racine, _symbole(_marker(M.Cross2, 1.0, couleur, trait=0.12)),
               "\"type\" = 'raccordement_existant'",
               R.libelle_type('raccordement_existant'))
        muets = ", ".join(f"'{c}'" for c, (d, _p) in R.AEP_NOEUD_TYPES.items()
                          if not d)
        _regle(racine, _symbole(_marker(M.Circle, 0.15, couleur)),
               f"\"type\" IS NULL OR \"type\" IN ({muets})",
               R.libelle_type(R.AEP_NOEUD_TYPE_DEFAUT),
               echelle_max=_ECHELLE_MUETS)
        # Surimpression des bouches à clé (option de rendu). Sur un robinet,
        # la BAC suit le symbole décalé vers le branchement.
        bac = _marker(M.Circle, 0.9, couleur, fond=QColor(0, 0, 0, 0), trait=0.06)
        bac.setOffsetUnit(Qgis.RenderUnit.MapUnits)
        bac.setDataDefinedProperty(
            QgsSymbolLayer.Property.PropertyOffset,
            QgsProperty.fromExpression(
                "if(\"type\" = 'robinet_branchement', "
                f"{_expr_decalage_robinet()}, '0,0')"))
        _regle(racine,
               _symbole(bac),
               f"coalesce(@{VAR_AFFLEURANTS}, 0) = 1 AND "
               "\"type\" IN ('vanne', 'robinet_branchement')",
               "BAC")

    else:   # terminaux
        nom, taille = _SVG_TERMINAL_COMPTEUR
        _regle(racine,
               _symbole(_svg(nom, taille, couleur, _expr_angle_compteur())),
               "coalesce(\"type\", 'regard_compteur') = 'regard_compteur'",
               R.libelle_type('regard_compteur'))
        _regle(racine,
               _symbole(_marker(M.Line, 0.6, couleur, trait=0.1,
                                angle_expr=_expr_angle_branchement())),
               "\"type\" = 'extremite_libre'",
               R.libelle_type('extremite_libre'))

    layer.setRenderer(QgsRuleBasedRenderer(racine))
    layer.triggerRepaint()


def publier_variables(couches_aep):
    """Branche le recalcul des orientations sur les enregistrements des
    couches AEP (nom historique : le style lisait autrefois des variables de
    projet pointant vers ces couches)."""
    if not couches_aep:
        return
    from .aep_topo import brancher_orientations
    brancher_orientations(couches_aep)


def affleurants_actifs():
    val = QgsExpressionContextUtils.projectScope(QgsProject.instance()) \
        .variable(VAR_AFFLEURANTS)
    return str(val) in ('1', 'True', 'true')


def set_affleurants(actif):
    QgsExpressionContextUtils.setProjectVariable(
        QgsProject.instance(), VAR_AFFLEURANTS, 1 if actif else 0)
