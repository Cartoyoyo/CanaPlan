# -*- coding: utf-8 -*-
"""Territoire du projet : France ou International.

Pourquoi ce module
------------------
CanaPlan est né en France et s'appuyait sur ses services publics sans le
dire : Lambert 93, Base Adresse Nationale, cadastre, orthophoto et MNT de
l'IGN. Hors de France, rien de tout cela ne répond — et le pire n'est pas ce
qui échoue, c'est ce qui continue de tourner. Un projet laissé en Lambert 93
à Abidjan dessine juste à l'écran mais allonge toutes les longueurs de 25 % :
pentes, cubatures et profils sont faux sans qu'aucun message ne le signale.

Le territoire est donc une propriété du **projet**, lue par tout ce qui
dépend d'un service ou d'un système de coordonnées :

* ``france``        — comportement historique, inchangé : Lambert 93, BAN,
                      fonds IGN, cadastre, TN sur MNT, StaR-Eau, Star-DT ;
* ``international`` — système projeté choisi pour le chantier (UTM proposé
                      d'après sa position), recherche d'adresse OSM (Photon,
                      repli Nominatim), fond OpenStreetMap, photo aérienne
                      Esri World Imagery, bâti OpenStreetMap. Pas de
                      parcelles, pas de TN automatique, pas de StaR-Eau.

Stockage : une entrée du projet QGIS (``CanaPlan/territoire``), recopiée dans
le ``metadata.json`` du .bet puisqu'un projet CanaPlan n'est pas un .qgs. Le
dernier territoire choisi est aussi retenu en QSettings : c'est la valeur
proposée au prochain projet, et celle que prend ``api.nouveau_projet`` quand
on ne lui en passe pas.
"""
import math

from qgis.core import (
    Qgis, QgsCoordinateReferenceSystem, QgsCoordinateTransform, QgsDistanceArea,
    QgsPointXY, QgsProject,
)
from qgis.PyQt.QtCore import QSettings

FRANCE = "france"
INTERNATIONAL = "international"
TERRITOIRES = (FRANCE, INTERNATIONAL)

L93 = "EPSG:2154"
WGS84 = "EPSG:4326"

_SCOPE = "CanaPlan"
_CLE_PROJET = "territoire"
_CLE_DEFAUT = "CanaPlan/territoire_defaut"

#: Écart de longueur (en %) au-delà duquel le système de coordonnées est
#: déclaré inadapté au chantier. 1 % = 1 cm par mètre : un tronçon de 50 m
#: faux de 50 cm, une pente de 1 % lue 0,99 %. Lambert 93 reste sous 0,3 %
#: sur toute la métropole ; il vaut +2,3 % à Casablanca et +25 % à Abidjan.
SEUIL_DEFORMATION_PCT = 1.0

# ── Noms des couches de fond, par territoire ─────────────────────────────
# Les recettes et l'API désignent le bâti par son nom de couche : les noms
# français restent ceux d'avant, pour que rien ne change en France.
COUCHE_BATI = {FRANCE: "PCI - Bati", INTERNATIONAL: "OSM - Bati"}
COUCHE_PARCELLES = {FRANCE: "PCI - Parcelles", INTERNATIONAL: None}

NOM_OSM = "OpenStreetMap"
NOM_ESRI = "Esri World Imagery"

URI_OSM = ("type=xyz&url=https://tile.openstreetmap.org/%7Bz%7D/%7Bx%7D/%7By%7D.png"
           "&zmax=19&zmin=0&crs=EPSG3857")
URI_ESRI = ("type=xyz&url=https://server.arcgisonline.com/ArcGIS/rest/services/"
            "World_Imagery/MapServer/tile/%7Bz%7D/%7By%7D/%7Bx%7D"
            "&zmax=19&zmin=0&crs=EPSG3857")

#: Mentions obligatoires sur les plans imprimés, par nom de couche de fond.
ATTRIBUTIONS = {
    NOM_OSM: "© OpenStreetMap contributors",
    COUCHE_BATI[INTERNATIONAL]: "© OpenStreetMap contributors",
    NOM_ESRI: "Esri, Maxar, Earthstar Geographics, and the GIS User Community",
}


# ── Lecture / écriture ───────────────────────────────────────────────────

def _normaliser(valeur):
    valeur = (valeur or "").strip().lower()
    return valeur if valeur in TERRITOIRES else None


def defaut():
    """Territoire proposé à un nouveau projet : le dernier choisi, sinon France."""
    return _normaliser(QSettings().value(_CLE_DEFAUT, FRANCE)) or FRANCE


def courant(projet=None):
    """Territoire du projet ouvert. Un projet sans entrée est un projet France :
    tous ceux créés avant cette version le sont."""
    projet = projet or QgsProject.instance()
    valeur, ok = projet.readEntry(_SCOPE, _CLE_PROJET, "")
    return (_normaliser(valeur) if ok else None) or FRANCE


def definir(territoire, projet=None, memoriser=True):
    """Fixe le territoire du projet (et le retient comme défaut)."""
    t = _normaliser(territoire)
    if t is None:
        raise ValueError("Territoire inconnu : %r (attendus : %s)"
                         % (territoire, ", ".join(TERRITOIRES)))
    (projet or QgsProject.instance()).writeEntry(_SCOPE, _CLE_PROJET, t)
    if memoriser:
        QSettings().setValue(_CLE_DEFAUT, t)
    return t


def est_france(projet=None):
    return courant(projet) == FRANCE


def couche_bati(territoire=None):
    return COUCHE_BATI[territoire or courant()]


def couche_parcelles(territoire=None):
    return COUCHE_PARCELLES[territoire or courant()]


def nom_couche(nom, territoire=None):
    """Traduit un nom de couche de fond français vers le territoire courant.

    « PCI - Bati » devient « OSM - Bati » à l'international ; « PCI -
    Parcelles » n'y a pas d'équivalent et rend None. Tout autre nom passe tel
    quel : c'est ce qui permet aux recettes écrites pour la France de tourner
    ailleurs sans être réécrites.
    """
    t = territoire or courant()
    if t == FRANCE:
        return nom
    if nom == COUCHE_BATI[FRANCE]:
        return COUCHE_BATI[t]
    if nom == COUCHE_PARCELLES[FRANCE]:
        return COUCHE_PARCELLES[t]
    return nom


# ── Systèmes de coordonnées ──────────────────────────────────────────────

def epsg_utm(lon, lat):
    """Code EPSG de la zone UTM WGS 84 qui contient le point (lon, lat)."""
    zone = int(math.floor((float(lon) + 180.0) / 6.0)) + 1
    zone = min(60, max(1, zone))
    return "EPSG:%d" % ((32600 if lat >= 0 else 32700) + zone)


def crs(authid):
    return QgsCoordinateReferenceSystem(authid)


def crs_propose(lon=None, lat=None, territoire=None):
    """Système à proposer pour un chantier : Lambert 93 en France, la zone UTM
    du point à l'international (None tant que la position est inconnue)."""
    t = territoire or courant()
    if t == FRANCE:
        return crs(L93)
    if lon is None or lat is None:
        return None
    return crs(epsg_utm(lon, lat))


def _centre_canevas_wgs84():
    try:
        from qgis.utils import iface
        canvas = iface.mapCanvas()
        centre = canvas.extent().center()
        src = canvas.mapSettings().destinationCrs()
        if not src.isValid():
            return None
        tr = QgsCoordinateTransform(src, crs(WGS84), QgsProject.instance())
        p = tr.transform(centre)
        if -180 <= p.x() <= 180 and -90 <= p.y() <= 90:
            return p
    except Exception:
        return None
    return None


def crs_projet(projet=None):
    """Système de travail du projet, toujours projeté (en mètres).

    Celui du projet s'il est projeté. Sinon — projet QGIS neuf, en
    EPSG:4326 — Lambert 93 en France, et à l'international la zone UTM du
    centre de la carte. Jamais un système en degrés : longueurs, pentes et
    cubatures en seraient fausses.
    """
    projet = projet or QgsProject.instance()
    c = projet.crs()
    if c.isValid() and not c.isGeographic():
        return c
    if courant(projet) == FRANCE:
        return crs(L93)
    p = _centre_canevas_wgs84()
    if p is not None:
        return crs(epsg_utm(p.x(), p.y()))
    return crs(L93)


def vers_projet(lon, lat, systeme=None):
    """Point WGS 84 (lon, lat) exprimé dans le système du projet."""
    tr = QgsCoordinateTransform(crs(WGS84), systeme or crs_projet(),
                                QgsProject.instance())
    return tr.transform(QgsPointXY(lon, lat))


def vers_wgs84(point, systeme=None):
    """Point du système du projet exprimé en WGS 84 (lon, lat)."""
    tr = QgsCoordinateTransform(systeme or crs_projet(), crs(WGS84),
                                QgsProject.instance())
    return tr.transform(QgsPointXY(point))


def deformation_pct(systeme, lon, lat, pas_m=100.0):
    """Écart, en %, entre une longueur mesurée dans `systeme` et la vraie.

    La vraie est la distance géodésique sur l'ellipsoïde WGS 84. On mesure
    dans les deux sens (est et nord) et on garde le pire : c'est lui qui
    fausse un tronçon mal orienté. Rend None si le calcul est impossible
    (système en degrés, point hors du domaine de la projection).
    """
    if systeme is None or not systeme.isValid() or systeme.isGeographic():
        return None
    projet = QgsProject.instance()
    wgs = crs(WGS84)
    try:
        aller = QgsCoordinateTransform(wgs, systeme, projet)
        retour = QgsCoordinateTransform(systeme, wgs, projet)
        o = aller.transform(QgsPointXY(lon, lat))
        if not all(math.isfinite(v) for v in (o.x(), o.y())):
            return None
        da = QgsDistanceArea()
        da.setEllipsoid("WGS84")
        pire = 0.0
        for dx, dy in ((pas_m, 0.0), (0.0, pas_m)):
            a = retour.transform(o)
            b = retour.transform(QgsPointXY(o.x() + dx, o.y() + dy))
            vraie = da.measureLine(a, b)
            if vraie <= 0 or not math.isfinite(vraie):
                return None
            ecart = (pas_m / vraie - 1.0) * 100.0
            if abs(ecart) > abs(pire):
                pire = ecart
        return pire
    except Exception:
        return None


def diagnostic_crs(systeme, lon=None, lat=None):
    """Contrôle qu'un système de coordonnées convient au chantier.

    Rend un dict ``{'ok', 'crs', 'deformation_pct', 'motif'}``. `motif` vaut
    None si tout va bien, sinon, du plus grave au moins grave :

    * ``crs_invalide``, ``crs_geographique``, ``crs_non_metrique`` — bloquants :
      CanaPlan calcule en mètres, un système en degrés ou en pieds (State
      Plane ftUS aux États-Unis) fausse tout ;
    * ``crs_deforme`` — les longueurs s'écartent de plus de 1 % ;
    * ``crs_hors_domaine`` — le chantier sort du domaine d'emploi du système.
      Cas distinct du précédent : sur une projection conique, l'écart de
      longueur ne dépend que de la latitude, si bien que Lambert 93 à Boulder
      (Colorado, 40° N) ne déforme que de 0,5 % — mais le nord y est tourné
      de près de 80° et les coordonnées n'ont plus de sens.

    Sans position connue, seuls la validité et l'unité sont vérifiées.
    """
    res = {"ok": True, "crs": systeme.authid() if systeme else None,
           "deformation_pct": None, "motif": None}
    if systeme is None or not systeme.isValid():
        res.update(ok=False, motif="crs_invalide")
        return res
    if systeme.isGeographic():
        res.update(ok=False, motif="crs_geographique")
        return res
    if systeme.mapUnits() != Qgis.DistanceUnit.Meters:
        res.update(ok=False, motif="crs_non_metrique")
        return res
    if lon is None or lat is None:
        return res
    d = deformation_pct(systeme, lon, lat)
    if d is None:
        res.update(ok=False, motif="crs_deforme")
        return res
    res["deformation_pct"] = round(d, 3)
    if abs(d) > SEUIL_DEFORMATION_PCT:
        res.update(ok=False, motif="crs_deforme")
    elif not dans_domaine(systeme, lon, lat):
        res.update(ok=False, motif="crs_hors_domaine")
    return res


#: Marge, en degrés, tolérée autour du domaine d'emploi d'un système : un
#: chantier à cheval sur la limite d'une zone UTM reste bien servi par elle.
MARGE_DOMAINE_DEG = 1.0

#: Motifs qui interdisent de créer un projet dans ce système.
MOTIFS_BLOQUANTS = ("crs_invalide", "crs_geographique", "crs_non_metrique")


def dans_domaine(systeme, lon, lat):
    """Vrai si (lon, lat) tombe dans le domaine d'emploi du système (± marge).

    Un système sans domaine connu est présumé valable partout.
    """
    emprise = systeme.bounds()
    if emprise.isNull() or emprise.isEmpty():
        return True
    emprise.grow(MARGE_DOMAINE_DEG)
    return emprise.contains(QgsPointXY(lon, lat))


def message_diagnostic(diag, lon=None, lat=None):
    """Texte lisible d'un diagnostic en échec, dans la langue courante."""
    from . import i18n
    if diag.get("ok"):
        return ""
    conseil = ""
    if lon is not None and lat is not None:
        conseil = epsg_utm(lon, lat)
    if diag["motif"] == "crs_geographique":
        return i18n.tr('crs_msg_geographique', crs=diag["crs"], conseil=conseil)
    if diag["motif"] == "crs_invalide":
        return i18n.tr('crs_msg_invalide')
    if diag["motif"] == "crs_non_metrique":
        return i18n.tr('crs_msg_non_metrique', crs=diag["crs"], conseil=conseil)
    if diag["motif"] == "crs_hors_domaine":
        return i18n.tr('crs_msg_hors_domaine', crs=diag["crs"], conseil=conseil)
    d = diag.get("deformation_pct")
    ecart = "?"
    if d is not None:
        ecart = ("+" if d > 0 else "") + i18n.nombre(d, 1)
    return i18n.tr('crs_msg_deforme', crs=diag["crs"], ecart=ecart,
                   conseil=conseil)


def position_chantier(projet=None):
    """(lon, lat) du centre des couches métier CanaPlan, sinon de la carte."""
    projet = projet or QgsProject.instance()
    from .layer_keys import get_layer_id
    from qgis.core import QgsRectangle
    emprise = QgsRectangle()
    systeme = None
    for reseau in ("EU", "EP"):
        for role in ("conduite", "branchement", "regard", "tabouret"):
            lid = get_layer_id(role, reseau)
            couche = projet.mapLayer(lid) if lid else None
            if couche is None or couche.featureCount() == 0:
                continue
            ext = couche.extent()
            if ext.isNull():
                continue
            systeme = systeme or couche.crs()
            if couche.crs() != systeme:
                ext = QgsCoordinateTransform(couche.crs(), systeme, projet
                                             ).transformBoundingBox(ext)
            emprise.combineExtentWith(ext)
    if systeme is not None and not emprise.isNull():
        try:
            p = QgsCoordinateTransform(systeme, crs(WGS84), projet).transform(
                emprise.center())
            return p.x(), p.y()
        except Exception as _err:
            from . import errlog
            errlog.ignored(_err, "territoire.position_chantier")
    p = _centre_canevas_wgs84()
    return (p.x(), p.y()) if p is not None else (None, None)


def diagnostic_projet(projet=None):
    """Diagnostic du système de coordonnées du projet ouvert, à sa position."""
    projet = projet or QgsProject.instance()
    lon, lat = position_chantier(projet)
    diag = diagnostic_crs(projet.crs(), lon, lat)
    diag["lon"], diag["lat"] = lon, lat
    diag["message"] = message_diagnostic(diag, lon, lat)
    return diag


def attributions(couches):
    """Mentions de source à imprimer pour une liste de couches visibles."""
    vues = []
    for c in couches:
        texte = ATTRIBUTIONS.get(c.name())
        if texte and texte not in vues:
            vues.append(texte)
    return vues
