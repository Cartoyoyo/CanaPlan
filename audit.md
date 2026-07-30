# Audit technique — Plugin QGIS BET_HUMIDE

**Date :** 06/07/2026
**Périmètre :** code Python du plugin (hors `libs/` embarquées), packaging, distribution
**Volume analysé :** ~22 600 lignes de Python réparties sur ~50 fichiers, 81 Mo au total sur disque

---

## Synthèse

| Axe | Gravité | Effort | Gain attendu |
|-----|---------|--------|--------------|
| 1. Recherches spatiales en O(n×m) | 🔴 Haute | Moyen | ×50 à ×500 sur gros réseaux |
| 2. Écritures attributaires unitaires | 🟠 Moyenne | Faible | Commits rapides + undo groupé |
| 3. Réseau bloquant dans le thread UI | 🟠 Moyenne | Moyen | Fin des gels QGIS (jusqu'à 30 s × 6 requêtes) |
| 4. Poids du paquet et dépôt git | 🟡 Basse | Faible | −50 Mo distribués, −14 Mo de `.git` |
| 5. Qualité de code / duplications | 🟡 Basse | Faible | Maintenabilité |
| 6. Métadonnées et publication | 🟡 Basse | Trivial | Publication possible |

Points positifs relevés (à conserver) :

- **Imports paresseux systématiques** dans `main.py` : chaque `run_*` importe son outil localement → démarrage de QGIS non pénalisé par le plugin.
- **Séparation claire** `tools/` (logique) vs `gui/` (dialogues), dispatchers génériques `_run_tool_single` / `_run_tool_dual` bien factorisés.
- **Cycle de vie soigné** : `unload()` nettoie les rubber bands, utilise `sip.delete()` synchrone pour éviter les toolbars dupliquées au rechargement, `cleanup_plugin_resources()` purge le dossier temporaire.
- **Auto-création des couches** (`_get_couches` → `_create_layer` → `_ensure_fields`) : robuste, l'utilisateur ne peut pas se retrouver sans couche.
- `__pycache__` correctement exclu de git.

---

## 1. Performance — recherches spatiales en O(n×m) 🔴

### Constat

Mesures sur l'ensemble du code du plugin (hors `libs/`) :

| Motif | Occurrences |
|-------|-------------|
| `getFeatures()` **sans aucun filtre** | **78** |
| `QgsSpatialIndex` | **0** |
| `QgsFeatureRequest` (filtre rect/fid/expression) | **0** |

Toutes les recherches de proximité (« quel regard est sous le clic ? », « quelle conduite est la plus proche ? ») sont des **parcours linéaires complets** de la couche, souvent **imbriqués**.

### Cas concrets

**a) `tools/calc_pentes.py` — appelé à chaque toggle d'étiquettes**

`recalc_pentes()` est appelé par `main.py` dans `creer_etiquettes()` **et** `toggle_affichage_etiquettes()`, pour les deux réseaux EU et EP. Pour chaque conduite, le code parcourt le dictionnaire complet des regards :

```python
# calc_pentes.py:24-40 — pour CHAQUE conduite :
for feat in conduite_layer.getFeatures():
    ...
    for _rid, (rpt, fe) in r_pts.items():      # scan de TOUS les regards
        if pt0.distance(rpt) <= tol:
            fe0 = fe
        if pt1.distance(rpt) <= tol:
            fe1 = fe
```

Complexité : `O(conduites × regards)`. Avec un croquis de 30 conduites c'est invisible ; après un import Star-DT ou DXF de 2 000 nœuds, chaque clic sur le bouton étiquettes déclenche des millions de calculs de distance — **deux fois** (EU puis EP).

**b) `tools/move_tool.py` — double boucle dans un map tool interactif**

```python
# move_tool.py:703-716 — recalage des branchements après déplacement
for br_feat in branchement_layer.getFeatures():          # tous les branchements
    ...
    for c_feat in conduite_layer.getFeatures():           # × toutes les conduites
        sq_d, proj, _, _ = c_geom.closestSegmentWithContext(start_pt)
```

Même schéma aux lignes 656-678. Ce code s'exécute **pendant le drag/release de la souris** : c'est le pire endroit pour une complexité quadratique, la latence est directement perçue par l'utilisateur.

**c) Détection de l'entité sous le clic — répliquée dans chaque outil**

`move_tool.py:192-198`, et le même motif dans `delete_tool.py`, `renseignement_tool.py`, `copy_attributes_tool.py`, `insert_regard_tool.py`, `renommer_tool.py` :

```python
for feat in layer.getFeatures():                # toute la couche à chaque clic
    dist = click_pt.distance(QgsPointXY(geom.asPoint()))
    if dist <= tol and ...
```

**d) Répartition des 78 `getFeatures()` non filtrés**

| Fichier | Occurrences |
|---------|-------------|
| `tools/move_tool.py` | 12 |
| `tools/draw_branchement_tool.py` | 9 |
| `tools/cubature_tool.py` | 8 |
| `tools/delete_tool.py` | 6 |
| `tools/profil_batch.py` | 6 |
| `tools/calc_cubature.py` | 5 |
| `tools/calc_pentes.py` | 4 |
| `tools/profil_groupe_tool.py` | 4 |
| autres (13 fichiers) | 24 |

### Recommandations

1. **Créer un module `tools/spatial_cache.py`** exposant un index spatial par couche :

```python
from qgis.core import QgsSpatialIndex, QgsFeatureRequest

class LayerIndex:
    """Index spatial mis en cache, invalidé automatiquement sur édition."""
    def __init__(self, layer):
        self.layer = layer
        self._index = None
        for sig in (layer.featureAdded, layer.featureDeleted,
                    layer.geometryChanged):
            sig.connect(self._invalidate)

    def _invalidate(self, *args):
        self._index = None

    @property
    def index(self):
        if self._index is None:
            self._index = QgsSpatialIndex(self.layer.getFeatures())
        return self._index

    def nearest(self, pt, tol):
        """Entité la plus proche de pt dans le rayon tol, ou None."""
        for fid in self.index.nearestNeighbor(pt, 3, tol):
            feat = self.layer.getFeature(fid)
            ...
```

2. **Remplacer les scans par des requêtes filtrées** quand un index n'est pas justifié :

```python
rect = QgsRectangle(pt.x()-tol, pt.y()-tol, pt.x()+tol, pt.y()+tol)
request = QgsFeatureRequest().setFilterRect(rect)
for feat in layer.getFeatures(request):   # ne parcourt que la zone du clic
    ...
```

3. Dans `calc_pentes.py`, construire **un seul** `QgsSpatialIndex` des regards, puis pour chaque extrémité de conduite faire `index.nearestNeighbor(pt0, 1, tol)` : la complexité passe de `O(n×m)` à `O(n log m)`.

4. Bonus : `QgsFeatureRequest().setSubsetOfAttributes([...])` et `.setFlags(QgsFeatureRequest.NoGeometry)` quand seuls les attributs (ou seule la géométrie) sont nécessaires — évite la désérialisation inutile.

**Gain attendu :** réponse instantanée des map tools quel que soit le volume ; `recalc_pentes` passe de plusieurs secondes à quelques millisecondes sur un réseau importé.

---

## 2. Écritures attributaires unitaires, pas de commandes d'annulation 🟠

### Constat

| Motif | Occurrences |
|-------|-------------|
| `startEditing()` | 28 |
| `beginEditCommand()` / `endEditCommand()` | **0** |

Le schéma dominant (ex. `calc_pentes.py:23-49`) :

```python
conduite_layer.startEditing()
for feat in conduite_layer.getFeatures():
    ...
    conduite_layer.changeAttributeValue(feat.id(), pente_idx, round(pente, 3))
conduite_layer.commitChanges()
```

Problèmes :

1. **Performance** : chaque `changeAttributeValue()` passe par le buffer d'édition et émet des signaux (`attributeValueChanged`) qui peuvent déclencher des repaints/recalculs en cascade. Sur 2 000 entités, c'est 2 000 émissions de signaux.
2. **Annulation** : sans `beginEditCommand()`, chaque modification est une entrée séparée dans la pile d'undo — un Ctrl+Z de l'utilisateur n'annule qu'**une seule** valeur au lieu de l'opération complète.
3. **Cohérence** : si `commitChanges()` échoue à mi-parcours, aucun rollback groupé.

### Recommandations

**Option A — écriture batch via le provider** (adaptée ici : couches mémoire, pas de besoin d'undo pour un recalcul automatique) :

```python
amap = {}   # {fid: {field_idx: valeur}}
for feat in conduite_layer.getFeatures():
    ...
    amap[feat.id()] = {pente_idx: round(pente, 3)}
conduite_layer.dataProvider().changeAttributeValues(amap)
conduite_layer.triggerRepaint()
```

Un seul appel, un seul lot de signaux.

**Option B — commande d'édition groupée** (pour les actions utilisateur qui doivent rester annulables : move, delete, insert_regard) :

```python
layer.beginEditCommand("Déplacement ouvrage + recalage branchements")
try:
    ...  # toutes les modifications
    layer.endEditCommand()
except Exception:
    layer.destroyEditCommand()
    raise
```

**Règle proposée :** recalculs automatiques (pentes, longueurs, cotes) → Option A ; actions interactives → Option B.

---

## 3. Requêtes réseau synchrones dans le thread UI 🟠

### Constat

Quatre fonctions de `main.py` téléchargent des données WFS/BAN avec `urllib.request.urlopen()` **bloquant**, dans le thread principal :

| Fonction | Ligne | Requêtes | Timeout |
|----------|-------|----------|---------|
| `run_fond_projet` | 867 | jusqu'à **4 WFS** enchaînées (BAN, BD TOPO routes, bâti, parcelles) | 30 s chacune |
| `run_pci_emprise` | 1052 | 2 WFS | 30 s |
| `_wfs_emprise` | 1203 | 1 WFS | 20 s |
| `run_ban_vecteur` | 1283 | 1 WFS | 30 s |

Pendant le téléchargement, **QGIS est entièrement gelé** : le `QApplication.setOverrideCursor(Qt.WaitCursor)` affiche un sablier mais l'interface ne répond plus. Au-delà de ~5 s, Windows marque la fenêtre « Ne répond pas ». Dans le pire cas de `run_fond_projet` (serveur lent), le gel peut atteindre **4 × 30 s = 2 minutes**.

### Problèmes annexes

**a) TLS désactivé** (`main.py:906-908`, répété 4×) :

```python
ssl_ctx = ssl.create_default_context()
ssl_ctx.check_hostname = False
ssl_ctx.verify_mode    = ssl.CERT_NONE
```

`data.geopf.fr` présente un certificat valide. Désactiver la vérification systématiquement expose à une interception (MITM) sur les réseaux non maîtrisés, et masquerait un vrai problème de certificat. Si le besoin vient d'un proxy d'entreprise avec certificat auto-signé, préférer : tentative avec vérification → fallback explicite avec message d'avertissement.

**b) Fichiers temporaires jamais nettoyés** :

```python
tmp = tempfile.NamedTemporaryFile(mode='w', suffix='.geojson', delete=False,
                                  encoding='utf-8', prefix='bet_fdp_')
```

Préfixes `bet_fdp_`, `bet_pci_`, `bet_wfs_` : les GeoJSON créés à chaque chargement de fond de plan restent dans `%TEMP%` indéfiniment (la couche OGR pointe dessus tant que le projet est ouvert, mais rien ne les supprime ensuite). Sur un poste utilisé quotidiennement, cela représente des centaines de fichiers de plusieurs Mo.

**c) Duplication massive** : le pipeline « emprise → bbox L93 → URL WFS → urlopen → GeoJSON temp → `QgsVectorLayer` → ajout en bas de légende » est écrit **4 fois** (~60 lignes chacune) avec des variations mineures. `_wfs_emprise()` existe déjà comme helper mais n'est utilisé nulle part par les trois autres fonctions.

### Recommandations

1. **Un seul helper de téléchargement asynchrone** basé sur `QgsTask` :

```python
from qgis.core import QgsTask, QgsApplication

def load_wfs_async(self, typename, layer_name, style_cb=None):
    bbox = self._current_bbox_l93()

    def download(task):
        # thread de travail : réseau + écriture du GeoJSON uniquement
        return _fetch_to_geojson(typename, bbox)   # -> chemin fichier

    def done(exception, path=None):
        # thread principal : création + ajout de la couche
        if exception or not path:
            self.iface.messageBar().pushWarning(layer_name, str(exception))
            return
        layer = QgsVectorLayer(path, layer_name, "ogr")
        ...

    task = QgsTask.fromFunction(f"WFS {layer_name}", download, on_finished=done)
    QgsApplication.taskManager().addTask(task)
```

   L'utilisateur voit la progression dans la barre de tâches QGIS et peut continuer à travailler. Les 4 requêtes de `run_fond_projet` peuvent en plus partir **en parallèle**.

2. **Nettoyage des temporaires** : stocker les chemins créés dans une liste sur le plugin et les supprimer dans `cleanup_plugin_resources()` ; ou mieux, écrire dans un sous-dossier dédié (`%TEMP%/bet_humide/`) purgé au démarrage du plugin.

3. **Réactiver la vérification TLS** par défaut (voir a).

4. Alternative encore plus simple pour les flux WFS : utiliser directement le **provider WFS natif de QGIS** (`QgsVectorLayer(uri, name, "WFS")` avec `restrictToRequestBBOX=1`) — streaming, cache et gestion réseau gérés par QGIS, plus aucun fichier temporaire. À évaluer car le comportement de chargement diffère (progressif vs instantané).

---

## 4. Poids du paquet et hygiène du dépôt git 🟡

### Constat

| Élément | Taille | Remarque |
|---------|--------|----------|
| Total plugin | 81 Mo | |
| `libs/` | **65 Mo** | dont l'essentiel évitable |
| `.git/` | 14 Mo | gonflé par l'historique de `libs/` |
| Code du plugin proprement dit | ~2 Mo | |

Détail de `libs/` :

| Composant | Taille | Verdict |
|-----------|--------|---------|
| `numpy.libs` + `numpy` | **35 Mo** | ❌ **Inutile** : QGIS embarque déjà numpy dans son Python |
| `ezdxf` | 18 Mo | ✅ Justifié (export DXF), non fourni par QGIS |
| `fontTools` | 11 Mo | ⚠️ À vérifier : dépendance optionnelle d'ezdxf (rendu MTEXT) ; QGIS l'embarque souvent déjà |
| `pyparsing` | 1 Mo | ⚠️ Fourni par QGIS (dépendance de matplotlib/packaging) |
| `bin/*.exe` (ezdxf.exe, f2py.exe, ttx.exe…) | 760 Ko | ❌ Scripts console jamais appelés par le plugin |
| `*.dist-info` (×4) | ~570 Ko | ❌ Métadonnées pip inutiles à l'exécution |
| `libs/__pycache__` | 160 Ko | ❌ Régénéré à la volée |

### Problème git : `libs/` ignoré… mais déjà tracké

Le `.gitignore` contient bien `libs/`, **mais 1 688 fichiers de `libs/` sont encore suivis par git** (commités avant l'ajout de la règle — un `.gitignore` n'a aucun effet sur les fichiers déjà indexés). Conséquences : `.git` de 14 Mo, diffs pollués si une lib est mise à jour, clone lent.

### Recommandations

1. **Détracker `libs/` sans le supprimer du disque :**

```bash
git rm -r --cached libs/
git commit -m "Retire libs/ du suivi git (couvert par .gitignore)"
```

   (Pour récupérer les 14 Mo de `.git`, il faudrait réécrire l'historique — `git filter-repo --path libs --invert-paths` — utile seulement si le dépôt est partagé/cloné.)

2. **Supprimer numpy de `libs/`** et importer celui de QGIS. Vérification préalable dans la console Python QGIS : `import numpy; numpy.__version__`. Gain : **−35 Mo**.

3. Tester le plugin après suppression de `pyparsing` et, si ezdxf fonctionne sans (le rendu MTEXT dégradé est acceptable ?), de `fontTools`. Gain potentiel : −12 Mo supplémentaires.

4. **Script de packaging** (à intégrer au skill `qgis-plugin-publisher`) qui construit le ZIP de distribution en excluant : `libs/bin/`, `*.dist-info/`, `__pycache__/`, `.git/`, `amelioration.txt`, `audit.md`. Paquet final estimé : **~20 Mo au lieu de 81 Mo**.

---

## 5. Qualité de code et duplications 🟡

### a) `run_cubature` / `run_remblai` dupliqués à ~95 %

`main.py:640-696` et `main.py:697-752` : deux blocs de ~55 lignes strictement identiques à trois différences près (clé d'action, titre de fenêtre, flag `show_remblai`). Toute correction future devra être faite deux fois — c'est le terreau classique des divergences de comportement.

**Proposition :**

```python
def run_cubature(self, checked):
    self._run_cubature_remblai(checked, key='cubature',
                               titre="Cubature tranchées", show_remblai=False)

def run_remblai(self, checked):
    self._run_cubature_remblai(checked, key='remblai',
                               titre="Remblai de tranchées", show_remblai=True)
```

### b) Pipeline WFS écrit 4 fois

Déjà détaillé au §3c. Le helper `_wfs_emprise()` (`main.py:1203`) fait déjà 80 % du travail : le compléter (callback de style, position dans la légende) et faire converger `run_fond_projet`, `run_pci_emprise` et `run_ban_vecteur` dessus. Économie : ~180 lignes.

### c) Calcul de bbox L93 répété 4 fois

Le bloc « extent canvas → reprojection EPSG:2154 → chaîne bbox » apparaît à l'identique aux lignes 898-904, 1066-1075, 1220-1230, 1298-1307 de `main.py`. → méthode `_current_bbox_l93(self) -> str`.

### d) Doublon `config_dialog.py`

- `config_dialog.py` (racine, 392 octets)
- `gui/config_dialog.py` (31 Ko, le vrai)

Le fichier racine est vraisemblablement un shim de réexport pour compatibilité (`main.py:645` fait `from .config_dialog import get_cubature_config`). À clarifier : soit mettre à jour les imports et supprimer le shim, soit documenter son rôle en en-tête.

### e) Configuration stockée en `QSettings` globales et non dans le projet

Les identifiants de couches sont persistés en **QSettings utilisateur** (`BET_HUMIDE/couche_conduite_eu`, etc. — `main.py:440-448`), donc **partagés entre tous les projets QGIS**. Scénario de bug : l'utilisateur travaille sur le projet A, ouvre le projet B → les clés pointent vers des IDs de couches du projet A ; `_get_couches` ne les trouve pas et **recrée des couches vides** dans B, ou pire, si B contient par hasard un layer de même ID, écrit dedans.

**Proposition :** persister ces clés dans le projet :

```python
QgsProject.instance().writeEntry("BET_HUMIDE", f"couche_{role}_{reseau}", layer.id())
value, ok = QgsProject.instance().readEntry("BET_HUMIDE", key)
```

Les QSettings restent pertinentes pour les préférences *utilisateur* (taille d'étiquettes par défaut, dernier dossier utilisé).

### f) Points mineurs

- **`QVariant.Double` / `QVariant.String`** (`main.py:331+`) : API dépréciée depuis QGIS 3.38 au profit de `QMetaType.Type.Double`. Non bloquant avec `qgisMinimumVersion=3.28`, mais à prévoir pour la pérennité.
- **`QgsSimpleMarkerSymbolLayer.Circle`** : idem, les enums de forme migrent vers `Qgis.MarkerShape`.
- **`exec_()`** utilisé partout : déprécié en PyQt6 (QGIS 4) au profit de `exec()`. Migration mécanique à anticiper.
- `main.py:1177` : `from qgis.core import Qgis` importé **au milieu** de `_style_pci_layer` alors que le module est déjà importé en tête de fonction voisine — à remonter.
- `_style_pci_layer` teste `"Bâti" in layer_name` (avec accent) alors que la couche s'appelle `"PCI - Bati"` (sans accent, `main.py:984`) → **le style bâti de cette branche n'est jamais appliqué** dans `run_pci_emprise` (il l'est via un autre chemin dans `run_fond_projet`). Bug latent typique de la duplication du §5b.
- `unload()` (`main.py:289`) appelle `removePluginMenu("Réseau Assainissement", action)` alors que le menu a été créé via `pluginMenu().addMenu(...)` — la suppression effective repose sur le `sip.delete(self.menu)` qui suit ; l'appel `removePluginMenu` est probablement sans effet.

---

## 6. Métadonnées et publication 🟡

`metadata.txt` actuel :

```
name=Réseau Assainissement
version=1.0
qgisMinimumVersion=3.28
author=Ton nom          ← placeholder
email=ton@email.com     ← placeholder
```

Bloquants pour une publication sur plugins.qgis.org (ou simplement pour un partage propre) :

1. `author` / `email` sont des placeholders.
2. Pas de `repository=`, `tracker=`, `homepage=` (obligatoires pour le dépôt officiel).
3. Pas de `changelog=`.
4. Incohérence de nommage : dossier `BET_HUMIDE`, `name=Réseau Assainissement`, classe `ReseauAssainissementPlugin`, préfixe QSettings `BET_HUMIDE/` — choisir une identité unique.
5. `version=1.0` figée alors que le développement est actif — adopter un versionnage incrémental (le skill `qgis-plugin-publisher` gère le bump automatiquement).

---

## Plan d'action recommandé

| # | Action | Fichiers concernés | Effort | Impact |
|---|--------|--------------------|--------|--------|
| 1 | Index spatiaux (`spatial_cache.py`) + `QgsFeatureRequest.setFilterRect` | `calc_pentes.py`, `move_tool.py`, `delete_tool.py`, `draw_branchement_tool.py`, `cubature_tool.py`, `renommer_tool.py`… | 1-2 j | 🔴 Fluidité sur gros réseaux |
| 2 | Écritures batch `changeAttributeValues` + `beginEditCommand` sur les outils interactifs | mêmes fichiers | 0,5 j | 🟠 Commits rapides, undo propre |
| 3 | Helper WFS unique + `QgsTask` asynchrone + nettoyage temp + TLS | `main.py` §3 | 1 j | 🟠 Fin des gels UI |
| 4 | `git rm -r --cached libs/` + suppression numpy/pyparsing/bin/dist-info + script de packaging | `libs/`, `.gitignore` | 0,5 j | 🟡 −50 Mo |
| 5 | Factorisation cubature/remblai, bbox L93, fix bug « Bâti/Bati », clés projet vs QSettings | `main.py` | 0,5 j | 🟡 Maintenabilité + bug fix |
| 6 | `metadata.txt` complet + versionnage | `metadata.txt` | 15 min | 🟡 Publication |

Les points 1 et 2 se traitent naturellement ensemble (mêmes fichiers, mêmes boucles). Le point 3 corrige au passage le bug latent du style bâti (§5f).
