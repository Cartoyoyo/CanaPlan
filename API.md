# API de pilotage CanaPlan

Référence du module `CanaPlan.tools.api` — 43 fonctions publiques pour piloter
le plugin depuis la console Python de QGIS, un script, un serveur MCP ou un
agent, **sans jamais ouvrir de fenêtre**.

```python
from CanaPlan.tools import api
api.aide()          # sommaire : signature et résumé de chaque fonction
```

---

## 1. Pourquoi ce module

Les outils de CanaPlan sont conçus pour une souris : des `QgsMapTool` nourris
par des clics, des `QDialog` qui rendent des dictionnaires. Pilotés de
l'extérieur, ils posent trois problèmes qui n'existent pas sous la main d'un
opérateur.

**Les modales bloquent.** Un `QMessageBox` ouvert depuis un appel distant fige
QGIS : plus rien ne répond, la session est perdue. L'API neutralise les quatre
entrées de `QMessageBox` et `QDialog.exec` pendant chaque opération, collecte
les messages et les rend dans le résultat sous la clé `messages`.

**Les tolérances de snap sont en pixels.** `30 * mapUnitsPerPixel()` est juste
sous la souris — l'opérateur vise ce qu'il voit. Piloté par script, le zoom
devient un paramètre caché : à l'échelle de la rue, la tolérance des regards
vaut 8 m et fusionne des ouvrages distincts. L'API impose `TOL_SNAP_M = 0.20`
via le paramètre `tol_m` ajouté aux outils de dessin.

**Chaque aller-retour coûte.** Reconstruire l'état à chaque appel domine le
temps total. L'API expose des verbes métier qui font une opération complète en
un appel et rendent un résultat sérialisable.

**Ce module ne contient aucune logique métier.** Tout est délégué aux outils
existants — `DrawConduiteTool._add_point`, `RenommerTool._rename_path`,
`PrintTool.definir_feuilles`… — pour que le résultat soit identique au geste
manuel : snapping, topologie, valeurs par défaut comprises.

---

## 2. Démarrage rapide

```python
from CanaPlan.tools import api

# 1. Projet, à une adresse, avec tous les fonds
api.nouveau_projet(adresse="Rue Julien Charpentier, 03250 Châtel-Montagne",
                   dossier="~/Documents/CanaPlan", nom="Charpentier")
api.attendre_fonds(["PCI - Bati"])          # le WFS est asynchrone

# 2. Réseau EU sur l'axe de la rue
axe = api.axe_de_rue("Rue Julien Charpentier", "Châtel-Montagne")
api.tracer_conduite("EU", axe=axe, entraxe_max=50, tol_axe=0.5)

# 3. Un branchement par bâtiment à moins de 10 m
api.creer_branchements("EU", distance_max=10)

# 4. Numérotation et cotes
api.renumeroter("EU")                        # REU01… / EU-BRCHT01…
api.caler_cotes("EU", tn=100, pente=1.0, ancrage=("REU07", 2.50),
                tabourets={"tn": 100, "profondeur": 0.50})
api.verifier("EU")

# 5. Livraison
api.enregistrer()
t = api.exporter_async(echelle=200, format="A4", orientation="portrait",
                       fonds_wms=False)
api.tache(t["ticket"])                       # à interroger jusqu'à "fini"
api.fermer()
```

Ou d'un seul appel : `api.chantier(...)`.

---

## 3. Référence

### 3.1 Lecture et séance

| Fonction | Rôle |
|---|---|
| `etat()` | Inventaire : couches métier par réseau (nom, entités, provider), fonds chargés, projet courant, fenêtres ouvertes. |
| `lire(reseau, role, champs=None)` | Entités d'un rôle en liste de dicts, avec `__id`. |
| `verifier(reseau="EU")` | Contrôle avant livraison : champs restés vides par rôle, conduites en contre-pente, contrôle des branchements. |
| `aide(domaine=None)` | Sommaire : signature exacte et résumé de chaque fonction. Point d'entrée conseillé pour un agent. |
| `fermer(detruire=True)` | Ferme et détruit les fenêtres CanaPlan, désactive l'outil carte. |
| `dependances_manquantes()` | Bibliothèques absentes, par usage : `dxf` (ezdxf) et `pdf` (pypdf). |

`etat()` rend sous `projet` le **.bet courant** — celui que retient le plugin —
et sous `qgs` le fichier de projet QGIS, presque toujours vide : un projet
CanaPlan est une archive .bet, pas un .qgs, et `QgsProject.fileName()` rendait
donc `null` juste après `nouveau_projet()`. Les chemins rendus par l API sont
normalisés (`~` développé, séparateurs homogènes).

`fermer()` est à appeler en fin de séance scriptée. Instancier un dialogue pour
lire ses accesseurs laisse un widget vivant, invisible mais bien présent, et ils
s'accumulent d'une opération à l'autre. Une session de pilotage ordinaire en
avait laissé quatre — trois `ExportDialog` et un `TableauSaisieDialog`.

> **Piège Qt.** `QApplication.processEvents()` ne traite **pas** les suppressions
> différées. Sans `sendPostedEvents(None, QEvent.Type.DeferredDelete)`, un
> widget fermé puis `deleteLater()` survit indéfiniment. `fermer()` poste
> l'événement explicitement, puis attend la destruction effective (1 s au plus)
> avant de rendre `restantes` — qui est donc une liste fiable, pas un instantané
> pris trop tôt.

### 3.2 Données externes

| Fonction | Rôle |
|---|---|
| `adresse(recherche)` | Géocode sur la Base Adresse Nationale. Rend label, score, code INSEE, lon/lat et x/y en Lambert 93. |
| `axe_de_rue(nom_voie, commune=None, insee=None, rafraichir=False)` | Axe de chaussée depuis OpenStreetMap, en Lambert 93 (`QgsGeometry` ligne). Mis en cache pour la session. |

L'axe OSM **est** l'axe de la voie : une conduite posée dessus est centrée dans
la rue par construction. Overpass refuse les requêtes sans `User-Agent`
(HTTP 406) ; l'API en fournit un.

L'appel coûte 2 à 4 s et l'axe ne bouge pas d'une seconde à l'autre : le
résultat est **gardé en cache pour la session**, sur la clé (voie, commune,
insee). Le rappeler pour le passer à `implanter_regards` puis à
`tracer_conduite` est donc gratuit ; `rafraichir=True` force une nouvelle
requête.

### 3.3 Projet

| Fonction | Rôle |
|---|---|
| `nouveau_projet(adresse=None, dossier=None, nom=None, fonds=None, demi_emprise=200.0)` | Crée un projet `.bet`. |
| `charger(chemin)` | Charge un `.bet`, sans compte rendu modal. |
| `enregistrer(chemin=None)` | Enregistre le projet courant, sans barre de progression. |
| `enregistrer_sous(chemin)` | Enregistre sous un nouveau nom. |
| `projets_recents()` | Derniers `.bet` ouverts, projet courant, dossier. |

`nouveau_projet` reproduit la dernière page de l'assistant sans construire la
fenêtre. **Par défaut il charge tous les fonds**, dont le bâti cadastral que
l'assistant laisse décoché alors qu'il est indispensable aux branchements.

`enregistrer` passe par `_do_save(..., silencieux=True)` : pas de
`QProgressDialog`, donc pas de `processEvents`. Ce n'est pas qu'un confort —
chaque `processEvents` de la barre sert aussi les rendus de fond en attente
(ortho, WMS), ce qui peut faire durer plusieurs minutes une sauvegarde de
quelques secondes. Les erreurs ne sont pas perdues : elles sont retournées dans
`erreurs`.

### 3.4 Fonds de plan

| Fonction | Rôle |
|---|---|
| `fonds(*demandes, **bascules)` | Charge des fonds. Sans argument, charge tout. |
| `attendre_fonds(noms=("PCI - Bati",), delai=90.0, pas=0.5)` | Bloque jusqu'à leur apparition. |

Clés : `osm`, `ortho`, `ban`, `noms_voie`, `pci_bati`, `pci_parcelles`.

```python
api.fonds("pci_bati", "pci_parcelles")
api.fonds(ortho=False, osm=True)
```

> **Piège numéro un du pilotage.** Les quatre fonds vectoriels passent par un
> WFS **asynchrone** (`QgsTask`) : ils n'existent pas au retour de `fonds()`.
> Sans `attendre_fonds()`, l'appel suivant travaille sur des couches absentes.

### 3.5 Dessin

| Fonction | Rôle |
|---|---|
| `implanter_regards(axe, entraxe_max=50.0, tol_axe=0.5)` | Calcule les abscisses des regards, sans rien dessiner. |
| `tracer_conduite(reseau, axe=None, points=None, entraxe_max=50.0, tol_axe=0.5, vider=False, diametre=None, materiau=None)` | Trace conduite et regards. |
| `creer_branchements(reseau, distance_max=10.0, couche_bati="PCI - Bati", vider=False, diametre=None, materiau=None)` | Un branchement par bâtiment proche. |
| `inserer_regard(point, reseau=None)` | Insère un regard sur une conduite et la coupe en deux. |
| `supprimer(reseau, role, ids)` | Supprime des entités par identifiant. |
| `vider(reseau, roles=…)` | Vide les couches métier d'un réseau. |

**`implanter_regards` applique deux règles, dans cet ordre :**

1. **Un regard à chaque coude** dont l'omission écarterait la conduite de plus
   de `tol_axe` mètres de l'axe réel. Sans cela, la corde d'un long tronçon
   coupe les virages et la conduite sort de la chaussée — mesuré jusqu'à 3,2 m
   sur une rue de 159 m.
2. **Puis subdivision** de tout intervalle plus long que `entraxe_max`, en parts
   égales.

`entraxe_max` est un **maximum**, pas un pas fixe : c'est la lecture métier de
« un regard tous les 50 m », et la règle usuelle en assainissement (regard à
chaque changement de direction, de pente ou de diamètre).

`tracer_conduite` passe par `DrawConduiteTool._add_point`, le point d'entrée
d'un clic : le snapping, la topologie et les valeurs par défaut (diamètre,
matériau) sont ceux du dessin manuel. Fournir soit `axe` (échantillonné par
`implanter_regards`), soit `points` (liste de `QgsPointXY` déjà choisis).

`diametre` et `materiau` valent **pour les seuls ouvrages créés par l'appel** :
ils sont posés dans les défauts du plugin le temps du tracé, puis rendus à leur
état antérieur, y compris si l'appel lève. Passer par `config()` reste possible,
mais change le réglage de toute la session.

```python
api.tracer_conduite("EU", axe=axe, diametre=200, materiau="PVC")
api.creer_branchements("EU", distance_max=8, diametre=160, materiau="PVC")
```

`creer_branchements` part du point de piquage le plus proche sur la conduite et
rejoint le point du bâti le plus proche, où un tabouret est posé. Passe par
`DrawBranchementTool._finish` : tabouret, contrôle topologique, cote de piquage
et attributs sont ceux du tracé manuel. Les échecs sont listés dans `echecs`
plutôt que levés.

`supprimer` est une suppression **brute**, volontairement : le `DeleteTool` du
plugin gère en plus un survol, un lasso et l'effacement d'étiquettes, logique
attachée au pointeur et non reproduite ici. Contrôler après coup avec
`recalculer_pentes()` puis `verifier()`.

### 3.6 Attributs et cotes

| Fonction | Rôle |
|---|---|
| `saisir(reseau, role, valeurs, ou=None)` | Écrit des attributs en masse. |
| `renumeroter(reseau, prefixe_regard=None, prefixe_tabouret=None, depart=1, de=None, vers=None)` | Renumérote de l'amont vers l'aval. |
| `caler_cotes(reseau, tn=None, ancrage=None, pente=None, tabourets=None)` | TN, profondeurs et fils d'eau. |
| `recalculer_pentes(reseau="EU", tolerance=0.05)` | Recalcule les pentes depuis les fils d'eau. |
| `controler_branchements(reseau, pente_max=30.0)` | Pente de chaque branchement, plus la liste des non cotés. |

```python
api.saisir("EU", "regard", {"tn": 100})
api.saisir("EU", "conduite", {"materiau": "PVC"}, ou=lambda f: f["diametre"] == 160)
```

`saisir` n'ouvre pas le tableau de saisie et **ne recalcule pas les champs
dérivés** : enchaîner sur `caler_cotes()` ou `recalculer_pentes()`.

`renumeroter` appelle l'outil du plugin, donc hérite de sa numérotation en
parcours de graphe et de l'ordonnancement des tabourets par tronçon puis par pk
de piquage. Préfixes par défaut : `REU` / `EU-BRCHT` (EU), `REP` / `EP-BRCHT`
(EP), format `%02d` — `depart=1` donne donc `REU01`. Sans `de`/`vers`, les deux
extrémités du réseau sont prises, le nord comme amont.

> **⚠ Convention de signe de la pente.** CanaPlan compte une pente **positive
> pour une conduite descendante** : `FE aval = FE amont − pente% × L`. Une chute
> de 1 cm/m se saisit donc `pente=1.0`, **pas** `-1.0`. Une valeur négative crée
> une contre-pente : le fil d'eau remonte vers l'aval et l'écoulement gravitaire
> ne se fait pas.

`caler_cotes` ancre le calcul sur un regard donné : `ancrage=("REU07", 2.50)`
fixe REU07 à 2,50 m de profondeur. Si l'ancrage est le point bas — cas courant
de l'exutoire — le calcul **remonte** le réseau ; sinon il descend.

Il **cote aussi les branchements** : la cote de piquage et la pente de chaque
branchement sont propagées dans la foulée, par le même calcul que le tableau de
saisie. Il n'y a donc plus à enchaîner `recalculer_pentes()` derrière — celui-ci
reste utile après une écriture directe par `saisir()`.

Le retour donne les 4 cotes de **chaque** ouvrage : `regards`, `pentes` des
tronçons, et `tabourets` — une entrée nommée par tabouret, plus `nb_tabourets`.

`controler_branchements` signale deux choses : les contre-pentes (l'écoulement
ne se fait pas) et, au-delà de `pente_max`, les chutes. Une série de pentes
excessives est presque toujours le signe de tabourets tous calés à la même
profondeur au-dessus d'un collecteur qui, lui, s'enfonce.

Un branchement dont une cote manque n'interrompt rien : il sort dans
`non_cotes`, avec le nom des champs absents, et le compte rendu porte alors un
`conseil`. Les cotes sont lues en NULL-safe — un champ vide remonte du provider
un `QVariant` nul, qui passe le test `is None` et faisait précédemment lever un
`TypeError` au `float()` suivant.

### 3.7 Présentation

| Fonction | Rôle |
|---|---|
| `styles(reseau="EU")` | Réapplique la symbologie (EU rouge, EP bleu). |
| `etiquettes(reseau="EU", roles=None, taille=None, unite=None, champs=None, visibilite=None, forcer_toutes=None, echelle_min=None)` | Moteur d'étiquettes. |
| `config(defauts=None, cubature=None)` | Lit ou modifie les valeurs par défaut. |

`unite` répond à la question qu'on se pose vraiment : **quelle hauteur de texte
sur la feuille imprimée ?**

| `unite` | Sens | Exige |
|---|---|---|
| `'mm'` | millimètres **sur le papier**, à l'échelle du plan | `echelle` |
| `'map'` | unités carte (mètres au sol) | — |
| `'points'` | points typographiques, taille fixe à l'écran | — |

Le moteur d'étiquettes de CanaPlan travaille en unités carte — toute sa mise en
page en dépend : fonds d'étiquette, lignes de rappel, décalages. L'API fait donc
la conversion à partir de l'échelle du plan :

    taille_carte = taille_mm / 1000 × echelle

soit **2,5 mm de papier = 0,50 m au sol au 1/200**. Sans cette conversion, une
taille de `2` lue en unités carte donne 2 m de haut, c'est-à-dire **10 mm de
texte sur la feuille** — le défaut natif du plugin, illisible de trop gros sur un
plan au 1/200.

`echelle` (dénominateur du plan) ne se confond pas avec `echelle_min` (seuil de
dézoom au-delà duquel les étiquettes disparaissent). Le retour donne les deux
lectures de la taille : `taille_carte_m` et `taille_mm_papier`.

La taille s'applique à tout le projet, pas au seul réseau.

`visibilite` accepte trois formes : un booléen (tous les rôles du réseau visé),
`{role: bool}` pour ce réseau, ou la forme complète `{reseau: {role: bool}}`.

Le retour dit **l'état obtenu**, pas les arguments reçus : `roles` traités,
`actives` (étiquettes activées par rôle), `visibilite`, `taille`, `unite`
normalisée et `forcer_toutes`. Un rôle inconnu lève, avec la liste des rôles
attendus.

```python
api.etiquettes("EU", forcer_toutes=True)              # toutes, collisions comprises
api.etiquettes("EU", taille=2.5, unite="mm", echelle=200)   # 2,5 mm sur le papier
api.etiquettes("EU", visibilite={"branchement": False})
```

```python
api.config()   # diamètres/matériaux par défaut + paramètres de cubature
api.config(defauts={"conduite_eu": {"diametre": 315, "materiau": "PVC"}})
```

### 3.8 Calculs

| Fonction | Rôle |
|---|---|
| `cubature(reseau="EU", reglages=None)` | Déblais, lit de pose, remblai : détail par ouvrage et totaux. |
| `coupe_type(reseau="EU", dossier=None, reglages=None)` | Coupe type de tranchée en PDF, plus les statistiques du réseau. |

`reglages` surcharge la configuration du plugin (épaisseur du lit de pose,
largeurs de tranchée) sans la modifier durablement.

### 3.9 Sorties

| Fonction | Rôle |
|---|---|
| `profil(reseau="EU", format="A3", dossier=None)` | Profil en long en PDF. |
| `profil_groupe(reference="EU", format="A3", dossier=None)` | Profil combiné EU + EP. |
| `reglages_plan(echelle=200, format="A4", orientation="portrait", dpi=300, cadrage="auto", titre=None, plan_ensemble=True)` | Dictionnaire de réglages pour `PrintTool`. |
| `exporter(dossier=None, pdf_complet=True, fonds_wms=True, **reglages)` | Export synchrone. |
| `exporter_async(...)` | Lance l'export et rend un ticket. |
| `tache(ticket)` | État d'une tâche asynchrone. |
| `exporter_dxf(dossier=None, emprise=None)` | DXF 2018 de l'emprise visible. |
| `controle_stareau()` | Conformité CNIG/ASTEE avant export. |
| `exporter_stareau(parametres, chemin)` | GeoPackage StaR-Eau. |

Formats : `A4`, `A3`, `A2`, `A1`, `A0`. `cadrage="auto"` calcule les planches et
exporte sans pose manuelle ; les marges sont déduites de la largeur réelle des
étiquettes affichées.

`reglages_plan` écrit le dictionnaire à la main plutôt que de le lire dans
`ExportDialog` : instancier la fenêtre pour ses accesseurs laisse un widget
vivant derrière soi.

**`fonds_wms` vaut `True` par défaut, et c'est le bon défaut : les plans portent
l'ortho.** L'orthophoto est ce qui permet de vérifier l'implantation sur le
terrain ; un plan livré sans elle n'est pas le même document.

`fonds_wms=False` n'est donc **pas une optimisation** mais un compromis, réservé
au tirage de contrôle interne. Ce qu'il coûte et ce qu'il rapporte, mesuré sur
une page A4 à 300 dpi : réseau seul 0,94 s, avec cadastre 1,77 s, avec ortho et
OSM 4,89 s — soit 3,13 s par page pour les fonds WMS. Sur un chantier de
13 pages, l'export passe de 43,7 s à 6,4 s, mais les planches perdent leur fond :
il ne reste que le réseau et le cadastre. À n'utiliser que si personne n'a
besoin de voir le terrain.

**Asynchrone.** `exporter_async` rend la main en 0,000 s et laisse l'export
tourner. Cela fonctionne parce que le rendu des planches passe par des jobs QGIS
parallèles dont la boucle d'attente appelle `processEvents` : les appels
d'interrogation sont donc servis **pendant** l'export.

> **⚠ Sonder depuis des appels séparés.** L'export s'exécute sur le fil
> principal de QGIS. Une boucle d'attente écrite dans le même script —
> `while ...: time.sleep(2)` — garde ce fil et empêche la tâche d'avancer :
> l'état reste « en cours » aussi longtemps que dure la boucle, puis l'export
> repart dès que le script rend la main. Un pilote distant (MCP, agent) doit
> donc appeler `tache()` **une fois par aller-retour**, jamais dans une boucle
> bloquante. Le retour d'`exporter_async` le rappelle dans sa clé `sondage`.

```python
t = api.exporter_async(echelle=200, format="A4", orientation="portrait",
                       fonds_wms=False)
api.tache(t["ticket"])
# {'etat': 'en cours', 'secondes': 5.1, ...}
# {'etat': 'fini', 'resultat': {'fichiers': [...], 'secondes': 6.4}, ...}
```

`etat` vaut `en cours`, `fini`, `erreur` ou `inconnu`.

`exporter_dxf` et `importer_dxf` nécessitent ezdxf ; le PDF complet nécessite
pypdf. Vérifier avec `dependances_manquantes()` — l'API lève une erreur claire
plutôt que d'ouvrir la fenêtre d'installation.

### 3.10 Imports

| Fonction | Rôle |
|---|---|
| `importer_dxf(fichier, sortie=None, **options)` | DXF/DWG → GeoPackage. |
| `importer_star_dt(fichiers, dossier_sortie, types=None)` | Fichiers d'échange Star-DT → couches SIG. |

Les étiquettes ne sont récupérées que depuis un **DXF 2018** ; en 2013 elles
sont perdues.

### 3.11 Enchaînement

`chantier(adresse, dossier=None, nom=None, rue=None, commune=None,
reseau="EU", entraxe_max=50.0, tol_axe=0.5, distance_max=10.0, cotes=None,
export=None)` enchaîne la séquence complète et rend le compte rendu de chaque
étape. L'export part en asynchrone ; le ticket est dans
`resultat["export"]["ticket"]`.

> `chantier()` est un enchaînement **figé** : séquence en dur, ni diamètre, ni
> étiquettes, ni attente des fonds. Pour une procédure qu'on adapte sans
> toucher au code, voir les recettes en 3.12 — `collecteur_de_rue` fait la même
> chose, en douze étapes déclarées.

---

### 3.12 Suites et recettes

| Fonction | Rôle |
|---|---|
| `suite(etapes, parametres=None, arret_si_erreur=True)` | Exécute une liste d'appels en un seul échange. |
| `recettes(nom=None)` | Les procédures enregistrées ; avec `nom`, la fiche complète. |
| `recette(nom, arret_si_erreur=True, **parametres)` | Joue une procédure enregistrée. |
| `enregistrer_recette(nom, etapes, resume=None, parametres=None)` | Écrit une recette dans le profil. |

**Pourquoi.** Ce qui coûte, dans un pilotage distant, ce n'est pas le calcul —
les verbes de ce module rendent la main en moins d'une seconde — c'est
l'aller-retour : envoyer un appel, attendre, réfléchir, en envoyer un autre. Sur
une séance mesurée, 87 % du temps était de la latence d'échange et 13 % du
travail réel. Le même chantier, piloté pas à pas, a demandé 9 minutes ; joué
comme recette, **22,7 s en un seul échange**.

```python
api.suite([
    {"appel": "renumeroter", "args": {"reseau": "EU", "depart": 1}},
    {"appel": "caler_cotes", "args": {"reseau": "EU", "tn": 100, "pente": 1.0,
                                      "ancrage": ["REU07", 2.50]}},
    {"appel": "controler_branchements", "args": {"reseau": "EU"}},
])
```

**Une étape** est un dict : `appel` (un verbe public, cf. `aide()`), `args`,
et trois options — `nomme` pour désigner son résultat, `si` pour la sauter
quand la valeur est fausse, `ignorer_erreur` pour continuer malgré un échec.
Seuls les verbes listés par `aide()` sont appelables : un fichier de recette
n'ouvre aucun accès arbitraire au module.

**Deux substitutions** suffisent à tout enchaîner :

| Écriture | Sens |
|---|---|
| `"$param"` | la valeur passée à l'appel, ou le défaut de la recette |
| `"@etape.chemin"` | le résultat d'une étape précédente — `"@num.regards[-1]"` |

La seconde règle un problème que rien d'autre ne règle : l'axe de rue est un
`QgsGeometry`, qui ne franchit aucun protocole. Dans une suite il ne sort jamais
de QGIS — l'étape qui le fabrique le nomme, l'étape suivante le reprend par son
nom, et le compte rendu n'en garde qu'une description.

**Le retour** donne, pour chaque étape : le rang, l'appel, les arguments
résolus, la durée, l'état (`ok`, `sautee`, `erreur`) et le résultat. C'est le
journal de la séance, produit par l'outil.

#### Recettes livrées

| Nom | Ce qu'elle fait |
|---|---|
| `collecteur_de_rue` | Projet à une adresse, collecteur sur l'axe OSM, branchements, numérotation, cotes, étiquettes, enregistrement, plan PDF. 12 étapes. |
| `recaler_cotes` | Renumérote et repose TN, profondeurs et fils d'eau sur un réseau déjà tracé, puis contrôle. 4 étapes. |
| `livraison` | Styles, étiquettes, vérification, enregistrement, export PDF complet. 5 étapes. |

```python
api.recette("collecteur_de_rue",
            adresse="Rue Julien Charpentier, 03250 Châtel-Montagne",
            rue="Rue Julien Charpentier", commune="Châtel-Montagne",
            tn=100, pente=1.0, profondeur_aval=2.50, profondeur_tabouret=0.50)
```

**Ce qu'une recette ne fixe pas.** Les cotes de chantier — `tn`, `pente`,
`profondeur_aval`, `profondeur_tabouret` — n'ont **pas** de valeur par défaut :
elles changent à chaque affaire, et une valeur par défaut y serait un piège
silencieux. Un paramètre à `null` est obligatoire ; l'appel qui l'omet est
refusé avant la première étape, avec la liste des manquants. Restent en défaut
les choix de procédure : entraxe, tolérance d'axe, diamètres, format du plan.

**Où elles vivent.** Les recettes livrées sont dans `tools/recettes/` du plugin ;
celles écrites par `enregistrer_recette()` vont dans `CanaPlan/recettes/` du
profil QGIS et **masquent** une livrée de même nom. Une séquence éprouvée en
direct devient donc une procédure rejouable sans toucher au code.

---

## 4. Ce que l'API ne fait pas

Certains outils sont indissociables du pointeur : leur logique **est** le
survol. L'API ne les simule pas.

| Outil | Pourquoi | Équivalent API |
|---|---|---|
| Déplacer (`MoveTool`) | Survol, aperçu des lignes attachées, dépose | modifier la géométrie directement |
| Supprimer (`DeleteTool`) | Survol, lasso, effacement d'étiquettes | `supprimer()`, sans le lasso |
| Copier les attributs | Désignation source puis cible | `saisir()` avec un filtre `ou=` |
| Renseigner (`RenseignementTool`) | Formulaire par ouvrage désigné | `saisir()` |
| Annotation | Placement libre à l'écran | — |
| Coupe transversale | Trait de coupe tracé à la main | — |
| Cubature par axe ou par chemin | Suppose de désigner des ouvrages | `cubature()`, réseau entier |

---

## 5. Modifications apportées au plugin

L'API s'appuie sur trois ajouts **rétrocompatibles** : sans les nouveaux
arguments, le comportement manuel est identique.

| Fichier | Ajout |
|---|---|
| `tools/draw_conduite_tool.py` | `DrawConduiteTool(..., tol_m=None)` et `_tol(px)`. |
| `tools/draw_branchement_tool.py` | `DrawBranchementTool(..., tol_m=None)` et `_tol(px)` sur les 5 tolérances de snap. La croix de snap reste en pixels : c'est un rendu visuel. |
| `tools/projet_bet.py` | `_do_save(..., silencieux=False)` et la classe `_ProgressMuette`. En mode silencieux, `_do_save` **retourne** la liste des erreurs. |

---

## 6. Notes de performance

Mesuré dans QGIS 3.44 sous Windows, sur un chantier de 7 regards, 6 tronçons et
22 branchements.

| Poste | Coût | Remarque |
|---|--:|---|
| `QSettings()` construction | 0,520 ms | 94 % du coût de `i18n.tr()` |
| `i18n.tr()` | 0,555 ms | relit le registre à chaque chaîne traduite |
| `QgsProject.writeEntry` | 0,036 ms | — |
| `QSettings().setValue` | 41,7 ms | **1160× plus cher** que `writeEntry` |
| `layer_keys.set_layer_id` | 43,9 ms | dominé par l'écriture QSettings de compatibilité |
| Rendu d'une page A4 300 dpi, réseau seul | 0,94 s | — |
| … avec cadastre et BAN | 1,77 s | — |
| … avec ortho et OSM (WMS) | 4,89 s | **le poste dominant** |
| Export PDF complet, 13 pages, avec WMS | 43,7 s | 122 s à cache froid |
| Export PDF complet, sans WMS | **6,4 s** | PDF identique en structure |

Deux optimisations restent disponibles dans le plugin lui-même, non appliquées
faute d'arbitrage : mémoriser la langue résolue dans `i18n` (gain ~500× sur
`tr()`), et ne réécrire la clé QSettings de `set_layer_id` que si la valeur a
changé (gain ~334 ms par enregistrement, au prix de la compatibilité descendante
revendiquée par la docstring).
