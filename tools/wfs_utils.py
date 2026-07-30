# tools/wfs_utils.py
"""Téléchargement WFS asynchrone + utilitaires partagés.

Remplace les 4 copies du pipeline « emprise → bbox L93 → URL WFS → urlopen
bloquant → GeoJSON temporaire → QgsVectorLayer » de main.py :

- le réseau part dans une QgsTask (thread de fond) : plus de gel de QGIS,
  progression visible dans la barre de tâches, annulable ;
- TLS vérifié par défaut, avec repli explicite (signalé) en cas de
  certificat invalide (proxy d'entreprise) ;
- GeoJSON écrits dans %TEMP%/bet_humide/, purgé au chargement du plugin.
"""
import json
import os
import ssl
import tempfile
import urllib.request
from concurrent.futures import ThreadPoolExecutor

from qgis.core import (
    QgsTask, QgsApplication, QgsProject,
    QgsCoordinateReferenceSystem, QgsCoordinateTransform,
)

DEFAULT_WFS_URL = "https://data.geopf.fr/wfs/ows"
_TEMP_SUBDIR = "bet_humide"

# Références fortes sur les tâches en cours (sinon Python les ramasse
# avant la fin et le callback n'est jamais appelé).
_ACTIVE_TASKS = []


# ------------------------------------------------------------------ temporaires

def temp_dir():
    d = os.path.join(tempfile.gettempdir(), _TEMP_SUBDIR)
    os.makedirs(d, exist_ok=True)
    return d


def purge_temp_dir():
    """Supprime les GeoJSON des sessions précédentes.

    Appelé au chargement du plugin : les fichiers encore verrouillés par
    une couche ouverte sont simplement ignorés."""
    d = os.path.join(tempfile.gettempdir(), _TEMP_SUBDIR)
    if not os.path.isdir(d):
        return
    for name in os.listdir(d):
        try:
            os.unlink(os.path.join(d, name))
        except OSError:
            pass


def write_geojson(features, prefix):
    """Écrit une FeatureCollection L93 dans %TEMP%/bet_humide/ et
    retourne le chemin."""
    fd, path = tempfile.mkstemp(suffix='.geojson', prefix=prefix,
                                dir=temp_dir())
    with os.fdopen(fd, 'w', encoding='utf-8') as f:
        json.dump({
            "type": "FeatureCollection",
            "crs": {"type": "name", "properties": {
                "name": "urn:ogc:def:crs:EPSG::2154"}},
            "features": features,
        }, f, ensure_ascii=False)
    return path


# ------------------------------------------------------------------ bbox

def current_bbox_l93(canvas):
    """Emprise courante du canevas au format bbox WFS EPSG:2154."""
    extent  = canvas.extent()
    crs_src = canvas.mapSettings().destinationCrs()
    if crs_src.authid().upper() != "EPSG:2154":
        tr = QgsCoordinateTransform(
            crs_src, QgsCoordinateReferenceSystem("EPSG:2154"),
            QgsProject.instance())
        extent = tr.transformBoundingBox(extent)
    return (f"{extent.xMinimum():.2f},{extent.yMinimum():.2f},"
            f"{extent.xMaximum():.2f},{extent.yMaximum():.2f},EPSG:2154")


# ------------------------------------------------------------------ fetch

def _fetch_features(typename, bbox, wfs_url, timeout):
    """GET WFS → (features, insecure).

    TLS vérifié d'abord ; en cas d'erreur de certificat uniquement, second
    essai sans vérification, signalé par insecure=True (l'ancien code
    désactivait la vérification systématiquement)."""
    url = (f"{wfs_url}?SERVICE=WFS&VERSION=2.0.0&REQUEST=GetFeature"
           f"&TYPENAMES={typename}&BBOX={bbox}"
           f"&SRSNAME=EPSG:2154&outputFormat=application/json&COUNT=5000")
    try:
        with urllib.request.urlopen(url, timeout=timeout) as r:
            return json.loads(r.read().decode('utf-8')).get('features', []), False
    except (ssl.SSLError, urllib.error.URLError) as e:
        # URLError peut encapsuler une SSLError (proxy / certificat auto-signé)
        reason = getattr(e, 'reason', e)
        if not isinstance(e, ssl.SSLError) and not isinstance(reason, ssl.SSLError):
            raise
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        with urllib.request.urlopen(url, timeout=timeout, context=ctx) as r:
            return json.loads(r.read().decode('utf-8')).get('features', []), True


def fetch_wfs_async(description, requests, on_done, timeout=30):
    """Télécharge plusieurs couches WFS en tâche de fond.

    requests : liste de dicts :
        typename : nom de couche WFS
        name     : nom de la future couche QGIS
        bbox     : bbox L93 (current_bbox_l93)
        wfs_url  : optionnel (défaut data.geopf.fr)
        prefix   : optionnel, préfixe du fichier temporaire
        filter   : optionnel, callable(feature_dict) -> bool

    on_done(results, errors) est appelé dans le thread principal :
        results : [{'name', 'path' (None si 0 objet), 'count', 'insecure'}]
        errors  : [str]
    Le réseau ET l'écriture GeoJSON se font dans le thread de travail.
    """
    def _fetch_one(req):
        feats, insecure = _fetch_features(
            req['typename'], req['bbox'],
            req.get('wfs_url', DEFAULT_WFS_URL), timeout)
        flt = req.get('filter')
        if flt:
            feats = [f for f in feats if flt(f)]
        path = (write_geojson(feats, req.get('prefix', 'bet_wfs_'))
                if feats else None)
        return {'name': req['name'], 'path': path,
                'count': len(feats), 'insecure': insecure}

    def _work(task):
        results, errors = [], []
        n = max(1, len(requests))
        done = 0
        with ThreadPoolExecutor(max_workers=n) as pool:
            futures = {pool.submit(_fetch_one, req): req for req in requests}
            for future in futures:
                req = futures[future]
                if task.isCanceled():
                    return None
                try:
                    results.append(future.result())
                except Exception as e:
                    errors.append(f"{req['name']} : {e}")
                done += 1
                task.setProgress(done * 100.0 / n)
        return results, errors

    def _finished(exception, value=None):
        if task in _ACTIVE_TASKS:
            _ACTIVE_TASKS.remove(task)
        if exception is not None:
            on_done([], [str(exception)])
        elif value is None:
            on_done([], [])          # annulé par l'utilisateur
        else:
            on_done(*value)

    task = QgsTask.fromFunction(description, _work, on_finished=_finished)
    _ACTIVE_TASKS.append(task)
    QgsApplication.taskManager().addTask(task)
    return task
