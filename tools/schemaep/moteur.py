# tools/schemaep/moteur.py
"""Moteur SchemAEP : schéma, raccordements, contrôles et nomenclature.

Un schéma est un dict {items, nid, nom, ok} ; chaque pièce posée est un dict
{id, t, x, y, r, f, p} avec en option lo (décalage d'étiquette posé à la
main) et eo (types d'extrémité imposés point par point). C'est le format
.json de la page HTML SchemAEP.

`Schema` porte l'état d'édition (sélection, annulation) et les opérations ;
les fonctions de module sont sans état.
"""
import copy
import json
import math
import unicodedata

from .catalogue import (T, ENDN, MAT, PI, r1, num, n, egal, nearest, m_of, fdn,
                        fmt, nom_dn, conv_dn, ok_pair, sug, dn_list, opt_list)
from .langue import traduire, unite


# ---------------------------------------------------------------- paramètres
def fix_p(it):
    """Ramène chaque paramètre dans les valeurs permises par la pièce."""
    t, p = T[it['t']], it['p']
    for f in t.fields:
        if f['t'] == 'num':
            p[f['k']] = max(0, num(p.get(f['k'])))
            continue
        if f['t'] not in ('dn', 'sel', 'mat'):
            continue
        o = opt_list(p, f)
        if not o:
            continue
        v = [x[0] for x in o]
        if not any(egal(x, p.get(f['k'])) for x in v):
            p[f['k']] = nearest(v, p.get(f['k'])) if f['t'] == 'dn' else v[0]


def inherit(it, sp):
    """Nouvelle pièce raccordée au point sp : même matériau et diamètre,
    et une variante d'extrémités compatible."""
    t, p = T[it['t']], it['p']
    fm = next((f for f in t.fields if f['t'] == 'mat'), None)
    if fm and sp.get('mat') and sp['mat'] in fm['o']:
        p['mat'] = sp['mat']
    if sp.get('dn'):
        for f in t.fields:
            if f['t'] != 'dn' or f['k'] == 'dn2':
                continue
            m = f.get('m') or m_of(p)
            if f.get('raw'):
                v = nom_dn(sp['mat'], sp['dn'])
            elif m == sp['mat']:
                v = sp['dn']
            else:
                v = conv_dn(sp['mat'], m, sp['dn'])
            p[f['k']] = nearest(dn_list(p, f), v)
    f2 = t.field('dn2')
    if f2:
        L = dn_list(p, f2)
        lo = [d for d in L if d < num(p['dn'])]
        if L:
            if t.dn2def:
                p['dn2'] = nearest(L, t.dn2def)
            elif t.eq2:
                p['dn2'] = nearest(L, p['dn'])
            else:
                p['dn2'] = lo[-1] if lo else L[0]
    fix_p(it)
    fe = t.field('ext')
    if fe and not t.no_auto:
        def good(v):
            q = dict(p, ext=v)
            return any(ok_pair(pp['k'], sp['k'], (pp.get('mat') or m_of(q)) == 'pe' and sp.get('mat') == 'pe')
                       for pp in t.ports(q))
        if not good(p['ext']):
            g = next((x[0] for x in opt_list(p, fe) if good(x[0])), None)
            if g:
                p['ext'] = g


# ---------------------------------------------------------------- géométrie
def pts(it):
    """Extrémités locales, avec les types imposés à la main (it['eo'])."""
    ps = T[it['t']].ports(it['p'])
    eo = it.get('eo')
    if eo:
        ps = [dict(q, k=eo[str(i)]) if eo.get(str(i)) else q for i, q in enumerate(ps)]
    return ps


def wp(it):
    """Extrémités en coordonnées du schéma : wx, wy, direction wd, n° i."""
    f = -1 if it.get('f', 1) < 0 else 1
    a = it['r'] * PI / 180
    c, s = math.cos(a), math.sin(a)
    out = []
    for i, q in enumerate(pts(it)):
        y = q['y'] * f
        d = (360 - q['d']) % 360 if f < 0 else q['d']
        w = dict(q)
        w.update(i=i, mat=q.get('mat') or it['p'].get('mat') or 'fd',
                 wx=it['x'] + q['x'] * c - y * s, wy=it['y'] + q['x'] * s + y * c,
                 wd=r1(((d + it['r']) % 360 + 360) % 360))
        out.append(w)
    return out


class Graphe:
    """Liaisons entre extrémités coïncidentes (à 2 unités près).
    con : clés « id:n° » raccordées ; adj : voisins par pièce ;
    L : paires ((pièce, extrémité), (pièce, extrémité))."""

    def __init__(self, items):
        H, self.con, self.adj, self.L = {}, set(), {}, []
        for it in items:
            for q in wp(it):
                b = (it, q)
                cx, cy = math.floor(q['wx'] / 4), math.floor(q['wy'] / 4)
                for i in (-1, 0, 1):
                    for j in (-1, 0, 1):
                        for a in H.get((cx + i, cy + j), ()):
                            if a[0] is it:
                                continue
                            if abs(a[1]['wx'] - q['wx']) < 2 and abs(a[1]['wy'] - q['wy']) < 2:
                                self.con.add(cle(a[0], a[1]))
                                self.con.add(cle(it, q))
                                self.adj.setdefault(a[0]['id'], []).append((it['id'], a[1]['i']))
                                self.adj.setdefault(it['id'], []).append((a[0]['id'], q['i']))
                                self.L.append((a, b))
                H.setdefault((cx, cy), []).append(b)

    def libre(self, it, q):
        return cle(it, q) not in self.con


def cle(it, q):
    return '%s:%s' % (it['id'], q['i'])


def cle_liaison(a, b):
    return '|'.join(sorted((cle(*a), cle(*b))))


def comp(start, excl, G):
    """Pièces reliées aux pièces start, sans passer par la pièce excl."""
    seen, st = set(start), list(start)
    while st:
        i = st.pop()
        for j, _pi in G.adj.get(i, ()):
            if j != excl and j not in seen:
                seen.add(j)
                st.append(j)
    return seen


# ---------------------------------------------------------------- contrôles
def chk(a, b):
    """Défaut d'assemblage entre deux extrémités raccordées (None si bon)."""
    A, B = a[1], b[1]
    na, nb = T[a[0]['t']].nom, T[b[0]['t']].nom
    pe = A['mat'] == 'pe' and B['mat'] == 'pe'
    if not ok_pair(A['k'], B['k'], pe):
        return '%s (%s) ↔ %s (%s) : assemblage impossible → %s' % (na, ENDN[A['k']], nb, ENDN[B['k']], sug(A['k'], B['k']))
    dev = abs(((A['wd'] - B['wd']) % 360 + 360) % 360 - 180)
    if dev > 1:
        return '%s ↔ %s : pièces non alignées (%s°)' % (na, nb, n(math.floor(dev + 0.5)))
    if A.get('any') or B.get('any') or A['k'] == 'C' or B['k'] == 'C' or not A.get('dn') or not B.get('dn'):
        return None
    if A['k'] == 'B' and B['k'] == 'B':
        da, db = nom_dn(A['mat'], A['dn']), nom_dn(B['mat'], B['dn'])
        if num(da) != num(db):
            return '%s ↔ %s : brides DN%s / DN%s → bride de réduction ou cône' % (na, nb, n(da), n(db))
        return None
    if A['mat'] != B['mat']:
        return '%s %s (%s) ↔ %s %s (%s) : matériaux différents → raccord universel / adaptateur' % (
            na, fdn(A['mat'], A['dn']), MAT[A['mat']]['nom'], nb, fdn(B['mat'], B['dn']), MAT[B['mat']]['nom'])
    if not egal(A['dn'], B['dn']):
        return '%s %s ↔ %s %s : diamètres différents → cône / réduction' % (na, fdn(A['mat'], A['dn']), nb, fdn(B['mat'], B['dn']))
    return None


# ---------------------------------------------------------------- nomenclature
def _extras(t, p):
    r = []
    if p.get('but'):
        r.append({'d': 'Massif de butée béton – %s %s' % (t.nom.lower(), fmt(p)), 'q': 1, 'u': 'u'})
    if p.get('bac'):
        r.append({'d': 'Bouche à clé + tube allonge + tige de manœuvre', 'q': 1, 'u': 'u'})
    if p.get('reg') is True:
        r.append({'d': 'Regard de visite pour appareil', 'q': 1, 'u': 'u'})
    return r


def cle_tri(s):
    """Tri alphabétique à la française, comme localeCompare('fr') : accents
    ignorés au premier niveau ; espaces, ponctuation, symboles et chiffres
    avant les lettres."""
    prim = []
    for c in unicodedata.normalize('NFD', str(s).casefold()):
        if unicodedata.combining(c):
            continue
        cat = unicodedata.category(c)
        if c.isspace():
            prim.append((0, 0, c))
        elif cat[0] == 'P':
            prim.append((1, 0, c))
        elif cat[0] == 'S':
            prim.append((2, 0, c))
        elif cat[0] == 'N':
            prim.append((3, unicodedata.numeric(c, 0), c))
        else:
            prim.append((4, 0, c))
    return (prim, str(s))


def lignes_piece(it):
    """Lignes de nomenclature d'une pièce : [{d, q, u}, …]."""
    t = T[it['t']]
    if not t.bom:
        return []
    r = t.bom(it['p'])
    r = r if isinstance(r, list) else [r]
    return [x for x in r + _extras(t, it['p']) if x and x.get('q')]


def bom(items):
    """Nomenclature regroupée par désignation et unité, triée."""
    m = {}
    for it in items:
        for x in lignes_piece(it):
            k = (x['d'], x['u'])
            if k in m:
                m[k]['q'] += num(x['q'])
            else:
                m[k] = {'d': x['d'], 'q': num(x['q']), 'u': x['u']}
    # affichage : désignations et unités dans la langue de l'interface
    r = [dict(b, d=traduire(b['d']), u=unite(b['u'])) for b in m.values()]
    return sorted(r, key=lambda b: cle_tri(b['d']))


def fq(q):
    """Quantité au format français (2 décimales au plus)."""
    v = r1(num(q))
    s = n(v).replace('.', ',')
    if ',' not in s and abs(v) >= 1000:
        s = '{:,}'.format(int(v)).replace(',', ' ')
    return s


def csv_nomenclature(items):
    lignes = ['\ufeff' + traduire('Désignation;Quantité;Unité')]
    for b in bom(items):
        lignes.append('"%s";%s;%s' % (b['d'].replace('"', '""'), n(r1(b['q'])).replace('.', ','), b['u']))
    return '\n'.join(lignes)


# ---------------------------------------------------------------- étiquettes
def lbl_pos(it):
    """Position par défaut de l'étiquette : x, y, ancrage (start/middle/end),
    et point d'accroche ax, ay du connecteur sur la pièce."""
    t = T[it['t']]
    x, y, nx, ny = t.la(it['p']) if t.la else (0, 12, 0, 1)
    f = -1 if it.get('f', 1) < 0 else 1
    a = it['r'] * PI / 180
    c, s = math.cos(a), math.sin(a)
    lx, ly = x + nx * 10, (y + ny * 10) * f
    Nx, Ny = nx * c - ny * f * s, nx * s + ny * f * c
    return {'x': it['x'] + lx * c - ly * s,
            'y': it['y'] + lx * s + ly * c + (9 if Ny > 0.7 else -2 if Ny < -0.7 else 4),
            'anc': ('start' if Nx > 0 else 'end') if abs(Nx) > 0.6 else 'middle',
            'ax': it['x'] + x * c - y * f * s, 'ay': it['y'] + x * s + y * f * c}


def wbox(it, b):
    """Boîte englobante monde d'une pièce à partir de sa boîte locale
    b = (x, y, largeur, hauteur)."""
    f = -1 if it.get('f', 1) < 0 else 1
    a = it['r'] * PI / 180
    c, s = math.cos(a), math.sin(a)
    X, Y = [], []
    for x, v in ((b[0], b[1]), (b[0] + b[2], b[1]), (b[0], b[1] + b[3]), (b[0] + b[2], b[1] + b[3])):
        y = v * f
        X.append(it['x'] + x * c - y * s)
        Y.append(it['y'] + x * s + y * c)
    return {'id': it['id'], 'x0': min(X), 'y0': min(Y), 'x1': max(X), 'y1': max(Y)}


LCW, LCELL = 6.1, 40
LOFF = sorted(((i * 20, j * 14) for i in range(-5, 6) for j in range(-7, 8) if i or j),
              key=lambda o: math.hypot(o[0] * .7, o[1]))


def _hit(a, b):
    return a['x0'] < b['x1'] and b['x0'] < a['x1'] and a['y0'] < b['y1'] and b['y0'] < a['y1']


def _lbl_box(x, y, anc, w):
    x0 = x if anc == 'start' else x - w if anc == 'end' else x - w / 2
    return {'x0': x0, 'y0': y - 10, 'x1': x0 + w, 'y1': y + 3}


def etiquettes(items, obs, largeur=None):
    """Place les étiquettes sans chevauchement : position par défaut si elle
    est libre, sinon la position libre la plus proche (1er passage : ni
    étiquette ni autre pièce, 2e passage : aucune étiquette). Les étiquettes
    déplacées à la main (lo) passent d'abord. obs : boîtes des pièces
    (wbox). largeur(texte) : largeur du texte, estimée par défaut.

    Renvoie [{id, txt, x, y, anc, man, dx, dy, lien: (ax, ay, px, py) ou None}]."""
    largeur = largeur or (lambda s: len(s) * LCW)
    H = {}

    def cells(b):
        return [(i, j) for i in range(math.floor(b['x0'] / LCELL), math.floor(b['x1'] / LCELL) + 1)
                for j in range(math.floor(b['y0'] / LCELL), math.floor(b['y1'] / LCELL) + 1)]

    def put(b):
        for k in cells(b):
            H.setdefault(k, []).append(b)

    def free(b, id_, pc):
        return not any((o.get('lb') or (pc and o.get('id') != id_)) and _hit(o, b)
                       for k in cells(b) for o in H.get(k, ()))

    for b in obs:
        put(b)
    out = []
    for it in sorted(items, key=lambda i: 0 if i.get('lo') else 1):
        t = T[it['t']]
        if not t.lbl:
            continue
        txt = traduire(str(t.lbl(it['p']) or ''))
        if not txt:
            continue
        l = lbl_pos(it)
        w = largeur(txt) + 4
        b = _lbl_box(l['x'], l['y'], l['anc'], w)
        dx = dy = 0
        if it.get('lo'):
            dx, dy = it['lo']
            b = _lbl_box(l['x'] + dx, l['y'] + dy, l['anc'], w)
        elif not free(b, it['id'], True):
            trouve = False
            for pc in (True, False):
                for ox, oy in LOFF:
                    c = _lbl_box(l['x'] + ox, l['y'] + oy, l['anc'], w)
                    if free(c, it['id'], pc):
                        dx, dy, b, trouve = ox, oy, c, True
                        break
                if trouve:
                    break
        b['lb'] = 1
        put(b)
        px = max(b['x0'], min(l['ax'], b['x1']))
        py = max(b['y0'], min(l['ay'], b['y1']))
        lien = (l['ax'], l['ay'], px, py) if math.hypot(px - l['ax'], py - l['ay']) > 3 else None
        out.append({'id': it['id'], 'txt': txt, 'x': l['x'] + dx, 'y': l['y'] + dy, 'anc': l['anc'],
                    'man': bool(it.get('lo')), 'dx': dx, 'dy': dy, 'lien': lien})
    return out


# ---------------------------------------------------------------- chargement
def _clone(v):
    return copy.deepcopy(v)


def _somme(valeurs):
    """Somme de gauche à droite, sans la compensation de sum() (Python 3.12) :
    mêmes arrondis que la page HTML, donc mêmes positions au centième."""
    t = 0
    for v in valeurs:
        t += v
    return t


def normalize(s):
    """Contrôle d'un schéma chargé (fichier, montage) : types connus, valeurs
    valides, identifiants uniques ; les anciens schémas sont migrés."""
    s = s if isinstance(s, dict) else {}
    o = {'items': [], 'nid': 1, 'nom': str(s.get('nom') or '')}
    used = set()
    for i in (s.get('items') if isinstance(s.get('items'), list) else []):
        if not isinstance(i, dict) or i.get('t') not in T:
            continue
        t = T[i['t']]
        d = _clone(t.p)
        src = i.get('p') if isinstance(i.get('p'), dict) else {}
        for k in d:
            if k not in src or src[k] is None:
                continue
            v = src[k]
            if isinstance(d[k], bool):
                d[k] = bool(v)
            elif isinstance(d[k], (int, float)):
                d[k] = num(v, d[k])
            else:
                d[k] = str(v)
        if t.legacy:
            for k, v in t.legacy.items():
                if k not in src:
                    d[k] = v
        id_ = num(i.get('id'))
        id_ = int(math.floor(id_)) if id_ > 0 else 0
        if not id_ or id_ in used:
            id_ = 0
        else:
            used.add(id_)
        it = {'id': id_, 't': i['t'], 'x': num(i.get('x')), 'y': num(i.get('y')),
              'r': (num(i.get('r')) % 360 + 360) % 360, 'f': -1 if num(i.get('f'), 1) < 0 else 1, 'p': d}
        lo = i.get('lo')
        if isinstance(lo, list) and len(lo) == 2 and all(num(v, None) is not None for v in lo):
            it['lo'] = [num(lo[0]), num(lo[1])]
        if isinstance(i.get('eo'), dict):
            eo = {str(k): v for k, v in i['eo'].items() if str(k).isdigit() and v in ENDN}
            if eo:
                it['eo'] = eo
        try:
            fix_p(it)
        except Exception:
            it['p'] = _clone(t.p)
        o['items'].append(it)
    nxt = max([1] + [it['id'] + 1 for it in o['items']])
    for it in o['items']:
        if not it['id']:
            it['id'] = nxt
            nxt += 1
    o['nid'] = max(num(s.get('nid'), 1) or 1, nxt)
    if isinstance(s.get('ok'), dict):
        o['ok'] = {k: v for k, v in s['ok'].items() if isinstance(v, str)}
    # géométrie legacy (ex. tubulure de té longue) ramenée à l'actuelle ; les pièces raccordées suivent
    tmp = Schema(o)
    for it in o['items']:
        t = T[it['t']]
        for k in (t.legacy or {}):
            if it['p'].get(k) != t.p[k]:
                tmp.change(it, lambda it=it, k=k: it['p'].__setitem__(k, T[it['t']].p[k]))
    return o


def charger_json(texte):
    d = json.loads(texte)
    if not isinstance(d, dict):
        raise ValueError(traduire('format inconnu'))
    return normalize(d if 'items' in d else d.get('S') or {})


def vers_json(s):
    return json.dumps(s, ensure_ascii=False, indent=1)


# ---------------------------------------------------------------- édition
class Schema:
    """Schéma en cours d'édition : état (dict au format .json), sélection
    (sel = {'id', 'port'} ou None) et pile d'annulation."""

    ANNUL_MAX = 100

    def __init__(self, s=None):
        self.s = s if s is not None else {'items': [], 'nid': 1, 'nom': ''}
        self.sel = None
        self.undo = []

    # --- état
    @property
    def items(self):
        return self.s['items']

    def get(self, id_):
        return next((i for i in self.items if i['id'] == id_), None)

    def cur(self):
        return self.get(self.sel['id']) if self.sel else None

    def graphe(self):
        return Graphe(self.items)

    def snap(self):
        self.undo.append(json.dumps(self.s))
        if len(self.undo) > self.ANNUL_MAX:
            self.undo.pop(0)

    def annuler(self):
        if not self.undo:
            return False
        self.s = json.loads(self.undo.pop())
        self.sel = None
        return True

    def nouveau(self):
        self.snap()
        self.s = {'items': [], 'nid': 1, 'nom': ''}
        self.sel = None

    def effacer_tout(self):
        """Retire toutes les pièces (annulable) ; le nom du schéma reste."""
        if not self.items:
            return False
        self.snap()
        self.s['items'] = []
        self.s.pop('ok', None)
        self.sel = None
        return True

    def charger(self, s):
        self.snap()
        self.s = normalize(s)
        self.sel = None

    # --- point de raccordement courant
    def point_courant(self, G=None):
        """Extrémité sélectionnée, ou première extrémité libre de la pièce
        sélectionnée (None sinon)."""
        c0 = self.cur()
        if not c0:
            return None
        G = G or self.graphe()
        ps = wp(c0)
        if self.sel.get('port') is not None:
            return ps[self.sel['port']] if self.sel['port'] < len(ps) else None
        return next((q for q in ps if G.libre(c0, q)), None)

    # --- ajout
    def ajouter(self, tid, centre=(0, 0)):
        """Pose une pièce, raccordée au point courant s'il y en a un, sinon
        au centre de la vue ; sélectionne le point suivant pour enchaîner."""
        t = T[tid]
        self.snap()
        it = {'id': self.s['nid'], 't': tid, 'x': 0, 'y': 0, 'r': 0, 'f': 1, 'p': _clone(t.p)}
        self.s['nid'] += 1
        sp = self.point_courant()
        if sp:
            inherit(it, sp)
            k = attacher(it, sp)
            self.items.append(it)
            if k >= 0:
                ps = pts(it)
                nx = next((i for i, q in enumerate(ps) if i != k and ((q['d'] - ps[k]['d'] + 360) % 360) == 180), -1)
                if nx < 0:
                    nx = next((i for i in range(len(ps)) if i != k), -1)
                self.sel = {'id': it['id'], 'port': nx} if nx >= 0 else {'id': it['id'], 'port': None}
            else:
                self.sel = {'id': it['id'], 'port': None}
        else:
            fix_p(it)
            it['x'], it['y'] = centre
            if t.r0:
                it['r'] = t.r0(it['p']) % 360
            self.items.append(it)
            self.sel = {'id': it['id'], 'port': None}
        return it

    def poser_montage(self, m, centre=(0, 0)):
        """Pose un montage : accroché au point courant s'il y en a un, sinon au
        centre ; ses défauts internes sont validés d'office (la liaison avec le
        réseau existant reste contrôlée)."""
        src = normalize({'items': m['items']})['items']
        if not src:
            return
        sp = self.point_courant()
        a = m.get('a')
        ai = src[a[0]] if a and a[0] < len(src) else src[0]
        wa = wp(ai)
        A = (wa[a[1]] if a and a[1] < len(wa) else None) or (wa[0] if wa else None)
        if not a:
            g = Graphe(src)
            for i in src:
                q = next((q for q in wp(i) if g.libre(i, q)), None)
                if q:
                    ai, A = i, q
                    break
        if sp and A:
            dr = ((sp['wd'] + 180 - A['wd']) % 360 + 360) % 360
            ox, oy, tx, ty = A['wx'], A['wy'], sp['wx'], sp['wy']
        else:
            dr = 0
            ox = _somme(i['x'] for i in src) / len(src)
            oy = _somme(i['y'] for i in src) / len(src)
            tx, ty = centre
        self.snap()
        ang = dr * PI / 180
        c, s = math.cos(ang), math.sin(ang)
        for it in src:
            x, y = it['x'] - ox, it['y'] - oy
            it['x'], it['y'] = tx + x * c - y * s, ty + x * s + y * c
            it['r'] = ((it['r'] + dr) % 360 + 360) % 360
            it['id'] = self.s['nid']
            self.s['nid'] += 1
            self.items.append(it)
        ids = {i['id'] for i in src}
        ok = self.s.setdefault('ok', {})
        for a_, b_ in self.graphe().L:
            if a_[0]['id'] in ids and b_[0]['id'] in ids:
                msg = chk(a_, b_)
                if msg:
                    ok[cle_liaison(a_, b_)] = msg
        self.sel = {'id': src[-1]['id'], 'port': None}

    def montage_depuis(self, it, tout=False):
        """Ensemble raccordé à it (ou tout le schéma) au format montage :
        {a: [n° pièce, n° extrémité d'accroche], items}."""
        G = self.graphe()
        if tout:
            its = list(self.items)
        else:
            ids = comp([it['id']], None, G)
            its = [i for i in self.items if i['id'] in ids]
        if not its:
            return None
        if not it or it not in its:
            it = next((i for i in its if any(G.libre(i, q) for q in wp(i))), its[0])
        if self.sel and self.sel['id'] == it['id'] and self.sel.get('port') is not None:
            fp = self.sel['port']
        else:
            fp = next((q['i'] for q in wp(it) if G.libre(it, q)), 0)
        garde = ('t', 'x', 'y', 'r', 'f', 'p', 'eo')
        return {'a': [its.index(it), fp],
                'items': [_clone({k: i[k] for k in garde if k in i}) for i in its]}

    # --- modification avec maintien des raccordements
    def change(self, it, fn):
        """Applique fn (qui modifie it) ; les ensembles raccordés à une
        extrémité qui se déplace suivent, sauf s'ils touchent aussi une
        autre extrémité de la pièce."""
        G = self.graphe()
        old = wp(it)
        groups = []
        for q in old:
            st = [j for j, pi in G.adj.get(it['id'], ()) if pi == q['i']]
            groups.append(comp(st, it['id'], G) if st else None)
        fn()
        nw = wp(it)
        for i, g in enumerate(groups):
            if not g or i >= len(nw):
                continue
            dx, dy = nw[i]['wx'] - old[i]['wx'], nw[i]['wy'] - old[i]['wy']
            if abs(dx) < .01 and abs(dy) < .01:
                continue
            if any(j != i and h and (g & h) for j, h in enumerate(groups)):
                continue
            for x in self.items:
                if x['id'] in g:
                    x['x'] += dx
                    x['y'] += dy

    def modifier(self, it, k, v):
        """Change un paramètre d'une pièce depuis le panneau de propriétés."""
        f = T[it['t']].field(k)
        if not f:
            return
        if f['t'] == 'chk':
            v = bool(v)
        elif f['t'] in ('dn', 'num') or f.get('n'):
            v = num(v)
        self.snap()

        def fn():
            old = m_of(it['p'])
            it['p'][k] = v
            if k == 'ext':
                it.pop('eo', None)
            # changement de matériau : diamètres convertis par équivalence de DN nominal (FD DN100 → PE Ø110)
            if f['t'] == 'mat' and old != v:
                for g in T[it['t']].fields:
                    if g['t'] == 'dn' and not g.get('m'):
                        it['p'][g['k']] = conv_dn(old, v, it['p'][g['k']])
            fix_p(it)
        self.change(it, fn)

    def imposer_extremite(self, k, verrou=False):
        """Impose le type k (verrou : emboîtement verrouillé) au seul point
        sélectionné. Variante du catalogue si elle existe (nomenclature
        exacte), sinon type imposé sur ce point (it['eo']). Renvoie un
        message d'information ou ''."""
        it = self.cur()
        if not it or self.sel.get('port') is None:
            return ''
        t, i, p = T[it['t']], self.sel['port'], it['p']
        now = pts(it)
        if i >= len(now):
            return ''
        fe, fv = t.field('ext'), t.field('verr')
        eo = dict(it.get('eo') or {})
        eo.pop(str(i), None)

        def eff(c):
            return [eo.get(str(j)) or q['k'] for j, q in enumerate(t.ports(dict(p, ext=c)))]

        cands = [x[0] for x in opt_list(p, fe)] if fe else []
        cands.sort(key=lambda c: 0 if c == p.get('ext') else 1)
        best = next((c for c in cands
                     if len(eff(c)) == len(now)
                     and all((x == k) if j == i else (x == now[j]['k']) for j, x in enumerate(eff(c)))), None)
        nv = verrou if (k == 'E' and fv) else p.get('verr')
        msg = 'Pas de joints verrouillés sur cette pièce : emboîtement simple.' if verrou and not fv else ''
        self.snap()

        def fn():
            if best is not None:
                p['ext'] = best
            else:
                eo[str(i)] = k
            base = t.ports(p)
            for j in list(eo):
                if int(j) < len(base) and base[int(j)]['k'] == eo[j]:
                    del eo[j]
            if eo:
                it['eo'] = eo
            else:
                it.pop('eo', None)
            if fv:
                p['verr'] = nv
            fix_p(it)
        self.change(it, fn)
        return msg

    def revenir_catalogue(self):
        it = self.cur()
        if not it or not it.get('eo') or self.sel.get('port') is None:
            return
        self.snap()

        def fn():
            it['eo'].pop(str(self.sel['port']), None)
            if not it['eo']:
                it.pop('eo')
        self.change(it, fn)

    # --- actions sur la pièce sélectionnée
    def action(self, a):
        it = self.cur()
        if not it:
            return
        if a == 'del':
            self.snap()
            self.s['items'] = [i for i in self.items if i is not it]
            self.sel = None
        elif a == 'dup':
            self.snap()
            nv = _clone(it)
            nv['id'] = self.s['nid']
            self.s['nid'] += 1
            nv['x'] += 40
            nv['y'] += 40
            self.items.append(nv)
            self.sel = {'id': nv['id'], 'port': None}
        elif a == 'flip':
            self.snap()
            it['f'] = 1 if it.get('f', 1) < 0 else -1
        elif a == 'lblauto':
            self.snap()
            it.pop('lo', None)
        else:
            d = {'rot90': 90, 'rot45': 45, 'rotm90': -90}.get(a)
            if d is None:
                return
            self.snap()
            it['r'] = ((it['r'] + d) % 360 + 360) % 360

    def tourner_tout(self, d):
        """Rotation de tout le schéma (±90 ou 180) autour de son centre : les
        raccordements sont conservés ; textes libres gardés droits, cadres de
        regard permutés à 90°, décalages d'étiquettes tournés avec le schéma."""
        if not self.items:
            return
        self.snap()
        xs, ys = [i['x'] for i in self.items], [i['y'] for i in self.items]
        cx, cy = (min(xs) + max(xs)) / 2, (min(ys) + max(ys)) / 2
        c, s = round(math.cos(d * PI / 180)), round(math.sin(d * PI / 180))

        def R(x, y):
            return [r1(x * c - y * s), r1(x * s + y * c)]
        for it in self.items:
            x, y = R(it['x'] - cx, it['y'] - cy)
            it['x'], it['y'] = r1(cx + x), r1(cy + y)
            if it.get('lo'):
                it['lo'] = R(*it['lo'])
            if it['t'] == 'texte':
                continue
            if it['t'] == 'regard':
                if abs(d) == 90:
                    it['p']['w'], it['p']['h'] = it['p']['h'], it['p']['w']
                continue
            it['r'] = ((it['r'] + d) % 360 + 360) % 360

    # --- défauts
    def defauts(self, G=None):
        """(à traiter, validés) : listes de (clé, message, point x, y)."""
        G = G or self.graphe()
        ok = self.s.get('ok') or {}
        msgs, okd = [], []
        for a, b in G.L:
            m = chk(a, b)
            if not m:
                continue
            k = cle_liaison(a, b)
            (okd if ok.get(k) == m else msgs).append((k, m, a[1]['wx'], a[1]['wy']))
        return msgs, okd

    def valider(self, cles, on=True):
        msgs = dict((k, m) for k, m, _x, _y in self.defauts()[0])
        self.snap()
        ok = self.s.setdefault('ok', {})
        for k in cles:
            if on:
                if k in msgs:
                    ok[k] = msgs[k]
            else:
                ok.pop(k, None)


def attacher(it, sp):
    """Oriente et place la pièce pour qu'une de ses extrémités compatibles
    vienne sur le point sp ; renvoie l'indice utilisé (-1 si aucune)."""
    ps = pts(it)
    if not ps:
        it['x'], it['y'] = sp['wx'] + 40, sp['wy'] + 40
        return -1
    k = next((i for i, q in enumerate(ps)
              if ok_pair(q['k'], sp['k'], (q.get('mat') or m_of(it['p'])) == 'pe' and sp.get('mat') == 'pe')), 0)
    it['r'] = ((sp['wd'] + 180 - ps[k]['d']) % 360 + 360) % 360
    a = it['r'] * PI / 180
    c, s = math.cos(a), math.sin(a)
    it['x'] = sp['wx'] - (ps[k]['x'] * c - ps[k]['y'] * s)
    it['y'] = sp['wy'] - (ps[k]['x'] * s + ps[k]['y'] * c)
    return k


# ---------------------------------------------------------------- recherche
def sans_accents(s):
    s = unicodedata.normalize('NFD', str(s).lower())
    return ''.join(c for c in s if not unicodedata.combining(c))
