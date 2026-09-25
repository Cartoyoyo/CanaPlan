# tools/stareau_export_aep.py
"""Export du réseau AEP (eau potable) vers les tables StaR-Eau V2024.

Schémas `stareau_aep` et `stareau_aep_brcht` du modèle (scripts 06 et 07 du
dépôt github.com/cnigfr/StaR-Eau). Même principe que l'assainissement
(tools/stareau_export.py) : un GeoPackage dont chaque couche porte le nom et
les colonnes d'une table du modèle.

Correspondance des objets :

    conduite AEP              -> aep_canalisation
    nœud (selon son type)     -> aep_vanne, aep_appareillage, aep_regulation,
                                 aep_point_mesure, aep_point_livraison (PEI),
                                 aep_piece  (cf. stareau_values.AEP_CLASSE_NOEUD)
    robinet de branchement    -> aep_raccord  (non sécant, ref_canalisation)
    branchement AEP           -> aep_canalisation_branchement
    compteur (terminal)       -> aep_point_livraison

Sens des arcs. Le réseau est sous pression : pas de sens d'écoulement à lire
dans les cotes. Les conduites gardent le sens de dessin ; les branchements
vont du raccord (côté conduite) vers le point de livraison, sens de
distribution de l'eau.

Altimétrie. StaR-Eau ne porte pas de fil d'eau en AEP mais la cote de la
génératrice supérieure (cote_debut / cote_fin) : elle vaut fil d'eau + DN.
"""
from qgis.core import QgsFeature, QgsWkbTypes
from qgis.PyQt.QtCore import QMetaType

from . import i18n
from . import reseaux as R
from . import stareau_values as sv

T = QMetaType.Type

_NOEUD = (("id_noeud_reseau", T.QString),)


def _schemas(fields, common, canalisation, dimension):
    """Schémas des tables AEP. Les blocs communs viennent de stareau_export
    pour que les deux exports ne puissent pas diverger."""
    return {
        "aep_canalisation": fields(
            ("id_canalisation", T.QString), ("id_aep_canalisation", T.QString),
            *common, *canalisation, *dimension,
            ("fonction_canalisation", T.QString), ("contenu_canalisation", T.QString),
            ("protection_cathodique", T.QString), ("etage_pression", T.QString),
            ("type_pression", T.QString), ("secteur_hydraulique", T.QString),
            ("ref_udi", T.QString), ("cote_debut", T.Double), ("cote_fin", T.Double)),
        "aep_canalisation_branchement": fields(
            ("id_canalisation", T.QString),
            ("id_aep_canalisation_branchement", T.QString),
            *common, *canalisation, *dimension,
            ("fonction_canalisation", T.QString), ("contenu_canalisation", T.QString),
            ("protection_cathodique", T.QString),
            ("cote_debut", T.Double), ("cote_fin", T.Double)),
        "aep_vanne": fields(
            *_NOEUD, ("id_aep_vanne", T.QString), *common,
            ("type_vanne", T.QString), ("fonction_vanne", T.QString),
            ("diametre", T.Double), ("sens_fermeture", T.QString),
            ("etat_ouverture", T.QString), ("blocage", T.QString),
            ("motorisation", T.QString), ("telegestion", T.QString)),
        "aep_regulation": fields(
            *_NOEUD, ("id_aep_regulation", T.QString), *common,
            ("nom_usuel", T.QString), ("type_regulation", T.QString),
            ("type_consigne", T.QString), ("consigne_amont", T.Double),
            ("consigne_aval", T.Double), ("marque", T.QString),
            ("diametre", T.Double), ("annee_fabrication", T.Int),
            ("telegestion", T.QString)),
        "aep_appareillage": fields(
            *_NOEUD, ("id_aep_appareillage", T.QString), *common,
            ("type_appareillage", T.QString), ("diametre", T.Double),
            ("telegestion", T.QString)),
        "aep_point_mesure": fields(
            *_NOEUD, ("id_aep_point_mesure", T.QString), *common,
            ("nom_usuel", T.QString), ("type_point_mesure", T.QString),
            ("fonction_point_mesure", T.QString), ("calibre", T.Double),
            ("annee_fabrication", T.Int), ("marque", T.QString),
            ("numero_serie", T.QString), ("telegestion", T.QString)),
        "aep_piece": fields(
            *_NOEUD, ("id_aep_piece", T.QString), *common,
            ("type_piece", T.QString)),
        "aep_point_livraison": fields(
            *_NOEUD, ("id_point_livraison", T.QString), *common,
            ("type_point_livraison", T.QString), ("type_usager", T.QString),
            ("ref_externe", T.QString), ("ref_client", T.QString)),
        "aep_raccord": fields(
            *_NOEUD, ("id_raccord", T.QString), *common,
            ("ref_canalisation", T.QString)),
    }


GEOMETRIES = {
    "aep_canalisation": QgsWkbTypes.Type.LineString,
    "aep_canalisation_branchement": QgsWkbTypes.Type.LineString,
}
# Tables referencées d'abord : nœuds, puis arcs.
ORDRE = ("aep_vanne", "aep_regulation", "aep_appareillage", "aep_point_mesure",
         "aep_piece", "aep_point_livraison", "aep_raccord",
         "aep_canalisation", "aep_canalisation_branchement")

# Colonne d'identifiant métier de chaque table de nœuds.
_ID_METIER = {
    "aep_vanne": "id_aep_vanne", "aep_regulation": "id_aep_regulation",
    "aep_appareillage": "id_aep_appareillage",
    "aep_point_mesure": "id_aep_point_mesure", "aep_piece": "id_aep_piece",
    "aep_point_livraison": "id_point_livraison", "aep_raccord": "id_raccord",
}


def schemas(se):
    """Schémas instanciés, à partir des blocs de tools/stareau_export (`se`)."""
    return _schemas(se._fields, se._CHAMP_COMMUN, se._CANALISATION, se._DIMENSION)


def construire(params, layers, se, ids, stats):
    """Entités StaR-Eau AEP : {table: [QgsFeature]}.

    `layers` : {(role, reseau): couche} ; `se` : module stareau_export (outils
    partagés) ; `ids` : fabrique d'identifiants de l'export ; `stats` : compteur
    {'ecrits', 'ignores'} mis à jour.
    """
    sch = schemas(se)
    out = {name: [] for name in sch}
    noeuds = layers.get(("regard", "AEP"))
    terminaux = layers.get(("tabouret", "AEP"))
    conduites = layers.get(("conduite", "AEP"))
    branchements = layers.get(("branchement", "AEP"))
    if conduites is None or noeuds is None:
        return out

    common = se._common_values(params, "AEP")
    common["type_reseau"] = "aep"
    mat_defaut = params.get("materiau_defaut", "nr")
    oui_non = lambda v: "oui" if v else "non"   # noqa: E731

    # ── Index des nœuds et DN porté par chacun ────────────────────────────
    index = se._NodeIndex()
    for f in noeuds.getFeatures():
        index.add("regard", f)
    for f in (terminaux.getFeatures() if terminaux else []):
        index.add("tabouret", f)

    dn_noeud = {}
    for c in conduites.getFeatures():
        p0, p1 = se._line_points(c)
        dn = se._num(c, "diametre")
        for p in (p0, p1):
            k = index.find(p)
            if k is not None and dn:
                dn_noeud[k] = max(dn_noeud.get(k, 0.0), dn)

    # Robinets de branchement : conduite qui les porte (ref_canalisation).
    depart_br = {}           # {(role, fid) du nœud de départ: branchement}
    for br in (branchements.getFeatures() if branchements else []):
        p0, _p1 = se._line_points(br)
        k = index.find(p0)
        if k is not None:
            depart_br.setdefault(k, br)

    uuid_noeud, nom_noeud, fe_noeud = {}, {}, {}

    # ── Nœuds ─────────────────────────────────────────────────────────────
    raccords = []            # robinets à écrire après les conduites
    for f in noeuds.getFeatures():
        g = f.geometry()
        if g is None or g.isEmpty():
            stats["ignores"] += 1
            continue
        key = ("regard", f.id())
        code = se._txt(f, "type") or R.AEP_NOEUD_TYPE_DEFAUT
        nom = se._txt(f, "nom") or f"N{f.id()}"
        metier, tech = ids.make("AEP", (nom,))
        uuid_noeud[key], nom_noeud[key] = tech, nom
        fe_noeud[key] = se._num(f, "fe_radier")

        if code == R.AEP_NOEUD_BRANCHEMENT:
            raccords.append((f, key, metier, tech))
            continue

        table, col, valeur = sv.AEP_CLASSE_NOEUD.get(
            code, sv.AEP_CLASSE_NOEUD[R.AEP_NOEUD_TYPE_DEFAUT])
        dn = dn_noeud.get(key) or se._num(f, "diametre")
        feat = QgsFeature(sch[table])
        feat.setGeometry(g)
        se._set(feat, common)
        valeurs = {"id_noeud_reseau": tech, _ID_METIER[table]: metier}
        if col:
            valeurs[col] = valeur
        if table == "aep_vanne":
            valeurs.update({
                "type_vanne": params.get("aep_type_vanne", "opercule"),
                "fonction_vanne": params.get("aep_fonction_vanne", "coupure"),
                "diametre": dn, "sens_fermeture": params.get("aep_sens_fermeture", "FSH"),
                "etat_ouverture": "ouverte", "blocage": "non",
                "motorisation": "non", "telegestion": "non"})
        elif table == "aep_regulation":
            valeurs.update({"nom_usuel": nom, "type_consigne": "aval",
                            "diametre": dn, "telegestion": "non"})
        elif table == "aep_appareillage":
            valeurs.update({"diametre": dn, "telegestion": "non"})
        elif table == "aep_point_mesure":
            valeurs.update({"nom_usuel": nom, "calibre": dn,
                            "fonction_point_mesure": "sectorisation",
                            "telegestion": "non"})
        elif table == "aep_point_livraison":
            valeurs.update({"type_usager": params.get("type_usager", "domestique"),
                            "ref_externe": sv.AEP_PEI.get(code)})
        se._set(feat, valeurs)
        out[table].append(feat)
        stats["ecrits"] += 1

    # ── Compteurs (terminaux) → points de livraison ──────────────────────
    type_pl = params.get("aep_type_point_livraison", "citerneau")
    for f in (terminaux.getFeatures() if terminaux else []):
        g = f.geometry()
        if g is None or g.isEmpty():
            stats["ignores"] += 1
            continue
        key = ("tabouret", f.id())
        nom = se._txt(f, "nom") or f"CPT{f.id()}"
        metier, tech = ids.make("AEP", ("PL", nom))
        uuid_noeud[key], nom_noeud[key] = tech, nom
        fe_noeud[key] = se._num(f, "fe_entree")
        feat = QgsFeature(sch["aep_point_livraison"])
        feat.setGeometry(g)
        se._set(feat, common)
        se._set(feat, {
            "id_noeud_reseau": tech, "id_point_livraison": metier,
            "type_point_livraison": ("sans" if se._txt(f, "type") == "extremite_libre"
                                     else type_pl),
            "type_usager": params.get("type_usager", "domestique"),
        })
        out["aep_point_livraison"].append(feat)
        stats["ecrits"] += 1

    # ── Conduites ─────────────────────────────────────────────────────────
    uuid_conduite = {}
    for c in conduites.getFeatures():
        p0, p1 = se._line_points(c)
        if p0 is None:
            stats["ignores"] += 1
            continue
        k0, k1 = index.find(p0), index.find(p1)
        if k0 is None or k1 is None:
            stats["ignores"] += 1
            continue
        dn = se._num(c, "diametre")
        materiau = sv.materiau_code(se._txt(c, "materiau"), mat_defaut)
        a, b = nom_noeud.get(k0, ""), nom_noeud.get(k1, "")
        metier, tech = ids.make("AEP", ("C", a, b), ("C", se._mat_dn(materiau, dn), a, b))
        uuid_conduite[c.id()] = tech
        gs = lambda fe: round(fe + (dn or 0) / 1000.0, 3) if fe is not None else None  # noqa: E731
        feat = QgsFeature(sch["aep_canalisation"])
        feat.setGeometry(c.geometry())
        se._set(feat, common)
        se._set(feat, {
            "id_canalisation": tech, "id_aep_canalisation": metier,
            "mode_circulation": params.get("mode_circulation"),
            "type_pose": params.get("type_pose"),
            "raison_pose": params.get("raison_pose"),
            "materiau": materiau,
            "revetement_interieur": params.get("revetement_interieur"),
            "diametre_equivalent": int(dn) if dn else None,
            "longueur_terrain": se._num(c, "longueur"),
            "sensible": bool(params.get("sensible", False)),
            "noeudinitial": uuid_noeud.get(k0), "noeudterminal": uuid_noeud.get(k1),
            "forme": "circulaire", "largeur_interieure": dn,
            "fonction_canalisation": params.get("aep_fonction_canalisation", "distribution"),
            "contenu_canalisation": params.get("aep_contenu_canalisation", "eau_potable"),
            "protection_cathodique": oui_non(False),
            "type_pression": params.get("aep_type_pression", "gravitaire"),
            "cote_debut": gs(fe_noeud.get(k0)), "cote_fin": gs(fe_noeud.get(k1)),
        })
        out["aep_canalisation"].append(feat)
        stats["ecrits"] += 1

    # ── Raccords (robinets de branchement) ───────────────────────────────
    from .spatial_utils import nearest_line_feature
    for f, key, metier, tech in raccords:
        br = depart_br.get(key)
        cond_id = se._val(br, "id_conduite") if br is not None else None
        if cond_id is None:
            cf, _p, _d = nearest_line_feature(conduites, f.geometry().asPoint(), 0.05)
            cond_id = cf.id() if cf is not None else None
        feat = QgsFeature(sch["aep_raccord"])
        feat.setGeometry(f.geometry())
        se._set(feat, common)
        se._set(feat, {
            "id_noeud_reseau": tech, "id_raccord": metier,
            "ref_canalisation": uuid_conduite.get(int(cond_id)) if cond_id is not None else None,
        })
        out["aep_raccord"].append(feat)
        stats["ecrits"] += 1

    # ── Branchements ──────────────────────────────────────────────────────
    for br in (branchements.getFeatures() if branchements else []):
        p0, p1 = se._line_points(br)
        if p0 is None:
            stats["ignores"] += 1
            continue
        k0, k1 = index.find(p0), index.find(p1)
        if k1 is None:
            stats["ignores"] += 1
            continue
        dn = se._num(br, "diametre")
        materiau = sv.materiau_code(se._txt(br, "materiau"), mat_defaut)
        cible = nom_noeud.get(k1, "")
        metier, tech = ids.make("AEP", ("B", cible), ("B", se._mat_dn(materiau, dn), cible))
        fe0 = fe_noeud.get(k0) if k0 else se._num(br, "cote_piquage")
        gs = lambda fe: round(fe + (dn or 0) / 1000.0, 3) if fe is not None else None  # noqa: E731
        feat = QgsFeature(sch["aep_canalisation_branchement"])
        feat.setGeometry(br.geometry())
        se._set(feat, common)
        se._set(feat, {
            "id_canalisation": tech, "id_aep_canalisation_branchement": metier,
            "mode_circulation": params.get("mode_circulation"),
            "type_pose": params.get("type_pose"),
            "raison_pose": params.get("raison_pose"),
            "materiau": materiau,
            "revetement_interieur": params.get("revetement_interieur"),
            "diametre_equivalent": int(dn) if dn else None,
            "longueur_terrain": se._num(br, "longueur"),
            "sensible": bool(params.get("sensible", False)),
            "noeudinitial": uuid_noeud.get(k0) if k0 else None,
            "noeudterminal": uuid_noeud.get(k1),
            "forme": "circulaire", "largeur_interieure": dn,
            "fonction_canalisation": params.get("aep_fonction_branchement", "usager"),
            "contenu_canalisation": params.get("aep_contenu_canalisation", "eau_potable"),
            "protection_cathodique": oui_non(False),
            "cote_debut": gs(fe0), "cote_fin": gs(fe_noeud.get(k1)),
        })
        out["aep_canalisation_branchement"].append(feat)
        stats["ecrits"] += 1

    return out


def controler(layers, se, add):
    """Contrôle de conformité AEP. `add(niveau, couche, entité, objet, message)`.

    Pas d'avertissement TN / fil d'eau par nœud : il y a un coude à chaque
    sommet, la liste en serait noyée ; les cotes AEP sont d'ailleurs
    facultatives dans le modèle.
    """
    noeuds = layers.get(("regard", "AEP"))
    terminaux = layers.get(("tabouret", "AEP"))
    index = se._NodeIndex()
    for role, lyr in (("regard", noeuds), ("tabouret", terminaux)):
        for f in (lyr.getFeatures() if lyr else []):
            index.add(role, f)
    for role, lyr in (("conduite", layers.get(("conduite", "AEP"))),
                      ("branchement", layers.get(("branchement", "AEP")))):
        if lyr is None:
            continue
        label = "Conduite" if role == "conduite" else "Branchement"
        for f in lyr.getFeatures():
            objet = f"{label} #{f.id()} (AEP)"
            p0, p1 = se._line_points(f)
            if p0 is None:
                add("bloquant", lyr, f, objet, i18n.tr('sec_geom_invalide'))
                continue
            if se._num(f, "diametre") is None:
                add("bloquant", lyr, f, objet, i18n.tr('sec_diametre_absent'))
            if not se._txt(f, "materiau"):
                add("avertissement", lyr, f, objet, i18n.tr('sec_materiau_absent'))
            if role == "conduite":
                if index.find(p0) is None or index.find(p1) is None:
                    add("bloquant", lyr, f, objet, i18n.tr('sec_extremite_sans_regard'))
            elif index.find(p1) is None:
                add("bloquant", lyr, f, objet, i18n.tr('sec_aucune_extremite'))
