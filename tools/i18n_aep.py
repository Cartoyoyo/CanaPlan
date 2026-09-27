# tools/i18n_aep.py
"""Traductions du module AEP (eau potable), fusionnées dans i18n.TR.

Rangées à part pour que le module AEP se relise d'un bloc ; même format que
i18n.TR. Les codes de type (vanne, robinet_branchement…) sont des valeurs
normatives, jamais traduites : seules leurs étiquettes `aep_t_<code>` le sont.
"""

TR_AEP = {
    # ── Menus et panneau ────────────────────────────────────────────────
    'grp_aep': {
        'fr': "AEP – Eau Potable", 'en': "AEP – Drinking water",
        'es': "AEP – Agua potable", 'pt': "AEP – Água potável",
        'de': "AEP – Trinkwasser",
    },
    'conduite_aep': {
        'fr': "Dessiner une conduite AEP", 'en': "Draw a drinking water main",
        'es': "Dibujar una tubería AEP", 'pt': "Desenhar uma conduta AEP",
        'de': "Trinkwasserleitung zeichnen",
    },
    'branchement_aep': {
        'fr': "Dessiner un branchement AEP", 'en': "Draw a water service connection",
        'es': "Dibujar una acometida AEP", 'pt': "Desenhar um ramal AEP",
        'de': "Hausanschluss Trinkwasser zeichnen",
    },
    'appareil_aep': {
        'fr': "Poser un appareil AEP", 'en': "Place a water network fitting",
        'es': "Colocar un accesorio AEP", 'pt': "Colocar um acessório AEP",
        'de': "Armatur setzen (Trinkwasser)",
    },
    'profil_aep': {
        'fr': "Profil en long AEP", 'en': "Drinking water long profile",
        'es': "Perfil longitudinal AEP", 'pt': "Perfil longitudinal AEP",
        'de': "Längsschnitt Trinkwasser",
    },
    'coupe_aep': {
        'fr': "Coupe transversale AEP", 'en': "Drinking water cross section",
        'es': "Sección transversal AEP", 'pt': "Corte transversal AEP",
        'de': "Querschnitt Trinkwasser",
    },
    'renommer_aep': {
        'fr': "Renuméroter les appareils AEP", 'en': "Renumber water fittings",
        'es': "Renumerar los accesorios AEP", 'pt': "Renumerar os acessórios AEP",
        'de': "Armaturen neu nummerieren",
    },
    # Nom propre de l'outil : identique dans toutes les langues.
    'schemaep': {
        'fr': "SchemAEP", 'en': "SchemAEP", 'es': "SchemAEP", 'pt': "SchemAEP", 'de': "SchemAEP",
    },
    # Renseigner : TN auto d'un ouvrage
    'rens_tn_auto_tip': {
        'fr': "TN relevé sur le MNT IGN (LiDAR HD, sinon RGE ALTI) ; recalcule la profondeur ou le fil d'eau. "
              "Écrit à OK / Appliquer.",
        'en': "Ground level read from the IGN DEM (LiDAR HD, else RGE ALTI); recomputes depth or invert. "
              "Written on OK / Apply.",
        'es': 'TN medido en el MDT del IGN (LiDAR HD, si no RGE ALTI); recalcula la profundidad o la cota de solera. Se escribe con Aceptar / Aplicar.',
        'pt': 'Terreno natural lido no MDT do IGN (LiDAR HD, senão RGE ALTI); recalcula a profundidade ou a soleira. Escrito com OK / Aplicar.',
        'de': 'Geländehöhe aus dem IGN-DGM (LiDAR HD, sonst RGE ALTI); berechnet Tiefe oder Sohlhöhe neu. Wird mit OK / Anwenden geschrieben.',
    },
    'rens_tn_auto_source': {
        'fr': "TN relevé sur : {source}", 'en': "Ground level from: {source}",
        'es': 'TN medido en: {source}',
        'pt': 'Terreno natural lido em: {source}',
        'de': 'Geländehöhe aus: {source}',
    },
    'rens_tn_auto_echec': {
        'fr': "Aucun MNT n'a répondu pour ce point (connexion, ou hors couverture IGN).",
        'en': "No DEM answered for this point (connection, or outside IGN coverage).",
        'es': 'Ningún MDT ha respondido para este punto (conexión, o fuera de la cobertura del IGN).',
        'pt': 'Nenhum MDT respondeu para este ponto (ligação, ou fora da cobertura do IGN).',
        'de': 'Kein DGM hat für diesen Punkt geantwortet (Verbindung, oder außerhalb der IGN-Abdeckung).',
    },
    # Gestion des étiquettes : regards de comptage AEP
    'ea_regards_cpt': {
        'fr': "Regards", 'en': "Meter pits",
        'es': 'Arquetas',
        'pt': 'Caixas',
        'de': 'Schächte',
    },
    'ea_regards_cpt_tip': {
        'fr': "Étiquettes des regards de comptage (compteurs de type « regard compteur »)",
        'en': "Labels of meter pits (meters of type “meter pit”)",
        'es': 'Etiquetas de las arquetas de contador (contadores de tipo «arqueta de contador»)',
        'pt': 'Etiquetas das caixas de contador (contadores do tipo «caixa de contador»)',
        'de': 'Beschriftungen der Zählerschächte (Zähler vom Typ „Zählerschacht“)',
    },
    # Renseigner un nœud AEP : bouton SchemAEP
    'rens_schemaep_tip': {
        'fr': "Enregistre ce formulaire et dessine le schéma de pièces de ce nœud (SchemAEP)",
        'en': "Saves this form and draws the fittings diagram of this node (SchemAEP)",
        'es': 'Guarda este formulario y dibuja el esquema de piezas de este nodo (SchemAEP)',
        'pt': 'Guarda este formulário e desenha o esquema de peças deste nó (SchemAEP)',
        'de': 'Speichert dieses Formular und zeichnet das Formstückschema dieses Knotens (SchemAEP)',
    },
    'rens_schemaep_tip_existe': {
        'fr': "Enregistre ce formulaire et ouvre le schéma de pièces de ce nœud (SchemAEP)",
        'en': "Saves this form and opens the fittings diagram of this node (SchemAEP)",
        'es': 'Guarda este formulario y abre el esquema de piezas de este nodo (SchemAEP)',
        'pt': 'Guarda este formulário e abre o esquema de peças deste nó (SchemAEP)',
        'de': 'Speichert dieses Formular und öffnet das Formstückschema dieses Knotens (SchemAEP)',
    },
    # Export des schémas de nœuds
    'exp_schemas_titre': {
        'fr': "Schémas de nœuds AEP ({n})", 'en': "Water node diagrams ({n})",
        'es': 'Esquemas de nodos AEP ({n})',
        'pt': 'Esquemas de nós AEP ({n})',
        'de': 'Trinkwasser-Knotenschemata ({n})',
    },
    'exp_schemas_pdf': {
        'fr': "Pages PDF (6 schémas par page A4)", 'en': "PDF pages (6 diagrams per A4 page)",
        'es': 'Páginas PDF (6 esquemas por página A4)',
        'pt': 'Páginas PDF (6 esquemas por página A4)',
        'de': 'PDF-Seiten (6 Schemata je A4-Seite)',
    },
    'exp_schemas_pdf_note': {
        'fr': "Grille de 6 schémas par page A4, puis la nomenclature de chaque nœud.",
        'en': "Grid of 6 diagrams per A4 page, then the bill of materials of each node.",
        'es': 'Cuadrícula de 6 esquemas por página A4 y, a continuación, la lista de materiales de cada nodo.',
        'pt': 'Grelha de 6 esquemas por página A4 e, a seguir, a lista de materiais de cada nó.',
        'de': 'Raster mit 6 Schemata je A4-Seite, danach die Stückliste jedes Knotens.',
    },
    'exp_schemas_svg': {
        'fr': "Fichiers SVG", 'en': "SVG files",
        'es': 'Archivos SVG',
        'pt': 'Ficheiros SVG',
        'de': 'SVG-Dateien',
    },
    'msg_schemas_pdf': {
        'fr': "Schémas de nœuds AEP : {nb} schéma(s) sur {pages} page(s) (schemas_aep.pdf)",
        'en': "Water node diagrams: {nb} diagram(s) on {pages} page(s) (schemas_aep.pdf)",
        'es': 'Esquemas de nodos AEP: {nb} esquema(s) en {pages} página(s) (schemas_aep.pdf)',
        'pt': 'Esquemas de nós AEP: {nb} esquema(s) em {pages} página(s) (schemas_aep.pdf)',
        'de': 'Trinkwasser-Knotenschemata: {nb} Schema(ta) auf {pages} Seite(n) (schemas_aep.pdf)',
    },
    'msg_schemas_svg': {
        'fr': "Schémas de nœuds AEP : {nb} fichier(s) SVG (dossier schemas_aep)",
        'en': "Water node diagrams: {nb} SVG file(s) (schemas_aep folder)",
        'es': 'Esquemas de nodos AEP: {nb} archivo(s) SVG (carpeta schemas_aep)',
        'pt': 'Esquemas de nós AEP: {nb} ficheiro(s) SVG (pasta schemas_aep)',
        'de': 'Trinkwasser-Knotenschemata: {nb} SVG-Datei(en) (Ordner schemas_aep)',
    },
    'msg_schemas_erreur': {
        'fr': "Schémas de nœuds AEP : échec de l’export ({erreur})",
        'en': "Water node diagrams: export failed ({erreur})",
        'es': 'Esquemas de nodos AEP: fallo de la exportación ({erreur})',
        'pt': 'Esquemas de nós AEP: falha na exportação ({erreur})',
        'de': 'Trinkwasser-Knotenschemata: Export fehlgeschlagen ({erreur})',
    },
    'exp_schemas_svg_note': {
        'fr': "Un fichier SVG par nœud, dans le sous-dossier « schemas_aep ».",
        'en': "One SVG file per node, in the “schemas_aep” sub-folder.",
        'es': 'Un archivo SVG por nodo, en la subcarpeta «schemas_aep».',
        'pt': 'Um ficheiro SVG por nó, na subpasta «schemas_aep».',
        'de': 'Eine SVG-Datei je Knoten, im Unterordner „schemas_aep“.',
    },
    'ot_aide_appareil_aep': {
        'fr': "Clic sur un nœud : choisir son type. Clic sur une conduite : "
              "insérer un appareil (la conduite est coupée). Échap : quitter.",
        'en': "Click a node: choose its type. Click a main: insert a fitting "
              "(the main is split). Esc: exit.",
        'es': "Clic en un nodo: elegir su tipo. Clic en una tubería: insertar "
              "un accesorio (la tubería se corta). Esc: salir.",
        'pt': "Clique num nó: escolher o tipo. Clique numa conduta: inserir um "
              "acessório (a conduta é cortada). Esc: sair.",
        'de': "Klick auf einen Knoten: Typ wählen. Klick auf eine Leitung: "
              "Armatur einfügen (die Leitung wird geteilt). Esc: beenden.",
    },
    'aep_muet': {
        'fr': "non dessiné", 'en': "not drawn", 'es': "no dibujado",
        'pt': "não desenhado", 'de': "nicht dargestellt",
    },

    # ── Types de nœuds et de terminaux ──────────────────────────────────
    'aep_t_vanne': {
        'fr': "Vanne", 'en': "Valve", 'es': "Válvula", 'pt': "Válvula",
        'de': "Schieber",
    },
    'aep_t_robinet_branchement': {
        'fr': "Robinet de branchement", 'en': "Service tapping valve",
        'es': "Llave de acometida", 'pt': "Torneira de ramal",
        'de': "Anbohrarmatur",
    },
    'aep_t_ventouse': {
        'fr': "Ventouse", 'en': "Air valve", 'es': "Ventosa", 'pt': "Ventosa",
        'de': "Be- und Entlüfter",
    },
    'aep_t_vidange': {
        'fr': "Vidange", 'en': "Drain valve", 'es': "Desagüe", 'pt': "Descarga",
        'de': "Entleerung",
    },
    'aep_t_poteau_incendie': {
        'fr': "Poteau incendie", 'en': "Fire hydrant (pillar)",
        'es': "Hidrante de columna", 'pt': "Marco de incêndio",
        'de': "Überflurhydrant",
    },
    'aep_t_bouche_incendie': {
        'fr': "Bouche incendie", 'en': "Fire hydrant (underground)",
        'es': "Boca de incendio", 'pt': "Boca de incêndio",
        'de': "Unterflurhydrant",
    },
    'aep_t_reducteur_pression': {
        'fr': "Réducteur de pression", 'en': "Pressure reducing valve",
        'es': "Reductor de presión", 'pt': "Redutor de pressão",
        'de': "Druckminderer",
    },
    'aep_t_compteur': {
        'fr': "Compteur", 'en': "Meter", 'es': "Contador", 'pt': "Contador",
        'de': "Wasserzähler",
    },
    'aep_t_raccordement_existant': {
        'fr': "Raccordement sur existant", 'en': "Connection to existing main",
        'es': "Conexión a red existente", 'pt': "Ligação à rede existente",
        'de': "Anschluss an Bestand",
    },
    'aep_t_te': {
        'fr': "Té", 'en': "Tee", 'es': "Te", 'pt': "Tê", 'de': "T-Stück",
    },
    'aep_t_reducteur_dn': {
        'fr': "Réduction de diamètre", 'en': "Reducer", 'es': "Reducción",
        'pt': "Redução", 'de': "Reduzierstück",
    },
    'aep_t_coude': {
        'fr': "Coude", 'en': "Bend", 'es': "Codo", 'pt': "Curva",
        'de': "Bogen",
    },
    'aep_t_bouchon': {
        'fr': "Bouchon", 'en': "End cap", 'es': "Tapón", 'pt': "Tampão",
        'de': "Endkappe",
    },
    'aep_t_regard_compteur': {
        'fr': "Regard compteur", 'en': "Meter box", 'es': "Arqueta de contador",
        'pt': "Caixa de contador", 'de': "Zählerschacht",
    },
    'aep_t_extremite_libre': {
        'fr': "Extrémité libre (attente)", 'en': "Open end (stub)",
        'es': "Extremo libre (espera)", 'pt': "Extremidade livre (espera)",
        'de': "Freies Ende (Anschlussstutzen)",
    },

    # ── Renumérotation ──────────────────────────────────────────────────
    'ot_lbl_depart_aep': {
        'fr': "Premier numéro de chaque type :", 'en': "First number of each type:",
        'es': "Primer número de cada tipo:", 'pt': "Primeiro número de cada tipo:",
        'de': "Erste Nummer je Typ:",
    },
    'ot_renum_aep_note': {
        'fr': "Un compteur par type d'appareil, dans l'ordre du chemin : {prefixes}. "
              "Chaque regard compteur prend le numéro du robinet de son branchement (RB05 → RC05). "
              "Coudes, tés, réductions, bouchons, raccordements et extrémités libres ne sont pas numérotés.",
        'en': "One counter per fitting type, in path order: {prefixes}. "
              "Each meter chamber takes the number of its service valve (RB05 → RC05). "
              "Bends, tees, reducers, end caps, connections and free ends are not numbered.",
        'es': "Un contador por tipo de accesorio, en el orden del recorrido: {prefixes}. "
              "Cada arqueta de contador toma el número de la llave de su acometida (RB05 → RC05). "
              "Codos, tes, reducciones, tapones, conexiones y extremos libres no se numeran.",
        'pt': "Um contador por tipo de acessório, pela ordem do percurso: {prefixes}. "
              "Cada caixa de contador recebe o número da torneira do seu ramal (RB05 → RC05). "
              "Curvas, tês, reduções, tampões, ligações e extremidades livres não são numerados.",
        'de': "Ein Zähler je Armaturtyp, in Reihenfolge des Weges: {prefixes}. "
              "Jeder Zählerschacht erhält die Nummer des Ventils seines Anschlusses (RB05 → RC05). "
              "Bögen, T-Stücke, Reduzierungen, Endkappen, Anschlüsse und freie Enden werden nicht nummeriert.",
    },
    'ot_renum_aep_ligne': {
        'fr': "{type} : {nb} ({debut} → {fin})", 'en': "{type}: {nb} ({debut} → {fin})",
        'es': "{type}: {nb} ({debut} → {fin})", 'pt': "{type}: {nb} ({debut} → {fin})",
        'de': "{type}: {nb} ({debut} → {fin})",
    },
    'ot_renum_aep_rc': {
        'fr': "{type} : {nb} (numéro du robinet : RB05 → RC05)",
        'en': "{type}: {nb} (valve number: RB05 → RC05)",
        'es': "{type}: {nb} (número de la llave: RB05 → RC05)",
        'pt': "{type}: {nb} (número da torneira: RB05 → RC05)",
        'de': "{type}: {nb} (Nummer des Ventils: RB05 → RC05)",
    },
    'ot_renum_aep_aucun': {
        'fr': "Aucun appareil numérotable sur ce chemin.",
        'en': "No numberable fitting on this path.",
        'es': "Ningún accesorio numerable en este recorrido.",
        'pt': "Nenhum acessório numerável neste percurso.",
        'de': "Keine nummerierbare Armatur auf diesem Weg.",
    },

    # ── Tableau de saisie ───────────────────────────────────────────────
    'ts_type_tip': {
        'fr': "Saisir un type : code, libellé ou préfixe (V, RB, PI…).",
        'en': "Enter a type: code, label or prefix (V, RB, PI…).",
        'es': "Introducir un tipo: código, etiqueta o prefijo (V, RB, PI…).",
        'pt': "Introduzir um tipo: código, designação ou prefixo (V, RB, PI…).",
        'de': "Typ eingeben: Code, Bezeichnung oder Präfix (V, RB, PI…).",
    },
    'ts_type_inconnu': {
        'fr': "Type « {saisie} » inconnu. Types admis : {types}.",
        'en': "Unknown type “{saisie}”. Allowed types: {types}.",
        'es': "Tipo «{saisie}» desconocido. Tipos admitidos: {types}.",
        'pt': "Tipo «{saisie}» desconhecido. Tipos admitidos: {types}.",
        'de': "Unbekannter Typ „{saisie}“. Zulässige Typen: {types}.",
    },
    'ts_couverture_btn': {
        'fr': "Couverture → FE", 'en': "Cover → invert", 'es': "Recubrimiento → cota",
        'pt': "Recobrimento → soleira", 'de': "Überdeckung → Sohle",
    },
    'ts_couverture_tip': {
        'fr': "AEP : fil d'eau = TN − couverture − DN, profondeur = TN − fil d'eau, "
              "pour tous les nœuds et terminaux qui ont un TN.",
        'en': "Water: invert = ground − cover − DN, depth = ground − invert, "
              "for every node and end point with a ground level.",
        'es': "AEP: cota = terreno − recubrimiento − DN, profundidad = terreno − cota, "
              "para todos los nodos y extremos con cota de terreno.",
        'pt': "AEP: soleira = terreno − recobrimento − DN, profundidade = terreno − soleira, "
              "para todos os nós e extremidades com cota de terreno.",
        'de': "Trinkwasser: Sohle = Gelände − Überdeckung − DN, Tiefe = Gelände − Sohle, "
              "für alle Knoten und Endpunkte mit Geländehöhe.",
    },
    'ts_couverture_q': {
        'fr': "Couverture au-dessus de la conduite (m) :",
        'en': "Cover above the pipe (m):",
        'es': "Recubrimiento sobre la tubería (m):",
        'pt': "Recobrimento sobre a conduta (m):",
        'de': "Überdeckung über der Leitung (m):",
    },
    'ts_couverture_ok': {
        'fr': "Couverture {cv} m appliquée à {nb} ouvrage(s) ; {sans_tn} sans TN laissé(s) tel(s) quel(s).",
        'en': "Cover {cv} m applied to {nb} item(s); {sans_tn} without ground level left unchanged.",
        'es': "Recubrimiento {cv} m aplicado a {nb} elemento(s); {sans_tn} sin cota de terreno sin cambios.",
        'pt': "Recobrimento {cv} m aplicado a {nb} elemento(s); {sans_tn} sem cota de terreno inalterado(s).",
        'de': "Überdeckung {cv} m auf {nb} Objekt(e) angewendet; {sans_tn} ohne Geländehöhe unverändert.",
    },

    # ── Configuration rapide ────────────────────────────────────────────
    'qc_couverture_aep': {
        'fr': "Couverture de la conduite :", 'en': "Pipe cover:",
        'es': "Recubrimiento de la tubería:", 'pt': "Recobrimento da conduta:",
        'de': "Rohrüberdeckung:",
    },
    'qc_terminal_aep': {
        'fr': "Fin de branchement par défaut :", 'en': "Default connection end:",
        'es': "Extremo de acometida por defecto:", 'pt': "Fim de ramal por defeito:",
        'de': "Standard-Anschlussende:",
    },
    'qc_affleurants_aep': {
        'fr': "Afficher les bouches à clé (vannes, robinets)",
        'en': "Show valve boxes (valves, tapping valves)",
        'es': "Mostrar las arquetas de llave (válvulas, llaves)",
        'pt': "Mostrar as caixas de manobra (válvulas, torneiras)",
        'de': "Straßenkappen anzeigen (Schieber, Anbohrarmaturen)",
    },
    'qc_affleurants_aep_tip': {
        'fr': "Option de rendu du projet ouvert : rien n'est écrit dans les données.",
        'en': "Display option of the open project: nothing is written to the data.",
        'es': "Opción de visualización del proyecto abierto: no se escribe nada en los datos.",
        'pt': "Opção de visualização do projeto aberto: nada é escrito nos dados.",
        'de': "Darstellungsoption des geöffneten Projekts: in die Daten wird nichts geschrieben.",
    },
    'qc_conduite_aep': {
        'fr': "Conduite AEP", 'en': "Water main", 'es': "Tubería AEP",
        'pt': "Conduta AEP", 'de': "Trinkwasserleitung",
    },
    'qc_branchement_aep': {
        'fr': "Branchement AEP", 'en': "Water service connection",
        'es': "Acometida AEP", 'pt': "Ramal AEP", 'de': "Trinkwasseranschluss",
    },
    'ea_robinets': {
        'fr': "Robinets", 'en': "Valves", 'es': "Llaves",
        'pt': "Torneiras", 'de': "Absperrer",
    },
    'ea_robinets_tip': {
        'fr': "Étiquettes des robinets de branchement AEP",
        'en': "Labels of the drinking water service valves",
        'es': "Etiquetas de las llaves de acometida AEP",
        'pt': "Etiquetas das torneiras de ramal AEP",
        'de': "Beschriftung der Trinkwasser-Hausanschlussabsperrer",
    },
    'qc_branch_court_aep': {
        'fr': "Branch. AEP", 'en': "Water conn.", 'es': "Acom. AEP",
        'pt': "Ramal AEP", 'de': "TW-Anschl.",
    },
    'qc_larg_cond_aep': {
        'fr': "Largeur tranchée Conduite AEP :",
        'en': "Trench width — water main:",
        'es': "Ancho de zanja — tubería de agua potable:",
        'pt': "Largura da vala — conduta de água potável:",
        'de': "Grabenbreite — Trinkwasserleitung:",
    },
    'qc_larg_branch_aep': {
        'fr': "Largeur tranchée Branchement AEP :",
        'en': "Trench width — water service connection:",
        'es': "Ancho de zanja — acometida de agua potable:",
        'pt': "Largura da vala — ramal de água potável:",
        'de': "Grabenbreite — Trinkwasseranschluss:",
    },
    'cb_aep_seul': {
        'fr': "AEP seulement", 'en': "AEP only", 'es': "Solo AEP",
        'pt': "Apenas AEP", 'de': "Nur AEP",
    },
    'pg_titre_reseaux': {
        'fr': "Profil groupé {reseaux}", 'en': "Combined {reseaux} profile",
        'es': "Perfil agrupado {reseaux}", 'pt': "Perfil agrupado {reseaux}",
        'de': "Kombiniertes {reseaux} Profil",
    },
    # ── Vocabulaire : nœuds et compteurs au lieu de regards et tabourets ─
    'aep_col_noeud': {
        'fr': "Nœud", 'en': "Node", 'es': "Nodo", 'pt': "Nó", 'de': "Knoten",
    },
    'aep_qc_noeuds': {
        'fr': "Nœuds", 'en': "Nodes", 'es': "Nodos", 'pt': "Nós", 'de': "Knoten",
    },
    'aep_rap_total_noeuds': {
        'fr': "Total nœuds", 'en': "Total nodes", 'es': "Total nodos",
        'pt': "Total nós", 'de': "Summe Knoten",
    },
    'aep_col_compteur': {
        'fr': "Compteur", 'en': "Meter", 'es': "Contador", 'pt': "Contador",
        'de': "Wasserzähler",
    },
    'aep_qc_compteurs': {
        'fr': "Compteurs", 'en': "Meters", 'es': "Contadores", 'pt': "Contadores",
        'de': "Wasserzähler",
    },
    'aep_rap_total_compteurs': {
        'fr': "Total compteurs", 'en': "Total meters", 'es': "Total contadores",
        'pt': "Total contadores", 'de': "Summe Wasserzähler",
    },
    'aep_col_fe_compteur': {
        'fr': "FE compteur (m NGF)", 'en': "Meter invert (m)",
        'es': "Cota contador (m)", 'pt': "Soleira do contador (m)",
        'de': "Sohle Wasserzähler (m)",
    },
    # ── Export StaR-Eau ─────────────────────────────────────────────────
    'se_aep_titre': {
        'fr': "Eau potable (fichier de type EAU)", 'en': "Drinking water (EAU file type)",
        'es': "Agua potable (archivo de tipo EAU)", 'pt': "Água potável (ficheiro tipo EAU)",
        'de': "Trinkwasser (Dateityp EAU)",
    },
    'se_aep_contenu': {
        'fr': "Type d'eau :", 'en': "Water type:", 'es': "Tipo de agua:",
        'pt': "Tipo de água:", 'de': "Wasserart:",
    },
    'se_aep_pression': {
        'fr': "Type de pression :", 'en': "Pressure type:", 'es': "Tipo de presión:",
        'pt': "Tipo de pressão:", 'de': "Druckart:",
    },
    'se_aep_type_vanne': {
        'fr': "Type des vannes :", 'en': "Valve type:", 'es': "Tipo de válvulas:",
        'pt': "Tipo de válvulas:", 'de': "Schieberart:",
    },
    'se_aep_fonction_vanne': {
        'fr': "Fonction des vannes :", 'en': "Valve function:",
        'es': "Función de las válvulas:", 'pt': "Função das válvulas:",
        'de': "Schieberfunktion:",
    },
    'se_aep_sens': {
        'fr': "Sens de fermeture :", 'en': "Closing direction:",
        'es': "Sentido de cierre:", 'pt': "Sentido de fecho:", 'de': "Schließrichtung:",
    },
    'se_aep_livraison': {
        'fr': "Compteurs (point de livraison) :", 'en': "Meters (delivery point):",
        'es': "Contadores (punto de entrega):", 'pt': "Contadores (ponto de entrega):",
        'de': "Wasserzähler (Übergabepunkt):",
    },
    'se_aep_aide': {
        'fr': "Choisir « EAU » comme type de fichier (onglet Fichier) pour exporter "
              "le réseau AEP : conduites, vannes, appareils, pièces, raccords, "
              "branchements et points de livraison. Poteaux et bouches incendie "
              "sortent en points de livraison « défense incendie » (PI / BI en "
              "référence externe).",
        'en': "Choose “EAU” as the file type (File tab) to export the drinking water "
              "network: mains, valves, fittings, pieces, connections, service pipes "
              "and delivery points. Fire hydrants are exported as “fire defence” "
              "delivery points (PI / BI as external reference).",
        'es': "Elegir «EAU» como tipo de archivo (pestaña Archivo) para exportar la "
              "red de agua potable. Los hidrantes se exportan como puntos de entrega "
              "«defensa contra incendios» (PI / BI en referencia externa).",
        'pt': "Escolher «EAU» como tipo de ficheiro (separador Ficheiro) para exportar "
              "a rede de água potável. Os marcos e bocas de incêndio saem como pontos "
              "de entrega «defesa contra incêndios» (PI / BI em referência externa).",
        'de': "„EAU“ als Dateityp wählen (Reiter Datei), um das Trinkwassernetz zu "
              "exportieren. Hydranten werden als Übergabepunkte „Brandschutz“ "
              "exportiert (PI / BI als externe Referenz).",
    },
    'ct_aep_relatif': {
        'fr': "AEP sans TN : coupe en cotes relatives (terrain = 0, conduite sous "
              "{cv} m de couverture).",
        'en': "Water main without ground level: section in relative levels "
              "(ground = 0, pipe under {cv} m of cover).",
        'es': "AEP sin cota de terreno: sección en cotas relativas (terreno = 0, "
              "tubería bajo {cv} m de recubrimiento).",
        'pt': "AEP sem cota de terreno: corte em cotas relativas (terreno = 0, "
              "conduta sob {cv} m de recobrimento).",
        'de': "Trinkwasser ohne Geländehöhe: Schnitt in relativen Höhen "
              "(Gelände = 0, Leitung unter {cv} m Überdeckung).",
    },
    'rap_eau_potable': {
        'fr': "Eau Potable", 'en': "Drinking water", 'es': "Agua potable",
        'pt': "Água potável", 'de': "Trinkwasser",
    },
    # ── Tableau de saisie : résumé ──────────────────────────────────────
    'aep_ts_resume': {
        'fr': "{regards} nœuds · {tabourets} compteurs · {conduites} conduites "
              "· {branchements} branchements — réseau {reseau} — {manquantes} "
              "valeur(s) manquante(s)",
        'en': "{regards} nodes · {tabourets} meters · {conduites} mains · "
              "{branchements} service connections — {reseau} network — "
              "{manquantes} missing value(s)",
        'es': "{regards} nodos · {tabourets} contadores · {conduites} tuberías · "
              "{branchements} acometidas — red {reseau} — {manquantes} "
              "valor(es) ausente(s)",
        'pt': "{regards} nós · {tabourets} contadores · {conduites} condutas · "
              "{branchements} ramais — rede {reseau} — {manquantes} "
              "valor(es) em falta",
        'de': "{regards} Knoten · {tabourets} Wasserzähler · {conduites} Leitungen · "
              "{branchements} Hausanschlüsse — Netz {reseau} — {manquantes} "
              "fehlende(r) Wert(e)",
    },
}
