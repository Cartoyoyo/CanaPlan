# tools/errlog.py
"""Journalisation bornée des exceptions volontairement ignorées.

Le plugin comporte beaucoup d'endroits où une exception est sans gravité et
où continuer est le bon comportement : une entité DXF exotique parmi cent
mille, un fichier temporaire déjà supprimé, une propriété de symbologie
absente d'une version de QGIS. Ces cas étaient traités par un ``except: pass``
muet, ce qui a deux défauts : rien ne distingue l'échec attendu du bug réel,
et l'analyse de sécurité du dépôt QGIS les signale tous (B110 / B112).

``ignored()`` remplace ce ``pass``. Le comportement du programme ne change
pas — l'exception reste avalée — mais elle laisse une trace dans le panneau
de journal, sous l'onglet « CanaPlan ».

Le plafond est le point important. Ces gestionnaires sont souvent dans des
boucles par entité : sans limite, un DXF de 100 000 objets écrirait 100 000
lignes et le journal deviendrait à la fois inutile et coûteux. On garde donc
les premières occurrences de chaque site, puis on se tait — l'information
utile (« ça échoue ici, et voilà pourquoi ») tient dans les trois premières.
"""

from qgis.core import QgsMessageLog, Qgis

_ETIQUETTE = "CanaPlan"

# Trois suffit pour reconnaître un motif ; au-delà on ne fait que répéter.
MAX_PAR_SITE = 3

_compteurs = {}


def ignored(err, contexte, level=Qgis.Info):
    """Trace une exception que l'appelant choisit d'ignorer.

    err      : l'exception attrapée
    contexte : identifiant stable du site, « module.fonction:ligne ». Sert
               aussi de clé de plafonnement : chaque site a son propre quota.
    level    : Qgis.Info par défaut — c'est un échec attendu, pas un incident.
    """
    # Cette fonction ne doit JAMAIS lever. Elle est appelée depuis des blocs
    # `except`, et certains de ces blocs existent justement parce que
    # QgsMessageLog peut échouer (voir adxf/fnc4all.py, où le try entoure un
    # logMessage). Y relancer une exception la ferait remonter depuis un
    # gestionnaire d'erreur, à l'endroit précis où le code voulait continuer.
    try:
        n = _compteurs.get(contexte, 0) + 1
        _compteurs[contexte] = n
        if n > MAX_PAR_SITE:
            return
        fin = " [occurrences suivantes masquées]" if n == MAX_PAR_SITE else ""
        QgsMessageLog.logMessage(
            f"{contexte} — ignoré : {type(err).__name__}: {err}{fin}",
            _ETIQUETTE, level)
    except Exception:
        return          # journaliser est un confort, jamais une obligation


def reset():
    """Remet les compteurs à zéro (début d'un nouvel export, par exemple)."""
    _compteurs.clear()
