# tools/i18n_magic.py
"""Traductions de la Magic Box, fusionnées dans i18n.TR (même format)."""

TR_MAGIC = {
    'magic_box': {
        'fr': "Magic Box", 'en': "Magic Box", 'es': "Magic Box",
        'pt': "Magic Box", 'de': "Magic Box",
    },
    'mb_aide': {
        'fr': "Choisissez une fonction automatique.",
        'en': "Choose an automatic function.",
        'es': "Elija una función automática.",
        'pt': "Escolha uma função automática.",
        'de': "Wählen Sie eine automatische Funktion.",
    },
    'mb_branchements_auto': {
        'fr': "Branchements automatiques", 'en': "Automatic service connections",
        'es': "Acometidas automáticas", 'pt': "Ramais automáticos",
        'de': "Automatische Hausanschlüsse",
    },
    'mb_branchements_auto_tip': {
        'fr': "Trace un branchement par parcelle, bâtiment ou numéro de rue le long des tronçons choisis.",
        'en': "Draws one connection per parcel, building or street number along the chosen pipes.",
        'es': "Traza una acometida por parcela, edificio o número de calle a lo largo de los tramos elegidos.",
        'pt': "Traça um ramal por parcela, edifício ou número de porta ao longo dos troços escolhidos.",
        'de': "Zeichnet einen Anschluss je Flurstück, Gebäude oder Hausnummer entlang der gewählten Haltungen.",
    },
    'mb_raccorder': {
        'fr': "Un branchement…", 'en': "One connection…", 'es': "Una acometida…",
        'pt': "Um ramal…", 'de': "Ein Anschluss…",
    },
    'mb_mode_parcelle': {
        'fr': "à la parcelle", 'en': "per parcel", 'es': "por parcela",
        'pt': "por parcela", 'de': "je Flurstück",
    },
    'mb_mode_parcelle_tip': {
        'fr': "Chaque parcelle riveraine, même sans bâtiment.",
        'en': "Every parcel along the street, even without a building.",
        'es': "Cada parcela colindante, incluso sin edificio.",
        'pt': "Cada parcela confinante, mesmo sem edifício.",
        'de': "Jedes angrenzende Flurstück, auch ohne Gebäude.",
    },
    'mb_mode_bati': {
        'fr': "au bâti", 'en': "per building", 'es': "por edificio",
        'pt': "por edifício", 'de': "je Gebäude",
    },
    'mb_mode_bati_tip': {
        'fr': "Chaque bâtiment riverain, en face de sa façade.",
        'en': "Every building along the street, facing its front.",
        'es': "Cada edificio colindante, frente a su fachada.",
        'pt': "Cada edifício confinante, em frente à fachada.",
        'de': "Jedes angrenzende Gebäude, gegenüber seiner Fassade.",
    },
    'mb_mode_numero': {
        'fr': "au numéro de rue", 'en': "per street number",
        'es': "por número de calle", 'pt': "por número de porta",
        'de': "je Hausnummer",
    },
    'mb_mode_numero_tip': {
        'fr': "Chaque adresse BAN riveraine, en face du numéro.",
        'en': "Every BAN address along the street, facing the number.",
        'es': "Cada dirección BAN colindante, frente al número.",
        'pt': "Cada endereço BAN confinante, em frente ao número.",
        'de': "Jede angrenzende BAN-Adresse, gegenüber der Nummer.",
    },
    'mb_reseau': {
        'fr': "Réseau :", 'en': "Network:", 'es': "Red:", 'pt': "Rede:",
        'de': "Netz:",
    },
    'mb_cote': {
        'fr': "Côté de la rue :", 'en': "Street side:", 'es': "Lado de la calle:",
        'pt': "Lado da rua:", 'de': "Straßenseite:",
    },
    'mb_cote_deux': {
        'fr': "Les deux côtés", 'en': "Both sides", 'es': "Ambos lados",
        'pt': "Ambos os lados", 'de': "Beide Seiten",
    },
    'mb_cote_gauche': {
        'fr': "Gauche (sens de tracé)", 'en': "Left (drawing direction)",
        'es': "Izquierda (sentido de trazado)", 'pt': "Esquerda (sentido do traçado)",
        'de': "Links (Zeichenrichtung)",
    },
    'mb_cote_droite': {
        'fr': "Droite (sens de tracé)", 'en': "Right (drawing direction)",
        'es': "Derecha (sentido de trazado)", 'pt': "Direita (sentido do traçado)",
        'de': "Rechts (Zeichenrichtung)",
    },
    'mb_distance_max': {
        'fr': "Distance max. conduite → limite :", 'en': "Max. distance pipe → boundary:",
        'es': "Distancia máx. tubería → límite:", 'pt': "Distância máx. conduta → limite:",
        'de': "Max. Abstand Leitung → Grenze:",
    },
    'mb_diametre': {
        'fr': "Diamètre (mm) :", 'en': "Diameter (mm):", 'es': "Diámetro (mm):",
        'pt': "Diâmetro (mm):", 'de': "Durchmesser (mm):",
    },
    'mb_materiau': {
        'fr': "Matériau :", 'en': "Material:", 'es': "Material:",
        'pt': "Material:", 'de': "Werkstoff:",
    },
    'mb_selectionner': {
        'fr': "Sélectionner les tronçons…", 'en': "Select the pipes…",
        'es': "Seleccionar los tramos…", 'pt': "Selecionar os troços…",
        'de': "Haltungen auswählen…",
    },
    'mb_couches_manquantes': {
        'fr': "Couche(s) absente(s) du projet : {noms}.\nChargez-les depuis « Fonds de plan » puis relancez.",
        'en': "Layer(s) missing from the project: {noms}.\nLoad them from “Base maps” and try again.",
        'es': "Capa(s) ausente(s) del proyecto: {noms}.\nCárguelas desde «Fondos de plano» y vuelva a intentarlo.",
        'pt': "Camada(s) ausente(s) do projeto: {noms}.\nCarregue-as em «Fundos de plano» e tente de novo.",
        'de': "Fehlende Layer im Projekt: {noms}.\nÜber „Hintergrundkarten“ laden und erneut versuchen.",
    },
    'mb_aide_selection': {
        'fr': "Cliquez les conduites à raccorder (re-clic = retirer). Clic droit ou Entrée : valider — Échap : annuler.",
        'en': "Click the pipes to connect (click again to remove). Right-click or Enter: confirm — Esc: cancel.",
        'es': "Haga clic en las tuberías (otro clic = quitar). Clic derecho o Intro: validar — Esc: cancelar.",
        'pt': "Clique nas condutas (novo clique = retirar). Clique direito ou Enter: validar — Esc: cancelar.",
        'de': "Leitungen anklicken (erneut = entfernen). Rechtsklick oder Enter: bestätigen — Esc: abbrechen.",
    },
    'mb_aucune_conduite': {
        'fr': "Aucune conduite sélectionnée.", 'en': "No pipe selected.",
        'es': "Ninguna tubería seleccionada.", 'pt': "Nenhuma conduta selecionada.",
        'de': "Keine Leitung ausgewählt.",
    },
    'mb_apercu': {
        'fr': "Aperçu des branchements", 'en': "Connections preview",
        'es': "Vista previa de las acometidas", 'pt': "Pré-visualização dos ramais",
        'de': "Vorschau der Anschlüsse",
    },
    'mb_apercu_resume': {
        'fr': "<b>{n}</b> branchement(s) {reseau} proposé(s) en pointillés sur la carte.<br>{e} cible(s) écartée(s).",
        'en': "<b>{n}</b> {reseau} connection(s) proposed, dashed on the map.<br>{e} target(s) skipped.",
        'es': "<b>{n}</b> acometida(s) {reseau} propuesta(s) en discontinuo en el mapa.<br>{e} objetivo(s) descartado(s).",
        'pt': "<b>{n}</b> ramal(is) {reseau} proposto(s) a tracejado no mapa.<br>{e} alvo(s) excluído(s).",
        'de': "<b>{n}</b> {reseau}-Anschluss/Anschlüsse gestrichelt in der Karte.<br>{e} Ziel(e) übersprungen.",
    },
    'mb_portee': {
        'fr': "Portée max :", 'en': "Max reach:", 'es': "Alcance máx.:",
        'pt': "Alcance máx.:", 'de': "Max. Reichweite:",
    },
    'mb_portee_tip': {
        'fr': "Distance maximale entre la conduite et la cible (bâtiment, parcelle, numéro), qui borne aussi la longueur du branchement. À augmenter quand des cibles sont écartées faute de limite atteinte.",
        'en': "Maximum distance between the main and the target (building, parcel, number), which also caps the connection length. Increase it when targets are skipped because no boundary was reached.",
        'es': "Distancia máxima entre la conducción y el objetivo (edificio, parcela, número), que también limita la longitud de la acometida. Auméntela cuando se descarten objetivos por no alcanzar ningún límite.",
        'pt': "Distância máxima entre a conduta e o alvo (edifício, parcela, número), que também limita o comprimento do ramal. Aumente-a quando alvos forem excluídos por nenhum limite ser alcançado.",
        'de': "Maximaler Abstand zwischen Leitung und Ziel (Gebäude, Flurstück, Hausnummer), der auch die Anschlusslänge begrenzt. Erhöhen, wenn Ziele mangels erreichter Grenze übersprungen werden.",
    },
    'mb_recalculer': {
        'fr': "↻ Recalculer", 'en': "↻ Recompute", 'es': "↻ Recalcular",
        'pt': "↻ Recalcular", 'de': "↻ Neu berechnen",
    },
    'mb_details': {
        'fr': "Détails des cibles écartées", 'en': "Skipped targets details",
        'es': "Detalle de los objetivos descartados", 'pt': "Detalhe dos alvos excluídos",
        'de': "Details der übersprungenen Ziele",
    },
    'mb_tracer': {
        'fr': "Tracer", 'en': "Draw", 'es': "Trazar", 'pt': "Traçar",
        'de': "Zeichnen",
    },
    'mb_resultat': {
        'fr': "{n} branchement(s) {reseau} tracé(s).", 'en': "{n} {reseau} connection(s) drawn.",
        'es': "{n} acometida(s) {reseau} trazada(s).", 'pt': "{n} ramal(is) {reseau} traçado(s).",
        'de': "{n} {reseau}-Anschluss/Anschlüsse gezeichnet.",
    },
    'mb_echecs': {
        'fr': "{n} branchement(s) non tracé(s) :", 'en': "{n} connection(s) not drawn:",
        'es': "{n} acometida(s) no trazada(s):", 'pt': "{n} ramal(is) não traçado(s):",
        'de': "{n} Anschluss/Anschlüsse nicht gezeichnet:",
    },
    'mb_rien': {
        'fr': "Aucun branchement à proposer sur ces tronçons.",
        'en': "No connection to propose on these pipes.",
        'es': "Ninguna acometida que proponer en estos tramos.",
        'pt': "Nenhum ramal a propor nestes troços.",
        'de': "Keine Anschlüsse an diesen Haltungen vorzuschlagen.",
    },
    'mb_etape_mode': {
        'fr': "Qu'est-ce qu'on raccorde ?", 'en': "What do we connect?",
        'es': "¿Qué conectamos?", 'pt': "O que ligamos?",
        'de': "Was schließen wir an?",
    },
    'mb_etape_reseau': {
        'fr': "Sur quel réseau ?", 'en': "On which network?",
        'es': "¿En qué red?", 'pt': "Em que rede?", 'de': "An welches Netz?",
    },
    'mb_etape_cote': {
        'fr': "De quel côté de la rue ?", 'en': "Which side of the street?",
        'es': "¿De qué lado de la calle?", 'pt': "De que lado da rua?",
        'de': "Welche Straßenseite?",
    },
    'mb_retour': {
        'fr': "Retour", 'en': "Back", 'es': "Atrás", 'pt': "Voltar",
        'de': "Zurück",
    },
    'mb_reglages': {
        'fr': "Réglages (distance, diamètre, matériau)",
        'en': "Settings (distance, diameter, material)",
        'es': "Ajustes (distancia, diámetro, material)",
        'pt': "Definições (distância, diâmetro, material)",
        'de': "Einstellungen (Abstand, Durchmesser, Werkstoff)",
    },
    'mb_branchements_court': {
        'fr': 'Branchements auto', 'en': 'Auto connections',
        'es': 'Acometidas auto', 'pt': 'Ramais auto',
        'de': 'Auto-Anschlüsse',
    },
    'mb_annuler': {
        'fr': 'Annuler', 'en': 'Cancel',
        'es': 'Cancelar', 'pt': 'Cancelar',
        'de': 'Abbrechen',
    },
    'mb_autre_reseau': {
        'fr': 'Sélection en cours sur le réseau {reseau} : une seule famille de conduites à la fois.', 'en': 'Selection in progress on the {reseau} network: one network at a time.',
        'es': 'Selección en curso en la red {reseau}: una red a la vez.', 'pt': 'Seleção em curso na rede {reseau}: uma rede de cada vez.',
        'de': 'Auswahl läuft im Netz {reseau}: jeweils nur ein Netz.',
    },
}
