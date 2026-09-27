# tools/i18n_schemaep.py
"""Traductions de l'interface SchemAEP (fenêtre, liste des nœuds, panneau,
sorties imprimées), fusionnées dans i18n.TR.

Le catalogue (noms de pièces, familles, extrémités, désignations de
nomenclature, messages de contrôle) reste en français : ce sont des gabarits
de phrases métier partagés avec le format .json de la page SchemAEP.

Deux conventions de paramètres, qu'une langue ne doit pas mélanger :
- clés à « %s / %d / %.1f » : appelées par i18n.tr(cle) % valeurs, mêmes
  spécificateurs dans le même ordre dans les cinq langues ;
- clés à « {n} » (pluriels en _1 / _n) : appelées par i18n.tr(cle, n=…).
"""

TR_SCHEMAEP = {
    # ── Fenêtre : palette et barre d'outils ─────────────────────────────
    'se_rechercher_piece': {
        'fr': "Rechercher une pièce…", 'en': "Search for a fitting…",
        'es': "Buscar una pieza…", 'pt': "Procurar uma peça…", 'de': "Formstück suchen…",
    },
    'se_range_noeud': {
        'fr': "Schéma rangé sur le nœud %s. Pensez à enregistrer le projet CanaPlan.",
        'en': "Diagram stored on node %s. Remember to save the CanaPlan project.",
        'es': "Esquema guardado en el nodo %s. Recuerde guardar el proyecto CanaPlan.",
        'pt': "Esquema guardado no nó %s. Lembre-se de guardar o projeto CanaPlan.",
        'de': "Schema am Knoten %s abgelegt. Denken Sie daran, das CanaPlan-Projekt zu speichern.",
    },
    'se_modifie_enregistrer': {
        'fr': "Le schéma du nœud %s a été modifié. L’enregistrer dans le projet ?",
        'en': "The diagram of node %s has been modified. Save it in the project?",
        'es': "El esquema del nodo %s ha sido modificado. ¿Guardarlo en el proyecto?",
        'pt': "O esquema do nó %s foi modificado. Guardá-lo no projeto?",
        'de': "Das Schema des Knotens %s wurde geändert. Im Projekt speichern?",
    },
    'se_nom_projet': {
        'fr': "Nom du projet", 'en': "Project name", 'es': "Nombre del proyecto",
        'pt': "Nome do projeto", 'de': "Projektname",
    },
    'se_enr_projet': {
        'fr': "Enregistrer dans le projet", 'en': "Save in project", 'es': "Guardar en el proyecto",
        'pt': "Guardar no projeto", 'de': "Im Projekt speichern",
    },
    'se_enr_projet_tip': {
        'fr': "Ranger ce schéma sur le nœud %s (enregistré avec le projet CanaPlan)",
        'en': "Store this diagram on node %s (saved with the CanaPlan project)",
        'es': "Guardar este esquema en el nodo %s (se guarda con el proyecto CanaPlan)",
        'pt': "Guardar este esquema no nó %s (guardado com o projeto CanaPlan)",
        'de': "Dieses Schema am Knoten %s ablegen (wird mit dem CanaPlan-Projekt gespeichert)",
    },
    'se_nouveau': {'fr': "Nouveau", 'en': "New", 'es': "Nuevo", 'pt': "Novo", 'de': "Neu"},
    'se_annuler': {'fr': "Annuler", 'en': "Undo", 'es': "Deshacer", 'pt': "Anular", 'de': "Rückgängig"},
    'se_annuler_tip': {
        'fr': "Annuler la dernière modification (Ctrl+Z)", 'en': "Undo the last change (Ctrl+Z)",
        'es': "Deshacer el último cambio (Ctrl+Z)", 'pt': "Anular a última alteração (Ctrl+Z)",
        'de': "Letzte Änderung rückgängig machen (Strg+Z)",
    },
    'se_effacer_tout': {
        'fr': "Effacer tout", 'en': "Clear all", 'es': "Borrar todo", 'pt': "Apagar tudo",
        'de': "Alles löschen",
    },
    'se_effacer_tout_tip': {
        'fr': "Retirer toutes les pièces du schéma (le nom et le nœud rattaché restent ; Ctrl+Z pour revenir)",
        'en': "Remove all fittings from the diagram (the name and linked node are kept; Ctrl+Z to undo)",
        'es': "Quitar todas las piezas del esquema (el nombre y el nodo vinculado se conservan; "
              "Ctrl+Z para deshacer)",
        'pt': "Retirar todas as peças do esquema (o nome e o nó associado mantêm-se; Ctrl+Z para anular)",
        'de': "Alle Formstücke aus dem Schema entfernen (Name und verknüpfter Knoten bleiben; "
              "Strg+Z zum Rückgängigmachen)",
    },
    'se_copier': {'fr': "Copier", 'en': "Copy", 'es': "Copiar", 'pt': "Copiar", 'de': "Kopieren"},
    'se_copier_tip': {
        'fr': "Copier tout le schéma, pour le coller sur un autre nœud (ici ou depuis la liste des nœuds)",
        'en': "Copy the whole diagram, to paste it onto another node (here or from the node list)",
        'es': "Copiar todo el esquema para pegarlo en otro nodo (aquí o desde la lista de nodos)",
        'pt': "Copiar todo o esquema para o colar noutro nó (aqui ou a partir da lista de nós)",
        'de': "Ganzes Schema kopieren, um es in einen anderen Knoten einzufügen (hier oder aus der Knotenliste)",
    },
    'se_coller': {'fr': "Coller", 'en': "Paste", 'es': "Pegar", 'pt': "Colar", 'de': "Einfügen"},
    'se_coller_tip': {
        'fr': "Remplacer ce schéma par le schéma copié (Ctrl+Z pour revenir)",
        'en': "Replace this diagram with the copied one (Ctrl+Z to undo)",
        'es': "Reemplazar este esquema por el copiado (Ctrl+Z para deshacer)",
        'pt': "Substituir este esquema pelo copiado (Ctrl+Z para anular)",
        'de': "Dieses Schema durch das kopierte ersetzen (Strg+Z zum Rückgängigmachen)",
    },
    'se_ouvrir': {'fr': "Ouvrir…", 'en': "Open…", 'es': "Abrir…", 'pt': "Abrir…", 'de': "Öffnen…"},
    'se_enregistrer': {
        'fr': "Enregistrer", 'en': "Save", 'es': "Guardar", 'pt': "Guardar", 'de': "Speichern",
    },
    'se_export_svg': {
        'fr': "Export SVG", 'en': "Export SVG", 'es': "Exportar SVG", 'pt': "Exportar SVG",
        'de': "SVG-Export",
    },
    'se_export_svg_tip': {
        'fr': "Enregistrer le dessin en SVG", 'en': "Save the drawing as SVG",
        'es': "Guardar el dibujo en SVG", 'pt': "Guardar o desenho em SVG",
        'de': "Zeichnung als SVG speichern",
    },
    'se_nomenc_csv': {
        'fr': "Nomenclature CSV", 'en': "Bill of materials CSV", 'es': "Lista de materiales CSV",
        'pt': "Lista de materiais CSV", 'de': "Stückliste CSV",
    },
    'se_nomenc_csv_tip': {
        'fr': "Enregistrer la nomenclature (tableur)", 'en': "Save the bill of materials (spreadsheet)",
        'es': "Guardar la lista de materiales (hoja de cálculo)",
        'pt': "Guardar a lista de materiais (folha de cálculo)", 'de': "Stückliste speichern (Tabelle)",
    },
    'se_imprimer': {
        'fr': "Imprimer", 'en': "Print", 'es': "Imprimir", 'pt': "Imprimir", 'de': "Drucken",
    },
    'se_imprimer_tip': {
        'fr': "Imprimer le schéma et sa nomenclature", 'en': "Print the diagram and its bill of materials",
        'es': "Imprimir el esquema y su lista de materiales",
        'pt': "Imprimir o esquema e a sua lista de materiais", 'de': "Schema und Stückliste drucken",
    },
    'se_schema_favori': {
        'fr': "★ Schéma en favori", 'en': "★ Diagram to favourites", 'es': "★ Esquema a favoritos",
        'pt': "★ Esquema nos favoritos", 'de': "★ Schema als Favorit",
    },
    'se_schema_favori_tip': {
        'fr': "Enregistrer tout le schéma en cours dans les Favoris, pour le reposer dans un autre projet",
        'en': "Save the whole current diagram to Favourites, to reuse it in another project",
        'es': "Guardar todo el esquema actual en Favoritos, para reutilizarlo en otro proyecto",
        'pt': "Guardar todo o esquema atual nos Favoritos, para o reutilizar noutro projeto",
        'de': "Das ganze aktuelle Schema in den Favoriten speichern, um es in einem anderen Projekt "
              "wiederzuverwenden",
    },
    'se_lbl_schema': {
        'fr': " Schéma : ", 'en': " Diagram: ", 'es': " Esquema: ", 'pt': " Esquema: ", 'de': " Schema: ",
    },
    'se_tourner_m90_tip': {
        'fr': "Tourner tout le schéma de 90° (sens inverse des aiguilles d’une montre)",
        'en': "Rotate the whole diagram by 90° (anticlockwise)",
        'es': "Girar todo el esquema 90° (sentido antihorario)",
        'pt': "Rodar todo o esquema 90° (sentido anti-horário)",
        'de': "Ganzes Schema um 90° drehen (gegen den Uhrzeigersinn)",
    },
    'se_tourner_p90_tip': {
        'fr': "Tourner tout le schéma de 90° (sens des aiguilles d’une montre)",
        'en': "Rotate the whole diagram by 90° (clockwise)",
        'es': "Girar todo el esquema 90° (sentido horario)",
        'pt': "Rodar todo o esquema 90° (sentido horário)",
        'de': "Ganzes Schema um 90° drehen (im Uhrzeigersinn)",
    },
    'se_tourner_180_tip': {
        'fr': "Retourner tout le schéma de 180°", 'en': "Turn the whole diagram by 180°",
        'es': "Girar todo el esquema 180°", 'pt': "Rodar todo o esquema 180°",
        'de': "Ganzes Schema um 180° drehen",
    },
    'se_etiquettes': {
        'fr': "Étiquettes", 'en': "Labels", 'es': "Etiquetas", 'pt': "Etiquetas", 'de': "Beschriftungen",
    },
    'se_etiquettes_tip': {
        'fr': "Afficher / masquer les étiquettes", 'en': "Show / hide labels",
        'es': "Mostrar / ocultar etiquetas", 'pt': "Mostrar / ocultar etiquetas",
        'de': "Beschriftungen ein-/ausblenden",
    },
    'se_recentrer': {
        'fr': "Recentrer", 'en': "Recentre", 'es': "Recentrar", 'pt': "Recentrar", 'de': "Zentrieren",
    },
    'se_titre_noeud': {
        'fr': " – nœud %s", 'en': " – node %s", 'es': " – nodo %s", 'pt': " – nó %s", 'de': " – Knoten %s",
    },
    'se_favoris': {
        'fr': "★ Favoris", 'en': "★ Favourites", 'es': "★ Favoritos", 'pt': "★ Favoritos", 'de': "★ Favoriten",
    },
    'se_retirer_favoris': {
        'fr': "Retirer des favoris", 'en': "Remove from favourites", 'es': "Quitar de favoritos",
        'pt': "Retirar dos favoritos", 'de': "Aus Favoriten entfernen",
    },
    'se_ajouter_favoris': {
        'fr': "Ajouter aux favoris", 'en': "Add to favourites", 'es': "Añadir a favoritos",
        'pt': "Adicionar aos favoritos", 'de': "Zu Favoriten hinzufügen",
    },
    'se_favoris_vide': {
        'fr': "Cliquez ☆ sur une pièce, ou « ★ Montage » sur une pièce posée.",
        'en': "Click ☆ on a fitting, or “★ Assembly” on a placed fitting.",
        'es': "Haga clic en ☆ en una pieza, o en «★ Montaje» en una pieza colocada.",
        'pt': "Clique em ☆ numa peça, ou em «★ Montagem» numa peça colocada.",
        'de': "Klicken Sie ☆ bei einem Formstück oder „★ Baugruppe“ bei einem gesetzten Formstück.",
    },
    'se_retablir': {
        'fr': "Rétablir les montages par défaut", 'en': "Restore default assemblies",
        'es': "Restablecer los montajes por defecto", 'pt': "Repor as montagens predefinidas",
        'de': "Standard-Baugruppen wiederherstellen",
    },
    'se_suppr_montage': {
        'fr': "Supprimer le montage « %s » ?", 'en': "Delete the assembly “%s”?",
        'es': "¿Eliminar el montaje «%s»?", 'pt': "Eliminar a montagem «%s»?",
        'de': "Baugruppe „%s“ löschen?",
    },
    'se_schema_vide': {
        'fr': "Le schéma est vide.", 'en': "The diagram is empty.", 'es': "El esquema está vacío.",
        'pt': "O esquema está vazio.", 'de': "Das Schema ist leer.",
    },
    'se_defaut_nom_schema': {
        'fr': "Schéma (%d pièces)", 'en': "Diagram (%d fittings)", 'es': "Esquema (%d piezas)",
        'pt': "Esquema (%d peças)", 'de': "Schema (%d Formstücke)",
    },
    'se_plus_piece_1': {
        'fr': " + {n} pièce", 'en': " + {n} fitting", 'es': " + {n} pieza", 'pt': " + {n} peça",
        'de': " + {n} Formstück",
    },
    'se_plus_piece_n': {
        'fr': " + {n} pièces", 'en': " + {n} fittings", 'es': " + {n} piezas", 'pt': " + {n} peças",
        'de': " + {n} Formstücke",
    },
    'se_nom_favori_schema': {
        'fr': "Nom du schéma à mettre en favori :", 'en': "Name of the diagram to add to favourites:",
        'es': "Nombre del esquema para favoritos:", 'pt': "Nome do esquema para os favoritos:",
        'de': "Name des Schemas für die Favoriten:",
    },
    'se_nom_montage': {
        'fr': "Nom du montage :", 'en': "Assembly name:", 'es': "Nombre del montaje:",
        'pt': "Nome da montagem:", 'de': "Name der Baugruppe:",
    },
    'se_effacer_en_cours': {
        'fr': "Effacer le schéma en cours ?", 'en': "Clear the current diagram?",
        'es': "¿Borrar el esquema actual?", 'pt': "Apagar o esquema atual?",
        'de': "Aktuelles Schema löschen?",
    },
    'se_rien_a_copier': {
        'fr': "Le schéma est vide : rien à copier.", 'en': "The diagram is empty: nothing to copy.",
        'es': "El esquema está vacío: nada que copiar.", 'pt': "O esquema está vazio: nada a copiar.",
        'de': "Das Schema ist leer: nichts zu kopieren.",
    },
    'se_schema_libre_source': {
        'fr': "schéma libre", 'en': "free diagram", 'es': "esquema libre", 'pt': "esquema livre",
        'de': "freies Schema",
    },
    'se_copie_ok': {
        'fr': "Schéma de %s copié : collez-le sur un autre nœud (bouton Coller, ou depuis la liste des nœuds).",
        'en': "Diagram of %s copied: paste it onto another node (Paste button, or from the node list).",
        'es': "Esquema de %s copiado: péguelo en otro nodo (botón Pegar o desde la lista de nodos).",
        'pt': "Esquema de %s copiado: cole-o noutro nó (botão Colar ou a partir da lista de nós).",
        'de': "Schema von %s kopiert: in einen anderen Knoten einfügen (Schaltfläche Einfügen oder aus "
              "der Knotenliste).",
    },
    'se_aucun_copie_info': {
        'fr': "Aucun schéma copié. Utilisez d’abord « Copier » sur un schéma.",
        'en': "No diagram copied. First use “Copy” on a diagram.",
        'es': "Ningún esquema copiado. Use primero «Copiar» en un esquema.",
        'pt': "Nenhum esquema copiado. Use primeiro «Copiar» num esquema.",
        'de': "Kein Schema kopiert. Verwenden Sie zuerst „Kopieren“ bei einem Schema.",
    },
    'se_remplacer_copie': {
        'fr': "Remplacer ce schéma par celui copié de %s ? (Ctrl+Z pour revenir)",
        'en': "Replace this diagram with the one copied from %s? (Ctrl+Z to undo)",
        'es': "¿Reemplazar este esquema por el copiado de %s? (Ctrl+Z para deshacer)",
        'pt': "Substituir este esquema pelo copiado de %s? (Ctrl+Z para anular)",
        'de': "Dieses Schema durch das von %s kopierte ersetzen? (Strg+Z zum Rückgängigmachen)",
    },
    'se_effacer_toutes': {
        'fr': "Effacer toutes les pièces du schéma ? (Ctrl+Z pour revenir)",
        'en': "Remove all fittings from the diagram? (Ctrl+Z to undo)",
        'es': "¿Borrar todas las piezas del esquema? (Ctrl+Z para deshacer)",
        'pt': "Apagar todas as peças do esquema? (Ctrl+Z para anular)",
        'de': "Alle Formstücke aus dem Schema löschen? (Strg+Z zum Rückgängigmachen)",
    },
    'se_ouvrir_schema': {
        'fr': "Ouvrir un schéma", 'en': "Open a diagram", 'es': "Abrir un esquema",
        'pt': "Abrir um esquema", 'de': "Schema öffnen",
    },
    'se_filtre_json': {
        'fr': "Schéma SchemAEP (*.json)", 'en': "SchemAEP diagram (*.json)",
        'es': "Esquema SchemAEP (*.json)", 'pt': "Esquema SchemAEP (*.json)",
        'de': "SchemAEP-Schema (*.json)",
    },
    'se_illisible': {
        'fr': "Fichier illisible : %s", 'en': "Unreadable file: %s", 'es': "Archivo ilegible: %s",
        'pt': "Ficheiro ilegível: %s", 'de': "Datei nicht lesbar: %s",
    },
    'se_enr_schema': {
        'fr': "Enregistrer le schéma", 'en': "Save the diagram", 'es': "Guardar el esquema",
        'pt': "Guardar o esquema", 'de': "Schema speichern",
    },
    'se_exporter_svg': {
        'fr': "Exporter en SVG", 'en': "Export as SVG", 'es': "Exportar en SVG",
        'pt': "Exportar em SVG", 'de': "Als SVG exportieren",
    },
    'se_filtre_svg': {
        'fr': "Image SVG (*.svg)", 'en': "SVG image (*.svg)", 'es': "Imagen SVG (*.svg)",
        'pt': "Imagem SVG (*.svg)", 'de': "SVG-Bild (*.svg)",
    },
    'se_filtre_csv': {
        'fr': "Tableur CSV (*.csv)", 'en': "CSV spreadsheet (*.csv)", 'es': "Hoja de cálculo CSV (*.csv)",
        'pt': "Folha de cálculo CSV (*.csv)", 'de': "CSV-Tabelle (*.csv)",
    },
    'se_noeud_titre': {
        'fr': "Nœud %s", 'en': "Node %s", 'es': "Nodo %s", 'pt': "Nó %s", 'de': "Knoten %s",
    },
    'se_schema_aep': {
        'fr': "Schéma AEP", 'en': "Water diagram", 'es': "Esquema AEP", 'pt': "Esquema AEP",
        'de': "Trinkwasserschema",
    },

    # ── Zone de dessin : aide et infobulles ─────────────────────────────
    'se_ext_libre': {
        'fr': "Extrémité libre : %s", 'en': "Free end: %s", 'es': "Extremo libre: %s",
        'pt': "Extremidade livre: %s", 'de': "Freies Ende: %s",
    },
    'se_cliquer_valider': {
        'fr': "\nCliquer pour valider ce défaut", 'en': "\nClick to accept this defect",
        'es': "\nHaga clic para validar este defecto", 'pt': "\nClique para validar este defeito",
        'de': "\nKlicken, um diesen Mangel zu bestätigen",
    },
    'se_aide_point': {
        'fr': "Point sélectionné : cliquez une pièce de la palette pour la raccorder ici.",
        'en': "Selected point: click a fitting in the palette to connect it here.",
        'es': "Punto seleccionado: haga clic en una pieza de la paleta para conectarla aquí.",
        'pt': "Ponto selecionado: clique numa peça da paleta para a ligar aqui.",
        'de': "Ausgewählter Punkt: Klicken Sie ein Formstück in der Palette an, um es hier anzuschließen.",
    },
    'se_aide_sel': {
        'fr': "Glisser : déplacer l’ensemble raccordé (Alt : pièce seule, Maj : sans grille) · "
              "R : pivoter · Suppr : supprimer · Échap : désélectionner",
        'en': "Drag: move the connected group (Alt: fitting only, Shift: no grid) · "
              "R: rotate · Del: delete · Esc: deselect",
        'es': "Arrastrar: mover el conjunto conectado (Alt: solo la pieza, Mayús: sin cuadrícula) · "
              "R: girar · Supr: eliminar · Esc: deseleccionar",
        'pt': "Arrastar: mover o conjunto ligado (Alt: só a peça, Shift: sem grelha) · "
              "R: rodar · Del: eliminar · Esc: desmarcar",
        'de': "Ziehen: verbundene Gruppe verschieben (Alt: nur Formstück, Umschalt: ohne Raster) · "
              "R: drehen · Entf: löschen · Esc: Auswahl aufheben",
    },
    'se_aide_vide': {
        'fr': "Cliquez une pièce de la palette pour commencer · points orange = extrémités libres · "
              "molette : zoom · glisser le fond : déplacer la vue",
        'en': "Click a fitting in the palette to start · orange points = free ends · "
              "wheel: zoom · drag the background: pan",
        'es': "Haga clic en una pieza de la paleta para empezar · puntos naranjas = extremos libres · "
              "rueda: zoom · arrastrar el fondo: desplazar la vista",
        'pt': "Clique numa peça da paleta para começar · pontos laranja = extremidades livres · "
              "roda: zoom · arrastar o fundo: deslocar a vista",
        'de': "Klicken Sie ein Formstück in der Palette an, um zu beginnen · orange Punkte = freie Enden · "
              "Mausrad: Zoom · Hintergrund ziehen: Ansicht verschieben",
    },

    # ── Panneau de droite ───────────────────────────────────────────────
    'se_appliquer_point': {
        'fr': "Appliquer au point sélectionné", 'en': "Apply to the selected point",
        'es': "Aplicar al punto seleccionado", 'pt': "Aplicar ao ponto selecionado",
        'de': "Auf den ausgewählten Punkt anwenden",
    },
    'se_mode_emploi_titre': {
        'fr': "Mode d’emploi", 'en': "How to use", 'es': "Modo de empleo", 'pt': "Modo de utilização",
        'de': "Anleitung",
    },
    'se_mode_emploi': {
        'fr': '<ol style="margin-left:-20px;color:#666">'
              '<li>Cliquez une pièce de la palette (par ex. « Réseau existant » ou « Tuyau ») pour la poser.</li>'
              '<li>Cliquez un <b>point orange</b> (extrémité libre) puis une pièce : elle se raccorde avec le même '
              'diamètre et matériau. Le point suivant est sélectionné automatiquement pour enchaîner.</li>'
              '<li>Pour raccorder deux pièces déjà posées, glissez-en une : son extrémité libre s’accroche au point '
              'libre le plus proche (Alt : pièce seule).</li>'
              '<li>Cliquez une pièce pour modifier ses caractéristiques. « ★ Montage » enregistre l’ensemble raccordé '
              'dans les Favoris, « ★ Schéma en favori » (en haut) tout le schéma ; ☆ dans la palette ajoute une pièce '
              'aux Favoris.</li>'
              '<li>Glissez une étiquette pour la déplacer ; double-clic dessus : retour au placement automatique.</li>'
              '<li>Ctrl+Z annule.</li></ol>',
        'en': '<ol style="margin-left:-20px;color:#666">'
              '<li>Click a fitting in the palette (e.g. “Existing network” or “Pipe”) to place it.</li>'
              '<li>Click an <b>orange point</b> (free end), then a fitting: it connects with the same '
              'diameter and material. The next point is selected automatically so you can carry on.</li>'
              '<li>To connect two fittings already placed, drag one: its free end snaps to the nearest '
              'free point (Alt: fitting only).</li>'
              '<li>Click a fitting to edit its properties. “★ Assembly” saves the connected group to '
              'Favourites, “★ Diagram to favourites” (top) the whole diagram; ☆ in the palette adds a '
              'fitting to Favourites.</li>'
              '<li>Drag a label to move it; double-click it to return to automatic placement.</li>'
              '<li>Ctrl+Z undoes.</li></ol>',
        'es': '<ol style="margin-left:-20px;color:#666">'
              '<li>Haga clic en una pieza de la paleta (p. ej. «Red existente» o «Tubo») para colocarla.</li>'
              '<li>Haga clic en un <b>punto naranja</b> (extremo libre) y luego en una pieza: se conecta con el '
              'mismo diámetro y material. El punto siguiente se selecciona automáticamente para continuar.</li>'
              '<li>Para conectar dos piezas ya colocadas, arrastre una: su extremo libre se engancha al punto '
              'libre más cercano (Alt: solo la pieza).</li>'
              '<li>Haga clic en una pieza para modificar sus características. «★ Montaje» guarda el conjunto '
              'conectado en Favoritos, «★ Esquema a favoritos» (arriba) todo el esquema; ☆ en la paleta añade '
              'una pieza a Favoritos.</li>'
              '<li>Arrastre una etiqueta para moverla; doble clic en ella: vuelta a la colocación automática.</li>'
              '<li>Ctrl+Z deshace.</li></ol>',
        'pt': '<ol style="margin-left:-20px;color:#666">'
              '<li>Clique numa peça da paleta (por ex. «Rede existente» ou «Tubo») para a colocar.</li>'
              '<li>Clique num <b>ponto laranja</b> (extremidade livre) e depois numa peça: liga-se com o mesmo '
              'diâmetro e material. O ponto seguinte é selecionado automaticamente para continuar.</li>'
              '<li>Para ligar duas peças já colocadas, arraste uma: a sua extremidade livre prende-se ao ponto '
              'livre mais próximo (Alt: só a peça).</li>'
              '<li>Clique numa peça para alterar as suas características. «★ Montagem» guarda o conjunto ligado '
              'nos Favoritos, «★ Esquema nos favoritos» (em cima) todo o esquema; ☆ na paleta adiciona uma peça '
              'aos Favoritos.</li>'
              '<li>Arraste uma etiqueta para a mover; duplo clique nela: volta ao posicionamento automático.</li>'
              '<li>Ctrl+Z anula.</li></ol>',
        'de': '<ol style="margin-left:-20px;color:#666">'
              '<li>Klicken Sie ein Formstück in der Palette an (z. B. „Bestehendes Netz“ oder „Rohr“), um es '
              'zu setzen.</li>'
              '<li>Klicken Sie einen <b>orangen Punkt</b> (freies Ende) und dann ein Formstück an: es wird mit '
              'gleichem Durchmesser und Werkstoff angeschlossen. Der nächste Punkt wird automatisch gewählt, '
              'damit Sie weitermachen können.</li>'
              '<li>Um zwei bereits gesetzte Formstücke zu verbinden, ziehen Sie eines: sein freies Ende rastet am '
              'nächsten freien Punkt ein (Alt: nur das Formstück).</li>'
              '<li>Klicken Sie ein Formstück an, um seine Eigenschaften zu ändern. „★ Baugruppe“ speichert die '
              'verbundene Gruppe in den Favoriten, „★ Schema als Favorit“ (oben) das ganze Schema; ☆ in der '
              'Palette fügt ein Formstück den Favoriten hinzu.</li>'
              '<li>Ziehen Sie eine Beschriftung, um sie zu verschieben; Doppelklick darauf: zurück zur '
              'automatischen Platzierung.</li>'
              '<li>Strg+Z macht rückgängig.</li></ol>',
    },
    'se_point_sel_html': {
        'fr': "<b>Point sélectionné</b> : %s", 'en': "<b>Selected point</b>: %s",
        'es': "<b>Punto seleccionado</b>: %s", 'pt': "<b>Ponto selecionado</b>: %s",
        'de': "<b>Ausgewählter Punkt</b>: %s",
    },
    'se_ext_imposee_html': {
        'fr': '<span style="color:#777">Extrémité imposée à la main (hors variantes du catalogue).</span> '
              '<a href="#">Revenir au catalogue</a>',
        'en': '<span style="color:#777">End set by hand (outside the catalogue variants).</span> '
              '<a href="#">Back to the catalogue</a>',
        'es': '<span style="color:#777">Extremo impuesto a mano (fuera de las variantes del catálogo).</span> '
              '<a href="#">Volver al catálogo</a>',
        'pt': '<span style="color:#777">Extremidade imposta à mão (fora das variantes do catálogo).</span> '
              '<a href="#">Voltar ao catálogo</a>',
        'de': '<span style="color:#777">Ende von Hand festgelegt (außerhalb der Katalogvarianten).</span> '
              '<a href="#">Zurück zum Katalog</a>',
    },
    'se_aide_raccorder_html': {
        'fr': '<span style="color:#777">Cliquez une pièce de la palette pour la raccorder ici.</span>',
        'en': '<span style="color:#777">Click a fitting in the palette to connect it here.</span>',
        'es': '<span style="color:#777">Haga clic en una pieza de la paleta para conectarla aquí.</span>',
        'pt': '<span style="color:#777">Clique numa peça da paleta para a ligar aqui.</span>',
        'de': '<span style="color:#777">Klicken Sie ein Formstück in der Palette an, um es hier '
              'anzuschließen.</span>',
    },
    'se_piv90': {
        'fr': "Pivoter de 90° (sens des aiguilles d’une montre) – R", 'en': "Rotate by 90° (clockwise) – R",
        'es': "Girar 90° (sentido horario) – R", 'pt': "Rodar 90° (sentido horário) – R",
        'de': "Um 90° drehen (im Uhrzeigersinn) – R",
    },
    'se_piv45': {
        'fr': "Pivoter de 45°", 'en': "Rotate by 45°", 'es': "Girar 45°", 'pt': "Rodar 45°",
        'de': "Um 45° drehen",
    },
    'se_pivm90': {
        'fr': "Pivoter de 90° (sens inverse) – Maj+R", 'en': "Rotate by 90° (anticlockwise) – Shift+R",
        'es': "Girar 90° (sentido antihorario) – Mayús+R", 'pt': "Rodar 90° (sentido anti-horário) – Shift+R",
        'de': "Um 90° drehen (gegen den Uhrzeigersinn) – Umschalt+R",
    },
    'se_miroir': {'fr': "Miroir", 'en': "Mirror", 'es': "Espejo", 'pt': "Espelho", 'de': "Spiegeln"},
    'se_miroir_tip': {
        'fr': "Retourner la pièce", 'en': "Flip the fitting", 'es': "Voltear la pieza", 'pt': "Virar a peça",
        'de': "Formstück spiegeln",
    },
    'se_dupliquer': {
        'fr': "Dupliquer", 'en': "Duplicate", 'es': "Duplicar", 'pt': "Duplicar", 'de': "Duplizieren",
    },
    'se_montage': {
        'fr': "★ Montage", 'en': "★ Assembly", 'es': "★ Montaje", 'pt': "★ Montagem", 'de': "★ Baugruppe",
    },
    'se_montage_tip': {
        'fr': "Enregistrer cette pièce et tout ce qui y est raccordé comme montage favori",
        'en': "Save this fitting and everything connected to it as a favourite assembly",
        'es': "Guardar esta pieza y todo lo conectado a ella como montaje favorito",
        'pt': "Guardar esta peça e tudo o que lhe está ligado como montagem favorita",
        'de': "Dieses Formstück und alles Angeschlossene als Favoriten-Baugruppe speichern",
    },
    'se_supprimer': {
        'fr': "Supprimer", 'en': "Delete", 'es': "Eliminar", 'pt': "Eliminar", 'de': "Löschen",
    },
    'se_etiq_auto': {
        'fr': "Étiquette auto", 'en': "Auto label", 'es': "Etiqueta auto", 'pt': "Etiqueta auto",
        'de': "Auto-Beschriftung",
    },
    'se_etiq_auto_tip': {
        'fr': "L’étiquette a été déplacée à la main : revenir au placement automatique",
        'en': "The label was moved by hand: return to automatic placement",
        'es': "La etiqueta se movió a mano: volver a la colocación automática",
        'pt': "A etiqueta foi movida à mão: voltar ao posicionamento automático",
        'de': "Die Beschriftung wurde von Hand verschoben: zurück zur automatischen Platzierung",
    },
    'se_controle': {
        'fr': "Contrôle des assemblages", 'en': "Joint check", 'es': "Control de uniones",
        'pt': "Controlo das ligações", 'de': "Verbindungsprüfung",
    },
    'se_valider': {
        'fr': "✔ Valider", 'en': "✔ Accept", 'es': "✔ Validar", 'pt': "✔ Validar", 'de': "✔ Bestätigen",
    },
    'se_valider_tip': {
        'fr': "Défaut accepté : retire le rond rouge", 'en': "Defect accepted: removes the red circle",
        'es': "Defecto aceptado: quita el círculo rojo", 'pt': "Defeito aceite: retira o círculo vermelho",
        'de': "Mangel akzeptiert: entfernt den roten Kreis",
    },
    'se_valider_tous': {
        'fr': "✔ Valider tous les défauts", 'en': "✔ Accept all defects", 'es': "✔ Validar todos los defectos",
        'pt': "✔ Validar todos os defeitos", 'de': "✔ Alle Mängel bestätigen",
    },
    'se_ok_non_valide_1': {
        'fr': "✔ Aucun problème non validé ({n} assemblage)", 'en': "✔ No unaccepted problem ({n} joint)",
        'es': "✔ Ningún problema sin validar ({n} unión)", 'pt': "✔ Nenhum problema por validar ({n} ligação)",
        'de': "✔ Kein offenes Problem ({n} Verbindung)",
    },
    'se_ok_non_valide_n': {
        'fr': "✔ Aucun problème non validé ({n} assemblages)", 'en': "✔ No unaccepted problem ({n} joints)",
        'es': "✔ Ningún problema sin validar ({n} uniones)", 'pt': "✔ Nenhum problema por validar ({n} ligações)",
        'de': "✔ Kein offenes Problem ({n} Verbindungen)",
    },
    'se_ok_detecte_1': {
        'fr': "✔ Aucun problème détecté ({n} assemblage)", 'en': "✔ No problem found ({n} joint)",
        'es': "✔ Ningún problema detectado ({n} unión)", 'pt': "✔ Nenhum problema detetado ({n} ligação)",
        'de': "✔ Kein Problem gefunden ({n} Verbindung)",
    },
    'se_ok_detecte_n': {
        'fr': "✔ Aucun problème détecté ({n} assemblages)", 'en': "✔ No problem found ({n} joints)",
        'es': "✔ Ningún problema detectado ({n} uniones)", 'pt': "✔ Nenhum problema detetado ({n} ligações)",
        'de': "✔ Kein Problem gefunden ({n} Verbindungen)",
    },
    'se_def_valide_1': {
        'fr': "{n} défaut validé", 'en': "{n} accepted defect", 'es': "{n} defecto validado",
        'pt': "{n} defeito validado", 'de': "{n} bestätigter Mangel",
    },
    'se_def_valide_n': {
        'fr': "{n} défauts validés", 'en': "{n} accepted defects", 'es': "{n} defectos validados",
        'pt': "{n} defeitos validados", 'de': "{n} bestätigte Mängel",
    },
    'se_annuler_validation': {
        'fr': "Annuler", 'en': "Undo", 'es': "Deshacer", 'pt': "Anular", 'de': "Aufheben",
    },
    'se_nomenclature': {
        'fr': "Nomenclature", 'en': "Bill of materials", 'es': "Lista de materiales",
        'pt': "Lista de materiais", 'de': "Stückliste",
    },
    'se_aucune_piece': {
        'fr': "Aucune pièce.", 'en': "No fittings.", 'es': "Ninguna pieza.", 'pt': "Nenhuma peça.",
        'de': "Keine Formstücke.",
    },
    'se_designation': {
        'fr': "Désignation", 'en': "Description", 'es': "Designación", 'pt': "Designação",
        'de': "Bezeichnung",
    },
    'se_qte': {'fr': "Qté", 'en': "Qty", 'es': "Cant.", 'pt': "Qtd.", 'de': "Menge"},
    'se_legende': {
        'fr': "Légende des extrémités", 'en': "End types legend", 'es': "Leyenda de los extremos",
        'pt': "Legenda das extremidades", 'de': "Legende der Enden",
    },

    # ── Liste des nœuds ─────────────────────────────────────────────────
    'se_pas_aep': {
        'fr': "Ce projet n’a pas de réseau AEP. Ouvrir un schéma libre (non rattaché à un nœud) ?",
        'en': "This project has no drinking-water (AEP) network. Open a free diagram (not linked to a node)?",
        'es': "Este proyecto no tiene red AEP. ¿Abrir un esquema libre (no vinculado a un nodo)?",
        'pt': "Este projeto não tem rede AEP. Abrir um esquema livre (não associado a um nó)?",
        'de': "Dieses Projekt hat kein Trinkwassernetz (AEP). Ein freies Schema (ohne Knoten) öffnen?",
    },
    'se_cote_voisin': {
        'fr': "Côté %s (%s)", 'en': "Towards %s (%s)", 'es': "Lado %s (%s)", 'pt': "Lado %s (%s)",
        'de': "Seite %s (%s)",
    },
    'se_cote': {'fr': "Côté %s", 'en': "Towards %s", 'es': "Lado %s", 'pt': "Lado %s", 'de': "Seite %s"},
    'se_vanne_angle': {
        'fr': "La vanne %s est posée sur un angle de conduite : on ne sait pas sur quelle branche elle se "
              "trouve.\nSur quelle branche est-elle ?\n\n(Mieux : dans les données, un point coude à "
              "l’angle et la vanne sur sa branche.)",
        'en': "Valve %s sits on a pipe bend: its branch is unknown.\nWhich branch is it on?\n\n"
              "(Better: in the data, a bend point at the corner and the valve on its branch.)",
        'es': "La válvula %s está sobre un ángulo de tubería: no se sabe en qué ramal se encuentra.\n"
              "¿En qué ramal está?\n\n(Mejor: en los datos, un punto codo en el ángulo y la válvula en su "
              "ramal.)",
        'pt': "A válvula %s está num ângulo de conduta: não se sabe em que ramo se encontra.\n"
              "Em que ramo está?\n\n(Melhor: nos dados, um ponto curva no ângulo e a válvula no seu ramo.)",
        'de': "Der Schieber %s liegt auf einem Leitungsknick: sein Strang ist unbekannt.\n"
              "Auf welchem Strang liegt er?\n\n(Besser: in den Daten ein Bogenpunkt am Knick und der "
              "Schieber auf seinem Strang.)",
    },
    'se_titre_choix': {
        'fr': "SchemAEP – choisir un nœud ou un regard compteur",
        'en': "SchemAEP – choose a node or a meter pit",
        'es': "SchemAEP – elegir un nodo o una arqueta de contador",
        'pt': "SchemAEP – escolher um nó ou uma caixa de contador",
        'de': "SchemAEP – Knoten oder Zählerschacht wählen",
    },
    'se_intro_choix': {
        'fr': "Choisissez le nœud AEP ou le regard compteur dont vous voulez dessiner le schéma. "
              "Un nœud déjà schématisé rouvre son schéma ; sinon SchemAEP part des conduites raccordées.",
        'en': "Choose the water node or meter pit whose diagram you want to draw. "
              "A node that already has a diagram reopens it; otherwise SchemAEP starts from the connected pipes.",
        'es': "Elija el nodo AEP o la arqueta de contador cuyo esquema desea dibujar. "
              "Un nodo que ya tiene esquema lo vuelve a abrir; si no, SchemAEP parte de las tuberías conectadas.",
        'pt': "Escolha o nó AEP ou a caixa de contador cujo esquema quer desenhar. "
              "Um nó que já tem esquema reabre-o; caso contrário, o SchemAEP parte das condutas ligadas.",
        'de': "Wählen Sie den Trinkwasserknoten oder Zählerschacht, dessen Schema Sie zeichnen möchten. "
              "Ein Knoten mit Schema öffnet dieses erneut; sonst geht SchemAEP von den angeschlossenen "
              "Leitungen aus.",
    },
    'se_rech_nom_type': {
        'fr': "Rechercher (nom, type)…", 'en': "Search (name, type)…", 'es': "Buscar (nombre, tipo)…",
        'pt': "Procurar (nome, tipo)…", 'de': "Suchen (Name, Typ)…",
    },
    'se_col_noeud': {'fr': "Nœud", 'en': "Node", 'es': "Nodo", 'pt': "Nó", 'de': "Knoten"},
    'se_col_type': {'fr': "Type", 'en': "Type", 'es': "Tipo", 'pt': "Tipo", 'de': "Typ"},
    'se_col_schema': {'fr': "Schéma", 'en': "Diagram", 'es': "Esquema", 'pt': "Esquema", 'de': "Schema"},
    'se_col_noeuds': {'fr': "Nœuds", 'en': "Nodes", 'es': "Nodos", 'pt': "Nós", 'de': "Knoten"},
    'se_choisir_carte': {
        'fr': "Choisir sur la carte", 'en': "Pick on the map", 'es': "Elegir en el mapa",
        'pt': "Escolher no mapa", 'de': "Auf der Karte wählen",
    },
    'se_copier_schema': {
        'fr': "Copier le schéma", 'en': "Copy diagram", 'es': "Copiar el esquema", 'pt': "Copiar o esquema",
        'de': "Schema kopieren",
    },
    'se_copier_schema_tip': {
        'fr': "Copier le schéma du nœud sélectionné", 'en': "Copy the diagram of the selected node",
        'es': "Copiar el esquema del nodo seleccionado", 'pt': "Copiar o esquema do nó selecionado",
        'de': "Schema des ausgewählten Knotens kopieren",
    },
    'se_coller_sel': {
        'fr': "Coller sur la sélection", 'en': "Paste onto selection", 'es': "Pegar en la selección",
        'pt': "Colar na seleção", 'de': "In Auswahl einfügen",
    },
    'se_coller_sel_n': {
        'fr': "Coller sur la sélection (%d)", 'en': "Paste onto selection (%d)",
        'es': "Pegar en la selección (%d)", 'pt': "Colar na seleção (%d)", 'de': "In Auswahl einfügen (%d)",
    },
    'se_coller_sel_tip': {
        'fr': "Coller le schéma copié sur les nœuds sélectionnés (Ctrl+clic ou Maj+clic pour en choisir plusieurs)",
        'en': "Paste the copied diagram onto the selected nodes (Ctrl+click or Shift+click to select several)",
        'es': "Pegar el esquema copiado en los nodos seleccionados (Ctrl+clic o Mayús+clic para elegir varios)",
        'pt': "Colar o esquema copiado nos nós selecionados (Ctrl+clique ou Shift+clique para escolher vários)",
        'de': "Kopiertes Schema in die ausgewählten Knoten einfügen (Strg+Klick oder Umschalt+Klick für mehrere)",
    },
    'se_suppr_schema': {
        'fr': "Supprimer le schéma", 'en': "Delete diagram", 'es': "Eliminar el esquema",
        'pt': "Eliminar o esquema", 'de': "Schema löschen",
    },
    'se_suppr_schemas_n': {
        'fr': "Supprimer les schémas (%d)", 'en': "Delete diagrams (%d)", 'es': "Eliminar los esquemas (%d)",
        'pt': "Eliminar os esquemas (%d)", 'de': "Schemata löschen (%d)",
    },
    'se_schema_libre': {
        'fr': "Schéma libre", 'en': "Free diagram", 'es': "Esquema libre", 'pt': "Esquema livre",
        'de': "Freies Schema",
    },
    'se_schema_libre_tip': {
        'fr': "Schéma non rattaché à un nœud (fichier .json)", 'en': "Diagram not linked to a node (.json file)",
        'es': "Esquema no vinculado a un nodo (archivo .json)",
        'pt': "Esquema não associado a um nó (ficheiro .json)", 'de': "Schema ohne Knoten (.json-Datei)",
    },
    'se_nomenc_tous': {
        'fr': "Nomenclature de tous les schémas…", 'en': "Bill of materials of all diagrams…",
        'es': "Lista de materiales de todos los esquemas…", 'pt': "Lista de materiais de todos os esquemas…",
        'de': "Stückliste aller Schemata…",
    },
    'se_ouvrir_le_schema': {
        'fr': "Ouvrir le schéma", 'en': "Open diagram", 'es': "Abrir el esquema", 'pt': "Abrir o esquema",
        'de': "Schema öffnen",
    },
    'se_fermer': {'fr': "Fermer", 'en': "Close", 'es': "Cerrar", 'pt': "Fechar", 'de': "Schließen"},
    'se_realigner': {
        'fr': "Réaligner (horizontal / vertical)", 'en': "Realign (horizontal / vertical)",
        'es': "Realinear (horizontal / vertical)", 'pt': "Realinhar (horizontal / vertical)",
        'de': "Neu ausrichten (horizontal / vertikal)",
    },
    'se_realigner_tip': {
        'fr': "Tourne les schémas sélectionnés au quart de tour le plus proche, sans changer leur contenu",
        'en': "Rotates the selected diagrams to the nearest quarter turn, without changing their content",
        'es': "Gira los esquemas seleccionados al cuarto de vuelta más cercano, sin cambiar su contenido",
        'pt': "Roda os esquemas selecionados para o quarto de volta mais próximo, sem alterar o seu conteúdo",
        'de': "Dreht die ausgewählten Schemata auf die nächste Vierteldrehung, ohne ihren Inhalt zu ändern",
    },
    'se_recreer': {
        'fr': "Recréer par défaut", 'en': "Recreate default", 'es': "Recrear por defecto",
        'pt': "Recriar predefinido", 'de': "Standard neu erstellen",
    },
    'se_recreer_tip': {
        'fr': "Remplace les schémas sélectionnés par le schéma calculé depuis la carte et les favoris",
        'en': "Replaces the selected diagrams with the diagram computed from the map and favourites",
        'es': "Reemplaza los esquemas seleccionados por el esquema calculado a partir del mapa y los favoritos",
        'pt': "Substitui os esquemas selecionados pelo esquema calculado a partir do mapa e dos favoritos",
        'de': "Ersetzt die ausgewählten Schemata durch das aus Karte und Favoriten berechnete Schema",
    },
    'se_schema_vide_html': {
        'fr': "<br><i>Schéma vide</i>", 'en': "<br><i>Empty diagram</i>", 'es': "<br><i>Esquema vacío</i>",
        'pt': "<br><i>Esquema vazio</i>", 'de': "<br><i>Leeres Schema</i>",
    },
    'se_vanne_carrefour': {
        'fr': "Vanne à %.1f m du carrefour : elle est dessinée dans son schéma",
        'en': "Valve %.1f m from the junction: it is drawn in the junction diagram",
        'es': "Válvula a %.1f m del cruce: se dibuja en su esquema",
        'pt': "Válvula a %.1f m do cruzamento: é desenhada no seu esquema",
        'de': "Schieber %.1f m vom Knotenpunkt: er wird in dessen Schema gezeichnet",
    },
    'se_vanne_angle_tip': {
        'fr': "Vanne posée sur un angle ou un té : on ne sait pas sur quelle branche elle se trouve. Dans les "
              "données, placez un point coude/té au carrefour et la vanne sur sa branche (à 2 m ou moins).",
        'en': "Valve placed on a bend or tee: its branch is unknown. In the data, place a bend/tee point at "
              "the junction and the valve on its branch (2 m away or less).",
        'es': "Válvula colocada en un ángulo o una te: no se sabe en qué ramal está. En los datos, coloque un "
              "punto codo/te en el cruce y la válvula en su ramal (a 2 m o menos).",
        'pt': "Válvula colocada num ângulo ou num tê: não se sabe em que ramo está. Nos dados, coloque um "
              "ponto curva/tê no cruzamento e a válvula no seu ramo (a 2 m ou menos).",
        'de': "Schieber auf einem Knick oder T-Stück: sein Strang ist unbekannt. Setzen Sie in den Daten "
              "einen Bogen-/T-Punkt am Knotenpunkt und den Schieber auf seinen Strang (höchstens 2 m entfernt).",
    },
    'se_schema_copie_lbl': {
        'fr': "Schéma copié : %s", 'en': "Copied diagram: %s", 'es': "Esquema copiado: %s",
        'pt': "Esquema copiado: %s", 'de': "Kopiertes Schema: %s",
    },
    'se_aucun_copie': {
        'fr': "Aucun schéma copié.", 'en': "No diagram copied.", 'es': "Ningún esquema copiado.",
        'pt': "Nenhum esquema copiado.", 'de': "Kein Schema kopiert.",
    },
    'se_deja_schema': {
        'fr': "%d nœud(s) sélectionné(s) ont déjà un schéma. Le remplacer par celui de %s ?",
        'en': "%d selected node(s) already have a diagram. Replace it with the one from %s?",
        'es': "%d nodo(s) seleccionado(s) ya tienen un esquema. ¿Reemplazarlo por el de %s?",
        'pt': "%d nó(s) selecionado(s) já têm um esquema. Substituí-lo pelo de %s?",
        'de': "%d ausgewählte(r) Knoten hat/haben bereits ein Schema. Durch das von %s ersetzen?",
    },
    'se_colle_1': {
        'fr': "Schéma de {source} collé sur {n} nœud.", 'en': "Diagram of {source} pasted onto {n} node.",
        'es': "Esquema de {source} pegado en {n} nodo.", 'pt': "Esquema de {source} colado em {n} nó.",
        'de': "Schema von {source} in {n} Knoten eingefügt.",
    },
    'se_colle_n': {
        'fr': "Schéma de {source} collé sur {n} nœuds.", 'en': "Diagram of {source} pasted onto {n} nodes.",
        'es': "Esquema de {source} pegado en {n} nodos.", 'pt': "Esquema de {source} colado em {n} nós.",
        'de': "Schema von {source} in {n} Knoten eingefügt.",
    },
    'se_non_colle': {
        'fr': "\nNon collé sur %s : son schéma est ouvert avec des modifications non enregistrées.",
        'en': "\nNot pasted onto %s: its diagram is open with unsaved changes.",
        'es': "\nNo pegado en %s: su esquema está abierto con cambios sin guardar.",
        'pt': "\nNão colado em %s: o seu esquema está aberto com alterações não guardadas.",
        'de': "\nNicht in %s eingefügt: sein Schema ist mit ungespeicherten Änderungen geöffnet.",
    },
    'se_pensez': {
        'fr': "\nPensez à enregistrer le projet CanaPlan.", 'en': "\nRemember to save the CanaPlan project.",
        'es': "\nRecuerde guardar el proyecto CanaPlan.", 'pt': "\nLembre-se de guardar o projeto CanaPlan.",
        'de': "\nDenken Sie daran, das CanaPlan-Projekt zu speichern.",
    },
    'se_realigne_1': {
        'fr': "{n} schéma réaligné.", 'en': "{n} diagram realigned.", 'es': "{n} esquema realineado.",
        'pt': "{n} esquema realinhado.", 'de': "{n} Schema neu ausgerichtet.",
    },
    'se_realigne_n': {
        'fr': "{n} schémas réalignés.", 'en': "{n} diagrams realigned.", 'es': "{n} esquemas realineados.",
        'pt': "{n} esquemas realinhados.", 'de': "{n} Schemata neu ausgerichtet.",
    },
    'se_non_modifie': {
        'fr': "\nNon modifié : %s (modifications non enregistrées).",
        'en': "\nNot changed: %s (unsaved changes).",
        'es': "\nSin modificar: %s (cambios sin guardar).",
        'pt': "\nNão alterado: %s (alterações não guardadas).",
        'de': "\nNicht geändert: %s (ungespeicherte Änderungen).",
    },
    'se_remplaces_defaut': {
        'fr': "%d schéma(s) existant(s) seront remplacés par le schéma par défaut "
              "(vos modifications dessus seront perdues). Continuer ?",
        'en': "%d existing diagram(s) will be replaced by the default diagram "
              "(your changes to them will be lost). Continue?",
        'es': "%d esquema(s) existente(s) se reemplazarán por el esquema por defecto "
              "(se perderán sus cambios). ¿Continuar?",
        'pt': "%d esquema(s) existente(s) serão substituídos pelo esquema predefinido "
              "(as suas alterações perder-se-ão). Continuar?",
        'de': "%d vorhandene(s) Schema(ta) wird/werden durch das Standardschema ersetzt "
              "(Ihre Änderungen gehen verloren). Fortfahren?",
    },
    'se_recree_1': {
        'fr': "{n} schéma recréé.", 'en': "{n} diagram recreated.", 'es': "{n} esquema recreado.",
        'pt': "{n} esquema recriado.", 'de': "{n} Schema neu erstellt.",
    },
    'se_recree_n': {
        'fr': "{n} schémas recréés.", 'en': "{n} diagrams recreated.", 'es': "{n} esquemas recreados.",
        'pt': "{n} esquemas recriados.", 'de': "{n} Schemata neu erstellt.",
    },
    'se_suppr_schemas_q': {
        'fr': "Supprimer les schémas des %d nœuds sélectionnés ?",
        'en': "Delete the diagrams of the %d selected nodes?",
        'es': "¿Eliminar los esquemas de los %d nodos seleccionados?",
        'pt': "Eliminar os esquemas dos %d nós selecionados?",
        'de': "Schemata der %d ausgewählten Knoten löschen?",
    },
    'se_suppr_schema_q': {
        'fr': "Supprimer le schéma de ce nœud ?", 'en': "Delete this node's diagram?",
        'es': "¿Eliminar el esquema de este nodo?", 'pt': "Eliminar o esquema deste nó?",
        'de': "Schema dieses Knotens löschen?",
    },
    'se_titre_nomenc': {
        'fr': "SchemAEP – nomenclature de tous les schémas", 'en': "SchemAEP – bill of materials of all diagrams",
        'es': "SchemAEP – lista de materiales de todos los esquemas",
        'pt': "SchemAEP – lista de materiais de todos os esquemas", 'de': "SchemAEP – Stückliste aller Schemata",
    },
    'se_nb_schemas_1': {
        'fr': "{n} schéma de nœud.", 'en': "{n} node diagram.", 'es': "{n} esquema de nodo.",
        'pt': "{n} esquema de nó.", 'de': "{n} Knotenschema.",
    },
    'se_nb_schemas_n': {
        'fr': "{n} schémas de nœuds.", 'en': "{n} node diagrams.", 'es': "{n} esquemas de nodos.",
        'pt': "{n} esquemas de nós.", 'de': "{n} Knotenschemata.",
    },
    'se_exporter_csv': {
        'fr': "Exporter en CSV…", 'en': "Export to CSV…", 'es': "Exportar a CSV…", 'pt': "Exportar para CSV…",
        'de': "Als CSV exportieren…",
    },
    'se_nomenc_schemas': {
        'fr': "Nomenclature des schémas", 'en': "Diagrams bill of materials",
        'es': "Lista de materiales de los esquemas", 'pt': "Lista de materiais dos esquemas",
        'de': "Stückliste der Schemata",
    },
    'se_csv_entete': {
        'fr': "Désignation;Quantité;Unité;Nœuds", 'en': "Description;Quantity;Unit;Nodes",
        'es': "Designación;Cantidad;Unidad;Nodos", 'pt': "Designação;Quantidade;Unidade;Nós",
        'de': "Bezeichnung;Menge;Einheit;Knoten",
    },

    # ── Sorties imprimées (PDF des schémas) ─────────────────────────────
    'se_pied': {
        'fr': "%s – schémas de nœuds AEP – %s", 'en': "%s – water node diagrams – %s",
        'es': "%s – esquemas de nodos AEP – %s", 'pt': "%s – esquemas de nós AEP – %s",
        'de': "%s – Trinkwasser-Knotenschemata – %s",
    },
    'se_projet': {'fr': "Projet", 'en': "Project", 'es': "Proyecto", 'pt': "Projeto", 'de': "Projekt"},
    'se_page': {'fr': "Page %d", 'en': "Page %d", 'es': "Página %d", 'pt': "Página %d", 'de': "Seite %d"},
    'se_suite': {
        'fr': " (suite)", 'en': " (continued)", 'es': " (continuación)", 'pt': " (continuação)",
        'de': " (Fortsetzung)",
    },
    'se_nomenc_par_noeud': {
        'fr': "Nomenclature par nœud", 'en': "Bill of materials by node", 'es': "Lista de materiales por nodo",
        'pt': "Lista de materiais por nó", 'de': "Stückliste je Knoten",
    },
    'se_listing_total': {
        'fr': "Listing total des pièces", 'en': "Total list of fittings", 'es': "Listado total de piezas",
        'pt': "Listagem total das peças", 'de': "Gesamtliste der Formstücke",
    },
    'se_total': {'fr': "Total", 'en': "Total", 'es': "Total", 'pt': "Total", 'de': "Summe"},
    'se_n_noeud_1': {
        'fr': "{n} nœud", 'en': "{n} node", 'es': "{n} nodo", 'pt': "{n} nó", 'de': "{n} Knoten",
    },
    'se_n_noeud_n': {
        'fr': "{n} nœuds", 'en': "{n} nodes", 'es': "{n} nodos", 'pt': "{n} nós", 'de': "{n} Knoten",
    },
}
