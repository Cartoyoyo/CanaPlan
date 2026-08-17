# tools/stareau_values.py
"""Listes de valeurs officielles du geostandard StaR-Eau V2024 (CNIG / ASTEE).

Source : https://github.com/cnigfr/StaR-Eau
  Documentation/Modele/Star-Eau_v2024/03.9-catalogues/

Ces listes sont referencees par des cles etrangeres dans le modele PostGIS
(fichiers 210/220-contraintes_sur_liste_valeurs_*.sql). Tout code produit a
l'export DOIT en provenir, sinon l'integration dans une base StaR-Eau echoue.

Chaque liste est un tuple de (code, libelle). L'ordre est celui d'affichage
dans les combos ; le premier element sert de valeur par defaut raisonnable
pour un chantier d'assainissement neuf.
"""

# ─────────────────────────────────────────────────────────────────────────────
#  Listes communes (com_*)
# ─────────────────────────────────────────────────────────────────────────────

TYPE_RESEAU = (
    ("assaeu", "Eaux usées"),
    ("assaep", "Eaux pluviales"),
    ("assaru", "Réseau unitaire"),
    ("aep",    "Eau potable"),
    ("ince",   "Incendie"),
)

ETAT_SERVICE = (
    ("en_service",      "En service"),
    ("en_construction", "En construction"),
    ("en_projet",       "En projet"),
    ("en_arret",        "En arrêt"),
    ("abandon",         "Abandon"),
    ("comble",          "Comblé"),
    ("depose",          "Déposé"),
)

PRECISION = (
    ("A", "Classe A"),
    ("B", "Classe B"),
    ("C", "Classe C"),
)

MODE_CIRCULATION = (
    ("gravitaire",  "Gravitaire"),
    ("refoulement", "Refoulement"),
    ("sous_vide",   "Sous vide"),
    ("forcee",      "Forcée"),
)

TYPE_POSE = (
    ("tranchee_ouverte", "Tranchée ouverte"),
    ("fusee",            "Fusée pneumatique"),
    ("tunnelier",        "Tunnelier (micro)"),
    ("forage_dirige",    "Fonçage-forage dirigé"),
    ("pousse_tube",      "Direct pipe (pousse-tube)"),
    ("eclatement",       "Éclatement"),
    ("extraction",       "Tirage (extraction)"),
    ("decoupe",          "Tirage (découpe)"),
)

RAISON_POSE = (
    ("creation",            "Création"),
    ("renouvellement",      "Renouvellement"),
    ("rehab_structurante",  "Réhabilitation structurante"),
    ("rehab_ponctuelle",    "Réhabilitation ponctuelle"),
)

ORIGINE = (
    ("recolement_certifie", "Récolement certifié"),
    ("plan_realisation",    "Plan de réalisation"),
    ("projet_certifie",     "Projet vérifié ou certifié"),
    ("recolement_ancien",   "Récolement ancien"),
    ("croquis_certifie",    "Croquis vérifié"),
    ("plan_non_verifie",    "Plan non vérifié"),
    ("croquis",             "Croquis"),
    ("non_fiable",          "Source non vérifiée"),
)

FORME = (
    ("circulaire",    "Circulaire"),
    ("rectangulaire", "Rectangulaire"),
    ("ovoide",        "Ovoïde"),
    ("en_u",          "En U"),
    ("en_arc",        "En arc"),
    ("ovale",         "Ovale"),
    ("complexe",      "Complexe"),
)

TYPE_USAGER = (
    ("domestique", "Domestique"),
    ("industriel", "Industriel"),
    ("commercial", "Commercial"),
    ("tertiaire",  "Tertiaire"),
    ("medical",    "Médical"),
    ("mixte",      "Mixte"),
)

REVETEMENT_INTERIEUR = (
    ("aucun",                "Aucun"),
    ("mortier_ciment",       "Mortier de ciment"),
    ("gaine_pet",            "Gaine polyéthylène"),
    ("feutre_epoxy",         "Gaine feutre époxy"),
    ("feutre_polyester",     "Gaine feutre polyester"),
    ("feutre_pur",           "Gaine feutre polyuréthane"),
    ("fibre_epoxy",          "Gaine fibre de verre époxy"),
    ("fibre_polyester",      "Gaine fibre de verre polyester"),
    ("peinture_epoxy",       "Peinture intérieure époxy"),
    ("peinture_pu",          "Peinture intérieure polyuréthane"),
    ("peinture_bitumineuse", "Peinture bitumineuse"),
    ("projection_beton",     "Projection béton"),
)

# com_materiau : liste complete du standard, triee par famille d'usage
# assainissement (les plus courants en tete).
MATERIAU = (
    ("pvc",     "PVC"),
    ("pvca",    "PVC annelé"),
    ("pehd",    "PEHD"),
    ("pehda",   "PEHD annelé"),
    ("pp",      "Polypropylène"),
    ("ppa",     "Polypropylène annelé"),
    ("fd",      "Fonte ductile"),
    ("fonte",   "Fonte (non identifiée)"),
    ("fg",      "Fonte grise"),
    ("beton",   "Béton (non identifié)"),
    ("ba",      "Béton armé"),
    ("btna",    "Béton non armé"),
    ("btfb",    "Béton fibré"),
    ("gres",    "Grès"),
    ("amci",    "Amiante-ciment"),
    ("fbro",    "Fibres-ciment"),
    ("acier",   "Acier"),
    ("prv",     "Plastique renforcé fibres"),
    ("pe",      "Polyéthylène"),
    ("pebd",    "PEBD"),
    ("pvcbo",   "PVC bi-orienté"),
    ("mac",     "Maçonné"),
    ("maca",    "Maçonnerie appareillée"),
    ("macna",   "Maçonnerie non appareillée"),
    ("briq",    "Briquetage"),
    ("bois",    "Bois"),
    ("trct",    "Terre cuite"),
    ("plast",   "Plastique (non identifié)"),
    ("metal",   "Métal (non identifié)"),
    ("autre",   "Autre"),
    ("inc",     "Inconnu"),
    ("nr",      "Non renseigné"),
)

# ─────────────────────────────────────────────────────────────────────────────
#  Listes assainissement (ass_*)
# ─────────────────────────────────────────────────────────────────────────────

CONTENU_CANALISATION = (
    ("eru",                "Eaux résiduaires urbaines"),
    ("eri",                "Eaux résiduaires industrielles"),
    ("eaux_usees_traitee", "Eaux usées traitées"),
)

FONCTION_CANALISATION = (
    ("collecte",      "Collecte"),
    ("transport",     "Transport"),
    ("by_pass",       "By-pass"),
    ("stockage",      "Stockage"),
    ("trop_plein",    "Trop-plein"),
    ("drain",         "Drain"),
    ("galerie_acces", "Galerie d'accès"),
)

# ass_fonction_branchement : porte fonction_canalisation sur les branchements
FONCTION_BRANCHEMENT = (
    ("collecte",   "Collecte"),
    ("transport",  "Transport"),
    ("trop_plein", "Trop-plein"),
    ("drain",      "Drain"),
)

TYPE_REGARD = (
    ("visite",  "Regard de visite"),
    ("chambre", "Chambre"),
    ("borgne",  "Regard borgne"),
    ("mixte",   "Mixte"),
)

POSITION_REGARD = (
    ("axial",     "Axial"),
    ("non_axial", "Non axial"),
    ("deporte",   "Déporté"),
)

TYPE_DESCENTE = (
    ("echelon_double", "Échelon double"),
    ("echelon_simple", "Échelon simple"),
    ("echelle",        "Échelle fixe"),
    ("echelle_mobile", "Échelle mobile"),
    ("trou",           "Trous dans la paroi"),
    ("aucun",          "Aucun"),
)

TYPE_POINT_COLLECTE = (
    ("direct",        "Boîte à passage direct"),
    ("siphon",        "Boîte siphoïde"),
    ("te",            "Té de visite"),
    ("disconnecteur", "Disconnecteur"),
    ("borgne",        "Borgne"),
    ("etanche",       "Étanche"),
)

TYPE_RACCORD = (
    ("piquage_direct", "Piquage direct"),
    ("culotte",        "Culotte"),
    ("selle",          "Selle"),
    ("tulipe",         "Tulipe"),
    ("te",             "Té"),
    ("libre",          "Sortie libre"),
)


# ─────────────────────────────────────────────────────────────────────────────
#  Materiaux de conduite proposes a la saisie
# ─────────────────────────────────────────────────────────────────────────────

# Source de vérité unique des materiaux proposes dans le plugin : la
# Configuration rapide, le Tableau de saisie et le dialogue d'export StaR-Eau
# lisent tous cette liste. Avant, chaque dialogue avait la sienne et elles
# divergeaient (Amiante-ciment absent d'un cote, materiaux de remblai melanges
# aux materiaux de conduite de l'autre), ce qui eclatait le regroupement par
# materiau de la synthese de cubature.
#
# C'est le LIBELLE qui est stocke dans le champ `materiau` des couches : il
# reste lisible dans les etiquettes, l'export DXF et les tableaux. Le code
# StaR-Eau qui lui est attache n'apparait qu'a l'export.
#
# Sous-ensemble de com_materiau couvrant l'assainissement courant, en
# distinguant les variantes que le geostandard separe (fonte / fonte ductile,
# beton / beton arme).
MATERIAUX_CONDUITE = (
    ("pvc",   "PVC"),
    ("pvca",  "PVC annelé"),
    ("beton", "Béton"),
    ("ba",    "Béton armé"),
    ("fonte", "Fonte"),
    ("fd",    "Fonte ductile"),
    ("gres",  "Grès"),
    ("pehd",  "PEHD"),
    ("amci",  "Amiante-ciment"),
    ("acier", "Acier"),
    ("nr",    "Non renseigné"),
)


def materiaux_labels():
    """Libelles des materiaux de conduite, pour alimenter les combos."""
    return [libelle for _, libelle in MATERIAUX_CONDUITE]


# ─────────────────────────────────────────────────────────────────────────────
#  Correspondance materiau libre -> code StaR-Eau
# ─────────────────────────────────────────────────────────────────────────────

# Le plugin stocke le materiau en texte libre. On tente une reconnaissance
# avant de retomber sur le defaut du dialogue. Les cles sont normalisees
# (minuscules, sans accent ni separateur) et testees de la plus specifique a
# la plus generale : "pvc annele" doit gagner sur "pvc".
_MATERIAU_ALIASES = (
    ("pvcannele",      "pvca"),
    ("pvcbiooriente",  "pvcbo"),
    ("pvcbioriente",   "pvcbo"),
    ("pvcu",           "pvc"),
    ("pvc",            "pvc"),
    ("pehdannele",     "pehda"),
    ("pehd",           "pehd"),
    ("pebd",           "pebd"),
    ("polyethylene",   "pe"),
    ("pe",             "pe"),
    ("polypropyleneannele", "ppa"),
    ("ppannele",       "ppa"),
    ("polypropylene",  "pp"),
    ("pp",             "pp"),
    ("fonteductile",   "fd"),
    ("fontegrise",     "fg"),
    ("fonte",          "fonte"),
    ("betonarme",      "ba"),
    ("betonnonarme",   "btna"),
    ("betonfibre",     "btfb"),
    ("beton",          "beton"),
    ("ba",             "ba"),
    ("gres",           "gres"),
    ("amianteciment",  "amci"),
    ("amiante",        "amci"),
    ("fibrociment",    "fbro"),
    ("fibreciment",    "fbro"),
    ("acier",          "acier"),
    ("inox",           "acier"),
    ("prv",            "prv"),
    ("maconnerie",     "mac"),
    ("maconne",        "mac"),
    ("brique",         "briq"),
    ("bois",           "bois"),
    ("terrecuite",     "trct"),
    ("inconnu",        "inc"),
)

# Alias trop courts pour etre cherches en sous-chaine : "pe" matcherait
# "special", "inc" matcherait "principal". Ils exigent l'egalite stricte.
_MATERIAU_EXACTS = frozenset(("pe", "pp", "ba", "inc"))


def _normalize(text):
    """Minuscules, sans accent ni caractere non alphanumerique."""
    import unicodedata
    if not text:
        return ""
    decomposed = unicodedata.normalize("NFD", str(text))
    stripped = "".join(c for c in decomposed if unicodedata.category(c) != "Mn")
    return "".join(c for c in stripped.lower() if c.isalnum())


def materiau_code(libelle, defaut="nr"):
    """Convertit un materiau saisi vers un code com_materiau.

    Trois passes, de la plus sure a la plus permissive :
      1. libelle exact de MATERIAUX_CONDUITE — le cas normal, puisque les
         combos du plugin ne proposent que ces libelles ;
      2. code officiel saisi tel quel ;
      3. reconnaissance approchee, filet pour les anciens projets .bet et les
         combos editables.

    Retourne `defaut` si aucune correspondance n'est trouvee.
    """
    key = _normalize(libelle)
    if not key:
        return defaut
    for code, label in MATERIAUX_CONDUITE:
        if key == _normalize(label):
            return code
    for code, _ in MATERIAU:
        if key == code:
            return code
    for alias, code in _MATERIAU_ALIASES:
        if alias in _MATERIAU_EXACTS:
            if key == alias:
                return code
        elif alias in key:
            return code
    return defaut


def labels(liste):
    """Libelles d'affichage d'une liste de valeurs."""
    return [libelle for _, libelle in liste]


def code_at(liste, index):
    """Code correspondant a l'index d'affichage, ou None hors bornes."""
    if 0 <= index < len(liste):
        return liste[index][0]
    return None


def index_of(liste, code):
    """Index d'affichage d'un code, 0 si absent."""
    for i, (c, _) in enumerate(liste):
        if c == code:
            return i
    return 0
