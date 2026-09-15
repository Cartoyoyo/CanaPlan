# -*- coding: utf-8 -*-
"""Les recettes de CanaPlan, publiées dans la boîte à outils Processing.

Pourquoi ce module
------------------
`tools/api.py` rend CanaPlan entièrement pilotable, mais il faut **connaître la
porte** : `from CanaPlan.tools import api`. Un agent qui découvre QGIS ne la
connaît pas. Il fait ce qu'on lui a appris — il interroge le registre
Processing, n'y trouve aucun `canaplan`, et conclut que le plugin ne
s'utilise qu'à la souris. La conclusion est fausse, l'observation ne l'est pas.

Ce module ne change rien à l'API : il l'**annonce**. Chaque recette devient un
`QgsProcessingAlgorithm` qui appelle `api.recette()` avec les paramètres du
formulaire. Même code, même résultat — une seconde porte, dans le catalogue où
tout le monde regarde déjà.

Deux effets secondaires, tous deux voulus : les recettes deviennent utilisables
à la souris depuis la boîte à outils, formulaire compris ; et `execute_processing`
d'un serveur MCP suffit à jouer un chantier, sans rien savoir de CanaPlan.

Pas de threading
----------------
Les algorithmes portent `FlagNoThreading`. Ce n'est pas une précaution : l'API
manipule `iface`, le canevas et des dialogues, qui n'existent que sur le fil
principal. Lancée dans un *worker* Processing, elle fige ou fait tomber QGIS.

Les blocs ne sont pas publiés
-----------------------------
Une recette dont le résumé s'ouvre par « BLOC. » est une brique d'assemblage :
elle attend une géométrie (`axe`) qu'aucun formulaire ne sait fournir, et elle
n'a de sens qu'appelée par une autre recette. La publier offrirait un
formulaire qui ne peut qu'échouer.
"""

import json
import os

from qgis.core import (
    QgsProcessingAlgorithm, QgsProcessingException, QgsProcessingOutputNumber,
    QgsProcessingOutputString, QgsProcessingParameterBoolean,
    QgsProcessingParameterNumber, QgsProcessingParameterString,
    QgsProcessingProvider,
)
from qgis.PyQt.QtGui import QIcon

from . import api


def _drapeau_sans_thread():
    """`FlagNoThreading`, quelle que soit la génération de l'API Processing."""
    from qgis.core import Qgis
    candidats = (
        (getattr(Qgis, "ProcessingAlgorithmFlag", None), "NoThreading"),
        (getattr(QgsProcessingAlgorithm, "Flag", None), "FlagNoThreading"),
        (QgsProcessingAlgorithm, "FlagNoThreading"),
    )
    for porteur, attribut in candidats:
        if porteur is None:
            continue
        drapeau = getattr(porteur, attribut, None)
        if drapeau is not None:
            return drapeau
    return None


def _type_nombre(entier):
    """`QgsProcessingParameterNumber.Integer` / `.Double`, ancienne API ou non."""
    porteur = getattr(QgsProcessingParameterNumber, "Type",
                      QgsProcessingParameterNumber)
    return getattr(porteur, "Integer" if entier else "Double")


def _relire(texte):
    """Rend au texte d'un champ libre le type que la recette attend.

    Les paramètres déclarés `null` dans une recette n'annoncent pas leur type :
    `pente` est un nombre, `rue` une chaîne, et le formulaire ne montre qu'une
    ligne de saisie pour les deux. `caler_cotes` fait `pente / 100.0` — une
    chaîne y lèverait. On relit donc la saisie : ce qui s'écrit comme un nombre
    ou un booléen en devient un, le reste demeure du texte. Un nom de voie ne
    se lit jamais comme un nombre, la conversion est sans risque.
    """
    brut = (texte or "").strip()
    if not brut:
        return None
    if brut.lower() in ("true", "vrai", "oui"):
        return True
    if brut.lower() in ("false", "faux", "non"):
        return False
    try:
        return int(brut)
    except ValueError:
        pass
    try:
        return float(brut.replace(",", "."))
    except ValueError:
        return brut


class RecetteAlgorithm(QgsProcessingAlgorithm):
    """Une recette CanaPlan exposée comme algorithme Processing."""

    def __init__(self, fiche):
        super().__init__()
        self._fiche = fiche
        self._nom = fiche.get("nom")
        self._parametres = dict(fiche.get("parametres") or {})
        try:
            self._requis = api._params_requis(fiche.get("etapes") or [],
                                              self._parametres)
        except Exception:
            self._requis = set()

    # ── identité ────────────────────────────────────────────────────────────

    def createInstance(self):
        return RecetteAlgorithm(self._fiche)

    def name(self):
        return self._nom

    def displayName(self):
        return self._nom.replace("_", " ").capitalize()

    def group(self):
        return ("Recettes livrées" if self._fiche.get("origine") == "livree"
                else "Recettes personnelles")

    def groupId(self):
        return ("recettes_livrees" if self._fiche.get("origine") == "livree"
                else "recettes_perso")

    def shortHelpString(self):
        return self._fiche.get("resume") or ""

    def shortDescription(self):
        # Le resume complet passe par `shortHelpString`, que la boite a outils
        # affiche dans son panneau d'aide. Les clients qui n'interrogent que
        # `shortDescription` — un serveur MCP, par exemple — n'en voyaient
        # rien : sans elle, un agent recoit la liste des parametres sans la
        # phrase qui dit comment les remplir.
        try:
            return api._resume_court(self._fiche.get("resume") or "")
        except Exception:
            return self._fiche.get("resume") or ""

    def flags(self):
        drapeau = _drapeau_sans_thread()
        return super().flags() | drapeau if drapeau is not None \
            else super().flags()

    # ── formulaire ──────────────────────────────────────────────────────────

    def initAlgorithm(self, config=None):
        for cle, defaut in self._parametres.items():
            etiquette = cle.replace("_", " ")
            if isinstance(defaut, bool):
                self.addParameter(QgsProcessingParameterBoolean(
                    cle, etiquette, defaultValue=defaut))
            elif isinstance(defaut, int):
                self.addParameter(QgsProcessingParameterNumber(
                    cle, etiquette, type=_type_nombre(True),
                    defaultValue=defaut, optional=True))
            elif isinstance(defaut, float):
                self.addParameter(QgsProcessingParameterNumber(
                    cle, etiquette, type=_type_nombre(False),
                    defaultValue=defaut, optional=True))
            else:
                # `null` ne dit pas le type : champ libre, relu a l'execution.
                obligatoire = defaut is None and cle in self._requis
                self.addParameter(QgsProcessingParameterString(
                    cle, etiquette,
                    defaultValue=None if defaut is None else str(defaut),
                    optional=not obligatoire))

        self.addOutput(QgsProcessingOutputString("ETAT", "État"))
        self.addOutput(QgsProcessingOutputNumber("SECONDES", "Durée (s)"))
        self.addOutput(QgsProcessingOutputString("RAPPORT", "Compte rendu JSON"))

    # ── exécution ───────────────────────────────────────────────────────────

    def processAlgorithm(self, parameters, context, feedback):
        arguments = {}
        for cle, defaut in self._parametres.items():
            if isinstance(defaut, bool):
                arguments[cle] = self.parameterAsBool(parameters, cle, context)
            elif isinstance(defaut, int):
                arguments[cle] = self.parameterAsInt(parameters, cle, context)
            elif isinstance(defaut, float):
                arguments[cle] = self.parameterAsDouble(parameters, cle, context)
            else:
                valeur = _relire(
                    self.parameterAsString(parameters, cle, context))
                # Un champ laisse vide n'est pas une valeur vide : c'est
                # l'absence de consigne. La recette applique alors son defaut.
                if valeur is not None:
                    arguments[cle] = valeur

        feedback.pushInfo("CanaPlan — recette « %s »" % self._nom)
        for cle in sorted(arguments):
            feedback.pushInfo("    %s = %r" % (cle, arguments[cle]))

        try:
            resultat = api.recette(self._nom, **arguments)
        except Exception as err:
            raise QgsProcessingException(
                "Recette « %s » interrompue : %s" % (self._nom, err))

        for compte in resultat.get("etapes") or []:
            feedback.pushInfo("  [%s] %s : %s" % (
                compte.get("rang"), compte.get("appel"),
                compte.get("etat", "ok")))
            if feedback.isCanceled():
                break

        etat = resultat.get("etat", "?")
        if etat != "ok":
            feedback.reportError(
                "Recette « %s » en échec à l'étape %s."
                % (self._nom, resultat.get("echouee", "?")), fatalError=False)

        return {"ETAT": etat,
                "SECONDES": float(resultat.get("secondes") or 0.0),
                "RAPPORT": json.dumps(api._serialisable(resultat),
                                      ensure_ascii=False)}


class CanaPlanProvider(QgsProcessingProvider):
    """Le fournisseur `canaplan` : une entrée par recette publiable."""

    def id(self):
        return "canaplan"

    def name(self):
        return "CanaPlan"

    def longName(self):
        return "CanaPlan — réseaux d'assainissement EU / EP"

    def icon(self):
        chemin = os.path.join(os.path.dirname(os.path.dirname(__file__)),
                              "icon", "icon.png")
        return QIcon(chemin) if os.path.exists(chemin) else super().icon()

    def loadAlgorithms(self):
        try:
            fiches = api._charger_recettes()
        except Exception:
            return
        for nom in sorted(fiches):
            fiche = fiches[nom]
            if fiche.get("erreur"):
                continue                      # recette illisible : rien a offrir
            resume = (fiche.get("resume") or "").strip().upper()
            if resume.startswith("BLOC"):
                continue                      # brique d'assemblage, cf. docstring
            try:
                self.addAlgorithm(RecetteAlgorithm(fiche))
            except (TypeError, ValueError, KeyError, AttributeError,
                    RuntimeError):
                continue
