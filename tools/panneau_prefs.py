# tools/panneau_prefs.py
"""Contenu du panneau latéral et préférences d'interface de l'utilisateur.

Le panneau est décrit ici comme une donnée (dossiers, sous-dossiers, entrées)
plutôt qu'écrit en dur dans le widget : l'onglet Interface de la
configuration rapide peut ainsi réordonner et masquer les entrées, et le
panneau se reconstruit d'après ces préférences.

Préférences (QSettings, gardées d'une session à l'autre) :
    CanaPlan/panneau            JSON {"ordre": {parent: [clés]}, "masques": [clés]}
    CanaPlan/interface_coloree  bool, panneau en couleurs (défaut : oui ;
                                non = apparence classique de QGIS)
"""

import json

from qgis.PyQt.QtCore import QSettings

CLE_PANNEAU = "CanaPlan/panneau"
CLE_COULEUR = "CanaPlan/interface_coloree"
RACINE = "__racine__"


def _entree(action, icone, tr=None):
    return {'action': action, 'icone': icone, 'tr': tr}


def _dossier(cle, enfants):
    return {'dossier': cle, 'enfants': enfants}


# Ordre par défaut, celui du panneau avant l'onglet Interface.
STRUCTURE = [
    _dossier('grp_projet', [
        _entree('nouveau_projet_assistant', 'config.svg'),
        _entree('projets_recents', 'config.svg'),
        _entree('enregistrer_projet', 'config.svg', 'panel_enregistrer_projet'),
        _entree('enregistrer_projet_sous', 'config.svg'),
        _entree('charger_projet', 'config.svg'),
        _entree('import_dxf', 'config.svg'),
        _entree('import_star_dt', 'config.svg'),
    ]),
    _dossier('grp_general', [
        _entree('renseignement', 'renseignement.svg'),
        _entree('tableau_saisie', 'config.svg'),
        _entree('insert_regard', 'insert_regard.svg'),
        _entree('move', 'move.svg'),
        _entree('copy_attributes', 'copy_attrib.svg'),
        _entree('delete', 'delete.svg'),
        _entree('config', 'config.svg', 'panel_config'),
        _entree('magic_box', 'magic_box.svg'),
    ]),
    _dossier('grp_eu', [
        _entree('conduite_eu', 'conduite_eu.svg'),
        _entree('branchement_eu', 'branchement_eu.svg'),
        _entree('profil_eu', 'profil.svg'),
        _entree('coupe_eu', 'profil.svg'),
        _entree('renommer_eu', 'renommer.svg'),
    ]),
    _dossier('grp_ep', [
        _entree('conduite_ep', 'conduite_ep.svg'),
        _entree('branchement_ep', 'branchement_ep.svg'),
        _entree('profil_ep', 'profil.svg'),
        _entree('coupe_ep', 'profil.svg'),
        _entree('renommer_ep', 'renommer.svg'),
    ]),
    _dossier('grp_aep', [
        _entree('conduite_aep', 'conduite_aep.svg'),
        _entree('branchement_aep', 'branchement_aep.svg'),
        _entree('appareil_aep', 'insert_regard.svg'),
        _entree('profil_aep', 'profil.svg'),
        _entree('coupe_aep', 'profil.svg'),
        _entree('renommer_aep', 'renommer.svg'),
        _entree('schemaep', 'insert_regard.svg'),
    ]),
    _dossier('grp_etiquettes', [
        _entree('creer_etiquettes', 'etiquettes.svg'),
        _entree('afficher_etiquettes', 'etiquettes_toggle.svg'),
        _entree('taille_etiquettes', 'etiquettes.svg'),
        _entree('forcer_etiquettes', 'etiquettes_toggle.svg', 'panel_forcer_etiquettes'),
        _entree('affichage_etiquettes', 'etiquettes.svg'),
        _entree('annotation', 'etiquettes.svg'),
    ]),
    _dossier('grp_sorties', [
        _entree('imprimer', 'config.svg'),
        _entree('profil_groupe', 'profil.svg'),
        _entree('coupe_transversale', 'profil.svg'),
        _entree('cubature', 'config.svg'),
        _entree('coupe_tranchee_composee', 'profil.svg', 'panel_coupe_tranchee_composee'),
        _entree('export_stareau', 'config.svg', 'panel_export_stareau'),
    ]),
    _dossier('grp_fond', [
        _entree('fond_projet', 'config.svg', 'panel_fond_projet'),
        _dossier('grp_fond_france', [
            _entree('osm_desature', 'config.svg'),
            _entree('ortho_ign', 'config.svg'),
            _entree('pci_parcelles', 'config.svg'),
            _entree('pci_bati', 'config.svg'),
            _entree('ban_vecteur', 'config.svg', 'panel_ban_vecteur'),
            _entree('nom_voie', 'config.svg'),
        ]),
        _dossier('grp_fond_international', [
            _entree('monde_osm', 'config.svg'),
            _entree('monde_esri', 'config.svg'),
            _entree('monde_bati_osm', 'config.svg'),
        ]),
    ]),
]

# Couleur des bandeaux de dossiers en interface colorée : celle du réseau
# pour EU / EP / AEP (la même que sur la carte), des teintes soutenues pour
# le reste, lisibles sous un texte blanc.
COULEURS = {
    'grp_projet':     '#37474F',
    'grp_general':    '#00796B',
    'grp_eu':         '#E30613',
    'grp_ep':         '#0033CC',
    'grp_aep':        '#00838F',
    'grp_etiquettes': '#E65100',
    'grp_sorties':    '#6A1B9A',
    'grp_fond':       '#2E7D32',
}


def cle(noeud):
    return noeud.get('dossier') or noeud.get('action')


def charger():
    """Préférences du panneau : {"ordre": {...}, "masques": set()}."""
    brut = QSettings().value(CLE_PANNEAU, "")
    try:
        d = json.loads(brut) if brut else {}
    except (TypeError, ValueError):
        d = {}
    return {'ordre': dict(d.get('ordre') or {}),
            'masques': set(d.get('masques') or [])}


def enregistrer(prefs):
    QSettings().setValue(CLE_PANNEAU, json.dumps(
        {'ordre': prefs.get('ordre', {}),
         'masques': sorted(prefs.get('masques', ()))}))


def reinitialiser():
    QSettings().remove(CLE_PANNEAU)


def interface_coloree():
    return QSettings().value(CLE_COULEUR, True, type=bool)


def definir_interface_coloree(active):
    QSettings().setValue(CLE_COULEUR, bool(active))


def _ordonner(noeuds, ordre_voulu):
    """Les clés connues de `ordre_voulu` d'abord, dans cet ordre ; les autres
    (entrées ajoutées depuis) ensuite, dans l'ordre par défaut."""
    par_cle = {cle(n): n for n in noeuds}
    tete = [par_cle[k] for k in ordre_voulu if k in par_cle]
    vus = {cle(n) for n in tete}
    return tete + [n for n in noeuds if cle(n) not in vus]


def structure_ordonnee(prefs=None):
    """STRUCTURE réordonnée selon les préférences (copie, masques non retirés)."""
    prefs = prefs if prefs is not None else charger()
    ordre = prefs.get('ordre', {})

    def copier(noeuds, parent):
        resultat = []
        for n in _ordonner(noeuds, ordre.get(parent, [])):
            if 'dossier' in n:
                resultat.append(_dossier(n['dossier'], copier(n['enfants'], n['dossier'])))
            else:
                resultat.append(dict(n))
        return resultat

    return copier(STRUCTURE, RACINE)
