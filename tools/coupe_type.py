# tools/coupe_type.py
"""Coupe type d'un réseau, générée sans désigner de tronçon sur la carte.

L'outil Coupe transversale demande de tracer un axe : il produit la coupe
réelle à un endroit précis. Pour l'export groupé (dialogue Exporter), on a
besoin d'une coupe *représentative* du chantier, calculée sur les seules
statistiques du réseau :

* diamètre  → le plus fréquent parmi les conduites ;
* matériau  → le dominant parmi les conduites ;
* profondeur → la moyenne des (TN − fil d'eau) relevés sur les regards ;
* largeur   → celle de la configuration projet, comme partout ailleurs.

Le dessin lui-même est délégué à CoupeTransversaleDialog, qui sait déjà
mettre en page une liste de « crossings ». On l'instancie sans l'afficher,
puis on écrit la figure : aucune duplication du code de rendu.
"""
import os
from collections import Counter

import sip

from . import i18n
from .graph_utils import _to_float, QGIS_NULL


def _valeur_num(feat, champ):
    """Nombre d'un champ, ou None si le champ manque ou n'est pas numérique."""
    try:
        return _to_float(feat[champ])
    except KeyError:
        return None


def _valeur_texte(feat, champ):
    """Chaîne non vide d'un champ, ou '' si NULL / absent."""
    try:
        v = feat[champ]
    except KeyError:
        return ''
    if v is None or (QGIS_NULL is not None and v == QGIS_NULL):
        return ''
    return str(v).strip()


def _couche_vivante(couches, cle):
    """Couche utilisable, ou None si absente ou détruite côté C++."""
    couche = couches.get(cle) if couches else None
    if couche is None or sip.isdeleted(couche):
        return None
    return couche


def stats_reseau(couches, reseau, config):
    """Statistiques de la coupe type, ou None si les données sont trop pauvres.

    Renvoie un dict directement consommable comme « crossing » par
    CoupeTransversaleDialog, enrichi des effectifs ayant servi au calcul
    (nb_conduites / nb_regards) pour le compte rendu.
    """
    conduites = _couche_vivante(couches, 'conduite')
    regards   = _couche_vivante(couches, 'regard')
    if conduites is None or regards is None:
        return None

    # ── Diamètre le plus fréquent et matériau dominant ────────────────────
    diams = Counter()
    mats  = Counter()
    for feat in conduites.getFeatures():
        d = _valeur_num(feat, 'diametre')
        if d and d > 0:
            diams[round(d)] += 1
        mat = _valeur_texte(feat, 'materiau')
        if mat:
            mats[mat] += 1

    if not diams:
        return None

    diam_mm, nb_conduites = diams.most_common(1)[0]
    materiau = mats.most_common(1)[0][0] if mats else ''

    # ── TN moyen et profondeur moyenne, relevés sur les regards ───────────
    tns, profondeurs = [], []
    for feat in regards.getFeatures():
        tn = _valeur_num(feat, 'tn')
        fe = _valeur_num(feat, 'fe_radier')
        if tn is None:
            continue
        tns.append(tn)
        if fe is not None and tn - fe > 0:
            profondeurs.append(tn - fe)

    if not tns or not profondeurs:
        return None

    tn_moy   = sum(tns) / len(tns)
    prof_moy = sum(profondeurs) / len(profondeurs)

    largeur = config.get(f'largeur_conduite_{reseau.lower()}', 0.80)

    return {
        'x':            0.0,
        'tn':           tn_moy,
        'fe':           tn_moy - prof_moy,
        'diam_m':       diam_mm / 1000.0,
        'materiau':     materiau,
        'reseau':       reseau,
        'width':        largeur,
        'nom_amont':    i18n.tr('exp_coupe_type', code=reseau),
        'nom_aval':     '',
        # Informations de compte rendu, ignorées par le dessin
        'diam_mm':      diam_mm,
        'profondeur':   prof_moy,
        'nb_conduites': nb_conduites,
        'nb_regards':   len(profondeurs),
    }


def exporter_coupe_type(couches, config, reseau, out_dir,
                        fmt='pdf', paper='a4_paysage', parent=None):
    """Écrit la coupe type du réseau dans out_dir.

    Retourne (chemin, stats) en cas de succès, (None, None) si le réseau
    ne fournit pas de quoi construire une coupe.
    """
    stats = stats_reseau(couches, reseau, config)
    if stats is None:
        return None, None

    from ..gui.coupe_transversale_dialog import (
        CoupeTransversaleDialog, PAPER_SIZES,
    )

    # Le dialogue dessine dès sa construction ; il n'est jamais affiché.
    dlg = CoupeTransversaleDialog([stats], config, parent, cut_line_pts=None)
    try:
        index = dlg.fmt_combo.findData(paper)
        if index >= 0 and index != dlg.fmt_combo.currentIndex():
            dlg.fmt_combo.setCurrentIndex(index)   # déclenche _refresh()

        ext  = 'png' if fmt.lower() == 'png' else 'pdf'
        path = os.path.join(out_dir, f"coupe_type_{reseau}.{ext}")

        w_mm, h_mm = PAPER_SIZES[dlg.fmt_combo.currentData()]
        old_size = dlg.figure.get_size_inches()
        dlg.figure.set_size_inches(w_mm / 25.4, h_mm / 25.4)
        dlg.figure.savefig(path, format=ext,
                           dpi=300 if ext == 'png' else 150,
                           bbox_inches=None)
        dlg.figure.set_size_inches(*old_size)
    finally:
        dlg.deleteLater()

    return path, stats
