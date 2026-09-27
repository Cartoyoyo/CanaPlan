# tools/schemaep/langue.py
"""Langue d'affichage du catalogue SchemAEP.

Le moteur et le catalogue restent en français (valeurs des .json, défauts
validés, parité avec la page SchemAEP) ; l'interface traduit ce qu'elle
affiche par traduire(). Sans langue définie — tests, moteur seul — tout
reste en français, sans aucun coût.

L'interface branche sa langue par definir_langue(fn), fn rendant le code
courant ('fr', 'en', 'es', 'pt', 'de').
"""
import re

from .traductions import CATALOGUE, UNITES

LANGUES = ('en', 'es', 'pt', 'de')
_source = None
_cache = {}          # langue -> (dict minuscules -> traduction, regex des morceaux)
_BORD = r'[\wÀ-ÿœŒ’\'-]'


def definir_langue(fn):
    """fn() -> code de langue ; None : français."""
    global _source
    _source = fn


def langue():
    try:
        return (_source() if _source else 'fr') or 'fr'
    except Exception:           # langue illisible (QSettings absent) : français
        return 'fr'


def _table(code):
    if code not in _cache:
        i = LANGUES.index(code)
        table = {fr.lower(): tr[i] for fr, tr in CATALOGUE.items()}
        cles = sorted(table, key=len, reverse=True)
        motif = re.compile('(?<!%s)(%s)(?!%s)' % (_BORD, '|'.join(re.escape(c) for c in cles), _BORD),
                          re.IGNORECASE)
        _cache[code] = (table, motif)
    return _cache[code]


def _casse(source, cible, code):
    """Initiale de la traduction calée sur celle du texte français ; les noms
    allemands et les sigles (« PE outlet », « UV ») gardent leur majuscule."""
    if not cible or not source[:1].isalpha():
        return cible
    if source[0].isupper():
        return cible[0].upper() + cible[1:]
    if code == 'de' or (len(cible) > 1 and cible[1].isupper()):
        return cible
    return cible[0].lower() + cible[1:]


def traduire(texte):
    """Texte du catalogue (nom, champ, option, désignation, message) dans la
    langue d'affichage ; inchangé en français ou s'il n'est pas connu."""
    code = langue()
    if code not in LANGUES or not texte:
        return texte
    texte = str(texte)
    table, motif = _table(code)
    entier = table.get(texte.lower())
    if entier is not None:
        return _casse(texte, entier, code)
    texte = motif.sub(lambda m: _casse(m.group(0), table[m.group(0).lower()], code), texte)
    # typographie : pas d'espace avant « : » hors du français
    return re.sub(r' ([:;!?])', lambda m: m.group(1), texte)


def unite(u):
    code = langue()
    if code not in LANGUES:
        return u
    return UNITES.get(u, (u,) * 4)[LANGUES.index(code)]
