# BET Humide — Plugin QGIS Reseau Assainissement

Plugin QGIS de dessin topologique de reseaux d'assainissement **EU** (Eaux Usees) et **EP** (Eaux Pluviales), avec continuite geometrique, recalage automatique des branchements et gestion des etiquettes.

---

## Fonctionnalites

### Dessin de reseau

| Outil | Description |
|---|---|
| **Conduite EU / EP** | Trace d'une conduite par clics successifs. Chaque sommet genere automatiquement un regard. |
| **Branchement EU / EP** | Piquage sur une conduite existante, trace libre jusqu'a un ouvrage (regard ou tabouret). |
| **Inserer un regard** | Insere un regard sur une conduite existante en cliquant sur la conduite. |

### Edition

| Outil | Description |
|---|---|
| **Renseigner** | Survol pour mettre en evidence un element (orange), clic pour ouvrir son formulaire d'attributs. |
| **Deplacer** | Deplace un ouvrage (regard ou tabouret) et recale automatiquement les conduites et branchements connectes. |
| **Effacer** | Supprime un element et ses etiquettes associees. Lasso possible pour une selection multiple. |
| **Copier les attributs** | Copie les attributs (diametre, materiau...) d'un element vers un ou plusieurs autres du meme type. |

### Analyse

| Outil | Description |
|---|---|
| **Profil en long EU / EP** | Selectionner deux regards pour tracer le profil en long du troncon (BFS). Affiche les cotes TN, radier et la pente. Necessite **matplotlib**. |
| **Profil groupe EU + EP** | Superpose les profils EU et EP sur le meme graphique. Un premier clic selectionne le regard de depart du premier reseau, le second le regard d'arrivee, puis idem pour le second reseau. |
| **Coupe transversale EU** | Trace un axe de coupe sur le reseau EU uniquement. Les conduites croisees sont representees en section avec TN, FE, lit de pose, enrobage, remblai et chaussee. |
| **Coupe transversale EP** | Meme principe sur le reseau EP uniquement. |
| **Coupe transversale des tranchees** | Trace un axe de coupe croisant les reseaux EU et EP simultanement. Genere un plan de coupe A4/A3 (portrait ou paysage) avec : profil de coupe (tranchees empilees par largeur configuree, cotes NGF), plan de situation (couches QGIS visibles + trait de coupe), titre et cartouche. Export PDF. |

### Cubature et Remblai

| Outil | Description |
|---|---|
| **Cubature tranchees** | Calcule le volume de deblai des tranchees. Mode BFS (2 regards) ou reseau complet. Formule : `Volume = largeur × L3D × (prof_debut + prof_fin) / 2`. Export CSV, PDF, Excel. |
| **Remblai tranchees** | Calcule la decomposition du remblai par couche : lit de pose, enrobage, conduite, chaussee inf/sup et remblai. Parametrage des materiaux et epaisseurs dans la Configuration rapide (onglet Remblai). Export exhaustif CSV, PDF, Excel. |

### Renumerotation

| Outil | Description |
|---|---|
| **Renuméroter EU / EP** | Selectionner deux regards pour renumeroter tous les regards et tabourets du chemin (BFS). Un dialogue permet de saisir les prefixes et le numero de depart. |

### Etiquettes

| Outil | Description |
|---|---|
| **Creer les etiquettes** | Configure le moteur d'etiquettes QGIS sur toutes les couches EU et EP. |
| **Afficher / Masquer** | Bascule la visibilite des etiquettes sans reconfigurer le moteur. |
| **Taille des etiquettes** | Regle la taille des etiquettes (points ecran ou metres carte) sur toutes les couches. |
| **Forcer toutes les etiquettes visibles** | Active le decalage automatique pour qu'aucune etiquette ne soit supprimee par le moteur de placement. |
| **Gestion de l'affichage** | Dialogue pour activer/desactiver les etiquettes par reseau et par role, et choisir les champs affiches. |

### Gestion de projet

| Outil | Description |
|---|---|
| **Enregistrer** | Sauvegarde toutes les couches EU/EP dans une archive `.bet` (ZIP contenant un GeoPackage + metadonnees JSON). |
| **Enregistrer sous** | Choisit un dossier et un nom, cree un fichier `.bet`. |
| **Charger un projet** | Charge un fichier `.bet` (v2 ZIP ou v1 JSON legacy) et restaure les couches, etiquettes et visibilite. |
| **Importer DXF / DWG** | Convertit un fichier DXF/DWG en couches vectorielles (points, polylignes, polygones). |
| **Imprimer / Exporter PDF** | Positionne les feuilles d'impression sur la carte (clic + rotation), puis genere un PDF multi-pages avec cartouche et page de vue d'ensemble optionnelle. |

### Fonds de plan

| Outil | Description |
|---|---|
| **Mise en place fond de projet** | Charge les 6 fonds de carte (BAN, Noms de rue, PCI Bati, PCI Parcelles, OSM Desature, Ortho 2022) sur l'emprise courante et configure le projet (fond blanc, SCR). |
| **BAN Adresses (vecteur)** | Charge les adresses de la BAN sur l'emprise courante. |
| **Noms de rue BD TOPO** | Charge les voies nominees de la BD TOPO sur l'emprise courante. |
| **PCI Vecteur – Parcelles & Bati** | Charge le cadastre vectoriel sur l'emprise courante. |
| **Ortho 2022** | Ajoute le flux d'orthophotographie 2022. |
| **OSM Desature** | Ajoute un fond OpenStreetMap desature. |

---

## Couches et attributs

Le plugin gere 4 types de couches, declinees pour chaque reseau (`_EU` / `_EP`) :

### Conduite *(LineString)*
| Champ | Type | Description |
|---|---|---|
| `diametre` | Double | Diametre en mm |
| `materiau` | String | Materiau |
| `longueur` | Double | Longueur en m (calculee automatiquement) |
| `pente` | Double | Pente en % |

### Branchement *(LineString)*
| Champ | Type | Description |
|---|---|---|
| `id_conduite` | Int | ID de la conduite piquee |
| `pk_debut` | Double | Abscisse curviligne du piquage |
| `cote_piquage` | Double | Cote du piquage en m NGF |
| `diametre` | Double | Diametre en mm |
| `materiau` | String | Materiau |
| `longueur` | Double | Longueur en m |
| `pente` | Double | Pente en % |
| `sens` | String | Sens du branchement |

### Regard *(Point)*
| Champ | Type | Description |
|---|---|---|
| `nom` | String | Identifiant du regard |
| `tn` | Double | Terrain naturel en m NGF |
| `fe_radier` | Double | Fil d'eau radier en m NGF |
| `diametre` | Double | Diametre en mm |
| `profondeur` | Double | Profondeur en m |

### Tabouret *(Point)*
| Champ | Type | Description |
|---|---|---|
| `nom` | String | Identifiant du tabouret |
| `tn` | Double | Terrain naturel en m NGF |
| `fe_entree` | Double | Fil d'eau entree en m NGF |
| `diametre` | Double | Diametre en mm |
| `profondeur` | Double | Profondeur en m |

---

## Symbologie

- **EU** — Eaux Usees : couleur **rouge**
  - Conduites : ligne epaisse (1.2 pt)
  - Branchements : ligne fine (0.6 pt)
  - Regards : cercle
  - Tabourets : carre

- **EP** — Eaux Pluviales : couleur **bleue**
  - Meme logique que EU

---

## Raccourcis clavier

### Outils de dessin (conduite, branchement)

| Touche | Action |
|---|---|
| **Clic gauche** | Ajouter un point / un regard |
| **Clic droit** | Terminer le trace |
| **Backspace** | Annuler le dernier point |
| **Entree** | Valider le trace en cours |
| **Echap** | Annuler et supprimer tout ce qui a ete dessine |

### Outil Imprimer

| Touche / Action | Effet |
|---|---|
| **Clic gauche** (libre) | Poser une feuille a la position courante |
| **Clic gauche** (apres ancrage) | Valider la rotation et poser la feuille |
| **Clic droit** | Ancrer le centre de la feuille (active le mode rotation) |
| **Clic droit** (sans feuilles) | Generer le PDF |
| **Echap** | Annuler l'ancrage en cours |

### Outils BFS (Profil, Profil groupe, Renuméroter)

| Touche | Action |
|---|---|
| **1er clic gauche** | Selectionner le regard de depart (vert) |
| **2e clic gauche** | Selectionner le regard d'arrivee et lancer l'action |
| **Echap** | Annuler la selection en cours |

### Outil Copier les attributs

| Touche | Action |
|---|---|
| **1er clic gauche** | Copier les attributs de la source (bleu) |
| **Clics suivants** | Ajouter des cibles du meme type (vert) |
| **Clic droit** | Appliquer les attributs copies aux cibles |
| **Echap** | Annuler |

---

## Format de projet .bet

Le fichier `.bet` est une archive ZIP contenant :
- `metadata.json` — version, CRS, etat des etiquettes, visibilite des couches
- `data.gpkg` — toutes les couches EU/EP au format GeoPackage

Une rotation de sauvegardes est effectuee automatiquement : `.bet` → `.bak1` → `.bak2`.

La compatibilite ascendante est assuree avec le format v1 (JSON brut + GPKG externe).

---

## Installation

1. Copier le dossier `BET_HUMIDE` dans :
   ```
   %APPDATA%\QGIS\QGIS3\profiles\default\python\plugins\
   ```
2. Dans QGIS : **Extensions → Installer/Gerer les extensions → Installees** → cocher **Reseau Assainissement**.
3. La barre d'outils et le panneau lateral apparaissent automatiquement.

### Prerequis

- QGIS **>= 3.28** (recommande >= 3.38 pour eviter les avertissements `QMetaType`)
- **matplotlib** (optionnel) — requis pour le profil en long
- Aucune autre dependance Python externe

---

## Structure du projet

```
BET_HUMIDE/
├── main.py                         # Classe principale du plugin
├── config_dialog.py                # Dialogue de configuration (reseaux, couches, cubature, remblai)
├── __init__.py
├── metadata.txt
├── gui/
│   ├── __init__.py
│   ├── side_panel.py               # Panneau lateral (arbre des outils)
│   ├── etiquettes.py               # Moteur d'etiquettes QGIS
│   ├── renseignement_dialog.py     # Formulaire d'attributs
│   ├── print_dialog.py             # Dialogue format / echelle / orientation
│   ├── profil_dialog.py            # Affichage du profil en long (matplotlib)
│   ├── profil_groupe_dialog.py     # Profil groupe EU + EP (matplotlib)
│   ├── coupe_transversale_dialog.py# Plan de coupe transversale (matplotlib) + plan de situation QGIS
│   ├── cubature_dialog.py          # Tableau resultats cubature/remblai + exports CSV/PDF/Excel
│   ├── etiquette_taille_dialog.py  # Dialogue de reglage de la taille des etiquettes
│   └── etiquette_affichage_dialog.py # Dialogue de gestion de l'affichage des etiquettes
├── tools/
│   ├── __init__.py                 # Utilitaire partage layer_ok()
│   ├── draw_conduite_tool.py       # Trace des conduites
│   ├── draw_branchement_tool.py    # Trace des branchements
│   ├── insert_regard_tool.py       # Insertion de regard sur conduite
│   ├── renseignement_tool.py       # Survol et saisie des attributs
│   ├── move_tool.py                # Deplacement d'ouvrages
│   ├── delete_tool.py              # Suppression d'elements
│   ├── copy_attributes_tool.py     # Copie d'attributs entre elements
│   ├── profil_tool.py              # Profil en long (BFS + ProfilDialog)
│   ├── profil_groupe_tool.py       # Profil groupe EU + EP (BFS + ProfilGroupeDialog)
│   ├── renommer_tool.py            # Renumerotation le long d'un chemin BFS
│   ├── cubature_tool.py            # Selection BFS pour cubature/remblai tranchees
│   ├── calc_cubature.py            # Calcul cubature (volumes, BFS, remblai par couche)
│   ├── print_tool.py               # Impression PDF multi-feuilles
│   ├── coupe_transversale_tool.py  # Outil de trace de l'axe de coupe (EU+EP ou mono-reseau)
│   ├── projet_bet.py               # Sauvegarde / chargement .bet (archive ZIP)
│   ├── calc_pentes.py              # Recalcul des pentes a partir des FE radier
│   └── dxf_convert/                # Conversion DXF/DWG vers couches vectorielles
│       ├── ui_dialog.py            # Dialogue principal
│       ├── alg_cad_to_gis_convert.py
│       └── services/
└── icon/                           # Icones SVG de la barre d'outils
```

---

## Auteur

Developpe dans le cadre du BET Humide.
