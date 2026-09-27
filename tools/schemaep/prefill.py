# tools/schemaep/prefill.py
"""Schéma de départ d'un nœud AEP : l'appareil du nœud et ses raccordements.

Chaque conduite ou branchement qui touche le nœud devient une pièce
« Réseau existant » (diamètre, matériau, repère du nœud voisin). Au centre,
le favori le plus proche du type de nœud (montage personnel ou montage
type), diamètres adaptés aux conduites raccordées ; à défaut, la pièce
correspondant au type. Il est tourné pour que ses extrémités regardent les
conduites, puis le schéma est calé à l'horizontale / verticale la plus
proche (angles entre conduites conservés). Les pièces existantes s'y
raccordent quand une extrémité libre pointe dans leur direction (à 45° près).

Directions : azimut carte (0 = nord, sens horaire) → direction schéma
(0 = est, 90 = sud, y vers le bas) : wd = (az − 90) mod 360.
"""
import math

from qgis.core import QgsPointXY

from .. import reseaux as R
from ..aep_topo import _azimut
from ..spatial_utils import rect_request, nearest_point_feature
from ..stareau_values import materiau_code
from . import catalogue as C
from . import moteur as M
from .montages import MONTAGES

TOL = 0.05          # m : extrémité de conduite sur le nœud
ECART_MAX = 45      # ° : appariement conduite ↔ extrémité libre de l'appareil
RAYON_LIBRE = 60    # distance au centre d'une pièce existante non raccordée
ALIGNE = 150        # ° : au-delà, deux conduites sont en ligne ; en deçà, le nœud est sur un angle
DIST_CARREFOUR = 2.0   # m (le long de la conduite) : une vanne à cette distance appartient au carrefour
# appareils dont le montage contient déjà une vanne : ils ne ramassent pas de vannes voisines
NON_CARREFOUR = ('vanne', 'poteau_incendie', 'bouche_incendie', 'vidange')

# type de nœud CanaPlan → pièce SchemAEP posée au centre
PIECE_CENTRE = {'vanne': 'vanne', 'te': 'te', 'reducteur_dn': 'cone', 'coude': 'coude',
                'bouchon': 'bouchon', 'robinet_branchement': 'prise', 'compteur': 'compteur',
                'regard_compteur': 'compteur'}
# … ou montage type, par défaut
MONTAGE_CENTRE = {'ventouse': 'j-ventouse', 'vidange': 'j-vidange', 'poteau_incendie': 'j-pi',
                  'bouche_incendie': 'j-bi', 'reducteur_pression': 'j-reducteur-de-pression'}

# pièces caractéristiques de chaque type de nœud, pour choisir un favori
SIGNATURE = {'vanne': {'vanne', 'papillon'}, 'te': {'te'}, 'coude': {'coude'}, 'bouchon': {'bouchon'},
             'reducteur_dn': {'cone', 'bred'}, 'robinet_branchement': {'prise'},
             'regard_compteur': {'compteur'}, 'compteur': {'compteur'}, 'ventouse': {'ventouse'},
             'vidange': {'vidange'}, 'poteau_incendie': {'poteau'}, 'bouche_incendie': {'bi'},
             'reducteur_pression': {'rp'}}
# appareils propres à un type : un favori qui en contient d'un autre type est écarté
# (ex. branchement complet prise + compteur : le regard compteur a son propre schéma)
EXCLUSIFS = {'vanne', 'papillon', 'prise', 'compteur', 'ventouse', 'vidange', 'poteau', 'bi', 'rp'}

_MAT = {'fd': 'fd', 'fonte': 'fd', 'pvc': 'pvc', 'pvca': 'pvc', 'pehd': 'pe'}


def _mat(libelle):
    """(code SchemAEP, libellé à afficher si le matériau n'existe pas dans SchemAEP)."""
    code = materiau_code(libelle or '')
    if code in _MAT:
        return _MAT[code], ''
    return 'fd', (str(libelle) if libelle and str(libelle) != 'NULL' else '')


def _num(v):
    try:
        f = float(v)
        return None if math.isnan(f) else f
    except (TypeError, ValueError):
        return None


def _lignes(geom):
    if geom is None or geom.isEmpty():
        return []
    if geom.isMultipart():
        return [list(map(QgsPointXY, part)) for part in geom.asMultiPolyline()]
    return [list(map(QgsPointXY, geom.asPolyline()))]


def _nom_noeud(couche_noeuds, pt):
    if couche_noeuds is None or pt is None:
        return ''
    f, _d = nearest_point_feature(couche_noeuds, pt, TOL)
    if f is None:
        return ''
    v = f['nom'] if 'nom' in f.fields().names() else None
    if v is not None and str(v) not in ('', 'NULL'):
        return str(v)
    # nœud sans numéro (té, coude, bouchon…) : son type et son identifiant
    typ = f['type'] if 'type' in f.fields().names() else None
    typ = R.AEP_NOEUD_TYPE_DEFAUT if typ is None or str(typ) in ('', 'NULL') else str(typ)
    return '%s #%s' % (R.libelle_type(typ), f.id())


def raccordements(pt, couches):
    """Conduites et branchements AEP qui touchent le point pt :
    [{az, dn, mat, mat_txt, voisin, genre}], conduite principale en tête.
    Un branchement part du robinet (nœud) et arrive au regard compteur."""
    out = []
    noeuds = couches.get('regard')

    def ajouter(feat, az, voisin, genre, loin=None):
        mat, txt = _mat(feat['materiau'] if 'materiau' in feat.fields().names() else '')
        out.append({'az': az, 'dn': _num(feat['diametre']) if 'diametre' in feat.fields().names() else None,
                    'mat': 'pe' if genre == 'branchement' and txt else mat, 'mat_txt': txt,
                    'voisin': voisin, 'genre': genre, 'loin': loin, 'long': feat.geometry().length()})

    cond = couches.get('conduite')
    if cond is not None:
        for f in cond.getFeatures(rect_request(pt, TOL)):
            for line in _lignes(f.geometry()):
                if len(line) < 2:
                    continue
                if pt.distance(line[0]) <= TOL:
                    ajouter(f, _azimut(pt, line[1]), _nom_noeud(noeuds, line[-1]), 'conduite', line[-1])
                elif pt.distance(line[-1]) <= TOL:
                    ajouter(f, _azimut(pt, line[-2]), _nom_noeud(noeuds, line[0]), 'conduite', line[0])
                else:     # conduite qui traverse le nœud sans y être coupée (robinet de branchement)
                    g = f.geometry()
                    sq, _p, apres, _c = g.closestSegmentWithContext(pt)
                    if math.sqrt(sq) <= TOL:
                        i = max(1, min(apres, len(line) - 1))
                        ajouter(f, _azimut(pt, line[i]), _nom_noeud(noeuds, line[-1]), 'conduite')
                        ajouter(f, _azimut(pt, line[i - 1]), _nom_noeud(noeuds, line[0]), 'conduite')
    br = couches.get('branchement')
    if br is not None:
        for f in br.getFeatures(rect_request(pt, TOL)):
            for line in _lignes(f.geometry()):
                if len(line) < 2:
                    continue
                if pt.distance(line[0]) <= TOL:
                    ajouter(f, _azimut(pt, line[1]), '', 'branchement')
                elif pt.distance(line[-1]) <= TOL:
                    ajouter(f, _azimut(pt, line[-2]), _nom_noeud(noeuds, line[0]), 'branchement')
    out.sort(key=lambda r: (r['genre'] != 'conduite', -(r['dn'] or 0)))
    return out


def _dir(az):
    return (az - 90) % 360


# ---------------------------------------------------------------- carrefours
def _type(feat):
    typ = feat['type'] if 'type' in feat.fields().names() else None
    return R.AEP_NOEUD_TYPE_DEFAUT if typ is None or str(typ) in ('', 'NULL') else str(typ)


def est_carrefour(racc):
    """Té (3 conduites ou plus) ou angle (2 conduites non alignées)."""
    cond = [r for r in racc if r['genre'] == 'conduite']
    if len(cond) >= 3:
        return True
    return len(cond) == 2 and _ecart(_dir(cond[0]['az']), _dir(cond[1]['az'])) < ALIGNE


def satellites(couches):
    """Vannes à DIST_CARREFOUR ou moins d'un carrefour, le long d'une conduite :
    {clé de la vanne: (clé du carrefour, distance)} ; le plus proche l'emporte.
    Une vanne qui est elle-même un carrefour (posée sur l'angle) n'en fait pas partie."""
    noeuds, cond = (couches or {}).get('regard'), (couches or {}).get('conduite')
    out = {}
    if noeuds is None or cond is None:
        return out
    racc_cache = {}

    def carrefour(f):
        if f.id() not in racc_cache:
            racc_cache[f.id()] = est_carrefour(raccordements(QgsPointXY(f.geometry().asPoint()), couches))
        return racc_cache[f.id()]
    for c in cond.getFeatures():
        long = c.geometry().length()
        if long > DIST_CARREFOUR:
            continue
        lignes = _lignes(c.geometry())
        if not lignes or len(lignes[0]) < 2:
            continue
        bouts = [nearest_point_feature(noeuds, p, TOL)[0] for p in (lignes[0][0], lignes[-1][-1])]
        if None in bouts or bouts[0].id() == bouts[1].id():
            continue
        for v, cr in (bouts, bouts[::-1]):
            if _type(v) != 'vanne' or _type(cr) in NON_CARREFOUR or not carrefour(cr) or carrefour(v):
                continue
            k = ('regard', v.id())
            if k not in out or long < out[k][1]:
                out[k] = (('regard', cr.id()), long)
    return out


def racc_carrefour(pt, couches, cle, carte):
    """raccordements() du nœud cle, vannes satellites comprises : sur la
    branche d'une vanne, direction du bout de conduite court, mais diamètre,
    matériau et voisin de la conduite au-delà de la vanne ; 'vanne' = True,
    'rep' = son nom (vide si le point n'est pas numéroté : « Vanne #22 »
    dépend du fid, renouvelé à chaque enregistrement du .bet)."""
    racc = raccordements(pt, couches)
    noeuds = couches.get('regard')
    if not carte or noeuds is None:
        return racc
    for r in racc:
        if r['genre'] != 'conduite' or r.get('loin') is None or r['long'] > DIST_CARREFOUR:
            continue
        v, _d = nearest_point_feature(noeuds, r['loin'], TOL)
        if v is None or (carte.get(('regard', v.id())) or (None,))[0] != cle:
            continue
        vpt = QgsPointXY(v.geometry().asPoint())
        suite = next((s for s in raccordements(vpt, couches)
                      if s['genre'] == 'conduite' and (s.get('loin') is None or s['loin'].distance(pt) > TOL)), None)
        r['vanne'] = True
        r['rep'] = nom_reel(v)
        if suite:
            for k in ('dn', 'mat', 'mat_txt', 'voisin'):
                r[k] = suite[k]
        else:
            r['voisin'] = ''
    return racc


def realigner(schema):
    """Schéma enregistré tourné au quart de tour le plus proche (contenu
    inchangé) : rotation qui cale l'appareil principal (1re pièce hors
    réseau existant, tuyau ou annotation) sur un axe. Renvoie la rotation."""
    items = schema.get('items') or []
    ref = next((i for i in items if i['t'] not in ('existant', 'tuyau', 'texte', 'regard')), None) \
        or (items[0] if items else None)
    if ref is None:
        return 0
    r = ref['r'] % 360
    delta = round(r / 90.0) * 90 - r
    if abs(delta) < 0.01:
        return 0
    _tourner(items, delta)
    for it in items:      # restes d'arrondi (359,995°) calés sur l'axe ; pièces obliques inchangées
        axe = round(it['r'] / 90.0) * 90
        it['r'] = (axe if abs(it['r'] - axe) < 0.1 else round(it['r'], 6)) % 360
    return delta


def nom_reel(feat):
    """Nom saisi du point ('' si non numéroté)."""
    v = feat['nom'] if 'nom' in feat.fields().names() else None
    return '' if v is None or str(v) in ('', 'NULL') else str(v)


def vanne_en_angle(type_noeud, racc):
    """Vanne posée sur un angle de conduite : on ne sait pas sur quelle
    branche elle se trouve. Indices dans racc des 2 conduites, sinon None."""
    if type_noeud != 'vanne' or len(racc) != 2 or not est_carrefour(racc):
        return None
    return [0, 1]


def _ecart(a, b):
    return abs((a - b + 180) % 360 - 180)


def _tourner(items, delta):
    a = math.radians(delta)
    c, s = math.cos(a), math.sin(a)
    for it in items:
        x, y = it['x'], it['y']
        it['x'], it['y'] = x * c - y * s, x * s + y * c
        it['r'] = ((it['r'] + delta) % 360 + 360) % 360


def _ports_libres(S):
    G = S.graphe()
    return [(it, q) for it in S.items for q in M.wp(it) if G.libre(it, q)]


def _sans_te_principal(S):
    """Nœud en bout de branche (une seule conduite) : le té de piquage du
    montage type et ses deux tronçons sur la conduite principale n'ont pas
    lieu d'être ; la dérivation se raccorde directement à la conduite."""
    te = next((i for i in S.items if i['t'] == 'te'), None)
    if te is None:
        return
    G = S.graphe()
    retirer = {te['id']}
    for voisin, port in G.adj.get(te['id'], ()):
        v = S.get(voisin)
        # tronçons des ports 0 et 1 (conduite principale), libres à l'autre bout
        if port in (0, 1) and v and v['t'] == 'tuyau' and len(G.adj.get(voisin, ())) == 1:
            retirer.add(voisin)
    S.s['items'] = [i for i in S.items if i['id'] not in retirer]
    S.s['ok'] = {k: m for k, m in (S.s.get('ok') or {}).items()
                 if not any(k.startswith('%s:' % r) or ('|%s:' % r) in k for r in retirer)}


def _libres(items):
    g = M.Graphe(items)
    return sum(1 for it in items for q in M.wp(it) if g.libre(it, q))


def choisir_montage(type_noeud, n_racc, montages=None):
    """Favori le plus proche du type de nœud, ou None.

    Candidats : les favoris qui contiennent une pièce caractéristique du type
    et aucun appareil propre à un autre type (le montage type par défaut
    reste toujours candidat). Classement : nom du favori = libellé du type,
    montage personnel, montage type par défaut, puis nombre d'extrémités
    libres le plus proche du nombre de raccordements, puis le plus simple."""
    montages = MONTAGES if montages is None else montages
    sig = SIGNATURE.get(type_noeud, set())
    defaut = MONTAGE_CENTRE.get(type_noeud)
    # Le nom d'un favori se compare au libellé français du type (celui des
    # montages livrés) et à celui de la langue courante (favoris perso).
    from .. import i18n
    fr = (i18n.TR.get('aep_t_%s' % type_noeud) or {}).get('fr')
    libs = {M.sans_accents(x).strip() for x in (fr, R.libelle_type(type_noeud)) if x}
    best, best_cle = None, None
    for m in montages:
        items = m.get('items') or []
        ts = {i.get('t') for i in items}
        if m.get('id') != defaut and (not ts & sig or (ts & EXCLUSIFS) - sig):
            continue
        nom = M.sans_accents(m.get('nom') or '').strip()
        score = 10 if nom in libs else (5 if any(lib in nom for lib in libs) else 0)
        if not str(m.get('id', '')).startswith('j-'):
            score += 2
        if m.get('id') == defaut:
            score += 1
        try:
            libres = _libres(M.normalize({'items': items})['items'])
        except (KeyError, IndexError, TypeError, ValueError, AttributeError):   # favori illisible : ignoré
            continue
        cle = (score, -abs(libres - n_racc), -len(items))
        if best_cle is None or cle > best_cle:
            best, best_cle = m, cle
    return best


def _adapter_dn(S, racc):
    """Diamètres du favori posé → diamètres des conduites raccordées : ses
    diamètres distincts, du plus grand au plus petit, prennent ceux des
    raccordements (conduite principale puis branchement). Une même valeur
    d'origine donne partout la même valeur, les raccords internes restent
    cohérents."""
    cibles = []
    for r in racc:
        if r.get('dn') and (r['mat'], r['dn']) not in cibles:
            cibles.append((r['mat'], r['dn']))
    if not cibles:
        return
    champs = []
    for it in S.items:
        if it['t'] == 'existant':
            continue
        for f in C.T[it['t']].fields:
            if f['t'] == 'dn' and C.num(it['p'].get(f['k'])):
                champs.append((it, f))
    origines = sorted({C.num(it['p'][f['k']]) for it, f in champs}, reverse=True)
    corresp = dict(zip(origines, cibles))
    modifies = set()
    for it, f in champs:
        cible = corresp.get(C.num(it['p'][f['k']]))
        if not cible:
            continue
        mat_c, dn_c = cible
        m = f.get('m') or C.m_of(it['p'])
        if 'dl' in f and not C.T[it['t']].field('mat') and not f.get('m'):
            v = C.num(C.nom_dn(mat_c, dn_c))     # pièce sans matériau (compteur) : DN nominal, PE Ø25 → DN20
        else:
            v = dn_c if m == mat_c else C.conv_dn(mat_c, m, dn_c)
        liste = C.dn_list(it['p'], f)
        if liste:
            it['p'][f['k']] = C.nearest(liste, v)
            modifies.add(it['id'])
    for it in S.items:
        if it['id'] in modifies:
            M.fix_p(it)


def _robinet(montages):
    """Robinet des vannes de branche : celui du favori « vanne » (papillon ou
    robinet-vanne), sinon le robinet-vanne."""
    fav = choisir_montage('vanne', 2, montages)
    return next((i['t'] for i in (fav or {}).get('items', []) if i.get('t') in SIGNATURE['vanne']), 'vanne')


def _poser_vannes(S, racc, directions, montages):
    """Vanne raccordée à l'extrémité de l'appareil central en face de chaque
    branche marquée 'vanne' (satellite ou branche choisie), avec son repère."""
    tid = None
    for r, d in zip(racc, directions):
        if not r.get('vanne'):
            continue
        cands = [(it, q) for it, q in _ports_libres(S) if _ecart(q['wd'], d) <= ECART_MAX]
        if not cands:
            continue
        it, q = min(cands, key=lambda c: _ecart(c[1]['wd'], d))
        tid = tid or _robinet(montages)
        S.sel = {'id': it['id'], 'port': q['i']}
        v = S.ajouter(tid)
        v['p']['rep'] = r.get('rep') or ''
    S.sel = None


def _tubulures(S, racc, directions):
    """Pièces à deux diamètres (té, cône) : le petit diamètre (dn2) prend
    celui de la conduite en face de son extrémité, une fois l'appareil orienté."""
    for it in S.items:
        f2 = C.T[it['t']].field('dn2')
        if it['t'] == 'existant' or not f2 or f2.get('m'):
            continue
        ports = M.wp(it)
        if len(ports) < 3:
            continue
        q = ports[2]                      # extrémité de la tubulure (té : 3e extrémité)
        if not S.graphe().libre(it, q):   # déjà raccordée dans le montage : on n'y touche pas
            continue
        r = min(((r, d) for r, d in zip(racc, directions) if r.get('dn')),
                key=lambda rd: _ecart(rd[1], q['wd']), default=(None, None))[0]
        if r is None or _ecart(directions[racc.index(r)], q['wd']) > ECART_MAX:
            continue
        m = C.m_of(it['p'])
        v = r['dn'] if m == r['mat'] else C.conv_dn(r['mat'], m, r['dn'])
        liste = C.dn_list(it['p'], f2)
        if liste:
            it['p']['dn2'] = C.nearest(liste, v)
            M.fix_p(it)


def _poser_centre(S, type_noeud, racc, directions, montages=None):
    """Pose l'appareil du nœud au centre (0, 0). Faux s'il n'y en a pas."""
    princ = racc[0] if racc else None
    sp = {'k': 'C', 'mat': princ['mat'], 'dn': princ['dn']} if princ and princ.get('dn') else None
    m = choisir_montage(type_noeud, len(racc), montages)
    if m:
        S.poser_montage(m, (0, 0))
        if len(directions) <= 1:
            _sans_te_principal(S)
        _adapter_dn(S, racc)
        return True
    tid = PIECE_CENTRE.get(type_noeud)
    if not tid:
        return False
    t = C.T[tid]
    it = {'id': S.s['nid'], 't': tid, 'x': 0, 'y': 0, 'r': 0, 'f': 1, 'p': M._clone(t.p)}
    S.s['nid'] += 1
    if sp:
        M.inherit(it, sp)
    if tid == 'coude' and len(directions) >= 2:
        dev = 180 - _ecart(directions[0], directions[1])
        it['p']['ang'] = min((a for a, _l in C.ANG), key=lambda a: abs(a - dev))
    M.fix_p(it)
    S.items.append(it)
    _adapter_dn(S, racc)
    return True


def _orienter(S, directions):
    """Tourne l'appareil pour que ses extrémités libres regardent au mieux
    les conduites, calé au quart de tour le plus proche (schéma horizontal /
    vertical). Renvoie la rotation appliquée aux directions des conduites
    pour rester en face des extrémités (0 si rien à tourner)."""
    libres = _ports_libres(S)
    if not libres or not directions:
        return 0
    best = None
    for _it, q in libres:
        delta = directions[0] - q['wd']
        dirs = sorted(((q2['wd'] + delta) % 360 for _i2, q2 in libres))
        err = sum(min(_ecart(d, x) for x in dirs) for d in directions[:len(dirs)])
        if best is None or err < best[0]:
            best = (err, delta)
    delta = best[1]
    delta90 = round(delta / 90.0) * 90
    _tourner(S.items, delta90)
    return delta90 - delta


def _axe_libre(d, pris):
    """Quart de tour le plus proche de d qui n'est pas déjà pris."""
    for a in sorted((0, 90, 180, 270), key=lambda a: _ecart(a, d)):
        if a not in pris:
            return a
    return round(d / 90.0) * 90 % 360


def schema_noeud(type_noeud, racc, libelle='', montages=None):
    """Schéma de départ (dict au format .json) d'un nœud de type type_noeud
    raccordé à racc (voir raccordements()). montages : favoris où choisir
    l'appareil (None : montages types seuls)."""
    S = M.Schema()
    S.s['nom'] = libelle or ''
    directions = [_dir(r['az']) for r in racc]
    centre = _poser_centre(S, type_noeud, racc, directions, montages)
    if centre:
        decalage = _orienter(S, directions)
        S.undo = []
    else:
        decalage = (round(directions[0] / 90.0) * 90 - directions[0]) if directions else 0
    directions = [(d + decalage) % 360 for d in directions]
    if centre:
        _tubulures(S, racc, directions)
        _poser_vannes(S, racc, directions, montages)
    axes = set()
    pris = set()
    for r, d in zip(racc, directions):
        cible = None
        if centre:
            cands = [(it, q) for it, q in _ports_libres(S)
                     if M.cle(it, q) not in pris and _ecart(q['wd'], d) <= ECART_MAX and it['t'] != 'existant']
            if cands:
                cible = min(cands, key=lambda c: _ecart(c[1]['wd'], d))
        if cible:
            pris.add(M.cle(*cible))
            S.sel = {'id': cible[0]['id'], 'port': cible[1]['i']}
            ex = S.ajouter('existant')
        else:
            S.sel = None
            ex = S.ajouter('existant')
            d = _axe_libre(d, axes)       # pièce non raccordée : sur l'axe libre le plus proche
            axes.add(d)
            a = math.radians(d)
            ex['r'] = (d + 180) % 360
            rr = math.radians(ex['r'])
            px, py = RAYON_LIBRE * math.cos(a), RAYON_LIBRE * math.sin(a)
            ex['x'], ex['y'] = px - 20 * math.cos(rr), py - 20 * math.sin(rr)
        p = ex['p']
        p['mat'] = r['mat']
        if r['dn']:
            p['dn'] = C.nearest(C.MAT[r['mat']]['dn'], r['dn'])
        rep = []
        if r['genre'] == 'branchement':
            rep.append('branchement')
        if r['voisin']:
            rep.append('vers ' + r['voisin'])
        if r['mat_txt']:
            rep.append(r['mat_txt'])
        p['txt'] = ' – '.join(rep)
        M.fix_p(ex)
    S.sel = None
    return M.normalize(S.s)
