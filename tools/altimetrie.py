# -*- coding: utf-8 -*-
"""Altimétrie : récupération du TN depuis les MNT de la Géoplateforme IGN.

Cascade de sources, de la plus précise à la plus disponible :

  1. MNT LiDAR HD      — 0,50 m, ~10 cm en Z, couverture nationale en cours
  2. RGE ALTI 1 m      — 1 m, 0,2 à 0,7 m en Z selon le bloc, couverture complète
  3. API REST RGE ALTI — dernier secours si le WMS refuse le format BIL

Les deux premières passent par le WMS raster de data.geopf.fr en
`image/x-bil;bits=32` : la réponse est une grille de float32 bruts, ce qui
évite une requête HTTP par point et garde tout en Lambert 93 — la couche
LiDAR HD est servie nativement en EPSG:2154, sans reprojection.

Ce format n'est pas déclaré dans le GetCapabilities (qui n'annonce que
`image/png`, lequel renvoie pourtant une erreur 400) mais il est bien servi ;
d'où le repli (3), qui dégrade la précision sans casser la fonction.

Ce module ne dépend pas de QGIS : il est testable seul.
"""

import json
import math
import sys
import urllib.parse
import urllib.request
from array import array

WMS_URL = "https://data.geopf.fr/wms-r/wms"
REST_URL = "https://data.geopf.fr/altimetrie/1.0/calcul/alti/rest/elevation.json"

LAYER_LIDAR_HD = "IGNF_LIDAR-HD_MNT_ELEVATION.ELEVATIONGRIDCOVERAGE.LAMB93"
LAYER_RGE_ALTI = "ELEVATION.ELEVATIONGRIDCOVERAGE.HIGHRES"

RES_LIDAR_HD = 0.5   # m
RES_RGE_ALTI = 1.0   # m

# Sentinelles hors couverture : -9999 (LiDAR HD), -99999 (RGE ALTI).
_NODATA_MAX = -1000.0

MAX_PX = 2048        # dalle max ; 2048 px en float32 = 16 Mo, ~4 s
MARGE = 20.0         # m ajoutés autour de l'emprise des points
TIMEOUT = 60

SRC_LIDAR_HD = 'lidar_hd'
SRC_RGE_ALTI = 'rge_alti'
SRC_REST = 'rge_alti_api'
SRC_AUCUNE = 'aucune'

# Libellés des sources, pour le rapport CSV et le dialogue d'aperçu.
SOURCE_LABELS = {
    SRC_LIDAR_HD: "LiDAR HD (0,50 m)",
    SRC_RGE_ALTI: "RGE ALTI (1 m)",
    SRC_REST:     "RGE ALTI (API)",
    SRC_AUCUNE:   "hors couverture",
}


class ErreurAltimetrie(Exception):
    pass


# ────────────────────────────────────────────────────────── grille BIL

class Grille:
    """Grille de float32 renvoyée par le WMS en BIL : lignes du nord au sud,
    colonnes d'ouest en est, valeur au centre de chaque cellule."""

    __slots__ = ('xmin', 'ymin', 'xmax', 'ymax', 'nx', 'ny', 'res', 'vals')

    def __init__(self, bbox, nx, ny, res, vals):
        self.xmin, self.ymin, self.xmax, self.ymax = bbox
        self.nx, self.ny, self.res, self.vals = nx, ny, res, vals

    def _cell(self, i, j):
        """Valeur brute de la cellule (ligne i, colonne j) ; None hors grille
        ou en nodata."""
        if not (0 <= i < self.ny and 0 <= j < self.nx):
            return None
        v = self.vals[i * self.nx + j]
        return None if v <= _NODATA_MAX or math.isnan(v) else v

    def valeur(self, x, y):
        """Altitude interpolée bilinéairement en (x, y) Lambert 93.

        Repli sur la cellule la plus proche si l'un des quatre voisins est en
        nodata : sur un bord de couverture LiDAR, mieux vaut une valeur franche
        qu'une moyenne calculée avec un trou."""
        fx = (x - self.xmin) / self.res - 0.5
        fy = (self.ymax - y) / self.res - 0.5
        j0, i0 = math.floor(fx), math.floor(fy)
        tx, ty = fx - j0, fy - i0

        v00 = self._cell(i0, j0)
        v01 = self._cell(i0, j0 + 1)
        v10 = self._cell(i0 + 1, j0)
        v11 = self._cell(i0 + 1, j0 + 1)

        if None not in (v00, v01, v10, v11):
            return ((v00 * (1 - tx) + v01 * tx) * (1 - ty)
                    + (v10 * (1 - tx) + v11 * tx) * ty)

        # Plus proche cellule valide parmi les quatre (poids bilinéaire max).
        meilleur, poids_max = None, -1.0
        for v, poids in ((v00, (1 - tx) * (1 - ty)), (v01, tx * (1 - ty)),
                         (v10, (1 - tx) * ty), (v11, tx * ty)):
            if v is not None and poids > poids_max:
                meilleur, poids_max = v, poids
        return meilleur


def _decoder_bil(raw, nx, ny):
    attendu = nx * ny * 4
    if len(raw) != attendu:
        raise ErreurAltimetrie(
            "réponse BIL de {} octets, {} attendus ({}x{}) — le service a "
            "probablement renvoyé une exception".format(len(raw), attendu, nx, ny))
    vals = array('f')
    vals.frombytes(raw)
    if sys.byteorder != 'little':
        vals.byteswap()
    return vals


def _get(url, timeout):
    # Bandit B310 signale tout appel à urlopen() sans distinguer le schéma ;
    # il ne peut pas voir que l'URL vient toujours de WMS_URL/REST_URL
    # ci-dessus (https:// fixe) — d'où le contrôle explicite et le nosec.
    # `urllib` est utilisé ici volontairement, pas QgsNetworkAccessManager :
    # ce module reste indépendant de QGIS pour rester testable seul.
    if not url.startswith('https://'):
        raise ErreurAltimetrie("URL non https refusée : {}".format(url))
    req = urllib.request.Request(url, headers={'User-Agent': 'CanaPlan/QGIS'})
    with urllib.request.urlopen(req, timeout=timeout) as rep:  # nosec B310
        return rep.read()


def charger_grille(layer, bbox, res, timeout=TIMEOUT):
    """Télécharge une dalle MNT en BIL32. `bbox` doit déjà être calée sur la
    résolution native (cf. _caler)."""
    xmin, ymin, xmax, ymax = bbox
    nx = int(round((xmax - xmin) / res))
    ny = int(round((ymax - ymin) / res))
    if nx <= 0 or ny <= 0:
        raise ErreurAltimetrie("emprise vide")
    if nx > MAX_PX or ny > MAX_PX:
        raise ErreurAltimetrie("dalle trop grande ({}x{} px)".format(nx, ny))

    params = urllib.parse.urlencode({
        'SERVICE': 'WMS', 'VERSION': '1.3.0', 'REQUEST': 'GetMap',
        'LAYERS': layer, 'STYLES': '', 'CRS': 'EPSG:2154',
        'BBOX': "{},{},{},{}".format(xmin, ymin, xmax, ymax),
        'WIDTH': nx, 'HEIGHT': ny,
        'FORMAT': 'image/x-bil;bits=32',
    })
    raw = _get("{}?{}".format(WMS_URL, params), timeout)
    return Grille(bbox, nx, ny, res, _decoder_bil(raw, nx, ny))


# ────────────────────────────────────────────────────────── découpage

def _caler(bbox, res, marge=0.0):
    """Cale l'emprise sur la grille native du MNT : les pixels demandés
    coïncident alors avec les cellules du produit, sans rééchantillonnage."""
    xmin, ymin, xmax, ymax = bbox
    return (math.floor((xmin - marge) / res) * res,
            math.floor((ymin - marge) / res) * res,
            math.ceil((xmax + marge) / res) * res,
            math.ceil((ymax + marge) / res) * res)


def _emprise(points, res, marge=MARGE):
    xs = [p[1] for p in points]
    ys = [p[2] for p in points]
    return _caler((min(xs), min(ys), max(xs), max(ys)), res, marge)


def _tuiles(bbox, res, max_px=MAX_PX):
    """Découpe l'emprise en dalles d'au plus max_px de côté."""
    xmin, ymin, xmax, ymax = bbox
    pas = max_px * res
    tuiles = []
    y = ymin
    while y < ymax:
        y2 = min(y + pas, ymax)
        x = xmin
        while x < xmax:
            tuiles.append((x, y, min(x + pas, xmax), y2))
            x += pas
        y = y2
    return tuiles


def _passe(layer, res, points, timeout, log):
    """Une passe sur une source : renvoie {cle: z} pour les points résolus."""
    obtenus = {}
    tuiles = _tuiles(_emprise(points, res), res)
    for n, bbox in enumerate(tuiles, 1):
        dedans = [p for p in points
                  if bbox[0] <= p[1] <= bbox[2] and bbox[1] <= p[2] <= bbox[3]]
        if not dedans:
            continue
        log("  dalle {}/{} ({:.0f}x{:.0f} m, {} pt)".format(
            n, len(tuiles), bbox[2] - bbox[0], bbox[3] - bbox[1], len(dedans)))
        grille = charger_grille(layer, bbox, res, timeout)
        for cle, x, y in dedans:
            z = grille.valeur(x, y)
            if z is not None:
                obtenus[cle] = z
    return obtenus


# ────────────────────────────────────────────────────────── repli API REST

def _passe_rest(points, to_wgs84, timeout, log, lot=50):
    """Repli : API REST RGE ALTI. `to_wgs84` convertit (x, y) L93 en
    (lon, lat) — fourni par l'appelant (QgsCoordinateTransform côté QGIS)."""
    if to_wgs84 is None:
        return {}
    obtenus = {}
    for i in range(0, len(points), lot):
        paquet = points[i:i + lot]
        lonlat = [to_wgs84(x, y) for _cle, x, y in paquet]
        params = urllib.parse.urlencode({
            'lon': '|'.join("{:.7f}".format(lon) for lon, _ in lonlat),
            'lat': '|'.join("{:.7f}".format(lat) for _, lat in lonlat),
            'resource': 'ign_rge_alti_wld', 'zonly': 'true',
        })
        log("  API REST : lot de {} points".format(len(paquet)))
        data = json.loads(_get("{}?{}".format(REST_URL, params), timeout).decode('utf-8'))
        if 'error' in data:
            raise ErreurAltimetrie(data['error'].get('description', 'erreur API'))
        for (cle, _x, _y), z in zip(paquet, data.get('elevations', [])):
            if isinstance(z, (int, float)) and z > _NODATA_MAX:
                obtenus[cle] = float(z)
    return obtenus


# ────────────────────────────────────────────────────────── point d'entrée

def echantillonner(points, to_wgs84=None, timeout=TIMEOUT, log=None):
    """Altitude de chaque point, par la source la plus précise disponible.

    `points` : liste de (cle, x, y) en Lambert 93.
    Retourne {cle: {'z': float|None, 'source': SRC_*}}.
    """
    log = log or (lambda _m: None)
    resultats = {cle: {'z': None, 'source': SRC_AUCUNE} for cle, _x, _y in points}
    if not points:
        return resultats

    restants = list(points)
    for layer, res, source in ((LAYER_LIDAR_HD, RES_LIDAR_HD, SRC_LIDAR_HD),
                               (LAYER_RGE_ALTI, RES_RGE_ALTI, SRC_RGE_ALTI)):
        if not restants:
            break
        log("{} : {} point(s) à résoudre".format(SOURCE_LABELS[source], len(restants)))
        try:
            obtenus = _passe(layer, res, restants, timeout, log)
        except (ErreurAltimetrie, OSError) as exc:
            log("  échec ({}) — passage à la source suivante".format(exc))
            continue
        for cle, z in obtenus.items():
            resultats[cle] = {'z': z, 'source': source}
        restants = [p for p in restants if p[0] not in obtenus]

    if restants:
        log("{} : {} point(s) restant(s)".format(SOURCE_LABELS[SRC_REST], len(restants)))
        try:
            for cle, z in _passe_rest(restants, to_wgs84, timeout, log).items():
                resultats[cle] = {'z': z, 'source': SRC_REST}
        except (ErreurAltimetrie, OSError) as exc:
            log("  échec ({})".format(exc))

    return resultats
