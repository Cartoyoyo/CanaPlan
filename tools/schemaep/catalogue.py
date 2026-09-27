# tools/schemaep/catalogue.py
"""Catalogue SchemAEP : matériaux, extrémités, compatibilités et pièces.

Chaque pièce décrit ses paramètres par défaut (`p`), ses champs de saisie,
ses extrémités (`ports(p)`), son dessin SVG en coordonnées locales
(`draw(p)`), son étiquette et sa ligne de nomenclature. Les dessins sont les
mêmes que ceux de la page HTML (classes w3, w4, f, fw, da, tx), traduits en
attributs par le rendu Qt.

Un port est un dict : x, y (local), d (direction sortante en degrés, 0 = est,
90 = sud), k (type d'extrémité), dn, mat ; options nm (extrémité dessinée par
la pièce elle-même) et any (accepte tout diamètre).
"""
import math
import re

PI = math.pi


# ---------------------------------------------------------------- nombres
def r1(v):
    """Arrondi au centième, comme Math.round(v*100)/100 en JavaScript."""
    return math.floor(v * 100 + 0.5) / 100


def num(v, defaut=0):
    """Conversion numérique tolérante (équivalent de +v en JavaScript) ;
    un entier reste un entier, pour l'affichage et le JSON."""
    if isinstance(v, bool):
        v = int(v)
    try:
        f = float(v)
    except (TypeError, ValueError):
        return defaut
    if math.isnan(f) or math.isinf(f):
        return defaut
    return int(f) if f == int(f) else f


def n(v):
    """Nombre → texte, à la manière de JavaScript (100 et non 100.0)."""
    v = num(v)
    if isinstance(v, int):
        return str(v)
    if v == 0:
        return '0'
    s = repr(v)
    if 'e' in s:
        m, e = s.split('e')
        s = m + 'e' + ('-' if e.startswith('-') else '+') + e.lstrip('+-').lstrip('0')
    return s


def egal(a, b):
    """Égalité souple (== JavaScript) entre valeurs de liste et paramètre."""
    if a == b:
        return True
    na, nb = num(a, None), num(b, None)
    if na is not None and nb is not None and str(a).strip() != '' and str(b).strip() != '':
        return float(na) == float(nb)
    return str(a) == str(b)


def esc(s):
    s = '' if s is None else str(s)
    return (s.replace('&', '&amp;').replace('<', '&lt;')
            .replace('>', '&gt;').replace('"', '&quot;'))


# ---------------------------------------------------------------- matériaux
MAT = {
    'fd': {'nom': 'Fonte ductile', 'ab': 'FD', 'pref': 'DN', 'col': '#1565c0',
           'dn': [40, 50, 60, 65, 80, 100, 125, 150, 200, 250, 300, 350, 400, 450, 500, 600]},
    'pvc': {'nom': 'PVC pression', 'ab': 'PVC', 'pref': 'Ø', 'col': '#607d8b',
            'dn': [63, 75, 90, 110, 125, 140, 160, 200, 225, 250, 315]},
    'pe': {'nom': 'PEHD', 'ab': 'PEHD', 'pref': 'Ø', 'col': '#212121',
           'dn': [20, 25, 32, 40, 50, 63, 75, 90, 110, 125, 160, 200, 250, 315]},
    'ac': {'nom': 'Laiton / acier fileté', 'ab': 'Lt', 'pref': 'DN', 'col': '#8d6e63',
           'dn': [15, 20, 25, 32, 40, 50]},
}
PEB = [20, 25, 32, 40, 50, 63]
DNT = [15, 20, 25, 32, 40, 50, 60, 65, 80, 100, 125, 150, 200, 250, 300, 350, 400, 450, 500, 600]
OD2DN = {20: 15, 25: 20, 32: 25, 40: 32, 50: 40, 63: 50, 75: 65, 90: 80, 110: 100, 125: 100,
         140: 125, 160: 150, 200: 200, 225: 200, 250: 250, 315: 300}


def nom_dn(m, d):
    """Diamètre nominal équivalent (PE/PVC : diamètre extérieur → DN)."""
    if m in ('pe', 'pvc'):
        return OD2DN.get(num(d), d)
    return d


def conv_dn(m1, m2, v):
    if not m1 or m2 not in MAT or m1 == m2:
        return v
    cible = num(nom_dn(m1, v))
    best, bd = v, float('inf')
    for d in MAT[m2]['dn']:
        x = abs(num(nom_dn(m2, d)) - cible)
        if x < bd:
            bd, best = x, d
    return best


def nearest(liste, v):
    v = num(v)
    best, bd = liste[0], float('inf')
    for d in liste:
        x = abs(d - v)
        if x < bd:
            bd, best = x, d
    return best


def m_of(p):
    return p.get('mat') or 'fd'


def fdn(m, d):
    return MAT[m or 'fd']['pref'] + n(d)


def fmt(p):
    return fdn(m_of(p), p['dn'])


# ---------------------------------------------------------------- extrémités
ENDN = {'E': 'emboîtement', 'X': 'emboîtement Express', 'U': 'bout uni', 'B': 'bride',
        'S': 'électrosoudable', 'K': 'raccord à compression', 'F': 'filetage femelle',
        'M': 'filetage mâle', 'A': 'universel (tout bout uni)', 'C': 'sur conduite / libre'}


def ok_pair(a, b, pe):
    """Deux extrémités s'assemblent-elles ? pe : deux pièces en PEHD
    (bout uni contre bout uni = soudure bout à bout)."""
    if a == 'C' or b == 'C':
        return True
    s = ''.join(sorted((a, b)))
    return s in ('EU', 'UX', 'SU', 'KU', 'BB', 'FM', 'AU') or (pe and s == 'UU')


SUG = {'BU': 'bride-emboîtement (BE) ou adaptateur de bride multi-matériaux',
       'BE': 'bride-bout uni (BU)', 'BX': 'bride-bout uni (BU)',
       'EE': 'bout uni manquant : tronçon de tuyau ou pièce à bout uni',
       'EX': 'tronçon de tuyau', 'XX': 'tronçon de tuyau', 'UU': 'manchon ou raccord universel',
       'KK': 'tronçon de tuyau PE entre les deux raccords', 'SS': 'tronçon de tuyau PE',
       'KS': 'tronçon de tuyau PE', 'BK': 'collet PE + bride tournante',
       'BS': 'collet PE + bride tournante', 'FF': 'mamelon double (M-M)',
       'MM': 'manchon fileté (F-F)', 'BF': 'bride taraudée', 'BM': 'bride taraudée',
       'KM': 'tronçon PE + raccord compression femelle',
       'FK': 'tronçon PE + raccord compression mâle', 'EK': 'tronçon PE + adaptateur'}


def sug(a, b):
    return SUG.get(''.join(sorted((a, b))), 'pièce d’adaptation à prévoir')


def mark(q, v):
    """Symbole d'extrémité (symbologie AEP) : emboîtement = demi-cercle ouvert
    vers l'extérieur, bride = trait perpendiculaire, Express = emboîtement +
    contre-bride boulonnée, verrouillé (v) = trait oblique."""
    k = q.get('k')
    if not k or q.get('nm') or k in ('U', 'C'):
        return ''
    a = q['d'] * PI / 180
    ux, uy = math.cos(a), math.sin(a)
    nx, ny = -uy, ux

    def P(u, w):
        return '%s %s' % (n(r1(q['x'] + ux * u + nx * w)), n(r1(q['y'] + uy * u + ny * w)))

    arc = 'M%sA6 6 0 0 0 %s' % (P(6, -6), P(6, 6))
    lk = '<path d="M%sL%s"/>' % (P(-2, 9), P(12, -9)) if v else ''
    if k == 'B':
        return '<path d="M%sL%s"/>' % (P(0, -7), P(0, 7))
    if k == 'E':
        return '<path d="%s"/>' % arc + lk
    if k == 'X':
        return ('<path d="%sM%sL%sM%sL%sM%sL%sM%sL%sM%sL%sM%sL%s"/>' % (
            arc, P(6, -6), P(6, -9), P(6, 6), P(6, 9), P(8.6, -10), P(8.6, -4.5),
            P(10.9, -10), P(10.9, -4.5), P(8.6, 4.5), P(8.6, 10), P(10.9, 4.5), P(10.9, 10))) + lk
    if k == 'K':
        return '<path class="f" d="M%sL%sL%sL%sZ"/>' % (P(-5, -4), P(0, -4), P(0, 4), P(-5, 4))
    if k in ('F', 'M'):
        return '<circle class="%s" cx="%s" cy="%s" r="3"/>' % (
            'fw' if k == 'F' else 'f', n(r1(q['x'] - ux * 3)), n(r1(q['y'] - uy * 3)))
    s = '<path%s d="M%sL%sL%sL%s"/>' % (' class="da"' if k == 'A' else '',
                                        P(5, -6), P(0, -6), P(0, 6), P(5, 6))
    if k == 'S':
        s += '<path d="M%sL%s"/>' % (P(-3, -3), P(-3, 3))
    return s


# ---------------------------------------------------------------- registre
T = {}
FAM = []


class Piece:
    """Définition d'un type de pièce."""

    def __init__(self, id, nom, fam, p, fields, ports, draw, lbl=None, bom=None,
                 la=None, r0=None, kw='', no_auto=False, eq2=False, dn2def=None,
                 legacy=None, back=False):
        self.id, self.nom, self.fam, self.kw = id, nom, fam, kw or ''
        self.p, self.fields = p, fields
        self.ports, self.draw, self.lbl, self.bom = ports, draw, lbl, bom
        self.la, self.r0 = la, r0
        self.no_auto, self.eq2, self.dn2def = no_auto, eq2, dn2def
        self.legacy, self.back = legacy, back

    def field(self, k):
        return next((f for f in self.fields if f['k'] == k), None)


def define(id, **o):
    T[id] = Piece(id, **o)
    if o['fam'] not in FAM:
        FAM.append(o['fam'])


F1, F2, F3 = 'Canalisations', 'Raccords réseau', 'Raccords PE & filetés'
F4, F5, F6 = 'Robinetterie', 'Régulation & protection', 'Branchement & comptage'
F7, F8, F9 = 'Incendie & usages', 'Ouvrages', 'Annotations'
FCOL = {F2: '#1565c0', F3: '#212121', F4: '#ad1457', F5: '#6a1b9a', F6: '#00838f',
        F7: '#d84315', F8: '#2e7d32', F9: '#455a64'}

MATS = ['fd', 'pvc', 'pe']


def FMAT(o):
    return {'k': 'mat', 't': 'mat', 'l': 'Matériau', 'o': o}


FDN = {'k': 'dn', 't': 'dn', 'l': 'Diamètre'}
FBUT = {'k': 'but', 't': 'chk', 'l': 'Massif de butée béton'}
FVER = {'k': 'verr', 't': 'chk', 'l': 'Joints verrouillés'}
FBAC = {'k': 'bac', 't': 'chk', 'l': 'Bouche à clé + tige'}
FREG = {'k': 'reg', 't': 'chk', 'l': 'Sous regard / chambre'}
FPE = {'k': 'dn', 't': 'dn', 'l': 'Diamètre PE', 'm': 'pe', 'dl': lambda p: PEB}


def FAC(k='dn', l='Diamètre (filetage)'):
    return {'k': k, 't': 'dn', 'l': l, 'm': 'ac', 'dl': lambda p: MAT['ac']['dn']}


def ext_o(mp):
    return lambda p: mp.get(m_of(p)) or mp['fd']


def ext_l(mp, p):
    return next((x for x in (mp.get(m_of(p)) or mp['fd']) if x[0] == p['ext']), ('', ''))[1]


def FEXT(mp, l='Extrémités'):
    return {'k': 'ext', 't': 'sel', 'l': l, 'o': ext_o(mp)}


def vt(p):
    return ' – verrouillé' if p.get('verr') else ''


def u1(d, q=1, u='u'):
    return {'d': d, 'q': q, 'u': u}


STUB = '<path d="M-20 0H-12M12 0H20"/>'
BOW = '<path class="fw" d="M-12 -8L0 0L-12 8ZM12 -8L0 0L12 8Z"/>'


def BOX(t, w=24):
    return ('<rect class="fw" x="%s" y="-9" width="%s" height="18" rx="2"/>'
            '<text class="tx" y="3.5">%s</text>') % (n(-w / 2), n(w), t)


ROB14 = '<circle class="fw" r="7"/><path d="M-5 -5L5 5M5 -5L-5 5"/>'
ANG = [[90, '1/4 (90°)'], [45, '1/8 (45°)'], [22.5, '1/16 (22°30)'], [11.25, '1/32 (11°15)']]


def ang_s(a):
    return {90: '1/4', 45: '1/8', 22.5: '1/16', 11.25: '1/32'}.get(num(a), n(a) + '°')


def _dn_field(o):
    if o.get('thr'):
        return {'k': 'dn', 't': 'dn', 'l': 'Diamètre', 'dl': lambda p: o.get('dl') or DNT}
    if o.get('dl'):
        return {'k': 'dn', 't': 'dn', 'l': 'Diamètre', 'dl': lambda p: o['dl']}
    return FDN


def inl(id, **o):
    """Fabrique : pièce en ligne à 2 extrémités (brides, ou filetées si
    DN ≤ 40 quand thr)."""
    def ports(p):
        if o.get('thr') and num(p['dn']) <= 40:
            a = o.get('k1') or 'F'
            e = (a, o.get('k2') or a, 'ac')
        else:
            e = ('B', 'B', 'fd')
        return [{'x': -20, 'y': 0, 'd': 180, 'k': e[0], 'dn': p['dn'], 'mat': e[2]},
                {'x': 20, 'y': 0, 'd': 0, 'k': e[1], 'dn': p['dn'], 'mat': e[2]}]
    p = {'dn': 100}
    p.update(o.get('p') or {})
    define(id, nom=o['nom'], fam=o['fam'], kw=o.get('kw'), p=p,
           fields=[_dn_field(o)] + list(o.get('f') or []), ports=ports,
           draw=lambda p: STUB + o['draw'](p),
           lbl=o.get('lbl') or (lambda p: '%s DN%s' % (o['ab'], n(p['dn']))),
           bom=o.get('bom') or (lambda p: u1('%s DN%s' % (o['nom'], n(p['dn'])))))


def up(id, **o):
    """Fabrique : appareil vertical à 1 extrémité en bas."""
    def ports(p):
        th = o.get('thr') and num(p['dn']) <= 40
        q = {'x': 0, 'y': 20, 'd': 90, 'k': 'F' if th else (o.get('k') or 'B'), 'dn': p['dn'],
             'mat': 'ac' if th else (o.get('m') or 'fd')}
        if o.get('nm'):
            q['nm'] = 1
        return [q]
    p = {'dn': o.get('dn') or 80}
    p.update(o.get('p') or {})
    fd = {'k': 'dn', 't': 'dn', 'l': 'Diamètre'}
    if o.get('m'):
        fd['m'] = o['m']
    if o.get('dl'):
        fd['dl'] = o['dl']
    define(id, nom=o['nom'], fam=o['fam'], kw=o.get('kw'), p=p,
           fields=[fd] + list(o.get('f') or []), ports=ports,
           draw=lambda p: ('' if o.get('ns') else '<path d="M0 20V9"/>') + o['draw'](p),
           la=lambda p: [12, 0, 1, 0],
           lbl=o.get('lbl') or (lambda p: '%s DN%s' % (o['ab'], n(p['dn']))),
           bom=o.get('bom') or (lambda p: u1('%s DN%s' % (o['nom'], n(p['dn'])))))


def _q(x, y, d, k, dn, mat=None, **kw):
    q = {'x': x, 'y': y, 'd': d, 'k': k, 'dn': dn}
    if mat:
        q['mat'] = mat
    q.update(kw)
    return q


def _l(k, t, l, **kw):
    f = {'k': k, 't': t, 'l': l}
    f.update(kw)
    return f


# ================================================================ CANALISATIONS
def plen(p):
    dl = num(p.get('dl'))
    return dl if dl > 0 else max(60, min(400, 40 + num(p.get('L')) * 2))


def _tuyau_draw(p):
    l = plen(p)
    if p.get('fou'):
        return ('<path class="w4" d="M0 0H6M%s 0H%s"/><rect x="6" y="-7" width="%s" height="14"/>'
                '<path d="M6 0H%s" style="stroke-dasharray:4 4;stroke-linecap:butt"/>') % (
            n(l - 6), n(l), n(l - 12), n(l - 6))
    return '<path class="w4" d="M0 0H%s"/>' % n(l)


def _tuyau_bom(p):
    L = num(p.get('L'))
    e = p['ext']
    r = [u1('Tuyau %s %s%s%s' % (MAT[m_of(p)]['nom'], fmt(p),
                                 ' à brides' if e == 'BB' else ' Express' if e == 'XU' else '',
                                 vt(p)), L, 'ml')]
    if p.get('grill'):
        r.append(u1('Grillage avertisseur bleu', L, 'ml'))
    if p.get('fou'):
        r.append(u1('Fourreau pour %s %s' % (MAT[m_of(p)]['ab'], fmt(p)), L, 'ml'))
    return r


_EXT_TUYAU = {'fd': [['EU', 'Emboîtement + bout uni'], ['XU', 'Express + bout uni'],
                     ['BB', 'Tuyau à brides'], ['UU', 'Bouts unis (coupe)']],
              'pvc': [['EU', 'Emboîtement + bout uni'], ['UU', 'Bouts unis (coupe)']],
              'pe': [['UU', 'Bouts unis (soudage / raccords)']]}

define('tuyau', nom='Tuyau', fam=F1, kw='conduite canalisation', no_auto=True,
       p={'mat': 'fd', 'dn': 100, 'ext': 'EU', 'L': 6, 'dl': 0, 'verr': False, 'grill': True, 'fou': False},
       fields=[FMAT(MATS), FDN, _l('ext', 'sel', 'Extrémités', o=lambda p: _EXT_TUYAU[m_of(p)]),
               _l('L', 'num', 'Longueur réelle (m)', st=0.1), _l('dl', 'num', 'Longueur dessin (0 = auto)', st=10),
               FVER, _l('grill', 'chk', 'Grillage avertisseur'), _l('fou', 'chk', 'Sous fourreau')],
       ports=lambda p: [_q(0, 0, 180, p['ext'][0], p['dn']), _q(plen(p), 0, 0, p['ext'][1], p['dn'])],
       draw=_tuyau_draw, la=lambda p: [plen(p) / 2, 0, 0, -1],
       lbl=lambda p: '%s %s%s' % (MAT[m_of(p)]['ab'], fmt(p), (' – %s m' % n(p['L'])) if num(p.get('L')) else ''),
       bom=_tuyau_bom)

# ================================================================ RACCORDS RÉSEAU
EX2 = {'fd': [['EE', '2 emboîtements'], ['BB', '2 brides'], ['EU', 'emboîtement + bout uni']],
       'pvc': [['EE', '2 emboîtements'], ['UU', '2 bouts unis']],
       'pe': [['SS', 'électrosoudable'], ['UU', 'à souder bout à bout']]}
EX3 = {'fd': [['EEB', '2 emboîtements + tubulure à bride'], ['EEE', '3 emboîtements'], ['BBB', '3 brides']],
       'pvc': [['EEE', '3 emboîtements'], ['EEB', '2 emboîtements + tubulure à bride']],
       'pe': [['SSS', 'électrosoudable'], ['UUU', 'à souder bout à bout']]}
EXM = {'fd': [['EE', '2 emboîtements']], 'pvc': [['EE', '2 emboîtements']], 'pe': [['SS', 'électrosoudable']]}
EXB = {'fd': [['E', 'Bouchon (sur bout uni)'], ['U', 'Obturateur (dans emboîtement)']],
       'pvc': [['E', 'Bouchon (sur bout uni)']],
       'pe': [['S', 'Bouchon électrosoudable'], ['U', 'Bouchon à souder']]}


def _coude_ports(p):
    a = num(p['ang']) * PI / 180
    return [_q(-20, 0, 180, p['ext'][0], p['dn']),
            _q(r1(20 * math.cos(a)), r1(-20 * math.sin(a)), (360 - num(p['ang'])) % 360, p['ext'][1], p['dn'])]


def _coude_draw(p):
    a = num(p['ang']) * PI / 180
    return '<path d="M-20 0H0L%s %s"/>' % (n(r1(20 * math.cos(a))), n(r1(-20 * math.sin(a))))


define('coude', nom='Coude', fam=F2,
       p={'mat': 'fd', 'dn': 100, 'ang': 90, 'ext': 'EE', 'but': True, 'verr': False},
       fields=[FMAT(MATS), FDN, _l('ang', 'sel', 'Angle', n=1, o=ANG), FEXT(EX2), FBUT, FVER],
       ports=_coude_ports, draw=_coude_draw,
       r0=lambda p: 180 + num(p['ang']) / 2,  # posé seul : en V pointe en haut
       lbl=lambda p: 'Coude %s %s' % (ang_s(p['ang']), fmt(p)),
       bom=lambda p: u1('Coude %s %s %s – %s%s' % (ang_s(p['ang']), MAT[m_of(p)]['nom'], fmt(p), ext_l(EX2, p), vt(p))))

define('patin', nom='Coude à patin (pied d’assise)', fam=F2, kw='poteau', p={'dn': 100, 'but': True},
       fields=[FDN, FBUT],
       ports=lambda p: [_q(-20, 0, 180, 'B', p['dn']), _q(0, -24, 270, 'B', p['dn'])],
       draw=lambda p: '<path class="w3" d="M-20 0H0V-24"/><path d="M-9 7H9M0 0V7"/>',
       lbl=lambda p: 'Coude à patin DN%s' % n(p['dn']),
       bom=lambda p: u1('Coude à patin à brides fonte DN%s' % n(p['dn'])))

# tb : longueur de la tubulure ; legacy : valeur des schémas antérieurs, migrés au chargement
define('te', nom='Té', fam=F2, eq2=True, legacy={'tb': 20},
       p={'mat': 'fd', 'dn': 100, 'dn2': 100, 'ext': 'EEB', 'but': True, 'verr': False, 'tb': 10},
       fields=[FMAT(MATS), FDN,
               _l('dn2', 'dn', 'Diamètre tubulure', dl=lambda p: [d for d in MAT[m_of(p)]['dn'] if d <= num(p['dn'])]),
               FEXT(EX3), FBUT, FVER],
       ports=lambda p: [_q(-20, 0, 180, p['ext'][0], p['dn']), _q(20, 0, 0, p['ext'][1], p['dn']),
                        _q(0, -num(p['tb']), 270, p['ext'][2], p['dn2'])],
       draw=lambda p: '<path d="M-20 0H20M0 0V-%s"/>' % n(p['tb']),
       lbl=lambda p: 'Té %s/%s' % (fmt(p), fdn(m_of(p), p['dn2'])),
       bom=lambda p: u1('Té %s %s × %s – %s%s' % (MAT[m_of(p)]['nom'], fmt(p), fdn(m_of(p), p['dn2']), ext_l(EX3, p), vt(p))))

define('croix', nom='Croix à brides', fam=F2, eq2=True, p={'dn': 150, 'dn2': 100, 'but': True},
       fields=[FDN, _l('dn2', 'dn', 'Diamètre dérivations', dl=lambda p: [d for d in MAT['fd']['dn'] if d <= num(p['dn'])]), FBUT],
       ports=lambda p: [_q(-20, 0, 180, 'B', p['dn']), _q(20, 0, 0, 'B', p['dn']),
                        _q(0, -20, 270, 'B', p['dn2']), _q(0, 20, 90, 'B', p['dn2'])],
       draw=lambda p: '<path class="w3" d="M-20 0H20M0 -20V20"/>', la=lambda p: [6, 6, 1, 1],
       lbl=lambda p: 'Croix DN%s/%s' % (n(p['dn']), n(p['dn2'])),
       bom=lambda p: u1('Croix à brides fonte DN%s × DN%s' % (n(p['dn']), n(p['dn2']))))


def _cone_draw(p):
    def e(k, v):
        return v if k in ('E', 'X') else 0
    a = -20 - e(p['ext'][0], 2.7)
    b = 20 + e(p['ext'][1], 0.8)
    return '<path d="M%s -5L%s -3M%s 5L%s 3"/>' % (n(a), n(b), n(a), n(b))


define('cone', nom='Cône de réduction', fam=F2, kw='réduction',
       p={'mat': 'fd', 'dn': 150, 'dn2': 100, 'ext': 'EE', 'but': True, 'verr': False},
       fields=[FMAT(MATS), _l('dn', 'dn', 'Grand diamètre'),
               _l('dn2', 'dn', 'Petit diamètre', dl=lambda p: [d for d in MAT[m_of(p)]['dn'] if d < num(p['dn'])]),
               FEXT(EX2), FBUT, FVER],
       ports=lambda p: [_q(-20, 0, 180, p['ext'][0], p['dn']), _q(20, 0, 0, p['ext'][1], p['dn2'])],
       draw=_cone_draw,
       lbl=lambda p: 'Cône %s/%s' % (fmt(p), fdn(m_of(p), p['dn2'])),
       bom=lambda p: u1('Cône %s %s × %s – %s%s' % (MAT[m_of(p)]['nom'], fmt(p), fdn(m_of(p), p['dn2']), ext_l(EX2, p), vt(p))))

define('manchon', nom='Manchon', fam=F2, p={'mat': 'fd', 'dn': 100, 'ext': 'EE', 'typ': 'Manchon', 'verr': False},
       fields=[FMAT(MATS), FDN, FEXT(EXM),
               _l('typ', 'sel', 'Type', o=[['Manchon', 'Manchon simple'], ['Manchon coulissant', 'Manchon coulissant (réparation)']]),
               FVER],
       ports=lambda p: [_q(-12, 0, 180, p['ext'][0], p['dn']), _q(12, 0, 0, p['ext'][1], p['dn'])],
       draw=lambda p: '<path class="w3" d="M-12 0H12"/>',
       lbl=lambda p: 'Manchon %s' % fmt(p),
       bom=lambda p: u1('%s %s %s – %s%s' % (p['typ'], MAT[m_of(p)]['nom'], fmt(p), ext_l(EXM, p), vt(p))))

define('be', nom='Bride-emboîtement (BE)', fam=F2, kw='express', p={'dn': 100, 'ext': 'E', 'verr': False},
       fields=[FDN, _l('ext', 'sel', 'Emboîtement', o=[['E', 'Standard'], ['X', 'Express']]), FVER],
       ports=lambda p: [_q(-14, 0, 180, 'B', p['dn']), _q(14, 0, 0, p['ext'], p['dn'])],
       draw=lambda p: '<path class="w3" d="M-14 0H14"/>',
       lbl=lambda p: 'BE%s DN%s' % (' Express' if p['ext'] == 'X' else '', n(p['dn'])),
       bom=lambda p: u1('Bride-emboîtement (BE)%s fonte DN%s%s' % (' Express' if p['ext'] == 'X' else '', n(p['dn']), vt(p))))

define('bu', nom='Bride-bout uni (BU)', fam=F2, p={'dn': 100}, fields=[FDN],
       ports=lambda p: [_q(-14, 0, 180, 'B', p['dn']), _q(14, 0, 0, 'U', p['dn'])],
       draw=lambda p: '<path class="w3" d="M-14 0H14"/>',
       lbl=lambda p: 'BU DN%s' % n(p['dn']), bom=lambda p: u1('Bride-bout uni (BU) fonte DN%s' % n(p['dn'])))

define('adapt', nom='Adaptateur de bride multi-matériaux', fam=F2, kw='grande tolérance', p={'dn': 100, 'verr': False},
       fields=[FDN, FVER],
       ports=lambda p: [_q(-14, 0, 180, 'B', p['dn']), _q(14, 0, 0, 'A', p['dn'], any=1, nm=1)],
       draw=lambda p: '<path d="M-14 -4H9M-14 4H9M10 -8V-2M13 -8V-2M10 2V8M13 2V8M13 0H14"/>' + (
           '<path d="M2 10L16 -10"/>' if p.get('verr') else ''),
       lbl=lambda p: 'Adapt. bride DN%s' % n(p['dn']),
       bom=lambda p: u1('Adaptateur de bride grande tolérance DN%s%s' % (n(p['dn']), ' – auto-buté' if p.get('verr') else '')))

define('univ', nom='Raccord universel multi-matériaux', fam=F2, kw='manchon grande tolérance', p={'dn': 100, 'verr': False},
       fields=[FDN, FVER],
       ports=lambda p: [_q(-14, 0, 180, 'A', p['dn'], any=1), _q(14, 0, 0, 'A', p['dn'], any=1)],
       draw=lambda p: '<path class="w3" d="M-14 0H14"/><rect class="fw" x="-8" y="-7" width="16" height="14"/>',
       lbl=lambda p: 'Raccord univ. DN%s' % n(p['dn']),
       bom=lambda p: u1('Raccord universel grande tolérance DN%s%s' % (n(p['dn']), ' – auto-buté' if p.get('verr') else '')))

define('jdem', nom='Joint de démontage', fam=F2, p={'dn': 100, 'typ': 'Joint de démontage'},
       fields=[FDN, _l('typ', 'sel', 'Type', o=[['Joint de démontage', 'Standard'],
                                               ['Joint de démontage auto-buté', 'Auto-buté (verrouillé)']])],
       ports=lambda p: [_q(-20, 0, 180, 'B', p['dn']), _q(20, 0, 0, 'B', p['dn'], nm=1)],
       draw=lambda p: '<path d="M-20 -4H13M-20 4H13M15 -9V-2M18 -9V-2M15 2V9M18 2V9M18 0H20"/>' + (
           '<path d="M6 11L22 -11"/>' if re.search('auto', str(p['typ']), re.I) else ''),
       lbl=lambda p: 'JD DN%s' % n(p['dn']), bom=lambda p: u1('%s DN%s' % (p['typ'], n(p['dn']))))

define('manchette', nom='Manchette à brides', fam=F2, kw='ancrage étanchéité', p={'dn': 100, 'L': 0.5, 'anc': False},
       fields=[FDN, _l('L', 'num', 'Longueur (m)', st=0.05), _l('anc', 'chk', 'D’ancrage et d’étanchéité')],
       ports=lambda p: [_q(-24, 0, 180, 'B', p['dn']), _q(24, 0, 0, 'B', p['dn'])],
       draw=lambda p: '<path class="w3" d="M-24 0H24"/>' + ('<path class="w3" d="M0 -5V5"/>' if p.get('anc') else ''),
       lbl=lambda p: 'Manchette%s DN%s L%s' % (' anc.' if p.get('anc') else '', n(p['dn']), n(p['L'])),
       bom=lambda p: u1('Manchette %s fonte DN%s – L = %s m' % (
           'd’ancrage et d’étanchéité' if p.get('anc') else 'à brides', n(p['dn']), n(p['L']))))

define('bred', nom='Plaque (bride) de réduction', kw='taraudée', fam=F2, p={'dn': 150, 'dn2': 100},
       fields=[FDN, _l('dn2', 'dn', 'Diamètre réduit', dl=lambda p: [d for d in MAT['fd']['dn'] if d < num(p['dn'])])],
       ports=lambda p: [_q(-8, 0, 180, 'B', p['dn'], nm=1), _q(8, 0, 0, 'B', p['dn2'], nm=1)],
       draw=lambda p: '<path d="M-8 0H-4M4 0H8"/><path class="w4" style="stroke-linecap:butt" d="M-4 -11V11M4 -6V6"/>',
       lbl=lambda p: 'Bride réd. DN%s/%s' % (n(p['dn']), n(p['dn2'])),
       bom=lambda p: u1('Bride de réduction DN%s × DN%s' % (n(p['dn']), n(p['dn2']))))

define('collet', nom='Collet PE + bride tournante', fam=F2, kw='PEHD bride', p={'mat': 'pe', 'dn': 110},
       fields=[_l('dn', 'dn', 'Diamètre PE', m='pe', dl=lambda p: [d for d in MAT['pe']['dn'] if d >= 63])],
       ports=lambda p: [_q(-14, 0, 180, 'U', p['dn'], 'pe'), _q(14, 0, 0, 'B', p['dn'], 'pe')],
       draw=lambda p: '<path class="w3" d="M-14 0H14"/>',
       lbl=lambda p: 'Collet Ø%s' % n(p['dn']),
       bom=lambda p: u1('Collet PE Ø%s + bride tournante DN%s' % (n(p['dn']), n(nom_dn('pe', p['dn'])))))

define('bouchon', nom='Bouchon / obturateur', fam=F2, p={'mat': 'fd', 'dn': 100, 'ext': 'E', 'but': True, 'verr': False},
       fields=[FMAT(MATS), FDN, FEXT(EXB, 'Type'), FBUT, FVER],
       ports=lambda p: [_q(-12, 0, 180, p['ext'], p['dn'])],
       draw=lambda p: '<path class="w3" d="M-12 0H-4"/><path class="w4" d="M-3 -9V9"/>',
       lbl=lambda p: 'Bouchon %s' % fmt(p),
       bom=lambda p: u1('%s %s %s%s' % (ext_l(EXB, p), MAT[m_of(p)]['nom'], fmt(p), vt(p))))

define('pleine', nom='Plaque pleine (bride pleine)', fam=F2, p={'dn': 100, 'but': False}, fields=[FDN, FBUT],
       ports=lambda p: [_q(-10, 0, 180, 'B', p['dn'], nm=1)],
       draw=lambda p: '<path class="w3" d="M-10 0H-2"/><path class="w4" style="stroke-linecap:butt" d="M-2 -11V11"/>',
       lbl=lambda p: 'Plaque pleine DN%s' % n(p['dn']), bom=lambda p: u1('Plaque pleine DN%s' % n(p['dn'])))

define('collrep', nom='Collier de réparation', fam=F2, p={'mat': 'fd', 'dn': 100, 'typ': 'Collier de réparation'},
       fields=[FMAT(MATS), FDN, _l('typ', 'sel', 'Type', o=[['Collier de réparation', 'Collier de réparation'],
                                                             ['Collier de réparation grande largeur', 'Grande largeur']])],
       ports=lambda p: [_q(-20, 0, 180, 'C', p['dn']), _q(20, 0, 0, 'C', p['dn'])],
       draw=lambda p: '<path class="w4" d="M-20 0H20"/><rect class="fw" x="-9" y="-8" width="18" height="16" rx="2"/><path d="M-4 -8V8M4 -8V8"/>',
       lbl=lambda p: 'Collier rép. %s' % fmt(p),
       bom=lambda p: u1('%s sur %s %s' % (p['typ'], MAT[m_of(p)]['nom'], fmt(p))))


# ================================================================ RACCORDS PE & FILETÉS
def K(x, y, d, dn):
    return {'x': x, 'y': y, 'd': d, 'k': 'K', 'dn': dn, 'mat': 'pe'}


def _red(p):
    return num(p['dn2']) != num(p['dn'])


define('mcomp', nom='Manchon à compression', fam=F3, eq2=True, p={'mat': 'pe', 'dn': 32, 'dn2': 32},
       fields=[FPE, _l('dn2', 'dn', 'Sortie (réduit si <)', m='pe', dl=lambda p: [d for d in PEB if d <= num(p['dn'])])],
       ports=lambda p: [K(-14, 0, 180, p['dn']), K(14, 0, 0, p['dn2'])],
       draw=lambda p: '<path class="w3" d="M-14 0H14"/>',
       lbl=lambda p: 'Manchon Ø%s%s' % (n(p['dn']), ('/' + n(p['dn2'])) if _red(p) else ''),
       bom=lambda p: u1('Manchon à compression PE Ø%s%s' % (n(p['dn']), (' × Ø%s (réduit)' % n(p['dn2'])) if _red(p) else '')))
define('ccomp', nom='Coude à compression 90°', fam=F3, p={'mat': 'pe', 'dn': 32}, fields=[FPE],
       ports=lambda p: [K(-14, 0, 180, p['dn']), K(0, -14, 270, p['dn'])],
       draw=lambda p: '<path class="w3" d="M-14 0H0V-14"/>',
       lbl=lambda p: 'Coude Ø%s' % n(p['dn']), bom=lambda p: u1('Coude 90° à compression PE Ø%s' % n(p['dn'])))
define('tcomp', nom='Té à compression', fam=F3, eq2=True, p={'mat': 'pe', 'dn': 32, 'dn2': 32},
       fields=[FPE, _l('dn2', 'dn', 'Dérivation', m='pe', dl=lambda p: [d for d in PEB if d <= num(p['dn'])])],
       ports=lambda p: [K(-14, 0, 180, p['dn']), K(14, 0, 0, p['dn']), K(0, -14, 270, p['dn2'])],
       draw=lambda p: '<path class="w3" d="M-14 0H14M0 0V-14"/>',
       lbl=lambda p: 'Té Ø%s/%s' % (n(p['dn']), n(p['dn2'])),
       bom=lambda p: u1('Té à compression PE Ø%s × Ø%s' % (n(p['dn']), n(p['dn2']))))
define('cmale', nom='Raccord compression / fileté mâle', fam=F3, p={'mat': 'pe', 'dn': 32, 'fil': 25},
       fields=[FPE, FAC('fil', 'Filetage mâle')],
       ports=lambda p: [K(-14, 0, 180, p['dn']), _q(14, 0, 0, 'M', p['fil'], 'ac')],
       draw=lambda p: '<path class="w3" d="M-14 0H14"/>',
       lbl=lambda p: 'Ø%s × DN%s M' % (n(p['dn']), n(p['fil'])),
       bom=lambda p: u1('Raccord compression PE Ø%s × fileté mâle DN%s' % (n(p['dn']), n(p['fil']))))
define('cfem', nom='Raccord compression / fileté femelle', fam=F3, p={'mat': 'pe', 'dn': 32, 'fil': 25},
       fields=[FPE, FAC('fil', 'Filetage femelle')],
       ports=lambda p: [K(-14, 0, 180, p['dn']), _q(14, 0, 0, 'F', p['fil'], 'ac')],
       draw=lambda p: '<path class="w3" d="M-14 0H14"/>',
       lbl=lambda p: 'Ø%s × DN%s F' % (n(p['dn']), n(p['fil'])),
       bom=lambda p: u1('Raccord compression PE Ø%s × fileté femelle DN%s' % (n(p['dn']), n(p['fil']))))
define('bcomp', nom='Bouchon à compression', fam=F3, p={'mat': 'pe', 'dn': 32}, fields=[FPE],
       ports=lambda p: [K(-10, 0, 180, p['dn'])],
       draw=lambda p: '<path class="w3" d="M-10 0H-3"/><path class="w4" d="M-2 -7V7"/>',
       lbl=lambda p: 'Bouchon Ø%s' % n(p['dn']), bom=lambda p: u1('Bouchon à compression PE Ø%s' % n(p['dn'])))
define('mamelon', nom='Mamelon double (M-M)', fam=F3, p={'dn': 25}, fields=[FAC()],
       ports=lambda p: [_q(-10, 0, 180, 'M', p['dn'], 'ac'), _q(10, 0, 0, 'M', p['dn'], 'ac')],
       draw=lambda p: '<path class="w3" d="M-10 0H10"/>',
       lbl=lambda p: 'Mamelon DN%s' % n(p['dn']), bom=lambda p: u1('Mamelon double laiton DN%s' % n(p['dn'])))
define('mfil', nom='Manchon fileté (F-F)', fam=F3, p={'dn': 25}, fields=[FAC()],
       ports=lambda p: [_q(-10, 0, 180, 'F', p['dn'], 'ac'), _q(10, 0, 0, 'F', p['dn'], 'ac')],
       draw=lambda p: '<path class="w3" d="M-10 0H10"/>',
       lbl=lambda p: 'Manchon DN%s' % n(p['dn']), bom=lambda p: u1('Manchon fileté laiton DN%s' % n(p['dn'])))
define('redfil', nom='Réduction filetée (M-F)', fam=F3, p={'dn': 25, 'dn2': 20},
       fields=[FAC('dn', 'Mâle'), _l('dn2', 'dn', 'Femelle', m='ac', dl=lambda p: [d for d in MAT['ac']['dn'] if d < num(p['dn'])])],
       ports=lambda p: [_q(-10, 0, 180, 'M', p['dn'], 'ac'), _q(10, 0, 0, 'F', p['dn2'], 'ac')],
       draw=lambda p: '<path class="w3" d="M-10 0H10"/>',
       lbl=lambda p: 'Réd. DN%s/%s' % (n(p['dn']), n(p['dn2'])),
       bom=lambda p: u1('Réduction filetée laiton DN%s mâle × DN%s femelle' % (n(p['dn']), n(p['dn2']))))

# ================================================================ ROBINETTERIE
MAN = [['Carré de manœuvre', 'Carré (bouche à clé)'], ['Volant', 'Volant'],
       ['Réducteur', 'Réducteur à volant'], ['Motorisée', 'Motorisée (actionneur)']]
EXV = [['BB', 'à brides'], ['EE', 'à emboîtements'], ['BE', 'bride + emboîtement']]


def _lib(liste, v):
    return next((x[1] for x in liste if x[0] == v), '')


# repère de la vanne (numéro du point CanaPlan : V02…), en tête de son étiquette
FREP = {'k': 'rep', 't': 'txt', 'l': 'Repère'}


def _rep(p):
    return ('%s – ' % p['rep']) if p.get('rep') else ''


define('vanne', nom='Robinet-vanne (opercule)', fam=F4, kw='RV vanne sectionnement',
       p={'dn': 100, 'ext': 'BB', 'man': 'Carré de manœuvre', 'bac': True, 'reg': False, 'rep': ''},
       fields=[FDN, _l('ext', 'sel', 'Extrémités', o=EXV), _l('man', 'sel', 'Manœuvre', o=MAN), FBAC, FREG, FREP],
       ports=lambda p: [_q(-20, 0, 180, p['ext'][0], p['dn'], 'fd'), _q(20, 0, 0, p['ext'][1], p['dn'], 'fd')],
       draw=lambda p: STUB + BOW,
       lbl=lambda p: _rep(p) + 'RV DN%s' % n(p['dn']),
       bom=lambda p: u1('Robinet-vanne à opercule DN%s %s – %s' % (n(p['dn']), _lib(EXV, p['ext']), str(p['man']).lower())))
inl('papillon', nom='Vanne papillon', fam=F4, ab='VP', p={'dn': 200, 'man': 'Réducteur', 'bac': False, 'reg': True, 'rep': ''},
    f=[_l('man', 'sel', 'Manœuvre', o=[['Réducteur', 'Réducteur à volant'], ['Levier', 'Levier'],
                                       ['Carré de manœuvre', 'Carré (bouche à clé)'], ['Motorisée', 'Motorisée']]), FBAC, FREG, FREP],
    draw=lambda p: BOW,
    lbl=lambda p: _rep(p) + 'VP DN%s' % n(p['dn']),
    bom=lambda p: u1('Vanne papillon à brides DN%s – %s' % (n(p['dn']), str(p['man']).lower())))
EXQ = [['FF', 'femelle / femelle'], ['MF', 'mâle / femelle'], ['MM', 'mâle / mâle']]
define('rob14', nom='Robinet ¼ de tour', fam=F4, kw='quart de tour sphérique boisseau branchement', p={'dn': 20, 'ext': 'FF'},
       fields=[FAC(), _l('ext', 'sel', 'Filetages', o=EXQ)],
       ports=lambda p: [_q(-16, 0, 180, p['ext'][0], p['dn'], 'ac'), _q(16, 0, 0, p['ext'][1], p['dn'], 'ac')],
       draw=lambda p: '<path d="M-16 0H-7M7 0H16"/>' + ROB14,
       lbl=lambda p: 'R¼ DN%s' % n(p['dn']),
       bom=lambda p: u1('Robinet ¼ de tour laiton DN%s – %s' % (n(p['dn']), _lib(EXQ, p['ext']))))

# ================================================================ RÉGULATION & PROTECTION
inl('clapet', nom='Clapet anti-retour', fam=F5, thr=1, ab='CAR', kw='retenue', p={'dn': 100, 'typ': 'À battant'},
    f=[_l('typ', 'sel', 'Type', o=[['À battant', 'À battant'], ['Double battant', 'Double battant'],
                                   ['À boule', 'À boule'], ['À ressort', 'À ressort']])],
    draw=lambda p: '<path d="M-12 0H12M-3 -8V8M-3 -8L9 8M-18 -6H-10"/><path class="f" d="M-6 -6L-10 -8.5V-3.5Z"/>',
    bom=lambda p: u1('Clapet anti-retour %s DN%s' % (str(p['typ']).lower(), n(p['dn']))))
inl('filtre', nom='Filtre à tamis', fam=F5, thr=1, ab='Filtre', p={'dn': 100},
    draw=lambda p: '<path class="fw" d="M0 -11L12 0L0 11L-12 0Z"/><path class="da" d="M0 -9V9"/>')
inl('rp', nom='Réducteur de pression', fam=F5, thr=1, ab='RP', kw='régulateur aval', p={'dn': 100, 'pav': 3, 'reg': True},
    f=[_l('pav', 'num', 'Consigne aval (bar)', st=0.1), FREG],
    draw=lambda p: '<path class="fw" d="M-12 -11V11L12 6V-6Z"/><text class="tx" y="3.5">RP</text>',
    lbl=lambda p: 'RP DN%s – %s bar' % (n(p['dn']), n(p['pav'])),
    bom=lambda p: u1('Réducteur de pression DN%s (consigne aval %s bar)' % (n(p['dn']), n(p['pav']))))
inl('sa', nom='Stabilisateur amont', fam=F5, ab='SA', kw='maintien pression', p={'dn': 100, 'pam': 4, 'reg': True},
    f=[_l('pam', 'num', 'Consigne amont (bar)', st=0.1), FREG], draw=lambda p: BOX('SA'),
    lbl=lambda p: 'SA DN%s – %s bar' % (n(p['dn']), n(p['pam'])),
    bom=lambda p: u1('Stabilisateur de pression amont DN%s (consigne %s bar)' % (n(p['dn']), n(p['pam']))))
inl('rd', nom='Régulateur / limiteur de débit', fam=F5, ab='RD', p={'dn': 100, 'q': 20, 'reg': True},
    f=[_l('q', 'num', 'Débit (m³/h)'), FREG], draw=lambda p: BOX('RD'),
    lbl=lambda p: 'RD DN%s – %s m³/h' % (n(p['dn']), n(p['q'])),
    bom=lambda p: u1('Régulateur de débit DN%s (%s m³/h)' % (n(p['dn']), n(p['q']))))
inl('vr', nom='Vanne de régulation hydraulique', fam=F5, ab='VR', kw='multifonction',
    p={'dn': 100, 'fn': 'Réduction + stabilisation', 'reg': True},
    f=[_l('fn', 'txt', 'Fonction(s)'), FREG], draw=lambda p: BOX('VR'),
    bom=lambda p: u1('Vanne de régulation hydraulique DN%s – %s' % (n(p['dn']), p['fn'])))
inl('va', nom='Vanne altimétrique', fam=F5, ab='VA', kw='réservoir niveau', p={'dn': 100, 'reg': True}, f=[FREG],
    draw=lambda p: BOX('VA'), bom=lambda p: u1('Vanne altimétrique DN%s' % n(p['dn'])))
up('ventouse', nom='Ventouse', fam=F5, ab='Ventouse', kw='purge air dégazage', dn=80,
   dl=lambda p: [40, 50, 60, 65, 80, 100, 150],
   p={'typ': 'Trifonctionnelle', 'iso': True, 'reg': True},
   f=[_l('typ', 'sel', 'Type', o=[['Trifonctionnelle', 'Trifonctionnelle'], ['Double fonction', 'Double fonction'],
                                  ['Simple fonction', 'Simple fonction (dégazage)']]),
      _l('iso', 'chk', 'Robinet d’isolement'), FREG],
   draw=lambda p: '<path d="M0 9V2M-9 2Q0 -12 9 2"/>' + ('<rect x="-13" y="-10" width="26" height="30"/>' if p.get('reg') else ''),
   bom=lambda p: [u1('Ventouse %s DN%s' % (str(p['typ']).lower(), n(p['dn']))),
                  p.get('iso') and u1('Robinet d’isolement de ventouse DN%s' % n(p['dn']))])
_EXU = [['Fossé / exutoire', 'Fossé / exutoire naturel'], ['Regard de vidange', 'Regard de vidange (pompage)'],
        ['Réseau pluvial', 'Réseau d’eaux pluviales']]
define('vidange', nom='Vidange / purge de réseau', fam=F5, kw='décharge',
       p={'dn': 80, 'exu': 'Fossé / exutoire', 'bac': True, 'reg': False},
       fields=[_l('dn', 'dn', 'Diamètre', dl=lambda p: [d for d in MAT['fd']['dn'] if d <= 200]),
               _l('exu', 'sel', 'Rejet', o=_EXU), FBAC, FREG],
       ports=lambda p: [_q(-20, 0, 180, 'B', p['dn'], 'fd')],
       draw=lambda p: '<path d="M-20 0H-12"/>' + BOW + '<path d="M13 0H26" style="stroke-dasharray:1 4"/><path d="M33 -6H27V6H33"/>',
       lbl=lambda p: 'Vidange DN%s' % n(p['dn']),
       bom=lambda p: [u1('Robinet-vanne de vidange DN%s' % n(p['dn'])),
                      u1('Conduite de vidange vers %s' % str(p['exu']).lower(), 1, 'ens')])


# conduite de purge : sans pression, en pointillé, flèche = sens d'écoulement ; se branche sur toute sortie
def plg(p):
    dl = num(p.get('dl'))
    return dl if dl > 0 else max(50, min(300, 30 + num(p.get('L')) * 2))


define('purge', nom='Conduite de purge', fam=F5, kw='vidange évacuation pointillé flèche exutoire',
       p={'dn': 50, 'L': 5, 'dl': 0, 'exu': 'Fossé / exutoire'},
       fields=[_l('dn', 'dn', 'Diamètre', dl=lambda p: DNT, raw=1), _l('L', 'num', 'Longueur réelle (m)', st=0.5),
               _l('dl', 'num', 'Longueur dessin (0 = auto)', st=10),
               _l('exu', 'sel', 'Rejet', o=_EXU + [['Réseau d’eaux usées', 'Réseau d’eaux usées']])],
       ports=lambda p: [_q(0, 0, 180, 'C', p['dn'], any=1)],
       draw=lambda p: '<path class="w3" d="M0 0H%s" style="stroke-dasharray:1 5"/><path class="f" d="M%s 0L%s -5V5Z"/>' % (
           n(plg(p) - 9), n(plg(p)), n(plg(p) - 10)),
       la=lambda p: [plg(p) / 2, 0, 0, -1],
       lbl=lambda p: 'Purge DN%s%s' % (n(p['dn']), (' – %s m' % n(p['L'])) if num(p.get('L')) else ''),
       bom=lambda p: u1('Conduite de purge DN%s vers %s' % (n(p['dn']), str(p['exu']).lower()),
                        num(p.get('L')) or 1, 'ml' if num(p.get('L')) else 'ens'))
up('soupape', nom='Soupape de décharge', fam=F5, ab='SD', dn=80, dl=lambda p: [40, 50, 60, 65, 80, 100, 150], p={'pt': 10},
   f=[_l('pt', 'num', 'Tarage (bar)', st=0.1)], draw=lambda p: BOX('SD'),
   bom=lambda p: u1('Soupape de décharge DN%s (tarage %s bar)' % (n(p['dn']), n(p['pt']))))
up('antibelier', nom='Réservoir anti-bélier', fam=F5, ab='Anti-bélier', kw='coup de bélier', dn=100,
   p={'vol': 500, 'typ': 'Réservoir à vessie'},
   f=[_l('typ', 'sel', 'Type', o=[['Réservoir à vessie', 'À vessie'], ['Réservoir à air', 'À air (compresseur)'],
                                  ['Cheminée d’équilibre', 'Cheminée d’équilibre']]), _l('vol', 'num', 'Volume (L)')],
   draw=lambda p: '<path class="fw" d="M-9 13H9L0 -4ZM-9 -21H9L0 -4Z"/><path d="M0 20V13M0 -21V-25"/><ellipse class="fw" cy="-29" rx="6" ry="4"/>',
   lbl=lambda p: 'Anti-bélier %s L' % n(p['vol']),
   bom=lambda p: u1('%s %s L – DN%s' % (p['typ'], n(p['vol']), n(p['dn']))))
define('flotteur', nom='Robinet à flotteur', fam=F5, kw='réservoir', p={'dn': 80}, fields=[FDN],
       ports=lambda p: [_q(-20, 0, 180, 'B', p['dn'], 'fd')],
       draw=lambda p: '<path d="M-20 0H-12"/>' + BOW + '<path d="M0 0V-14H14"/><circle class="fw" cx="18" cy="-14" r="4"/>',
       lbl=lambda p: 'Flotteur DN%s' % n(p['dn']), bom=lambda p: u1('Robinet à flotteur DN%s' % n(p['dn'])))

# ================================================================ BRANCHEMENT & COMPTAGE
_TYP_PRISE = [['Collier + robinet', 'Collier + robinet (2 pièces)'], ['Robinet à collier intégré', 'Robinet à collier intégré'],
              ['Prise électrosoudable PE', 'Prise électrosoudable PE (avec robinet)'],
              ['Collier de prise seul', 'Collier seul (sans robinet)']]
define('prise', nom='Robinet de prise en charge', fam=F6, kw='PEC collier branchement', dn2def=32,
       p={'mat': 'fd', 'dn': 100, 'dn2': 32, 'typ': 'Collier + robinet', 'bac': True},
       fields=[FMAT(MATS), _l('dn', 'dn', 'Conduite principale'), _l('dn2', 'dn', 'Branchement PE', m='pe', dl=lambda p: PEB),
               _l('typ', 'sel', 'Type', o=_TYP_PRISE), FBAC],
       ports=lambda p: [_q(-20, 0, 180, 'C', p['dn']), _q(20, 0, 0, 'C', p['dn']), _q(0, -44, 270, 'K', p['dn2'], 'pe')],
       draw=lambda p: '<path class="w4" d="M-20 0H20"/><path d="M0 0V-44"/>' + (
           '<rect class="fw" x="-9" y="-7" width="18" height="10" rx="2"/>' if str(p['typ']).startswith('Collier') else '') + (
           '<circle class="f" cy="-14" r="3.5"/>' if p['typ'] != 'Collier de prise seul' else ''),
       la=lambda p: [0, 6, 0, 1], lbl=lambda p: 'PEC %s/Ø%s' % (fmt(p), n(p['dn2'])),
       bom=lambda p: u1('%s sur %s %s – sortie PE Ø%s (%s)' % (
           'Collier de prise en charge' if p['typ'] == 'Collier de prise seul' else 'Robinet de prise en charge',
           MAT[m_of(p)]['nom'], fmt(p), n(p['dn2']), str(p['typ']).lower())))
define('robbr', nom='Robinet d’arrêt de branchement', fam=F6, kw='robinet sous bouche à clé',
       p={'mat': 'pe', 'dn': 32, 'typ': 'Tête carrée', 'bac': True},
       fields=[FPE, _l('typ', 'sel', 'Manœuvre', o=[['Tête carrée', 'Tête carrée (sous bouche à clé)'], ['Quart de tour', 'Quart de tour']]), FBAC],
       ports=lambda p: [K(-18, 0, 180, p['dn']), K(18, 0, 0, p['dn'])],
       draw=lambda p: ('<path d="M-18 0H-7M7 0H18"/>' + ROB14) if p['typ'] == 'Quart de tour'
       else '<path d="M-18 0H18"/><circle class="f" r="3.5"/>',
       lbl=lambda p: 'Robinet Ø%s' % n(p['dn']),
       bom=lambda p: u1('Robinet d’arrêt de branchement PE Ø%s – %s' % (n(p['dn']), str(p['typ']).lower())))
define('boisseau', nom='Robinet à boisseau sphérique', fam=F6, kw='avant compteur après compteur quart de tour',
       p={'dn': 20, 'typ': 'Robinet avant compteur'},
       fields=[FAC(), _l('typ', 'sel', 'Usage', o=[['Robinet avant compteur', 'Avant compteur (quart de tour)'],
                                                  ['Robinet après compteur', 'Après compteur (avec purge)'],
                                                  ['Robinet de purge', 'Purge / vidange'], ['Robinet d’isolement', 'Isolement']])],
       ports=lambda p: [_q(-16, 0, 180, 'F', p['dn'], 'ac'), _q(16, 0, 0, 'F', p['dn'], 'ac')],
       draw=lambda p: '<path d="M-16 0H-7M7 0H16"/>' + ROB14,
       lbl=lambda p: '%s DN%s' % (str(p['typ']).replace('Robinet ', '', 1), n(p['dn'])),
       bom=lambda p: u1('%s à boisseau sphérique DN%s' % (p['typ'], n(p['dn']))))
inl('compteur', nom='Compteur d’eau', fam=F6, thr=1, k1='M', ab='Compteur', dl=[15, 20, 25, 32, 40, 50, 65, 80, 100, 150, 200],
    p={'dn': 15, 'typ': 'Volumétrique', 'log': 'Regard de comptage', 'tete': False},
    f=[_l('typ', 'sel', 'Technologie', o=[['Volumétrique', 'Volumétrique'], ['Vitesse jet unique', 'Vitesse (jet unique)'],
                                          ['Woltmann', 'Woltmann'], ['Électromagnétique', 'Électromagnétique / ultrasons']]),
       _l('log', 'sel', 'Logement', o=[['', 'Aucun'], ['Regard de comptage', 'Regard de comptage'],
                                       ['Abri de compteur incongelable', 'Abri / citerneau incongelable'],
                                       ['Niche de comptage en façade', 'Niche en façade'], ['Local technique', 'Local technique']]),
       _l('tete', 'chk', 'Tête émettrice (télérelève)')],
    draw=lambda p: '<path d="M-12 0H-10M10 0H12"/><circle class="fw" r="10"/><path d="M-7 -7L7 7"/>',
    lbl=lambda p: 'Compteur DN%s' % n(p['dn']),
    bom=lambda p: [u1('Compteur %s DN%s' % (str(p['typ']).lower(), n(p['dn']))),
                   p.get('log') and u1(p['log']), p.get('tete') and u1('Tête émettrice de télérelève')])
inl('clapetea', nom='Clapet anti-retour contrôlable (EA)', fam=F6, thr=1, k1='F', k2='M', ab='EA', p={'dn': 20},
    draw=lambda p: BOX('EA'))
inl('disco', nom='Disconnecteur BA', fam=F6, thr=1, ab='BA', kw='protection retour eau', p={'dn': 40}, draw=lambda p: BOX('BA'),
    bom=lambda p: u1('Disconnecteur à zone de pression réduite contrôlable (BA) DN%s' % n(p['dn'])))
inl('debit', nom='Débitmètre électromagnétique', fam=F6, ab='Q', kw='sectorisation', p={'dn': 100}, draw=lambda p: BOX('Q'))

# ================================================================ INCENDIE & USAGES
up('poteau', nom='Poteau d’incendie', fam=F7, ab='PI', kw='hydrant PI défense', dn=100, dl=lambda p: [80, 100, 150],
   p={'typ': 'Incongelable'},
   f=[_l('typ', 'sel', 'Type', o=[['Incongelable', 'Incongelable'], ['Renversable', 'Renversable'],
                                  ['À prises apparentes', 'À prises apparentes']])],
   draw=lambda p: '<path d="M0 9V6"/><circle class="fw" cy="-2" r="8"/><path class="f" d="M-8 -2A8 8 0 0 0 8 -2Z"/>',
   bom=lambda p: u1('Poteau d’incendie DN%s %s' % (n(p['dn']), str(p['typ']).lower())))
up('bi', nom='Bouche d’incendie', fam=F7, ab='BI', dn=100, dl=lambda p: [100], ns=1, nm=1,
   draw=lambda p: '<path d="M-12 20H12"/><rect class="fw" x="-8" y="-1" width="16" height="16"/><path class="f" d="M-8 15H8V-1Z"/>')
up('arrosage', nom='Bouche d’arrosage / de lavage', fam=F7, ab='BA', k='F', m='ac', dn=40, ns=1, nm=1,
   dl=lambda p: [25, 32, 40], p={'typ': 'Bouche d’arrosage'},
   f=[_l('typ', 'sel', 'Type', o=[['Bouche d’arrosage', 'Bouche d’arrosage'], ['Bouche de lavage', 'Bouche de lavage'],
                                  ['Prise d’eau de voirie', 'Prise d’eau de voirie']])],
   draw=lambda p: '<path d="M-16 20H16"/><rect class="fw" x="-9" y="2" width="18" height="18"/>'
                  '<circle class="f" cx="-4" cy="11" r="2"/><circle class="f" cx="4" cy="11" r="2"/>',
   lbl=lambda p: '%s DN%s' % (p['typ'], n(p['dn'])), bom=lambda p: u1('%s DN%s' % (p['typ'], n(p['dn']))))
up('fontaine', nom='Borne fontaine', fam=F7, ab='Borne fontaine', k='F', m='ac', dn=20, dl=lambda p: [15, 20, 25],
   draw=lambda p: '<rect class="fw" x="-5" y="-22" width="10" height="31"/><path d="M5 -16H12V-11"/>')
up('puisage', nom='Borne de puisage', fam=F7, ab='Borne puisage', thr=1, dn=65, dl=lambda p: [40, 50, 65, 80, 100],
   draw=lambda p: '<rect class="fw" x="-8" y="-20" width="16" height="29" rx="2"/><text class="tx" y="-3">P</text>')
define('reglage', nom='Pièce de réglage (en S)', fam=F7, kw='mise à niveau poteau incendie rehausse', p={'dn': 100},
       fields=[_l('dn', 'dn', 'Diamètre', dl=lambda p: [80, 100, 150])],
       ports=lambda p: [_q(-20, -7, 180, 'B', p['dn'], 'fd'), _q(20, 7, 0, 'B', p['dn'], 'fd')],
       draw=lambda p: '<path class="w3" d="M-20 -7C0 -7 0 7 20 7"/>',
       lbl=lambda p: 'Pièce de réglage DN%s' % n(p['dn']),
       bom=lambda p: u1('Pièce de réglage (en S) à brides DN%s' % n(p['dn'])))
define('abonne', nom='Abonné / installation privée', fam=F7, kw='limite propriété', p={'txt': ''},
       fields=[_l('txt', 'txt', 'Nom / n°')],
       ports=lambda p: [{'x': -20, 'y': 0, 'd': 180, 'k': 'C', 'any': 1}],
       draw=lambda p: '<path d="M-20 0H-10"/><path class="fw" d="M-10 9V-5L0 -14L10 -5V9Z"/>',
       lbl=lambda p: p.get('txt') or 'Abonné')

# ================================================================ OUVRAGES
define('existant', nom='Réseau existant (raccordement)', fam=F8, kw='piquage départ', p={'mat': 'fd', 'dn': 150, 'txt': ''},
       fields=[FMAT(MATS), FDN, _l('txt', 'txt', 'Repère / rue')],
       ports=lambda p: [_q(20, 0, 0, 'C', p['dn'])],
       draw=lambda p: '<path class="w4 da" d="M-26 0H20"/><path class="w3" d="M-26 -10V10"/>',
       la=lambda p: [-3, 0, 0, -1],
       lbl=lambda p: 'Existant %s %s%s' % (MAT[m_of(p)]['ab'], fmt(p), (' – ' + p['txt']) if p.get('txt') else ''))


def _reservoir_draw(p):
    geo = 'géodésique' in str(p['typ'])
    s = '<path d="M-40 -14H-14.3M-40 14H-14.3M40 14H14.3"/><circle class="fw" r="20"/>'
    if geo or 'Château' in str(p['typ']):
        s += '<circle r="12"/>'
        if geo:
            s += ('<circle class="f" r="4"/><text class="tx" x="20" y="-20" style="text-anchor:start">%.2f m</text>'
                  % (num(p.get('cote')) or 0))
        return s
    return s + '<path d="M-12 16V32H12V16"/>'


define('reservoir', nom='Réservoir / château d’eau', fam=F8, kw='point géodésique',
       p={'typ': 'Réservoir semi-enterré', 'vol': 500, 'dn': 150, 'dn2': 100, 'cote': 0},
       fields=[_l('typ', 'sel', 'Type', o=[['Réservoir semi-enterré', 'Semi-enterré'], ['Réservoir enterré', 'Enterré'],
                                          ['Château d’eau', 'Château d’eau'],
                                          ['Réservoir surélevé (point géodésique)', 'Surélevé – point géodésique'],
                                          ['Bâche de reprise', 'Bâche de reprise']]),
               _l('vol', 'num', 'Volume (m³)'), _l('cote', 'num', 'Cote point géodésique (m)', st=0.01),
               _l('dn', 'dn', 'Diamètre départ'), _l('dn2', 'dn', 'Diamètre arrivée / vidange')],
       ports=lambda p: [_q(-40, -14, 180, 'B', p['dn2'], 'fd'), _q(40, 14, 0, 'B', p['dn'], 'fd'),
                        _q(-40, 14, 180, 'B', p['dn2'], 'fd')],
       draw=_reservoir_draw, la=lambda p: [0, 32, 0, 1],
       lbl=lambda p: '%s %s m³' % (p['typ'], n(p['vol'])),
       bom=lambda p: u1('%s %s m³' % (p['typ'], n(p['vol'])), 1, 'ens'))
inl('pompe', nom='Pompe / surpresseur', fam=F8, ab='Pompe', kw='refoulement surpression',
    p={'dn': 100, 'typ': 'Pompe de refoulement', 'q': 30, 'hmt': 40, 'n': 1},
    f=[_l('typ', 'sel', 'Type', o=[['Pompe de refoulement', 'Pompe de refoulement'], ['Surpresseur', 'Surpresseur'],
                                   ['Pompe immergée', 'Pompe immergée (forage)']]),
       _l('q', 'num', 'Débit (m³/h)'), _l('hmt', 'num', 'HMT (m)'), _l('n', 'num', 'Nombre')],
    draw=lambda p: '<circle class="fw" r="12"/><path d="M-12 0Q-6 -8 0 0T12 0"/><circle class="f" r="2"/>',
    lbl=lambda p: '%s %s m³/h – %s m' % (p['typ'], n(p['q']), n(p['hmt'])),
    bom=lambda p: u1('%s %s m³/h à %s m HMT – DN%s' % (p['typ'], n(p['q']), n(p['hmt']), n(p['dn'])), num(p.get('n')) or 1))
CAP = [['Puits / forage', 'Puits, forage'], ['Source (captage)', 'Source (captage)'],
       ['Prise d’eau superficielle', 'Prise d’eau superficielle']]


def _forage_draw(p):
    if p['typ'] == 'Source (captage)':
        return '<path class="fw" d="M-7 -8V8L7 0Z"/><path d="M7 0H20"/>'
    if p['typ'] == 'Prise d’eau superficielle':
        return '<path d="M-7 -8H1V8H-7M1 0H20"/>'
    return '<circle class="fw" r="7"/><path d="M7 0H20"/>'


define('forage', nom='Captage (source, puits, forage, prise d’eau)', fam=F8, kw='source puits forage prise superficielle',
       p={'typ': 'Puits / forage', 'dn': 100, 'prof': 50, 'q': 20},
       fields=[_l('typ', 'sel', 'Type', o=CAP), FDN, _l('prof', 'num', 'Profondeur (m)'), _l('q', 'num', 'Débit (m³/h)')],
       ports=lambda p: [_q(20, 0, 0, 'B', p['dn'], 'fd')],
       draw=_forage_draw,
       lbl=lambda p: ('Forage %s m – %s m³/h' % (n(p['prof']), n(p['q']))) if p['typ'] == 'Puits / forage'
       else '%s – %s m³/h' % (p['typ'], n(p['q'])),
       bom=lambda p: u1(('Tête de forage / captage DN%s (profondeur %s m)' % (n(p['dn']), n(p['prof'])))
                        if p['typ'] == 'Puits / forage' else '%s – ouvrage de captage DN%s' % (p['typ'], n(p['dn'])), 1, 'ens'))
inl('traitement', nom='Poste de traitement', fam=F8, ab='Traitement', kw='chloration désinfection UV',
    p={'dn': 100, 'typ': 'Chloration (hypochlorite)'},
    f=[_l('typ', 'sel', 'Type', o=[['Chloration (hypochlorite)', 'Chloration (hypochlorite)'], ['Chloration gazeuse', 'Chloration gazeuse'],
                                   ['Désinfection UV', 'Désinfection UV'], ['Filtration', 'Filtration'],
                                   ['Reminéralisation', 'Reminéralisation']])],
    draw=lambda p: '<rect class="fw" x="-12" y="-9" width="24" height="18"/><path d="M-5 9V-1M5 9V-1"/>',
    lbl=lambda p: p['typ'], bom=lambda p: u1('Poste de traitement – %s DN%s' % (str(p['typ']).lower(), n(p['dn'])), 1, 'ens'))

# ================================================================ ANNOTATIONS
define('regard', nom='Regard / chambre (cadre)', fam=F9, back=True,
       p={'txt': 'Chambre de vannes', 'dim': '1,20 × 1,20 m', 'w': 120, 'h': 80, 'bom': True},
       fields=[_l('txt', 'txt', 'Libellé'), _l('dim', 'txt', 'Dimensions réelles'), _l('w', 'num', 'Largeur dessin', st=10),
               _l('h', 'num', 'Hauteur dessin', st=10), _l('bom', 'chk', 'Compter en nomenclature')],
       ports=lambda p: [],
       draw=lambda p: ('<rect class="da" x="%s" y="%s" width="%s" height="%s" rx="4"/>'
                       '<text class="tx" x="%s" y="%s" style="text-anchor:start">%s</text>') % (
           n(-num(p['w']) / 2), n(-num(p['h']) / 2), n(p['w']), n(p['h']),
           n(-num(p['w']) / 2 + 5), n(-num(p['h']) / 2 + 13), esc(p['txt'])),
       lbl=None,
       bom=lambda p: u1('Regard / chambre %s%s' % (p['dim'], (' – ' + p['txt']) if p.get('txt') else '')) if p.get('bom') else None)
define('texte', nom='Texte / note', fam=F9, p={'txt': 'Note', 'sz': 12},
       fields=[_l('txt', 'txt', 'Texte'), _l('sz', 'num', 'Taille')],
       ports=lambda p: [],
       draw=lambda p: '<text class="tx" style="font-size:%spx;font-weight:normal">%s</text>' % (n(num(p['sz']) or 12), esc(p['txt'])),
       lbl=None)


# ---------------------------------------------------------------- champs
def dn_list(p, f):
    return f['dl'](p) if f.get('dl') else MAT[f.get('m') or m_of(p)]['dn']


def opt_list(p, f):
    """Valeurs proposées par un champ : [(valeur, libellé), …] (None pour
    les champs libres : texte, nombre, case à cocher)."""
    if f['t'] == 'dn':
        m = f.get('m') or m_of(p)
        return [[d, MAT[m]['pref'] + n(d)] for d in dn_list(p, f)]
    if f['t'] == 'mat':
        return [[m, MAT[m]['nom']] for m in f['o']]
    o = f.get('o')
    if o is None:
        return None
    return o(p) if callable(o) else o
