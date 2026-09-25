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
              "Coudes, tés, réductions, bouchons et raccordements ne sont pas numérotés.",
        'en': "One counter per fitting type, in path order: {prefixes}. "
              "Bends, tees, reducers, end caps and connections are not numbered.",
        'es': "Un contador por tipo de accesorio, en el orden del recorrido: {prefixes}. "
              "Codos, tes, reducciones, tapones y conexiones no se numeran.",
        'pt': "Um contador por tipo de acessório, pela ordem do percurso: {prefixes}. "
              "Curvas, tês, reduções, tampões e ligações não são numerados.",
        'de': "Ein Zähler je Armaturtyp, in Reihenfolge des Weges: {prefixes}. "
              "Bögen, T-Stücke, Reduzierungen, Endkappen und Anschlüsse werden nicht nummeriert.",
    },
    'ot_renum_aep_ligne': {
        'fr': "{type} : {nb} ({debut} → {fin})", 'en': "{type}: {nb} ({debut} → {fin})",
        'es': "{type}: {nb} ({debut} → {fin})", 'pt': "{type}: {nb} ({debut} → {fin})",
        'de': "{type}: {nb} ({debut} → {fin})",
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
