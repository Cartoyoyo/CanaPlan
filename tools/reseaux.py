# tools/reseaux.py
"""Registre des réseaux dessinés par CanaPlan : EU, EP et AEP.

Tout ce qui distingue un réseau d'un autre vit ici, pas dans les outils :
couleurs, libellés, et pour l'AEP les types de nœuds et de terminaux, leurs
préfixes de numérotation et la couverture par défaut.

Les quatre rôles de couche sont les mêmes pour les trois réseaux ; seul leur
sens métier change en AEP :

    rôle          EU / EP        AEP
    conduite      collecteur     conduite principale
    branchement   branchement    branchement PE
    regard        regard         nœud (appareil ou nœud muet, champ `type`)
    tabouret      tabouret       terminal (regard compteur, extrémité libre)

Cette correspondance laisse intacts le dessin, le déplacement avec recalage
des branchements, la suppression, les profils et la cubature : un nœud AEP
est un point de la topologie comme un regard.

Altimétrie AEP : le réseau est sous pression, sans pente imposée. Le champ
`fe_radier` des nœuds garde son nom et son sens (fil d'eau = génératrice
inférieure intérieure) ; il se déduit de la couverture :
    fe_radier = TN − couverture − DN / 1000
de sorte que profils, cubature et coupes le lisent comme en EU/EP.

Les codes de type sont des valeurs normatives : stockés tels quels, jamais
traduits. Seuls leurs libellés passent par i18n (clé `aep_t_<code>`).
"""
from qgis.PyQt.QtGui import QColor

RESEAUX = ('EU', 'EP', 'AEP')
GRAVITAIRES = ('EU', 'EP')

_RGB = {
    'EU':  (255, 0, 0),
    'EP':  (0, 0, 255),
    'AEP': (0, 150, 190),     # cyan foncé : convention eau potable, lisible sur ortho
}
# Teintes des rapports et graphiques (texte foncé, fond clair).
HEX_FONCE = {'EU': '#CC0000', 'EP': '#0044CC', 'AEP': '#00838F'}
HEX_CLAIR = {'EU': '#FFECEC', 'EP': '#ECF0FF', 'AEP': '#E0F7FA'}


def couleur(reseau, alpha=255):
    r, g, b = _RGB.get(reseau, (90, 90, 90))
    return QColor(r, g, b, alpha)


def hex_fonce(reseau):
    return HEX_FONCE.get(reseau, '#444444')


def hex_clair(reseau):
    return HEX_CLAIR.get(reseau, '#F4F4F4')


def est_aep(reseau):
    return (reseau or '').upper() == 'AEP'


# ── AEP : nœuds ─────────────────────────────────────────────────────────────

# code: (dessiné, préfixe de numérotation)
AEP_NOEUD_TYPES = {
    'vanne':                 (True,  'V'),
    'robinet_branchement':   (True,  'RB'),
    'ventouse':              (True,  'VT'),
    'vidange':               (True,  'VD'),
    'poteau_incendie':       (True,  'PI'),
    'bouche_incendie':       (True,  'BI'),
    'reducteur_pression':    (True,  'RP'),
    'compteur':              (True,  'CPT'),
    'raccordement_existant': (True,  None),
    'te':                    (False, None),
    'reducteur_dn':          (False, None),
    'coude':                 (False, None),
    'bouchon':               (False, None),
}
AEP_NOEUD_TYPE_DEFAUT = 'coude'      # lecture : nœud sans type (données anciennes, import)
AEP_NOEUD_TYPE_CREATION = 'vanne'    # écriture : type posé à la création d'un nœud
AEP_NOEUD_BRANCHEMENT = 'robinet_branchement'   # posé au piquage par l'outil branchement

# Types qu'un opérateur choisit à la main (le robinet de branchement est posé
# par l'outil branchement, les coudes par l'outil conduite).
AEP_NOEUD_TYPES_MANUELS = tuple(
    c for c in AEP_NOEUD_TYPES if c not in (AEP_NOEUD_BRANCHEMENT,))


def aep_dessine(code):
    return AEP_NOEUD_TYPES.get(code, (False, None))[0]


def aep_prefixe(code):
    return AEP_NOEUD_TYPES.get(code, (False, None))[1]


def aep_numerotes():
    """Codes numérotés, dans l'ordre du registre."""
    return [c for c, (_d, p) in AEP_NOEUD_TYPES.items() if p]


# ── AEP : terminaux ─────────────────────────────────────────────────────────

AEP_TERMINAL_TYPES = ('regard_compteur', 'extremite_libre')
AEP_TERMINAL_TYPE_DEFAUT = 'regard_compteur'


def libelle_type(code):
    """Libellé traduit d'un code de nœud ou de terminal ; le code sinon."""
    from . import i18n
    if not code:
        return ''
    cle = f'aep_t_{code}'
    return i18n.tr(cle) if cle in i18n.TR else str(code)


# ── AEP : altimétrie ────────────────────────────────────────────────────────

COUVERTURE_DEFAUT = 1.00      # m au-dessus de la génératrice supérieure
_CLE_COUVERTURE = "CanaPlan/default/couverture_aep"


def couverture_aep():
    from qgis.core import QgsSettings
    try:
        return float(QgsSettings().value(_CLE_COUVERTURE, COUVERTURE_DEFAUT))
    except (TypeError, ValueError):
        return COUVERTURE_DEFAUT


def set_couverture_aep(valeur):
    from qgis.core import QgsSettings
    QgsSettings().setValue(_CLE_COUVERTURE, float(valeur))


def fe_depuis_couverture(tn, dn_mm, couverture=None):
    """Fil d'eau (génératrice inférieure) d'une conduite AEP sous `couverture`.

    Rend None si le TN manque. DN absent : compté nul (fil d'eau = génératrice
    supérieure), plutôt que d'inventer un diamètre.
    """
    if tn is None:
        return None
    cv = couverture_aep() if couverture is None else couverture
    dn = (dn_mm or 0) / 1000.0
    return round(tn - cv - dn, 3)


# ── Champs propres à l'AEP ──────────────────────────────────────────────────

# Ajoutés aux définitions communes de main.LAYER_DEFINITIONS pour les couches
# AEP seulement : EU/EP ne portent pas de champ `type`.
# sym_angle / sym_dir : orientation des symboles, calculée par
# aep_topo.recalculer_orientations (voir style_aep : pas de lecture d'une autre
# couche pendant le rendu).
CHAMPS_AEP = {
    'regard':   [('type', 'QString', 'Type'),
                 ('sym_angle', 'Double', 'Orientation symbole'),
                 ('sym_dir', 'Double', 'Direction branchement')],
    'tabouret': [('type', 'QString', 'Type'),
                 ('sym_angle', 'Double', 'Orientation symbole')],
}


_CLE_TERMINAL = "CanaPlan/default/terminal_aep"


def terminal_aep_defaut():
    """Type de terminal posé en fin de branchement AEP (Configuration rapide)."""
    from qgis.core import QgsSettings
    val = QgsSettings().value(_CLE_TERMINAL, AEP_TERMINAL_TYPE_DEFAUT)
    return val if val in AEP_TERMINAL_TYPES else AEP_TERMINAL_TYPE_DEFAUT


def set_terminal_aep_defaut(code):
    from qgis.core import QgsSettings
    if code in AEP_TERMINAL_TYPES:
        QgsSettings().setValue(_CLE_TERMINAL, code)


# ── Vocabulaire AEP ─────────────────────────────────────────────────────────

# En eau potable, on ne parle ni de regard ni de tabouret : les ouvrages
# ponctuels sont des nœuds (appareils ou pièces) et le bout d'un branchement
# est un compteur. Clé i18n EU/EP → clé AEP équivalente.
_CLES_AEP = {
    'col_regard':          'aep_col_noeud',
    'qc_regards':          'aep_qc_noeuds',
    'rap_regards':         'aep_qc_noeuds',
    'rap_total_regards':   'aep_rap_total_noeuds',
    'col_tabouret':        'aep_col_compteur',
    'qc_tabourets':        'aep_qc_compteurs',
    'rap_tabourets':       'aep_qc_compteurs',
    'rap_total_tabourets': 'aep_rap_total_compteurs',
    'col_fe_tabouret':     'aep_col_fe_compteur',
    'ts_resume':           'aep_ts_resume',
}


def cle_role(cle, reseau):
    """Clé i18n adaptée au réseau : « Tabourets » devient « Compteurs » en AEP."""
    return _CLES_AEP.get(cle, cle) if est_aep(reseau) else cle
