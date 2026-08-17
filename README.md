# BET Humide — Plugin QGIS Reseau Assainissement

**Version 1.3** — QGIS >= 3.28

Plugin QGIS de dessin topologique de reseaux d'assainissement **EU** (Eaux Usees) et **EP** (Eaux Pluviales), avec continuite geometrique, recalage automatique des branchements et gestion des etiquettes.

Du trace sur le terrain jusqu'a la livraison : dessin, profils en long,
cubatures et remblais, coupes de tranchees, impression PDF multi-feuilles,
export DXF 2018 et export GeoPackage conforme au geostandard **StaR-Eau
V2024** (CNIG / ASTEE).

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
| **Tableau de saisie - pente** | Saisie groupee en tableau, par onglets **Regards / Tabourets / Conduites / Branchements**, avec calcul automatique de la pente ou de la cote fil d'eau selon le sens choisi. Apercu carte miniature de l'element selectionne, copier/coller depuis Excel, saisie multi-cellules, historique d'annulation (Ctrl+Z). Un onglet **Chaine** trace le profil simplifie entre deux regards choisis. Sur l'onglet Branchements, la **cote de piquage est interpolee sur la conduite mere** au PK du piquage : modifier un fil d'eau de la conduite met a jour en cascade tous les branchements qui y sont piques (cellule affichee en couleur « valeur derivee »). |

#### Modes de calcul du Tableau de saisie

Chaque ligne porte un **cadenas** qui indique quelles valeurs sont saisies et
laquelle est deduite. Convention de signe commune a tout le plugin (profils,
cubature, formulaire Renseigner) : la pente vaut
`(cote amont − cote aval) / longueur × 100`.

| Onglet | Mode | Saisi | Calcule |
|---|---|---|---|
| Conduites | `fe` | FE amont + FE aval | pente |
| Conduites | `pente_aval` | FE amont + pente | FE aval |
| Conduites | `pente_amont` | FE aval + pente | FE amont |
| Branchements | `fe` | cote piquage + FE tabouret | pente |
| Branchements | `pente_fe` | cote piquage + pente | FE tabouret *(applique au tabouret)* |
| Branchements | `pente_cote` | FE tabouret + pente | cote piquage |

Un branchement etant trace **du piquage vers le tabouret**, la pente d'un
branchement vaut `(cote piquage − FE tabouret) / longueur × 100`.

Dans les modes `fe` et `pente_fe`, la cote de piquage reste **asservie a la
conduite mere** : elle est interpolee entre les deux fils d'eau de la conduite
au PK du piquage, et se recalcule automatiquement quand ces fils d'eau
changent. Le mode `pente_cote` rompt volontairement ce lien, puisque la cote
de piquage y devient une valeur calculee a partir de la pente.

### Analyse

| Outil | Description |
|---|---|
| **Profil en long EU / EP** | Selectionner deux regards pour tracer le profil en long du troncon (BFS). Affiche les cotes TN, radier et la pente. Dialogue d'options (cartouche, fleches piquages, noms, distances, format papier A3/A4). Export PDF/SVG/PNG. Nom de fichier : `{nom_dep}_{nom_arr}_PROFIL.{fmt}`. Necessite **matplotlib**. |
| **Profil groupe EU + EP** | Superpose les profils EU et EP sur le meme graphique. Premier clic = regard depart du reseau de reference, second clic = regard arrivee. Le second reseau est automatiquement projete sur l'axe (buffer 3 m). Nom de fichier : `{eu_dep}_{eu_arr}_{ep_dep}_{ep_arr}_PROFIL.{fmt}`. |
| **Coupe transversale EU** | Trace un axe de coupe sur le reseau EU uniquement. Les conduites croisees sont representees en section avec TN, FE, lit de pose, enrobage, remblai et chaussee. |
| **Coupe transversale EP** | Meme principe sur le reseau EP uniquement. |
| **Coupe transversale des tranchees** | Trace un axe de coupe croisant les reseaux EU et EP simultanement. Genere un plan de coupe A4/A3 (**paysage par defaut**) avec : profil de coupe (tranchees empilees par largeur configuree, cotes NGF), plan de situation (couches QGIS visibles + trait de coupe), titre et cartouche. Export PDF. |
| **Dessinateur – Coupe de tranchees composee** | Dialogue de dessin de coupes de tranchees composees (EU, EP et **AEP** — eau potable, cote a cote). Gestion de N tranches juxtaposees : reseau (EU/EP/AEP), DN, materiau, profondeur fil d'eau, ecarts gauche/droit, lit de pose, enrobage, remblai, chaussee inferieure (GB/GC) et superieure (enrobe). Apercu matplotlib temps reel avec cotes, annotations de couches et couleurs conventionnelles (EU rouge, EP bleu, AEP cyan). Export PDF et PNG (200 dpi). Les valeurs par defaut des couches de remblai heritent de la configuration rapide. Memorisation automatique des dernieres tranches saisies (QgsSettings). Necessite **matplotlib**. |

### Cubature et Remblai

| Outil | Description |
|---|---|
| **Cubature / Remblai tranchees** | Calcule le volume de deblai des tranchees. Mode BFS (2 regards), axe trace (buffer 3 m) ou reseau complet. Formule : `Volume = largeur × L3D × (prof_debut + prof_fin) / 2`. Une case a cocher **« Afficher le detail remblai »** dans la fenetre de resultats affiche/masque a la volee les colonnes de decomposition du remblai (lit de pose, enrobage, conduite, chaussee inf/sup, remblai) sans refaire le calcul — parametrage des materiaux et epaisseurs dans la Configuration rapide (onglet Remblai). Sous-totaux par colonne (lineaires, surfaces, volumes) sur chaque ligne de sous-total EU/EP. Onglet/section **Synthese des ouvrages** (tronçons et branchements groupes par materiau/diametre, comptage des regards et tabourets). Fenetre redimensionnable, plein ecran, et qui s'ajuste automatiquement au nombre de lignes et de colonnes affichees. Export CSV, PDF, Excel. |

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
| **Annotation texte** | Pose un texte libre sur la carte (mainAnnotationLayer du projet). Clic sur zone vide = creation, clic sur annotation existante = edition. Police, taille, couleur, gras / italique / souligne, alignement gauche / centre / droite, cadre optionnel (rempli ou non, couleurs de fond/bordure independantes), transparence reglable. Taille liee a l'echelle configuree pour les etiquettes, en **metres** (RenderMapUnits) : l'annotation suit le zoom comme les conduites, ne grossit plus relativement au plan au dezoom. Bouton **Appliquer** pour previsualiser les changements sans fermer la fenetre. |
| **Copier / coller** | `Ctrl + clic` sur une annotation = duplication immediate avec leger decalage. `Ctrl + C` (curseur sur l'annotation) = copie dans un presse-papier interne au plugin. `Ctrl + V` puis clic = collage au point clique. `Echap` annule un coller en attente. |
| **Figer en map units** | Fonction `freeze_annotations_to_map_units(canvas)` exposable dans la console Python : convertit toutes les annotations existantes (qui seraient en pt) vers map units, calcule a la vue courante du canvas — regle la vue sur 1:200 avant de lancer pour avoir une taille coherente. |

### Gestion de projet

| Outil | Description |
|---|---|
| **Enregistrer** | Sauvegarde toutes les couches EU/EP dans une archive `.bet` (ZIP contenant un GeoPackage + metadonnees JSON). |
| **Enregistrer sous** | Choisit un dossier et un nom, cree un fichier `.bet`. |
| **Charger un projet** | Charge un fichier `.bet` (v2 ZIP ou v1 JSON legacy) et restaure les couches, etiquettes et visibilite. |
| **Importer DXF / DWG** | Convertit un fichier DXF/DWG en couches vectorielles (points, polylignes, polygones). |
| **Importer Star-DT (GML)** | Lit un ou plusieurs fichiers GML Star-DT / StaR-Elec (standard DT-DICT, reseaux enterres) et cree les couches points / polylignes / polygones correspondantes, filtrees par type d'objet. Selection multiple et glisser-deposer. Voir la section dediee ci-dessous. Sans rapport avec StaR-Eau : Star-DT decrit les reseaux pour les declarations de travaux, StaR-Eau decrit le patrimoine eau / assainissement. |
| **Imprimer / Exporter PDF / DXF** | Positionne les feuilles d'impression sur la carte (clic + rotation), puis genere un PDF multi-pages avec cartouche, barre d'echelle et page de vue d'ensemble optionnelle. Resolution PDF parametrable (96 / 150 / 200 / 300 dpi ou personnalisee) avec suggestion automatique selon le format (A4 → 300 dpi, A2/A3 → 200 dpi, A0/A1 → 150 dpi). Export DXF 2018 fidele en parallele : symbologie, etiquettes (MTEXT + decoration ezdxf : fond + cadre + callout), symboles ponctuels, pattern de tirets EU/EP. Encodage CP1252 (compatibilite AutoCAD). |
| **Export combine** | Dialogue unique pour generer en une passe : plan PDF, plan DXF, profils EU, profils EP, profil groupe (avec choix du reseau de reference EU ou EP). Tous les exports vont dans un dossier choisi, noms de fichiers automatiques (1er regard / dernier regard). |
| **Exporter StaR-Eau (GPKG)** | Genere un GeoPackage conforme au geostandard **StaR-Eau V2024** (CNIG / ASTEE). Menu *Sorties & Impression*. Voir la section dediee ci-dessous. |

### Fonds de plan

| Outil | Description |
|---|---|
| **Mise en place fond de projet** | Charge les 6 fonds de carte (BAN, Noms de rue, PCI Bati, PCI Parcelles, OSM Desature, Ortho IGN) sur l'emprise courante et configure le projet (fond blanc, SCR). |
| **BAN Adresses (vecteur)** | Charge les adresses de la BAN sur l'emprise courante. |
| **Noms de rue BD TOPO** | Charge les voies nominees de la BD TOPO sur l'emprise courante. |
| **PCI Vecteur – Parcelles & Bati** | Charge le cadastre vectoriel sur l'emprise courante. |
| **Ortho IGN (BD ORTHO nationale)** | Ajoute le flux d'orthophotographie BD ORTHO de l'IGN, disponible sur toute la France (remplace l'ancien fond regional CRAIG limite a un millesime). |
| **OSM Desature** | Ajoute un fond OpenStreetMap desature. |

---

## Interface

Les outils sont accessibles par trois chemins, qui exposent tous les memes
actions :

- la **barre d'outils** « BET Humide » ;
- le **panneau lateral** (dock), arborescence repliable par categorie ;
- le **menu** *Extensions ▸ BET Humide*, organise en sous-menus reprenant
  exactement les categories du panneau lateral : Projet, General,
  EU – Eaux Usees, EP – Eaux Pluviales, Etiquettes, Sorties & Impression,
  Fond de carte.

En tete du menu, **Afficher la barre d'outils** bascule sa visibilite. La
case est synchronisee nativement par Qt avec l'etat reel de la barre : elle
reste juste meme si l'utilisateur a ferme la barre par la croix ou par le
menu contextuel de QGIS.

En pied de menu, **A propos** ouvre un dialogue qui lit `metadata.txt` :
nom, version, auteur, description, lien vers le depot et vers le profil
LinkedIn de l'auteur. Rien n'y est duplique — la version affichee est
toujours celle du plugin installe.

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

## Import Star-DT / StaR-Elec (DT-DICT)

Star-DT est le format d'echange GML des reseaux enterres utilise pour les
**declarations de travaux** (DT-DICT). StaR-Elec en est la declinaison
electrique, dans le meme espace de noms `cnig.gouv.fr/star-dt/core`. Le meme
lecteur traite les deux.

### Selection des fichiers

Le dialogue accepte **plusieurs fichiers a la fois**, par le bouton
*Parcourir...* (selection multiple) ou par **glisser-deposer** de fichiers
`.gml` / `.xml` sur la fenetre. Les doublons sont ecartes en conservant
l'ordre de selection. Le comptage d'objets affiche est le cumul de tous les
fichiers, et l'import produit un GeoPackage unique.

### Decouverte automatique

Aucune liste de classes n'est codee en dur : **tout objet portant une
`<geometrie>` est importe**, quelle que soit sa classe. Les classes connues
(cables, fourreaux, accessoires, coffrets, poteaux, points leves) sont
proposees en premier, les autres (`Support`, `Regard`, `Jonction`,
`PosteElectrique`, `Luminaire`...) sont listees ensuite par ordre
alphabetique.

Les **attributs** sont decouverts de la meme facon, en parcourant les objets
du type : un attribut absent du fichier ne cree pas de colonne vide, un
attribut inattendu n'est pas perdu. Les references `xlink:href` sont
resolues sur leur dernier segment. Les seuls objets scindes sont les
`CableElectrique`, separes en **HTA** et **BT** selon `classeTension`.

Le systeme de coordonnees est celui declare par le `srsName` du GML, pas
celui du projet QGIS. La geometrie de sortie (point, ligne ou polygone) est
deduite des donnees, un meme type pouvant porter plusieurs geometries.

### Symbologie

Les epaisseurs de trait et les tailles de texte sont exprimees en
**millimetres** : le rendu est identique a l'ecran et a l'impression, a
toutes les echelles.

| Type | Rendu |
|---|---|
| `Cable_HTA` | rouge vif, 0,25 mm |
| `Cable_BT` | rouge sombre, 0,18 mm |
| `Cable_HTA/BT_schematique` | idem, en pointille |
| `Fourreau` | `#93120C`, 0,18 mm, tirets |
| `Accessoire` | rond orange 0,8 m |
| `Coffret` | rond orange fonce 0,6 m |
| `Poteau` | rond gris 0,5 m |
| `PointLeveOuvrageReseau` | rond bleu 0,2 m |

Les cables portent leur **classe de precision** directement sur le trait :
le trait est coupe a intervalle regulier (10 mm de plein, 10,5 mm de
coupure) et le libelle `HTA-A`, `BT-C`... est ecrit dans la coupure, en
3 mm de haut. La coupure est dimensionnee pour contenir le plus long
libelle sans le faire mordre sur le trait. Les objets ponctuels sont
etiquetes a 1 mm du symbole.

### Ecriture du GeoPackage

Un GeoPackage existant est **supprime et regenere**. Les couches du projet
qui pointaient dessus sont d'abord retirees : ecraser un GeoPackage encore
ouvert par QGIS fait planter l'application. Les couches sont ecrites en une
premiere passe, puis chargees en une seconde — garder le fichier ouvert
pendant l'ajout de tables laisse GDAL servir un catalogue perime, et les
couches suivantes semblent introuvables. Les couches importees sont
regroupees sous un groupe nomme d'apres l'identifiant du fichier.

---

## Export StaR-Eau (CNIG / ASTEE V2024)

StaR-Eau est le geostandard des reseaux enterres d'eau et d'assainissement.
Ce n'est **pas un format de fichier** mais un modele de donnees relationnel,
publie sous forme de scripts PostGIS. Le geostandard designe le **GeoPackage**
comme format d'echange a privilegier (§ 03.7.4).

L'export produit donc un `.gpkg` dont chaque couche porte le nom et les
colonnes d'une table du modele, directement injectable par `ogr2ogr` dans une
base StaR-Eau.

### Correspondance des objets

| BET Humide | Couche StaR-Eau | Schema du modele |
|---|---|---|
| Conduite | `ass_canalisation` | `stareau_ass` |
| Regard | `ass_regard` | `stareau_ass` |
| Branchement | `ass_canalisation_branchement` | `stareau_ass_brcht` |
| Tabouret | `ass_point_collecte` | `stareau_ass_brcht` |
| Point de piquage | `ass_raccord` | `stareau_ass_brcht` |

Les attributs se transposent directement : `tn` -> `z_tampon`,
`fe_radier` -> `z_radier`, `profondeur` -> `profondeur_mesure`,
`diametre` -> `diametre_equivalent`, et les fils d'eau des regards
d'extremite alimentent `altitude_fil_eau_amont` / `altitude_fil_eau_aval`.

### Topologie

Le geostandard impose une topologie noeud-arc-noeud : chaque canalisation
joint deux noeuds references par `noeudinitial` / `noeudterminal`. Cette
contrainte est **deja satisfaite nativement** — l'outil de dessin cree un
troncon a deux sommets entre deux regards, donc un troncon donne exactement
une `ass_canalisation`.

Les arcs sont **orientes dans le sens d'ecoulement** : l'amont est le fil
d'eau le plus haut, la geometrie etant inversee au besoin, car StaR-Eau
rattache `altitude_fil_eau_amont` a `noeudinitial`. Un branchement est
oriente de l'ouvrage vers le piquage, et un `ass_raccord` est cree au point
de piquage, relie a la conduite piquee par `ref_canalisation`.

### Identifiants

Le geostandard distingue deux identifiants par objet (§ 03.1) :

- la **cle technique** (`id_canalisation`, `id_noeud_reseau`), referencee par
  `noeudinitial` / `noeudterminal` / `ref_canalisation` ;
- l'**identifiant metier** (`id_ass_regard`, `id_ass_canalisation`...), prevu
  pour la lecture humaine.

La cle technique est un **UUID v5 deterministe**, derive du SIREN et de la
seule **topologie** de l'objet (code chantier, reseau, ouvrages d'extremite).
Le standard autorise explicitement les UUID et precise qu'ils *« devront etre
conserves dans le cadre d'une migration »* : un UUID aleatoire changerait a
chaque export, et le destinataire verrait un reseau entierement neuf a chaque
livraison au lieu d'une mise a jour.

Deux consequences voulues :

- reexporter le meme chantier redonne exactement les memes cles ;
- corriger un materiau, un diametre ou la date de pose ne change **pas** la
  cle technique — seul le libellé metier suit. Le destinataire voit une
  modification, et non une suppression suivie d'une creation.

L'identifiant metier, lui, est descriptif : prefixe par le code chantier et
la date de pose (ce qui evite les collisions quand l'exploitant fusionne
plusieurs chantiers, les regards `R1`, `R2` existant partout), puis le
reseau, la nature de l'objet, le materiau et le diametre, enfin les ouvrages
d'extremite.

```
100  -  20260816  -  EU  -  C  -  PVC200  -  REU05  -  REU04
 │         │          │     │       │          │        │
 │         │          │     │       │          │        └─ regard aval
 │         │          │     │       │          └────────── regard amont
 │         │          │     │       └───────────────────── materiau + DN
 │         │          │     └───────────────────────────── C / B / RC
 │         │          └─────────────────────────────────── reseau
 │         └────────────────────────────────────────────── date de pose
 └──────────────────────────────────────────────────────── code chantier
```

| Couche | Identifiant metier |
|---|---|
| `ass_regard` | `100-20260816-EU-REU05` |
| `ass_point_collecte` | `100-20260816-EU-T1` |
| `ass_canalisation` | `100-20260816-EU-C-PVC200-REU05-REU04` *(amont → aval)* |
| `ass_canalisation_branchement` | `100-20260816-EU-B-PVC160-T1` |
| `ass_raccord` | `100-20260816-EU-RC-T1` |

Le materiau apparait sous son **code StaR-Eau en majuscules** (`PVC`, `PVCA`,
`BA`, `FD`, `AMCI`...), donc identique a la valeur ecrite dans la colonne
`materiau`. Le geostandard decoupant les arcs par homogeneite de
caracteristiques, materiau et diametre sont constants sur un troncon et le
decrivent donc fidelement.

La **date de pose** est saisie en entier (jour/mois/annee) dans l'onglet
Chantier, alors que le modele ne stocke qu'une annee (`an_pose_sup`, domaine
`c_annee`) : l'annee en est deduite pour le standard, le jour ne servant
qu'aux identifiants metier.

### Dialogue d'export

Le geostandard impose une trentaine de colonnes `NOT NULL` a valeurs
controlees que le plugin ne stocke pas. Elles sont constantes a l'echelle
d'un chantier et se saisissent au moment de l'export, en cinq onglets :

| Onglet | Contenu |
|---|---|
| **Fichier** | Code chantier, SIREN du maitre d'ouvrage, type, date. Apercu du nom normalise `Stareau-fr<code>-<SIREN><type><date>.gpkg` (§ 03.7.5). |
| **Chantier** | INSEE, maitre d'ouvrage, exploitant, entreprise de pose, etat de service, classes de precision XY / Z, date de pose, annee de mise en service, origine de la donnee. |
| **Reseau** | Type de reseau EU / EP, mode de circulation, type et raison de la pose, revetement interieur, fonction des conduites et des branchements, materiau par defaut, contenu EU / EP. |
| **Ouvrages** | Regards (type, position, descente, materiau), tabourets (type de point de collecte, type d'usager, materiau), raccords (type de raccord). |
| **Controle** | Anomalies bloquantes et avertissements avant generation. Double-clic = zoom sur l'objet dans QGIS. |

Toutes les listes deroulantes sont alimentees par les **listes de valeurs
officielles** (`tools/stareau_values.py`) : produire un code invalide est
structurellement impossible. Les valeurs saisies sont memorisees et
reproposees au chantier suivant.

Le materiau, saisi en texte libre dans le plugin, est reconnu
automatiquement (`PVC` -> `pvc`, `Beton arme` -> `ba`, `Fonte ductile` ->
`fd`...) ; a defaut de correspondance, le materiau par defaut du dialogue
s'applique.

### Cas des eaux pluviales

La liste officielle `ass_contenu_canalisation` ne comporte **aucun code pour
les eaux pluviales** : elle ne decrit que des eaux usees (`eru`, `eri`,
`eaux_usees_traitee`). L'information EU / EP est en realite portee par
`type_reseau` (`assaeu` / `assaep` / `assaru`). Le dialogue laisse donc le
choix : colonne vide (semantiquement juste) ou code impose, si le
destinataire exige un import PostGIS strict ou la colonne est `NOT NULL`.

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
│   ├── coupe_tranchee_composee_dialog.py # Dessinateur de coupes de tranchees composees (EU/EP/AEP, matplotlib)
│   ├── annotation_dialog.py        # Dialogue d'annotation (texte, police, couleur, cadre, transparence)
│   ├── tableau_saisie_dialog.py    # Tableau de saisie groupee (regards/tabourets/conduites/branchements)
│   ├── chain_profile_widget.py     # Widget du profil simplifie pour l'onglet Chaine du tableau de saisie
│   ├── export_dialog.py            # Dialogue d'export combine (plan PDF/DXF + profils)
│   ├── welcome_dialog.py           # Dialogue d'accueil (nouveau / ouvrir / annuler)
│   ├── star_dt_dialog.py           # Dialogue d'import GML Star-DT / StaR-Elec (multi-fichiers + drag & drop)
│   ├── stareau_export_dialog.py    # Dialogue d'export StaR-Eau (5 onglets + controle)
│   ├── about_dialog.py             # Dialogue « A propos » (lit metadata.txt)
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
│   ├── cubature_tool.py            # Selection BFS/axe pour cubature/remblai tranchees
│   ├── calc_cubature.py            # Calcul cubature (volumes, BFS, remblai par couche)
│   ├── print_tool.py               # Impression PDF multi-feuilles
│   ├── coupe_transversale_tool.py  # Outil de trace de l'axe de coupe (EU+EP ou mono-reseau)
│   ├── annotation_tool.py          # Outil d'annotation texte (clic / ctrl+clic / ctrl+c-v)
│   ├── profil_batch.py             # Export batch profils EU/EP/groupe (ExportDialog)
│   ├── dxf_export.py               # Export DXF 2018 (pattern QgsDxfExport canonique)
│   ├── dxf_postprocess.py          # Decoration ezdxf (fond + cadre + callout etiquettes, symboles, ltscale)
│   ├── star_dt_import.py           # Import GML Star-DT / StaR-Elec (multi-fichiers, types et champs decouverts)
│   ├── stareau_values.py           # Listes de valeurs officielles StaR-Eau V2024 + materiaux partages
│   ├── stareau_export.py           # Export GeoPackage conforme StaR-Eau (UUID v5, orientation, controle)
│   ├── projet_bet.py               # Sauvegarde / chargement .bet (archive ZIP)
│   ├── graph_utils.py              # Construction graphe + BFS (partages par tous les outils BFS)
│   ├── calc_pentes.py              # Recalcul des pentes a partir des FE radier
│   ├── layer_keys.py               # Persistance des identifiants de couches dans le projet (.qgs)
│   ├── spatial_utils.py            # Recherche spatiale indexee (point/ligne les plus proches), partagee
│   ├── wfs_utils.py                 # Telechargement WFS mutualise en tache de fond (BAN/PCI/BD TOPO)
│   └── dxf_convert/                # Conversion DXF/DWG vers couches vectorielles
│       ├── ui_dialog.py            # Dialogue principal
│       ├── alg_cad_to_gis_convert.py
│       └── services/
└── icon/                           # Icones SVG de la barre d'outils
```

---

## Changelog

### 1.3

- **Export StaR-Eau (CNIG / ASTEE V2024)** : GeoPackage conforme au
  geostandard, cinq couches (`ass_canalisation`, `ass_regard`,
  `ass_canalisation_branchement`, `ass_point_collecte`, `ass_raccord`), arcs
  orientes dans le sens d'ecoulement, cles techniques UUID v5 deterministes,
  identifiants metier lisibles, nom de fichier normalise.
- Dialogue d'export en cinq onglets alimente par les listes de valeurs
  officielles, **non modal** pour permettre de corriger les anomalies dans
  QGIS, controle de conformite avec zoom sur l'objet fautif au double-clic,
  saisies memorisees d'un chantier a l'autre.
- **Import Star-DT etendu a StaR-Elec** : selection multi-fichiers et
  glisser-deposer, decouverte automatique des classes et des attributs
  presents dans le GML, cables HTA / BT separes, symbologie en millimetres,
  marqueurs de classe de precision inseres dans les coupures du trait.
- **Tableau de saisie** : cote de piquage interpolee sur la conduite mere et
  recalculee en cascade quand ses fils d'eau changent ; modes de calcul des
  branchements renommes et convention de signe alignee sur les profils, la
  cubature et le formulaire Renseigner.
- Liste des materiaux de conduite unifiee entre Configuration rapide,
  Tableau de saisie et export StaR-Eau, et separee des materiaux de remblai.
- **Interface** : menu QGIS organise en sous-menus reprenant les categories
  du panneau lateral, bascule d'affichage de la barre d'outils, dialogue
  « A propos », renommage en « BET Humide », suppression du doublon
  « Mise en place fond de projet » dans le panneau lateral.

### 1.2

- Fusion des outils Cubature et Remblai en une fenetre de resultats unique,
  colonnes de detail remblai affichables a la volee, sous-totaux par colonne.
- Onglet **Synthese des ouvrages** (PDF + Excel) groupe par materiau /
  diametre, avec comptage des regards et tabourets.
- **Tableau de saisie groupee** (Regards / Tabourets / Conduites /
  Branchements) : calcul automatique pente ou cote fil d'eau, apercu carte,
  copier-coller Excel, annulation (Ctrl+Z).
- Reseau **AEP** ajoute au dessinateur de coupe de tranchees composee.
- Annotations texte enrichies (cadre, transparence, echelle liee aux
  etiquettes, apercu sans fermer la fenetre).
- Fond Ortho 2022 (CRAIG) remplace par la **BD ORTHO IGN** nationale.
- Persistance des identifiants de couches dans le projet, mutualisation des
  recherches spatiales et des telechargements WFS.

### 1.1

- Rendu PDF parallele et annulable, fleche du nord, echelle normalisee du
  plan d'ensemble, suppression feuille par feuille.
- Index spatiaux sur tous les outils carte, ecritures attributaires batch.
- Fonds WFS (BAN / PCI / BD TOPO) charges en tache de fond sans geler QGIS,
  TLS verifie, nettoyage des temporaires.
- Correction du style bati PCI, paquet allege.

### 1.0

- Version initiale.

---

## Auteur

**Yoan Laloux** — [LinkedIn](https://www.linkedin.com/in/ylaloux/)

Developpe dans le cadre du BET Humide.
Depot : <https://github.com/Cartoyoyo/BET_humide>
Anomalies et demandes : <https://github.com/Cartoyoyo/BET_humide/issues>
