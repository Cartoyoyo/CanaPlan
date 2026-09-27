# tools/schemaep/stockage.py
"""Schémas SchemAEP rattachés aux nœuds AEP d'un projet CanaPlan.

En session, les schémas vivent en mémoire sur le plugin (`plugin._schemas_aep`),
indexés par la clé (rôle de la couche, fid) : ('regard', fid) pour un nœud AEP,
('tabouret', fid) pour un regard compteur de la couche des compteurs. À l'enregistrement du .bet, ils sont écrits dans
la table `schema_aep` (sans géométrie) de data.gpkg ; au chargement, ils sont
relus et rattachés aux nœuds.

Les fid changent entre deux enregistrements (les couches passent par la
mémoire) : sur disque, un schéma est repéré par le nom du nœud et sa
position (et sa couche, colonne `couche`). Au chargement : même nom et à moins de 1 m, sinon nœud le plus
proche à moins de TOLERANCE. Un schéma qui ne retrouve pas son nœud est
gardé à part (orphelin) et réécrit tel quel au prochain enregistrement.
"""
import json
import math
from datetime import datetime

from qgis.core import (Qgis, QgsFeature, QgsField, QgsFields, QgsMemoryProviderUtils, QgsVectorFileWriter,
                       QgsVectorLayer, QgsCoordinateTransformContext)
from qgis.PyQt.QtCore import QMetaType

TABLE = 'schema_aep'
TOLERANCE = 0.05       # m : nœud déplacé ou renommé, rattachement par position
TOLERANCE_NOM = 1.0    # m : même nom, légèrement déplacé
ROLES = ('regard', 'tabouret')     # couches porteuses de schémas


def _texte(v):
    return '' if v is None or str(v) == 'NULL' else str(v)


def _noeud_infos(feat, role='regard'):
    g = feat.geometry()
    p = g.asPoint() if g and not g.isEmpty() else None
    nom = feat['nom'] if 'nom' in feat.fields().names() else ''
    typ = feat['type'] if 'type' in feat.fields().names() else ''
    return {'nom': _texte(nom), 'type': _texte(typ), 'couche': role,
            'x': p.x() if p else None, 'y': p.y() if p else None}


def porte_schema(role, feat):
    """Vrai si l'entité peut porter un schéma : tout nœud AEP, et dans la
    couche des compteurs les seuls regards compteur (pas les extrémités libres)."""
    if role == 'regard':
        return True
    if role != 'tabouret':
        return False
    typ = feat['type'] if 'type' in feat.fields().names() else None
    return _texte(typ) in ('', 'regard_compteur')


def entite(couches, cle):
    """Entité désignée par la clé (rôle, fid), ou None."""
    if not couches or not cle:
        return None
    couche = couches.get(cle[0])
    if couche is None:
        return None
    f = couche.getFeature(cle[1])
    return f if f.isValid() else None


def _candidats(couches):
    """{rôle: [(clé, infos)]} des entités pouvant porter un schéma."""
    out = {}
    for role in ROLES:
        couche = (couches or {}).get(role)
        lst = out.setdefault(role, [])
        if couche is None:
            continue
        for f in couche.getFeatures():
            if porte_schema(role, f):
                i = _noeud_infos(f, role)
                if i['x'] is not None:
                    lst.append(((role, f.id()), i))
    return out


class Magasin:
    """Schémas du projet : {(rôle, fid): {'schema', 'svg', 'date'}} + orphelins."""

    def __init__(self):
        self.schemas = {}
        self.orphelins = []     # entrées lues sur disque sans nœud correspondant

    def __len__(self):
        return len(self.schemas)

    def get(self, cle):
        return self.schemas.get(cle)

    def mettre(self, cle, schema, svg):
        self.schemas[cle] = {'schema': schema, 'svg': svg, 'date': datetime.now().strftime('%Y-%m-%d %H:%M')}

    def supprimer(self, cle):
        self.schemas.pop(cle, None)

    def vider(self):
        self.schemas.clear()
        self.orphelins = []

    def tous(self, couches=None):
        """[(clé, entrée, infos du nœud)] triés par nom de nœud."""
        out = []
        for cle, e in self.schemas.items():
            f = entite(couches, cle)
            out.append((cle, e, _noeud_infos(f, cle[0]) if f is not None else {}))
        return sorted(out, key=lambda t: (t[2].get('nom') or '~', t[0]))


def instantane(magasin, couches):
    """Entrées à écrire : [{nom, x, y, type, couche, schema, svg, date}], lues
    sur les nœuds tant que leurs fid sont valides (avant que l'enregistrement
    du .bet ne retire les couches). Un nœud supprimé emporte son schéma."""
    out = []
    for cle, e in magasin.schemas.items():
        nf = entite(couches, cle)
        if nf is None:
            continue
        d = _noeud_infos(nf, cle[0])
        d.update(schema=e['schema'], svg=e['svg'], date=e['date'])
        out.append(d)
    return out + [dict(o) for o in magasin.orphelins]


def infos_noeud(couches, cle):
    f = entite(couches, cle)
    return _noeud_infos(f, cle[0]) if f is not None else None


def retrouver(couches, infos):
    """Clé actuelle du nœud décrit par infos (nom, x, y, couche), ou None."""
    if not couches or not infos:
        return None
    return _rattacher(infos, _candidats(couches).get(infos.get('couche') or 'regard', []), set())


def ecrire_gpkg(entrees, gpkg_path, contexte=None):
    """Écrit la table schema_aep dans gpkg_path (couche remplacée). Renvoie
    un message d'erreur ou ''."""
    if not entrees:
        return ''
    champs = QgsFields()
    for nom, t in (('noeud_nom', QMetaType.Type.QString), ('x', QMetaType.Type.Double),
                   ('y', QMetaType.Type.Double), ('type', QMetaType.Type.QString),
                   ('couche', QMetaType.Type.QString),
                   ('schema_json', QMetaType.Type.QString), ('schema_svg', QMetaType.Type.QString),
                   ('date', QMetaType.Type.QString)):
        champs.append(QgsField(nom, t))
    mem = QgsMemoryProviderUtils.createMemoryLayer(TABLE, champs, Qgis.WkbType.NoGeometry)
    feats = []
    for d in entrees:
        f = QgsFeature(champs)
        f.setAttributes([d.get('nom') or '', d.get('x'), d.get('y'), d.get('type') or '',
                         d.get('couche') or 'regard',
                         json.dumps(d['schema'], ensure_ascii=False), d.get('svg') or '', d.get('date') or ''])
        feats.append(f)
    mem.dataProvider().addFeatures(feats)
    opts = QgsVectorFileWriter.SaveVectorOptions()
    opts.driverName = 'GPKG'
    opts.layerName = TABLE
    opts.actionOnExistingFile = QgsVectorFileWriter.ActionOnExistingFile.CreateOrOverwriteLayer
    err, msg, _a, _b = QgsVectorFileWriter.writeAsVectorFormatV3(
        mem, gpkg_path, contexte or QgsCoordinateTransformContext(), opts)
    return '' if err == QgsVectorFileWriter.WriterError.NoError else '%s : %s' % (TABLE, msg)


def lire_gpkg(gpkg_path, couches):
    """Relit la table schema_aep et rattache chaque schéma à son nœud
    (tables d'avant la colonne `couche` : tous sur la couche des nœuds)."""
    mag = Magasin()
    lay = QgsVectorLayer('%s|layername=%s' % (gpkg_path, TABLE), TABLE, 'ogr')
    if not lay.isValid():
        return mag
    cands = _candidats(couches)
    avec_couche = 'couche' in lay.fields().names()
    pris = set()
    for f in lay.getFeatures():
        try:
            schema = json.loads(_texte(f['schema_json']) or 'null')
        except ValueError:
            continue
        if not isinstance(schema, dict):
            continue
        infos = {'nom': _texte(f['noeud_nom']), 'type': _texte(f['type']),
                 'couche': (_texte(f['couche']) if avec_couche else '') or 'regard',
                 'x': f['x'] if _texte(f['x']) else None, 'y': f['y'] if _texte(f['y']) else None}
        cle = _rattacher(infos, cands.get(infos['couche'], []), pris)
        if cle is None:
            infos.update(schema=schema, svg=_texte(f['schema_svg']), date=_texte(f['date']))
            mag.orphelins.append(infos)
            continue
        pris.add(cle)
        mag.schemas[cle] = {'schema': schema, 'svg': _texte(f['schema_svg']), 'date': _texte(f['date'])}
    return mag


def _rattacher(infos, noeuds, pris):
    if infos['x'] is None:
        cands = [(0, fid) for fid, n in noeuds if infos['nom'] and n['nom'] == infos['nom'] and fid not in pris]
        return cands[0][1] if len(cands) == 1 else None
    x, y = float(infos['x']), float(infos['y'])
    best, bd = None, None
    for fid, n in noeuds:
        if fid in pris:
            continue
        d = math.hypot(n['x'] - x, n['y'] - y)
        if infos['nom'] and n['nom'] == infos['nom'] and d <= TOLERANCE_NOM:
            return fid
        if d <= TOLERANCE and (bd is None or d < bd):
            best, bd = fid, d
    return best
