# -*- coding: utf-8 -*-
"""Façade de pilotage de CanaPlan par script (console Python, MCP, agent).

Pourquoi ce module
------------------
Les outils de CanaPlan sont faits pour une souris : ce sont des `QgsMapTool`
nourris par des clics, et des `QDialog` qui rendent des dictionnaires. Piloté
depuis l'extérieur, cela pose trois problèmes qui n'existent pas sous la main
d'un opérateur :

1. **Les fenêtres modales bloquent.** Un `QMessageBox` ouvert depuis un appel
   distant fige QGIS : plus rien ne répond, la session est perdue.
2. **Les tolérances de snap sont en pixels**, donc dépendantes du zoom. Ce qui
   est juste sous la souris devient un paramètre caché quand personne ne
   regarde l'écran : à l'échelle de la rue, la tolérance des regards vaut
   plusieurs mètres et fusionne des ouvrages distincts.
3. **Chaque aller-retour coûte.** Reconstruire l'état (imports, couches,
   cadrage) à chaque appel domine le temps total.

Ce module répond aux trois : il n'instancie **aucun widget**, il impose les
tolérances **en mètres**, et il expose des **verbes métier** qui font une
opération complète en un appel, en rendant un résultat sérialisable.

Il n'y a pas de logique métier ici : tout est délégué aux outils existants,
pour que le résultat soit identique au geste manuel — snapping, topologie,
valeurs par défaut comprises.

Usage
-----
    from CanaPlan.tools import api

    api.etat()
    api.nouveau_projet(adresse="Rue Julien Charpentier, 03250 Châtel-Montagne",
                       dossier="~/Documents/CanaPlan")
    api.tracer_conduite("EU", axe=api.axe_de_rue("Rue Julien Charpentier",
                                                 "Châtel-Montagne"))
    api.creer_branchements("EU", distance_max=10)
    api.renumeroter("EU")
    api.caler_cotes("EU", tn=100, ancrage=("REU07", 2.50), pente=1.0,
                    tabourets={"tn": 100, "profondeur": 0.50})
    t = api.exporter_async(echelle=200, format="A4", orientation="portrait")
    api.tache(t)          # à interroger jusqu'à etat == "fini"
"""

import json
import math
import os
import time
import urllib.parse
import urllib.request
import uuid

from qgis.core import (
    Qgis, QgsCoordinateReferenceSystem, QgsCoordinateTransform, QgsFeatureRequest,
    QgsGeometry, QgsPointXY, QgsProject, QgsRectangle,
)
from qgis.PyQt.QtCore import QTimer, QVariant
from qgis.PyQt.QtWidgets import QDialog, QMessageBox

from . import i18n

L93 = "EPSG:2154"
WGS84 = "EPSG:4326"

#: Tolérance de snap imposée aux outils quand on les pilote (mètres). Assez
#: large pour rattraper un point calculé, assez fine pour ne jamais confondre
#: deux ouvrages : le minimum réglementaire entre deux regards est de 0,50 m.
TOL_SNAP_M = 0.20

_UA = {"User-Agent": "QGIS-CanaPlan/1.8 (assainissement)"}

_taches = {}

#: Axes de rue deja rapatries d'Overpass, par (voie, commune, insee). Une
#: requete coute ~2,5 s et l'axe ne bouge pas d'un appel a l'autre.
_axes = {}


# ───────────────────────────────────────────────────────────── infrastructure

def _plugin():
    import qgis.utils
    p = qgis.utils.plugins.get("CanaPlan")
    if p is None:
        raise RuntimeError("Le plugin CanaPlan n'est pas chargé.")
    return p


def _iface():
    from qgis.utils import iface
    return iface


class sans_fenetre:
    """Empêche toute boîte de dialogue de s'ouvrir pendant le bloc.

    Une modale ouverte depuis un appel distant fige QGIS sans retour possible.
    Plutôt que de risquer l'interblocage, on remplace les quatre entrées de
    `QMessageBox` : les messages sont collectés dans `.messages` et remontés
    dans le résultat, et les questions reçoivent la réponse affirmative — un
    script qui appelle l'API a déjà décidé.

    `QDialog.exec` est également neutralisé : certains chemins du plugin
    ouvrent une fenêtre de réglages en cours de route.

    Les **modales ouvertes sur une instance** le sont tout autant. Neutraliser
    les seules fonctions statiques de `QMessageBox` et `QDialog.exec` laissait
    passer `exec_dialog(box)` — la voie que prend le plugin pour rester
    compatible PyQt5/PyQt6 : elle appelle `box.exec_()`, lié à `QMessageBox`,
    et non `QDialog.exec`. Le compte rendu de fin d'export s'ouvrait donc
    réellement et bloquait la tâche asynchrone, qui restait « en cours »
    jusqu'à ce qu'un humain clique — exactement l'interblocage que cette classe
    existe pour éviter. `exec` et `exec_` sont donc remplacés sur `QDialog`
    **et** sur `QMessageBox`, dont le texte part dans `.messages`.
    """

    _NIVEAUX = ("information", "warning", "critical")

    def __init__(self):
        self.messages = []

    def __enter__(self):
        collecteur = self
        self._orig = {n: getattr(QMessageBox, n)
                      for n in self._NIVEAUX + ("question",)}
        self._orig_exec = {}
        for classe in (QDialog, QMessageBox):
            for nom in ("exec", "exec_"):
                if nom in vars(classe):
                    self._orig_exec[(classe, nom)] = vars(classe)[nom]

        def _capte(niveau):
            def _f(*a, **k):
                collecteur.messages.append(
                    {"niveau": niveau,
                     "texte": a[2] if len(a) > 2 else " ".join(map(str, a))})
                return None
            return _f

        for n in self._NIVEAUX:
            setattr(QMessageBox, n, staticmethod(_capte(n)))
        QMessageBox.question = staticmethod(
            lambda *a, **k: (collecteur.messages.append(
                {"niveau": "question", "texte": a[2] if len(a) > 2 else ""}),
                QMessageBox.StandardButton.Yes)[1])

        def _exec_boite(boite, *a, **k):
            """Recueille le texte de la boîte au lieu de l'afficher."""
            try:
                texte = " ".join(t for t in (boite.text(),
                                             boite.informativeText(),
                                             boite.detailedText()) if t)
                titre = boite.windowTitle()
            except Exception:
                texte, titre = "", ""
            collecteur.messages.append({"niveau": "rapport", "titre": titre,
                                        "texte": texte})
            return QMessageBox.StandardButton.Ok

        def _exec_dialogue(dialogue, *a, **k):
            return QDialog.DialogCode.Accepted

        for nom in ("exec", "exec_"):
            if hasattr(QDialog, nom):
                setattr(QDialog, nom, _exec_dialogue)
            if hasattr(QMessageBox, nom):
                setattr(QMessageBox, nom, _exec_boite)
        return self

    def __exit__(self, *_exc):
        for n, f in self._orig.items():
            setattr(QMessageBox, n, f)
        for nom in ("exec", "exec_"):
            for classe in (QDialog, QMessageBox):
                origine = self._orig_exec.get((classe, nom))
                if origine is not None:
                    setattr(classe, nom, origine)
                elif nom in vars(classe):
                    # Entrée héritée : la retirer rend la méthode de la classe mère.
                    delattr(classe, nom)
        return False


def _couches(reseau):
    return _plugin()._get_couches(reseau)


def _cadrer(geom_ou_points, marge=20.0):
    """Cadre le canevas sur l'objet de travail.

    Utile pour les captures et pour le confort visuel, jamais pour la
    précision : les tolérances sont fixées en mètres par `TOL_SNAP_M`.
    """
    if isinstance(geom_ou_points, QgsGeometry):
        bb = geom_ou_points.boundingBox()
    else:
        xs = [p.x() for p in geom_ou_points]
        ys = [p.y() for p in geom_ou_points]
        bb = QgsRectangle(min(xs), min(ys), max(xs), max(ys))
    bb.grow(marge)
    canvas = _iface().mapCanvas()
    canvas.setExtent(bb)
    canvas.refresh()


def _to_l93(lon, lat):
    tr = QgsCoordinateTransform(QgsCoordinateReferenceSystem(WGS84),
                                QgsCoordinateReferenceSystem(L93),
                                QgsProject.instance())
    return tr.transform(QgsPointXY(lon, lat))


def _get_json(url, data=None):
    """Requête JSON par la pile réseau de QGIS.

    Passer par `QgsBlockingNetworkRequest` plutôt que par `urllib` n'est pas
    qu'une affaire de scanner : le plugin hérite ainsi du proxy, des
    certificats et des délais configurés dans QGIS — ce qu'`urllib` ignore,
    alors que la plupart des collectivités sortent par un proxy.
    """
    from qgis.core import QgsBlockingNetworkRequest
    from qgis.PyQt.QtCore import QByteArray, QUrl
    from qgis.PyQt.QtNetwork import QNetworkRequest

    if not url.lower().startswith("https://"):
        raise RuntimeError("URL refusée (https attendu) : %s" % url)
    requete = QNetworkRequest(QUrl(url))
    requete.setRawHeader(b"User-Agent", _UA["User-Agent"].encode("utf-8"))
    bloquante = QgsBlockingNetworkRequest()
    if data is None:
        code = bloquante.get(requete)
    else:
        requete.setHeader(QNetworkRequest.KnownHeaders.ContentTypeHeader,
                          "application/x-www-form-urlencoded")
        code = bloquante.post(requete, QByteArray(data))
    if code != QgsBlockingNetworkRequest.ErrorCode.NoError:
        raise RuntimeError("Requête réseau échouée : %s"
                           % (bloquante.errorMessage() or code))
    return json.loads(bytes(bloquante.reply().content()).decode("utf-8"))


def _nb(valeur):
    """Attribut numerique en float, ou None si le champ est vide.

    Un champ NULL ne remonte pas `None` depuis le provider OGR mais un
    `QVariant` nul, qui passe sans bruit le test `is None` et fait planter le
    `float()` suivant. Toute lecture de cote passe donc par ici : une cote
    absente doit se rendre compte, pas lever.
    """
    if isinstance(valeur, QVariant):
        valeur = None if valeur.isNull() else valeur.value()
    if valeur is None or valeur == "":
        return None
    try:
        return float(valeur)
    except (TypeError, ValueError):
        return None


def _chemin(p):
    """Chemin absolu, ~ developpe et separateurs homogenes.

    os.path.expanduser recolle le HOME Windows avec des antislashs sur un
    argument ecrit avec des slashs : le chemin rendu melange les deux
    separateurs et n'est pas comparable d'un appel a l'autre.
    """
    return os.path.normpath(os.path.expanduser(p)) if p else p


def _bet_courant():
    """Chemin du projet .bet courant, tel que le plugin le retient."""
    from qgis.PyQt.QtCore import QSettings
    from .projet_bet import _KEY_BET_PATH
    return _chemin(QSettings().value(_KEY_BET_PATH, "") or "")


# ─────────────────────────────────────────────────────────────────── lecture

def etat():
    """Inventaire du projet : couches métier, fonds, fenêtres ouvertes."""
    projet = QgsProject.instance()
    res = {"reseaux": {}, "fonds": [], "fenetres": _fenetres_ouvertes()}
    for reseau in ("EU", "EP"):
        jeu = _couches(reseau)
        res["reseaux"][reseau] = {
            role: {"nom": c.name(), "entites": c.featureCount(),
                   "source": c.dataProvider().name()}
            for role, c in jeu.items()
        }
    metier = {c.id() for r in ("EU", "EP") for c in _couches(r).values()}
    for c in projet.mapLayers().values():
        if c.id() not in metier:
            res["fonds"].append(c.name())
    # Un projet CanaPlan est un .bet, pas un .qgs : `QgsProject.fileName()`
    # est vide juste apres `nouveau_projet()` et rendait "projet": null.
    res["projet"] = _bet_courant() or projet.fileName() or None
    res["qgs"] = projet.fileName() or None
    return res


def _fenetres_ouvertes():
    from qgis.PyQt.QtWidgets import QApplication
    return [type(w).__name__ for w in QApplication.topLevelWidgets()
            if isinstance(w, QDialog) and "CanaPlan" in type(w).__module__]


def fermer(detruire=True):
    """Ferme et détruit les fenêtres CanaPlan, désactive l'outil carte actif.

    À appeler en fin de séance scriptée : instancier un dialogue pour lire ses
    réglages laisse un widget vivant, invisible mais bien présent, et ils
    s'accumulent d'une opération à l'autre.
    """
    from qgis.PyQt.QtWidgets import QApplication
    plugin = _plugin()
    fermees = []
    for w in list(QApplication.topLevelWidgets()):
        if isinstance(w, QDialog) and "CanaPlan" in type(w).__module__:
            fermees.append(type(w).__name__)
            w.close()
            if detruire:
                w.setParent(None)
                w.deleteLater()
    plugin._tableau_saisie_dialog = None
    try:
        plugin._cleanup_tools()
    except (AttributeError, RuntimeError):
        # AttributeError : un plugin partiellement chargé n'a pas la méthode.
        # RuntimeError : un outil dont l'objet C++ a déjà été détruit. Dans
        # les deux cas il n'y a plus rien à nettoyer.
        pass
    outil = _iface().mapCanvas().mapTool()
    if outil is not None:
        _iface().mapCanvas().unsetMapTool(outil)
    # deleteLater ne prend effet qu'au tour de boucle suivant, et un widget
    # qui vient d'etre ferme peut survivre plusieurs tours. Sans cette
    # attente, `restantes` listerait des fenetres deja condamnees.
    # Piege : QApplication.processEvents() ne traite PAS les suppressions
    # differees. Sans sendPostedEvents(DeferredDelete), les fenetres fermees
    # restent vivantes indefiniment et `restantes` les liste a tort.
    from qgis.PyQt.QtCore import QEvent
    t0 = time.time()
    while _fenetres_ouvertes() and time.time() - t0 < 1.0:
        QApplication.processEvents()
        QApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
        time.sleep(0.02)
    return {"fermees": fermees, "restantes": _fenetres_ouvertes()}


# ─────────────────────────────────────────────────────────── données externes

def adresse(recherche):
    """Géocode une adresse sur la Base Adresse Nationale."""
    url = ("https://api-adresse.data.gouv.fr/search/?limit=1&q="
           + urllib.parse.quote(recherche))
    feats = _get_json(url).get("features") or []
    if not feats:
        raise RuntimeError("Adresse introuvable : %s" % recherche)
    f = feats[0]
    lon, lat = f["geometry"]["coordinates"]
    p = _to_l93(lon, lat)
    return {"label": f["properties"]["label"], "score": f["properties"]["score"],
            "insee": f["properties"].get("citycode"),
            "lon": lon, "lat": lat, "x": p.x(), "y": p.y()}


def axe_de_rue(nom_voie, commune=None, insee=None, rafraichir=False):
    """Axe de chaussée d'une rue, en Lambert 93, depuis OpenStreetMap.

    L'axe OSM est l'axe de la voie : une conduite posée dessus est centrée
    dans la rue par construction. Retourne une `QgsGeometry` de type ligne.

    Le résultat est mis en cache pour la session : rappeler la fonction avec
    les mêmes arguments ne refait pas la requête Overpass (~2,5 s). Passer
    `rafraichir=True` pour forcer un nouvel appel.
    """
    cle = (nom_voie.strip().lower(), (commune or "").strip().lower(), insee or "")
    if not rafraichir and cle in _axes:
        return QgsGeometry(_axes[cle])
    if not insee:
        insee = adresse("%s, %s" % (nom_voie, commune or ""))["insee"]
    requete = (
        '[out:json][timeout:40];\n'
        'area["ref:INSEE"="%s"][admin_level=8]->.a;\n'
        'way[highway][name~"%s",i](area.a);\n'
        'out geom;' % (insee, nom_voie.replace('"', ''))
    )
    data = _get_json("https://overpass-api.de/api/interpreter",
                     urllib.parse.urlencode({"data": requete}).encode())
    elements = data.get("elements") or []
    if not elements:
        raise RuntimeError("Rue introuvable dans OSM : %s" % nom_voie)
    pts = []
    for e in elements:
        pts.extend(_to_l93(p["lon"], p["lat"]) for p in e["geometry"])
    geom = QgsGeometry.fromPolylineXY(pts)
    _axes[cle] = QgsGeometry(geom)
    return geom


# ────────────────────────────────────────────────────────────────── projet

def nouveau_projet(adresse=None, dossier=None, nom=None, fonds=None,
                   demi_emprise=200.0):
    """Crée un projet CanaPlan, sans passer par l'assistant.

    Reproduit exactement ce que fait la dernière page de l'assistant, mais
    sans construire la fenêtre. `fonds` accepte les clés de `run_fond_projet`
    ('osm', 'ortho', 'ban', 'noms_voie', 'pci_bati', 'pci_parcelles') ; par
    défaut tout est chargé — dont le bâti cadastral, que l'assistant laisse
    décoché alors qu'il est indispensable aux branchements.
    """
    from .projet_bet import _do_save
    plugin, iface = _plugin(), _iface()

    dossier = _chemin(dossier or os.path.join("~", "Documents", "CanaPlan"))
    os.makedirs(dossier, exist_ok=True)
    nom = nom or "CanaPlan"
    bet = os.path.join(dossier, nom + ".bet")

    infos = {}
    canvas = iface.mapCanvas()
    canvas.setDestinationCrs(QgsCoordinateReferenceSystem(L93))
    if adresse:
        infos = globals()["adresse"](adresse)
        canvas.setExtent(QgsRectangle(infos["x"] - demi_emprise, infos["y"] - demi_emprise,
                                      infos["x"] + demi_emprise, infos["y"] + demi_emprise))
    canvas.refresh()

    with sans_fenetre() as sf:
        plugin.run_fond_projet(fonds if fonds is not None else {})
        _couches("EU")
        _couches("EP")
        erreurs = _do_save(plugin, iface, os.path.join(dossier, nom + "_tmp.gpkg"),
                           bet, silencieux=True)
    return {"bet": bet, "adresse": infos, "erreurs": erreurs or [],
            "messages": sf.messages,
            "note": "Les fonds WFS (bâti, parcelles) se chargent en tâche de "
                    "fond : interroger etat() jusqu'à leur apparition."}


def enregistrer(chemin=None):
    """Enregistre le projet .bet sans barre de progression ni fenêtre."""
    from qgis.PyQt.QtCore import QSettings
    from .projet_bet import _do_save, _KEY_BET_PATH, _set_current
    plugin, iface = _plugin(), _iface()
    bet = _chemin(chemin or QSettings().value(_KEY_BET_PATH, ""))
    if not bet:
        raise RuntimeError("Aucun projet courant : passer `chemin`.")
    base = os.path.splitext(bet)[0]
    t = time.perf_counter()
    with sans_fenetre() as sf:
        erreurs = _do_save(plugin, iface, base + "_tmp.gpkg", bet, silencieux=True)
    return {"bet": bet, "secondes": round(time.perf_counter() - t, 2),
            "erreurs": erreurs or [], "messages": sf.messages}


def charger(chemin):
    """Charge un projet .bet, sans compte rendu modal."""
    from .projet_bet import load_projet
    with sans_fenetre() as sf:
        load_projet(_plugin(), _iface(), os.path.expanduser(chemin))
    return {"bet": chemin, "messages": sf.messages, "etat": etat()}


# ───────────────────────────────────────────────────────────────── dessin

def implanter_regards(axe, entraxe_max=50.0, tol_axe=0.5):
    """Abscisses des regards le long d'un axe, sans rien dessiner.

    Deux règles, dans cet ordre :

    1. **Un regard à chaque coude** dont l'omission écarterait la conduite de
       plus de `tol_axe` mètres de l'axe réel. Sans cela, la corde d'un long
       tronçon coupe les virages et la conduite sort de la chaussée.
    2. **Puis subdivision** de tout intervalle restant plus long que
       `entraxe_max`, en parts égales.

    `entraxe_max` est bien un maximum, pas un pas fixe : c'est la lecture
    métier de « un regard tous les 50 m ».
    """
    pts = axe.asPolyline()
    longueur = axe.length()
    cumul, pk_sommets = 0.0, [0.0]
    for i in range(1, len(pts)):
        cumul += pts[i - 1].distance(pts[i])
        pk_sommets.append(cumul)

    pk = [0.0, longueur]
    coudes = []
    while True:
        pire = (0.0, None, None)
        for a, b in zip(pk, pk[1:]):
            corde = QgsGeometry.fromPolylineXY(
                [axe.interpolate(a).asPoint(), axe.interpolate(b).asPoint()])
            for p, v in zip(pts, pk_sommets):
                if a + 0.1 < v < b - 0.1:
                    d = corde.distance(QgsGeometry.fromPointXY(p))
                    if d > pire[0]:
                        pire = (d, v, b)
        if pire[0] <= tol_axe:
            break
        pk.insert(pk.index(pire[2]), pire[1])
        coudes.append(pire[1])
        pk.sort()

    final = [pk[0]]
    for a, b in zip(pk, pk[1:]):
        n = max(1, math.ceil((b - a) / entraxe_max))
        final += [a + (b - a) * k / n for k in range(1, n + 1)]
    return {"pk": final, "coudes": sorted(coudes), "longueur": longueur,
            "entraxe_max": max(b - a for a, b in zip(final, final[1:]))}


def tracer_conduite(reseau, axe=None, points=None, entraxe_max=50.0,
                    tol_axe=0.5, vider=False, diametre=None, materiau=None):
    """Trace une conduite et ses regards en un appel.

    Passe par `DrawConduiteTool._add_point`, le point d'entrée d'un clic : le
    snapping, la topologie et les valeurs par défaut (diamètre, matériau) sont
    donc ceux du dessin manuel. La tolérance est imposée en mètres, le zoom
    n'entre pas en jeu.

    Fournir soit `axe` (géométrie ligne, échantillonnée par
    `implanter_regards`), soit `points` (liste de QgsPointXY déjà choisis).

    `diametre` et `materiau` s'appliquent aux conduites tracées par cet appel.
    Ils sont posés dans les valeurs par défaut du plugin le temps du tracé,
    puis rendus à leur état antérieur : pas besoin d'un `config()` préalable
    qui, lui, change le réglage global de la session.
    """
    from .draw_conduite_tool import DrawConduiteTool
    jeu = _couches(reseau)
    if vider:
        for role in ("conduite", "regard"):
            _vider(jeu[role])

    if axe is not None:
        plan = implanter_regards(axe, entraxe_max, tol_axe)
        points = [axe.interpolate(v).asPoint() for v in plan["pk"]]
    else:
        plan = {"pk": None, "coudes": [], "longueur": None}
    if not points or len(points) < 2:
        raise RuntimeError("Il faut au moins deux points.")

    _cadrer(points)
    with _defauts_temporaires("conduite_%s" % reseau.lower(),
                              diametre=diametre, materiau=materiau) as pose:
        with sans_fenetre() as sf:
            outil = DrawConduiteTool(_iface().mapCanvas(), reseau, jeu,
                                     tol_m=TOL_SNAP_M)
            for p in points:
                outil._add_point(p)

    longueurs = [f.geometry().length() for f in jeu["conduite"].getFeatures()]
    return {"regards": jeu["regard"].featureCount(),
            "troncons": len(longueurs),
            "lineaire": round(sum(longueurs), 2),
            "longueur_axe": round(plan["longueur"], 2) if plan["longueur"] else None,
            "entraxes": [round(v, 2) for v in longueurs],
            "coudes_ajoutes": [round(v, 1) for v in plan["coudes"]],
            "diametre": pose.get("diametre"), "materiau": pose.get("materiau"),
            "messages": sf.messages}


def creer_branchements(reseau, distance_max=10.0, couche_bati="PCI - Bati",
                       vider=False, diametre=None, materiau=None):
    """Un branchement par bâtiment situé à moins de `distance_max` du réseau.

    Chaque branchement part du point de piquage le plus proche sur la conduite
    et rejoint le point du bâti le plus proche, où un tabouret est posé. Passe
    par `DrawBranchementTool._finish` : tabouret, contrôle topologique, cote de
    piquage et attributs sont ceux du tracé manuel.

    `diametre` et `materiau`, comme pour `tracer_conduite`, ne valent que pour
    les branchements créés par cet appel.
    """
    from .draw_branchement_tool import DrawBranchementTool
    jeu = _couches(reseau)
    if vider:
        for role in ("branchement", "tabouret"):
            _vider(jeu[role])

    bati = None
    for c in QgsProject.instance().mapLayers().values():
        if c.name() == couche_bati:
            bati = c
            break
    if bati is None:
        raise RuntimeError("Couche « %s » absente : charger le bâti cadastral "
                           "(run_fond_projet) et attendre la fin du WFS." % couche_bati)

    reseau_geom = QgsGeometry.unaryUnion(
        [f.geometry() for f in jeu["conduite"].getFeatures()])
    if reseau_geom.isEmpty():
        raise RuntimeError("Aucune conduite %s : tracer le réseau d'abord." % reseau)

    cibles = []
    for f in bati.getFeatures(QgsFeatureRequest(
            reseau_geom.buffer(distance_max, 8).boundingBox())):
        g = f.geometry()
        if g.distance(reseau_geom) <= distance_max:
            cibles.append((f.id(), QgsGeometry(g)))

    faits, echecs = 0, []
    with _defauts_temporaires("branchement_%s" % reseau.lower(),
                              diametre=diametre, materiau=materiau) as pose,             sans_fenetre() as sf:
        for fid, g in cibles:
            seg = reseau_geom.shortestLine(g).asPolyline()
            pa, pb = QgsPointXY(seg[0]), QgsPointXY(seg[1])
            _cadrer([pa, pb], marge=5.0)
            outil = DrawBranchementTool(_iface().mapCanvas(), reseau, jeu,
                                        tol_m=TOL_SNAP_M)
            res = outil._snap_to_conduite(pa)
            if not res:
                echecs.append({"bati": fid, "cause": "piquage impossible"})
                continue
            outil.snapped_points = [res[0], pb]
            outil.points = [pa, pb]
            outil.id_conduite, outil.pk_debut = res[1], res[2]
            avant = jeu["branchement"].featureCount()
            outil._finish()
            if jeu["branchement"].featureCount() > avant:
                faits += 1
            else:
                echecs.append({"bati": fid, "cause": "refus topologique"})

    lb = [f.geometry().length() for f in jeu["branchement"].getFeatures()]
    return {"batis_retenus": len(cibles), "branchements": faits,
            "tabourets": jeu["tabouret"].featureCount(),
            "lineaire": round(sum(lb), 2),
            "longueur_min": round(min(lb), 2) if lb else None,
            "longueur_max": round(max(lb), 2) if lb else None,
            "diametre": pose.get("diametre"), "materiau": pose.get("materiau"),
            "echecs": echecs, "messages": sf.messages}


class _defauts_temporaires:
    """Pose diamètre et matériau par défaut le temps d'un tracé, puis les rend.

    Les outils de dessin lisent le diamètre et le matériau dans les réglages
    du plugin, pas dans leurs arguments : c'est la couture, et on ne la
    contourne pas. Mais un pilotage ne doit pas laisser la session modifiée
    derrière lui — d'où la restauration en sortie, y compris sur exception.
    """

    def __init__(self, cle, diametre=None, materiau=None):
        self.cle = cle
        self.pose = {}
        if diametre is not None:
            self.pose["diametre"] = diametre
        if materiau is not None:
            self.pose["materiau"] = materiau
        self.avant = None

    def __enter__(self):
        courant = config()["defauts"]
        if self.pose and self.cle in courant:
            self.avant = dict(courant[self.cle])
            config(defauts={self.cle: self.pose})
        return dict(courant.get(self.cle, {}), **self.pose)

    def __exit__(self, *exc):
        if self.avant is not None:
            config(defauts={self.cle: self.avant})
        return False


def _vider(couche):
    ids = [f.id() for f in couche.getFeatures()]
    if ids:
        couche.startEditing()
        couche.deleteFeatures(ids)
        couche.commitChanges()


# ───────────────────────────────────────────────────── numérotation et cotes

def renumeroter(reseau, prefixe_regard=None, prefixe_tabouret=None, depart=1,
                de=None, vers=None):
    """Renumérote regards et tabourets de l'amont vers l'aval.

    Appelle l'outil du plugin, donc hérite de sa numérotation en parcours de
    graphe et de l'ordonnancement des tabourets par tronçon puis par pk de
    piquage. `de` et `vers` sont des noms de regards ; à défaut, les deux
    extrémités du réseau sont prises (le nord comme amont).
    """
    from . import renommer_tool as rt
    jeu = _couches(reseau)
    regards = list(jeu["regard"].getFeatures())
    if len(regards) < 2:
        raise RuntimeError("Il faut au moins deux regards.")

    def _par_nom(nom):
        for f in regards:
            if f["nom"] == nom:
                return f
        raise RuntimeError("Regard « %s » introuvable." % nom)

    if de and vers:
        amont, aval = _par_nom(de), _par_nom(vers)
    else:
        tri = sorted(regards, key=lambda f: -f.geometry().asPoint().y())
        amont, aval = tri[0], tri[-1]

    defauts = rt._DEFAULTS.get(reseau, rt._DEFAULTS["EU"])

    class _Prefixes:
        def __init__(self, *_a, **_k):
            pass

        def exec(self):
            return QDialog.DialogCode.Accepted
        regard_prefix = property(lambda s: prefixe_regard or defauts["regard"])
        tabouret_prefix = property(lambda s: prefixe_tabouret or defauts["tabouret"])
        start_num_regard = property(lambda s: depart)
        start_num_tabouret = property(lambda s: depart)

    origine = rt._PrefixDialog
    rt._PrefixDialog = _Prefixes
    try:
        with sans_fenetre() as sf:
            rt.RenommerTool(_iface().mapCanvas(), _iface(), reseau,
                            jeu)._rename_path(amont, aval)
    finally:
        rt._PrefixDialog = origine

    return {"regards": [f["nom"] for f in sorted(
                jeu["regard"].getFeatures(), key=lambda f: f["nom"] or "")],
            "tabourets": sorted(f["nom"] for f in jeu["tabouret"].getFeatures()
                                if f["nom"]),
            "messages": sf.messages}


def caler_cotes(reseau, tn=None, ancrage=None, pente=None, tabourets=None):
    """Renseigne TN, profondeurs et fils d'eau.

    `tn`        : terrain naturel appliqué à tous les regards.
    `tabourets` : dict {'tn': .., 'profondeur': ..} appliqué à tous les tabourets.
    `ancrage`   : (nom_regard, profondeur) — le point dur d'où part le calcul.
    `pente`     : pente en %, **convention CanaPlan** — positive pour une
                  conduite descendante (FE aval = FE amont − pente% × L). Une
                  chute de 1 cm/m se saisit donc `1.0`, pas `-1.0` ; saisir une
                  valeur négative crée une contre-pente.

    Si l'ancrage est le point bas (cas courant : l'exutoire), le calcul remonte
    le réseau. Sinon il descend.

    Les branchements sont cotés dans la foulée : poser les fils d'eau des
    regards sans propager la cote de piquage laissait le réseau à moitié coté
    et faisait échouer tout contrôle en aval.
    """
    jeu = _couches(reseau)
    regard, tabouret, conduite = jeu["regard"], jeu["tabouret"], jeu["conduite"]

    def _ecrire(couche, feat_id, champ, valeur):
        idx = couche.fields().indexOf(champ)
        if idx < 0:
            return
        if not couche.isEditable():
            couche.startEditing()
        couche.changeAttributeValue(feat_id, idx, valeur)
        couche.commitChanges()

    if tn is not None:
        for f in regard.getFeatures():
            _ecrire(regard, f.id(), "tn", float(tn))
    if tabourets:
        for f in tabouret.getFeatures():
            t = float(tabourets.get("tn", tn or 0))
            p = float(tabourets["profondeur"])
            _ecrire(tabouret, f.id(), "tn", t)
            _ecrire(tabouret, f.id(), "profondeur", p)
            _ecrire(tabouret, f.id(), "fe_entree", round(t - p, 3))

    if not ancrage or pente is None:
        _coter_branchements(reseau)
        return _recap_cotes(jeu)

    nom_ancre, prof_ancre = ancrage
    ancre = next((f for f in regard.getFeatures() if f["nom"] == nom_ancre), None)
    if ancre is None:
        raise RuntimeError("Regard d'ancrage « %s » introuvable." % nom_ancre)
    tn_ancre = float(ancre["tn"] if ancre["tn"] is not None else (tn or 0))
    _ecrire(regard, ancre.id(), "profondeur", float(prof_ancre))
    _ecrire(regard, ancre.id(), "fe_radier", round(tn_ancre - float(prof_ancre), 3))

    # Chaîne des regards dans l'ordre du réseau, par proximité des extrémités.
    ordre = _chaine_regards(conduite, regard)
    noms = [f["nom"] for f in ordre]
    if nom_ancre not in noms:
        raise RuntimeError("L'ancrage n'est pas sur la chaîne principale.")
    i_ancre = noms.index(nom_ancre)

    def _longueur_entre(a, b):
        pa = a.geometry().asPoint()
        pb = b.geometry().asPoint()
        for f in conduite.getFeatures():
            l = f.geometry().asPolyline()
            if not l:
                continue
            e0, e1 = QgsPointXY(l[0]), QgsPointXY(l[-1])
            if (e0.distance(pa) < 0.5 and e1.distance(pb) < 0.5) or \
               (e0.distance(pb) < 0.5 and e1.distance(pa) < 0.5):
                return f.geometry().length(), f.id()
        return None, None

    # En remontant depuis l'ancrage : FE amont = FE aval + pente% × L
    for i in range(i_ancre - 1, -1, -1):
        aval, amont = ordre[i + 1], ordre[i]
        L, cid = _longueur_entre(amont, aval)
        if L is None:
            continue
        fe_aval = regard.getFeature(aval.id())["fe_radier"]
        fe = round(float(fe_aval) + pente / 100.0 * L, 3)
        tn_i = float(regard.getFeature(amont.id())["tn"] or tn or 0)
        _ecrire(regard, amont.id(), "fe_radier", fe)
        _ecrire(regard, amont.id(), "profondeur", round(tn_i - fe, 2))
        _ecrire(conduite, cid, "pente", round(pente, 3))
    # En descendant : FE aval = FE amont − pente% × L
    for i in range(i_ancre + 1, len(ordre)):
        amont, aval = ordre[i - 1], ordre[i]
        L, cid = _longueur_entre(amont, aval)
        if L is None:
            continue
        fe_amont = regard.getFeature(amont.id())["fe_radier"]
        fe = round(float(fe_amont) - pente / 100.0 * L, 3)
        tn_i = float(regard.getFeature(aval.id())["tn"] or tn or 0)
        _ecrire(regard, aval.id(), "fe_radier", fe)
        _ecrire(regard, aval.id(), "profondeur", round(tn_i - fe, 2))
        _ecrire(conduite, cid, "pente", round(pente, 3))

    _coter_branchements(reseau)
    return _recap_cotes(jeu)


def _coter_branchements(reseau):
    """Propage les cotes des ouvrages aux branchements (cote_piquage, pente).

    C'est `calc_pentes.recalc_pentes` qui fait le travail, exactement comme
    après une saisie manuelle dans le tableau.
    """
    try:
        recalculer_pentes(reseau)
    except Exception as err:            # une cote manquante ne doit rien bloquer
        return {"erreur": "%s: %s" % (type(err).__name__, err)}
    return None


def _chaine_regards(conduite, regard):
    """Regards ordonnés le long du réseau, en suivant les extrémités des tronçons."""
    pts = {f.id(): QgsPointXY(f.geometry().asPoint()) for f in regard.getFeatures()}
    voisins = {fid: set() for fid in pts}
    for f in conduite.getFeatures():
        l = f.geometry().asPolyline()
        if not l:
            continue
        e0, e1 = QgsPointXY(l[0]), QgsPointXY(l[-1])
        a = min(pts, key=lambda k: pts[k].distance(e0))
        b = min(pts, key=lambda k: pts[k].distance(e1))
        if a != b:
            voisins[a].add(b)
            voisins[b].add(a)
    extremites = [fid for fid, v in voisins.items() if len(v) == 1]
    depart = (max(extremites, key=lambda fid: pts[fid].y())
              if extremites else next(iter(pts)))
    ordre, vus, courant = [], set(), depart
    while courant is not None and courant not in vus:
        vus.add(courant)
        ordre.append(regard.getFeature(courant))
        suite = [v for v in voisins[courant] if v not in vus]
        courant = suite[0] if suite else None
    return ordre


def _recap_cotes(jeu):
    r = [{"nom": f["nom"], "tn": _nb(f["tn"]), "profondeur": _nb(f["profondeur"]),
          "fe_radier": _nb(f["fe_radier"])}
         for f in sorted(jeu["regard"].getFeatures(), key=lambda f: f["nom"] or "")]
    pentes = [_nb(f["pente"]) for f in jeu["conduite"].getFeatures()]
    # Un set de triplets dédoublonnait les tabourets : 17 ouvrages cotés à
    # l'identique ne rendaient qu'une ligne, illisible pour un appelant.
    tabourets = [{"nom": f["nom"], "tn": _nb(f["tn"]),
                  "profondeur": _nb(f["profondeur"]),
                  "fe_entree": _nb(f["fe_entree"])}
                 for f in sorted(jeu["tabouret"].getFeatures(),
                                 key=lambda f: f["nom"] or "")]
    return {"regards": r, "pentes": pentes, "tabourets": tabourets,
            "nb_tabourets": len(tabourets)}


def controler_branchements(reseau, pente_max=30.0):
    """Pente de chaque branchement, du tabouret vers le piquage.

    Une pente négative est une contre-pente (l'écoulement ne se fait pas) ;
    au-delà de `pente_max` il s'agit d'une chute, pas d'un branchement
    ordinaire — le plus souvent le signe de tabourets tous calés à la même
    profondeur au-dessus d'un collecteur qui, lui, s'enfonce.
    """
    jeu = _couches(reseau)
    anomalies, pentes, non_cotes = [], [], []
    for f in jeu["branchement"].getFeatures():
        # Lecture NULL-safe : un champ vide remonte un QVariant nul, que le
        # test `is None` laissait passer jusqu'au float() — l'API levait alors
        # un TypeError au lieu de rendre le compte rendu attendu.
        cp, L = _nb(f["cote_piquage"]), _nb(f["longueur"])
        fin = f.geometry().asPolyline()[-1]
        tab = min(jeu["tabouret"].getFeatures(),
                  key=lambda t: t.geometry().asPoint().distance(QgsPointXY(fin)),
                  default=None)
        fe = _nb(tab["fe_entree"]) if tab is not None else None
        if cp is None or not L or fe is None:
            manque = [nom for nom, v in (("cote_piquage", cp), ("longueur", L),
                                         ("fe_entree du tabouret", fe)) if not v]
            non_cotes.append({"id": f.id(), "manque": manque})
            anomalies.append({"id": f.id(), "cause": "cotes incomplètes",
                              "manque": manque})
            continue
        p = (fe - cp) / L * 100
        pentes.append(p)
        if p < 0:
            anomalies.append({"id": f.id(), "pente": round(p, 2), "cause": "contre-pente"})
        elif p > pente_max:
            anomalies.append({"id": f.id(), "pente": round(p, 2), "cause": "chute"})
    res = {"nombre": len(pentes),
           "pente_min": round(min(pentes), 2) if pentes else None,
           "pente_max": round(max(pentes), 2) if pentes else None,
           "non_cotes": non_cotes,
           "anomalies": anomalies}
    if non_cotes:
        res["conseil"] = ("Branchements non cotés : appeler caler_cotes(), qui "
                          "propage désormais les cotes de piquage, ou "
                          "recalculer_pentes() après une saisie manuelle.")
    return res


# ──────────────────────────────────────────────────────────────── export

_FORMATS = {"A4": (297, 210), "A3": (420, 297), "A2": (594, 420),
            "A1": (841, 594), "A0": (1189, 841)}


# Défaut de la fenêtre Exporter : gui/print_settings_widget.py, _DPI_PRESETS
# et _DPI_DEFAULT_IDX = 1. La façade doit rendre le même plan que l'IHM.
_DPI_DEFAUT = 150


def reglages_plan(echelle=200, format="A4", orientation="portrait",
                  dpi=_DPI_DEFAUT, cadrage="auto", titre=None,
                  plan_ensemble=True):
    """Construit le dictionnaire de réglages attendu par PrintTool.

    Écrit à la main plutôt que lu dans `ExportDialog` : instancier la fenêtre
    pour lire ses accesseurs laisse un widget vivant derrière soi.
    """
    w, h = _FORMATS[format]
    if orientation == "portrait":
        w, h = h, w
    return {"titre": titre or i18n.tr("pd_plan_reseau"), "format": format,
            "orientation": orientation, "w_mm": float(w), "h_mm": float(h),
            "echelle": echelle, "dpi": dpi, "cadrage_auto": cadrage == "auto",
            "plan_ensemble": plan_ensemble}


def _choix_export(dossier, pdf_complet=True, plan_pdf=True, plan_dxf=False):
    return {"plan_pdf": plan_pdf, "plan_dxf": plan_dxf,
            "profil_eu": False, "profil_ep": False, "profil_groupe": False,
            "profil_eu_format": "A3", "profil_ep_format": "A3",
            "profil_groupe_format": "A3", "profil_groupe_reseau": "EU",
            "cubature": False, "cubature_perimetre": None,
            "cubature_conduites": True, "cubature_branchements": True,
            "cubature_pdf": True, "cubature_xlsx": False, "cubature_csv": False,
            "coupe_eu": False, "coupe_ep": False, "coupe_papier": None,
            "coupe_fichier": "pdf", "tout_en_un": False,
            "pdf_complet": pdf_complet, "output_dir": dossier}


def exporter(dossier=None, pdf_complet=True, fonds_wms=True, **reglages):
    """Export synchrone du plan. Voir `exporter_async` pour les gros tirages.

    `fonds_wms=True` (defaut) garde l'ortho et l'OSM sur les planches : c'est
    ce qui est attendu d'un plan livre. Le passer a False accelere l'export
    mais produit un plan sans fond, bon pour un controle interne seulement.
    """
    return _executer_export(dossier, pdf_complet, fonds_wms, reglages)


def exporter_async(dossier=None, pdf_complet=True, fonds_wms=True, **reglages):
    """Lance l'export et rend immédiatement un ticket.

    L'appelant n'est plus bloqué : `tache(ticket)` renseigne l'avancement en
    quelques millisecondes. Le rendu des planches passe par des jobs QGIS
    parallèles qui pompent la boucle d'événements — les appels d'interrogation
    sont donc servis pendant l'export.

    **Sonder depuis des appels séparés.** L'export s'exécute sur le fil
    principal de QGIS. Une boucle d'attente écrite dans le même script
    (`while ...: time.sleep(2)`) garde ce fil et empêche la tâche d'avancer :
    l'état reste « en cours » aussi longtemps que dure la boucle. Un pilote
    distant doit rendre la main entre deux `tache()`.
    """
    ticket = uuid.uuid4().hex[:8]
    _taches[ticket] = {"etat": "en cours", "debut": time.time(),
                       "operation": "export", "resultat": None}

    def _go():
        try:
            _taches[ticket]["resultat"] = _executer_export(
                dossier, pdf_complet, fonds_wms, reglages)
            _taches[ticket]["etat"] = "fini"
        except Exception as e:
            _taches[ticket]["etat"] = "erreur"
            _taches[ticket]["resultat"] = {"erreur": "%s: %s" % (type(e).__name__, e)}
        _taches[ticket]["secondes"] = round(time.time() - _taches[ticket]["debut"], 1)

    QTimer.singleShot(0, _go)
    return {"ticket": ticket, "etat": "en cours",
            "sondage": "Interroger tache('%s') depuis des appels séparés : une "
                       "boucle d'attente bloquante dans le script appelant "
                       "empêche l'export de progresser." % ticket}


def tache(ticket):
    """État d'une tâche lancée en asynchrone."""
    t = _taches.get(ticket)
    if t is None:
        return {"ticket": ticket, "etat": "inconnu"}
    d = dict(t)
    d["ticket"] = ticket
    d.setdefault("secondes", round(time.time() - t["debut"], 1))
    d.pop("debut", None)
    return d


def _executer_export(dossier, pdf_complet, fonds_wms, reglages):
    import glob
    from qgis.PyQt.QtWidgets import QApplication
    plugin = _plugin()
    dossier = _chemin(dossier or os.path.join("~", "Documents", "CanaPlan"))
    settings = reglages_plan(**reglages)
    choix = _choix_export(dossier, pdf_complet=pdf_complet)

    if pdf_complet:
        from . import dependances
        if not dependances.tout_est_la(dependances.REQUIS_PDF):
            raise RuntimeError("pypdf absent : l'assemblage du PDF complet est "
                               "impossible. Installer via le menu Dépendances.")

    # L'ortho est ce qui permet de verifier l'implantation sur le terrain : un
    # plan livre sans elle n'est pas le meme document. `fonds_wms` vaut donc
    # True par defaut. Le passer a False fait gagner ~3 s par page A4 a 300 dpi,
    # mais ampute les planches de leur fond : reserve au tirage de controle.
    caches = []
    if not fonds_wms:
        racine = QgsProject.instance().layerTreeRoot()
        for c in QgsProject.instance().mapLayers().values():
            if c.dataProvider() and c.dataProvider().name() == "wms":
                noeud = racine.findLayer(c.id())
                if noeud is not None and noeud.isVisible():
                    noeud.setItemVisibilityChecked(False)
                    caches.append(noeud)

    avant = set(glob.glob(os.path.join(dossier, "*.pdf")))
    t0 = time.perf_counter()
    try:
        with sans_fenetre() as sf:
            plugin._export_tout_en_un(choix, settings,
                                      mode="pdf" if pdf_complet else "zip")
            for _ in range(200):
                QApplication.processEvents()
    finally:
        for noeud in caches:
            noeud.setItemVisibilityChecked(True)

    nouveaux = sorted(set(glob.glob(os.path.join(dossier, "*.pdf"))) - avant)
    return {"fichiers": nouveaux, "secondes": round(time.perf_counter() - t0, 1),
            "reglages": settings, "fonds_wms": fonds_wms,
            "messages": sf.messages}


# ─────────────────────────────────────────────────────────── enchaînement

def chantier(adresse, dossier=None, nom=None, rue=None, commune=None,
             reseau="EU", entraxe_max=50.0, tol_axe=0.5, distance_max=10.0,
             cotes=None, export=None):
    """Enchaîne la séquence complète : projet, réseau, branchements, cotes, PDF.

    Rend le compte rendu de chaque étape. L'export part en asynchrone : le
    ticket est dans `resultat['export']['ticket']`.
    """
    cr = {}
    cr["projet"] = nouveau_projet(adresse=adresse, dossier=dossier, nom=nom)
    cr["axe"] = "OSM"
    axe = axe_de_rue(rue or adresse.split(",")[0], commune)
    cr["conduite"] = tracer_conduite(reseau, axe=axe, entraxe_max=entraxe_max,
                                     tol_axe=tol_axe, vider=True)
    cr["branchements"] = creer_branchements(reseau, distance_max=distance_max,
                                            vider=True)
    cr["numerotation"] = renumeroter(reseau)
    if cotes:
        cr["cotes"] = caler_cotes(reseau, **cotes)
        cr["controle"] = controler_branchements(reseau)
    cr["enregistrement"] = enregistrer()
    if export is not None:
        cr["export"] = exporter_async(dossier=dossier, **export)
    return cr


# ═════════════════════════════════════════════════════════════════════════
#  FONDS DE PLAN
# ═════════════════════════════════════════════════════════════════════════

#: Clés acceptées par `fonds()`.
FONDS = ("ban", "noms_voie", "pci_bati", "pci_parcelles", "osm", "ortho")


def fonds(*demandes, **bascules):
    """Charge des fonds de plan. Sans argument, charge tout.

    Clés : 'osm', 'ortho', 'ban', 'noms_voie', 'pci_bati', 'pci_parcelles'.
    Les quatre derniers passent par un WFS **asynchrone** : ils n'existent pas
    au retour de cet appel. Enchaîner sur `attendre_fonds()`.

        api.fonds("pci_bati", "pci_parcelles")
        api.fonds(ortho=False, osm=True)
    """
    options = {c: False for c in FONDS} if demandes else {}
    for d in demandes:
        if d not in FONDS:
            raise RuntimeError("Fond inconnu : %s (attendus : %s)"
                               % (d, ", ".join(FONDS)))
        options[d] = True
    options.update(bascules)
    with sans_fenetre() as sf:
        _plugin().run_fond_projet(options)
    return {"demandes": options, "messages": sf.messages,
            "note": "WFS asynchrone : voir attendre_fonds()."}


def attendre_fonds(noms=("PCI - Bati",), delai=90.0, pas=0.5):
    """Bloque jusqu'à l'apparition des couches WFS, ou expiration du délai.

    Le chargement des fonds part dans une `QgsTask` : sans cette attente, un
    script enchaîne sur des couches qui n'existent pas encore. C'est le piège
    numéro un du pilotage de CanaPlan.
    """
    from qgis.PyQt.QtWidgets import QApplication
    attendus = set(noms)
    t0 = time.time()
    while time.time() - t0 < delai:
        presents = {c.name() for c in QgsProject.instance().mapLayers().values()}
        if attendus <= presents:
            return {"prets": sorted(attendus),
                    "secondes": round(time.time() - t0, 1)}
        QApplication.processEvents()
        time.sleep(pas)
    presents = {c.name() for c in QgsProject.instance().mapLayers().values()}
    return {"prets": sorted(attendus & presents),
            "manquants": sorted(attendus - presents),
            "secondes": round(time.time() - t0, 1), "expire": True}


# ═════════════════════════════════════════════════════════════════════════
#  CONFIGURATION, PENTES, STYLES, ÉTIQUETTES
# ═════════════════════════════════════════════════════════════════════════

def config(defauts=None, cubature=None):
    """Lit ou modifie les valeurs par défaut du plugin.

    Sans argument, retourne la configuration courante : diamètres et matériaux
    par défaut (conduites et branchements, EU et EP) et paramètres de cubature
    (épaisseur du lit de pose, largeurs de tranchée).

        api.config()
        api.config(defauts={"conduite_eu": {"diametre": 315, "materiau": "PVC"}})
    """
    from qgis.PyQt.QtCore import QSettings
    from ..config_dialog import get_default_params, get_cubature_config, SETTINGS_KEY
    s = QSettings()
    if defauts:
        courant = get_default_params()
        for cle, vals in defauts.items():
            if cle not in courant:
                raise RuntimeError("Clé inconnue : %s (attendues : %s)"
                                   % (cle, ", ".join(courant)))
            for champ, val in vals.items():
                s.setValue("%s/%s_%s" % (SETTINGS_KEY, cle, champ), val)
    if cubature:
        for champ, val in cubature.items():
            s.setValue("%s/%s" % (SETTINGS_KEY, champ), val)
    return {"defauts": get_default_params(), "cubature": get_cubature_config()}


def recalculer_pentes(reseau="EU", tolerance=0.05):
    """Recalcule les pentes des conduites depuis les fils d'eau des ouvrages.

    À appeler après toute modification manuelle des cotes hors `caler_cotes`.
    """
    from .calc_pentes import recalc_pentes
    jeu = _couches(reseau)
    recalc_pentes(jeu["conduite"], jeu["regard"], tol=tolerance,
                  branchement_layer=jeu["branchement"],
                  tabouret_layer=jeu["tabouret"])
    return {"pentes": [f["pente"] for f in jeu["conduite"].getFeatures()]}


def styles(reseau="EU"):
    """Réapplique la symbologie CanaPlan (EU rouge, EP bleu)."""
    plugin = _plugin()
    jeu = _couches(reseau)
    for role, couche in jeu.items():
        plugin._apply_style(couche, role, reseau)
    _iface().mapCanvas().refreshAllLayers()
    return {"reseau": reseau, "couches": sorted(jeu)}


#: Unités de taille d'étiquette acceptées.
#:
#: 'mm' est la seule qui réponde à la question qu'on se pose vraiment — quelle
#: hauteur de texte sur la feuille imprimée ? Le moteur d'étiquettes de
#: CanaPlan travaille en unités carte, parce que tout le reste de sa mise en
#: page en dépend (fonds d'étiquette, lignes de rappel, décalages) ; l'API fait
#: donc la conversion à partir de l'échelle du plan :
#:
#:     taille_carte = taille_mm / 1000 × echelle
#:
#: soit, au 1/200, 2,5 mm de papier pour 0,50 m au sol. Sans cette conversion,
#: une taille lue comme « 2 » en unités carte donne 2 m de haut, c'est-à-dire
#: 10 mm de texte sur la feuille : illisible de trop gros.
_UNITES = {"mm": "mm_papier", "papier": "mm_papier", "mm_papier": "mm_papier",
           "points": "points", "pt": "points",
           "map": "map_units", "map_units": "map_units", "carte": "map_units",
           "m": "map_units", "metres": "map_units", "mètres": "map_units"}


def _prefs_visibilite(reseau, visibilite):
    """Normalise `visibilite` vers la forme {reseau: {role: bool}}.

    Accepte un booléen (tous les rôles du réseau visé), {role: bool} pour ce
    réseau, ou la forme complète {reseau: {role: bool}} qu'attend l'IHM.
    """
    from ..gui.etiquettes import get_label_display_prefs
    prefs = get_label_display_prefs(_plugin())
    if isinstance(visibilite, bool):
        prefs[reseau] = {role: visibilite for role in prefs.get(reseau, {})}
    elif set(visibilite) <= {"EU", "EP"}:
        for r, v in visibilite.items():
            prefs.setdefault(r, {}).update(v)
    else:
        prefs.setdefault(reseau, {}).update(visibilite)
    return prefs


def etiquettes(reseau="EU", roles=None, taille=None, unite=None,
               champs=None, visibilite=None, forcer_toutes=None,
               echelle_min=None, echelle=None):
    """Applique le moteur d'étiquettes de CanaPlan.

    `taille` + `unite` : 'mm' — hauteur du texte **sur la feuille imprimée**,
        convertie en unités carte d'après `echelle` (2,5 mm au 1/200 font
        0,50 m au sol) ; 'map' — unités carte directes ; 'points' — points
        typographiques, taille fixe à l'écran. S'applique à tout le projet.
    `echelle` : dénominateur de l'échelle du plan (200 pour un 1/200), exigé
        par 'mm'. À ne pas confondre avec `echelle_min`, seuil de dézoom
        au-delà duquel les étiquettes disparaissent.
    `champs` : dict {role: [champs affichés]}.
    `visibilite` : booléen pour tous les rôles du réseau, {role: bool}, ou la
        forme complète {reseau: {role: bool}}.
    `forcer_toutes` : True affiche les étiquettes malgré les collisions.

    Rend l'état obtenu — rôles traités, étiquettes actives par rôle, taille,
    forçage — et non l'écho des arguments reçus : un appelant qui n'a pas
    l'écran doit pouvoir rendre compte à partir du seul retour.
    """
    from ..gui.etiquettes import (apply_etiquettes, apply_label_size_all,
                                  apply_label_fields, apply_label_display_prefs,
                                  set_force_all_labels, get_force_all_labels,
                                  get_label_display_prefs)
    plugin = _plugin()
    jeu = _couches(reseau)
    roles = tuple(roles or ("conduite", "branchement", "regard", "tabouret"))
    inconnus = [r for r in roles if r not in jeu]
    if inconnus:
        raise RuntimeError("Rôle inconnu : %s (attendus : %s)"
                           % (", ".join(inconnus), ", ".join(sorted(jeu))))
    for role in roles:
        apply_etiquettes(jeu[role], role, reseau)
    mode, taille_carte = None, None
    if taille is not None:
        mode = _UNITES.get(str(unite or "mm").lower())
        if mode is None:
            raise RuntimeError("Unité inconnue : %s (attendues : %s)"
                               % (unite, ", ".join(sorted(_UNITES))))
        taille_carte = float(taille)
        if mode == "mm_papier":
            if not echelle:
                raise RuntimeError(
                    "Une taille en millimètres de papier exige l'échelle du "
                    "plan : etiquettes(taille=2.5, unite='mm', echelle=200).")
            taille_carte = float(taille) * float(echelle) / 1000.0
            mode = "map_units"
        apply_label_size_all(plugin, mode, taille_carte, echelle_min)
    if champs:
        apply_label_fields(plugin, champs)
    if visibilite is not None:
        apply_label_display_prefs(plugin, _prefs_visibilite(reseau, visibilite))
    if forcer_toutes is not None:
        set_force_all_labels(bool(forcer_toutes), _iface().mapCanvas(), plugin)
    _iface().mapCanvas().refreshAllLayers()
    return {"reseau": reseau, "roles": list(roles),
            "actives": {role: couche.labelsEnabled()
                        for role, couche in sorted(jeu.items())},
            "visibilite": get_label_display_prefs(plugin).get(reseau, {}),
            "taille": taille, "unite": mode,
            "taille_carte_m": taille_carte,
            "taille_mm_papier": (round(taille_carte * 1000.0 / float(echelle), 2)
                                 if taille_carte is not None and echelle else None),
            "echelle": echelle, "echelle_min": echelle_min,
            "champs": champs or None,
            "forcer_toutes": get_force_all_labels()}


# ═════════════════════════════════════════════════════════════════════════
#  SAISIE ATTRIBUTAIRE ET ÉDITION D'OUVRAGES
# ═════════════════════════════════════════════════════════════════════════

def saisir(reseau, role, valeurs, ou=None):
    """Écrit des attributs en masse, sans ouvrir le tableau de saisie.

    `valeurs` : dict {champ: valeur}. `ou` : filtre callable(feature) -> bool.

        api.saisir("EU", "regard", {"tn": 100})
        api.saisir("EU", "conduite", {"materiau": "PVC"},
                   ou=lambda f: f["diametre"] == 160)

    Les champs dérivés ne sont pas recalculés : enchaîner sur `caler_cotes()`
    ou `recalculer_pentes()` selon le besoin.
    """
    couche = _couches(reseau)[role]
    champs = couche.fields()
    for c in valeurs:
        if champs.indexOf(c) < 0:
            raise RuntimeError("Champ « %s » absent de %s (présents : %s)"
                               % (c, couche.name(),
                                  ", ".join(f.name() for f in champs)))
    touchees = 0
    couche.startEditing()
    for f in couche.getFeatures():
        if ou is not None and not ou(f):
            continue
        for c, v in valeurs.items():
            couche.changeAttributeValue(f.id(), champs.indexOf(c), v)
        touchees += 1
    couche.commitChanges()
    return {"couche": couche.name(), "entites_modifiees": touchees,
            "valeurs": valeurs}


def lire(reseau, role, champs=None):
    """Retourne les entités d'un rôle sous forme de liste de dicts."""
    couche = _couches(reseau)[role]
    noms = champs or [f.name() for f in couche.fields()]
    return [dict({"__id": f.id()}, **{c: f[c] for c in noms})
            for f in couche.getFeatures()]


def inserer_regard(point, reseau=None):
    """Insère un regard sur une conduite existante et la coupe en deux.

    Délègue à `InsertRegardTool` : le regard est posé sur la projection du
    point sur la conduite la plus proche, et le tronçon est scindé avec report
    des attributs et recalcul des longueurs.
    """
    from qgis.core import QgsFeature
    from .insert_regard_tool import InsertRegardTool
    _cadrer([point], marge=5.0)
    outil = InsertRegardTool(_iface().mapCanvas(), _couches("EU"), _couches("EP"))
    if reseau:
        outil.couches = {reseau: _couches(reseau)}
    with sans_fenetre() as sf:
        res = outil._find_closest_conduite(point)
        if not res:
            raise RuntimeError("Aucune conduite à proximité du point.")
        feat, proj, res_reseau = res
        jeu = _couches(res_reseau)
        rl = jeu["regard"]
        rl.startEditing()
        nf = QgsFeature(rl.fields())
        nf.setGeometry(QgsGeometry.fromPointXY(proj))
        rl.addFeature(nf)
        rl.commitChanges()
        outil._split_conduite(jeu["conduite"], feat, proj)
    return {"reseau": res_reseau, "regards": jeu["regard"].featureCount(),
            "troncons": jeu["conduite"].featureCount(), "messages": sf.messages}


def supprimer(reseau, role, ids):
    """Supprime des entités par identifiant.

    Suppression brute, volontairement : le `DeleteTool` du plugin gère en plus
    un survol, un lasso et l'effacement d'étiquettes, logique attachée au
    pointeur et non reproduite ici. Contrôler la cohérence après coup
    (`recalculer_pentes`, `verifier`).
    """
    ids = list(ids)
    couche = _couches(reseau)[role]
    couche.startEditing()
    couche.deleteFeatures(ids)
    couche.commitChanges()
    return {"couche": couche.name(), "supprimees": len(ids),
            "restantes": couche.featureCount()}


def vider(reseau, roles=("conduite", "branchement", "regard", "tabouret")):
    """Vide les couches métier d'un réseau. Irréversible sans rechargement."""
    jeu = _couches(reseau)
    return {role: (_vider(jeu[role]), jeu[role].featureCount())[1]
            for role in roles}


# ═════════════════════════════════════════════════════════════════════════
#  PROFILS, CUBATURE, COUPES
# ═════════════════════════════════════════════════════════════════════════

def profil(reseau="EU", format="A3", dossier=None):
    """Exporte le profil en long d'un réseau en PDF.

    Le profil suit la chaîne principale (plus long chemin entre deux
    extrémités) et porte les branchements piqués, à leur abscisse.
    """
    from .profil_batch import export_profils_eu_ep
    dossier = _chemin(dossier or os.path.join("~", "Documents", "CanaPlan"))
    os.makedirs(dossier, exist_ok=True)
    with sans_fenetre() as sf:
        fichiers = export_profils_eu_ep(_couches(reseau), reseau, format, dossier)
    return {"fichiers": fichiers, "format": format, "messages": sf.messages}


def profil_groupe(reference="EU", format="A3", dossier=None):
    """Profil en long combiné EU + EP, calé sur l'axe du réseau `reference`."""
    from .profil_batch import export_profils_groupe
    dossier = _chemin(dossier or os.path.join("~", "Documents", "CanaPlan"))
    os.makedirs(dossier, exist_ok=True)
    with sans_fenetre() as sf:
        fichiers = export_profils_groupe(_couches("EU"), _couches("EP"),
                                         format, dossier, reference)
    return {"fichiers": fichiers, "reference": reference, "messages": sf.messages}


def cubature(reseau="EU", reglages=None):
    """Calcule la cubature (déblais, lit de pose, remblai) du réseau.

    Retourne le détail par ouvrage et les totaux. `reglages` surcharge la
    configuration du plugin (épaisseur du lit de pose, largeurs de tranchée).
    """
    from .calc_cubature import calculer_cubature_reseau
    from ..config_dialog import get_cubature_config
    cfg = dict(get_cubature_config())
    cfg.update(reglages or {})
    lignes = calculer_cubature_reseau(_couches(reseau), cfg, reseau)
    totaux = {}
    for l in lignes:
        for k, v in l.items():
            if isinstance(v, (int, float)):
                totaux[k] = round(totaux.get(k, 0) + v, 3)
    return {"reseau": reseau, "lignes": lignes, "totaux": totaux,
            "config": cfg, "nombre": len(lignes)}


def coupe_type(reseau="EU", dossier=None, reglages=None):
    """Exporte la coupe type de tranchée du réseau (PDF)."""
    from .coupe_type import exporter_coupe_type, stats_reseau
    from ..config_dialog import get_cubature_config
    cfg = dict(get_cubature_config())
    cfg.update(reglages or {})
    dossier = _chemin(dossier or os.path.join("~", "Documents", "CanaPlan"))
    os.makedirs(dossier, exist_ok=True)
    jeu = _couches(reseau)
    with sans_fenetre() as sf:
        chemin = exporter_coupe_type(jeu, cfg, reseau, dossier)
    return {"fichier": chemin, "stats": stats_reseau(jeu, reseau, cfg),
            "messages": sf.messages}


# ═════════════════════════════════════════════════════════════════════════
#  EXPORTS ET IMPORTS MÉTIER
# ═════════════════════════════════════════════════════════════════════════

def exporter_dxf(dossier=None, emprise=None):
    """Export DXF 2018 de l'emprise visible (ou de `emprise`), échelle 1/200.

    Les étiquettes ne survivent qu'en DXF 2018 ; en 2013 elles sont perdues.
    Nécessite ezdxf (voir `dependances_manquantes()`).
    """
    import glob
    canvas = _iface().mapCanvas()
    if emprise is not None:
        canvas.setExtent(emprise)
        canvas.refresh()
    dossier = _chemin(dossier or os.path.join("~", "Documents", "CanaPlan"))
    os.makedirs(dossier, exist_ok=True)
    avant = set(glob.glob(os.path.join(dossier, "*.dxf")))
    with sans_fenetre() as sf:
        _plugin()._export_dxf_direct(out_dir=dossier)
    nouveaux = sorted(set(glob.glob(os.path.join(dossier, "*.dxf"))) - avant)
    return {"fichiers": nouveaux, "messages": sf.messages}


def controle_stareau():
    """Contrôle de conformité StaR-Eau (CNIG/ASTEE) avant export.

    Retourne les non-conformités : champs obligatoires vides, ouvrages
    orphelins, géométries douteuses. À passer avant `exporter_stareau`.
    """
    from .stareau_export import check_conformity, source_layers
    return {"couches_sources": [c.name() for c in source_layers() if c],
            "controle": check_conformity()}


def exporter_stareau(parametres, chemin):
    """Écrit le GeoPackage StaR-Eau (CNIG/ASTEE).

    `parametres` : dict attendu par `stareau_export.export_stareau` (maître
    d'ouvrage, commune, date de relevé, précision…). Voir
    `gui/stareau_export_dialog.params()` pour la liste exacte.
    """
    from .stareau_export import export_stareau
    chemin = os.path.expanduser(chemin)
    with sans_fenetre() as sf:
        path, stats = export_stareau(parametres, chemin)
    return {"fichier": path, "stats": stats, "messages": sf.messages}


def importer_star_dt(fichiers, dossier_sortie, types=None):
    """Importe des fichiers d'échange Star-DT vers des couches SIG."""
    from .star_dt_import import import_star_dt
    dossier_sortie = os.path.expanduser(dossier_sortie)
    os.makedirs(dossier_sortie, exist_ok=True)
    with sans_fenetre() as sf:
        crees = import_star_dt([os.path.expanduser(f) for f in fichiers],
                               dossier_sortie, selected_types=types)
    return {"couches_creees": crees, "fichiers_lus": len(fichiers),
            "messages": sf.messages}


def importer_dxf(fichier, sortie=None, **options):
    """Convertit un DXF/DWG en GeoPackage via le fournisseur intégré.

    Les étiquettes ne sont récupérées que depuis un DXF 2018. Nécessite ezdxf.
    """
    import processing
    fichier = os.path.expanduser(fichier)
    sortie = os.path.expanduser(sortie or os.path.splitext(fichier)[0] + ".gpkg")
    params = {"INPUT": fichier, "OUTPUT": sortie}
    params.update(options)
    with sans_fenetre() as sf:
        res = processing.run("cad_to_gis:convert", params)
    return {"sortie": res.get("OUTPUT", sortie), "messages": sf.messages}


# ═════════════════════════════════════════════════════════════════════════
#  PROJETS ET DIAGNOSTIC
# ═════════════════════════════════════════════════════════════════════════

def projets_recents():
    """Les derniers projets .bet ouverts, du plus récent au plus ancien."""
    from .projet_bet import recent_projects, current_bet_name, project_dir
    return {"recents": recent_projects(), "courant": current_bet_name(),
            "dossier": project_dir()}


def enregistrer_sous(chemin):
    """Enregistre le projet sous un nouveau nom, sans boîte de dialogue."""
    from .projet_bet import _do_save
    chemin = os.path.expanduser(chemin)
    if not chemin.endswith(".bet"):
        chemin += ".bet"
    base = os.path.splitext(chemin)[0]
    os.makedirs(os.path.dirname(chemin) or ".", exist_ok=True)
    t = time.perf_counter()
    with sans_fenetre() as sf:
        erreurs = _do_save(_plugin(), _iface(), base + "_tmp.gpkg", chemin,
                           silencieux=True)
    return {"bet": chemin, "secondes": round(time.perf_counter() - t, 2),
            "erreurs": erreurs or [], "messages": sf.messages}


def dependances_manquantes():
    """Bibliothèques tierces absentes, par fonction.

    'dxf' : export DXF et conversion DXF/DWG. 'pdf' : assemblage du PDF
    complet. Tout le reste du plugin fonctionne sans elles.
    """
    from . import dependances
    return {"dxf": dependances.manquants(dependances.REQUIS),
            "pdf": dependances.manquants(dependances.REQUIS_PDF)}


def verifier(reseau="EU"):
    """Contrôle de cohérence avant livraison : renseignement, pentes, topologie.

    Rend, par rôle, le nombre d'entités et les champs restés vides ; la liste
    des conduites en contre-pente ; et le contrôle des branchements.
    """
    jeu = _couches(reseau)
    manques = {}
    for role, champs in (("regard", ("nom", "tn", "profondeur", "fe_radier")),
                         ("tabouret", ("nom", "tn", "profondeur", "fe_entree")),
                         ("conduite", ("diametre", "materiau", "pente")),
                         ("branchement", ("diametre", "materiau", "cote_piquage"))):
        couche = jeu[role]
        vides = {c: 0 for c in champs if couche.fields().indexOf(c) >= 0}
        for f in couche.getFeatures():
            for c in vides:
                v = f[c]
                if v is None or str(v) == "NULL" or v == "":
                    vides[c] += 1
        manques[role] = {"entites": couche.featureCount(),
                         "champs_vides": {k: v for k, v in vides.items() if v}}
    contre_pentes = [f.id() for f in jeu["conduite"].getFeatures()
                     if f["pente"] is not None and str(f["pente"]) != "NULL"
                     and float(f["pente"]) < 0]
    return {"reseau": reseau, "renseignement": manques,
            "conduites_en_contre_pente": contre_pentes,
            "branchements": controler_branchements(reseau)}


#: Sommaire de l'API, par domaine. Sert à `aide()` et à la documentation.
# ═════════════════════════════════════════════════════════════════════════
#  SUITES ET RECETTES
# ═════════════════════════════════════════════════════════════════════════
#
# Ce que coûte un pilotage distant, ce n'est pas le calcul — les verbes de ce
# module rendent la main en moins d'une seconde — c'est l'aller-retour : le
# pilote envoie un appel, attend, réfléchit, en envoie un autre. Sur une
# séance mesurée, 87 % du temps était de la latence d'échange, 13 % du travail
# réel. La bonne réponse n'est donc pas d'accélérer les fonctions, mais d'en
# passer plusieurs d'un coup.
#
# `suite()` exécute une liste d'appels en un seul échange. `recette()` est la
# même chose, nommée, paramétrée et rangée dans un fichier : la procédure de
# travail écrite une fois, rejouée à volonté.
#
# Deux substitutions suffisent à tout enchaîner :
#
#   "$param"        la valeur passée à l'appel, ou le défaut de la recette ;
#   "@etape.chemin" le résultat d'une étape précédente.
#
# La seconde règle un problème que rien d'autre ne règle : l'axe de rue est un
# `QgsGeometry`, qui ne franchit aucun protocole. Dans une suite il ne sort
# jamais de QGIS — l'étape qui le fabrique le nomme, l'étape suivante le
# reprend par son nom.


def _appel_public(nom):
    """La fonction publique `nom`, ou une erreur si elle n'existe pas.

    Une suite ne peut appeler que les verbes documentés par `aide()` : pas
    d'accès arbitraire au module depuis un fichier de recette.
    """
    permis = {n for noms in DOMAINES.values() for n in noms}
    if nom not in permis:
        raise RuntimeError("Appel inconnu : %s (voir aide())" % nom)
    fonction = globals().get(nom)
    if not callable(fonction):
        raise RuntimeError("Appel indisponible : %s" % nom)
    return fonction


def _chemin_valeur(racine, chemin):
    """Descend `chemin` ('regards[-1].nom') dans un résultat déjà obtenu."""
    valeur = racine
    for morceau in chemin.split("."):
        if not morceau:
            continue
        nom, _, reste = morceau.partition("[")
        if nom:
            if isinstance(valeur, dict):
                if nom not in valeur:
                    raise RuntimeError("Clé absente du résultat : %s" % nom)
                valeur = valeur[nom]
            else:
                valeur = getattr(valeur, nom)
        while reste:
            index, _, reste = reste.partition("]")
            valeur = valeur[int(index)]
            reste = reste.lstrip("[")
    return valeur


def _resoudre(valeur, parametres, nommes):
    """Remplace les "$param" et "@etape.chemin" partout dans `valeur`."""
    if isinstance(valeur, dict):
        return {k: _resoudre(v, parametres, nommes) for k, v in valeur.items()}
    if isinstance(valeur, (list, tuple)):
        return [_resoudre(v, parametres, nommes) for v in valeur]
    if not isinstance(valeur, str) or len(valeur) < 2:
        return valeur
    if valeur[0] == "$":
        cle = valeur[1:]
        if cle not in parametres:
            raise RuntimeError("Paramètre inconnu : %s (connus : %s)"
                               % (cle, ", ".join(sorted(parametres)) or "aucun"))
        return parametres[cle]
    if valeur[0] == "@":
        nom, _, chemin = valeur[1:].partition(".")
        if nom not in nommes:
            raise RuntimeError("Étape non nommée ou pas encore jouée : %s "
                               "(nommées : %s)"
                               % (nom, ", ".join(nommes) or "aucune"))
        return _chemin_valeur(nommes[nom], chemin)
    return valeur


def _serialisable(valeur, rang=0):
    """Rend `valeur` transmissible : ce qui ne l'est pas devient sa description.

    Un résultat d'étape peut contenir un `QgsGeometry` — utile à l'étape
    suivante, intransmissible au pilote. Le compte rendu en garde une trace
    lisible plutôt que d'échouer à la sérialisation.
    """
    if valeur is None or isinstance(valeur, (bool, int, float, str)):
        return valeur
    if rang > 6:
        return "…"
    if isinstance(valeur, dict):
        return {str(k): _serialisable(v, rang + 1) for k, v in valeur.items()}
    if isinstance(valeur, (list, tuple, set)):
        return [_serialisable(v, rang + 1) for v in valeur]
    if isinstance(valeur, QgsGeometry):
        return "<QgsGeometry %s, %.2f m>" % (
            "vide" if valeur.isEmpty() else valeur.wkbType(), valeur.length())
    return repr(valeur)[:200]


def suite(etapes, parametres=None, arret_si_erreur=True):
    """Exécute une liste d'appels de l'API en un seul échange.

    Chaque étape est un dict :

        {"appel": "tracer_conduite",        # verbe public, cf. aide()
         "args": {"reseau": "EU", "axe": "@axe"},
         "nomme": "conduite",               # pour s'y référer plus loin
         "si": "$avec_export",              # étape sautée si la valeur est fausse
         "ignorer_erreur": false}

    Rend le compte rendu de chaque étape — appel résolu, durée, résultat — et
    l'état final. Sans `arret_si_erreur`, la suite continue et l'erreur reste
    consignée dans l'étape fautive.
    """
    parametres = dict(parametres or {})
    nommes, comptes = {}, []
    t_total = time.perf_counter()
    for rang, etape in enumerate(etapes, 1):
        nom = etape.get("appel")
        cr = {"rang": rang, "appel": nom}
        try:
            condition = etape.get("si")
            if condition is not None and not _resoudre(condition, parametres, nommes):
                cr["etat"] = "sautee"
                comptes.append(cr)
                continue
            fonction = _appel_public(nom)
            args = _resoudre(etape.get("args") or {}, parametres, nommes)
            cr["args"] = _serialisable(args)
            t0 = time.perf_counter()
            resultat = fonction(**args)
            cr["secondes"] = round(time.perf_counter() - t0, 2)
            cr["etat"] = "ok"
            cr["resultat"] = _serialisable(resultat)
            if etape.get("nomme"):
                nommes[etape["nomme"]] = resultat
        except Exception as err:
            cr["etat"] = "erreur"
            cr["erreur"] = "%s: %s" % (type(err).__name__, err)
            comptes.append(cr)
            if arret_si_erreur and not etape.get("ignorer_erreur"):
                return {"etapes": comptes, "etat": "erreur",
                        "secondes": round(time.perf_counter() - t_total, 2),
                        "echouee": rang}
            continue
        comptes.append(cr)
    return {"etapes": comptes, "etat": "ok",
            "secondes": round(time.perf_counter() - t_total, 2),
            "nommees": sorted(nommes)}


def _dossiers_recettes():
    """Les deux dossiers de recettes : celles livrées, puis celles de l'agent."""
    from qgis.core import QgsApplication
    livrees = os.path.join(os.path.dirname(__file__), "recettes")
    perso = os.path.join(QgsApplication.qgisSettingsDirPath(), "CanaPlan",
                         "recettes")
    return [("livree", livrees), ("perso", perso)]


def _charger_recettes():
    fiches = {}
    for origine, dossier in _dossiers_recettes():
        if not os.path.isdir(dossier):
            continue
        for fichier in sorted(os.listdir(dossier)):
            if not fichier.endswith(".json"):
                continue
            chemin = os.path.join(dossier, fichier)
            try:
                with open(chemin, encoding="utf-8") as flux:
                    fiche = json.load(flux)
            except Exception as err:
                fiches[os.path.splitext(fichier)[0]] = {
                    "nom": os.path.splitext(fichier)[0],
                    "erreur": "%s: %s" % (type(err).__name__, err),
                    "origine": origine, "fichier": chemin}
                continue
            fiche.setdefault("nom", os.path.splitext(fichier)[0])
            fiche["origine"] = origine       # une perso masque celle livrée
            fiche["fichier"] = chemin
            fiches[fiche["nom"]] = fiche
    return fiches


def recettes(nom=None):
    """Les procédures enregistrées : nom, résumé, paramètres, nombre d'étapes.

    Une recette est une suite d'appels rangée dans un fichier JSON, avec ses
    paramètres et leurs valeurs par défaut. Passer `nom` rend la fiche
    complète, étapes comprises.
    """
    fiches = _charger_recettes()
    if nom is not None:
        if nom not in fiches:
            raise RuntimeError("Recette inconnue : %s (connues : %s)"
                               % (nom, ", ".join(sorted(fiches)) or "aucune"))
        return fiches[nom]
    return [{"nom": f["nom"], "resume": f.get("resume", ""),
             "parametres": f.get("parametres", {}),
             "etapes": len(f.get("etapes", [])),
             "origine": f["origine"]}
            for f in sorted(fiches.values(), key=lambda f: f["nom"])]


def recette(nom, arret_si_erreur=True, **parametres):
    """Joue une recette enregistrée, ses paramètres complétés par défaut.

        api.recette("collecteur_de_rue", adresse="Rue …, 03250 …",
                    rue="Rue …", commune="…", pente=1.0)

    Rend le compte rendu de `suite()`, précédé du nom et des paramètres
    effectivement retenus.
    """
    fiche = recettes(nom)
    if fiche.get("erreur"):
        raise RuntimeError("Recette illisible : %s" % fiche["erreur"])
    attendus = dict(fiche.get("parametres") or {})
    inconnus = [p for p in parametres if p not in attendus]
    if inconnus:
        raise RuntimeError("Paramètre(s) hors recette : %s (attendus : %s)"
                           % (", ".join(inconnus), ", ".join(sorted(attendus))))
    attendus.update(parametres)
    manquants = [p for p, v in attendus.items() if v is None]
    if manquants:
        raise RuntimeError("Paramètre(s) sans valeur : %s" % ", ".join(sorted(manquants)))
    cr = suite(fiche.get("etapes") or [], parametres=attendus,
               arret_si_erreur=arret_si_erreur)
    cr["recette"] = nom
    cr["parametres"] = _serialisable(attendus)
    return cr


def enregistrer_recette(nom, etapes, resume=None, parametres=None):
    """Écrit une recette dans le dossier personnel du profil QGIS.

    C'est ainsi qu'une séquence éprouvée en direct devient une procédure
    rejouable : la passer telle quelle, avec les valeurs variables remplacées
    par des "$param".
    """
    if not nom or any(c in nom for c in "\\/:*?\"<>|"):
        raise RuntimeError("Nom de recette invalide : %r" % nom)
    if not isinstance(etapes, (list, tuple)) or not etapes:
        raise RuntimeError("`etapes` doit être une liste non vide.")
    for etape in etapes:
        _appel_public(etape.get("appel"))          # refus immédiat d'un verbe inconnu
    dossier = _dossiers_recettes()[1][1]
    os.makedirs(dossier, exist_ok=True)
    chemin = os.path.join(dossier, nom + ".json")
    fiche = {"nom": nom, "resume": resume or "",
             "parametres": dict(parametres or {}), "etapes": list(etapes)}
    with open(chemin, "w", encoding="utf-8") as flux:
        json.dump(fiche, flux, ensure_ascii=False, indent=2)
    return {"nom": nom, "fichier": chemin, "etapes": len(etapes)}


DOMAINES = {
    "Lecture et séance": ["etat", "lire", "verifier", "aide", "fermer",
                          "dependances_manquantes"],
    "Données externes": ["adresse", "axe_de_rue"],
    "Projet": ["nouveau_projet", "charger", "enregistrer", "enregistrer_sous",
               "projets_recents"],
    "Fonds de plan": ["fonds", "attendre_fonds"],
    "Dessin": ["implanter_regards", "tracer_conduite", "creer_branchements",
               "inserer_regard", "supprimer", "vider"],
    "Attributs et cotes": ["saisir", "renumeroter", "caler_cotes",
                           "recalculer_pentes", "controler_branchements"],
    "Présentation": ["styles", "etiquettes", "config"],
    "Calculs": ["cubature", "coupe_type"],
    "Sorties": ["profil", "profil_groupe", "reglages_plan", "exporter",
                "exporter_async", "tache", "exporter_dxf", "controle_stareau",
                "exporter_stareau"],
    "Imports": ["importer_dxf", "importer_star_dt"],
    "Enchaînement": ["chantier"],
    "Recettes": ["suite", "recette", "recettes", "enregistrer_recette"],
}


def aide(domaine=None):
    """Sommaire des fonctions publiques, par domaine : appel et résumé.

    Point d'entrée conseillé pour un agent qui découvre le module : il donne
    la signature exacte et la première ligne de docstring de chaque fonction,
    sans avoir à lire les sources.
    """
    import inspect
    res = {}
    for titre, noms in DOMAINES.items():
        if domaine and domaine.lower() not in titre.lower():
            continue
        res[titre] = []
        for n in noms:
            f = globals().get(n)
            if f is None:
                continue
            try:
                sig = str(inspect.signature(f))
            except (TypeError, ValueError):
                sig = "(...)"
            res[titre].append({"appel": n + sig,
                               "resume": (inspect.getdoc(f) or "").split("\n")[0]})
    return res
