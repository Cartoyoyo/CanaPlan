# tools/dependances.py
"""Installation à la demande des bibliothèques Python de CanaPlan.

Deux fonctions du plugin ont besoin de bibliothèques tierces : l'export DXF
et la conversion DXF/DWG → SIG. Tout le reste — dessin, profils en long,
cubatures, coupes, impression, export StaR-Eau, import Star-DT — fonctionne
sans elles.

Elles ne sont donc plus embarquées dans le paquet publié : la première fois
qu'une de ces deux fonctions est demandée, le plugin propose de les installer.
Les autres fonctions restent disponibles quoi qu'il arrive, et l'utilisateur
qui n'exporte jamais en DXF n'est jamais sollicité.

Emplacement : `<plugin>/libs`. Ce dossier est effacé par QGIS à chaque mise à
jour du plugin, donc l'installation est à refaire après une montée de
version. C'est le compromis retenu : `libs/` est déjà en tête du `sys.path`
du plugin, et la logique d'import existante n'a pas à changer.
"""

import os
import sys

# Même liste que requirements-libs.txt, mêmes versions. --no-deps est
# volontaire : ezdxf déclare numpy en dépendance dure, or QGIS le fournit
# déjà et libs/ passe AVANT lui dans le sys.path. Un numpy déposé ici
# masquerait celui de QGIS — au mieux redondant, au pire compilé pour une
# autre plateforme.
REQUIS = (
    ("ezdxf", "ezdxf==1.4.4"),
    ("fontTools", "fontTools==4.63.0"),
    ("pyparsing", "pyparsing==3.3.2"),
    ("typing_extensions", "typing_extensions"),
)


def libs_dir():
    """`<plugin>/libs`, créé au besoin et placé en tête du sys.path."""
    racine = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    libs = os.path.join(racine, "libs")
    os.makedirs(libs, exist_ok=True)
    if libs not in sys.path:
        sys.path.insert(0, libs)
    return libs


def manquants():
    """Spécifications pip des bibliothèques absentes, dans l'ordre de REQUIS."""
    libs_dir()
    absents = []
    for module, spec in REQUIS:
        try:
            __import__(module)
        except Exception:
            # Un import qui échoue pour une autre raison qu'une absence
            # (installation tronquée, par exemple) doit aussi mener à une
            # réinstallation : c'est le seul geste qui puisse le réparer.
            absents.append(spec)
    return absents


def tout_est_la():
    return not manquants()


def interpreteur_python():
    """Chemin de l'interpréteur Python, ou None.

    Piège de QGIS sous Windows : `sys.executable` ne désigne PAS Python mais
    le binaire de QGIS (`qgis-bin.exe`). Lancer « sys.executable -m pip »
    relancerait donc QGIS. Il faut aller chercher le python.exe de
    l'installation, qui se trouve dans sys.prefix.
    """
    candidats = []
    exe = sys.executable or ""
    if os.path.basename(exe).lower().startswith("python"):
        candidats.append(exe)
    if os.name == "nt":
        candidats += [
            os.path.join(sys.prefix, "python.exe"),
            os.path.join(sys.prefix, "python3.exe"),
            os.path.join(sys.prefix, "Scripts", "python.exe"),
        ]
    else:
        candidats += [
            os.path.join(sys.prefix, "bin", "python3"),
            os.path.join(sys.prefix, "bin", "python"),
        ]
    import shutil
    for nom in ("python3", "python"):
        trouve = shutil.which(nom)
        if trouve:
            candidats.append(trouve)

    for c in candidats:
        if c and os.path.isfile(c):
            return c
    return None


def commande_pip(paquets, libs=None):
    """Commande d'installation, ou None si aucun interpréteur n'a été trouvé."""
    python = interpreteur_python()
    if not python:
        return None
    return [
        python, "-m", "pip", "install",
        "--target", libs or libs_dir(),
        "--upgrade",
        "--no-deps",
        "--no-warn-script-location",
    ] + list(paquets)


def commande_manuelle(paquets):
    """La même commande, en texte, à coller dans l'OSGeo4W Shell.

    Sert quand l'installation automatique échoue — proxy d'entreprise,
    pip absent, droits refusés. L'utilisateur peut alors la porter sur un
    poste connecté, ou la donner à son service informatique.
    """
    python = interpreteur_python() or "python"
    return (f'"{python}" -m pip install --target "{libs_dir()}" '
            f'--upgrade --no-deps ' + " ".join(paquets))


def installer(paquets, timeout=600):
    """Lance pip. Retourne (succès, sortie texte).

    Ne lève pas : l'appelant affiche la sortie telle quelle en cas d'échec.
    """
    import subprocess  # nosec B404
    cmd = commande_pip(paquets)
    if cmd is None:
        return False, ("Aucun interpréteur Python n'a été trouvé "
                       f"(sys.prefix = {sys.prefix}).")
    try:
        # Liste d'arguments, sans shell. argv[0] est un python.exe localisé
        # sur le disque, les autres éléments sont des littéraux et des noms
        # de paquets figés dans REQUIS.
        res = subprocess.run(  # nosec B603
            cmd, capture_output=True, text=True, timeout=timeout)
    except Exception as err:
        return False, f"{type(err).__name__}: {err}"

    sortie = (res.stdout or "") + (res.stderr or "")
    if res.returncode != 0:
        return False, sortie.strip() or f"pip a retourné {res.returncode}"

    # Les modules absents ont pu être importés (et mis en cache comme
    # introuvables) avant l'installation.
    import importlib
    importlib.invalidate_caches()
    return True, sortie.strip()


def assurer(parent=None):
    """Garantit la présence des bibliothèques. Retourne True si on peut continuer.

    Appelée juste avant une fonction qui en dépend. Si tout est là, ne fait
    rien et ne montre rien. Sinon, propose l'installation ; l'utilisateur
    peut refuser, et la fonction appelante doit alors renoncer.
    """
    if tout_est_la():
        return True
    from ..gui.dependances_dialog import DependancesDialog
    dlg = DependancesDialog(manquants(), parent)
    dlg.exec_()
    return tout_est_la()
