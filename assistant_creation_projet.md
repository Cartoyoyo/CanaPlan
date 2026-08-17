# Assistant de création de projet — Plan d'implémentation

Décidé en discussion le 2026-08-17. Remplace le flux actuel `WelcomeDialog.NEW`
(`save_projet_sous()` direct) par un assistant en 4 étapes, navigable en
arrière/avant, qui se termine par le même `save_projet_sous()`.

## Décisions actées

- **Entrée** : bouton "Nouveau projet" du `WelcomeDialog` renommé
  "Débuter avec l'assistant" ; lance l'assistant au lieu d'appeler
  `save_projet_sous()` directement.
- **Étape 1 (adresse)** : `QgsMapCanvas` dédié et léger (couche OSM
  temporaire, jamais ajoutée au projet), barre de recherche BAN flottante
  avec debounce (mini-provider maison inspiré de
  `magic_search/providers/ban_provider.py`, pas de dépendance au plugin).
  Pan/zoom libres après sélection d'une adresse. L'étendue finale du mini-canvas
  devient l'étendue de départ du vrai canvas QGIS.
- **Étape 2 (fonds de plan)** : cases à cocher — OSM + Ortho cochées par
  défaut, BAN vecteur / Noms de voie / PCI Bâti / PCI Parcelles en option.
  Réutilise `run_fond_projet()`, qui gagne un paramètre `options: dict|None`
  (défaut = tout activé, comportement actuel inchangé pour le bouton toolbar).
- **Étape 3 (config rapide)** : les widgets `NetworkSchemaWidget` /
  `CubatureSchemaWidget` / `TrenchSchemaWidget` (et les formulaires associés)
  sont **extraits** de `ConfigDialog` en 3 widgets réutilisables
  (`ReseauDefautWidget`, `CubatureConfigWidget`, `RemblaiConfigWidget`) dans
  `gui/quick_config_widgets.py`. `ConfigDialog` les embarque en onglets comme
  avant (zéro régression). L'assistant les embarque en accordéons repliables
  (`QToolBox`). Mêmes clés `QgsSettings`, donc pas de nouvelle persistance —
  ce que l'assistant écrit, `ConfigDialog` le relit et vice-versa.
  L'onglet "Couches" de `ConfigDialog` (association aux couches existantes)
  n'a pas de sens pour un projet neuf : absent de l'assistant.
- **Étape 4 (récap)** : résumé texte des 3 étapes, retour libre à n'importe
  quelle étape, bouton "Créer" qui : applique l'étendue à `iface.mapCanvas()`,
  appelle `run_fond_projet(options)`, appelle `save_settings()` sur les 3
  widgets de config rapide, puis `save_projet_sous(self, iface)`.

## Fichiers

- **Nouveau** `gui/quick_config_widgets.py` — extraction de
  `ReseauDefautWidget`, `CubatureConfigWidget`, `RemblaiConfigWidget` depuis
  `gui/config_dialog.py` (chacun avec `load_settings()` / `save_settings()` /
  `summary()`).
- **Modifié** `gui/config_dialog.py` — `ConfigDialog` instancie les 3 widgets
  au lieu de construire leur UI inline ; conserve l'onglet "Couches" tel quel.
- **Nouveau** `tools/ban_search.py` — `BanSearchProvider` (QNetworkAccessManager,
  debounce 1000 ms, signal `results_ready(list)`), calqué sur
  `magic_search/providers/ban_provider.py`.
- **Nouveau** `gui/ban_search_widget.py` — `QLineEdit` + liste de suggestions
  flottante, émet `address_picked(lon, lat, label)`.
- **Nouveau** `gui/project_wizard_dialog.py` — `ProjectWizardDialog` :
  `QStackedWidget` de 4 pages + barre de progression/étapes + boutons
  Précédent/Suivant/Créer. Pages : `_AddressPage`, `_BasemapsPage`,
  `_QuickConfigPage`, `_RecapPage`.
- **Modifié** `gui/welcome_dialog.py` — libellé du bouton "Nouveau projet"
  → "Débuter avec l'assistant".
- **Modifié** `main.py` :
  - `_ensure_project_loaded()` : `NEW` → ouvre `ProjectWizardDialog` au lieu
    d'appeler `save_projet_sous()` directement.
  - `run_fond_projet(self, options=None)` : ajout du paramètre optionnel,
    chaque bloc (OSM, Ortho, BAN, Noms de voie, PCI Bâti, PCI Parcelles)
    conditionné par `options.get(clé, True)`.

## État d'implémentation (2026-08-17)

Implémenté :
1. ✅ `gui/quick_config_widgets.py` créé — `ReseauDefautWidget`,
   `CubatureConfigWidget`, `RemblaiConfigWidget` avec `load_settings()` /
   `save_settings()` / `summary()`.
2. ✅ `gui/config_dialog.py` refactoré pour déléguer aux 3 widgets
   (l'onglet "Couches" reste inline, propre à `ConfigDialog`).
3. ✅ `main.py` : `run_fond_projet(self, options=None)` — chaque bloc
   (OSM, Ortho, BAN, Noms de voie, PCI Bâti, PCI Parcelles) conditionné par
   `options.get(clé, True)`.
4. ✅ `tools/ban_search.py` (`BanSearchProvider`) + `gui/ban_search_widget.py`
   (`BanSearchWidget`).
5. ✅ `gui/project_wizard_dialog.py` (`ProjectWizardDialog`, 4 pages).
6. ✅ Branchement :
   - `gui/welcome_dialog.py` : bouton renommé "Débuter avec l'assistant".
   - `main.py` : nouvelle action `nouveau_projet_assistant` (menu "Projet",
     en tête, avant "Enregistrer") + `run_nouveau_projet_assistant()` —
     accessible directement, pas seulement via le `WelcomeDialog`.
   - `_ensure_project_loaded()` délègue à `run_nouveau_projet_assistant()`.

Tout compile (`py_compile`) mais **non testé dans QGIS** — à faire avant
usage réel (voir checklist ci-dessous).

## Ordre d'implémentation

1. Extraction des widgets de config rapide (`quick_config_widgets.py`) +
   refactor de `ConfigDialog` — pas de changement de comportement visible,
   vérifiable en ouvrant "Configuration rapide" depuis le menu existant.
2. `run_fond_projet(options=None)` — refactor rétrocompatible.
3. `tools/ban_search.py` + `gui/ban_search_widget.py`.
4. `gui/project_wizard_dialog.py` (les 4 pages).
5. Branchement dans `welcome_dialog.py` + `main.py`.
6. Test manuel dans QGIS (assistant complet, retour arrière entre étapes,
   vérification que `ConfigDialog` et l'assistant partagent bien les mêmes
   valeurs).

## Points de vigilance

- Le mini-`QgsMapCanvas` de l'étape 1 doit avoir son propre `QgsMapSettings`/
  CRS (EPSG:2154, comme le reste du plugin) et ne jamais toucher
  `QgsProject.instance()` avant l'étape "Créer".
- `run_fond_projet()` est aussi appelé depuis le menu "Fonds de plan" en
  dehors de l'assistant : le paramètre `options=None` doit reproduire
  exactement l'ancien comportement (tout activé) pour ne rien casser là.
- Les 3 widgets extraits doivent rester strictement équivalents visuellement
  à ce qu'ils remplacent dans `ConfigDialog` (mêmes signaux de rafraîchissement
  des schémas).
