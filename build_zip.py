# build_zip.py
"""Construit le ZIP de distribution du plugin CanaPlan.

Usage :  python build_zip.py [dossier_sortie]

Exclut du paquet : .git, __pycache__, *.dist-info, libs/bin, libs/share,
le workflow de publication (.github), le figeage des librairies
(requirements-libs.txt), fichiers de travail (audit.md, amelioration.txt, INTERVIEW.md,
assistant_creation_projet.md, uml_structure.mmd / .d2 / .puml,
icon/fichedemarque.md, symbology-style.db, .gitignore, build_zip.py lui-même,
les scripts de mise au point
tools/dxf_convert/{analyze_dxf,analyze_ml,inspect_all,test_parser}.py)
et fichiers temporaires (*.pyc, *.tmp, *.zip).

NB : le paquet reprend libs/ tel qu'il est sur la machine de build. C'est
cette installation-la qui est testee et qui tourne, on publie donc la meme.
Le paquet est par construction lie a la plateforme de build : ne pas le
reconstruire ailleurs (une CI Linux, par exemple) sans le savoir, car le
plugin insere libs/ en tete du sys.path et un binaire d'une autre
plateforme y masquerait le module fonctionnel de QGIS.
"""
import os
import sys
import zipfile

PLUGIN_NAME = "CanaPlan"

EXCLUDE_DIRS = {
    ".git", ".github", "__pycache__",
    # captures d'ecran du README : referencees par aucun module, 3.8 Mo
    "images",
    os.path.join("libs", "bin"),
    os.path.join("libs", "share"),
}
EXCLUDE_FILES = {
    "audit.md", "amelioration.txt",
    "uml_structure.puml", "uml_structure.mmd", "uml_structure.d2",
    ".gitignore", "build_zip.py", "requirements-libs.txt",
    "INTERVIEW.md", "assistant_creation_projet.md",
    "symbology-style.db",
    os.path.join("icon", "fichedemarque.md"),
    # Scripts de mise au point du parseur DXF : importes par aucun module,
    # chemins absolus en dur vers une machine de developpement. Livres par
    # erreur dans la 1.7.0, ils y declenchaient les dix alertes bandit
    # (B110 try/except/pass, B608 requete SQL construite par concatenation)
    # qui bloquent la validation sur plugins.qgis.org.
    os.path.join("tools", "dxf_convert", "analyze_dxf.py"),
    os.path.join("tools", "dxf_convert", "analyze_ml.py"),
    os.path.join("tools", "dxf_convert", "inspect_all.py"),
    os.path.join("tools", "dxf_convert", "test_parser.py"),
}
# .zip : le paquet est ecrit dans le dossier parcouru par os.walk. Sans cette
# exclusion, build_zip s'ajoute au ZIP en cours d'ecriture et lit un fichier qui
# grossit a mesure qu'il l'ecrit — la construction ne se termine jamais.
EXCLUDE_SUFFIXES = (".pyc", ".pyo", ".tmp", ".log", ".zip")

# Poids mort des librairies : suites de tests, en-tetes de compilation et
# stubs de typage ne servent jamais a l'execution. Sur les roues Linux que
# reconstruit la CI, ils pesent plus de la moitie du paquet (105 Mo avant,
# et le ZIP passait de 15 a 28 Mo).
LIB_EXCLUDE_DIRS = {"tests", "test", "testing", "_pyinstaller", "__pycache__"}
LIB_EXCLUDE_SUFFIXES = (".pyi", ".h", ".c", ".pyx", ".pxd", ".f", ".a")


def _excluded(rel_path):
    parts = rel_path.split(os.sep)
    if any(p == "__pycache__" or p.endswith(".dist-info") or p == ".git"
           for p in parts):
        return True
    if parts[0] == "libs":
        # Le filtre ne vise que les librairies : le code du plugin, lui,
        # garde ses eventuels fichiers de test.
        if any(p in LIB_EXCLUDE_DIRS for p in parts[1:]):
            return True
        if rel_path.endswith(LIB_EXCLUDE_SUFFIXES):
            return True
    for d in EXCLUDE_DIRS:
        if rel_path == d or rel_path.startswith(d + os.sep):
            return True
    if rel_path in EXCLUDE_FILES:
        return True
    return rel_path.endswith(EXCLUDE_SUFFIXES)


def main():
    root = os.path.dirname(os.path.abspath(__file__))
    out_dir = sys.argv[1] if len(sys.argv) > 1 else os.path.dirname(root)

    # Version depuis metadata.txt
    version = "0.0"
    with open(os.path.join(root, "metadata.txt"), encoding="utf-8") as f:
        for line in f:
            if line.strip().startswith("version="):
                version = line.split("=", 1)[1].strip()
                break

    zip_path = os.path.join(out_dir, f"{PLUGIN_NAME}_v{version}.zip")
    n, total = 0, 0
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for dirpath, dirnames, filenames in os.walk(root):
            rel_dir = os.path.relpath(dirpath, root)
            if rel_dir == ".":
                rel_dir = ""
            # élague les dossiers exclus (évite de les parcourir)
            dirnames[:] = [d for d in dirnames
                           if not _excluded(os.path.join(rel_dir, d))]
            for name in filenames:
                rel = os.path.join(rel_dir, name) if rel_dir else name
                if _excluded(rel):
                    continue
                full = os.path.join(dirpath, name)
                zf.write(full, os.path.join(PLUGIN_NAME, rel))
                n += 1
                total += os.path.getsize(full)

    print(f"{zip_path}")
    print(f"{n} fichiers, {total / 1e6:.1f} Mo source, "
          f"{os.path.getsize(zip_path) / 1e6:.1f} Mo compressé")


if __name__ == "__main__":
    main()
