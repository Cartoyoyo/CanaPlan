# tools/schemaep/svg_qt.py
"""Dessins SchemAEP → documents SVG autonomes pour QSvgRenderer.

Les dessins du catalogue utilisent des classes CSS (w3, w4, f, fw, da, tx) et
la couleur courante (currentColor), comme la page HTML. Le moteur SVG de Qt
ne lit pas les feuilles de style : chaque élément reçoit ici un attribut
style complet, couleur de la pièce comprise.
"""
import re

from .catalogue import T, mark
from .moteur import pts

# styles de base (sélecteur « .it * » de la page HTML) puis classes
_BASE = {'fill': 'none', 'stroke': 'C', 'stroke-width': '2',
         'stroke-linejoin': 'round', 'stroke-linecap': 'round'}
_CLASSES = {
    'w3': {'stroke-width': '3'},
    'w4': {'stroke-width': '4.5'},
    'f': {'fill': 'C'},
    'fw': {'fill': '#ffffff'},
    'da': {'stroke-dasharray': '5 4'},
    'tx': {'fill': 'C', 'stroke': 'none', 'font-family': 'Arial', 'font-weight': 'bold',
           'font-size': '9px', 'text-anchor': 'middle'},
}
_TAG = re.compile(r'<(path|rect|circle|ellipse|text)\b([^>]*?)(/?)>')
_ATTR = re.compile(r'\s(class|style)="([^"]*)"')


def _style(tag, attrs, couleur, epaisseur):
    st = dict(_BASE)
    if tag == 'text':
        st.update(_CLASSES['tx'])
    classes = []
    decl = ''
    for nom, val in _ATTR.findall(attrs):
        if nom == 'class':
            classes = val.split()
        else:
            decl = val
    for c in classes:
        st.update(_CLASSES.get(c, {}))
    for d in decl.split(';'):
        if ':' in d:
            k, v = d.split(':', 1)
            st[k.strip()] = v.strip()
    if epaisseur and st.get('stroke') != 'none':
        st['stroke-width'] = str(float(st['stroke-width']) + epaisseur)
    if epaisseur and tag == 'text':
        st['stroke'] = 'C'
        st['stroke-width'] = str(epaisseur)
    return ';'.join('%s:%s' % (k, couleur if v == 'C' else v) for k, v in st.items())


def styler(fragment, couleur, epaisseur=0):
    """Remplace classes et currentColor par des styles explicites.
    epaisseur > 0 : épaissit tous les traits (halo de sélection)."""
    def rep(m):
        tag, attrs, fin = m.group(1), m.group(2), m.group(3)
        reste = _ATTR.sub('', attrs)
        return '<%s%s style="%s"%s>' % (tag, reste, _style(tag, attrs, couleur, epaisseur), fin)
    return _TAG.sub(rep, fragment)


def dessin(it):
    """Dessin local d'une pièce (corps + extrémités), classes CSS."""
    return T[it['t']].draw(it['p']) + ''.join(mark(q, it['p'].get('verr')) for q in pts(it))


def document(fragment, couleur, epaisseur=0):
    """Document SVG complet ; le dessin est dans <g id="g"> pour que
    QSvgRenderer.boundsOnElement('g') donne son encombrement."""
    return ('<svg xmlns="http://www.w3.org/2000/svg" viewBox="-500 -500 1000 1000">'
            '<g id="g">%s</g></svg>') % styler(fragment, couleur, epaisseur)
