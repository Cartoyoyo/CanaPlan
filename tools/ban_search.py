# -*- coding: utf-8 -*-
"""Recherche d'adresses via l'API BAN, pour l'étape 1 de l'assistant de
création de projet. Calqué sur magic_search/providers/ban_provider.py (pas
de dépendance à ce plugin — BET_HUMIDE doit fonctionner sans lui)."""

import json
import urllib.parse
from qgis.PyQt.QtCore import QObject, QUrl, QTimer, pyqtSignal
from qgis.PyQt.QtNetwork import QNetworkRequest, QNetworkReply
from qgis.core import QgsMessageLog, QgsNetworkAccessManager, Qgis

BAN_URL = 'https://api-adresse.data.gouv.fr/search/?q={query}&limit=5'
DEBOUNCE_MS = 600
TAG = 'BET_HUMIDE'


class BanSearchProvider(QObject):
    """Recherche BAN avec debounce. Émet results_ready(list[dict]) avec
    pour chaque résultat : label, city, postcode, type, score, lon, lat."""

    results_ready = pyqtSignal(list)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._nam = QgsNetworkAccessManager.instance()
        self._reply = None
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self._do_request)
        self._pending_query = ''

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

        url = QUrl(BAN_URL.format(query=urllib.parse.quote(self._pending_query, safe='')))
        request = QNetworkRequest(url)
        self._reply = self._nam.get(request)
        self._reply.finished.connect(self._on_finished)

    def _on_finished(self):
        reply = self._reply
        if reply is None:
            return

        if reply.error() != QNetworkReply.NoError:
            QgsMessageLog.logMessage(
                f"BAN error: {reply.error()} - {reply.errorString()}",
                TAG, Qgis.Warning)
            reply.deleteLater()
            self._reply = None
            self.results_ready.emit([])
            return

        try:
            raw = reply.readAll()
            text = raw.data().decode('utf-8')
            data = json.loads(text)

            results = []
            for feat in data.get('features', []):
                props = feat.get('properties', {})
                coords = feat.get('geometry', {}).get('coordinates', [0, 0])
                results.append({
                    'label': props.get('label', ''),
                    'city': props.get('city', ''),
                    'postcode': props.get('postcode', ''),
                    'type': props.get('type', ''),
                    'score': props.get('score', 0),
                    'lon': coords[0],
                    'lat': coords[1],
                })

            self.results_ready.emit(results)

        except Exception as e:
            QgsMessageLog.logMessage(f"BAN parse error: {e}", TAG, Qgis.Warning)
            self.results_ready.emit([])

        finally:
            reply.deleteLater()
            self._reply = None
