# API CanaPlan — référence de pilotage

LECTEUR VISÉ : agent. Document optimisé pour la décision, pas pour la lecture
suivie. Ordre imposé : §0 procédure → §1 règles → §2 recettes. Les §3 et
suivants sont consultés à la demande, jamais lus en entier.

MODULE : `CanaPlan.tools.api`. 51 verbes publics, 8 recettes. Pilote le plugin
sans ouvrir aucune fenêtre. Aucune logique métier propre : tout est délégué aux
outils du plugin, donc le résultat est identique au geste manuel (snapping,
topologie, valeurs par défaut comprises).

```python
from CanaPlan.tools import api
```

---

## §0. PROCÉDURE

```
1. api.aide()                      -> sommaire des verbes
2. api.recettes()                  -> une recette couvre-t-elle la demande ?
3. api.recettes("<nom>")           -> fiche : requis, optionnels, étapes
4. api.recette("<nom>", **params)  -> jouer, en UN seul échange
```

SI aucune recette ne couvre → composer avec `api.suite([...])` (même grammaire,
sans fichier) → si la séquence est bonne, la figer par
`api.enregistrer_recette()`.

`execute_code` enchaînant des verbes à la main est le DERNIER recours. Il perd
simultanément : les paramètres obligatoires (§1 R1), les assertions (§1 R5) et
le journal d'étapes. Les six pièges du §5 viennent tous de là.

DÉCISION D'ENTRÉE :

| Demande | Recette | Motif |
|---|---|---|
| Réseau sur une rue, sans cote imposée | `reseau_de_voie` | `coter=false` par défaut |
| Chantier complet coté + PDF | `collecteur_de_rue` | exige pente + 2 profondeurs |
| Réseau déjà tracé, à coter | `coter_mnt` | — |
| Réseau déjà tracé, à réorienter et recoter | `recaler_cotes` | exige `voie_de_raccordement` |
| Livrer (étiquettes, contrôle, PDF) | `livraison` | — |

RÈGLE DE CHOIX : prendre la recette dont les `requis` sont TOUS fournis par la
demande. Ne jamais choisir une recette plus exigeante puis inventer ses
paramètres manquants (§1 R1).

---

## §1. RÈGLES DURES

**R1 — Ne jamais inventer un engagement de chantier.**
`pente`, `profondeur_aval`, `profondeur_tabouret`, `tn` valent `null` dans les
recettes : ce sont des décisions de chantier, pas des réglages. Un appel qui les
omet est refusé avant la première étape, avec la liste des manquants.
Si la demande n'en parle pas : coter ce qui est demandé, laisser le reste non
coté, ET LE DIRE dans le compte rendu.

**R2 — Diamètres et matériaux se lisent dans `config()`.**
Les surcharger est un choix explicite, jamais un défaut recopié d'un exemple.
Défauts livrés : `conduite_eu` DN 200 PVC, `conduite_ep` DN 315 PVC,
`branchement_eu` / `branchement_ep` DN 160 PVC.

**R3 — L'orientation s'exprime par un paramètre, jamais par une correction.**
`voie_de_raccordement` désigne l'exutoire ; `extremites(pres_de=…)` en déduit
l'aval ; `renumeroter` et `caler_cotes` s'orientent dessus. Ne jamais inverser
une géométrie d'axe pour retourner un réseau.

**R4 — Les fonds WFS sont asynchrones.**
`fonds()` rend la main avant que les couches existent. Toujours
`attendre_fonds(["PCI - Bati"])` avant tout appel qui les lit.

**R5 — Un `attendu` sur chaque étape qui peut échouer en silence.**
Cibles usuelles : `echecs` vide, `conduites_en_contre_pente` vide, `erreurs`
vide, `regards` min 2.

**R6 — Convention de signe de la pente : positive = descendante.**
`FE aval = FE amont − pente% × L`. Une chute de 1 cm/m se saisit `1.0`, PAS
`-1.0`. Une valeur négative crée une contre-pente.

**R7 — Ne jamais sonder une tâche async dans une boucle bloquante.**
L'export tourne sur le fil principal. `while ...: time.sleep()` dans le même
script gèle la tâche. Appeler `tache(ticket)` une fois par aller-retour.

**R8 — Vérifier la cohérence, pas un champ isolé.**
Contrôle minimal après cotation des tabourets :
`tn` plausible (400 < tn < 700) ET `profondeur` attendue ET
`fe_entree == tn − profondeur`. Contrôler la seule `profondeur` laisse passer
un `tn` retombé à 0 (§5 P2).

**R9 — `fermer()` en fin de séance scriptée.**
Instancier un dialogue pour lire ses accesseurs laisse un widget vivant.

---

## §2. RECETTES

### 2.1 Catalogue

| Nom | Étapes | Requis | Effet |
|---|--:|---|---|
| `projet_sur_voie` | 5 | `rue`, `commune` | BLOC. Résout la voie, crée le projet, charge et ATTEND les fonds, rend l'axe OSM. |
| `tracer_reseau` | 5 | `axe` | BLOC. Conduite + regards, branchements, TN au MNT, orientation, numérotation. NE COTE RIEN. |
| `coter_mnt` | 6 | `pente`, `profondeur_aval`, `profondeur_tabouret` | TN mesuré, ancrage aval, cotes, pentes, contrôles. |
| `habiller` | 2 | — | BLOC. Symbologie + étiquettes forcées, taille en mm papier. |
| `reseau_de_voie` | 7 | `rue`, `commune` | Chantier sur la voie. `coter=false` par défaut. |
| `collecteur_de_rue` | 7 | `adresse`, `rue`, `commune`, `pente`, `profondeur_aval`, `profondeur_tabouret` | Chantier complet jusqu'au PDF. `coter` et `avec_export` vrais. |
| `recaler_cotes` | 7 | `voie_de_raccordement`, `tn`, `pente`, `profondeur_aval`, `profondeur_tabouret` | Renumérote et repose les cotes sur un réseau existant. |
| `livraison` | 5 | — | Étiquettes, vérification, enregistrement, export PDF async. |

`requis_si_active` : dans `reseau_de_voie`, `pente` / `profondeur_aval` /
`profondeur_tabouret` ne deviennent obligatoires que si `coter=true`.

### 2.2 Enchaînements internes à connaître

`projet_sur_voie` : `voie` → `nouveau_projet` (alternative `si`/`si_non` sur
`adresse`) → `attendre_fonds` (avec `attendu`) → `axe_de_rue`.
Sorties : `v`, `axe`.

`tracer_reseau` : `tracer_conduite` (attendu ≥2 regards, ≥1 tronçon) →
`creer_branchements` (attendu `echecs` vide) → `tn_mnt` (si `tn_auto`) →
`extremites` (nommée `ext`) → `renumeroter(de=@ext.amont_fid,
vers=@ext.aval_fid)`. Sorties : `ext`, `num`.
ORDRE CRITIQUE : `tn_mnt` AVANT `extremites`, sinon le terrain ne peut pas
trancher le sens d'écoulement. Identifiants (`amont_fid`) et non noms : au
sortir de `tracer_conduite` les regards ne sont pas encore nommés.

`coter_mnt` : `tn_mnt` → `extremites` → `caler_cotes(ancrage=[@ext.aval,
$profondeur_aval], tabourets={profondeur: $profondeur_tabouret})` →
`recalculer_pentes` → `controler_branchements` → `verifier`.
`ecraser_tn=False` préserve un TN de géomètre.

### 2.3 Grammaire

Recette = JSON à 5 clés : `nom`, `resume`, `parametres` (`null` = à fournir),
`sorties`, `etapes`.

Étape = dict :

| Clé | Sens |
|---|---|
| `appel` | un verbe public, et lui seul |
| `args` | arguments |
| `nomme` | nom pour référence `@nom` |
| `si` / `si_non` | saut conditionnel ; les paramètres d'une étape sautée ne sont plus exigés |
| `attendu` | assertion, sinon échec daté et situé |
| `ignorer_erreur` | poursuivre malgré l'échec |

Substitutions : `"$param"` = valeur passée ou défaut ; `"@etape.chemin"` =
morceau du résultat d'une étape nommée (`@ext.aval_fid`, `@num.regards[-1]`,
`@p.valeurs.axe`).

RAISON D'ÊTRE DE `@` : l'axe de rue est un `QgsGeometry`, qui ne franchit aucun
protocole. Dans une suite il ne sort jamais de QGIS. `sorties` sert à le rendre
disponible à une recette appelante.

Prédicats d'`attendu` : `egal`, `vide`, `non_vide`, `min`, `max`, `contient`,
`taille`.

Composition : une étape peut appeler `recette`. Résultat repris par
`@nom.valeurs.<sortie>`.

### 2.4 Outils

| Fonction | Rôle |
|---|---|
| `recettes(nom=None)` | Sommaire, ou fiche complète. |
| `recette(nom, arret_si_erreur=True, reprendre_a=1, **parametres)` | Joue. |
| `suite(etapes, parametres=None, arret_si_erreur=True, sorties=None, reprendre_a=1)` | Joue une liste ad hoc. |
| `valider_recette(nom=None)` | Contrôle verbes, `$param`, `@etape`. |
| `enregistrer_recette(nom, etapes, resume=None, parametres=None)` | Fige dans le profil. |

`reprendre_a=N` reprend au rang N. ATTENTION : les valeurs nommées par les
étapes sautées n'existent pas ; toute référence `@` vers elles échoue.

Emplacements : livrées dans `tools/recettes/` du plugin ; écrites dans
`CanaPlan/recettes/` du profil, qui MASQUE une livrée de même nom.

Trois règles pour écrire une recette : (1) tout engagement de chantier vaut
`None` dans `parametres` ; (2) un `attendu` sur chaque étape faillible ;
(3) `valider_recette()` avant usage.

---

## §3. VERBES

### 3.1 Lecture et séance

| Fonction | Rôle |
|---|---|
| `etat()` | Inventaire : couches par réseau, fonds, projet courant, fenêtres. |
| `lire(reseau, role, champs=None)` | Entités d'un rôle, liste de dicts avec `__id`. |
| `verifier(reseau="EU")` | Champs vides par rôle, contre-pentes, contrôle des branchements. |
| `aide(domaine=None)` | Signature et résumé de chaque fonction. |
| `fermer(detruire=True)` | Ferme les fenêtres CanaPlan, désactive l'outil carte. |
| `dependances_manquantes()` | Bibliothèques absentes : `dxf` (ezdxf), `pdf` (pypdf). |

`etat()` rend sous `projet` le .bet courant, sous `qgs` le fichier QGIS (presque
toujours vide : un projet CanaPlan est une archive .bet, pas un .qgs).

`fermer()` poste `DeferredDelete` explicitement puis attend la destruction
(1 s max) : `restantes` est donc fiable. `QApplication.processEvents()` seul ne
traite PAS les suppressions différées.

### 3.2 Données externes

| Fonction | Rôle |
|---|---|
| `adresse(recherche)` | Géocodage BAN : label, score, INSEE, lon/lat, x/y L93. |
| `voie(recherche, commune=None, insee=None, seuil=0.55)` | Nom de voie officiel : `nom`, `label`, `insee`, `score_ban`, `similitude`, `confiance`, `verdict` (sure/probable/douteuse). Lève sous `seuil`. |
| `axe_de_rue(nom_voie, commune=None, insee=None, rafraichir=False, rayon=1500.0, detail=False)` | Axe de chaussée OSM en L93 (`QgsGeometry` ligne). |

L'axe OSM EST l'axe de la voie : une conduite posée dessus est centrée par
construction. Coût 2 à 4 s, MIS EN CACHE pour la session sur la clé
(voie, commune, insee) — le rappeler est gratuit. `rafraichir=True` force.
Overpass refuse les requêtes sans `User-Agent` (HTTP 406) ; l'API en fournit un.

### 3.3 Projet

| Fonction | Rôle |
|---|---|
| `nouveau_projet(adresse=None, dossier=None, nom=None, fonds=None, demi_emprise=200.0)` | Crée un `.bet`. |
| `charger(chemin)` | Charge un `.bet`, sans modale. |
| `enregistrer(chemin=None)` | Enregistre, sans barre de progression. Erreurs dans `erreurs`. |
| `enregistrer_sous(chemin)` | — |
| `projets_recents()` | Derniers `.bet`, projet courant, dossier. |

`nouveau_projet` charge PAR DÉFAUT tous les fonds, dont le bâti cadastral que
l'assistant laisse décoché alors qu'il est indispensable aux branchements.

`enregistrer` passe par `_do_save(silencieux=True)` : pas de `QProgressDialog`,
donc pas de `processEvents`. Ce n'est pas un confort — chaque `processEvents`
sert aussi les rendus WMS en attente, ce qui peut faire durer des minutes une
sauvegarde de quelques secondes.

### 3.4 Fonds de plan

| Fonction | Rôle |
|---|---|
| `fonds(*demandes, **bascules)` | Charge des fonds. Sans argument, charge tout. |
| `attendre_fonds(noms=("PCI - Bati",), delai=90.0, pas=0.5)` | Bloque jusqu'à apparition. |

Clés : `osm`, `ortho`, `ban`, `noms_voie`, `pci_bati`, `pci_parcelles`.
Voir R4 : les quatre fonds vectoriels passent par un WFS asynchrone (`QgsTask`).

### 3.5 Dessin

| Fonction | Rôle |
|---|---|
| `implanter_regards(axe, entraxe_max=50.0, tol_axe=0.5)` | Abscisses des regards, sans dessiner. |
| `tracer_conduite(reseau, axe=None, points=None, entraxe_max=50.0, tol_axe=0.5, vider=False, diametre=None, materiau=None)` | Conduite + regards. |
| `creer_branchements(reseau, distance_max=10.0, couche_bati="PCI - Bati", vider=False, diametre=None, materiau=None)` | Un branchement par bâtiment proche. |
| `inserer_regard(point, reseau=None)` | Insère un regard et coupe la conduite. |
| `supprimer(reseau, role, ids)` | Suppression brute par identifiant. |
| `vider(reseau, roles=…)` | Vide les couches métier. |

`implanter_regards`, deux règles dans cet ordre : (1) un regard à chaque coude
dont l'omission écarterait la conduite de plus de `tol_axe` mètres de l'axe réel
— sans cela la corde coupe les virages, mesuré jusqu'à 3,2 m sur une rue de
159 m ; (2) subdivision en parts égales de tout intervalle > `entraxe_max`.
`entraxe_max` est un MAXIMUM, pas un pas fixe.

`diametre` / `materiau` valent pour les SEULS ouvrages créés par l'appel : posés
dans les défauts le temps du tracé, rendus ensuite, y compris sur exception.

`creer_branchements` part du piquage le plus proche sur la conduite et rejoint
le point du bâti le plus proche, où un tabouret est posé. Échecs listés dans
`echecs`, pas levés. `couche_bati` n'est qu'un nom de couche : toute couche de
points ou polygones du projet convient (ex. points d'adresse BAN).

`supprimer` est brute volontairement. Contrôler après coup par
`recalculer_pentes()` puis `verifier()`.

### 3.6 Attributs et cotes

| Fonction | Rôle |
|---|---|
| `saisir(reseau, role, valeurs, ou=None)` | Écrit des attributs en masse. |
| `extremites(reseau, pres_de=None)` | Rend `amont`, `aval`, `amont_fid`, `aval_fid`, `nommes`, `repere`. `pres_de` = nom de voie, `[x, y]` L93 ou `QgsGeometry`. |
| `tn_mnt(reseau, roles=('regard','tabouret'), ecraser=True)` | TN depuis le MNT IGN : LiDAR HD si la dalle existe, RGE ALTI sinon. Source rendue ouvrage par ouvrage. |
| `renumeroter(reseau, prefixe_regard=None, prefixe_tabouret=None, depart=1, de=None, vers=None)` | Amont → aval. |
| `caler_cotes(reseau, tn=None, ancrage=None, pente=None, tabourets=None)` | TN, profondeurs, fils d'eau. |
| `recalculer_pentes(reseau="EU", tolerance=0.05)` | Pentes depuis les fils d'eau. |
| `controler_branchements(reseau, pente_max=30.0)` | Pente de chaque branchement + non cotés. |

`saisir` ne recalcule PAS les champs dérivés : enchaîner `caler_cotes()` ou
`recalculer_pentes()`.

`renumeroter` : préfixes par défaut `REU` / `EU-BRCHT` (EU), `REP` / `EP-BRCHT`
(EP), format `%02d`. Sans `de`/`vers`, les deux extrémités sont prises, le nord
comme amont.

`caler_cotes` — LES QUATRE PARAMÈTRES SONT OPTIONNELS. Comportement selon ce
qui est fourni :

| Fourni | Effet |
|---|---|
| `tabourets={"profondeur": p}` seul | Écrit `profondeur=p` et `fe_entree = tn − p` sur tous les tabourets. Le collecteur n'est PAS calé. Sort avant tout calcul de fil d'eau. |
| `tn=v` | Applique `v` à tous les regards. |
| `ancrage=(nom, prof)` + `pente` | Cale la chaîne. Si l'ancrage est le point bas (exutoire), le calcul REMONTE ; sinon il descend. |
| ni `ancrage` ni `pente` | Cote les branchements et sort. |

Source du TN des tabourets, par ordre de priorité : `tabourets["tn"]`, puis
`tn`, puis le TN déjà présent sur l'ouvrage, PUIS `0.0` — voir §5 P2.

`caler_cotes` cote AUSSI les branchements (cote de piquage et pente propagées).
Pas besoin d'enchaîner `recalculer_pentes()` derrière ; celui-ci reste utile
après une écriture directe par `saisir()`.

Retour : `regards`, `pentes` des tronçons, `tabourets` (une entrée nommée par
tabouret), `nb_tabourets`.

`controler_branchements` signale contre-pentes et, au-delà de `pente_max`, les
chutes. Une série de pentes excessives signale presque toujours des tabourets
tous calés à la même profondeur au-dessus d'un collecteur qui s'enfonce.
Un branchement dont une cote manque sort dans `non_cotes` avec les champs
absents, plus un `conseil`.

### 3.7 Présentation

| Fonction | Rôle |
|---|---|
| `styles(reseau="EU")` | Symbologie (EU rouge, EP bleu). |
| `etiquettes(reseau="EU", roles=None, taille=None, unite=None, champs=None, visibilite=None, forcer_toutes=None, echelle_min=None, echelle=None)` | Moteur d'étiquettes. |
| `config(defauts=None, cubature=None)` | Lit ou modifie les défauts. |

| `unite` | Sens | Exige |
|---|---|---|
| `'mm'` | millimètres SUR LE PAPIER, à l'échelle du plan | `echelle` |
| `'map'` | unités carte (mètres au sol) | — |
| `'points'` | points typographiques, taille fixe à l'écran | — |

Conversion : `taille_carte = taille_mm / 1000 × echelle`.
Donc 2,5 mm papier = 0,50 m au sol au 1/200. Sans conversion, une taille de `2`
lue en unités carte donne 2 m de haut, soit 10 mm de texte sur la feuille.

`echelle` (dénominateur du plan) ≠ `echelle_min` (seuil de dézoom). Retour :
`taille_carte_m` et `taille_mm_papier`. La taille s'applique à TOUT le projet.

`visibilite` : booléen, `{role: bool}`, ou `{reseau: {role: bool}}`.
Retour = état obtenu, pas arguments reçus. Rôle inconnu → lève.

### 3.8 Calculs

| Fonction | Rôle |
|---|---|
| `cubature(reseau="EU", reglages=None)` | Déblais, lit de pose, remblai : détail + totaux. |
| `coupe_type(reseau="EU", dossier=None, reglages=None)` | Coupe type de tranchée (PDF) + statistiques. |

`reglages` surcharge sans modifier durablement.

### 3.9 Sorties

| Fonction | Rôle |
|---|---|
| `profil(reseau="EU", format="A3", dossier=None)` | Profil en long PDF. |
| `profil_groupe(reference="EU", format="A3", dossier=None)` | Profil EU + EP. |
| `reglages_plan(echelle=200, format="A4", orientation="portrait", dpi=150, cadrage="auto", titre=None, plan_ensemble=True)` | Réglages pour `PrintTool`. |
| `exporter(dossier=None, pdf_complet=True, fonds_wms=True, **reglages)` | Export synchrone. |
| `exporter_async(...)` | Rend un ticket, main rendue en 0,000 s. |
| `tache(ticket)` | État : `en cours`, `fini`, `erreur`, `inconnu`. |
| `exporter_dxf(dossier=None, emprise=None)` | DXF 2018 de l'emprise visible. |
| `controle_stareau()` | Conformité CNIG/ASTEE. |
| `exporter_stareau(parametres, chemin)` | GeoPackage StaR-Eau. |

Formats : A4, A3, A2, A1, A0. `cadrage="auto"` calcule les planches ; marges
déduites de la largeur réelle des étiquettes affichées.

`fonds_wms=True` est le BON défaut : l'ortho est ce qui permet de vérifier
l'implantation sur le terrain. `fonds_wms=False` n'est PAS une optimisation mais
un compromis réservé au tirage de contrôle interne (chiffres en §7).

Voir R7 pour le sondage des tâches async. `exporter_async` rappelle la règle
dans sa clé `sondage`.

### 3.10 Imports

| Fonction | Rôle |
|---|---|
| `importer_dxf(fichier, sortie=None, **options)` | DXF/DWG → GeoPackage. |
| `importer_star_dt(fichiers, dossier_sortie, types=None)` | Star-DT → couches SIG. |

Étiquettes récupérées depuis un DXF 2018 seulement ; perdues en 2013.

### 3.11 Hérité

`chantier(...)` enchaîne la séquence complète. NE PAS L'UTILISER : séquence en
dur, sans diamètre, étiquettes, attente des fonds, `voie_de_raccordement` ni
`attendu`. `collecteur_de_rue` fait la même chose en sept étapes contrôlées.
Conservé pour ne pas casser les scripts existants.

---

## §4. HORS PÉRIMÈTRE

Outils indissociables du pointeur : leur logique EST le survol.

| Outil | Équivalent API |
|---|---|
| Déplacer (`MoveTool`) | modifier la géométrie directement |
| Supprimer (`DeleteTool`) | `supprimer()`, sans le lasso |
| Copier les attributs | `saisir()` avec filtre `ou=` |
| Renseigner (`RenseignementTool`) | `saisir()` |
| Annotation | — |
| Coupe transversale | — |
| Cubature par axe ou par chemin | `cubature()`, réseau entier |

---

## §5. PIÈGES

Relevés en séance réelle. Chacun vient d'un agent ayant lu cette documentation
puis scripté à la main ce qu'une recette faisait déjà.

**P1 — Inventer une valeur que l'API refuse exprès de servir.**
Demande : « un branchement à chaque numéro, à 1 m de profondeur ». L'agent a
piloté par `execute_code`, donc hors recette, et a passé de lui-même `pente=1.0`
et `ancrage=("REU07", 2.00)` — deux décisions que personne n'avait demandées et
que la recette aurait refusées. Toute la suite de la séance a servi à réparer
cette pente inventée. → R1.

**P2 — Coter des tabourets sans TN, et ne contrôler que la profondeur.**
`creer_branchements(vider=True)` DÉTRUIT ET RECRÉE les tabourets, donc SANS TN.
Un `caler_cotes(tabourets={"profondeur": 1.0})` enchaîné directement retombe sur
la valeur de repli `tn = 0.0`, et écrit `fe_entree = −1.0` sur tous les
tabourets. Le contrôle « profondeurs distinctes = {1.0} » passe : l'anomalie est
invisible.
→ Après tout `vider=True`, rejouer `tn_mnt` AVANT `caler_cotes`.
→ Contrôler par R8, jamais un champ isolé.
→ La recette `tracer_reseau` impose déjà l'ordre `creer_branchements` → `tn_mnt`.
Reconstituer un état à la main plutôt que rejouer la recette est ce qui a rompu
cet ordre.

**P3 — Redresser à la main ce que `voie_de_raccordement` fait seul.**
Un agent a constaté 6 tronçons sur 6 en contre-pente, puis a inversé la
géométrie de l'axe OSM, retracé, recréé 17 branchements et renuméroté — deux
passes complètes. Une chaîne de caractères aurait suffi. → R3.

**P4 — Coder en dur ce que `config()` sert.**
`diametre=250, materiau="Fonte"` passés sur le collecteur quand `config()`
disait DN 200 PVC, sans rien dans la demande qui le justifie. → R2.

**P5 — Perdre les assertions.**
Sans recette, plus d'`attendu`. L'anomalie des 6 contre-pentes n'a pas été
signalée : elle était au milieu d'un JSON de 6 000 caractères. → R5.

**P6 — `reload_plugin` vide le projet.**
Recharger CanaPlan depuis le serveur MCP recrée des couches mémoire vides ;
`etat()` rend alors `source: "memory"` et `entites: 0`, tout en affichant
encore le chemin du `.bet`. Les données sur disque sont intactes.
→ Après un `reload_plugin`, faire `charger(<.bet>)` PUIS `fonds()` +
`attendre_fonds()`. Pour recharger du code sans perdre la session, préférer
`importlib.reload()` sur les modules de `CanaPlan.tools`.

**P7 — Le réflexe.**
```python
api.aide(); api.recettes(); api.recettes(nom)
```
Puis `suite()`, puis `enregistrer_recette()`. `execute_code` en dernier.

---

## §6. MODIFICATIONS APPORTÉES AU PLUGIN

Toutes rétrocompatibles : sans les nouveaux arguments, le comportement manuel
est identique.

| Fichier | Ajout |
|---|---|
| `tools/draw_conduite_tool.py` | `DrawConduiteTool(..., tol_m=None, differer_ecriture=False)` et `_tol(px)`. |
| `tools/draw_branchement_tool.py` | `DrawBranchementTool(..., tol_m=None, differer_ecriture=False)`, `_tol(px)` sur les 5 tolérances de snap. La croix de snap reste en pixels : rendu visuel. |
| `tools/projet_bet.py` | `_do_save(..., silencieux=False)` et `_ProgressMuette`. En mode silencieux, `_do_save` RETOURNE la liste des erreurs. |
| `tools/api.py` | `_edition_groupee(*couches)` : tient une session d'édition ouverte sur plusieurs couches le temps d'une pose. |

### 6.1 `tol_m` — pourquoi les tolérances sont en mètres

Les tolérances de snap du plugin sont en PIXELS (`30 * mapUnitsPerPixel()`) :
juste sous la souris, où l'opérateur vise ce qu'il voit. Piloté par script, le
zoom devient un paramètre caché : à l'échelle de la rue, la tolérance des
regards vaut 8 m et fusionne des ouvrages distincts. L'API impose
`TOL_SNAP_M = 0.20` via `tol_m`.

CONSÉQUENCE : `_cadrer()` (cadrage du canevas) n'a plus AUCUN effet sur le
résultat en pilotage scripté. Il ne sert plus qu'au confort visuel et aux
captures.

### 6.2 `differer_ecriture` — pourquoi les écritures sont groupées

Les outils de dessin sont écrits pour la souris : chaque entité ouvre sa session
d'édition, l'écrit, la referme. C'est le bon geste pour un ouvrage isolé, qui
doit rester annulable et être écrit tout de suite. Répété en pose de masse, ce
couple domine tout le reste (chiffres en §7).

`differer_ecriture=True` supprime le commit unitaire ; l'appelant tient la
session via `_edition_groupee` et commit une fois par couche.

Propriétés de `_edition_groupee` :

- Les couches DÉJÀ en édition à l'entrée sont laissées telles quelles et ne sont
  pas commitées en sortie : la session appartient à quelqu'un d'autre.
- Le commit a lieu dans `__exit__`, donc aussi sur exception : ce qui a été posé
  avant l'échec est conservé, comme avec les commits unitaires.
- Un commit refusé est remonté (dans `echecs` pour `creer_branchements`, par une
  exception pour `tracer_conduite`), jamais avalé.

Ce que le groupement ne change PAS : `getFeatures()` et `featureCount()` sur une
couche en édition voient le tampon, entités non commitées comprises. Le contrôle
topologique de `_finish` et le compteur avant/après gardent leur comportement.

⚠ CONTRAINTE — `differer_ecriture` est INCOMPATIBLE avec `_undo_last` et
`_cancel` de `DrawConduiteTool`. `_create_regard` et `_create_troncon` renvoient
`feat.id()`, empilé dans `regard_ids` / `conduite_ids` pour l'annulation ; tant
que la session n'est pas commitée cet identifiant est provisoire (négatif) et ne
désignera plus la même entité après le commit. Ces deux méthodes ne sont
appelées que par les événements souris, jamais par l'API — d'où l'usage réservé
au tracé scripté.

---

## §7. PERFORMANCE

Mesuré dans QGIS 3.44 sous Windows, chantier de référence : 7 regards,
6 tronçons (159,08 m), 22 branchements, rue Julien Charpentier à
Châtel-Montagne.

### 7.1 Le poste dominant : les sessions d'édition

`startEditing` + `commitChanges` coûtent ~110 ms le couple sur GeoPackage. Une
session par entité et par couche les multiplie par le nombre d'ouvrages.

Profil de `creer_branchements` AVANT groupement (7,057 s) :

| Poste | Appels | Temps |
|---|--:|--:|
| `commitChanges` | 46 | 2,647 s |
| `startEditing` | 46 | 2,376 s |
| `getFeatures` | 137 | 0,701 s |
| `getFeature` | 44 | 0,538 s |
| `_cadrer` (dont plugin `craig` 0,200 s) | 22 | 0,248 s |
| `shortestLine` (géométrie réelle) | 22 | **0,004 s** |

71 % du temps était de l'ouverture/fermeture de session ; le calcul géométrique
en représentait 0,06 %.

APRÈS groupement (1,298 s profilé) : `commitChanges` 4 appels / 0,266 s,
`startEditing` 4 appels / 0,157 s, `getFeatures` 0,172 s.

### 7.2 Gains obtenus

| Verbe | Avant | Après | Gain |
|---|--:|--:|--:|
| `creer_branchements` (22 branchements) | 6,15 s | 1,46 s | −4,69 s |
| `tracer_conduite` (7 regards, 6 tronçons) | 1,84 s | 0,78 s | −1,06 s |
| **Chantier complet** | **23,61 s** | **≈ 17,9 s** | **−5,75 s** |

Le total est arithmétique, non mesuré de bout en bout.

### 7.3 Le plancher : les services externes

| Poste | Temps | Nature |
|---|--:|---|
| `nouveau_projet` | 6,61 s | création des couches WMS/WFS |
| `axe_de_rue` | 2,90 s | Overpass (mis en cache session) |
| `tn_mnt` | 1,31 s | MNT IGN LiDAR HD |
| `attendre_fonds` | 1,01 s | WFS bâti |
| `voie` | 0,59 s | BAN |

≈ 12,4 s sur 23,6, soit 53 %, sont des allers-retours réseau. Aucune
optimisation de code ne les touche. Seuls leviers : `fonds=["PCI - Bati"]` (mais
le plan PDF perd ses fonds) et `demi_emprise` réduite.

### 7.4 Latence de pilotage

Une séance mesurée : 87 % du temps était de la latence d'échange, 13 % du
travail réel. Le même chantier piloté pas à pas a demandé 9 minutes ; joué comme
recette, 22,7 s en un seul échange.

COROLLAIRE : sur un chantier joué en recette, le transport MCP ne représente pas
un millième du temps (un seul aller-retour). Les optimisations de protocole
(sérialisation, compression, intervalle de polling) n'y gagnent RIEN. Elles ne
valent que pour un pilotage bavard — c'est-à-dire pour ce que §0 déconseille.

### 7.5 Rendu et export

| Poste | Coût | Remarque |
|---|--:|---|
| Page A4 300 dpi, réseau seul | 0,94 s | — |
| … avec cadastre et BAN | 1,77 s | — |
| … avec ortho et OSM (WMS) | 4,89 s | poste dominant |
| Export PDF complet, 13 pages, avec WMS | 43,7 s | 122 s à cache froid |
| Export PDF complet, sans WMS | 6,4 s | PDF identique en structure |

### 7.6 Coûts unitaires

| Poste | Coût | Remarque |
|---|--:|---|
| `QSettings()` construction | 0,520 ms | 94 % du coût de `i18n.tr()` |
| `i18n.tr()` | 0,555 ms | relit le registre à chaque chaîne |
| `QgsProject.writeEntry` | 0,036 ms | — |
| `QSettings().setValue` | 41,7 ms | 1160× plus cher que `writeEntry` |
| `layer_keys.set_layer_id` | 43,9 ms | dominé par l'écriture QSettings de compatibilité |

### 7.7 Optimisations disponibles, non appliquées

- Mémoriser la langue résolue dans `i18n` : gain ~500× sur `tr()`.
- Ne réécrire la clé QSettings de `set_layer_id` que si la valeur a changé :
  gain ~334 ms par enregistrement, au prix de la compatibilité descendante
  revendiquée par la docstring.
- `_cadrer()` dans la boucle de `creer_branchements` : 0,248 s, dont 0,200 s
  consommées par le plugin tiers `craig` qui écoute `map_extent_changed`. Sans
  effet sur le résultat (§6.1), conservé pour le suivi visuel.
