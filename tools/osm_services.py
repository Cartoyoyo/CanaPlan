# -*- coding: utf-8 -*-
"""Services OpenStreetMap du territoire International.

* Recherche d'adresse : **Photon** (komoot), qui accepte la recherche au fil
  de la frappe — la politique d'usage de Nominatim l'interdit. Nominatim ne
  sert qu'en repli, pour un géocodage ponctuel (``geocoder``).
* Bâti : **Overpass**, sur l'emprise de la carte, écrit en GeoJSON dans le
  système du projet. Le bâti doit être dans le même système que le réseau :
  `api.creer_branchements` mesure des distances entre les deux.

Tout passe par la pile réseau de QGIS (proxy, certificats, délais configurés
dans QGIS), comme la recherche BAN.
"""
import json
import os
import tempfile
import urllib.parse

from qgis.core import (
    Qgis, QgsApplication, QgsCoordinateReferenceSystem, QgsCoordinateTransform,
    QgsCoordinateTransformContext, QgsMessageLog, QgsNetworkAccessManager,
    QgsPointXY, QgsTask,
)
from qgis.PyQt.QtCore import QObject, QTimer, QUrl, pyqtSignal
from qgis.PyQt.QtNetwork import QNetworkReply, QNetworkRequest

from . import i18n

TAG = "CanaPlan"
USER_AGENT = b"QGIS-CanaPlan (reseaux d'assainissement)"

PHOTON_URL = "https://photon.komoot.io/api/?q={query}&limit=6{lang}"
NOMINATIM_URL = ("https://nominatim.openstreetmap.org/search?format=jsonv2"
                 "&addressdetails=1&limit=1&q={query}")
DEBOUNCE_MS = 600

#: Photon ne traduit les noms que dans ces langues ; les autres gardent le nom
#: local, ce qui vaut mieux qu'une erreur.
_LANGUES_PHOTON = ("fr", "en", "de")

#: Emprise maximale demandée à Overpass pour le bâti, en degrés carrés
#: (~ 5 km × 5 km à l'équateur). Au-delà, un quartier dense dépasse le
#: délai du serveur public et la requête revient vide.
EMPRISE_MAX_DEG2 = 0.002

#: Tours complets de miroirs Overpass tentés pour le bâti, et pause entre deux.
NB_TOURS_OVERPASS = 3
PAUSE_OVERPASS_S = 8

_ACTIVE_TASKS = []


# ── Recherche d'adresse ──────────────────────────────────────────────────

def _libelle_photon(props):
    """Libellé lisible d'un résultat Photon : « 12 Rue X, Quartier, Ville, Pays »."""
    rue = props.get("street")
    numero = props.get("housenumber")
    nom = props.get("name")
    morceaux = []
    if rue:
        morceaux.append("%s %s" % (numero, rue) if numero else rue)
        if nom and nom != rue:
            morceaux.insert(0, nom)
    elif nom:
        morceaux.append(nom)
    for cle in ("district", "city", "state", "country"):
        v = props.get(cle)
        if v and v not in morceaux:
            morceaux.append(v)
    return ", ".join(morceaux)


def resultat_photon(feat):
    """Un résultat Photon au format des résultats BAN (label, lon, lat…)."""
    props = feat.get("properties", {}) or {}
    lon, lat = (feat.get("geometry", {}) or {}).get("coordinates", [0, 0])[:2]
    return {
        "label": _libelle_photon(props),
        "city": props.get("city", "") or props.get("county", ""),
        "postcode": props.get("postcode", ""),
        "type": props.get("osm_value", ""),
        "score": None,
        "nom_voie": props.get("street") or (
            props.get("name") if props.get("osm_key") == "highway" else None),
        "pays": props.get("country", ""),
        "lon": float(lon), "lat": float(lat),
    }


def _url_photon(query, limite=6, traduire=True):
    lang = i18n.langue()
    suffixe = "&lang=%s" % lang if traduire and lang in _LANGUES_PHOTON else ""
    return PHOTON_URL.format(query=urllib.parse.quote(query, safe=""),
                             lang=suffixe).replace("&limit=6", "&limit=%d" % limite)


#: Distance maximale, en km, entre la ville demandée et la rue retenue.
RAYON_LIEU_KM = 50.0

#: Importance d'un lieu OSM (clé place=*), du plus au moins important.
_RANG_LIEU = {v: i for i, v in enumerate((
    "city", "municipality", "town", "borough", "suburb", "village",
    "quarter", "neighbourhood", "hamlet", "locality", "isolated_dwelling"))}


def _distance_km(lon1, lat1, lon2, lat2):
    """Distance à vol d'oiseau (haversine), suffisante pour écarter une homonyme."""
    import math
    r = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = p2 - p1, math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def _plat(texte):
    import unicodedata
    return "".join(c for c in unicodedata.normalize("NFD", str(texte or "").lower())
                   if unicodedata.category(c) != "Mn").strip()


def classer_par_lieu(features, recherche):
    """Met en tête les résultats dont la ville, la région ou le pays est
    exactement l'un des lieux écrits après la première virgule.

    Photon classe par pertinence mondiale, pas par respect de la demande :
    « Rua das Flores, Porto » rendait d'abord Porto Seguro, au Brésil — le mot
    « Porto » y figure, mais la ville demandée n'est pas celle-là. Un lieu
    écrit par l'utilisateur est une contrainte, pas un indice : un résultat
    dont la ville est *exactement* Porto passe devant. Le tri est stable, donc
    sans lieu reconnu l'ordre de Photon est conservé.
    """
    lieux_demandes = [_plat(m) for m in (recherche or "").split(",")[1:] if m.strip()]
    if not lieux_demandes:
        return list(features)

    def rang(feat):
        p = feat.get("properties") or {}
        lieux = {_plat(p.get(k)) for k in ("city", "county", "state", "country",
                                           "district", "locality") if p.get(k)}
        if p.get("osm_key") == "place":
            lieux.add(_plat(p.get("name")))
        return -sum(1 for m in lieux_demandes if m in lieux)

    return sorted(features, key=rang)


class PhotonSearchProvider(QObject):
    """Recherche Photon avec debounce. Même contrat que BanSearchProvider :
    émet results_ready(list[dict]) avec label, city, postcode, lon, lat."""

    results_ready = pyqtSignal(list)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._nam = QgsNetworkAccessManager.instance()
        self._reply = None
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self._do_request)
        self._pending_query = ""

    def search(self, query):
        if not query or len(query) < 3:
            self._timer.stop()
            return
        self._pending_query = query
        self._timer.start(DEBOUNCE_MS)

    def cancel(self):
        self._timer.stop()
        if self._reply and self._reply.isRunning():
            self._reply.abort()

    def _do_request(self):
        if self._reply and self._reply.isRunning():
            self._reply.abort()
        request = QNetworkRequest(QUrl(_url_photon(self._pending_query)))
        request.setRawHeader(b"User-Agent", USER_AGENT)
        self._reply = self._nam.get(request)
        self._reply.finished.connect(self._on_finished)

    def _on_finished(self):
        reply = self._reply
        if reply is None:
            return
        try:
            if reply.error() != QNetworkReply.NetworkError.NoError:
                if reply.error() != QNetworkReply.NetworkError.OperationCanceledError:
                    QgsMessageLog.logMessage(
                        "Photon error: %s - %s" % (reply.error(), reply.errorString()),
                        TAG, Qgis.MessageLevel.Warning)
                self.results_ready.emit([])
                return
            data = json.loads(reply.readAll().data().decode("utf-8"))
            feats = classer_par_lieu(data.get("features", []), self._pending_query)
            self.results_ready.emit([resultat_photon(f) for f in feats])
        except (ValueError, TypeError, KeyError) as err:
            QgsMessageLog.logMessage("Photon parse error: %s" % err, TAG,
                                     Qgis.MessageLevel.Warning)
            self.results_ready.emit([])
        finally:
            reply.deleteLater()
            self._reply = None


def geocoder(recherche, get_json):
    """Géocodage ponctuel : Photon, puis Nominatim si Photon ne trouve rien.

    `get_json(url)` est la requête bloquante de l'appelant (celle de l'API,
    qui passe par la pile réseau de QGIS). Rend le premier résultat au format
    de `resultat_photon`, ou lève RuntimeError.
    """
    erreurs = []
    try:
        feats = []
        # « Rue, Ville[, Pays] » : la ville d'abord, la rue ensuite autour
        # d'elle. En une seule requête, Photon classe par notoriété mondiale :
        # « Rua das Flores, Porto » rendait dix rues du Brésil (Porto Seguro,
        # Porto Velho…) et pas une de Porto, au Portugal. Chercher « Porto »
        # parmi les lieux rend Porto (Portugal) en tête, la ville la plus
        # importante de ce nom ; la rue cherchée autour d'elle est la bonne.
        #
        # La ville se cherche SANS traduction. Traduits en français, les noms
        # ne correspondent plus à ce que l'on tape : « London » y devient
        # « Londres » pour le Royaume-Uni, et c'est London (Ontario, Canada)
        # qui passait en tête — la rue était alors cherchée autour de lui, et
        # « Neal Street, London » tombait à Détroit. Sans traduction, Photon
        # compare aux noms locaux et à toutes leurs variantes, « Londres »
        # compris, et rend la ville la plus importante de ce nom.
        #
        # Une rue rendue à plus de RAYON_LIEU_KM de la ville demandée n'est pas
        # la bonne : le biais géographique de Photon est une préférence, pas un
        # filtre.
        #
        # Mais sans traduction, un exonyme ne se reconnaît plus : « Londres »
        # rend un village d'Argentine, « Anvers » un hameau de la Nièvre. Les
        # deux requêtes partent donc, et le lieu retenu est le plus important
        # (ville avant bourg, bourg avant village) — à rang égal, celui de la
        # requête sans traduction.
        rue, _, lieu = recherche.partition(",")
        if lieu.strip():
            places = []
            for traduire in (False, True):
                places += get_json(_url_photon(lieu.strip(), limite=3,
                                               traduire=traduire)
                                   + "&osm_tag=place").get("features") or []
            places.sort(key=lambda f: _RANG_LIEU.get(
                (f.get("properties") or {}).get("osm_value"), len(_RANG_LIEU)))
            if places:
                lon, lat = places[0]["geometry"]["coordinates"][:2]
                feats = get_json(
                    _url_photon(rue.strip(), limite=10)
                    + "&lat=%.6f&lon=%.6f&zoom=12&location_bias_scale=0.1"
                    % (lat, lon)).get("features") or []
                feats = [f for f in feats
                         if _distance_km(lon, lat, *f["geometry"]["coordinates"][:2])
                         <= RAYON_LIEU_KM]
        if not feats:
            feats = get_json(_url_photon(recherche, limite=10)).get("features") or []
        feats = classer_par_lieu(feats, recherche)
        if feats:
            return dict(resultat_photon(feats[0]), service="photon")
    except Exception as err:
        erreurs.append("Photon : %s" % err)
    try:
        rep = get_json(NOMINATIM_URL.format(
            query=urllib.parse.quote(recherche, safe="")))
        if rep:
            r = rep[0]
            adr = r.get("address") or {}
            return {"label": r.get("display_name", ""),
                    "city": adr.get("city") or adr.get("town")
                            or adr.get("village") or "",
                    "postcode": adr.get("postcode", ""),
                    "type": r.get("type", ""), "score": None,
                    "nom_voie": adr.get("road"),
                    "pays": adr.get("country", ""),
                    "lon": float(r["lon"]), "lat": float(r["lat"]),
                    "service": "nominatim"}
    except Exception as err:
        erreurs.append("Nominatim : %s" % err)
    raise RuntimeError("Adresse introuvable : %s%s"
                       % (recherche, (" (%s)" % " | ".join(erreurs)) if erreurs else ""))


# ── Bâti OpenStreetMap ───────────────────────────────────────────────────

def requete_bati(sud, ouest, nord, est):
    """Requête Overpass du bâti (ways et multipolygones) sur une emprise WGS 84."""
    bbox = "%.6f,%.6f,%.6f,%.6f" % (sud, ouest, nord, est)
    return ("[out:json][timeout:25];\n"
            "(way[\"building\"](%s);\n"
            " relation[\"building\"][\"type\"=\"multipolygon\"](%s););\n"
            "out geom;" % (bbox, bbox))


def _anneau(points, transform):
    anneau = []
    for p in points:
        q = transform.transform(QgsPointXY(p["lon"], p["lat"]))
        anneau.append([round(q.x(), 3), round(q.y(), 3)])
    if len(anneau) < 4:
        return None
    if anneau[0] != anneau[-1]:
        anneau.append(anneau[0])
    return anneau


def elements_en_geojson(elements, crs_authid):
    """Éléments Overpass « out geom » -> entités GeoJSON dans `crs_authid`.

    Seuls les anneaux fermés font un bâtiment : un way ouvert tagué building
    est une erreur de saisie OSM, écartée plutôt que refermée au hasard.
    """
    transform = QgsCoordinateTransform(
        QgsCoordinateReferenceSystem("EPSG:4326"),
        QgsCoordinateReferenceSystem(crs_authid),
        QgsCoordinateTransformContext())
    features = []
    for e in elements:
        tags = e.get("tags") or {}
        polygones = []
        if e.get("type") == "way":
            geom = e.get("geometry") or []
            if len(geom) >= 4 and geom[0] == geom[-1]:
                anneau = _anneau(geom, transform)
                if anneau:
                    polygones.append([anneau])
        elif e.get("type") == "relation":
            for membre in e.get("members") or []:
                geom = membre.get("geometry") or []
                if (membre.get("role") == "outer" and len(geom) >= 4
                        and geom[0] == geom[-1]):
                    anneau = _anneau(geom, transform)
                    if anneau:
                        polygones.append([anneau])
        if not polygones:
            continue
        features.append({
            "type": "Feature",
            "properties": {
                "osm_id": "%s/%s" % (e.get("type"), e.get("id")),
                "building": tags.get("building"),
                "name": tags.get("name"),
                "addr_street": tags.get("addr:street"),
                "addr_housenumber": tags.get("addr:housenumber"),
                "levels": tags.get("building:levels"),
            },
            "geometry": ({"type": "Polygon", "coordinates": polygones[0]}
                         if len(polygones) == 1 else
                         {"type": "MultiPolygon", "coordinates": polygones}),
        })
    return features


def ecrire_geojson(features, crs_authid, prefix="bet_osm_"):
    """GeoJSON temporaire dans le dossier des fonds WFS (purgé au démarrage)."""
    from .wfs_utils import temp_dir
    code = crs_authid.split(":")[-1]
    fd, path = tempfile.mkstemp(suffix=".geojson", prefix=prefix, dir=temp_dir())
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        json.dump({"type": "FeatureCollection",
                   "crs": {"type": "name", "properties": {
                       "name": "urn:ogc:def:crs:EPSG::%s" % code}},
                   "features": features}, f, ensure_ascii=False)
    return path


def fetch_bati_async(description, emprise_wgs84, crs_authid, nom_couche, on_done):
    """Télécharge le bâti OSM en tâche de fond.

    emprise_wgs84 : QgsRectangle en degrés (lon/lat).
    on_done(results, errors) est appelé dans le thread principal, au même
    format que `wfs_utils.fetch_wfs_async` : c'est ce qui permet au plugin de
    réutiliser tel quel son ajout de couches (mise à jour en place, style,
    visibilité par échelle).
    """
    from .api import _overpass

    surface = emprise_wgs84.width() * emprise_wgs84.height()
    if surface > EMPRISE_MAX_DEG2:
        on_done([], [i18n.tr('osm_bati_emprise_trop_grande', couche=nom_couche)])
        return None

    requete = requete_bati(emprise_wgs84.yMinimum(), emprise_wgs84.xMinimum(),
                           emprise_wgs84.yMaximum(), emprise_wgs84.xMaximum())

    def _work(task):
        # Les serveurs Overpass publics rendent des 504 au hasard de leur
        # charge : mesuré le 15/09/2026, la même requête sur Dakar passe en
        # 5 s puis échoue en 10 s sur le même miroir. Un tour de miroirs ne
        # suffit donc pas ; on en refait jusqu'à trois, espacés. Dans la tâche
        # de fond, l'attente ne fige pas QGIS.
        import time
        elements, derniere = None, None
        for essai in range(NB_TOURS_OVERPASS):
            if task.isCanceled():
                return None
            try:
                # tours=1 : la boucle d'ici fait déjà les tours, espacés.
                elements = _overpass(requete, tours=1).get("elements") or []
                if elements:
                    break
            except RuntimeError as err:
                derniere = err
            task.setProgress(100.0 * (essai + 1) / (NB_TOURS_OVERPASS + 1))
            if essai < NB_TOURS_OVERPASS - 1:
                time.sleep(PAUSE_OVERPASS_S)
        if elements is None:
            raise derniere or RuntimeError("Overpass injoignable")
        if task.isCanceled():
            return None
        feats = elements_en_geojson(elements, crs_authid)
        path = ecrire_geojson(feats, crs_authid) if feats else None
        return ([{"name": nom_couche, "path": path, "count": len(feats),
                  "insecure": False}], [])

    def _finished(exception, value=None):
        if task in _ACTIVE_TASKS:
            _ACTIVE_TASKS.remove(task)
        if exception is not None:
            on_done([], ["%s : %s" % (nom_couche, exception)])
        elif value is None:
            on_done([], [])
        else:
            on_done(*value)

    task = QgsTask.fromFunction(description, _work, on_finished=_finished)
    _ACTIVE_TASKS.append(task)
    QgsApplication.taskManager().addTask(task)
    return task
