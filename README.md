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
| **Renseigner** | Survol pour mettre en evidence un element (orange), clic pour ouvrir son formulaire d'attributs. Les champs numeriques (TN, FE, profondeur, diametre, longueur, pente, cote piquage) acceptent des **expressions additives** : ex. `1-0.25` -> `0.750`, `2+0.5-0.1` -> `2.400`. Pas de multiplication / division. Le champ recalcule TN / FE / P automatiquement quand l'un des trois est modifie. |
| **Deplacer** | Deplace un ouvrage (regard ou tabouret) et recale automatiquement les conduites et branchements connectes. Permet aussi de deplacer une etiquette (regard / tabouret / conduite) sans toucher a l'ouvrage. Mode **piquage** : survol du point de piquage d'un branchement (surligne en orange) puis glisser-deposer pour repositionner le piquage le long de la conduite ; met a jour `id_conduite`, `pk_debut`, `cote_piquage` et recale la geometrie du branchement. |
| **Effacer** | Supprime un element et ses etiquettes associees. Lasso possible pour une selection multiple. |
| **Copier les attributs** | Copie les attributs (diametre, materiau...) d'un element vers un ou plusieurs autres du meme type. |

### Analyse

| Outil | Description |
|---|---|
| **Profil en long EU / EP** | Selectionner deux regards pour tracer le profil en long du troncon (BFS). Affiche les cotes TN, radier et la pente. Dialogue d'options (cartouche, fleches piquages, noms, distances, format papier A3/A4). Export PDF/SVG/PNG. Nom de fichier : `{nom_dep}_{nom_arr}_PROFIL.{fmt}`. Necessite **matplotlib**. |
| **Profil groupe EU + EP** | Superpose les profils EU et EP sur le meme graphique. Premier clic = regard depart du reseau de reference, second clic = regard arrivee. Le second reseau est automatiquement projete sur l'axe (buffer 3 m). Nom de fichier : `{eu_dep}_{eu_arr}_{ep_dep}_{ep_arr}_PROFIL.{fmt}`. |
| **Coupe transversale EU** | Trace un axe de coupe sur le reseau EU uniquement. Les conduites croisees sont representees en section avec TN, FE, lit de pose, enrobage, remblai et chaussee. |
| **Coupe transversale EP** | Meme principe sur le reseau EP uniquement. |
| **Coupe transversale des tranchees** | Trace un axe de coupe croisant les reseaux EU et EP simultanement. Genere un plan de coupe A4/A3 (**paysage par defaut**) avec : profil de coupe (tranchees empilees par largeur configuree, cotes NGF), plan de situation (couches QGIS visibles + trait de coupe), titre et cartouche. Export PDF. |
| **Dessinateur – Coupe de tranchees composee** | Dialogue de dessin de coupes de tranchees composees (EU et EP cote a cote). Gestion de N tranches juxtaposees : reseau (EU/EP), DN, materiau, profondeur fil d'eau, ecarts gauche/droit, lit de pose, enrobage, remblai, chaussee inferieure (GB/GC) et superieure (enrobe). Apercu matplotlib temps reel avec cotes, annotations de couches et couleurs conventionnelles. Export PDF et PNG (200 dpi). Les valeurs par defaut des couches de remblai heritent de la configuration rapide. Memorisation automatique des dernieres tranches saisies (QgsSettings). Necessite **matplotlib**. |

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
| **Creer les etiquettes** | Configure le moteur d'etiquettes QGIS sur toutes les couches EU et EP. Regards / tabourets : fond rectangulaire blanc + cadre + ligne de rappel (callout). Conduites : moteur **regle** (rule-based labeling) avec deux regles : **Regle 1** (etiquette non deplacee, `lbl_x IS NULL`) placement curviligne automatique le long de la conduite ; **Regle 2** (etiquette deplacee / epinglee, `lbl_x IS NOT NULL`) placement au-dessus du point d'ancrage avec callout et orientation figee via le champ `lbl_rot`. Branchements : halo blanc 0.8 mm. |
| **Afficher / Masquer** | Bascule la visibilite des etiquettes sans reconfigurer le moteur. |
| **Taille des etiquettes** | Regle la taille des etiquettes (points ecran ou metres carte) sur toutes les couches. Memorise le dernier reglage (mode + valeur) et le restaure a l'ouverture du dialogue. |
| **Forcer toutes les etiquettes visibles** | Active le decalage automatique pour qu'aucune etiquette ne soit supprimee par le moteur de placement. |
| **Gestion de l'affichage** | Dialogue pour activer/desactiver les etiquettes par reseau et par role, et choisir les champs affiches. |

### Annotations

| Outil | Description |
|---|---|
| **Annotation texte** | Pose un texte libre sur la carte (mainAnnotationLayer du projet). Clic sur zone vide = creation, clic sur annotation existante = edition. Police, taille, couleur, gras / italique / souligne, alignement gauche / centre / droite. Taille en **metres** (RenderMapUnits) : l'annotation suit le zoom comme les conduites, ne grossit plus relativement au plan au dezoom. |
| **Copier / coller** | `Ctrl + clic` sur une annotation = duplication immediate avec leger decalage. `Ctrl + C` (curseur sur l'annotation) = copie dans un presse-papier interne au plugin. `Ctrl + V` puis clic = collage au point clique. `Echap` annule un coller en attente. |
| **Figer en map units** | Fonction `freeze_annotations_to_map_units(canvas)` exposable dans la console Python : convertit toutes les annotations existantes (qui seraient en pt) vers map units, calcule a la vue courante du canvas — regle la vue sur 1:200 avant de lancer pour avoir une taille coherente. |

### Gestion de projet

| Outil | Description |
|---|---|
| **Enregistrer** | Sauvegarde toutes les couches EU/EP dans une archive `.bet` (ZIP contenant un GeoPackage + metadonnees JSON). |
| **Enregistrer sous** | Choisit un dossier et un nom, cree un fichier `.bet`. |
| **Charger un projet** | Charge un fichier `.bet` (v2 ZIP ou v1 JSON legacy) et restaure les couches, etiquettes et visibilite. |
| **Importer DXF / DWG** | Convertit un fichier DXF/DWG en couches vectorielles (points, polylignes, polygones). |
| **Importer Star-DT (GML)** | Lit un fichier GML Star-DT (releve topographique) et cree les couches points / polylignes correspondantes, filtrees par type d'objet. |
| **Imprimer / Exporter PDF / DXF** | Positionne les feuilles d'impression sur la carte (clic + rotation), puis genere un PDF multi-pages avec cartouche, barre d'echelle et page de vue d'ensemble optionnelle. Resolution PDF parametrable (96 / 150 / 200 / 300 dpi ou personnalisee) avec suggestion automatique selon le format (A4 → 300 dpi, A2/A3 → 200 dpi, A0/A1 → 150 dpi). Export DXF 2018 fidele en parallele : symbologie, etiquettes (MTEXT + decoration ezdxf : fond + cadre + callout), symboles ponctuels, pattern de tirets EU/EP. Encodage CP1252 (compatibilite AutoCAD). |
| **Export combine** | Dialogue unique pour generer en une passe : plan PDF, plan DXF, profils EU, profils EP, profil groupe (avec choix du reseau de reference EU ou EP). Tous les exports vont dans un dossier choisi, noms de fichiers automatiques (1er regard / dernier regard). |

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
| `lbl_x` | Double | X du point d'ancrage de l'etiquette (NULL = placement auto) |
| `lbl_y` | Double | Y du point d'ancrage de l'etiquette (NULL = placement auto) |
| `lbl_rot` | Double | Angle de l'etiquette epinglee en degres (suit l'angle de la conduite au point d'ancrage) |
| `lbl_visible` | Int | Visibilite forcee de l'etiquette (0 = masquee) |

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

Toutes les dimensions sont en **map units (metres)** — la symbologie suit le zoom et reste proportionnelle au plan a 1:200.

- **EU** — Eaux Usees : couleur **rouge**
  - Conduites : largeur data-defined `coalesce("diametre", 200) / 1000` m (epaisseur reelle de la conduite a l'echelle du plan)
  - Branchements : largeur data-defined identique
  - Regards : cercle (1 m de diametre)
  - Tabourets : carre (0.4 m de cote)

- **EP** — Eaux Pluviales : couleur **bleue**
  - Meme logique que EU

Etiquettes : couleur du reseau (rouge EU / bleu EP), halo blanc 0.8 mm pour les conduites / branchements, fond rectangulaire blanc + cadre + ligne de rappel pour regards / tabourets.

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

### Outil Annotation

| Touche / Action | Effet |
|---|---|
| **Clic gauche** (zone vide) | Ouvre le dialogue de creation |
| **Clic gauche** (sur une annotation) | Ouvre le dialogue d'edition pre-rempli |
| **Ctrl + clic** (sur une annotation) | Duplication immediate avec decalage de ~30 px |
| **Ctrl + C** (curseur sur une annotation) | Copie dans le presse-papier interne du plugin |
| **Ctrl + V** | Active le mode coller — le prochain clic gauche depose la copie |
| **Echap** | Annule le coller en attente |

### Champs numeriques (Renseigner)

| Saisie | Resultat |
|---|---|
| `1.5` | `1.500` |
| `1-0.25` | `0.750` |
| `2+0.5-0.1` | `2.400` |
| `-1.5+2` | `0.500` |

Les operateurs `*` et `/` ne sont pas supportes — uniquement `+` et `-`.

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
- **matplotlib** (optionnel) — requis pour le profil en long, la coupe transversale et le dessinateur de coupes de tranchees composees
- **ezdxf** (deja inclus dans `libs/`) — utilise pour le post-traitement de l'export DXF (fonds + cadres + lignes de rappel + symboles ponctuels)
- **reportlab** (optionnel) — requis pour les exports PDF de cubature / remblai
- **openpyxl** (optionnel) — requis pour les exports Excel de cubature / remblai

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
│   ├── etiquette_affichage_dialog.py # Dialogue de gestion de l'affichage des etiquettes
│   ├── coupe_tranchee_composee_dialog.py # Dessinateur de coupes de tranchees composees (matplotlib)
│   ├── annotation_dialog.py        # Dialogue d'annotation (texte, police, couleur, alignement)
│   ├── export_dialog.py            # Dialogue d'export combine (plan PDF/DXF + profils)
│   ├── welcome_dialog.py           # Dialogue d'accueil (nouveau / ouvrir / annuler)
│   ├── star_dt_dialog.py           # Dialogue d'import GML Star-DT
│   └── config_dialog.py            # Dialogue de configuration (reseaux, couches, cubature, remblai)
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
│   ├── annotation_tool.py          # Outil d'annotation texte (clic / ctrl+clic / ctrl+c-v)
│   ├── profil_batch.py             # Export batch profils EU/EP/groupe (ExportDialog)
│   ├── dxf_export.py               # Export DXF 2018 (pattern QgsDxfExport canonique)
│   ├── dxf_postprocess.py          # Decoration ezdxf (fond + cadre + callout etiquettes, symboles, ltscale)
│   ├── star_dt_import.py           # Import GML Star-DT
│   ├── projet_bet.py               # Sauvegarde / chargement .bet (archive ZIP)
│   ├── graph_utils.py              # Construction graphe + BFS (partages par tous les outils BFS)
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
