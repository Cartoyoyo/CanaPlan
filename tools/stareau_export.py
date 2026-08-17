# tools/stareau_export.py
"""Export des couches BET Humide vers un GeoPackage conforme StaR-Eau V2024.

StaR-Eau (CNIG / ASTEE) n'est pas un format de fichier mais un modele de
donnees relationnel, publie sous forme de scripts PostGIS. Le geostandard
designe le GeoPackage comme format d'echange a privilegier : on produit donc
un .gpkg dont chaque couche porte le nom et les colonnes d'une table du
modele, directement injectable par ogr2ogr dans une base StaR-Eau.

Correspondance des objets :

    conduite    -> ass_canalisation               (stareau_ass)
    regard      -> ass_regard                     (stareau_ass)
    branchement -> ass_canalisation_branchement   (stareau_ass_brcht)
    tabouret    -> ass_point_collecte             (stareau_ass_brcht)
    piquage     -> ass_raccord                    (stareau_ass_brcht)

Le decoupage noeud-arc-noeud exige par le geostandard est deja natif dans le
plugin : chaque conduite est un troncon a deux sommets entre deux regards
(cf. draw_conduite_tool._create_troncon). Un troncon donne donc exactement
une ass_canalisation, et ses deux regards alimentent noeudinitial /
noeudterminal.

Les arcs sont orientes dans le sens d'ecoulement (amont = fil d'eau le plus
haut), la geometrie etant inversee si necessaire : StaR-Eau attache
altitude_fil_eau_amont a noeudinitial.
"""

import os
import uuid
from datetime import datetime

from qgis.core import (
    QgsCoordinateReferenceSystem, QgsFeature, QgsField, QgsFields,
    QgsGeometry, QgsMemoryProviderUtils, QgsPointXY, QgsProject,
    QgsSpatialIndex, QgsVectorFileWriter, QgsWkbTypes,
)
from qgis.PyQt.QtCore import QDateTime, QVariant

from . import layer_ok
from .layer_keys import get_layer_id

try:
    from qgis.core import NULL as QGIS_NULL
except ImportError:
    QGIS_NULL = None

CRS_STAREAU = "EPSG:2154"

# Tolerance de raccrochage d'une extremite d'arc sur un ouvrage, en metres.
# Meme valeur que graph_utils.build_graph : les outils de dessin posent les
# sommets exactement sur les regards, 5 cm couvre les recalages.
SNAP_TOL = 0.05

_RESEAUX = ("EU", "EP")


# ─────────────────────────────────────────────────────────────────────────────
#  Utilitaires
# ─────────────────────────────────────────────────────────────────────────────

def _val(feat, name):
    """Valeur d'attribut, ou None si absent / NULL QGIS."""
    try:
        idx = feat.fields().indexOf(name)
    except Exception:
        return None
    if idx < 0:
        return None
    v = feat.attribute(idx)
    if v is None or (QGIS_NULL is not None and v == QGIS_NULL):
        return None
    return v


def _num(feat, name):
    """Valeur numerique d'attribut, ou None."""
    v = _val(feat, name)
    if v is None:
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _txt(feat, name):
    """Valeur texte d'attribut nettoyee, ou '' si vide."""
    v = _val(feat, name)
    return str(v).strip() if v is not None else ""


# Namespace propre au plugin pour la derivation des UUID v5.
_UUID_NAMESPACE = uuid.uuid5(uuid.NAMESPACE_DNS, "stareau.bet-humide")


def _slug(text):
    """Fragment d'identifiant metier : majuscules, sans accent ni separateur."""
    import unicodedata
    if not text:
        return ""
    decomposed = unicodedata.normalize("NFD", str(text))
    stripped = "".join(c for c in decomposed if unicodedata.category(c) != "Mn")
    return "".join(c for c in stripped.upper() if c.isalnum())


def _mat_dn(code_materiau, diametre):
    """Fragment « PVC200 » pour l'identifiant metier d'une canalisation.

    Le code StaR-Eau en majuscules, suivi du diametre nominal. Le
    geostandard decoupe les arcs par homogeneite de caracteristiques : ces
    deux valeurs sont donc constantes sur un troncon et le decrivent bien.
    """
    fragment = (code_materiau or "").upper()
    if diametre:
        fragment += str(int(diametre))
    return fragment


class _IdFactory:
    """Fabrique les identifiants metier lisibles et les cles techniques.

    StaR-Eau separe deux identifiants par objet :
      - la cle technique (`id_canalisation`, `id_noeud_reseau`), referencee
        par noeudinitial / noeudterminal / ref_canalisation ;
      - l'identifiant metier (`id_ass_regard`, `id_ass_canalisation`...),
        prevu pour la lecture humaine.

    La cle technique est un **UUID v5 deterministe** derive de l'identifiant
    metier et du SIREN, et non un uuid4 aleatoire : reexporter le meme
    chantier redonne les memes identifiants, ce qui permet au destinataire de
    rapprocher une mise a jour de l'export precedent au lieu d'y voir un
    reseau entierement neuf.

    L'identifiant metier reste prefixe par le code chantier pour ne pas
    entrer en collision quand l'exploitant fusionne plusieurs chantiers : les
    regards R1, R2 existent dans tous les chantiers.
    """

    def __init__(self, params):
        self.prefix = _slug(params.get("code_chantier"))
        self.siren = params.get("siren") or ""
        self.date = _slug(params.get("date_pose"))
        self._used = set()

    def make(self, reseau, key_parts, label_parts=None):
        """Retourne (identifiant_metier, cle_technique).

        `key_parts` ne decrit que la TOPOLOGIE (role, ouvrages d'extremite) :
        c'est d'elle seule que derive l'UUID. Corriger un materiau, un
        diametre ou la date de pose laisse donc la cle technique intacte, et
        le destinataire voit une modification et non une suppression suivie
        d'une creation.

        `label_parts` decrit l'identifiant metier affiche, enrichi du
        materiau et du diametre. A defaut, il reprend `key_parts`.
        """
        key_base = "-".join(f for f in (
            [self.prefix, reseau] + [_slug(p) for p in key_parts]) if f)
        label_base = "-".join(f for f in (
            [self.prefix, self.date, reseau]
            + [_slug(p) for p in (label_parts or key_parts)]) if f)

        key_id, label = key_base, label_base
        suffix = 2
        while key_id in self._used:
            key_id = f"{key_base}-{suffix}"
            label = f"{label_base}-{suffix}"
            suffix += 1
        self._used.add(key_id)
        return label, str(uuid.uuid5(_UUID_NAMESPACE, f"{self.siren}/{key_id}"))


def _line_points(feat):
    """Extremites (premier, dernier) d'une geometrie lineaire, ou (None, None)."""
    geom = feat.geometry()
    if geom is None or geom.isEmpty():
        return None, None
    try:
        line = geom.asPolyline()
    except Exception:
        return None, None
    if len(line) < 2:
        return None, None
    return QgsPointXY(line[0]), QgsPointXY(line[-1])


# ─────────────────────────────────────────────────────────────────────────────
#  Index des ouvrages ponctuels
# ─────────────────────────────────────────────────────────────────────────────

class _NodeIndex:
    """Index spatial des ouvrages ponctuels d'un reseau (regards + tabourets).

    Sert a retrouver le noeud sous une extremite d'arc. Les fid de regard et
    de tabouret pouvant se recouvrir, chaque entree est stockee sous une cle
    composite (role, fid).
    """

    def __init__(self):
        self._index = QgsSpatialIndex()
        self._points = {}     # {slot: QgsPointXY}
        self._keys = {}       # {slot: (role, fid)}
        self._next_slot = 1

    def add(self, role, feat):
        geom = feat.geometry()
        if geom is None or geom.isEmpty():
            return
        pt = QgsPointXY(geom.asPoint())
        slot = self._next_slot
        self._next_slot += 1
        proxy = QgsFeature(slot)
        proxy.setGeometry(QgsGeometry.fromPointXY(pt))
        self._index.addFeature(proxy)
        self._points[slot] = pt
        self._keys[slot] = (role, feat.id())

    def find(self, pt, tol=SNAP_TOL):
        """Cle (role, fid) de l'ouvrage sous pt, ou None."""
        if pt is None:
            return None
        for slot in self._index.nearestNeighbor(pt, 1, tol):
            if pt.distance(self._points[slot]) <= tol:
                return self._keys[slot]
        return None


# ─────────────────────────────────────────────────────────────────────────────
#  Definition des couches de sortie
# ─────────────────────────────────────────────────────────────────────────────

def _fields(*specs):
    fields = QgsFields()
    for name, qtype in specs:
        fields.append(QgsField(name, qtype))
    return fields


# Colonnes heritees de stareau_principale.champ_commun, portees par tous les
# objets du modele. Les NOT NULL du standard sont toujours ecrits.
_CHAMP_COMMUN = (
    ("type_reseau",      QVariant.String),
    ("fictif",           QVariant.Bool),
    ("etat_service",     QVariant.String),
    ("insee_commune",    QVariant.String),
    ("localisation",     QVariant.String),
    ("maitre_ouvrage",   QVariant.String),
    ("exploitant",       QVariant.String),
    ("entreprise_pose",  QVariant.String),
    ("precision_xy",     QVariant.String),
    ("precision_z",      QVariant.String),
    ("an_pose_sup",      QVariant.Int),
    ("an_service_sup",   QVariant.Int),
    ("date_creation",    QVariant.DateTime),
    ("origine_creation", QVariant.String),
    ("date_maj",         QVariant.DateTime),
    ("origine_maj",      QVariant.String),
    ("commentaire",      QVariant.String),
)

# Colonnes heritees de stareau_principale.dimension.
_DIMENSION = (
    ("forme",              QVariant.String),
    ("hauteur_interieure", QVariant.Double),
    ("largeur_interieure", QVariant.Double),
)

# Colonnes heritees de stareau_principale.canalisation.
_CANALISATION = (
    ("mode_circulation",     QVariant.String),
    ("type_pose",            QVariant.String),
    ("raison_pose",          QVariant.String),
    ("materiau",             QVariant.String),
    ("revetement_interieur", QVariant.String),
    ("diametre_equivalent",  QVariant.Int),
    ("longueur_terrain",     QVariant.Double),
    ("sensible",             QVariant.Bool),
    ("noeudinitial",         QVariant.String),
    ("noeudterminal",        QVariant.String),
)


def _schema_canalisation():
    return _fields(
        ("id_canalisation",         QVariant.String),
        ("id_ass_canalisation",     QVariant.String),
        *_CHAMP_COMMUN, *_CANALISATION, *_DIMENSION,
        ("fonction_canalisation",   QVariant.String),
        ("contenu_canalisation",    QVariant.String),
        ("visitable",               QVariant.String),
        ("altitude_fil_eau_amont",  QVariant.Double),
        ("altitude_fil_eau_aval",   QVariant.Double),
    )


def _schema_canalisation_branchement():
    return _fields(
        ("id_canalisation",                  QVariant.String),
        ("id_ass_canalisation_branchement",  QVariant.String),
        *_CHAMP_COMMUN, *_CANALISATION, *_DIMENSION,
        ("fonction_canalisation",   QVariant.String),
        ("contenu_canalisation",    QVariant.String),
        ("altitude_fil_eau_amont",  QVariant.Double),
        ("altitude_fil_eau_aval",   QVariant.Double),
    )


def _schema_regard():
    return _fields(
        ("id_noeud_reseau",    QVariant.String),
        ("id_ass_regard",      QVariant.String),
        *_CHAMP_COMMUN, *_DIMENSION,
        ("type_regard",        QVariant.String),
        ("materiau",           QVariant.String),
        ("position",           QVariant.String),
        ("type_descente",      QVariant.String),
        ("z_tampon",           QVariant.Double),
        ("z_radier",           QVariant.Double),
        ("profondeur_mesure",  QVariant.Double),
    )


def _schema_point_collecte():
    return _fields(
        ("id_noeud_reseau",     QVariant.String),
        ("id_point_collecte",   QVariant.String),
        *_CHAMP_COMMUN, *_DIMENSION,
        ("type_point_collecte", QVariant.String),
        ("type_usager",         QVariant.String),
        ("materiau",            QVariant.String),
        ("z_tampon",            QVariant.Double),
        ("z_radier",            QVariant.Double),
        ("profondeur",          QVariant.Double),
    )


def _schema_raccord():
    return _fields(
        ("id_noeud_reseau",   QVariant.String),
        ("id_ass_raccord",    QVariant.String),
        *_CHAMP_COMMUN,
        ("type_raccord",      QVariant.String),
        ("ref_canalisation",  QVariant.String),
    )


# Nom de couche -> (schema, type de geometrie)
LAYER_SCHEMAS = {
    "ass_canalisation":             (_schema_canalisation,             QgsWkbTypes.LineString),
    "ass_regard":                   (_schema_regard,                   QgsWkbTypes.Point),
    "ass_canalisation_branchement": (_schema_canalisation_branchement, QgsWkbTypes.LineString),
    "ass_point_collecte":           (_schema_point_collecte,           QgsWkbTypes.Point),
    "ass_raccord":                  (_schema_raccord,                  QgsWkbTypes.Point),
}

# Ordre d'ecriture dans le GeoPackage : les tables referencees d'abord.
LAYER_ORDER = (
    "ass_regard",
    "ass_point_collecte",
    "ass_raccord",
    "ass_canalisation",
    "ass_canalisation_branchement",
)


# ─────────────────────────────────────────────────────────────────────────────
#  Remplissage des champs communs
# ─────────────────────────────────────────────────────────────────────────────

def _common_values(params, reseau):
    """Valeurs de champ_commun issues du dialogue, pour un reseau donne."""
    now = QDateTime.currentDateTime()
    type_reseau = params.get("type_reseau_eu" if reseau == "EU" else "type_reseau_ep")
    return {
        "type_reseau":      type_reseau,
        "fictif":           False,
        "etat_service":     params.get("etat_service"),
        "insee_commune":    params.get("insee_commune"),
        "localisation":     params.get("localisation") or None,
        "maitre_ouvrage":   params.get("maitre_ouvrage"),
        "exploitant":       params.get("exploitant"),
        "entreprise_pose":  params.get("entreprise_pose") or None,
        "precision_xy":     params.get("precision_xy"),
        "precision_z":      params.get("precision_z"),
        "an_pose_sup":      params.get("an_pose_sup"),
        "an_service_sup":   params.get("an_service_sup"),
        "date_creation":    now,
        "origine_creation": params.get("origine_creation"),
        "date_maj":         now,
        "origine_maj":      params.get("origine_creation"),
        "commentaire":      params.get("commentaire") or None,
    }


def _set(feat, values):
    """Affecte un dict de valeurs a une entite selon ses champs declares."""
    for name, value in values.items():
        idx = feat.fields().indexOf(name)
        if idx >= 0:
            feat.setAttribute(idx, value)


# ─────────────────────────────────────────────────────────────────────────────
#  Collecte des couches source
# ─────────────────────────────────────────────────────────────────────────────

def source_layers(project=None):
    """Retourne {(role, reseau): layer} pour toutes les couches BET presentes."""
    project = project or QgsProject.instance()
    found = {}
    for reseau in _RESEAUX:
        for role in ("conduite", "branchement", "regard", "tabouret"):
            layer_id = get_layer_id(role, reseau)
            layer = project.mapLayer(layer_id) if layer_id else None
            if layer_ok(layer):
                found[(role, reseau)] = layer
    return found


# ─────────────────────────────────────────────────────────────────────────────
#  Controle de conformite
# ─────────────────────────────────────────────────────────────────────────────

def check_conformity(project=None):
    """Verifie que les donnees permettent un export StaR-Eau conforme.

    Retourne une liste de dicts :
        {'niveau': 'bloquant'|'avertissement', 'objet': str,
         'message': str, 'layer_id': str, 'fid': int}

    Un point bloquant produit un objet non conforme au standard (champ
    NOT NULL impossible a deduire) ; un avertissement degrade la qualite
    sans empecher l'integration.
    """
    layers = source_layers(project)
    issues = []

    def add(niveau, layer, feat, objet, message):
        issues.append({
            "niveau": niveau,
            "objet": objet,
            "message": message,
            "layer_id": layer.id(),
            "fid": feat.id(),
        })

    for reseau in _RESEAUX:
        regard_layer = layers.get(("regard", reseau))
        tabouret_layer = layers.get(("tabouret", reseau))

        index = _NodeIndex()
        for role, layer in (("regard", regard_layer), ("tabouret", tabouret_layer)):
            if layer is None:
                continue
            for feat in layer.getFeatures():
                index.add(role, feat)

        for role, layer in (("regard", regard_layer), ("tabouret", tabouret_layer)):
            if layer is None:
                continue
            label = "Regard" if role == "regard" else "Tabouret"
            fe_field = "fe_radier" if role == "regard" else "fe_entree"
            for feat in layer.getFeatures():
                nom = _txt(feat, "nom") or f"#{feat.id()}"
                objet = f"{label} {nom} ({reseau})"
                if feat.geometry() is None or feat.geometry().isEmpty():
                    add("bloquant", layer, feat, objet, "géométrie absente")
                    continue
                if _num(feat, "tn") is None:
                    add("avertissement", layer, feat, objet,
                        "terrain naturel non renseigné (z_tampon vide)")
                if _num(feat, fe_field) is None:
                    add("avertissement", layer, feat, objet,
                        "fil d'eau non renseigné (z_radier vide)")

        for role, layer in (("conduite", layers.get(("conduite", reseau))),
                            ("branchement", layers.get(("branchement", reseau)))):
            if layer is None:
                continue
            label = "Conduite" if role == "conduite" else "Branchement"
            for feat in layer.getFeatures():
                objet = f"{label} #{feat.id()} ({reseau})"
                p0, p1 = _line_points(feat)
                if p0 is None:
                    add("bloquant", layer, feat, objet, "géométrie invalide ou vide")
                    continue
                if _num(feat, "diametre") is None:
                    add("bloquant", layer, feat, objet,
                        "diamètre absent (diametre_equivalent est obligatoire)")
                if not _txt(feat, "materiau"):
                    add("avertissement", layer, feat, objet,
                        "matériau non renseigné, le défaut du dialogue sera appliqué")
                if role == "conduite":
                    if index.find(p0) is None or index.find(p1) is None:
                        add("bloquant", layer, feat, objet,
                            "extrémité sans regard : noeudinitial/noeudterminal "
                            "ne peuvent pas être déduits")
                else:
                    if index.find(p1) is None and index.find(p0) is None:
                        add("bloquant", layer, feat, objet,
                            "aucune extrémité raccordée à un ouvrage")

    return issues


# ─────────────────────────────────────────────────────────────────────────────
#  Construction des entites
# ─────────────────────────────────────────────────────────────────────────────

def _build_features(params, project=None):
    """Construit les entites StaR-Eau de toutes les couches.

    Retourne ({nom_couche: [QgsFeature]}, stats) ou stats compte les objets
    ecrits et les objets ignores par couche source.
    """
    from .stareau_values import materiau_code

    layers = source_layers(project)
    out = {name: [] for name in LAYER_SCHEMAS}
    stats = {"ecrits": 0, "ignores": 0}

    schemas = {name: builder() for name, (builder, _) in LAYER_SCHEMAS.items()}
    mat_defaut = params.get("materiau_defaut", "nr")
    ids = _IdFactory(params)

    for reseau in _RESEAUX:
        common = _common_values(params, reseau)
        contenu = params.get("contenu_eu" if reseau == "EU" else "contenu_ep")

        regard_layer = layers.get(("regard", reseau))
        tabouret_layer = layers.get(("tabouret", reseau))
        conduite_layer = layers.get(("conduite", reseau))
        branchement_layer = layers.get(("branchement", reseau))

        # --- Ouvrages ponctuels : UUID + index spatial ---------------------
        index = _NodeIndex()
        node_uuid = {}       # {(role, fid): cle technique}
        node_name = {}       # {(role, fid): identifiant metier lisible}
        node_fe = {}         # {(role, fid): fil d'eau}

        for feat in (regard_layer.getFeatures() if regard_layer else []):
            if feat.geometry() is None or feat.geometry().isEmpty():
                stats["ignores"] += 1
                continue
            key = ("regard", feat.id())
            nom = _txt(feat, "nom") or f"REGARD{feat.id()}"
            business, technical = ids.make(reseau, (nom,))
            node_uuid[key] = technical
            node_name[key] = nom
            node_fe[key] = _num(feat, "fe_radier")
            index.add("regard", feat)

            out_feat = QgsFeature(schemas["ass_regard"])
            out_feat.setGeometry(feat.geometry())
            _set(out_feat, common)
            _set(out_feat, {
                "id_noeud_reseau":   technical,
                "id_ass_regard":     business,
                "forme":             "circulaire",
                "hauteur_interieure": None,
                "largeur_interieure": _num(feat, "diametre"),
                "type_regard":       params.get("type_regard"),
                "materiau":          params.get("materiau_regard"),
                "position":          params.get("position_regard"),
                "type_descente":     params.get("type_descente"),
                "z_tampon":          _num(feat, "tn"),
                "z_radier":          _num(feat, "fe_radier"),
                "profondeur_mesure": _num(feat, "profondeur"),
            })
            out["ass_regard"].append(out_feat)
            stats["ecrits"] += 1

        for feat in (tabouret_layer.getFeatures() if tabouret_layer else []):
            if feat.geometry() is None or feat.geometry().isEmpty():
                stats["ignores"] += 1
                continue
            key = ("tabouret", feat.id())
            nom = _txt(feat, "nom") or f"TABOURET{feat.id()}"
            business, technical = ids.make(reseau, (nom,))
            node_uuid[key] = technical
            node_name[key] = nom
            node_fe[key] = _num(feat, "fe_entree")
            index.add("tabouret", feat)

            out_feat = QgsFeature(schemas["ass_point_collecte"])
            out_feat.setGeometry(feat.geometry())
            _set(out_feat, common)
            _set(out_feat, {
                "id_noeud_reseau":     technical,
                "id_point_collecte":   business,
                "forme":               "circulaire",
                "hauteur_interieure":  None,
                "largeur_interieure":  _num(feat, "diametre"),
                "type_point_collecte": params.get("type_point_collecte"),
                "type_usager":         params.get("type_usager"),
                "materiau":            params.get("materiau_tabouret"),
                "z_tampon":            _num(feat, "tn"),
                "z_radier":            _num(feat, "fe_entree"),
                "profondeur":          _num(feat, "profondeur"),
            })
            out["ass_point_collecte"].append(out_feat)
            stats["ecrits"] += 1

        # --- Conduites -----------------------------------------------------
        conduite_uuid = {}   # {fid conduite: uuid} pour ref_canalisation
        for feat in (conduite_layer.getFeatures() if conduite_layer else []):
            p0, p1 = _line_points(feat)
            if p0 is None:
                stats["ignores"] += 1
                continue
            k0, k1 = index.find(p0), index.find(p1)
            if k0 is None or k1 is None:
                stats["ignores"] += 1
                continue

            geom = feat.geometry()
            fe0, fe1 = node_fe.get(k0), node_fe.get(k1)
            # Amont = fil d'eau le plus haut. Sans cote, on garde le sens
            # de dessin. StaR-Eau lie altitude_fil_eau_amont a noeudinitial.
            if fe0 is not None and fe1 is not None and fe1 > fe0:
                k0, k1 = k1, k0
                fe0, fe1 = fe1, fe0
                geom = _reversed_geometry(geom)

            diametre = _num(feat, "diametre")
            materiau = materiau_code(_txt(feat, "materiau"), mat_defaut)
            amont, aval = node_name.get(k0, ""), node_name.get(k1, "")
            # L'identifiant metier nomme le troncon par sa nature puis ses
            # deux regards, dans le sens d'ecoulement : C-PVC200-R1-R2 se lit
            # sans jointure. La cle technique ignore materiau et diametre.
            business, cana_id = ids.make(
                reseau,
                ("C", amont, aval),
                ("C", _mat_dn(materiau, diametre), amont, aval))
            conduite_uuid[feat.id()] = cana_id

            out_feat = QgsFeature(schemas["ass_canalisation"])
            out_feat.setGeometry(geom)
            _set(out_feat, common)
            _set(out_feat, {
                "id_canalisation":       cana_id,
                "id_ass_canalisation":   business,
                "mode_circulation":      params.get("mode_circulation"),
                "type_pose":             params.get("type_pose"),
                "raison_pose":           params.get("raison_pose"),
                "materiau":              materiau,
                "revetement_interieur":  params.get("revetement_interieur"),
                "diametre_equivalent":   int(diametre) if diametre else None,
                "longueur_terrain":      _num(feat, "longueur"),
                "sensible":              bool(params.get("sensible", False)),
                "noeudinitial":          node_uuid.get(k0),
                "noeudterminal":         node_uuid.get(k1),
                "forme":                 "circulaire",
                "largeur_interieure":    diametre,
                "fonction_canalisation": params.get("fonction_canalisation"),
                "contenu_canalisation":  contenu,
                "visitable":             "oui" if (diametre or 0) >= 1000 else "non",
                "altitude_fil_eau_amont": fe0,
                "altitude_fil_eau_aval":  fe1,
            })
            out["ass_canalisation"].append(out_feat)
            stats["ecrits"] += 1

        # --- Branchements + raccords ---------------------------------------
        # Le trace part du piquage sur la conduite et rejoint l'ouvrage
        # (cf. draw_branchement_tool). L'amont hydraulique est donc
        # l'extremite ouvrage : on inverse pour orienter l'arc.
        for feat in (branchement_layer.getFeatures() if branchement_layer else []):
            p_piquage, p_ouvrage = _line_points(feat)
            if p_piquage is None:
                stats["ignores"] += 1
                continue
            k_ouvrage = index.find(p_ouvrage)
            if k_ouvrage is None:
                stats["ignores"] += 1
                continue

            geom = _reversed_geometry(feat.geometry())

            cote_piquage = _num(feat, "cote_piquage")
            id_conduite = _val(feat, "id_conduite")
            ref_cana = conduite_uuid.get(int(id_conduite)) if id_conduite is not None else None

            ouvrage_nom = node_name.get(k_ouvrage, "")
            rac_business, raccord_id = ids.make(reseau, ("RC", ouvrage_nom))
            raccord = QgsFeature(schemas["ass_raccord"])
            raccord.setGeometry(QgsGeometry.fromPointXY(p_piquage))
            _set(raccord, common)
            _set(raccord, {
                "id_noeud_reseau":  raccord_id,
                "id_ass_raccord":   rac_business,
                "type_raccord":     params.get("type_raccord"),
                "ref_canalisation": ref_cana,
            })
            out["ass_raccord"].append(raccord)

            diametre = _num(feat, "diametre")
            materiau = materiau_code(_txt(feat, "materiau"), mat_defaut)
            brt_business, brt_id = ids.make(
                reseau,
                ("B", ouvrage_nom),
                ("B", _mat_dn(materiau, diametre), ouvrage_nom))
            out_feat = QgsFeature(schemas["ass_canalisation_branchement"])
            out_feat.setGeometry(geom)
            _set(out_feat, common)
            _set(out_feat, {
                "id_canalisation":       brt_id,
                "id_ass_canalisation_branchement": brt_business,
                "mode_circulation":      params.get("mode_circulation"),
                "type_pose":             params.get("type_pose"),
                "raison_pose":           params.get("raison_pose"),
                "materiau":              materiau,
                "revetement_interieur":  params.get("revetement_interieur"),
                "diametre_equivalent":   int(diametre) if diametre else None,
                "longueur_terrain":      _num(feat, "longueur"),
                "sensible":              bool(params.get("sensible", False)),
                "noeudinitial":          node_uuid.get(k_ouvrage),
                "noeudterminal":         raccord_id,
                "forme":                 "circulaire",
                "largeur_interieure":    diametre,
                "fonction_canalisation": params.get("fonction_branchement"),
                "contenu_canalisation":  contenu,
                "altitude_fil_eau_amont": node_fe.get(k_ouvrage),
                "altitude_fil_eau_aval":  cote_piquage,
            })
            out["ass_canalisation_branchement"].append(out_feat)
            stats["ecrits"] += 2

    return out, stats


def _reversed_geometry(geom):
    """Retourne une copie de la geometrie lineaire en sens inverse.

    QgsGeometry n'expose pas d'inversion portable entre versions de QGIS :
    on reconstruit la ligne sommet par sommet.
    """
    try:
        line = geom.asPolyline()
    except Exception:
        return geom
    if len(line) < 2:
        return geom
    return QgsGeometry.fromPolylineXY(list(reversed([QgsPointXY(p) for p in line])))


# ─────────────────────────────────────────────────────────────────────────────
#  Nommage normalise du fichier
# ─────────────────────────────────────────────────────────────────────────────

def file_name(params):
    """Nom de fichier conforme au geostandard.

    `Stareau-fr<code>-<SIREN><type><date>.gpkg`
    (03.7.5-consignes de nommage des fichiers)
    """
    code = (params.get("code_chantier") or "")[:10]
    siren = params.get("siren") or ""
    type_reseau = params.get("type_fichier") or "ASS"
    date = params.get("date_export") or datetime.now().strftime("%Y-%m-%d")
    return f"Stareau-fr{code}-{siren}{type_reseau}{date}.gpkg"


# ─────────────────────────────────────────────────────────────────────────────
#  Ecriture du GeoPackage
# ─────────────────────────────────────────────────────────────────────────────

def export_stareau(params, out_path, project=None, progress=None):
    """Ecrit le GeoPackage StaR-Eau. Retourne (chemin, stats).

    `progress` : callable(message, pourcentage) optionnel.
    Leve RuntimeError si aucune donnee exportable ou si l'ecriture echoue.
    """
    features, stats = _build_features(params, project)

    total = sum(len(v) for v in features.values())
    if not total:
        raise RuntimeError(
            "Aucun objet exportable. Vérifiez que les couches EU/EP sont "
            "chargées et que les conduites sont raccordées à des regards.")

    crs = QgsCoordinateReferenceSystem(CRS_STAREAU)
    if os.path.exists(out_path):
        os.remove(out_path)

    written = {}
    first = True
    for i, name in enumerate(LAYER_ORDER):
        feats = features.get(name) or []
        if not feats:
            continue
        if progress:
            progress(f"Écriture de {name}…", int(100 * i / len(LAYER_ORDER)))

        builder, wkb_type = LAYER_SCHEMAS[name]
        mem = QgsMemoryProviderUtils.createMemoryLayer(
            name, builder(), wkb_type, crs)
        mem.startEditing()
        mem.addFeatures(feats)
        mem.commitChanges()

        options = QgsVectorFileWriter.SaveVectorOptions()
        options.driverName = "GPKG"
        options.layerName = name
        options.fileEncoding = "UTF-8"
        options.actionOnExistingFile = (
            QgsVectorFileWriter.CreateOrOverwriteFile if first
            else QgsVectorFileWriter.CreateOrOverwriteLayer)

        result = QgsVectorFileWriter.writeAsVectorFormatV3(
            mem, out_path, QgsProject.instance().transformContext(), options)
        # writeAsVectorFormatV3 retourne (code, message) ou un tuple plus long
        # selon la version de QGIS ; seul le code d'erreur nous interesse.
        code = result[0] if isinstance(result, tuple) else result
        if code != QgsVectorFileWriter.NoError:
            message = result[1] if isinstance(result, tuple) and len(result) > 1 else ""
            raise RuntimeError(f"Échec de l'écriture de {name} : {message}")

        written[name] = len(feats)
        first = False

    if progress:
        progress("Terminé", 100)

    stats["couches"] = written
    return out_path, stats
