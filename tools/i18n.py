# tools/i18n.py
"""Traduction de l'interface de CanaPlan (FR / EN / ES / PT / DE).

Deux niveaux de décision, dans cet ordre :

1. l'utilisateur a choisi une langue explicitement → elle prime, quoi que
   fasse QGIS ensuite ;
2. sinon (préférence « auto », valeur par défaut) → on suit `locale/userLocale`,
   la langue de QGIS.

Le stockage se fait en QSettings, donc la préférence survit au redémarrage.

Le choix d'un dictionnaire Python plutôt que du couple QTranslator/.qm est
délibéré : lrelease, qui compile les .ts en .qm, n'est pas fourni avec QGIS
sous Windows, et surtout QTranslator ne retraduit pas les widgets déjà
construits — il impose un redémarrage. Ici, `signaux.langue_changee` permet
au panneau et au menu de se retraduire sur place.
"""
from qgis.PyQt.QtCore import QObject, QSettings, pyqtSignal

_CLE_PREFERENCE = "CanaPlan/language"

# Langues réellement traduites. Le français est la langue source.
SUPPORTEES = ('fr', 'en', 'es', 'pt', 'de')

# Repli quand la langue de QGIS n'est pas dans SUPPORTEES : l'anglais touche
# plus de monde que le français hors de France.
REPLI = 'en'

# Entrées du sélecteur : (code, libellé affiché). 'auto' n'est pas une langue,
# c'est le suivi de QGIS.
CHOIX = (
    ('auto', None),          # libellé traduit via la clé 'langue_auto'
    ('fr', 'Français'),
    ('en', 'English'),
    ('es', 'Español'),
    ('pt', 'Português'),
    ('de', 'Deutsch'),
)


class _Signaux(QObject):
    """Porte le signal de changement de langue (QObject requis par Qt)."""
    langue_changee = pyqtSignal(str)


signaux = _Signaux()


def preference():
    """Préférence brute : 'auto' ou un code de SUPPORTEES."""
    valeur = QSettings().value(_CLE_PREFERENCE, 'auto')
    return valeur if valeur in SUPPORTEES else 'auto'


def langue():
    """Langue effectivement appliquée, préférence et locale QGIS résolues."""
    pref = preference()
    if pref in SUPPORTEES:
        return pref
    locale = QSettings().value('locale/userLocale', '') or ''
    code = str(locale)[:2].lower()
    return code if code in SUPPORTEES else REPLI


def definir(pref):
    """Enregistre la préférence et prévient l'interface si elle change."""
    avant = langue()
    QSettings().setValue(_CLE_PREFERENCE, pref if pref in SUPPORTEES else 'auto')
    apres = langue()
    if apres != avant:
        signaux.langue_changee.emit(apres)


def tr(cle, **kwargs):
    """Traduit une clé dans la langue courante.

    Repli en cascade : langue courante, puis anglais, puis la clé elle-même —
    une clé oubliée reste ainsi visible à l'écran au lieu de faire planter.
    """
    entree = TR.get(cle)
    if entree is None:
        return cle
    texte = entree.get(langue()) or entree.get(REPLI) or cle
    if kwargs:
        try:
            return texte.format(**kwargs)
        except (KeyError, IndexError):
            return texte
    return texte


# Séparateur décimal par langue. L'anglais est la seule des cinq à utiliser
# le point ; sur un métré remis à un maître d'ouvrage français, le point
# détonne.
SEPARATEUR_DECIMAL = {'fr': ',', 'en': '.', 'es': ',', 'pt': ',', 'de': ','}


def nombre(valeur, decimales=2, vide="—"):
    """Formate un nombre selon la convention de la langue courante.

    Utilisé par les rapports PDF : les tableaux mélangent des valeurs et des
    cellules sans donnée, d'où le repli `vide` plutôt qu'un plantage.
    """
    if valeur is None:
        return vide
    try:
        texte = "%.*f" % (decimales, float(valeur))
    except (TypeError, ValueError):
        return vide
    separateur = SEPARATEUR_DECIMAL.get(langue(), '.')
    return texte.replace('.', separateur) if separateur != '.' else texte


def libelle_choix(code):
    """Libellé d'une entrée du sélecteur de langue."""
    if code == 'auto':
        return tr('langue_auto')
    for c, libelle in CHOIX:
        if c == code:
            return libelle
    return code


# ─────────────────────────────────────────────────────────────────────────────
#  Dictionnaire de traduction
#
#  Une clé par message. Les noms propres et les sigles normatifs (EU, EP, DXF,
#  StaR-Eau, BAN, PCI, BD TOPO, IGN, GML, GPKG) ne se traduisent pas.
# ─────────────────────────────────────────────────────────────────────────────

TR = {
    # ── Sélecteur de langue ──────────────────────────────────────────────
    'langue': {
        'fr': "Langue", 'en': "Language", 'es': "Idioma",
        'pt': "Idioma", 'de': "Sprache",
    },
    'langue_auto': {
        'fr': "Automatique (langue de QGIS)", 'en': "Automatic (QGIS language)",
        'es': "Automático (idioma de QGIS)", 'pt': "Automático (idioma do QGIS)",
        'de': "Automatisch (QGIS-Sprache)",
    },

    # ── Panneau et menu ──────────────────────────────────────────────────
    'toggle_panel': {
        'fr': "Afficher le panneau latéral", 'en': "Show the side panel",
        'es': "Mostrar el panel lateral", 'pt': "Mostrar o painel lateral",
        'de': "Seitenleiste anzeigen",
    },
    'toggle_panel_tip': {
        'fr': "CanaPlan — afficher / masquer le panneau latéral",
        'en': "CanaPlan — show / hide the side panel",
        'es': "CanaPlan — mostrar / ocultar el panel lateral",
        'pt': "CanaPlan — mostrar / ocultar o painel lateral",
        'de': "CanaPlan — Seitenleiste ein-/ausblenden",
    },

    # ── Titres de groupes ────────────────────────────────────────────────
    'grp_projet': {
        'fr': "Projet", 'en': "Project", 'es': "Proyecto",
        'pt': "Projeto", 'de': "Projekt",
    },
    'grp_general': {
        'fr': "Général", 'en': "General", 'es': "General",
        'pt': "Geral", 'de': "Allgemein",
    },
    'grp_eu': {
        'fr': "EU – Eaux Usées", 'en': "EU – Wastewater",
        'es': "EU – Aguas residuales", 'pt': "EU – Águas residuais",
        'de': "EU – Schmutzwasser",
    },
    'grp_ep': {
        'fr': "EP – Eaux Pluviales", 'en': "EP – Stormwater",
        'es': "EP – Aguas pluviales", 'pt': "EP – Águas pluviais",
        'de': "EP – Regenwasser",
    },
    'grp_etiquettes': {
        'fr': "Étiquettes", 'en': "Labels", 'es': "Etiquetas",
        'pt': "Rótulos", 'de': "Beschriftungen",
    },
    'grp_sorties': {
        'fr': "Sorties & Impression", 'en': "Output & Printing",
        'es': "Salidas e impresión", 'pt': "Saídas e impressão",
        'de': "Ausgabe & Druck",
    },
    'grp_fond': {
        'fr': "Fond de carte", 'en': "Basemap", 'es': "Mapa base",
        'pt': "Mapa base", 'de': "Hintergrundkarte",
    },

    # ── Groupe Projet ────────────────────────────────────────────────────
    'nouveau_projet_assistant': {
        'fr': "Créer un projet avec l'assistant",
        'en': "Create a project with the wizard",
        'es': "Crear un proyecto con el asistente",
        'pt': "Criar um projeto com o assistente",
        'de': "Projekt mit dem Assistenten erstellen",
    },
    'projets_recents': {
        'fr': "Projets récents…", 'en': "Recent projects…",
        'es': "Proyectos recientes…", 'pt': "Projetos recentes…",
        'de': "Zuletzt verwendete Projekte…",
    },
    'enregistrer_projet': {
        'fr': "Enregistrer le projet", 'en': "Save the project",
        'es': "Guardar el proyecto", 'pt': "Guardar o projeto",
        'de': "Projekt speichern",
    },
    'panel_enregistrer_projet': {
        'fr': "Enregistrer", 'en': "Save", 'es': "Guardar",
        'pt': "Guardar", 'de': "Speichern",
    },
    'enregistrer_projet_sous': {
        'fr': "Enregistrer sous", 'en': "Save as", 'es': "Guardar como",
        'pt': "Guardar como", 'de': "Speichern unter",
    },
    'charger_projet': {
        'fr': "Charger un projet", 'en': "Open a project",
        'es': "Abrir un proyecto", 'pt': "Abrir um projeto",
        'de': "Projekt öffnen",
    },
    'import_dxf': {
        'fr': "Importer DXF / DWG", 'en': "Import DXF / DWG",
        'es': "Importar DXF / DWG", 'pt': "Importar DXF / DWG",
        'de': "DXF / DWG importieren",
    },
    'import_star_dt': {
        'fr': "Importer Star-DT (GML)", 'en': "Import Star-DT (GML)",
        'es': "Importar Star-DT (GML)", 'pt': "Importar Star-DT (GML)",
        'de': "Star-DT (GML) importieren",
    },

    # ── Groupe Général ───────────────────────────────────────────────────
    'renseignement': {
        'fr': "Renseigner un élément", 'en': "Edit an element's attributes",
        'es': "Rellenar un elemento", 'pt': "Preencher um elemento",
        'de': "Element ausfüllen",
    },
    'tableau_saisie': {
        'fr': "Tableau de saisie - pente", 'en': "Data entry table - slope",
        'es': "Tabla de entrada - pendiente", 'pt': "Tabela de entrada - declive",
        'de': "Eingabetabelle - Gefälle",
    },
    'insert_regard': {
        'fr': "Insérer un regard sur conduite",
        'en': "Insert a manhole on a pipe",
        'es': "Insertar un pozo en la tubería",
        'pt': "Inserir uma caixa na conduta",
        'de': "Schacht in Leitung einfügen",
    },
    'move': {
        'fr': "Déplacer un ouvrage", 'en': "Move a structure",
        'es': "Mover una obra", 'pt': "Mover uma estrutura",
        'de': "Bauwerk verschieben",
    },
    'copy_attributes': {
        'fr': "Copier les attributs", 'en': "Copy attributes",
        'es': "Copiar los atributos", 'pt': "Copiar os atributos",
        'de': "Attribute kopieren",
    },
    'delete': {
        'fr': "Effacer un élément", 'en': "Delete an element",
        'es': "Borrar un elemento", 'pt': "Apagar um elemento",
        'de': "Element löschen",
    },
    'config': {
        'fr': "Configurer les couches", 'en': "Configure the layers",
        'es': "Configurar las capas", 'pt': "Configurar as camadas",
        'de': "Layer konfigurieren",
    },
    'panel_config': {
        'fr': "Configuration rapide", 'en': "Quick setup",
        'es': "Configuración rápida", 'pt': "Configuração rápida",
        'de': "Schnellkonfiguration",
    },

    # ── Groupes EU / EP ──────────────────────────────────────────────────
    'conduite_eu': {
        'fr': "Dessiner une conduite EU", 'en': "Draw an EU pipe",
        'es': "Dibujar una tubería EU", 'pt': "Desenhar uma conduta EU",
        'de': "EU-Leitung zeichnen",
    },
    'conduite_ep': {
        'fr': "Dessiner une conduite EP", 'en': "Draw an EP pipe",
        'es': "Dibujar una tubería EP", 'pt': "Desenhar uma conduta EP",
        'de': "EP-Leitung zeichnen",
    },
    'branchement_eu': {
        'fr': "Dessiner un branchement EU", 'en': "Draw an EU service connection",
        'es': "Dibujar una acometida EU", 'pt': "Desenhar um ramal EU",
        'de': "EU-Hausanschluss zeichnen",
    },
    'branchement_ep': {
        'fr': "Dessiner un branchement EP", 'en': "Draw an EP service connection",
        'es': "Dibujar una acometida EP", 'pt': "Desenhar um ramal EP",
        'de': "EP-Hausanschluss zeichnen",
    },
    'profil_eu': {
        'fr': "Profil en long EU", 'en': "EU longitudinal profile",
        'es': "Perfil longitudinal EU", 'pt': "Perfil longitudinal EU",
        'de': "EU-Längsschnitt",
    },
    'profil_ep': {
        'fr': "Profil en long EP", 'en': "EP longitudinal profile",
        'es': "Perfil longitudinal EP", 'pt': "Perfil longitudinal EP",
        'de': "EP-Längsschnitt",
    },
    'coupe_eu': {
        'fr': "Coupe transversale EU", 'en': "EU cross section",
        'es': "Sección transversal EU", 'pt': "Corte transversal EU",
        'de': "EU-Querschnitt",
    },
    'coupe_ep': {
        'fr': "Coupe transversale EP", 'en': "EP cross section",
        'es': "Sección transversal EP", 'pt': "Corte transversal EP",
        'de': "EP-Querschnitt",
    },
    'renommer_eu': {
        'fr': "Renuméroter regards/tabourets EU",
        'en': "Renumber EU manholes / inspection chambers",
        'es': "Renumerar pozos/arquetas EU",
        'pt': "Renumerar caixas/câmaras EU",
        'de': "EU-Schächte/Anschlussschächte neu nummerieren",
    },
    'renommer_ep': {
        'fr': "Renuméroter regards/tabourets EP",
        'en': "Renumber EP manholes / inspection chambers",
        'es': "Renumerar pozos/arquetas EP",
        'pt': "Renumerar caixas/câmaras EP",
        'de': "EP-Schächte/Anschlussschächte neu nummerieren",
    },

    # ── Groupe Étiquettes ────────────────────────────────────────────────
    'creer_etiquettes': {
        'fr': "Créer les étiquettes", 'en': "Create the labels",
        'es': "Crear las etiquetas", 'pt': "Criar os rótulos",
        'de': "Beschriftungen erstellen",
    },
    'afficher_etiquettes': {
        'fr': "Afficher / Masquer les étiquettes", 'en': "Show / Hide the labels",
        'es': "Mostrar / Ocultar las etiquetas",
        'pt': "Mostrar / Ocultar os rótulos",
        'de': "Beschriftungen ein-/ausblenden",
    },
    'taille_etiquettes': {
        'fr': "Taille des étiquettes", 'en': "Label size",
        'es': "Tamaño de las etiquetas", 'pt': "Tamanho dos rótulos",
        'de': "Beschriftungsgröße",
    },
    'forcer_etiquettes': {
        'fr': "Forcer toutes les étiquettes visibles (décalage auto)",
        'en': "Force all labels visible (automatic offset)",
        'es': "Forzar todas las etiquetas visibles (desplazamiento automático)",
        'pt': "Forçar todos os rótulos visíveis (deslocamento automático)",
        'de': "Alle Beschriftungen sichtbar erzwingen (automatischer Versatz)",
    },
    'panel_forcer_etiquettes': {
        'fr': "Forcer toutes les étiquettes visibles",
        'en': "Force all labels visible",
        'es': "Forzar todas las etiquetas visibles",
        'pt': "Forçar todos os rótulos visíveis",
        'de': "Alle Beschriftungen sichtbar erzwingen",
    },
    'affichage_etiquettes': {
        'fr': "Gestion de l'affichage des étiquettes",
        'en': "Label display management",
        'es': "Gestión de la visualización de etiquetas",
        'pt': "Gestão da exibição dos rótulos",
        'de': "Verwaltung der Beschriftungsanzeige",
    },
    'annotation': {
        'fr': "Placer une annotation texte", 'en': "Place a text annotation",
        'es': "Colocar una anotación de texto",
        'pt': "Colocar uma anotação de texto",
        'de': "Textanmerkung platzieren",
    },

    # ── Groupe Sorties & Impression ──────────────────────────────────────
    'imprimer': {
        'fr': "Imprimer / Exporter PDF/DXF", 'en': "Print / Export PDF/DXF",
        'es': "Imprimir / Exportar PDF/DXF", 'pt': "Imprimir / Exportar PDF/DXF",
        'de': "Drucken / PDF/DXF exportieren",
    },
    'profil_groupe': {
        'fr': "Profil groupé EU + EP", 'en': "Combined EU + EP profile",
        'es': "Perfil agrupado EU + EP", 'pt': "Perfil agrupado EU + EP",
        'de': "Kombiniertes EU + EP Profil",
    },
    'coupe_transversale': {
        'fr': "Coupe transversale des tranchées", 'en': "Trench cross section",
        'es': "Sección transversal de las zanjas",
        'pt': "Corte transversal das valas",
        'de': "Grabenquerschnitt",
    },
    'cubature': {
        'fr': "Cubature / Remblai tranchées",
        'en': "Trench volumes / backfill",
        'es': "Cubicación / Relleno de zanjas",
        'pt': "Cubagem / Aterro de valas",
        'de': "Massenberechnung / Grabenverfüllung",
    },
    'coupe_tranchee_composee': {
        'fr': "Dessinateur – Coupe de tranchées composée",
        'en': "Designer – Composite trench section",
        'es': "Diseñador – Sección de zanja compuesta",
        'pt': "Desenhador – Corte de vala composto",
        'de': "Zeichner – Zusammengesetzter Grabenschnitt",
    },
    'panel_coupe_tranchee_composee': {
        'fr': "Dessinateur – Coupe de tranchées",
        'en': "Designer – Trench section",
        'es': "Diseñador – Sección de zanja",
        'pt': "Desenhador – Corte de vala",
        'de': "Zeichner – Grabenschnitt",
    },
    'export_stareau': {
        'fr': "Exporter au format StaR-Eau", 'en': "Export to StaR-Eau format",
        'es': "Exportar al formato StaR-Eau", 'pt': "Exportar para o formato StaR-Eau",
        'de': "In das StaR-Eau-Format exportieren",
    },
    'panel_export_stareau': {
        'fr': "Exporter StaR-Eau (GPKG)", 'en': "Export StaR-Eau (GPKG)",
        'es': "Exportar StaR-Eau (GPKG)", 'pt': "Exportar StaR-Eau (GPKG)",
        'de': "StaR-Eau exportieren (GPKG)",
    },

    # ── Groupe Fond de carte ─────────────────────────────────────────────
    'fond_projet': {
        'fr': "Mise en place fond de projet", 'en': "Set up the project basemap",
        'es': "Configurar el mapa base del proyecto",
        'pt': "Configurar o mapa base do projeto",
        'de': "Projekt-Hintergrundkarte einrichten",
    },
    'panel_fond_projet': {
        'fr': "Fond de projet (6 couches)", 'en': "Project basemap (6 layers)",
        'es': "Mapa base del proyecto (6 capas)",
        'pt': "Mapa base do projeto (6 camadas)",
        'de': "Projekt-Hintergrundkarte (6 Layer)",
    },
    'osm_desature': {
        'fr': "OSM Desature", 'en': "Desaturated OSM", 'es': "OSM desaturado",
        'pt': "OSM dessaturado", 'de': "OSM entsättigt",
    },
    'ortho_ign': {
        'fr': "Ortho IGN (BD ORTHO nationale)",
        'en': "IGN orthophoto (national BD ORTHO)",
        'es': "Ortofoto IGN (BD ORTHO nacional)",
        'pt': "Ortofoto IGN (BD ORTHO nacional)",
        'de': "IGN-Orthofoto (nationale BD ORTHO)",
    },
    'pci_parcelles': {
        'fr': "PCI Vecteur Parcelles", 'en': "PCI Vector – Cadastral parcels",
        'es': "PCI Vector – Parcelas catastrales",
        'pt': "PCI Vetor – Parcelas cadastrais",
        'de': "PCI Vektor – Flurstücke",
    },
    'pci_bati': {
        'fr': "PCI Vecteur Bâti", 'en': "PCI Vector – Buildings",
        'es': "PCI Vector – Edificios", 'pt': "PCI Vetor – Edifícios",
        'de': "PCI Vektor – Gebäude",
    },
    'ban_vecteur': {
        'fr': "BAN Adresses", 'en': "BAN addresses", 'es': "Direcciones BAN",
        'pt': "Endereços BAN", 'de': "BAN-Adressen",
    },
    'panel_ban_vecteur': {
        'fr': "BAN Adresses – vecteur (emprise)",
        'en': "BAN addresses – vector (current extent)",
        'es': "Direcciones BAN – vector (extensión actual)",
        'pt': "Endereços BAN – vetor (extensão atual)",
        'de': "BAN-Adressen – Vektor (aktueller Ausschnitt)",
    },
    'nom_voie': {
        'fr': "Noms de rue BD TOPO (emprise)",
        'en': "BD TOPO street names (current extent)",
        'es': "Nombres de calles BD TOPO (extensión actual)",
        'pt': "Nomes de ruas BD TOPO (extensão atual)",
        'de': "BD TOPO Straßennamen (aktueller Ausschnitt)",
    },

    # ── Divers ───────────────────────────────────────────────────────────
    'about': {
        'fr': "À propos", 'en': "About", 'es': "Acerca de",
        'pt': "Acerca de", 'de': "Über",
    },

    # ── Fenêtre des projets récents ──────────────────────────────────────
    'recents_titre': {
        'fr': "Projets récents", 'en': "Recent projects",
        'es': "Proyectos recientes", 'pt': "Projetos recentes",
        'de': "Zuletzt verwendete Projekte",
    },
    'recents_invite': {
        'fr': "Choisissez le projet à rouvrir :",
        'en': "Choose the project to reopen:",
        'es': "Elija el proyecto que desea reabrir:",
        'pt': "Escolha o projeto a reabrir:",
        'de': "Wählen Sie das erneut zu öffnende Projekt:",
    },
    'recents_vide': {
        'fr': "Aucun projet récent.\n\nLes projets enregistrés ou ouverts "
              "apparaîtront ici.",
        'en': "No recent projects.\n\nProjects you save or open will appear here.",
        'es': "Ningún proyecto reciente.\n\nLos proyectos guardados o abiertos "
              "aparecerán aquí.",
        'pt': "Nenhum projeto recente.\n\nOs projetos guardados ou abertos "
              "aparecerão aqui.",
        'de': "Keine kürzlich verwendeten Projekte.\n\nGespeicherte oder "
              "geöffnete Projekte erscheinen hier.",
    },
    'recents_date_inconnue': {
        'fr': "date inconnue", 'en': "unknown date", 'es': "fecha desconocida",
        'pt': "data desconhecida", 'de': "unbekanntes Datum",
    },
    'ouvrir': {
        'fr': "Ouvrir", 'en': "Open", 'es': "Abrir",
        'pt': "Abrir", 'de': "Öffnen",
    },
    'annuler': {
        'fr': "Annuler", 'en': "Cancel", 'es': "Cancelar",
        'pt': "Cancelar", 'de': "Abbrechen",
    },
    'fichier_introuvable': {
        'fr': "Fichier introuvable, il a été retiré des projets récents :\n{path}",
        'en': "File not found; it has been removed from recent projects:\n{path}",
        'es': "Archivo no encontrado; se ha eliminado de los proyectos "
              "recientes:\n{path}",
        'pt': "Ficheiro não encontrado; foi removido dos projetos recentes:\n{path}",
        'de': "Datei nicht gefunden; sie wurde aus den zuletzt verwendeten "
              "Projekten entfernt:\n{path}",
    },
    'ouvrir_projet_titre': {
        'fr': "Ouvrir un projet CanaPlan", 'en': "Open a CanaPlan project",
        'es': "Abrir un proyecto CanaPlan", 'pt': "Abrir um projeto CanaPlan",
        'de': "CanaPlan-Projekt öffnen",
    },
    'filtre_projet': {
        'fr': "Projet CanaPlan (*.bet)", 'en': "CanaPlan project (*.bet)",
        'es': "Proyecto CanaPlan (*.bet)", 'pt': "Projeto CanaPlan (*.bet)",
        'de': "CanaPlan-Projekt (*.bet)",
    },

    # ─────────────────────────────────────────────────────────────────────
    #  Glossaire commun : boutons, en-têtes de colonnes, termes métier
    #  réutilisés par plusieurs dialogues.
    # ─────────────────────────────────────────────────────────────────────
    'appliquer': {
        'fr': "Appliquer", 'en': "Apply", 'es': "Aplicar",
        'pt': "Aplicar", 'de': "Anwenden",
    },
    'fermer': {
        'fr': "Fermer", 'en': "Close", 'es': "Cerrar",
        'pt': "Fechar", 'de': "Schließen",
    },
    'erreur': {
        'fr': "Erreur", 'en': "Error", 'es': "Error",
        'pt': "Erro", 'de': "Fehler",
    },
    'col_reseau': {
        'fr': "Réseau", 'en': "Network", 'es': "Red",
        'pt': "Rede", 'de': "Netz",
    },
    'col_type': {
        'fr': "Type", 'en': "Type", 'es': "Tipo",
        'pt': "Tipo", 'de': "Typ",
    },
    'col_materiau': {
        'fr': "Matériau", 'en': "Material", 'es': "Material",
        'pt': "Material", 'de': "Material",
    },
    'col_diametre': {
        'fr': "Diamètre (mm)", 'en': "Diameter (mm)", 'es': "Diámetro (mm)",
        'pt': "Diâmetro (mm)", 'de': "Durchmesser (mm)",
    },
    'col_longueur': {
        'fr': "Longueur (m)", 'en': "Length (m)", 'es': "Longitud (m)",
        'pt': "Comprimento (m)", 'de': "Länge (m)",
    },
    'col_pente': {
        'fr': "Pente (%)", 'en': "Slope (%)", 'es': "Pendiente (%)",
        'pt': "Declive (%)", 'de': "Gefälle (%)",
    },
    'col_troncon': {
        'fr': "Tronçon", 'en': "Pipe segment", 'es': "Tramo",
        'pt': "Troço", 'de': "Haltung",
    },
    'col_branchement': {
        'fr': "Branchement", 'en': "Service connection", 'es': "Acometida",
        'pt': "Ramal", 'de': "Hausanschluss",
    },
    'col_ouvrage': {
        'fr': "Ouvrage", 'en': "Structure", 'es': "Obra",
        'pt': "Estrutura", 'de': "Bauwerk",
    },
    'col_fe_amont': {
        'fr': "FE amont (m NGF)", 'en': "Upstream invert (m)",
        'es': "Cota clave aguas arriba (m)", 'pt': "Soleira montante (m)",
        'de': "Sohle oben (m)",
    },
    'col_fe_aval': {
        'fr': "FE aval (m NGF)", 'en': "Downstream invert (m)",
        'es': "Cota clave aguas abajo (m)", 'pt': "Soleira jusante (m)",
        'de': "Sohle unten (m)",
    },
    'col_fe': {
        'fr': "FE (m NGF)", 'en': "Invert level (m)", 'es': "Cota de solera (m)",
        'pt': "Cota de soleira (m)", 'de': "Sohlhöhe (m)",
    },
    'col_fe_tabouret': {
        'fr': "FE tabouret (m NGF)", 'en': "Chamber invert (m)",
        'es': "Cota solera arqueta (m)", 'pt': "Soleira da câmara (m)",
        'de': "Sohle Anschlussschacht (m)",
    },
    'col_cote_piquage': {
        'fr': "Cote piquage (m NGF)", 'en': "Tap-in level (m)",
        'es': "Cota de conexión (m)", 'pt': "Cota de ligação (m)",
        'de': "Anschlusshöhe (m)",
    },
    'col_tn': {
        'fr': "TN (m NGF)", 'en': "Ground level (m)", 'es': "Cota terreno (m)",
        'pt': "Cota do terreno (m)", 'de': "Geländehöhe (m)",
    },
    'col_profondeur': {
        'fr': "Profondeur (m)", 'en': "Depth (m)", 'es': "Profundidad (m)",
        'pt': "Profundidade (m)", 'de': "Tiefe (m)",
    },
    'col_sens_calcul': {
        'fr': "Sens calcul", 'en': "Calculation direction",
        'es': "Sentido de cálculo", 'pt': "Sentido de cálculo",
        'de': "Berechnungsrichtung",
    },
    'col_long_cumulee': {
        'fr': "Longueur cumulée (m)", 'en': "Cumulative length (m)",
        'es': "Longitud acumulada (m)", 'pt': "Comprimento acumulado (m)",
        'de': "Kumulierte Länge (m)",
    },
    'col_pente_suivant': {
        'fr': "Pente vers suivant (%)", 'en': "Slope to next (%)",
        'es': "Pendiente al siguiente (%)", 'pt': "Declive para o seguinte (%)",
        'de': "Gefälle zum nächsten (%)",
    },
    # Libellés de champs partagés (renseignement, étiquettes, profils)
    'col_nom': {
        'fr': "Nom", 'en': "Name", 'es': "Nombre", 'pt': "Nome",
        'de': "Name",
    },
    'col_regard': {
        'fr': "Regard", 'en': "Manhole", 'es': "Pozo de registro",
        'pt': "Câmara de visita", 'de': "Schacht",
    },
    'col_tabouret': {
        'fr': "Tabouret", 'en': "Inspection chamber", 'es': "Arqueta",
        'pt': "Caixa de ramal", 'de': "Anschlussschacht",
    },
    'col_conduite': {
        'fr': "Conduite", 'en': "Pipe", 'es': "Tubería", 'pt': "Conduta",
        'de': "Leitung",
    },
    'col_abscisse': {
        'fr': "Abscisse (m)", 'en': "Chainage (m)", 'es': "Abscisa (m)",
        'pt': "Abcissa (m)", 'de': "Station (m)",
    },
    'col_fe_radier': {
        'fr': "FE radier (m NGF)", 'en': "Invert level (m)",
        'es': "Cota de solera (m)", 'pt': "Cota de soleira (m)",
        'de': "Sohlhöhe (m)",
    },
    'col_fe_entree': {
        'fr': "FE entrée (m NGF)", 'en': "Inlet invert level (m)",
        'es': "Cota de entrada (m)", 'pt': "Cota de entrada (m)",
        'de': "Zulaufsohle (m)",
    },
    'col_fe_radier_court': {
        'fr': "FE radier", 'en': "Invert", 'es': "Solera",
        'pt': "Soleira", 'de': "Sohle",
    },
    'col_fe_entree_court': {
        'fr': "FE entrée", 'en': "Inlet invert", 'es': "Entrada",
        'pt': "Entrada", 'de': "Zulaufsohle",
    },
    'col_fe_rad_court': {
        'fr': "FE rad. (m)", 'en': "Invert (m)", 'es': "Solera (m)",
        'pt': "Soleira (m)", 'de': "Sohle (m)",
    },
    'col_tn_court': {
        'fr': "TN (m)", 'en': "Ground (m)", 'es': "Terreno (m)",
        'pt': "Terreno (m)", 'de': "Gelände (m)",
    },
    'col_prof_court': {
        'fr': "Prof. (m)", 'en': "Depth (m)", 'es': "Prof. (m)",
        'pt': "Prof. (m)", 'de': "Tiefe (m)",
    },
    'col_long_court': {
        'fr': "Long. (m)", 'en': "Length (m)", 'es': "Long. (m)",
        'pt': "Compr. (m)", 'de': "Länge (m)",
    },
    'col_long_cumulee_court': {
        'fr': "L. cumulée (m)", 'en': "Cumul. length (m)",
        'es': "L. acumulada (m)", 'pt': "C. acumulado (m)",
        'de': "Kum. Länge (m)",
    },
    # Profil en long et profil groupé
    'pf_titre_profil': {
        'fr': "Profil en long – Réseau {reseau}  ·  {debut} → {fin}",
        'en': "Long section – {reseau} network  ·  {debut} → {fin}",
        'es': "Perfil longitudinal – Red {reseau}  ·  {debut} → {fin}",
        'pt': "Perfil longitudinal – Rede {reseau}  ·  {debut} → {fin}",
        'de': "Längsschnitt – Netz {reseau}  ·  {debut} → {fin}",
    },
    'pf_altitude': {
        'fr': "Altitude (m NGF)", 'en': "Elevation (m)", 'es': "Cota (m)",
        'pt': "Cota (m)", 'de': "Höhe (m)",
    },
    'pf_distance_projetee': {
        'fr': "Distance projetée (m)", 'en': "Projected distance (m)",
        'es': "Distancia proyectada (m)", 'pt': "Distância projetada (m)",
        'de': "Projizierte Entfernung (m)",
    },
    # Export groupé
    'exp_profils_reseau': {
        'fr': "Profils {code}  (PDF)", 'en': "{code} profiles  (PDF)",
        'es': "Perfiles {code}  (PDF)", 'pt': "Perfis {code}  (PDF)",
        'de': "{code}-Längsschnitte  (PDF)",
    },
    # Gestion de l'affichage des étiquettes
    'ea_tout_afficher': {
        'fr': "Tout afficher", 'en': "Show all", 'es': "Mostrar todo",
        'pt': "Mostrar tudo", 'de': "Alle anzeigen",
    },
    'ea_tout_masquer': {
        'fr': "Tout masquer", 'en': "Hide all", 'es': "Ocultar todo",
        'pt': "Ocultar tudo", 'de': "Alle ausblenden",
    },
    'ea_tout': {
        'fr': "Tout", 'en': "All", 'es': "Todo", 'pt': "Tudo",
        'de': "Alle",
    },
    'ea_aucun': {
        'fr': "Aucun", 'en': "None", 'es': "Ninguno", 'pt': "Nenhum",
        'de': "Keine",
    },
    # Aperçu de chaîne
    'cp_aucune_chaine': {
        'fr': "Aucune chaîne sélectionnée — utilisez « Rechercher la chaîne » "
              "ci-dessus.",
        'en': "No chain selected — use “Find the chain” above.",
        'es': "Ninguna cadena seleccionada — use «Buscar la cadena» arriba.",
        'pt': "Nenhuma cadeia selecionada — use «Procurar a cadeia» acima.",
        'de': "Keine Kette ausgewählt — nutzen Sie oben „Kette suchen“.",
    },

    # ─────────────────────────────────────────────────────────────────────
    #  Tableau de saisie - pente
    # ─────────────────────────────────────────────────────────────────────
    'ts_mode_fe': {
        'fr': "🔒 FE amont + aval", 'en': "🔒 Upstream + downstream invert",
        'es': "🔒 Solera aguas arriba + abajo",
        'pt': "🔒 Soleira montante + jusante",
        'de': "🔒 Sohle oben + unten",
    },
    'ts_mode_pente_aval': {
        'fr': "🔒 Pente → FE aval", 'en': "🔒 Slope → downstream invert",
        'es': "🔒 Pendiente → solera aguas abajo",
        'pt': "🔒 Declive → soleira jusante",
        'de': "🔒 Gefälle → Sohle unten",
    },
    'ts_mode_pente_amont': {
        'fr': "🔒 Pente → FE amont", 'en': "🔒 Slope → upstream invert",
        'es': "🔒 Pendiente → solera aguas arriba",
        'pt': "🔒 Declive → soleira montante",
        'de': "🔒 Gefälle → Sohle oben",
    },
    'ts_mode_fe_aide': {
        'fr': "FE amont et FE aval connus → la pente est calculée.",
        'en': "Upstream and downstream inverts known → the slope is computed.",
        'es': "Soleras aguas arriba y abajo conocidas → se calcula la pendiente.",
        'pt': "Soleiras a montante e a jusante conhecidas → o declive é calculado.",
        'de': "Sohlhöhen oben und unten bekannt → das Gefälle wird berechnet.",
    },
    'ts_mode_pente_aval_aide': {
        'fr': "FE amont + pente connus → FE aval est calculé et appliqué au "
              "regard/tabouret aval.",
        'en': "Upstream invert + slope known → the downstream invert is computed "
              "and applied to the downstream structure.",
        'es': "Solera aguas arriba + pendiente conocidas → se calcula la solera "
              "aguas abajo y se aplica a la obra situada aguas abajo.",
        'pt': "Soleira a montante + declive conhecidos → a soleira a jusante é "
              "calculada e aplicada à estrutura a jusante.",
        'de': "Sohle oben + Gefälle bekannt → die Sohle unten wird berechnet und "
              "auf das untere Bauwerk angewendet.",
    },
    'ts_mode_pente_amont_aide': {
        'fr': "FE aval + pente connus → FE amont est calculé et appliqué au "
              "regard/tabouret amont.",
        'en': "Downstream invert + slope known → the upstream invert is computed "
              "and applied to the upstream structure.",
        'es': "Solera aguas abajo + pendiente conocidas → se calcula la solera "
              "aguas arriba y se aplica a la obra situada aguas arriba.",
        'pt': "Soleira a jusante + declive conhecidos → a soleira a montante é "
              "calculada e aplicada à estrutura a montante.",
        'de': "Sohle unten + Gefälle bekannt → die Sohle oben wird berechnet und "
              "auf das obere Bauwerk angewendet.",
    },
    'ts_bmode_fe': {
        'fr': "🔒 Cote piquage + FE tabouret",
        'en': "🔒 Tap-in level + chamber invert",
        'es': "🔒 Cota de conexión + solera arqueta",
        'pt': "🔒 Cota de ligação + soleira da caixa",
        'de': "🔒 Anschlusshöhe + Schachtsohle",
    },
    'ts_bmode_pente_fe': {
        'fr': "🔒 Pente → FE tabouret", 'en': "🔒 Slope → chamber invert",
        'es': "🔒 Pendiente → solera arqueta",
        'pt': "🔒 Declive → soleira da caixa",
        'de': "🔒 Gefälle → Schachtsohle",
    },
    'ts_bmode_pente_cote': {
        'fr': "🔒 Pente → cote piquage", 'en': "🔒 Slope → tap-in level",
        'es': "🔒 Pendiente → cota de conexión",
        'pt': "🔒 Declive → cota de ligação",
        'de': "🔒 Gefälle → Anschlusshöhe",
    },
    'ts_bmode_fe_aide': {
        'fr': "Cote piquage et FE tabouret connus → la pente est calculée.\n"
              "La cote de piquage suit automatiquement les FE de la conduite mère.",
        'en': "Tap-in level and chamber invert known → the slope is computed.\n"
              "The tap-in level follows the parent pipe inverts automatically.",
        'es': "Cota de conexión y solera de la arqueta conocidas → se calcula la "
              "pendiente.\nLa cota de conexión sigue automáticamente las soleras "
              "de la tubería madre.",
        'pt': "Cota de ligação e soleira da caixa conhecidas → o declive é "
              "calculado.\nA cota de ligação acompanha automaticamente as soleiras "
              "da conduta principal.",
        'de': "Anschlusshöhe und Schachtsohle bekannt → das Gefälle wird "
              "berechnet.\nDie Anschlusshöhe folgt automatisch den Sohlen der "
              "Hauptleitung.",
    },
    'ts_bmode_pente_fe_aide': {
        'fr': "Cote piquage + pente connus → FE tabouret est calculé et appliqué "
              "au tabouret/regard.\nLa cote de piquage suit automatiquement les FE "
              "de la conduite mère.",
        'en': "Tap-in level + slope known → the chamber invert is computed and "
              "applied to the structure.\nThe tap-in level follows the parent pipe "
              "inverts automatically.",
        'es': "Cota de conexión + pendiente conocidas → se calcula la solera de la "
              "arqueta y se aplica a la obra.\nLa cota de conexión sigue "
              "automáticamente las soleras de la tubería madre.",
        'pt': "Cota de ligação + declive conhecidos → a soleira da caixa é "
              "calculada e aplicada à estrutura.\nA cota de ligação acompanha "
              "automaticamente as soleiras da conduta principal.",
        'de': "Anschlusshöhe + Gefälle bekannt → die Schachtsohle wird berechnet "
              "und angewendet.\nDie Anschlusshöhe folgt automatisch den Sohlen der "
              "Hauptleitung.",
    },
    'ts_bmode_pente_cote_aide': {
        'fr': "FE tabouret + pente connus → la cote de piquage est calculée.\n"
              "⚠ Dans ce mode la cote de piquage ne suit plus la conduite mère.",
        'en': "Chamber invert + slope known → the tap-in level is computed.\n"
              "⚠ In this mode the tap-in level no longer follows the parent pipe.",
        'es': "Solera de la arqueta + pendiente conocidas → se calcula la cota de "
              "conexión.\n⚠ En este modo la cota de conexión ya no sigue la tubería "
              "madre.",
        'pt': "Soleira da caixa + declive conhecidos → a cota de ligação é "
              "calculada.\n⚠ Neste modo a cota de ligação deixa de acompanhar a "
              "conduta principal.",
        'de': "Schachtsohle + Gefälle bekannt → die Anschlusshöhe wird berechnet.\n"
              "⚠ In diesem Modus folgt die Anschlusshöhe der Hauptleitung nicht mehr.",
    },
    'ts_chaine_absente': {
        'fr': "Aucune chaîne trouvée entre {debut} et {fin}. Vérifiez qu'un tracé "
              "de conduites les relie bien.",
        'en': "No chain found between {debut} and {fin}. Check that a run of pipes "
              "actually connects them.",
        'es': "No se ha encontrado ninguna cadena entre {debut} y {fin}. Compruebe "
              "que un trazado de tuberías los conecta.",
        'pt': "Nenhuma cadeia encontrada entre {debut} e {fin}. Verifique que um "
              "traçado de condutas os liga.",
        'de': "Keine Kette zwischen {debut} und {fin} gefunden. Prüfen Sie, ob ein "
              "Leitungszug sie verbindet.",
    },
    'ts_chaine_trouvee': {
        'fr': "✓ Chaîne trouvée : {nb} ouvrages, {longueur} m au total. Vous "
              "pouvez modifier le tableau ci-dessous ou utiliser une des 3 actions.",
        'en': "✓ Chain found: {nb} structures, {longueur} m in total. You can edit "
              "the table below or use one of the 3 actions.",
        'es': "✓ Cadena encontrada: {nb} obras, {longueur} m en total. Puede "
              "modificar la tabla siguiente o usar una de las 3 acciones.",
        'pt': "✓ Cadeia encontrada: {nb} estruturas, {longueur} m no total. Pode "
              "alterar a tabela abaixo ou usar uma das 3 ações.",
        'de': "✓ Kette gefunden: {nb} Bauwerke, insgesamt {longueur} m. Sie können "
              "die Tabelle unten bearbeiten oder eine der 3 Aktionen nutzen.",
    },
    'ts_fe_inconnu': {
        'fr': "Le FE de {ouvrage} est inconnu — renseignez-le d'abord (dans le "
              "tableau ou l'onglet Regards).",
        'en': "The invert level of {ouvrage} is unknown — fill it in first (in the "
              "table or the Manholes tab).",
        'es': "La cota de solera de {ouvrage} es desconocida — introdúzcala primero "
              "(en la tabla o en la pestaña Pozos).",
        'pt': "A cota de soleira de {ouvrage} é desconhecida — indique-a primeiro "
              "(na tabela ou no separador Câmaras).",
        'de': "Die Sohlhöhe von {ouvrage} ist unbekannt — tragen Sie sie zuerst ein "
              "(in der Tabelle oder im Reiter Schächte).",
    },
    'ts_pente_appliquee': {
        'fr': "✓ Pente de {pente} % appliquée depuis {ouvrage} — FE, profondeurs, "
              "pentes des conduites et cotes de piquage mis à jour.",
        'en': "✓ Slope of {pente} % applied from {ouvrage} — inverts, depths, pipe "
              "slopes and tap-in levels updated.",
        'es': "✓ Pendiente de {pente} % aplicada desde {ouvrage} — soleras, "
              "profundidades, pendientes y cotas de conexión actualizadas.",
        'pt': "✓ Declive de {pente} % aplicado a partir de {ouvrage} — soleiras, "
              "profundidades, declives e cotas de ligação atualizados.",
        'de': "✓ Gefälle von {pente} % ab {ouvrage} angewendet — Sohlen, Tiefen, "
              "Leitungsgefälle und Anschlusshöhen aktualisiert.",
    },
    'ts_pente_calculee': {
        'fr': "✓ Pente calculée = {pente} % (sur {longueur} m), appliquée.",
        'en': "✓ Computed slope = {pente} % (over {longueur} m), applied.",
        'es': "✓ Pendiente calculada = {pente} % (en {longueur} m), aplicada.",
        'pt': "✓ Declive calculado = {pente} % (em {longueur} m), aplicado.",
        'de': "✓ Berechnetes Gefälle = {pente} % (auf {longueur} m), angewendet.",
    },
    'ts_profondeur_appliquee': {
        'fr': "✓ Profondeur {prof} m appliquée à {nb} ouvrage(s) — pentes des "
              "conduites et cotes de piquage mises à jour.",
        'en': "✓ Depth {prof} m applied to {nb} structure(s) — pipe slopes and "
              "tap-in levels updated.",
        'es': "✓ Profundidad {prof} m aplicada a {nb} obra(s) — pendientes y "
              "cotas de conexión actualizadas.",
        'pt': "✓ Profundidade {prof} m aplicada a {nb} estrutura(s) — declives e "
              "cotas de ligação atualizados.",
        'de': "✓ Tiefe {prof} m auf {nb} Bauwerk(e) angewendet — Leitungsgefälle "
              "und Anschlusshöhen aktualisiert.",
    },
    'ts_sans_tn': {
        'fr': " ({nb} sans TN connu — FE non recalculé)",
        'en': " ({nb} without a known ground level — invert not recomputed)",
        'es': " ({nb} sin cota de terreno conocida — solera no recalculada)",
        'pt': " ({nb} sem cota de terreno conhecida — soleira não recalculada)",
        'de': " ({nb} ohne bekannte Geländehöhe — Sohle nicht neu berechnet)",
    },
    'ts_titre': {
        'fr': "Tableau de saisie - pente", 'en': "Data entry table - slope",
        'es': "Tabla de entrada - pendiente", 'pt': "Tabela de entrada - declive",
        'de': "Eingabetabelle - Gefälle",
    },
    'ts_titre_reseau': {
        'fr': "Tableau de saisie - pente — Réseau {reseau}",
        'en': "Data entry table - slope — {reseau} network",
        'es': "Tabla de entrada - pendiente — Red {reseau}",
        'pt': "Tabela de entrada - declive — Rede {reseau}",
        'de': "Eingabetabelle - Gefälle — Netz {reseau}",
    },
    'ts_reseau_label': {
        'fr': "Réseau :", 'en': "Network:", 'es': "Red:",
        'pt': "Rede:", 'de': "Netz:",
    },
    'ts_filtrer': {
        'fr': "Filtrer par nom…", 'en': "Filter by name…",
        'es': "Filtrar por nombre…", 'pt': "Filtrar por nome…",
        'de': "Nach Name filtern…",
    },
    'ts_next_missing': {
        'fr': "⏭ Valeur manquante suivante", 'en': "⏭ Next missing value",
        'es': "⏭ Siguiente valor ausente", 'pt': "⏭ Próximo valor em falta",
        'de': "⏭ Nächster fehlender Wert",
    },
    'ts_next_missing_tip': {
        'fr': "Sélectionne la prochaine cellule en rouge (valeur manquante).",
        'en': "Selects the next red cell (missing value).",
        'es': "Selecciona la siguiente celda en rojo (valor ausente).",
        'pt': "Seleciona a próxima célula a vermelho (valor em falta).",
        'de': "Wählt die nächste rote Zelle aus (fehlender Wert).",
    },
    'ts_valeur_ph': {
        'fr': "valeur…", 'en': "value…", 'es': "valor…",
        'pt': "valor…", 'de': "Wert…",
    },
    'ts_appliquer_toutes': {
        'fr': "Appliquer à toutes", 'en': "Apply to all",
        'es': "Aplicar a todas", 'pt': "Aplicar a todas",
        'de': "Auf alle anwenden",
    },
    'ts_undo': {
        'fr': "↶ Annuler la saisie (Ctrl+Z)", 'en': "↶ Undo entry (Ctrl+Z)",
        'es': "↶ Deshacer la entrada (Ctrl+Z)", 'pt': "↶ Anular a entrada (Ctrl+Z)",
        'de': "↶ Eingabe rückgängig (Strg+Z)",
    },
    'ts_apercu': {
        'fr': "Aperçu carte", 'en': "Map preview", 'es': "Vista del mapa",
        'pt': "Pré-visualização do mapa", 'de': "Kartenvorschau",
    },
    'ts_longueur_tip': {
        'fr': "Longueur définie par le tracé — non modifiable ici.",
        'en': "Length is set by the geometry — not editable here.",
        'es': "La longitud viene del trazado — no editable aquí.",
        'pt': "O comprimento vem do traçado — não editável aqui.",
        'de': "Länge ergibt sich aus der Geometrie — hier nicht änderbar.",
    },
    'ts_piquage_tip': {
        'fr': "Interpolée sur la conduite mère au PK du piquage — recalculée "
              "dès que les FE de la conduite changent.",
        'en': "Interpolated on the parent pipe at the tap-in chainage — "
              "recalculated whenever the pipe inverts change.",
        'es': "Interpolada sobre la tubería madre en el PK de conexión — "
              "se recalcula cuando cambian las cotas de la tubería.",
        'pt': "Interpolada na conduta principal no PK de ligação — recalculada "
              "sempre que as soleiras da conduta mudam.",
        'de': "Auf der Hauptleitung an der Anschlussstation interpoliert — "
              "wird bei Änderung der Leitungssohlen neu berechnet.",
    },
    'ts_cellules_sel': {
        'fr': "{n} cellules sélectionnées :", 'en': "{n} cells selected:",
        'es': "{n} celdas seleccionadas:", 'pt': "{n} células selecionadas:",
        'de': "{n} Zellen ausgewählt:",
    },
    'ts_resume': {
        'fr': "{regards} regards · {tabourets} tabourets · {conduites} conduites "
              "· {branchements} branchements — réseau {reseau} — {manquantes} "
              "valeur(s) manquante(s)",
        'en': "{regards} manholes · {tabourets} inspection chambers · "
              "{conduites} pipes · {branchements} service connections — "
              "{reseau} network — {manquantes} missing value(s)",
        'es': "{regards} pozos · {tabourets} arquetas · {conduites} tuberías · "
              "{branchements} acometidas — red {reseau} — {manquantes} "
              "valor(es) ausente(s)",
        'pt': "{regards} caixas · {tabourets} câmaras · {conduites} condutas · "
              "{branchements} ramais — rede {reseau} — {manquantes} "
              "valor(es) em falta",
        'de': "{regards} Schächte · {tabourets} Anschlussschächte · "
              "{conduites} Leitungen · {branchements} Hausanschlüsse — "
              "Netz {reseau} — {manquantes} fehlende(r) Wert(e)",
    },
    'ts_regard_depart': {
        'fr': "Regard de départ :", 'en': "Start manhole:",
        'es': "Pozo inicial:", 'pt': "Caixa inicial:",
        'de': "Startschacht:",
    },
    'ts_regard_depart_tip': {
        'fr': "Le regard à partir duquel la chaîne est parcourue.",
        'en': "The manhole the chain is traced from.",
        'es': "El pozo desde el que se recorre la cadena.",
        'pt': "A caixa a partir da qual a cadeia é percorrida.",
        'de': "Der Schacht, ab dem die Kette verfolgt wird.",
    },
    'ts_swap_tip': {
        'fr': "Inverser le regard de départ et le regard d'arrivée.",
        'en': "Swap the start and end manholes.",
        'es': "Invertir el pozo inicial y el pozo final.",
        'pt': "Inverter a caixa inicial e a caixa final.",
        'de': "Start- und Endschacht vertauschen.",
    },
    'ts_regard_arrivee': {
        'fr': "Regard d'arrivée :", 'en': "End manhole:",
        'es': "Pozo final:", 'pt': "Caixa final:",
        'de': "Endschacht:",
    },
    'ts_regard_arrivee_tip': {
        'fr': "Le regard où la chaîne doit s'arrêter.",
        'en': "The manhole where the chain stops.",
        'es': "El pozo donde la cadena se detiene.",
        'pt': "A caixa onde a cadeia termina.",
        'de': "Der Schacht, an dem die Kette endet.",
    },
    'ts_rechercher': {
        'fr': "🔍 Rechercher la chaîne", 'en': "🔍 Find the chain",
        'es': "🔍 Buscar la cadena", 'pt': "🔍 Procurar a cadeia",
        'de': "🔍 Kette suchen",
    },
    'ts_rechercher_tip': {
        'fr': "Retrouve automatiquement tous les regards, tabourets et "
              "conduites entre les deux regards choisis.",
        'en': "Automatically finds every manhole, inspection chamber and pipe "
              "between the two selected manholes.",
        'es': "Encuentra automáticamente todos los pozos, arquetas y tuberías "
              "entre los dos pozos elegidos.",
        'pt': "Encontra automaticamente todas as caixas, câmaras e condutas "
              "entre as duas caixas escolhidas.",
        'de': "Findet automatisch alle Schächte, Anschlussschächte und "
              "Leitungen zwischen den beiden gewählten Schächten.",
    },
    'ts_selectionnez_2': {
        'fr': "Sélectionnez 2 regards puis cliquez sur « Rechercher la chaîne ».",
        'en': "Select 2 manholes, then click “Find the chain”.",
        'es': "Seleccione 2 pozos y haga clic en «Buscar la cadena».",
        'pt': "Selecione 2 caixas e clique em «Procurar a cadeia».",
        'de': "Wählen Sie 2 Schächte und klicken Sie auf „Kette suchen“.",
    },
    'ts_aide_tableau': {
        'fr': "Double-cliquez une cellule pour la modifier. Les valeurs se "
              "recalculent automatiquement le long de la chaîne, puis sont "
              "reportées sur les onglets Regards, Tabourets, Conduites (pente) "
              "et Branchements (cote de piquage + pente).\nDouble-clic sur une "
              "ligne : zoom sur l'ouvrage dans QGIS.",
        'en': "Double-click a cell to edit it. Values are recalculated along "
              "the chain automatically, then carried over to the Manholes, "
              "Chambers, Pipes (slope) and Service connections (tap-in level + "
              "slope) tabs.\nDouble-click a row to zoom to the structure in QGIS.",
        'es': "Haga doble clic en una celda para editarla. Los valores se "
              "recalculan a lo largo de la cadena y se trasladan a las pestañas "
              "Pozos, Arquetas, Tuberías (pendiente) y Acometidas (cota de "
              "conexión + pendiente).\nDoble clic en una fila: zoom a la obra "
              "en QGIS.",
        'pt': "Faça duplo clique numa célula para a editar. Os valores são "
              "recalculados ao longo da cadeia e transpostos para os separadores "
              "Caixas, Câmaras, Condutas (declive) e Ramais (cota de ligação + "
              "declive).\nDuplo clique numa linha: zoom à estrutura no QGIS.",
        'de': "Doppelklicken Sie eine Zelle zum Bearbeiten. Die Werte werden "
              "entlang der Kette automatisch neu berechnet und in die Register "
              "Schächte, Anschlussschächte, Leitungen (Gefälle) und "
              "Hausanschlüsse (Anschlusshöhe + Gefälle) übernommen.\n"
              "Doppelklick auf eine Zeile: Zoom auf das Bauwerk in QGIS.",
    },
    'ts_grp1': {
        'fr': "① Pente constante", 'en': "① Constant slope",
        'es': "① Pendiente constante", 'pt': "① Declive constante",
        'de': "① Konstantes Gefälle",
    },
    'ts_grp1_aide': {
        'fr': "Choisissez une pente à la main : elle sera appliquée sur toute "
              "la chaîne en partant du regard de départ, en recalculant chaque "
              "FE (et profondeur) en cascade, puis la pente des conduites et la "
              "cote de piquage des branchements concernés.",
        'en': "Enter a slope by hand: it is applied to the whole chain from the "
              "start manhole, recalculating each invert (and depth) in cascade, "
              "then the pipe slopes and the tap-in levels of the affected "
              "service connections.",
        'es': "Introduzca una pendiente a mano: se aplica a toda la cadena desde "
              "el pozo inicial, recalculando en cascada cada cota de solera (y "
              "profundidad), luego la pendiente de las tuberías y la cota de "
              "conexión de las acometidas afectadas.",
        'pt': "Introduza um declive à mão: é aplicado a toda a cadeia a partir "
              "da caixa inicial, recalculando em cascata cada soleira (e "
              "profundidade), depois o declive das condutas e a cota de ligação "
              "dos ramais afetados.",
        'de': "Geben Sie ein Gefälle von Hand ein: Es wird ab dem Startschacht "
              "auf die gesamte Kette angewendet, wobei jede Sohlhöhe (und Tiefe) "
              "kaskadierend neu berechnet wird, danach das Leitungsgefälle und "
              "die Anschlusshöhen der betroffenen Hausanschlüsse.",
    },
    'ts_ex_pente': {
        'fr': "ex : 0.5", 'en': "e.g. 0.5", 'es': "ej.: 0.5",
        'pt': "ex.: 0.5", 'de': "z. B. 0.5",
    },
    'ts_grp2': {
        'fr': "② Pente calculée", 'en': "② Computed slope",
        'es': "② Pendiente calculada", 'pt': "② Declive calculado",
        'de': "② Berechnetes Gefälle",
    },
    'ts_grp2_aide': {
        'fr': "Calcule automatiquement la pente moyenne à partir des altitudes "
              "(FE) connues du regard de départ et du regard d'arrivée, puis "
              "l'applique sur toute la chaîne — utile quand seuls ces 2 points "
              "sont connus.",
        'en': "Computes the average slope from the known invert levels of the "
              "start and end manholes, then applies it to the whole chain — "
              "useful when only those 2 points are known.",
        'es': "Calcula la pendiente media a partir de las cotas de solera "
              "conocidas del pozo inicial y del pozo final, y la aplica a toda "
              "la cadena — útil cuando solo se conocen esos 2 puntos.",
        'pt': "Calcula o declive médio a partir das soleiras conhecidas da caixa "
              "inicial e da caixa final e aplica-o a toda a cadeia — útil quando "
              "só esses 2 pontos são conhecidos.",
        'de': "Berechnet das mittlere Gefälle aus den bekannten Sohlhöhen von "
              "Start- und Endschacht und wendet es auf die gesamte Kette an — "
              "nützlich, wenn nur diese 2 Punkte bekannt sind.",
    },
    'ts_calculer_appliquer': {
        'fr': "Calculer et appliquer", 'en': "Compute and apply",
        'es': "Calcular y aplicar", 'pt': "Calcular e aplicar",
        'de': "Berechnen und anwenden",
    },
    'ts_grp3': {
        'fr': "③ Profondeur fixe", 'en': "③ Fixed depth",
        'es': "③ Profundidad fija", 'pt': "③ Profundidade fixa",
        'de': "③ Feste Tiefe",
    },
    'ts_grp3_aide': {
        'fr': "Applique la même profondeur (ex : 1,00 m) à tous les "
              "regards/tabourets de la chaîne. Le FE est recalculé "
              "automatiquement si le TN est connu.",
        'en': "Applies the same depth (e.g. 1.00 m) to every manhole and chamber "
              "in the chain. The invert level is recalculated automatically when "
              "the ground level is known.",
        'es': "Aplica la misma profundidad (ej.: 1,00 m) a todos los pozos y "
              "arquetas de la cadena. La cota de solera se recalcula "
              "automáticamente si se conoce la cota del terreno.",
        'pt': "Aplica a mesma profundidade (ex.: 1,00 m) a todas as caixas e "
              "câmaras da cadeia. A soleira é recalculada automaticamente se a "
              "cota do terreno for conhecida.",
        'de': "Wendet dieselbe Tiefe (z. B. 1,00 m) auf alle Schächte und "
              "Anschlussschächte der Kette an. Die Sohlhöhe wird automatisch neu "
              "berechnet, wenn die Geländehöhe bekannt ist.",
    },
    'ts_onglet_chaine': {
        'fr': "Chaîne regards PENTE", 'en': "Manhole chain SLOPE",
        'es': "Cadena de pozos PENDIENTE", 'pt': "Cadeia de caixas DECLIVE",
        'de': "Schachtkette GEFÄLLE",
    },
    'ts_err_deux_regards': {
        'fr': "Choisissez deux regards différents.",
        'en': "Choose two different manholes.",
        'es': "Elija dos pozos diferentes.",
        'pt': "Escolha duas caixas diferentes.",
        'de': "Wählen Sie zwei verschiedene Schächte.",
    },
    'ts_err_regard_introuvable': {
        'fr': "Regard introuvable.", 'en': "Manhole not found.",
        'es': "Pozo no encontrado.", 'pt': "Caixa não encontrada.",
        'de': "Schacht nicht gefunden.",
    },
    'ts_err_chaine_dabord': {
        'fr': "Recherchez d'abord la chaîne.", 'en': "Find the chain first.",
        'es': "Busque primero la cadena.", 'pt': "Procure primeiro a cadeia.",
        'de': "Suchen Sie zuerst die Kette.",
    },
    'ts_err_pente_invalide': {
        'fr': "Pente invalide — saisissez un nombre, ex : 0.5",
        'en': "Invalid slope — enter a number, e.g. 0.5",
        'es': "Pendiente no válida — introduzca un número, ej.: 0.5",
        'pt': "Declive inválido — introduza um número, ex.: 0.5",
        'de': "Ungültiges Gefälle — geben Sie eine Zahl ein, z. B. 0.5",
    },
    'ts_err_prof_invalide': {
        'fr': "Profondeur invalide — saisissez un nombre, ex : 1.00",
        'en': "Invalid depth — enter a number, e.g. 1.00",
        'es': "Profundidad no válida — introduzca un número, ej.: 1.00",
        'pt': "Profundidade inválida — introduza um número, ex.: 1.00",
        'de': "Ungültige Tiefe — geben Sie eine Zahl ein, z. B. 1.00",
    },

    # ─────────────────────────────────────────────────────────────────────
    #  Fenêtre d'accueil
    # ─────────────────────────────────────────────────────────────────────
    'acc_titre': {
        'fr': "CanaPlan – Réseau Assainissement",
        'en': "CanaPlan – Sewer network",
        'es': "CanaPlan – Red de saneamiento",
        'pt': "CanaPlan – Rede de saneamento",
        'de': "CanaPlan – Abwassernetz",
    },
    'acc_question': {
        'fr': "Aucun projet n'est chargé.\nQue souhaitez-vous faire ?",
        'en': "No project is loaded.\nWhat would you like to do?",
        'es': "No hay ningún proyecto cargado.\n¿Qué desea hacer?",
        'pt': "Nenhum projeto carregado.\nO que deseja fazer?",
        'de': "Es ist kein Projekt geladen.\nWas möchten Sie tun?",
    },
    'acc_assistant': {
        'fr': "Débuter avec l'assistant", 'en': "Start with the wizard",
        'es': "Empezar con el asistente", 'pt': "Começar com o assistente",
        'de': "Mit dem Assistenten beginnen",
    },
    'acc_ouvrir': {
        'fr': "Ouvrir un projet existant", 'en': "Open an existing project",
        'es': "Abrir un proyecto existente", 'pt': "Abrir um projeto existente",
        'de': "Vorhandenes Projekt öffnen",
    },
    'acc_continuer': {
        'fr': "Continuer sans projet", 'en': "Continue without a project",
        'es': "Continuar sin proyecto", 'pt': "Continuar sem projeto",
        'de': "Ohne Projekt fortfahren",
    },

    # ─────────────────────────────────────────────────────────────────────
    #  Assistant de création de projet
    # ─────────────────────────────────────────────────────────────────────
    'wz_adresse_aide': {
        'fr': "Entrez l'adresse du projet, puis ajustez la position en "
              "déplaçant/zoomant la carte si besoin.",
        'en': "Enter the project address, then fine-tune the position by "
              "panning or zooming the map if needed.",
        'es': "Introduzca la dirección del proyecto y ajuste la posición "
              "desplazando o ampliando el mapa si es necesario.",
        'pt': "Introduza o endereço do projeto e ajuste a posição deslocando "
              "ou ampliando o mapa se necessário.",
        'de': "Geben Sie die Projektadresse ein und passen Sie die Position "
              "bei Bedarf durch Verschieben oder Zoomen der Karte an.",
    },
    'wz_fonds_aide': {
        'fr': "Fonds de plan à charger dans le nouveau projet :",
        'en': "Basemaps to load into the new project:",
        'es': "Mapas base que se cargarán en el nuevo proyecto:",
        'pt': "Mapas base a carregar no novo projeto:",
        'de': "In das neue Projekt zu ladende Hintergrundkarten:",
    },
    'wz_fonds_titre': {
        'fr': "Fonds de plan", 'en': "Basemaps", 'es': "Mapas base",
        'pt': "Mapas base", 'de': "Hintergrundkarten",
    },
    'wz_config_aide': {
        'fr': "Configuration rapide du projet (modifiable plus tard depuis le "
              "menu Configuration) :",
        'en': "Quick project setup (can be changed later from the "
              "Configuration menu):",
        'es': "Configuración rápida del proyecto (modificable más tarde desde "
              "el menú Configuración):",
        'pt': "Configuração rápida do projeto (alterável mais tarde no menu "
              "Configuração):",
        'de': "Schnelle Projektkonfiguration (später über das Menü "
              "Konfiguration änderbar):",
    },
    'wz_recap_aide': {
        'fr': "Vérifiez les informations ci-dessous, ou revenez en arrière "
              "pour les modifier, puis cliquez sur « Créer ».",
        'en': "Check the information below, or go back to change it, then "
              "click “Create”.",
        'es': "Compruebe la información siguiente, o retroceda para "
              "modificarla, y haga clic en «Crear».",
        'pt': "Verifique as informações abaixo, ou volte atrás para as "
              "alterar, e clique em «Criar».",
        'de': "Prüfen Sie die folgenden Angaben oder gehen Sie zurück, um sie "
              "zu ändern, und klicken Sie dann auf „Erstellen“.",
    },
    'wz_enregistrement': {
        'fr': "Enregistrement du projet", 'en': "Saving the project",
        'es': "Guardado del proyecto", 'pt': "Gravação do projeto",
        'de': "Speichern des Projekts",
    },
    'wz_nom_label': {
        'fr': "Nom du projet :", 'en': "Project name:",
        'es': "Nombre del proyecto:", 'pt': "Nome do projeto:",
        'de': "Projektname:",
    },
    'wz_nom_ph': {
        'fr': "Nom du projet", 'en': "Project name", 'es': "Nombre del proyecto",
        'pt': "Nome do projeto", 'de': "Projektname",
    },
    'wz_dossier_label': {
        'fr': "Dossier :", 'en': "Folder:", 'es': "Carpeta:",
        'pt': "Pasta:", 'de': "Ordner:",
    },
    'wz_choisir_dossier': {
        'fr': "Choisir un dossier…", 'en': "Choose a folder…",
        'es': "Elegir una carpeta…", 'pt': "Escolher uma pasta…",
        'de': "Ordner wählen…",
    },
    'wz_parcourir': {
        'fr': "Parcourir…", 'en': "Browse…", 'es': "Examinar…",
        'pt': "Procurar…", 'de': "Durchsuchen…",
    },
    'wz_cubature_largeurs': {
        'fr': "Cubature — largeurs de tranchée",
        'en': "Volumes — trench widths",
        'es': "Cubicación — anchos de zanja",
        'pt': "Cubagem — larguras de vala",
        'de': "Massen — Grabenbreiten",
    },
    'wz_remblai': {
        'fr': "Remblai", 'en': "Backfill", 'es': "Relleno",
        'pt': "Aterro", 'de': "Verfüllung",
    },
    'wz_dossier_titre': {
        'fr': "Choisir le dossier de sauvegarde du projet",
        'en': "Choose the folder to save the project in",
        'es': "Elija la carpeta donde guardar el proyecto",
        'pt': "Escolha a pasta onde guardar o projeto",
        'de': "Ordner zum Speichern des Projekts wählen",
    },
    'wz_precedent': {
        'fr': "< Précédent", 'en': "< Back", 'es': "< Anterior",
        'pt': "< Anterior", 'de': "< Zurück",
    },
    'wz_suivant': {
        'fr': "Suivant >", 'en': "Next >", 'es': "Siguiente >",
        'pt': "Seguinte >", 'de': "Weiter >",
    },
    'wz_err_champs': {
        'fr': "Merci de renseigner le nom du projet et le dossier "
              "d'enregistrement avant de cliquer sur « Créer ».",
        'en': "Please fill in the project name and the destination folder "
              "before clicking “Create”.",
        'es': "Indique el nombre del proyecto y la carpeta de destino antes "
              "de hacer clic en «Crear».",
        'pt': "Indique o nome do projeto e a pasta de destino antes de clicar "
              "em «Criar».",
        'de': "Bitte geben Sie Projektname und Zielordner an, bevor Sie auf "
              "„Erstellen“ klicken.",
    },
    'wz_ecraser': {
        'fr': "Le fichier « {nom}.bet » existe déjà dans ce dossier. "
              "Voulez-vous l'écraser ?",
        'en': "The file “{nom}.bet” already exists in this folder. "
              "Overwrite it?",
        'es': "El archivo «{nom}.bet» ya existe en esta carpeta. "
              "¿Desea sobrescribirlo?",
        'pt': "O ficheiro «{nom}.bet» já existe nesta pasta. "
              "Deseja substituí-lo?",
        'de': "Die Datei „{nom}.bet“ existiert bereits in diesem Ordner. "
              "Überschreiben?",
    },
    # Titres des 4 étapes, en-tête de l'assistant
    'wz_etape1': {
        'fr': "1. Localiser le projet", 'en': "1. Locate the project",
        'es': "1. Localizar el proyecto", 'pt': "1. Localizar o projeto",
        'de': "1. Projekt verorten",
    },
    'wz_etape2': {
        'fr': "2. Fonds de plan", 'en': "2. Basemaps",
        'es': "2. Mapas base", 'pt': "2. Mapas de base",
        'de': "2. Hintergrundkarten",
    },
    'wz_etape3': {
        'fr': "3. Configuration rapide", 'en': "3. Quick setup",
        'es': "3. Configuración rápida", 'pt': "3. Configuração rápida",
        'de': "3. Schnelleinrichtung",
    },
    'wz_etape4': {
        'fr': "4. Récapitulatif", 'en': "4. Summary",
        'es': "4. Resumen", 'pt': "4. Resumo", 'de': "4. Zusammenfassung",
    },
    'wz_creer': {
        'fr': "Créer", 'en': "Create", 'es': "Crear", 'pt': "Criar",
        'de': "Erstellen",
    },
    # Fonds de plan proposés à l'étape 2 et rappelés au récapitulatif
    'wz_fond_osm': {
        'fr': "Fond OSM désaturé", 'en': "Desaturated OSM basemap",
        'es': "Mapa base OSM desaturado", 'pt': "Mapa base OSM dessaturado",
        'de': "Entsättigte OSM-Karte",
    },
    'wz_fond_osm_court': {
        'fr': "OSM désaturé", 'en': "Desaturated OSM",
        'es': "OSM desaturado", 'pt': "OSM dessaturado",
        'de': "OSM entsättigt",
    },
    'wz_fond_ortho': {
        'fr': "Orthophoto IGN", 'en': "IGN orthophoto",
        'es': "Ortofoto IGN", 'pt': "Ortofoto IGN", 'de': "IGN-Orthofoto",
    },
    'wz_fond_ban': {
        'fr': "Adresses BAN", 'en': "BAN addresses",
        'es': "Direcciones BAN", 'pt': "Endereços BAN",
        'de': "BAN-Adressen",
    },
    'wz_fond_noms_voie': {
        'fr': "Noms de voie (BD TOPO)", 'en': "Street names (BD TOPO)",
        'es': "Nombres de vía (BD TOPO)", 'pt': "Nomes de via (BD TOPO)",
        'de': "Straßennamen (BD TOPO)",
    },
    'wz_fond_noms_voie_court': {
        'fr': "Noms de voie", 'en': "Street names",
        'es': "Nombres de vía", 'pt': "Nomes de via",
        'de': "Straßennamen",
    },
    'wz_fond_parcelles': {
        'fr': "PCI Vecteur Parcelles", 'en': "PCI Vector parcels",
        'es': "PCI Vector parcelas", 'pt': "PCI Vetor parcelas",
        'de': "PCI-Vektor Flurstücke",
    },
    'wz_fond_bati': {
        'fr': "PCI Vecteur Bâti", 'en': "PCI Vector buildings",
        'es': "PCI Vector edificios", 'pt': "PCI Vetor edifícios",
        'de': "PCI-Vektor Gebäude",
    },
    # Accordéons de l'étape 3
    'wz_reseau_defaut': {
        'fr': "Réseau par défaut", 'en': "Default network",
        'es': "Red por defecto", 'pt': "Rede por omissão",
        'de': "Standardnetz",
    },
    'wz_cubature': {
        'fr': "Cubature", 'en': "Trench volumes", 'es': "Cubicación",
        'pt': "Cubicagem", 'de': "Massenermittlung",
    },
    # Récapitulatif de l'étape 4
    'wz_recap_reseau': {
        'fr': "Réseau : {texte}", 'en': "Network: {texte}",
        'es': "Red: {texte}", 'pt': "Rede: {texte}", 'de': "Netz: {texte}",
    },
    'wz_recap_cubature': {
        'fr': "Cubature : {texte}", 'en': "Trench volumes: {texte}",
        'es': "Cubicación: {texte}", 'pt': "Cubicagem: {texte}",
        'de': "Massenermittlung: {texte}",
    },
    'wz_recap_remblai': {
        'fr': "Remblai : {texte}", 'en': "Backfill: {texte}",
        'es': "Relleno: {texte}", 'pt': "Aterro: {texte}",
        'de': "Verfüllung: {texte}",
    },
    'wz_recap_adresse': {
        'fr': "Adresse du projet :", 'en': "Project address:",
        'es': "Dirección del proyecto:", 'pt': "Endereço do projeto:",
        'de': "Projektadresse:",
    },
    'wz_recap_sans_adresse': {
        'fr': "(non renseignée — position de la mini-carte utilisée)",
        'en': "(not set — the mini-map position is used)",
        'es': "(sin indicar — se usa la posición del mini-mapa)",
        'pt': "(não indicado — é usada a posição do mini-mapa)",
        'de': "(nicht angegeben — Position der Übersichtskarte wird verwendet)",
    },
    'wz_recap_fonds': {
        'fr': "Fonds de plan :", 'en': "Basemaps:", 'es': "Mapas base:",
        'pt': "Mapas de base:", 'de': "Hintergrundkarten:",
    },
    'wz_recap_aucun': {
        'fr': "(aucun)", 'en': "(none)", 'es': "(ninguno)",
        'pt': "(nenhum)", 'de': "(keine)",
    },
    'wz_projet_nomme': {
        'fr': "Projet {nom}", 'en': "{nom} project", 'es': "Proyecto {nom}",
        'pt': "Projeto {nom}", 'de': "Projekt {nom}",
    },
    # Configuration rapide : libellés partagés avec le dialogue de config
    'qc_conduites': {
        'fr': "Conduites", 'en': "Pipes", 'es': "Tuberías",
        'pt': "Condutas", 'de': "Leitungen",
    },
    'qc_branchements': {
        'fr': "Branchements", 'en': "Service connections",
        'es': "Acometidas", 'pt': "Ramais", 'de': "Hausanschlüsse",
    },
    'qc_regards': {
        'fr': "Regards", 'en': "Manholes", 'es': "Pozos de registro",
        'pt': "Câmaras de visita", 'de': "Schächte",
    },
    'qc_tabourets': {
        'fr': "Tabourets", 'en': "Inspection chambers", 'es': "Arquetas",
        'pt': "Caixas de ramal", 'de': "Anschlussschächte",
    },
    'qc_role_diametre': {
        'fr': "{role} — Diamètre :", 'en': "{role} — Diameter:",
        'es': "{role} — Diámetro:", 'pt': "{role} — Diâmetro:",
        'de': "{role} — Durchmesser:",
    },
    'qc_role_materiau': {
        'fr': "{role} — Matériau :", 'en': "{role} — Material:",
        'es': "{role} — Material:", 'pt': "{role} — Material:",
        'de': "{role} — Material:",
    },
    'qc_couche_role': {
        'fr': "{role} :", 'en': "{role}:", 'es': "{role}:", 'pt': "{role}:",
        'de': "{role}:",
    },
    'qc_ep_lit_pose': {
        'fr': "Épaisseur lit de pose :", 'en': "Bedding thickness:",
        'es': "Espesor de la cama:", 'pt': "Espessura do leito:",
        'de': "Bettungsdicke:",
    },
    'qc_larg_cond_eu': {
        'fr': "Largeur tranchée Conduite EU :",
        'en': "Trench width — wastewater pipe:",
        'es': "Ancho de zanja — tubería de aguas residuales:",
        'pt': "Largura da vala — conduta de águas residuais:",
        'de': "Grabenbreite — Schmutzwasserleitung:",
    },
    'qc_larg_cond_ep': {
        'fr': "Largeur tranchée Conduite EP :",
        'en': "Trench width — stormwater pipe:",
        'es': "Ancho de zanja — tubería de aguas pluviales:",
        'pt': "Largura da vala — conduta de águas pluviais:",
        'de': "Grabenbreite — Regenwasserleitung:",
    },
    'qc_larg_branch_eu': {
        'fr': "Largeur tranchée Branchement EU :",
        'en': "Trench width — wastewater service connection:",
        'es': "Ancho de zanja — acometida de aguas residuales:",
        'pt': "Largura da vala — ramal de águas residuais:",
        'de': "Grabenbreite — Schmutzwasser-Hausanschluss:",
    },
    'qc_larg_branch_ep': {
        'fr': "Largeur tranchée Branchement EP :",
        'en': "Trench width — stormwater service connection:",
        'es': "Ancho de zanja — acometida de aguas pluviales:",
        'pt': "Largura da vala — ramal de águas pluviais:",
        'de': "Grabenbreite — Regenwasser-Hausanschluss:",
    },
    'qc_conduite_eu': {
        'fr': "Conduite EU", 'en': "Wastewater pipe",
        'es': "Tubería EU", 'pt': "Conduta EU", 'de': "Schmutzwasserleitung",
    },
    'qc_conduite_ep': {
        'fr': "Conduite EP", 'en': "Stormwater pipe",
        'es': "Tubería EP", 'pt': "Conduta EP", 'de': "Regenwasserleitung",
    },
    'qc_branchement_eu': {
        'fr': "Branchement EU", 'en': "Wastewater connection",
        'es': "Acometida EU", 'pt': "Ramal EU",
        'de': "Schmutzwasseranschluss",
    },
    'qc_branchement_ep': {
        'fr': "Branchement EP", 'en': "Stormwater connection",
        'es': "Acometida EP", 'pt': "Ramal EP",
        'de': "Regenwasseranschluss",
    },
    'qc_branch_court_eu': {
        'fr': "Branch. EU", 'en': "WW conn.", 'es': "Acom. EU",
        'pt': "Ramal EU", 'de': "SW-Anschl.",
    },
    'qc_branch_court_ep': {
        'fr': "Branch. EP", 'en': "SW conn.", 'es': "Acom. EP",
        'pt': "Ramal EP", 'de': "RW-Anschl.",
    },
    'qc_mat_lit_pose': {
        'fr': "Matériau lit de pose :", 'en': "Bedding material:",
        'es': "Material de la cama:", 'pt': "Material do leito:",
        'de': "Bettungsmaterial:",
    },
    'qc_enrobage_ep_mat': {
        'fr': "Enrobage (ép. + mat.) :", 'en': "Surround (thickness + material):",
        'es': "Recubrimiento (esp. + material):",
        'pt': "Envolvimento (esp. + material):",
        'de': "Ummantelung (Dicke + Material):",
    },
    'qc_mat_remblai': {
        'fr': "Matériau remblai :", 'en': "Backfill material:",
        'es': "Material de relleno:", 'pt': "Material de aterro:",
        'de': "Verfüllmaterial:",
    },
    'qc_ep_materiau': {
        'fr': "Ép. + matériau :", 'en': "Thickness + material:",
        'es': "Esp. + material:", 'pt': "Esp. + material:",
        'de': "Dicke + Material:",
    },
    'qc_couches': {
        'fr': "Couches", 'en': "Layers", 'es': "Capas", 'pt': "Camadas",
        'de': "Layer",
    },
    'qc_zone_enrobage': {
        'fr': "Zone d'enrobage", 'en': "Surround zone",
        'es': "Zona de recubrimiento", 'pt': "Zona de envolvimento",
        'de': "Ummantelungszone",
    },
    'qc_variable': {
        'fr': "(var.)", 'en': "(var.)", 'es': "(var.)", 'pt': "(var.)",
        'de': "(var.)",
    },
    'qc_schema_conduite': {
        'fr': "Conduite : {diam} mm", 'en': "Pipe: {diam} mm",
        'es': "Tubería: {diam} mm", 'pt': "Conduta: {diam} mm",
        'de': "Leitung: {diam} mm",
    },
    'qc_schema_branchement': {
        'fr': "Branch. : {diam} mm", 'en': "Conn.: {diam} mm",
        'es': "Acom.: {diam} mm", 'pt': "Ramal: {diam} mm",
        'de': "Anschl.: {diam} mm",
    },
    'qc_resume_reseau': {
        'fr': "{code} — conduite {diam_c} mm {mat_c}, "
              "branchement {diam_b} mm {mat_b}",
        'en': "{code} — pipe {diam_c} mm {mat_c}, "
              "service connection {diam_b} mm {mat_b}",
        'es': "{code} — tubería {diam_c} mm {mat_c}, "
              "acometida {diam_b} mm {mat_b}",
        'pt': "{code} — conduta {diam_c} mm {mat_c}, "
              "ramal {diam_b} mm {mat_b}",
        'de': "{code} — Leitung {diam_c} mm {mat_c}, "
              "Hausanschluss {diam_b} mm {mat_b}",
    },
    'qc_resume_cubature': {
        'fr': "Lit de pose {lit} m — largeurs tranchée : conduite EU {ceu} m, "
              "conduite EP {cep} m, branchement EU {beu} m, "
              "branchement EP {bep} m",
        'en': "Bedding {lit} m — trench widths: wastewater pipe {ceu} m, "
              "stormwater pipe {cep} m, wastewater connection {beu} m, "
              "stormwater connection {bep} m",
        'es': "Cama {lit} m — anchos de zanja: tubería EU {ceu} m, "
              "tubería EP {cep} m, acometida EU {beu} m, "
              "acometida EP {bep} m",
        'pt': "Leito {lit} m — larguras de vala: conduta EU {ceu} m, "
              "conduta EP {cep} m, ramal EU {beu} m, ramal EP {bep} m",
        'de': "Bettung {lit} m — Grabenbreiten: SW-Leitung {ceu} m, "
              "RW-Leitung {cep} m, SW-Anschluss {beu} m, "
              "RW-Anschluss {bep} m",
    },
    'qc_resume_remblai': {
        'fr': "Lit {lit}, enrobage {enr} ({ep_enr} m), remblai {rem}{extra}",
        'en': "Bedding {lit}, surround {enr} ({ep_enr} m), backfill {rem}{extra}",
        'es': "Cama {lit}, recubrimiento {enr} ({ep_enr} m), relleno {rem}{extra}",
        'pt': "Leito {lit}, envolvimento {enr} ({ep_enr} m), aterro {rem}{extra}",
        'de': "Bettung {lit}, Ummantelung {enr} ({ep_enr} m), "
              "Verfüllung {rem}{extra}",
    },

    # ─────────────────────────────────────────────────────────────────────
    #  Messages du plugin (main.py)
    # ─────────────────────────────────────────────────────────────────────
    'msg_cubature_titre': {
        'fr': "Cubature tranchées", 'en': "Trench volumes",
        'es': "Cubicación de zanjas", 'pt': "Cubagem de valas",
        'de': "Grabenmassen",
    },
    'msg_aucun_element': {
        'fr': "Aucun élément trouvé dans le périmètre sélectionné.",
        'en': "No element found within the selected area.",
        'es': "Ningún elemento encontrado en el perímetro seleccionado.",
        'pt': "Nenhum elemento encontrado no perímetro selecionado.",
        'de': "Kein Element im gewählten Bereich gefunden.",
    },
    'msg_fond_ok': {
        'fr': "Fond de projet mis en place", 'en': "Project basemap set up",
        'es': "Mapa base del proyecto configurado",
        'pt': "Mapa base do projeto configurado",
        'de': "Projekt-Hintergrundkarte eingerichtet",
    },
    'msg_telechargement': {
        'fr': "Téléchargement en cours…", 'en': "Downloading…",
        'es': "Descargando…", 'pt': "A transferir…", 'de': "Wird geladen…",
    },
    'msg_fond_carte': {
        'fr': "Fond de carte", 'en': "Basemap", 'es': "Mapa base",
        'pt': "Mapa base", 'de': "Hintergrundkarte",
    },
    'msg_wms_echec': {
        'fr': "Impossible de charger la couche WMS :\n{nom}",
        'en': "Could not load the WMS layer:\n{nom}",
        'es': "No se pudo cargar la capa WMS:\n{nom}",
        'pt': "Não foi possível carregar a camada WMS:\n{nom}",
        'de': "WMS-Layer konnte nicht geladen werden:\n{nom}",
    },
    # Titres de la barre de messages des outils
    'ot_titre_profil': {
        'fr': "Profil en long {reseau}", 'en': "{reseau} long section",
        'es': "Perfil longitudinal {reseau}", 'pt': "Perfil longitudinal {reseau}",
        'de': "{reseau}-Längsschnitt",
    },
    'ot_titre_move_piquage': {
        'fr': "Déplacer piquage {reseau}", 'en': "Move {reseau} tap-in",
        'es': "Mover conexión {reseau}", 'pt': "Mover ligação {reseau}",
        'de': "{reseau}-Anschluss verschieben",
    },
    'ot_titre_renum': {
        'fr': "Renumérotation {reseau}", 'en': "{reseau} renumbering",
        'es': "Renumeración {reseau}", 'pt': "Renumeração {reseau}",
        'de': "{reseau}-Neunummerierung",
    },
    # Renumérotation : formulaire et bilan
    'ot_lbl_prefixe_regards': {
        'fr': "Préfixe regards :", 'en': "Manhole prefix:",
        'es': "Prefijo de pozos:", 'pt': "Prefixo das câmaras:",
        'de': "Schacht-Präfix:",
    },
    'ot_lbl_depart_regards': {
        'fr': "N° de départ regards :", 'en': "Manhole start number:",
        'es': "Nº inicial de pozos:", 'pt': "Nº inicial das câmaras:",
        'de': "Startnummer Schächte:",
    },
    'ot_lbl_prefixe_tabourets': {
        'fr': "Préfixe tabourets :", 'en': "Chamber prefix:",
        'es': "Prefijo de arquetas:", 'pt': "Prefixo das caixas:",
        'de': "Anschlussschacht-Präfix:",
    },
    'ot_lbl_depart_tabourets': {
        'fr': "N° de départ tabourets :", 'en': "Chamber start number:",
        'es': "Nº inicial de arquetas:", 'pt': "Nº inicial das caixas:",
        'de': "Startnummer Anschlussschächte:",
    },
    'ot_renum_regards': {
        'fr': "{nb} regard(s) renommé(s) : {debut} → {fin}",
        'en': "{nb} manhole(s) renamed: {debut} → {fin}",
        'es': "{nb} pozo(s) renombrado(s): {debut} → {fin}",
        'pt': "{nb} câmara(s) renomeada(s): {debut} → {fin}",
        'de': "{nb} Schacht/Schächte umbenannt: {debut} → {fin}",
    },
    'ot_renum_tabourets': {
        'fr': "{nb} tabouret(s) renommé(s) : {debut} → {fin}",
        'en': "{nb} chamber(s) renamed: {debut} → {fin}",
        'es': "{nb} arqueta(s) renombrada(s): {debut} → {fin}",
        'pt': "{nb} caixa(s) renomeada(s): {debut} → {fin}",
        'de': "{nb} Anschlussschacht/-schächte umbenannt: {debut} → {fin}",
    },
    'ot_renum_sans_tabouret': {
        'fr': "Aucun tabouret rattaché trouvé.",
        'en': "No attached chamber found.",
        'es': "No se ha encontrado ninguna arqueta asociada.",
        'pt': "Nenhuma caixa associada encontrada.",
        'de': "Kein zugehöriger Anschlussschacht gefunden.",
    },
    # Saisie rapide au dessin d'un branchement
    'ot_lbl_tn': {
        'fr': "TN (m)", 'en': "Ground level (m)", 'es': "Cota terreno (m)",
        'pt': "Cota do terreno (m)", 'de': "Geländehöhe (m)",
    },
    'ot_lbl_fe_radier': {
        'fr': "FE radier (m)", 'en': "Invert level (m)",
        'es': "Cota de solera (m)", 'pt': "Cota de soleira (m)",
        'de': "Sohlhöhe (m)",
    },
    'ot_lbl_diametre': {
        'fr': "Diamètre (mm)", 'en': "Diameter (mm)", 'es': "Diámetro (mm)",
        'pt': "Diâmetro (mm)", 'de': "Durchmesser (mm)",
    },
    # Import Star-DT : sélecteurs de fichiers
    'sdt_choisir_fichiers': {
        'fr': "Fichier(s) Star-DT", 'en': "Star-DT file(s)",
        'es': "Archivo(s) Star-DT", 'pt': "Ficheiro(s) Star-DT",
        'de': "Star-DT-Datei(en)",
    },
    'fic_star_dt': {
        'fr': "Star-DT GML (*.gml *.xml);;Tous (*.*)",
        'en': "Star-DT GML (*.gml *.xml);;All files (*.*)",
        'es': "Star-DT GML (*.gml *.xml);;Todos (*.*)",
        'pt': "Star-DT GML (*.gml *.xml);;Todos (*.*)",
        'de': "Star-DT GML (*.gml *.xml);;Alle (*.*)",
    },
    'fic_gpkg': {
        'fr': "GeoPackage (*.gpkg)", 'en': "GeoPackage (*.gpkg)",
        'es': "GeoPackage (*.gpkg)", 'pt': "GeoPackage (*.gpkg)",
        'de': "GeoPackage (*.gpkg)",
    },
    # Export StaR-Eau : onglet Contrôle et champs obligatoires
    'se_onglet_controle_nb': {
        'fr': "Contrôle ({nb})", 'en': "Check ({nb})", 'es': "Control ({nb})",
        'pt': "Controlo ({nb})", 'de': "Prüfung ({nb})",
    },
    'se_manque_dossier': {
        'fr': "le dossier de destination", 'en': "the destination folder",
        'es': "la carpeta de destino", 'pt': "a pasta de destino",
        'de': "den Zielordner",
    },
    'se_manque_insee': {
        'fr': "le code INSEE de la commune", 'en': "the INSEE municipality code",
        'es': "el código INSEE del municipio", 'pt': "o código INSEE do município",
        'de': "den INSEE-Gemeindecode",
    },
    'se_manque_moa': {
        'fr': "le maître d'ouvrage", 'en': "the owner", 'es': "el propietario",
        'pt': "o dono de obra", 'de': "den Bauherrn",
    },
    'se_manque_exploitant': {
        'fr': "l'exploitant", 'en': "the operator", 'es': "el explotador",
        'pt': "o operador", 'de': "den Betreiber",
    },
    'se_manque_intro': {
        'fr': "Ces informations sont exigées par le géostandard :",
        'en': "The geostandard requires this information:",
        'es': "El geoestándar exige esta información:",
        'pt': "O geopadrão exige estas informações:",
        'de': "Der Geostandard verlangt diese Angaben:",
    },
    # Enregistrement / rechargement d'un projet .bet
    'bet_sauvegarde': {
        'fr': "Sauvegarde en cours…", 'en': "Saving…", 'es': "Guardando…",
        'pt': "A guardar…", 'de': "Wird gespeichert…",
    },
    'bet_preparation': {
        'fr': "Préparation {couche} (ignoré)", 'en': "Preparing {couche} (skipped)",
        'es': "Preparando {couche} (omitido)", 'pt': "A preparar {couche} (ignorado)",
        'de': "Vorbereitung {couche} (übersprungen)",
    },
    'bet_copie': {
        'fr': "Copie mémoire : {couche}", 'en': "Copying to memory: {couche}",
        'es': "Copia en memoria: {couche}", 'pt': "Cópia em memória: {couche}",
        'de': "Kopie im Speicher: {couche}",
    },
    'bet_liberation': {
        'fr': "Libération : {couche}", 'en': "Releasing: {couche}",
        'es': "Liberando: {couche}", 'pt': "A libertar: {couche}",
        'de': "Freigabe: {couche}",
    },
    'bet_ecriture': {
        'fr': "Écriture GPKG : {couche}", 'en': "Writing GPKG: {couche}",
        'es': "Escritura GPKG: {couche}", 'pt': "Escrita GPKG: {couche}",
        'de': "GPKG schreiben: {couche}",
    },
    'bet_compression': {
        'fr': "Compression de l'archive .bet…", 'en': "Compressing the .bet archive…",
        'es': "Comprimiendo el archivo .bet…", 'pt': "A comprimir o arquivo .bet…",
        'de': "Das .bet-Archiv wird komprimiert…",
    },
    'bet_extraction': {
        'fr': "Extraction pour rechargement…", 'en': "Extracting for reload…",
        'es': "Extrayendo para recargar…", 'pt': "A extrair para recarregar…",
        'de': "Entpacken zum Neuladen…",
    },
    'bet_rechargement': {
        'fr': "Rechargement : {couche}", 'en': "Reloading: {couche}",
        'es': "Recargando: {couche}", 'pt': "A recarregar: {couche}",
        'de': "Neu laden: {couche}",
    },
    'bet_err_introuvable': {
        'fr': "{couche} : couche introuvable, ignorée",
        'en': "{couche}: layer not found, skipped",
        'es': "{couche}: capa no encontrada, omitida",
        'pt': "{couche}: camada não encontrada, ignorada",
        'de': "{couche}: Layer nicht gefunden, übersprungen",
    },
    'bet_err_recharge': {
        'fr': "{couche} : rechargement depuis archive échoué",
        'en': "{couche}: reload from the archive failed",
        'es': "{couche}: fallo al recargar desde el archivo",
        'pt': "{couche}: falha ao recarregar a partir do arquivo",
        'de': "{couche}: Neuladen aus dem Archiv fehlgeschlagen",
    },
    'bet_err_invalide': {
        'fr': "{couche} : couche invalide dans le GPKG",
        'en': "{couche}: invalid layer in the GPKG",
        'es': "{couche}: capa no válida en el GPKG",
        'pt': "{couche}: camada inválida no GPKG",
        'de': "{couche}: ungültiger Layer im GPKG",
    },
    'bet_err_etiquettes': {
        'fr': "{couche} : étiquettes non configurées ({detail})",
        'en': "{couche}: labels not configured ({detail})",
        'es': "{couche}: etiquetas no configuradas ({detail})",
        'pt': "{couche}: etiquetas não configuradas ({detail})",
        'de': "{couche}: Beschriftungen nicht konfiguriert ({detail})",
    },
    'bet_err_prefs_etiquettes': {
        'fr': "Restauration des préférences d'étiquettes : {detail}",
        'en': "Restoring label preferences: {detail}",
        'es': "Restauración de las preferencias de etiquetas: {detail}",
        'pt': "Restauro das preferências de etiquetas: {detail}",
        'de': "Wiederherstellung der Beschriftungseinstellungen: {detail}",
    },
    'bet_err_fonds_enreg': {
        'fr': "fonds de plan non enregistrés : {detail}",
        'en': "basemaps not saved: {detail}",
        'es': "mapas base no guardados: {detail}",
        'pt': "mapas de base não guardados: {detail}",
        'de': "Hintergrundkarten nicht gespeichert: {detail}",
    },
    'bet_err_fonds_recharge': {
        'fr': "fonds de plan non rechargés : {detail}",
        'en': "basemaps not reloaded: {detail}",
        'es': "mapas base no recargados: {detail}",
        'pt': "mapas de base não recarregados: {detail}",
        'de': "Hintergrundkarten nicht neu geladen: {detail}",
    },
    # Fonds de plan embarqués dans l'archive
    'fp_raster_local': {
        'fr': "{couche} : raster local, non embarqué",
        'en': "{couche}: local raster, not embedded",
        'es': "{couche}: ráster local, no incrustado",
        'pt': "{couche}: raster local, não incorporado",
        'de': "{couche}: lokales Raster, nicht eingebettet",
    },
    'fp_source_introuvable': {
        'fr': "{couche} : source introuvable, couche ignorée",
        'en': "{couche}: source not found, layer skipped",
        'es': "{couche}: fuente no encontrada, capa omitida",
        'pt': "{couche}: fonte não encontrada, camada ignorada",
        'de': "{couche}: Quelle nicht gefunden, Layer übersprungen",
    },
    'fp_donnees_absentes': {
        'fr': "{couche} : données absentes de l'archive",
        'en': "{couche}: data missing from the archive",
        'es': "{couche}: datos ausentes del archivo",
        'pt': "{couche}: dados ausentes do arquivo",
        'de': "{couche}: Daten fehlen im Archiv",
    },
    'fp_couche_invalide': {
        'fr': "{couche} : couche invalide, non rechargée",
        'en': "{couche}: invalid layer, not reloaded",
        'es': "{couche}: capa no válida, no recargada",
        'pt': "{couche}: camada inválida, não recarregada",
        'de': "{couche}: ungültiger Layer, nicht neu geladen",
    },
    'fp_style_non_applique': {
        'fr': "{couche} : style non appliqué ({detail})",
        'en': "{couche}: style not applied ({detail})",
        'es': "{couche}: estilo no aplicado ({detail})",
        'pt': "{couche}: estilo não aplicado ({detail})",
        'de': "{couche}: Stil nicht angewendet ({detail})",
    },
    'msg_impression': {
        'fr': "Impression", 'en': "Printing", 'es': "Impresión",
        'pt': "Impressão", 'de': "Druck",
    },
    'msg_wfs_vide': {
        'fr': "{couche} : 0 objet dans l'emprise",
        'en': "{couche}: no feature within the extent",
        'es': "{couche}: ningún objeto en el ámbito",
        'pt': "{couche}: nenhum objeto na extensão",
        'de': "{couche}: kein Objekt im Ausschnitt",
    },
    'msg_wfs_invalide': {
        'fr': "{couche} : couche invalide", 'en': "{couche}: invalid layer",
        'es': "{couche}: capa no válida", 'pt': "{couche}: camada inválida",
        'de': "{couche}: ungültiger Layer",
    },
    'msg_wfs_tls': {
        'fr': "certificat TLS non vérifié (proxy ?)",
        'en': "TLS certificate not verified (proxy?)",
        'es': "certificado TLS no verificado (¿proxy?)",
        'pt': "certificado TLS não verificado (proxy?)",
        'de': "TLS-Zertifikat nicht geprüft (Proxy?)",
    },
    'msg_wfs_charges': {
        'fr': "{nb} objet(s) chargé(s)", 'en': "{nb} feature(s) loaded",
        'es': "{nb} objeto(s) cargado(s)", 'pt': "{nb} objeto(s) carregado(s)",
        'de': "{nb} Objekt(e) geladen",
    },
    'msg_profils_ok': {
        'fr': "Profils {reseau} : {nb} page(s) → {fichier}",
        'en': "{reseau} profiles: {nb} page(s) → {fichier}",
        'es': "Perfiles {reseau}: {nb} página(s) → {fichier}",
        'pt': "Perfis {reseau}: {nb} página(s) → {fichier}",
        'de': "{reseau}-Längsschnitte: {nb} Seite(n) → {fichier}",
    },
    'msg_profils_vide': {
        'fr': "Profils {reseau} : aucune conduite trouvée",
        'en': "{reseau} profiles: no pipe found",
        'es': "Perfiles {reseau}: ninguna tubería encontrada",
        'pt': "Perfis {reseau}: nenhuma conduta encontrada",
        'de': "{reseau}-Längsschnitte: keine Leitung gefunden",
    },
    'msg_profil_groupe_ok': {
        'fr': "Profil groupé → {fichier}", 'en': "Combined profile → {fichier}",
        'es': "Perfil agrupado → {fichier}", 'pt': "Perfil agrupado → {fichier}",
        'de': "Sammel-Längsschnitt → {fichier}",
    },
    'msg_profil_groupe_vide': {
        'fr': "Profil groupé : aucune conduite trouvée",
        'en': "Combined profile: no pipe found",
        'es': "Perfil agrupado: ninguna tubería encontrada",
        'pt': "Perfil agrupado: nenhuma conduta encontrada",
        'de': "Sammel-Längsschnitt: keine Leitung gefunden",
    },
    'msg_erreur_detail': {
        'fr': "Erreur : {detail}", 'en': "Error: {detail}",
        'es': "Error: {detail}", 'pt': "Erro: {detail}",
        'de': "Fehler: {detail}",
    },
    'msg_dossier': {
        'fr': "Dossier : {chemin}", 'en': "Folder: {chemin}",
        'es': "Carpeta: {chemin}", 'pt': "Pasta: {chemin}",
        'de': "Ordner: {chemin}",
    },
    'msg_crs_non_metrique': {
        'fr': "Le CRS du projet ({crs}) n'est pas en mètres.\nLes dimensions "
              "des planches risquent d'être incorrectes.\nRecommandé : "
              "EPSG:2154 (RGF93 / Lambert-93).",
        'en': "The project CRS ({crs}) is not metric.\nSheet dimensions may be "
              "wrong.\nRecommended: EPSG:2154 (RGF93 / Lambert-93).",
        'es': "El SRC del proyecto ({crs}) no está en metros.\nLas dimensiones "
              "de las hojas pueden ser incorrectas.\nRecomendado: EPSG:2154 "
              "(RGF93 / Lambert-93).",
        'pt': "O SRC do projeto ({crs}) não está em metros.\nAs dimensões das "
              "folhas podem estar incorretas.\nRecomendado: EPSG:2154 "
              "(RGF93 / Lambert-93).",
        'de': "Das Projekt-KBS ({crs}) ist nicht metrisch.\nDie Blattmaße "
              "können falsch sein.\nEmpfohlen: EPSG:2154 (RGF93 / Lambert-93).",
    },
    'msg_export_profils_ok': {
        'fr': "Export profils terminé", 'en': "Profile export complete",
        'es': "Exportación de perfiles finalizada",
        'pt': "Exportação de perfis concluída",
        'de': "Profilexport abgeschlossen",
    },
    'msg_export_dxf_titre': {
        'fr': "Exporter le plan en DXF 2018", 'en': "Export the plan to DXF 2018",
        'es': "Exportar el plano a DXF 2018", 'pt': "Exportar o plano para DXF 2018",
        'de': "Plan als DXF 2018 exportieren",
    },
    'msg_erreur_export': {
        'fr': "Erreur lors de l'export :\n{erreur}",
        'en': "Export failed:\n{erreur}",
        'es': "Error durante la exportación:\n{erreur}",
        'pt': "Erro durante a exportação:\n{erreur}",
        'de': "Fehler beim Export:\n{erreur}",
    },
    'msg_erreur_import': {
        'fr': "Erreur lors de l'import :\n{erreur}",
        'en': "Import failed:\n{erreur}",
        'es': "Error durante la importación:\n{erreur}",
        'pt': "Erro durante a importação:\n{erreur}",
        'de': "Fehler beim Import:\n{erreur}",
    },
    'msg_import_ok': {
        'fr': "{couches} couche(s) importée(s) depuis {fichiers} fichier(s) "
              "dans {dossier}",
        'en': "{couches} layer(s) imported from {fichiers} file(s) in {dossier}",
        'es': "{couches} capa(s) importada(s) desde {fichiers} archivo(s) en "
              "{dossier}",
        'pt': "{couches} camada(s) importada(s) de {fichiers} ficheiro(s) em "
              "{dossier}",
        'de': "{couches} Layer aus {fichiers} Datei(en) in {dossier} importiert",
    },
    'msg_rien_a_importer': {
        'fr': "Aucun élément à importer.", 'en': "Nothing to import.",
        'es': "Nada que importar.", 'pt': "Nada a importar.",
        'de': "Nichts zu importieren.",
    },

    # ─────────────────────────────────────────────────────────────────────
    #  Fenêtre Imprimer / Exporter
    # ─────────────────────────────────────────────────────────────────────
    'exp_titre': {
        'fr': "Exporter", 'en': "Export", 'es': "Exportar",
        'pt': "Exportar", 'de': "Exportieren",
    },
    'exp_plan_carto': {
        'fr': "Plan cartographique :", 'en': "Map sheet:",
        'es': "Plano cartográfico:", 'pt': "Planta cartográfica:",
        'de': "Kartenplan:",
    },
    'exp_plan_pdf': {
        'fr': "Plan PDF", 'en': "PDF plan", 'es': "Plano PDF",
        'pt': "Planta PDF", 'de': "PDF-Plan",
    },
    'exp_plan_dxf': {
        'fr': "Plan DXF 2018", 'en': "DXF 2018 plan", 'es': "Plano DXF 2018",
        'pt': "Planta DXF 2018", 'de': "DXF-2018-Plan",
    },
    'exp_profils': {
        'fr': "Profils en long :", 'en': "Longitudinal profiles:",
        'es': "Perfiles longitudinales:", 'pt': "Perfis longitudinais:",
        'de': "Längsschnitte:",
    },
    # -- Titres de bloc du dialogue d'export -------------------------------
    'exp_cubature_titre': {
        'fr': "Cubature", 'en': "Earthworks", 'es': "Cubicación",
        'pt': "Cubagem", 'de': "Massenermittlung",
    },
    'exp_coupes_titre': {
        'fr': "Coupes", 'en': "Cross-sections", 'es': "Secciones",
        'pt': "Secções", 'de': "Querschnitte",
    },

    # -- Onglet Cubature ---------------------------------------------------
    'exp_cub_inclure': {
        'fr': "Inclure la cubature des tranchées",
        'en': "Include trench earthworks",
        'es': "Incluir la cubicación de zanjas",
        'pt': "Incluir a cubagem das valas",
        'de': "Grabenmassen einbeziehen",
    },
    'exp_cub_perimetre': {
        'fr': "Périmètre :", 'en': "Scope:", 'es': "Ámbito:",
        'pt': "Âmbito:", 'de': "Umfang:",
    },
    'exp_cub_contenu': {
        'fr': "Contenu :", 'en': "Content:", 'es': "Contenido:",
        'pt': "Conteúdo:", 'de': "Inhalt:",
    },
    'exp_cub_formats': {
        'fr': "Formats :", 'en': "Formats:", 'es': "Formatos:",
        'pt': "Formatos:", 'de': "Formate:",
    },
    'exp_cub_note': {
        'fr': "Les modes axe et BFS restent disponibles dans l'outil Cubature "
              "de la barre d'outils : ils demandent de désigner des ouvrages "
              "sur la carte.",
        'en': "The axis and BFS modes remain available in the Earthworks tool "
              "on the toolbar: they require picking structures on the map.",
        'es': "Los modos eje y BFS siguen disponibles en la herramienta "
              "Cubicación de la barra: requieren designar obras en el mapa.",
        'pt': "Os modos eixo e BFS continuam disponíveis na ferramenta "
              "Cubagem da barra: exigem designar órgãos no mapa.",
        'de': "Die Modi Achse und BFS bleiben im Werkzeug Massenermittlung "
              "verfügbar: sie erfordern die Auswahl von Bauwerken auf der Karte.",
    },

    # -- Onglet Coupes -----------------------------------------------------
    'exp_coupe_type': {
        'fr': "Coupe type {code}", 'en': "{code} typical section",
        'es': "Sección tipo {code}", 'pt': "Secção tipo {code}",
        'de': "Regelquerschnitt {code}",
    },
    'exp_coupe_format': {
        'fr': "Format :", 'en': "Format:", 'es': "Formato:",
        'pt': "Formato:", 'de': "Format:",
    },
    'exp_coupe_note': {
        'fr': "La coupe type est construite sur le diamètre le plus fréquent, "
              "le matériau dominant et la profondeur moyenne du réseau. "
              "Pour une coupe à un endroit précis, utilisez l'outil "
              "Coupe transversale de la barre d'outils.",
        'en': "The typical section uses the most frequent diameter, the dominant "
              "material and the average depth of the network. For a section at a "
              "given location, use the Cross-section tool on the toolbar.",
        'es': "La sección tipo usa el diámetro más frecuente, el material "
              "dominante y la profundidad media de la red. Para una sección en "
              "un punto concreto, use la herramienta Sección transversal.",
        'pt': "A secção tipo usa o diâmetro mais frequente, o material "
              "dominante e a profundidade média da rede. Para uma secção num "
              "ponto preciso, use a ferramenta Secção transversal.",
        'de': "Der Regelquerschnitt verwendet den häufigsten Durchmesser, das "
              "vorherrschende Material und die mittlere Tiefe des Netzes. Für "
              "einen Schnitt an einer bestimmten Stelle nutzen Sie das Werkzeug "
              "Querschnitt.",
    },

    # -- Comptes rendus d'export -------------------------------------------
    'msg_cubature_export_ok': {
        'fr': "Cubature : {nb} éléments exportés ({fichiers})",
        'en': "Earthworks: {nb} items exported ({fichiers})",
        'es': "Cubicación: {nb} elementos exportados ({fichiers})",
        'pt': "Cubagem: {nb} elementos exportados ({fichiers})",
        'de': "Massenermittlung: {nb} Elemente exportiert ({fichiers})",
    },
    'msg_cubature_export_vide': {
        'fr': "Cubature : aucun élément à exporter",
        'en': "Earthworks: nothing to export",
        'es': "Cubicación: nada que exportar",
        'pt': "Cubagem: nada a exportar",
        'de': "Massenermittlung: nichts zu exportieren",
    },
    'msg_coupe_export_ok': {
        'fr': "Coupe type {reseau} : {fichier}",
        'en': "{reseau} typical section: {fichier}",
        'es': "Sección tipo {reseau}: {fichier}",
        'pt': "Secção tipo {reseau}: {fichier}",
        'de': "Regelquerschnitt {reseau}: {fichier}",
    },
    'msg_coupe_export_vide': {
        'fr': "Coupe type {reseau} : données insuffisantes "
              "(diamètre, fil d'eau ou TN manquant)",
        'en': "{reseau} typical section: insufficient data "
              "(missing diameter, invert or ground level)",
        'es': "Sección tipo {reseau}: datos insuficientes "
              "(falta diámetro, cota de solera o TN)",
        'pt': "Secção tipo {reseau}: dados insuficientes "
              "(falta diâmetro, soleira ou TN)",
        'de': "Regelquerschnitt {reseau}: unzureichende Daten "
              "(Durchmesser, Sohle oder Gelände fehlt)",
    },
    'msg_export_sorties_ok': {
        'fr': "Export terminé", 'en': "Export complete",
        'es': "Exportación finalizada", 'pt': "Exportação concluída",
        'de': "Export abgeschlossen",
    },
    # -- Bouton Tout en un -------------------------------------------------
    'exp_tout_en_un': {
        'fr': "Toutes les pièces (ZIP)", 'en': "All documents (ZIP)",
        'es': "Todos los documentos (ZIP)", 'pt': "Todos os documentos (ZIP)",
        'de': "Alle Unterlagen (ZIP)",
    },
    'exp_tout_en_un_resume': {
        'fr': "Plan PDF + DXF, profils EU/EP, cubature remblai (PDF + XLSX) "
              "et coupes types, dans une seule archive.",
        'en': "PDF + DXF map, EU/EP profiles, backfill earthworks (PDF + XLSX) "
              "and typical sections, in a single archive.",
        'es': "Plano PDF + DXF, perfiles EU/EP, cubicación de relleno "
              "(PDF + XLSX) y secciones tipo, en un solo archivo.",
        'pt': "Planta PDF + DXF, perfis EU/EP, cubagem de aterro (PDF + XLSX) "
              "e secções tipo, num único arquivo.",
        'de': "Plan PDF + DXF, EU/EP-Längsschnitte, Verfüllmassen (PDF + XLSX) "
              "und Regelquerschnitte, in einem einzigen Archiv.",
    },
    'exp_tout_en_un_note': {
        'fr': "Produit toutes les sorties dans une seule archive : plan PDF "
              "et DXF, profils EU et EP, cubature de tout le projet (PDF et "
              "XLSX), coupes types EU et EP. Les cases ci-dessus sont "
              "ignorées. Le cadrage du plan reste à poser sur la carte, comme "
              "d'habitude : l'archive est refermée ensuite.",
        'en': "Produces every output in a single archive: PDF and DXF map, EU "
              "and EP profiles, project-wide earthworks (PDF and XLSX), EU and "
              "EP typical sections. The boxes above are ignored. The map "
              "framing is still placed on the canvas as usual: the archive is "
              "closed afterwards.",
        'es': "Genera todas las salidas en un solo archivo: plano PDF y DXF, "
              "perfiles EU y EP, cubicación de todo el proyecto (PDF y XLSX), "
              "secciones tipo EU y EP. Las casillas anteriores se ignoran. El "
              "encuadre del plano sigue colocándose en el mapa: el archivo se "
              "cierra después.",
        'pt': "Produz todas as saídas num único arquivo: planta PDF e DXF, "
              "perfis EU e EP, cubagem de todo o projeto (PDF e XLSX), secções "
              "tipo EU e EP. As caixas acima são ignoradas. O enquadramento da "
              "planta continua a ser colocado no mapa: o arquivo é fechado a "
              "seguir.",
        'de': "Erzeugt alle Ausgaben in einem einzigen Archiv: Plan als PDF und "
              "DXF, EU- und EP-Längsschnitte, Massenermittlung des gesamten "
              "Projekts (PDF und XLSX), Regelquerschnitte EU und EP. Die "
              "Kästchen oben werden ignoriert. Der Planausschnitt wird wie "
              "gewohnt auf der Karte gesetzt: das Archiv wird danach "
              "geschlossen.",
    },
    'msg_tout_en_un': {
        'fr': "Toutes les pièces", 'en': "All documents",
        'es': "Todos los documentos", 'pt': "Todos os documentos",
        'de': "Alle Unterlagen",
    },
    'msg_tout_en_un_pose': {
        'fr': "Sorties automatiques écrites. Posez maintenant le cadrage du "
              "plan : l'archive ZIP sera refermée ensuite.",
        'en': "Automatic outputs written. Now place the map framing: the ZIP "
              "archive will be closed afterwards.",
        'es': "Salidas automáticas escritas. Coloque ahora el encuadre del "
              "plano: el archivo ZIP se cerrará después.",
        'pt': "Saídas automáticas escritas. Coloque agora o enquadramento da "
              "planta: o arquivo ZIP será fechado a seguir.",
        'de': "Automatische Ausgaben geschrieben. Setzen Sie nun den "
              "Planausschnitt: das ZIP-Archiv wird danach geschlossen.",
    },
    'msg_zip_ok': {
        'fr': "Archive créée : {fichier} ({nb} fichiers)",
        'en': "Archive created: {fichier} ({nb} files)",
        'es': "Archivo creado: {fichier} ({nb} archivos)",
        'pt': "Arquivo criado: {fichier} ({nb} ficheiros)",
        'de': "Archiv erstellt: {fichier} ({nb} Dateien)",
    },
    'msg_zip_vide': {
        'fr': "Aucun fichier n'a pu être produit : archive non créée.",
        'en': "No file could be produced: archive not created.",
        'es': "No se pudo producir ningún archivo: archivo no creado.",
        'pt': "Nenhum ficheiro pôde ser produzido: arquivo não criado.",
        'de': "Es konnte keine Datei erzeugt werden: Archiv nicht erstellt.",
    },
    'msg_zip_erreur': {
        'fr': "Création de l'archive impossible : {erreur}",
        'en': "Could not create the archive: {erreur}",
        'es': "No se pudo crear el archivo: {erreur}",
        'pt': "Não foi possível criar o arquivo: {erreur}",
        'de': "Archiv konnte nicht erstellt werden: {erreur}",
    },
    # -- Cadrage des planches (fenetre d'impression) ------------------------
    'pd_cadrage': {
        'fr': "Cadrage :", 'en': "Sheet layout:", 'es': "Encuadre:",
        'pt': "Enquadramento:", 'de': "Blattaufteilung:",
    },
    'pd_cadrage_manuel': {
        'fr': "Pose manuelle sur la carte",
        'en': "Place sheets manually on the map",
        'es': "Colocación manual en el mapa",
        'pt': "Colocação manual no mapa",
        'de': "Blätter manuell auf der Karte setzen",
    },
    'pd_cadrage_auto': {
        'fr': "Cadrage automatique",
        'en': "Automatic layout",
        'es': "Encuadre automático",
        'pt': "Enquadramento automático",
        'de': "Automatische Aufteilung",
    },
    'pd_cadrage_note_manuel': {
        'fr': "Vous posez chaque planche : clic pour ancrer, clic pour "
              "orienter, clic droit pour exporter.",
        'en': "You place each sheet: click to anchor, click to orient, "
              "right-click to export.",
        'es': "Usted coloca cada plancha: clic para anclar, clic para "
              "orientar, clic derecho para exportar.",
        'pt': "Coloca cada prancha: clique para ancorar, clique para "
              "orientar, clique direito para exportar.",
        'de': "Sie setzen jedes Blatt: Klick zum Verankern, Klick zum "
              "Ausrichten, Rechtsklick zum Exportieren.",
    },
    'pd_cadrage_note_auto': {
        'fr': "Les planches sont calculées pour couvrir tout le réseau avec "
              "le moins de planches possible à l'échelle choisie, puis "
              "l'export part directement.",
        'en': "Sheets are computed to cover the whole network with as few "
              "pages as possible at the chosen scale, then the export starts "
              "straight away.",
        'es': "Las planchas se calculan para cubrir toda la red con el menor "
              "número de hojas posible a la escala elegida, y la exportación "
              "comienza de inmediato.",
        'pt': "As pranchas são calculadas para cobrir toda a rede com o menor "
              "número de folhas possível à escala escolhida, e a exportação "
              "começa de imediato.",
        'de': "Die Blätter werden so berechnet, dass das gesamte Netz mit so "
              "wenigen Seiten wie möglich im gewählten Maßstab abgedeckt wird; "
              "der Export startet danach sofort.",
    },
    'msg_cadrage_calcul': {
        'fr': "Calcul du cadrage automatique…",
        'en': "Computing automatic layout…",
        'es': "Calculando el encuadre automático…",
        'pt': "A calcular o enquadramento automático…",
        'de': "Automatische Aufteilung wird berechnet…",
    },
    'msg_cadrage_aucun': {
        'fr': "Aucun élément de réseau à cadrer : vérifiez que les couches "
              "EU ou EP contiennent des données.",
        'en': "No network feature to lay out: check that the EU or EP layers "
              "contain data.",
        'es': "Ningún elemento de red que encuadrar: compruebe que las capas "
              "EU o EP contienen datos.",
        'pt': "Nenhum elemento de rede para enquadrar: verifique se as camadas "
              "EU ou EP contêm dados.",
        'de': "Kein Netzelement zum Aufteilen: prüfen Sie, ob die EU- oder "
              "EP-Layer Daten enthalten.",
    },
    'msg_cadrage_beaucoup': {
        'fr': "Le cadrage automatique donne {nb} planches à l'échelle "
              "1 : {echelle}. L'export sera long. Continuer ?",
        'en': "The automatic layout yields {nb} sheets at scale 1:{echelle}. "
              "The export will take a while. Continue?",
        'es': "El encuadre automático da {nb} planchas a escala 1:{echelle}. "
              "La exportación será larga. ¿Continuar?",
        'pt': "O enquadramento automático dá {nb} pranchas à escala "
              "1:{echelle}. A exportação será longa. Continuar?",
        'de': "Die automatische Aufteilung ergibt {nb} Blätter im Maßstab "
              "1:{echelle}. Der Export wird lange dauern. Fortfahren?",
    },
    'msg_cadrage_pret': {
        'fr': "{nb} planches calculées à l'échelle 1 : {echelle}.",
        'en': "{nb} sheets computed at scale 1:{echelle}.",
        'es': "{nb} planchas calculadas a escala 1:{echelle}.",
        'pt': "{nb} pranchas calculadas à escala 1:{echelle}.",
        'de': "{nb} Blätter im Maßstab 1:{echelle} berechnet.",
    },
    'exp_impression_titre': {
        'fr': "Réglages du plan", 'en': "Map settings",
        'es': "Ajustes del plano", 'pt': "Definições da planta",
        'de': "Planeinstellungen",
    },
    'pd_plan_ensemble_case': {
        'fr': "Plan d'ensemble en première page",
        'en': "Overview map as first page",
        'es': "Plano de conjunto en la primera página",
        'pt': "Planta de conjunto na primeira página",
        'de': "Übersichtsplan als erste Seite",
    },
    'pd_plan_ensemble_note': {
        'fr': "Une première page situe toutes les planches, numérotées, sur "
              "une vue d'ensemble à échelle réduite.",
        'en': "A first page locates every sheet, numbered, on a reduced-scale "
              "overview.",
        'es': "Una primera página sitúa todas las planchas, numeradas, en una "
              "vista de conjunto a escala reducida.",
        'pt': "Uma primeira página situa todas as pranchas, numeradas, numa "
              "vista de conjunto à escala reduzida.",
        'de': "Eine erste Seite verortet alle nummerierten Blätter auf einer "
              "Übersicht in verkleinertem Maßstab.",
    },
    'exp_dossier': {
        'fr': "Dossier d'export :", 'en': "Output folder:",
        'es': "Carpeta de exportación:", 'pt': "Pasta de exportação:",
        'de': "Ausgabeordner:",
    },
    'exp_dossier_titre': {
        'fr': "Dossier d'export", 'en': "Output folder",
        'es': "Carpeta de exportación", 'pt': "Pasta de exportação",
        'de': "Ausgabeordner",
    },
    'exp_bouton': {
        'fr': "Exporter →", 'en': "Export →", 'es': "Exportar →",
        'pt': "Exportar →", 'de': "Exportieren →",
    },
    'exp_dossier_invalide': {
        'fr': "Dossier invalide", 'en': "Invalid folder",
        'es': "Carpeta no válida", 'pt': "Pasta inválida",
        'de': "Ungültiger Ordner",
    },
    'exp_dossier_absent': {
        'fr': "Le dossier d'export n'existe pas. Choisissez un dossier valide.",
        'en': "The output folder does not exist. Choose a valid folder.",
        'es': "La carpeta de exportación no existe. Elija una carpeta válida.",
        'pt': "A pasta de exportação não existe. Escolha uma pasta válida.",
        'de': "Der Ausgabeordner existiert nicht. Wählen Sie einen gültigen "
              "Ordner.",
    },
    'exp_profils_groupes': {
        'fr': "Profils groupés EU+EP  (PDF)",
        'en': "Combined EU+EP profiles (PDF)",
        'es': "Perfiles agrupados EU+EP (PDF)",
        'pt': "Perfis agrupados EU+EP (PDF)",
        'de': "Kombinierte EU+EP-Profile (PDF)",
    },
    'exp_ref': {
        'fr': "Réf :", 'en': "Ref:", 'es': "Ref.:",
        'pt': "Ref.:", 'de': "Ref.:",
    },
    'parcourir': {
        'fr': "Parcourir…", 'en': "Browse…", 'es': "Examinar…",
        'pt': "Procurar…", 'de': "Durchsuchen…",
    },

    # ─────────────────────────────────────────────────────────────────────
    #  Fenêtre Taille des étiquettes
    # ─────────────────────────────────────────────────────────────────────
    'et_choix_mode': {
        'fr': "Choisissez le mode de dimensionnement des étiquettes",
        'en': "Choose how label size is determined",
        'es': "Elija el modo de dimensionado de las etiquetas",
        'pt': "Escolha o modo de dimensionamento dos rótulos",
        'de': "Wählen Sie, wie die Beschriftungsgröße bestimmt wird",
    },
    'et_police_fixe': {
        'fr': "Taille de police fixe (points)", 'en': "Fixed font size (points)",
        'es': "Tamaño de fuente fijo (puntos)",
        'pt': "Tamanho de letra fixo (pontos)",
        'de': "Feste Schriftgröße (Punkt)",
    },
    'et_taille_points': {
        'fr': "Taille en points", 'en': "Size in points",
        'es': "Tamaño en puntos", 'pt': "Tamanho em pontos",
        'de': "Größe in Punkt",
    },
    'et_aide_fixe': {
        'fr': "<i>Taille constante à l'écran, indépendante du zoom.</i>",
        'en': "<i>Constant size on screen, independent of zoom.</i>",
        'es': "<i>Tamaño constante en pantalla, independiente del zoom.</i>",
        'pt': "<i>Tamanho constante no ecrã, independente do zoom.</i>",
        'de': "<i>Konstante Bildschirmgröße, unabhängig vom Zoom.</i>",
    },
    'et_adapte_echelle': {
        'fr': "Adapté à l'échelle d'impression",
        'en': "Matched to the printing scale",
        'es': "Adaptado a la escala de impresión",
        'pt': "Adaptado à escala de impressão",
        'de': "An den Druckmaßstab angepasst",
    },
    'et_echelle_cible': {
        'fr': "Échelle cible", 'en': "Target scale", 'es': "Escala objetivo",
        'pt': "Escala alvo", 'de': "Zielmaßstab",
    },
    'et_aide_echelle': {
        'fr': "<i>Taille proportionnelle au zoom — optimisée pour l'impression "
              "à l'échelle choisie.</i>",
        'en': "<i>Size proportional to zoom — tuned for printing at the chosen "
              "scale.</i>",
        'es': "<i>Tamaño proporcional al zoom — optimizado para la impresión a "
              "la escala elegida.</i>",
        'pt': "<i>Tamanho proporcional ao zoom — otimizado para a impressão à "
              "escala escolhida.</i>",
        'de': "<i>Größe proportional zum Zoom — auf den gewählten Maßstab "
              "abgestimmt.</i>",
    },
    'et_seuil': {
        'fr': "Seuil d'affichage", 'en': "Display threshold",
        'es': "Umbral de visualización", 'pt': "Limiar de exibição",
        'de': "Anzeigeschwelle",
    },
    'et_masquer_au_dela': {
        'fr': "Masquer les étiquettes au-delà de",
        'en': "Hide labels beyond",
        'es': "Ocultar las etiquetas más allá de",
        'pt': "Ocultar os rótulos para além de",
        'de': "Beschriftungen ausblenden ab",
    },
    'et_aide_seuil': {
        'fr': "<i>En dézoomant au-delà de ce seuil, le texte est de toute façon "
              "illisible mais reste calculé par le moteur de placement. Le "
              "masquer allège l'affichage sur les gros réseaux.</i>",
        'en': "<i>Beyond this threshold the text is unreadable anyway, yet the "
              "placement engine still computes it. Hiding it speeds up display "
              "on large networks.</i>",
        'es': "<i>Más allá de este umbral el texto es ilegible de todos modos, "
              "pero el motor de colocación sigue calculándolo. Ocultarlo "
              "aligera la visualización en redes grandes.</i>",
        'pt': "<i>Para além deste limiar o texto é ilegível de qualquer forma, "
              "mas o motor de posicionamento continua a calculá-lo. Ocultá-lo "
              "alivia a exibição em redes grandes.</i>",
        'de': "<i>Jenseits dieser Schwelle ist der Text ohnehin unlesbar, wird "
              "aber weiter berechnet. Ausblenden beschleunigt die Anzeige bei "
              "großen Netzen.</i>",
    },
    'et_apercu': {
        'fr': "→ {taille} m en unités carte  ({mm} mm sur papier)",
        'en': "→ {taille} m in map units ({mm} mm on paper)",
        'es': "→ {taille} m en unidades de mapa ({mm} mm en papel)",
        'pt': "→ {taille} m em unidades de mapa ({mm} mm no papel)",
        'de': "→ {taille} m in Karteneinheiten ({mm} mm auf Papier)",
    },
    'msg_export_stareau_ok': {
        'fr': "Export terminé — {fichier} ({detail})",
        'en': "Export complete — {fichier} ({detail})",
        'es': "Exportación finalizada — {fichier} ({detail})",
        'pt': "Exportação concluída — {fichier} ({detail})",
        'de': "Export abgeschlossen — {fichier} ({detail})",
    },

    # ─────────────────────────────────────────────────────────────────────
    #  Fenêtre Renseigner un élément
    # ─────────────────────────────────────────────────────────────────────
    'rens_titre': {
        'fr': "Renseignement – {type} {nom}",
        'en': "Attributes – {type} {nom}",
        'es': "Datos – {type} {nom}",
        'pt': "Dados – {type} {nom}",
        'de': "Angaben – {type} {nom}",
    },
    'rens_sous_titre': {
        'fr': "{type} – réseau {reseau}", 'en': "{type} – {reseau} network",
        'es': "{type} – red {reseau}", 'pt': "{type} – rede {reseau}",
        'de': "{type} – Netz {reseau}",
    },
    'rens_recalculer': {
        'fr': "Recalculer depuis la géométrie",
        'en': "Recalculate from the geometry",
        'es': "Recalcular desde la geometría",
        'pt': "Recalcular a partir da geometria",
        'de': "Aus der Geometrie neu berechnen",
    },
    'rens_calculer': {
        'fr': "Calculer", 'en': "Calculate", 'es': "Calcular",
        'pt': "Calcular", 'de': "Berechnen",
    },
    'rens_p_modifie': {
        'fr': "P modifié – que recalculer ?",
        'en': "Depth changed – what should be recalculated?",
        'es': "P modificado – ¿qué recalcular?",
        'pt': "P alterado – o que recalcular?",
        'de': "Tiefe geändert – was neu berechnen?",
    },
    'rens_p_question': {
        'fr': "La profondeur a changé.\nQuelle cote doit être recalculée ?",
        'en': "The depth has changed.\nWhich level should be recalculated?",
        'es': "La profundidad ha cambiado.\n¿Qué cota debe recalcularse?",
        'pt': "A profundidade mudou.\nQue cota deve ser recalculada?",
        'de': "Die Tiefe hat sich geändert.\nWelche Höhe soll neu berechnet "
              "werden?",
    },
    'rens_calcul_pente': {
        'fr': "Calcul pente", 'en': "Slope calculation",
        'es': "Cálculo de pendiente", 'pt': "Cálculo de declive",
        'de': "Gefälleberechnung",
    },
    'rens_couches_absentes': {
        'fr': "Les couches ne sont pas disponibles.",
        'en': "The layers are not available.",
        'es': "Las capas no están disponibles.",
        'pt': "As camadas não estão disponíveis.",
        'de': "Die Layer sind nicht verfügbar.",
    },
    'rens_fe_introuvables': {
        'fr': "Impossible de trouver les FE aux deux extrémités.\nVérifiez que "
              "les ouvrages sont bien renseignés.",
        'en': "Invert levels could not be found at both ends.\nCheck that the "
              "structures are filled in.",
        'es': "No se han encontrado las cotas de solera en ambos extremos.\n"
              "Compruebe que las obras están rellenadas.",
        'pt': "Não foi possível encontrar as soleiras nas duas extremidades.\n"
              "Verifique se as estruturas estão preenchidas.",
        'de': "Die Sohlhöhen konnten an beiden Enden nicht gefunden werden.\n"
              "Prüfen Sie, ob die Bauwerke ausgefüllt sind.",
    },
    'rens_longueur_requise': {
        'fr': "La longueur doit être renseignée avant de calculer la pente.",
        'en': "The length must be filled in before computing the slope.",
        'es': "Debe indicarse la longitud antes de calcular la pendiente.",
        'pt': "O comprimento deve ser indicado antes de calcular o declive.",
        'de': "Die Länge muss vor der Gefälleberechnung angegeben werden.",
    },

    # ─────────────────────────────────────────────────────────────────────
    #  Fenêtre Importer Star-DT
    # ─────────────────────────────────────────────────────────────────────
    'sdt_titre': {
        'fr': "Importer un fichier Star-DT", 'en': "Import a Star-DT file",
        'es': "Importar un archivo Star-DT", 'pt': "Importar um ficheiro Star-DT",
        'de': "Star-DT-Datei importieren",
    },
    'sdt_fichier_gml': {
        'fr': "Fichier GML :", 'en': "GML file:", 'es': "Archivo GML:",
        'pt': "Ficheiro GML:", 'de': "GML-Datei:",
    },
    'sdt_deposer': {
        'fr': "Parcourir… ou glisser-déposer un ou plusieurs fichiers ici",
        'en': "Browse… or drag and drop one or more files here",
        'es': "Examinar… o arrastre y suelte uno o varios archivos aquí",
        'pt': "Procurar… ou arraste e largue um ou mais ficheiros aqui",
        'de': "Durchsuchen… oder eine oder mehrere Dateien hierher ziehen",
    },
    'sdt_sortie_gpkg': {
        'fr': "Sortie GPKG :", 'en': "GPKG output:", 'es': "Salida GPKG:",
        'pt': "Saída GPKG:", 'de': "GPKG-Ausgabe:",
    },
    'sdt_analyser': {
        'fr': "Analyser le fichier", 'en': "Analyse the file",
        'es': "Analizar el archivo", 'pt': "Analisar o ficheiro",
        'de': "Datei analysieren",
    },
    'sdt_types_trouves': {
        'fr': "Types d'éléments trouvés", 'en': "Element types found",
        'es': "Tipos de elementos encontrados",
        'pt': "Tipos de elementos encontrados",
        'de': "Gefundene Elementtypen",
    },
    'sdt_nb_fichiers': {
        'fr': "{nb} fichiers : {noms}", 'en': "{nb} files: {noms}",
        'es': "{nb} archivos: {noms}", 'pt': "{nb} ficheiros: {noms}",
        'de': "{nb} Dateien: {noms}",
    },
    'sdt_gpkg_sortie': {
        'fr': "GeoPackage de sortie", 'en': "Output GeoPackage",
        'es': "GeoPackage de salida", 'pt': "GeoPackage de saída",
        'de': "Ausgabe-GeoPackage",
    },
    'sdt_aucun_type': {
        'fr': "Aucun type d'élément Star-DT détecté.",
        'en': "No Star-DT element type detected.",
        'es': "No se ha detectado ningún tipo de elemento Star-DT.",
        'pt': "Nenhum tipo de elemento Star-DT detetado.",
        'de': "Kein Star-DT-Elementtyp erkannt.",
    },
    'sdt_nb_elements': {
        'fr': "{nb} élément(s)", 'en': "{nb} element(s)",
        'es': "{nb} elemento(s)", 'pt': "{nb} elemento(s)",
        'de': "{nb} Element(e)",
    },

    # ─────────────────────────────────────────────────────────────────────
    #  Fenêtre Coupe transversale
    # ─────────────────────────────────────────────────────────────────────
    'ct_titre': {
        'fr': "Plan de coupe transversale", 'en': "Cross section drawing",
        'es': "Plano de sección transversal", 'pt': "Desenho de corte transversal",
        'de': "Querschnittsplan",
    },
    'ct_format': {
        'fr': "Format :", 'en': "Sheet size:", 'es': "Formato:",
        'pt': "Formato:", 'de': "Format:",
    },
    'ct_echelle_vide': {
        'fr': "Échelle : —", 'en': "Scale: —", 'es': "Escala: —",
        'pt': "Escala: —", 'de': "Maßstab: —",
    },
    'ct_echelle': {
        'fr': "Échelle : 1:{valeur}", 'en': "Scale: 1:{valeur}",
        'es': "Escala: 1:{valeur}", 'pt': "Escala: 1:{valeur}",
        'de': "Maßstab: 1:{valeur}",
    },
    'ct_export_pdf': {
        'fr': "Exporter PDF…", 'en': "Export PDF…", 'es': "Exportar PDF…",
        'pt': "Exportar PDF…", 'de': "PDF exportieren…",
    },
    'ct_export_png': {
        'fr': "Exporter PNG…", 'en': "Export PNG…", 'es': "Exportar PNG…",
        'pt': "Exportar PNG…", 'de': "PNG exportieren…",
    },
    'ct_enregistrer_pdf': {
        'fr': "Enregistrer le plan de coupe en PDF",
        'en': "Save the section drawing as PDF",
        'es': "Guardar el plano de sección en PDF",
        'pt': "Guardar o desenho de corte em PDF",
        'de': "Schnittplan als PDF speichern",
    },
    'ct_enregistrer_png': {
        'fr': "Enregistrer le plan de coupe en PNG",
        'en': "Save the section drawing as PNG",
        'es': "Guardar el plano de sección en PNG",
        'pt': "Guardar o desenho de corte em PNG",
        'de': "Schnittplan als PNG speichern",
    },
    'ct_export_pdf_titre': {
        'fr': "Export PDF", 'en': "PDF export", 'es': "Exportación PDF",
        'pt': "Exportação PDF", 'de': "PDF-Export",
    },
    'ct_export_png_titre': {
        'fr': "Export PNG", 'en': "PNG export", 'es': "Exportación PNG",
        'pt': "Exportação PNG", 'de': "PNG-Export",
    },
    'ct_exporte': {
        'fr': "Plan de coupe exporté :\n{chemin}",
        'en': "Section drawing exported:\n{chemin}",
        'es': "Plano de sección exportado:\n{chemin}",
        'pt': "Desenho de corte exportado:\n{chemin}",
        'de': "Schnittplan exportiert:\n{chemin}",
    },
    # Libellés dessinés dans le plan de coupe (couches, cotes, cartouche)
    'ct_couche_lit_pose': {
        'fr': "Lit de pose", 'en': "Bedding", 'es': "Cama",
        'pt': "Leito", 'de': "Bettung",
    },
    'ct_couche_enrobage': {
        'fr': "Enrobage", 'en': "Surround", 'es': "Recubrimiento",
        'pt': "Envolvimento", 'de': "Ummantelung",
    },
    'ct_couche_remblai': {
        'fr': "Remblai", 'en': "Backfill", 'es': "Relleno",
        'pt': "Aterro", 'de': "Verfüllung",
    },
    'ct_couche_chaussee_inf': {
        'fr': "Chaussée inf.", 'en': "Sub-base", 'es': "Base",
        'pt': "Base", 'de': "Tragschicht",
    },
    'ct_couche_chaussee_sup': {
        'fr': "Chaussée sup.", 'en': "Surface course", 'es': "Rodadura",
        'pt': "Desgaste", 'de': "Deckschicht",
    },
    'ct_prof_totale': {
        'fr': "Prof.\ntotale\n{valeur} m", 'en': "Total\ndepth\n{valeur} m",
        'es': "Prof.\ntotal\n{valeur} m", 'pt': "Prof.\ntotal\n{valeur} m",
        'de': "Gesamt-\ntiefe\n{valeur} m",
    },
    'ct_axe_largeur': {
        'fr': "Largeur de tranchée (m)", 'en': "Trench width (m)",
        'es': "Ancho de zanja (m)", 'pt': "Largura da vala (m)",
        'de': "Grabenbreite (m)",
    },
    'ct_axe_altitude': {
        'fr': "Altitude NGF (m)", 'en': "Elevation (m)",
        'es': "Cota (m)", 'pt': "Cota (m)", 'de': "Höhe (m)",
    },
    'ct_pas_de_trait': {
        'fr': "Trait de coupe non disponible", 'en': "Section line unavailable",
        'es': "Línea de corte no disponible", 'pt': "Linha de corte indisponível",
        'de': "Schnittlinie nicht verfügbar",
    },
    'ct_aucune_couche': {
        'fr': "Aucune couche visible", 'en': "No visible layer",
        'es': "Ninguna capa visible", 'pt': "Nenhuma camada visível",
        'de': "Keine sichtbare Ebene",
    },
    'ct_cartouche': {
        'fr': "Projet : {projet}     Échelle : 1:{echelle}     Date : {date}",
        'en': "Project: {projet}     Scale: 1:{echelle}     Date: {date}",
        'es': "Proyecto: {projet}     Escala: 1:{echelle}     Fecha: {date}",
        'pt': "Projeto: {projet}     Escala: 1:{echelle}     Data: {date}",
        'de': "Projekt: {projet}     Maßstab: 1:{echelle}     Datum: {date}",
    },
    'ct_titre_plan': {
        'fr': "PLAN DE COUPE  —  {titre}", 'en': "SECTION DRAWING  —  {titre}",
        'es': "PLANO DE SECCIÓN  —  {titre}",
        'pt': "DESENHO DE CORTE  —  {titre}",
        'de': "SCHNITTPLAN  —  {titre}",
    },
    'ct_coupe_defaut': {
        'fr': "Coupe transversale", 'en': "Cross section",
        'es': "Sección transversal", 'pt': "Corte transversal",
        'de': "Querschnitt",
    },

    # ─────────────────────────────────────────────────────────────────────
    #  Fenêtre Profil en long
    # ─────────────────────────────────────────────────────────────────────
    'pf_options': {
        'fr': "Options du profil en long",
        'en': "Longitudinal profile options",
        'es': "Opciones del perfil longitudinal",
        'pt': "Opções do perfil longitudinal",
        'de': "Optionen des Längsschnitts",
    },
    'pf_elements': {
        'fr': "Éléments à afficher :", 'en': "Items to show:",
        'es': "Elementos a mostrar:", 'pt': "Elementos a mostrar:",
        'de': "Anzuzeigende Elemente:",
    },
    'pf_tableau': {
        'fr': "Tableau de valeurs", 'en': "Value table",
        'es': "Tabla de valores", 'pt': "Tabela de valores",
        'de': "Werttabelle",
    },
    'pf_fleches': {
        'fr': "Emplacement des piquages (flèches)",
        'en': "Tap-in locations (arrows)",
        'es': "Ubicación de las conexiones (flechas)",
        'pt': "Localização das ligações (setas)",
        'de': "Anschlusspunkte (Pfeile)",
    },
    'pf_noms_piquages': {
        'fr': "Noms des piquages", 'en': "Tap-in names",
        'es': "Nombres de las conexiones", 'pt': "Nomes das ligações",
        'de': "Namen der Anschlüsse",
    },
    'pf_distance_piquage': {
        'fr': "Distance de piquage", 'en': "Tap-in chainage",
        'es': "Distancia de conexión", 'pt': "Distância de ligação",
        'de': "Anschlussstation",
    },
    'pf_format_papier': {
        'fr': "Format papier :", 'en': "Paper size:", 'es': "Formato de papel:",
        'pt': "Formato de papel:", 'de': "Papierformat:",
    },
    'pf_tracer': {
        'fr': "Tracer le profil", 'en': "Draw the profile",
        'es': "Trazar el perfil", 'pt': "Traçar o perfil",
        'de': "Profil zeichnen",
    },
    'pf_titre': {
        'fr': "Profil en long – {reseau} · {debut} → {fin}",
        'en': "Longitudinal profile – {reseau} · {debut} → {fin}",
        'es': "Perfil longitudinal – {reseau} · {debut} → {fin}",
        'pt': "Perfil longitudinal – {reseau} · {debut} → {fin}",
        'de': "Längsschnitt – {reseau} · {debut} → {fin}",
    },
    'pf_matplotlib_titre': {
        'fr': "matplotlib manquant", 'en': "matplotlib missing",
        'es': "falta matplotlib", 'pt': "matplotlib em falta",
        'de': "matplotlib fehlt",
    },
    'pf_matplotlib_msg': {
        'fr': "matplotlib est nécessaire pour afficher le profil.\nInstallez-le "
              "via : pip install matplotlib",
        'en': "matplotlib is required to display the profile.\nInstall it with: "
              "pip install matplotlib",
        'es': "matplotlib es necesario para mostrar el perfil.\nInstálelo con: "
              "pip install matplotlib",
        'pt': "matplotlib é necessário para mostrar o perfil.\nInstale-o com: "
              "pip install matplotlib",
        'de': "matplotlib wird zur Anzeige des Profils benötigt.\nInstallation: "
              "pip install matplotlib",
    },
    'pf_exporter_en': {
        'fr': "Exporter le profil en {format}",
        'en': "Export the profile as {format}",
        'es': "Exportar el perfil en {format}",
        'pt': "Exportar o perfil em {format}",
        'de': "Profil als {format} exportieren",
    },

    # ─────────────────────────────────────────────────────────────────────
    #  Fenêtre Cubature des tranchées
    # ─────────────────────────────────────────────────────────────────────
    'cb_titre': {
        'fr': "Cubature des tranchées", 'en': "Trench volumes",
        'es': "Cubicación de zanjas", 'pt': "Cubagem de valas",
        'de': "Grabenmassen",
    },
    'cb_detail_remblai': {
        'fr': "Afficher le détail remblai (lit de pose, enrobage, chaussée…)",
        'en': "Show the backfill breakdown (bedding, surround, roadway…)",
        'es': "Mostrar el desglose del relleno (cama, recubrimiento, calzada…)",
        'pt': "Mostrar a decomposição do aterro (leito, envolvimento, faixa…)",
        'de': "Verfüllungsaufteilung anzeigen (Bettung, Ummantelung, Fahrbahn…)",
    },
    'cb_export_csv': {
        'fr': "Exporter CSV", 'en': "Export CSV", 'es': "Exportar CSV",
        'pt': "Exportar CSV", 'de': "CSV exportieren",
    },
    'cb_export_pdf': {
        'fr': "Exporter PDF", 'en': "Export PDF", 'es': "Exportar PDF",
        'pt': "Exportar PDF", 'de': "PDF exportieren",
    },
    'cb_export_xlsx': {
        'fr': "Exporter Excel (.xlsx)", 'en': "Export Excel (.xlsx)",
        'es': "Exportar Excel (.xlsx)", 'pt': "Exportar Excel (.xlsx)",
        'de': "Excel exportieren (.xlsx)",
    },
    'cb_enregistrer_csv': {
        'fr': "Exporter en CSV", 'en': "Export to CSV", 'es': "Exportar a CSV",
        'pt': "Exportar para CSV", 'de': "Als CSV exportieren",
    },
    'cb_enregistrer_pdf': {
        'fr': "Exporter en PDF", 'en': "Export to PDF", 'es': "Exportar a PDF",
        'pt': "Exportar para PDF", 'de': "Als PDF exportieren",
    },
    'cb_enregistrer_xlsx': {
        'fr': "Exporter en Excel", 'en': "Export to Excel",
        'es': "Exportar a Excel", 'pt': "Exportar para Excel",
        'de': "Als Excel exportieren",
    },
    'cb_err_csv': {
        'fr': "Erreur export CSV", 'en': "CSV export error",
        'es': "Error de exportación CSV", 'pt': "Erro de exportação CSV",
        'de': "Fehler beim CSV-Export",
    },
    'cb_err_pdf': {
        'fr': "Erreur export PDF", 'en': "PDF export error",
        'es': "Error de exportación PDF", 'pt': "Erro de exportação PDF",
        'de': "Fehler beim PDF-Export",
    },
    'cb_err_xlsx': {
        'fr': "Erreur export Excel", 'en': "Excel export error",
        'es': "Error de exportación Excel", 'pt': "Erro de exportação Excel",
        'de': "Fehler beim Excel-Export",
    },
    'cb_reportlab': {
        'fr': "Impossible d'installer reportlab automatiquement.\n\nInstallez-le "
              "manuellement : pip install reportlab\n\nErreur : {erreur}",
        'en': "reportlab could not be installed automatically.\n\nInstall it "
              "manually: pip install reportlab\n\nError: {erreur}",
        'es': "No se ha podido instalar reportlab automáticamente.\n\nInstálelo "
              "manualmente: pip install reportlab\n\nError: {erreur}",
        'pt': "Não foi possível instalar o reportlab automaticamente.\n\n"
              "Instale-o manualmente: pip install reportlab\n\nErro: {erreur}",
        'de': "reportlab konnte nicht automatisch installiert werden.\n\n"
              "Manuell installieren: pip install reportlab\n\nFehler: {erreur}",
    },
    'cb_options_titre': {
        'fr': "Cubature de tranchées", 'en': "Trench volumes",
        'es': "Cubicación de zanjas", 'pt': "Cubagem de valas",
        'de': "Grabenmassen",
    },
    'cb_perimetre': {
        'fr': "Périmètre", 'en': "Scope", 'es': "Perímetro",
        'pt': "Perímetro", 'de': "Bereich",
    },
    'cb_tout': {
        'fr': "Tout le projet (EU + EP)", 'en': "Whole project (EU + EP)",
        'es': "Todo el proyecto (EU + EP)", 'pt': "Todo o projeto (EU + EP)",
        'de': "Gesamtes Projekt (EU + EP)",
    },
    'cb_eu_seul': {
        'fr': "EU seulement", 'en': "EU only", 'es': "Solo EU",
        'pt': "Apenas EU", 'de': "Nur EU",
    },
    'cb_ep_seul': {
        'fr': "EP seulement", 'en': "EP only", 'es': "Solo EP",
        'pt': "Apenas EP", 'de': "Nur EP",
    },
    'cb_types': {
        'fr': "Types d'ouvrages", 'en': "Structure types",
        'es': "Tipos de obras", 'pt': "Tipos de estruturas",
        'de': "Bauwerkstypen",
    },
    'cb_conduites': {
        'fr': "Conduites", 'en': "Pipes", 'es': "Tuberías",
        'pt': "Condutas", 'de': "Leitungen",
    },
    'cb_branchements': {
        'fr': "Branchements", 'en': "Service connections", 'es': "Acometidas",
        'pt': "Ramais", 'de': "Hausanschlüsse",
    },
    'cb_mode': {
        'fr': "Mode de sélection", 'en': "Selection mode",
        'es': "Modo de selección", 'pt': "Modo de seleção",
        'de': "Auswahlmodus",
    },
    'cb_mode_bfs': {
        'fr': "Sélectionner 2 regards (parcours BFS)",
        'en': "Select 2 manholes (breadth-first walk)",
        'es': "Seleccionar 2 pozos (recorrido BFS)",
        'pt': "Selecionar 2 caixas (percurso BFS)",
        'de': "2 Schächte wählen (Breitensuche)",
    },
    'cb_mode_axe': {
        'fr': "Tracer un axe (capture buffer 3 m)",
        'en': "Draw an axis (3 m capture buffer)",
        'es': "Trazar un eje (búfer de captura de 3 m)",
        'pt': "Traçar um eixo (buffer de captura de 3 m)",
        'de': "Achse zeichnen (3 m Fangpuffer)",
    },
    'cb_choisir_type': {
        'fr': "Veuillez sélectionner au moins un type d'ouvrage.",
        'en': "Please select at least one structure type.",
        'es': "Seleccione al menos un tipo de obra.",
        'pt': "Selecione pelo menos um tipo de estrutura.",
        'de': "Bitte mindestens einen Bauwerkstyp auswählen.",
    },

    # ─────────────────────────────────────────────────────────────────────
    #  Contenu des rapports (PDF, Excel, CSV)
    # ─────────────────────────────────────────────────────────────────────
    'rap_cubature': {
        'fr': "Cubature de tranchées", 'en': "Trench volumes",
        'es': "Cubicación de zanjas", 'pt': "Cubagem de valas",
        'de': "Grabenmassen",
    },
    'rap_remblai': {
        'fr': "Remblai de tranchées", 'en': "Trench backfill",
        'es': "Relleno de zanjas", 'pt': "Aterro de valas",
        'de': "Grabenverfüllung",
    },
    'rap_date': {
        'fr': "Date : {date}", 'en': "Date: {date}", 'es': "Fecha: {date}",
        'pt': "Data: {date}", 'de': "Datum: {date}",
    },
    'rap_parametres': {
        'fr': "Paramètres de calcul", 'en': "Calculation parameters",
        'es': "Parámetros de cálculo", 'pt': "Parâmetros de cálculo",
        'de': "Berechnungsparameter",
    },
    'rap_reseau_titre': {
        'fr': "Réseau {code} — {libelle}", 'en': "{code} network — {libelle}",
        'es': "Red {code} — {libelle}", 'pt': "Rede {code} — {libelle}",
        'de': "Netz {code} — {libelle}",
    },
    'rap_eaux_usees': {
        'fr': "Eaux Usées", 'en': "Wastewater", 'es': "Aguas residuales",
        'pt': "Águas residuais", 'de': "Schmutzwasser",
    },
    'rap_eaux_pluviales': {
        'fr': "Eaux Pluviales", 'en': "Stormwater", 'es': "Aguas pluviales",
        'pt': "Águas pluviais", 'de': "Regenwasser",
    },
    'rap_sous_total': {
        'fr': "Sous-total {libelle} {reseau} ({nb})",
        'en': "Subtotal {libelle} {reseau} ({nb})",
        'es': "Subtotal {libelle} {reseau} ({nb})",
        'pt': "Subtotal {libelle} {reseau} ({nb})",
        'de': "Zwischensumme {libelle} {reseau} ({nb})",
    },
    'rap_sous_total_court': {
        'fr': "Sous-total {reseau}", 'en': "Subtotal {reseau}",
        'es': "Subtotal {reseau}", 'pt': "Subtotal {reseau}",
        'de': "Zwischensumme {reseau}",
    },
    'rap_total_reseau': {
        'fr': "Total Réseau {reseau} : surface ouverte <b>{surface} m²</b>  —  "
              "déblai <b>{deblai} m³</b>  ({nb} élément(s))",
        'en': "{reseau} network total: open area <b>{surface} m²</b>  —  "
              "excavation <b>{deblai} m³</b>  ({nb} item(s))",
        'es': "Total red {reseau}: superficie abierta <b>{surface} m²</b>  —  "
              "desmonte <b>{deblai} m³</b>  ({nb} elemento(s))",
        'pt': "Total rede {reseau}: superfície aberta <b>{surface} m²</b>  —  "
              "escavação <b>{deblai} m³</b>  ({nb} elemento(s))",
        'de': "Summe Netz {reseau}: offene Fläche <b>{surface} m²</b>  —  "
              "Aushub <b>{deblai} m³</b>  ({nb} Element(e))",
    },
    'rap_recapitulatif': {
        'fr': "Récapitulatif projet", 'en': "Project summary",
        'es': "Resumen del proyecto", 'pt': "Resumo do projeto",
        'de': "Projektübersicht",
    },
    'rap_recapitulatif_court': {
        'fr': "Récapitulatif", 'en': "Summary", 'es': "Resumen",
        'pt': "Resumo", 'de': "Übersicht",
    },
    'rap_total_projet': {
        'fr': "TOTAL PROJET", 'en': "PROJECT TOTAL", 'es': "TOTAL PROYECTO",
        'pt': "TOTAL DO PROJETO", 'de': "PROJEKTSUMME",
    },
    'rap_synthese': {
        'fr': "Synthèse des ouvrages", 'en': "Structure summary",
        'es': "Resumen de las obras", 'pt': "Resumo das estruturas",
        'de': "Bauwerksübersicht",
    },
    'rap_synthese_court': {
        'fr': "Synthèse ouvrages", 'en': "Structure summary",
        'es': "Resumen de obras", 'pt': "Resumo de estruturas",
        'de': "Bauwerksübersicht",
    },
    'rap_troncons': {
        'fr': "Tronçons", 'en': "Pipe segments", 'es': "Tramos",
        'pt': "Troços", 'de': "Haltungen",
    },
    'rap_regards': {
        'fr': "Regards", 'en': "Manholes", 'es': "Pozos",
        'pt': "Caixas", 'de': "Schächte",
    },
    'rap_tabourets': {
        'fr': "Tabourets", 'en': "Inspection chambers", 'es': "Arquetas",
        'pt': "Câmaras", 'de': "Anschlussschächte",
    },
    'rap_total_troncons': {
        'fr': "Total tronçons", 'en': "Total pipe segments",
        'es': "Total tramos", 'pt': "Total troços", 'de': "Summe Haltungen",
    },
    'rap_total_branchements': {
        'fr': "Total branchements", 'en': "Total service connections",
        'es': "Total acometidas", 'pt': "Total ramais",
        'de': "Summe Hausanschlüsse",
    },
    'rap_total_regards': {
        'fr': "Total regards", 'en': "Total manholes", 'es': "Total pozos",
        'pt': "Total caixas", 'de': "Summe Schächte",
    },
    'rap_total_tabourets': {
        'fr': "Total tabourets", 'en': "Total inspection chambers",
        'es': "Total arquetas", 'pt': "Total câmaras",
        'de': "Summe Anschlussschächte",
    },
    'rap_long_totale': {
        'fr': "Long. totale (m)", 'en': "Total length (m)",
        'es': "Long. total (m)", 'pt': "Compr. total (m)",
        'de': "Gesamtlänge (m)",
    },
    'rap_deblai': {
        'fr': "Déblai", 'en': "Excavation", 'es': "Desmonte",
        'pt': "Escavação", 'de': "Aushub",
    },
    'rap_deblai_total': {
        'fr': "Déblai total (m³)", 'en': "Total excavation (m³)",
        'es': "Desmonte total (m³)", 'pt': "Escavação total (m³)",
        'de': "Aushub gesamt (m³)",
    },
    'rap_metre': {
        'fr': "Métré", 'en': "Measurement", 'es': "Medición",
        'pt': "Medição", 'de': "Aufmaß",
    },
    'rap_remblai_decomposition': {
        'fr': "Remblai — décomposition (m³)", 'en': "Backfill — breakdown (m³)",
        'es': "Relleno — desglose (m³)", 'pt': "Aterro — decomposição (m³)",
        'de': "Verfüllung — Aufteilung (m³)",
    },
    'rap_donnees_detaillees': {
        'fr': "Données détaillées", 'en': "Detailed data",
        'es': "Datos detallados", 'pt': "Dados detalhados",
        'de': "Detaildaten",
    },
    'rap_sous_total_affichees': {
        'fr': "Sous-total lignes affichées", 'en': "Subtotal of shown rows",
        'es': "Subtotal de las filas mostradas",
        'pt': "Subtotal das linhas mostradas",
        'de': "Zwischensumme der angezeigten Zeilen",
    },
    'rap_nb': {
        'fr': "Nb", 'en': "Qty", 'es': "Nº", 'pt': "Nº", 'de': "Anz.",
    },
    'rap_surf_ouv': {
        'fr': "Surf. ouv. (m²)", 'en': "Open area (m²)",
        'es': "Sup. abierta (m²)", 'pt': "Sup. aberta (m²)",
        'de': "Offene Fläche (m²)",
    },
    'rap_page': {
        'fr': "Page {n}", 'en': "Page {n}", 'es': "Página {n}",
        'pt': "Página {n}", 'de': "Seite {n}",
    },
    'rap_mat': {
        'fr': "Mat.", 'en': "Mat.", 'es': "Mat.", 'pt': "Mat.", 'de': "Mat.",
    },
    'rap_debut': {
        'fr': "Début", 'en': "Start", 'es': "Inicio", 'pt': "Início",
        'de': "Anfang",
    },
    'rap_fin': {
        'fr': "Fin", 'en': "End", 'es': "Fin", 'pt': "Fim", 'de': "Ende",
    },
    'rap_l2d': {
        'fr': "L. 2D", 'en': "L. 2D", 'es': "L. 2D", 'pt': "C. 2D",
        'de': "L. 2D",
    },
    'rap_l3d': {
        'fr': "L. 3D", 'en': "L. 3D", 'es': "L. 3D", 'pt': "C. 3D",
        'de': "L. 3D",
    },
    'rap_pente': {
        'fr': "Pente", 'en': "Slope", 'es': "Pendiente", 'pt': "Declive",
        'de': "Gefälle",
    },
    'rap_prof_moy': {
        'fr': "Prof. moy.", 'en': "Avg. depth", 'es': "Prof. media",
        'pt': "Prof. média", 'de': "Mittl. Tiefe",
    },
    'rap_larg': {
        'fr': "Larg.", 'en': "Width", 'es': "Ancho", 'pt': "Larg.",
        'de': "Breite",
    },
    'rap_surf': {
        'fr': "Surf.", 'en': "Area", 'es': "Sup.", 'pt': "Sup.",
        'de': "Fläche",
    },
    'col_profondeur_moy': {
        'fr': "Prof. moy. (m)", 'en': "Avg. depth (m)",
        'es': "Prof. media (m)", 'pt': "Prof. média (m)",
        'de': "Mittl. Tiefe (m)",
    },
    'col_largeur': {
        'fr': "Largeur (m)", 'en': "Width (m)", 'es': "Ancho (m)",
        'pt': "Largura (m)", 'de': "Breite (m)",
    },
    # En-tÃªtes du tableau de cubature / remblai (Ã©cran, CSV, XLSX)
    'col_id': {
        'fr': "ID", 'en': "ID", 'es': "ID", 'pt': "ID", 'de': "ID",
    },
    'col_diametre_court': {
        'fr': "Ã˜ (mm)", 'en': "Ã˜ (mm)", 'es': "Ã˜ (mm)",
        'pt': "Ã˜ (mm)", 'de': "Ã˜ (mm)",
    },
    'col_nom_debut': {
        'fr': "Nom dÃ©but", 'en': "Start name", 'es': "Nombre inicio",
        'pt': "Nome inÃ­cio", 'de': "Name Anfang",
    },
    'col_nom_fin': {
        'fr': "Nom fin", 'en': "End name", 'es': "Nombre fin",
        'pt': "Nome fim", 'de': "Name Ende",
    },
    'col_long_2d': {
        'fr': "Long. 2D (m)", 'en': "Length 2D (m)", 'es': "Long. 2D (m)",
        'pt': "Compr. 2D (m)", 'de': "LÃ¤nge 2D (m)",
    },
    'col_long_3d': {
        'fr': "Long. 3D (m)", 'en': "Length 3D (m)", 'es': "Long. 3D (m)",
        'pt': "Compr. 3D (m)", 'de': "LÃ¤nge 3D (m)",
    },
    'col_deblai': {
        'fr': "DÃ©blai (mÂ³)", 'en': "Excavation (mÂ³)", 'es': "Desmonte (mÂ³)",
        'pt': "EscavaÃ§Ã£o (mÂ³)", 'de': "Aushub (mÂ³)",
    },
    'col_csv_remblai': {
        'fr': "Remblai : {libelle}", 'en': "Backfill: {libelle}",
        'es': "Relleno: {libelle}", 'pt': "Aterro: {libelle}",
        'de': "VerfÃ¼llung: {libelle}",
    },
    # Décomposition du remblai : libellés courts (PDF) et longs (récapitulatif)
    'rap_vol_lit_pose': {
        'fr': "Lit pose", 'en': "Bedding", 'es': "Cama", 'pt': "Leito",
        'de': "Bettung",
    },
    'rap_vol_enrobage': {
        'fr': "Enrobage", 'en': "Surround", 'es': "Recubrimiento",
        'pt': "Envolvimento", 'de': "Ummantelung",
    },
    'rap_vol_conduite': {
        'fr': "Conduite", 'en': "Pipe", 'es': "Tubería", 'pt': "Conduta",
        'de': "Leitung",
    },
    'rap_vol_ch_inf': {
        'fr': "Ch.inf", 'en': "Sub-base", 'es': "Base", 'pt': "Base",
        'de': "Tragschicht",
    },
    'rap_vol_ch_sup': {
        'fr': "Ch.sup", 'en': "Surface", 'es': "Rodadura", 'pt': "Desgaste",
        'de': "Deckschicht",
    },
    'rap_vol_remblai': {
        'fr': "Remblai", 'en': "Backfill", 'es': "Relleno", 'pt': "Aterro",
        'de': "Verfüllung",
    },
    'rap_recap_lit_pose': {
        'fr': "Lit pose (m³)", 'en': "Bedding (m³)", 'es': "Cama (m³)",
        'pt': "Leito (m³)", 'de': "Bettung (m³)",
    },
    'rap_recap_enrobage': {
        'fr': "Enrobage (m³)", 'en': "Surround (m³)", 'es': "Recubrimiento (m³)",
        'pt': "Envolvimento (m³)", 'de': "Ummantelung (m³)",
    },
    'rap_recap_conduite': {
        'fr': "Conduite (m³)", 'en': "Pipe (m³)", 'es': "Tubería (m³)",
        'pt': "Conduta (m³)", 'de': "Leitung (m³)",
    },
    'rap_recap_ch_inf': {
        'fr': "Ch. inf (m³)", 'en': "Sub-base (m³)", 'es': "Base (m³)",
        'pt': "Base (m³)", 'de': "Tragschicht (m³)",
    },
    'rap_recap_ch_sup': {
        'fr': "Ch. sup (m³)", 'en': "Surface (m³)", 'es': "Rodadura (m³)",
        'pt': "Desgaste (m³)", 'de': "Deckschicht (m³)",
    },
    'rap_recap_remblai': {
        'fr': "Vol. remblai (m³)", 'en': "Backfill vol. (m³)",
        'es': "Vol. relleno (m³)", 'pt': "Vol. aterro (m³)",
        'de': "Verfüllvol. (m³)",
    },
    # Ligne des paramètres de calcul, en tête des rapports
    'rap_par_ch_inf': {
        'fr': "Chaussée inf.", 'en': "Sub-base", 'es': "Base",
        'pt': "Base", 'de': "Tragschicht",
    },
    'rap_par_ch_sup': {
        'fr': "Chaussée sup.", 'en': "Surface course", 'es': "Rodadura",
        'pt': "Desgaste", 'de': "Deckschicht",
    },
    'rap_projet_defaut': {
        'fr': "Projet CanaPlan", 'en': "CanaPlan project",
        'es': "Proyecto CanaPlan", 'pt': "Projeto CanaPlan",
        'de': "CanaPlan-Projekt",
    },
    'rap_projet_date': {
        'fr': "Projet : {projet}  |  Date : {date}",
        'en': "Project: {projet}  |  Date: {date}",
        'es': "Proyecto: {projet}  |  Fecha: {date}",
        'pt': "Projeto: {projet}  |  Data: {date}",
        'de': "Projekt: {projet}  |  Datum: {date}",
    },
    'rap_projet_type': {
        'fr': "{projet} — {type}", 'en': "{projet} — {type}",
        'es': "{projet} — {type}", 'pt': "{projet} — {type}",
        'de': "{projet} — {type}",
    },
    'rap_absence_fe': {
        'fr': "Absence FE", 'en': "No invert level", 'es': "Sin cota de solera",
        'pt': "Sem cota de soleira", 'de': "Keine Sohlhöhe",
    },
    'rap_absence_fe_court': {
        'fr': "Abs. FE", 'en': "No invert", 'es': "Sin solera",
        'pt': "Sem soleira", 'de': "Keine Sohle",
    },
    'fic_csv': {
        'fr': "Fichier CSV (*.csv)", 'en': "CSV file (*.csv)",
        'es': "Archivo CSV (*.csv)", 'pt': "Ficheiro CSV (*.csv)",
        'de': "CSV-Datei (*.csv)",
    },
    'fic_pdf': {
        'fr': "Fichier PDF (*.pdf)", 'en': "PDF file (*.pdf)",
        'es': "Archivo PDF (*.pdf)", 'pt': "Ficheiro PDF (*.pdf)",
        'de': "PDF-Datei (*.pdf)",
    },
    'fic_xlsx': {
        'fr': "Fichier Excel (*.xlsx)", 'en': "Excel file (*.xlsx)",
        'es': "Archivo Excel (*.xlsx)", 'pt': "Ficheiro Excel (*.xlsx)",
        'de': "Excel-Datei (*.xlsx)",
    },
    'rap_par_lit_pose': {
        'fr': "Ép. lit de pose", 'en': "Bedding thickness",
        'es': "Espesor de la cama", 'pt': "Espessura do leito",
        'de': "Bettungsdicke",
    },
    'rap_par_larg_cond': {
        'fr': "Larg. cond. {reseau}", 'en': "Pipe trench width {reseau}",
        'es': "Ancho tubería {reseau}", 'pt': "Larg. conduta {reseau}",
        'de': "Leitungsbreite {reseau}",
    },
    'rap_par_larg_branch': {
        'fr': "Larg. branch. {reseau}", 'en': "Connection trench width {reseau}",
        'es': "Ancho acometida {reseau}", 'pt': "Larg. ramal {reseau}",
        'de': "Anschlussbreite {reseau}",
    },
    'rap_par_enrobage': {
        'fr': "Enrobage", 'en': "Surround", 'es': "Recubrimiento",
        'pt': "Envolvimento", 'de': "Ummantelung",
    },
    'rap_par_remblai': {
        'fr': "Remblai", 'en': "Backfill", 'es': "Relleno", 'pt': "Aterro",
        'de': "Verfüllung",
    },

    # ─────────────────────────────────────────────────────────────────────
    #  Fenêtre Export StaR-Eau
    # ─────────────────────────────────────────────────────────────────────
    'se_titre': {
        'fr': "Exporter au format StaR-Eau (CNIG / ASTEE V2024)",
        'en': "Export to StaR-Eau format (CNIG / ASTEE V2024)",
        'es': "Exportar al formato StaR-Eau (CNIG / ASTEE V2024)",
        'pt': "Exportar para o formato StaR-Eau (CNIG / ASTEE V2024)",
        'de': "In das StaR-Eau-Format exportieren (CNIG / ASTEE V2024)",
    },
    'se_onglet_fichier': {
        'fr': "Fichier", 'en': "File",
        'es': "Archivo", 'pt': "Ficheiro",
        'de': "Datei",
    },
    'se_onglet_chantier': {
        'fr': "Chantier", 'en': "Worksite",
        'es': "Obra", 'pt': "Obra",
        'de': "Baustelle",
    },
    'se_onglet_reseau': {
        'fr': "Réseau", 'en': "Network",
        'es': "Red", 'pt': "Rede",
        'de': "Netz",
    },
    'se_onglet_ouvrages': {
        'fr': "Ouvrages", 'en': "Structures",
        'es': "Obras", 'pt': "Estruturas",
        'de': "Bauwerke",
    },
    'se_onglet_controle': {
        'fr': "Contrôle", 'en': "Check",
        'es': "Control", 'pt': "Controlo",
        'de': "Prüfung",
    },
    'se_lbl_code': {
        'fr': "Code chantier :", 'en': "Worksite code:",
        'es': "Código de obra:", 'pt': "Código de obra:",
        'de': "Baustellencode:",
    },
    'se_lbl_siren': {
        'fr': "SIREN :", 'en': "SIREN:",
        'es': "SIREN:", 'pt': "SIREN:",
        'de': "SIREN:",
    },
    'se_lbl_type_fichier': {
        'fr': "Type de réseau :", 'en': "Network type:",
        'es': "Tipo de red:", 'pt': "Tipo de rede:",
        'de': "Netzart:",
    },
    'se_lbl_date_export': {
        'fr': "Date d'export :", 'en': "Export date:",
        'es': "Fecha de exportación:", 'pt': "Data de exportação:",
        'de': "Exportdatum:",
    },
    'se_lbl_insee': {
        'fr': "Commune (INSEE) :", 'en': "Municipality (INSEE):",
        'es': "Municipio (INSEE):", 'pt': "Município (INSEE):",
        'de': "Gemeinde (INSEE):",
    },
    'se_lbl_moa': {
        'fr': "Maître d'ouvrage :", 'en': "Owner:",
        'es': "Propietario:", 'pt': "Dono de obra:",
        'de': "Bauherr:",
    },
    'se_lbl_exploitant': {
        'fr': "Exploitant :", 'en': "Operator:",
        'es': "Explotador:", 'pt': "Operador:",
        'de': "Betreiber:",
    },
    'se_lbl_entreprise': {
        'fr': "Entreprise de pose :", 'en': "Installing contractor:",
        'es': "Empresa instaladora:", 'pt': "Empresa instaladora:",
        'de': "Verlegefirma:",
    },
    'se_lbl_localisation': {
        'fr': "Localisation :", 'en': "Location:",
        'es': "Ubicación:", 'pt': "Localização:",
        'de': "Lage:",
    },
    'se_lbl_etat': {
        'fr': "État de service :", 'en': "Service status:",
        'es': "Estado de servicio:", 'pt': "Estado de serviço:",
        'de': "Betriebszustand:",
    },
    'se_lbl_prec_xy': {
        'fr': "Classe de précision XY :", 'en': "XY accuracy class:",
        'es': "Clase de precisión XY:", 'pt': "Classe de precisão XY:",
        'de': "Genauigkeitsklasse XY:",
    },
    'se_lbl_prec_z': {
        'fr': "Classe de précision Z :", 'en': "Z accuracy class:",
        'es': "Clase de precisión Z:", 'pt': "Classe de precisão Z:",
        'de': "Genauigkeitsklasse Z:",
    },
    'se_lbl_date_pose': {
        'fr': "Date de pose :", 'en': "Installation date:",
        'es': "Fecha de instalación:", 'pt': "Data de instalação:",
        'de': "Verlegedatum:",
    },
    'se_lbl_annee_service': {
        'fr': "Année de mise en service :", 'en': "Year brought into service:",
        'es': "Año de puesta en servicio:", 'pt': "Ano de entrada em serviço:",
        'de': "Inbetriebnahmejahr:",
    },
    'se_lbl_origine': {
        'fr': "Origine de la donnée :", 'en': "Data source:",
        'es': "Origen del dato:", 'pt': "Origem do dado:",
        'de': "Datenherkunft:",
    },
    'se_lbl_type_eu': {
        'fr': "Type de réseau — couches EU :", 'en': "Network type — wastewater layers:",
        'es': "Tipo de red — capas EU:", 'pt': "Tipo de rede — camadas EU:",
        'de': "Netzart — Schmutzwasser-Layer:",
    },
    'se_lbl_type_ep': {
        'fr': "Type de réseau — couches EP :", 'en': "Network type — stormwater layers:",
        'es': "Tipo de red — capas EP:", 'pt': "Tipo de rede — camadas EP:",
        'de': "Netzart — Regenwasser-Layer:",
    },
    'se_lbl_mode_circ': {
        'fr': "Mode de circulation :", 'en': "Flow mode:",
        'es': "Modo de circulación:", 'pt': "Modo de circulação:",
        'de': "Fließregime:",
    },
    'se_lbl_type_pose': {
        'fr': "Type de pose :", 'en': "Installation method:",
        'es': "Tipo de instalación:", 'pt': "Tipo de instalação:",
        'de': "Verlegeart:",
    },
    'se_lbl_raison_pose': {
        'fr': "Raison de la pose :", 'en': "Reason for installation:",
        'es': "Motivo de la instalación:", 'pt': "Motivo da instalação:",
        'de': "Verlegegrund:",
    },
    'se_lbl_revetement': {
        'fr': "Revêtement intérieur :", 'en': "Internal lining:",
        'es': "Revestimiento interior:", 'pt': "Revestimento interior:",
        'de': "Innenauskleidung:",
    },
    'se_lbl_fonction_cana': {
        'fr': "Fonction des conduites :", 'en': "Pipe function:",
        'es': "Función de las tuberías:", 'pt': "Função das condutas:",
        'de': "Funktion der Leitungen:",
    },
    'se_lbl_fonction_brt': {
        'fr': "Fonction des branchements :", 'en': "Service connection function:",
        'es': "Función de las acometidas:", 'pt': "Função dos ramais:",
        'de': "Funktion der Hausanschlüsse:",
    },
    'se_lbl_materiau_conduites': {
        'fr': "Matériau des conduites :", 'en': "Pipe material:",
        'es': "Material de las tuberías:", 'pt': "Material das condutas:",
        'de': "Material der Leitungen:",
    },
    'se_lbl_contenu_eu': {
        'fr': "Conduites EU :", 'en': "Wastewater pipes:",
        'es': "Tuberías EU:", 'pt': "Condutas EU:",
        'de': "Schmutzwasserleitungen:",
    },
    'se_lbl_contenu_ep': {
        'fr': "Conduites EP :", 'en': "Stormwater pipes:",
        'es': "Tuberías EP:", 'pt': "Condutas EP:",
        'de': "Regenwasserleitungen:",
    },
    'se_lbl_type_regard': {
        'fr': "Type de regard :", 'en': "Manhole type:",
        'es': "Tipo de pozo:", 'pt': "Tipo de câmara:",
        'de': "Schachttyp:",
    },
    'se_lbl_position': {
        'fr': "Position / canalisation :", 'en': "Position / pipe:",
        'es': "Posición / tubería:", 'pt': "Posição / conduta:",
        'de': "Lage / Leitung:",
    },
    'se_lbl_descente': {
        'fr': "Élément de descente :", 'en': "Drop element:",
        'es': "Elemento de bajada:", 'pt': "Elemento de queda:",
        'de': "Absturzelement:",
    },
    'se_lbl_type_collecte': {
        'fr': "Type de point de collecte :", 'en': "Collection point type:",
        'es': "Tipo de punto de recogida:", 'pt': "Tipo de ponto de recolha:",
        'de': "Art der Übergabestelle:",
    },
    'se_lbl_usager': {
        'fr': "Type d'usager raccordé :", 'en': "Connected user type:",
        'es': "Tipo de usuario conectado:", 'pt': "Tipo de utilizador ligado:",
        'de': "Art des angeschlossenen Nutzers:",
    },
    'se_lbl_type_raccord': {
        'fr': "Type de raccord :", 'en': "Connection type:",
        'es': "Tipo de conexión:", 'pt': "Tipo de ligação:",
        'de': "Anschlussart:",
    },
    'se_ep_vide': {
        'fr': "— laisser vide —", 'en': "— leave empty —",
        'es': "— dejar vacío —", 'pt': "— deixar vazio —",
        'de': "— leer lassen —",
    },
    'se_mat_projet': {
        'fr': "— Identique au projet —", 'en': "— Same as the project —",
        'es': "— Igual que el proyecto —", 'pt': "— Igual ao projeto —",
        'de': "— Wie im Projekt —",
    },
    'se_intro': {
        'fr': "StaR-Eau est un modèle de données, pas un format de fichier. "
              "L'export produit un GeoPackage dont chaque couche reprend le nom "
              "et les colonnes d'une table du géostandard, directement "
              "intégrable dans une base StaR-Eau.",
        'en': "StaR-Eau is a data model, not a file format. The export produces "
              "a GeoPackage whose layers carry the name and columns of a "
              "geostandard table, ready to load into a StaR-Eau database.",
        'es': "StaR-Eau es un modelo de datos, no un formato de archivo. La "
              "exportación produce un GeoPackage cuyas capas reproducen el "
              "nombre y las columnas de una tabla del geoestándar, integrable "
              "directamente en una base StaR-Eau.",
        'pt': "StaR-Eau é um modelo de dados, não um formato de ficheiro. A "
              "exportação produz um GeoPackage cujas camadas reproduzem o nome "
              "e as colunas de uma tabela do geopadrão, diretamente integrável "
              "numa base StaR-Eau.",
        'de': "StaR-Eau ist ein Datenmodell, kein Dateiformat. Der Export "
              "erzeugt ein GeoPackage, dessen Layer Name und Spalten einer "
              "Tabelle des Geostandards übernehmen und direkt in eine "
              "StaR-Eau-Datenbank geladen werden können.",
    },
    'se_code_chantier': {
        'fr': "code chantier, 10 caractères max",
        'en': "site code, 10 characters max",
        'es': "código de obra, 10 caracteres máx.",
        'pt': "código de obra, 10 caracteres máx.",
        'de': "Baustellencode, max. 10 Zeichen",
    },
    'se_siren': {
        'fr': "SIREN du maître d'ouvrage (9 chiffres)",
        'en': "Client's SIREN registration number (9 digits)",
        'es': "SIREN del promotor (9 cifras)",
        'pt': "SIREN do dono de obra (9 dígitos)",
        'de': "SIREN-Nummer des Bauherrn (9 Ziffern)",
    },
    'se_fichier_sortie': {
        'fr': "Fichier de sortie", 'en': "Output file", 'es': "Archivo de salida",
        'pt': "Ficheiro de saída", 'de': "Ausgabedatei",
    },
    'se_dossier_dest': {
        'fr': "dossier de destination", 'en': "destination folder",
        'es': "carpeta de destino", 'pt': "pasta de destino",
        'de': "Zielordner",
    },
    'se_dossier_dest_titre': {
        'fr': "Dossier de destination", 'en': "Destination folder",
        'es': "Carpeta de destino", 'pt': "Pasta de destino",
        'de': "Zielordner",
    },
    'se_nommage': {
        'fr': "Nommage imposé par le géostandard (§ 03.7.5) :\n"
              "Stareau-fr<code>-<SIREN><type><date>.gpkg",
        'en': "Naming imposed by the geostandard (§ 03.7.5):\n"
              "Stareau-fr<code>-<SIREN><type><date>.gpkg",
        'es': "Nomenclatura impuesta por el geoestándar (§ 03.7.5):\n"
              "Stareau-fr<code>-<SIREN><type><date>.gpkg",
        'pt': "Nomenclatura imposta pelo geopadrão (§ 03.7.5):\n"
              "Stareau-fr<code>-<SIREN><type><date>.gpkg",
        'de': "Vom Geostandard vorgegebene Benennung (§ 03.7.5):\n"
              "Stareau-fr<code>-<SIREN><type><date>.gpkg",
    },
    'se_champs_communs': {
        'fr': "Champs communs à tous les objets exportés "
              "(table stareau_principale.champ_commun).",
        'en': "Fields shared by every exported object "
              "(table stareau_principale.champ_commun).",
        'es': "Campos comunes a todos los objetos exportados "
              "(tabla stareau_principale.champ_commun).",
        'pt': "Campos comuns a todos os objetos exportados "
              "(tabela stareau_principale.champ_commun).",
        'de': "Für alle exportierten Objekte gemeinsame Felder "
              "(Tabelle stareau_principale.champ_commun).",
    },
    'se_insee': {
        'fr': "code INSEE sur 5 caractères", 'en': "5-character INSEE code",
        'es': "código INSEE de 5 caracteres", 'pt': "código INSEE de 5 caracteres",
        'de': "5-stelliger INSEE-Code",
    },
    'se_proprietaire': {
        'fr': "propriétaire du patrimoine", 'en': "asset owner",
        'es': "propietario del patrimonio", 'pt': "proprietário do património",
        'de': "Eigentümer des Bestands",
    },
    'se_facultatif': {
        'fr': "facultatif", 'en': "optional", 'es': "opcional",
        'pt': "facultativo", 'de': "optional",
    },
    'se_rue': {
        'fr': "rue principale ou lieu-dit (facultatif)",
        'en': "main street or locality (optional)",
        'es': "calle principal o paraje (opcional)",
        'pt': "rua principal ou lugar (facultativo)",
        'de': "Hauptstraße oder Flurname (optional)",
    },
    'se_commentaire': {
        'fr': "Commentaire :", 'en': "Comment:", 'es': "Comentario:",
        'pt': "Comentário:", 'de': "Kommentar:",
    },
    'se_materiau_aide': {
        'fr': "Le matériau saisi dans le projet est toujours conservé et "
              "converti automatiquement (PVC → pvc, Béton armé → ba…). Ce choix "
              "ne s'applique qu'aux conduites et branchements dont le champ "
              "Matériau est resté vide.",
        'en': "The material entered in the project is always kept and converted "
              "automatically (PVC → pvc, reinforced concrete → ba…). This choice "
              "only applies to pipes and connections whose Material field was "
              "left empty.",
        'es': "El material introducido en el proyecto siempre se conserva y se "
              "convierte automáticamente (PVC → pvc, hormigón armado → ba…). "
              "Esta opción solo se aplica a tuberías y acometidas cuyo campo "
              "Material quedó vacío.",
        'pt': "O material introduzido no projeto é sempre mantido e convertido "
              "automaticamente (PVC → pvc, betão armado → ba…). Esta escolha só "
              "se aplica a condutas e ramais cujo campo Material ficou vazio.",
        'de': "Das im Projekt erfasste Material bleibt stets erhalten und wird "
              "automatisch umgesetzt (PVC → pvc, Stahlbeton → ba…). Diese "
              "Auswahl gilt nur für Leitungen und Anschlüsse, deren Feld "
              "Material leer geblieben ist.",
    },
    'se_sensible': {
        'fr': "Ouvrage sensible au sens DT-DICT",
        'en': "Sensitive structure under the DT-DICT scheme",
        'es': "Obra sensible según DT-DICT",
        'pt': "Estrutura sensível na aceção DT-DICT",
        'de': "Sensibles Bauwerk im Sinne von DT-DICT",
    },
    'se_type_eau': {
        'fr': "Type d'eau transportée (contenu_canalisation)",
        'en': "Type of water conveyed (contenu_canalisation)",
        'es': "Tipo de agua transportada (contenu_canalisation)",
        'pt': "Tipo de água transportada (contenu_canalisation)",
        'de': "Art des transportierten Wassers (contenu_canalisation)",
    },
    'se_type_eau_aide': {
        'fr': "La liste officielle ass_contenu_canalisation ne comporte aucun "
              "code pour les eaux pluviales : elle ne décrit que des eaux usées. "
              "L'information EU/EP est portée par type_reseau (assaep). Laisser "
              "vide est sémantiquement juste ; choisir un code ne se justifie que "
              "si le destinataire du fichier impose un import PostGIS strict, où "
              "la colonne est NOT NULL.",
        'en': "The official ass_contenu_canalisation list has no code for "
              "stormwater: it only describes wastewater. The EU/EP distinction "
              "is carried by type_reseau (assaep). Leaving it empty is "
              "semantically correct; picking a code is only justified when the "
              "recipient requires a strict PostGIS import where the column is "
              "NOT NULL.",
        'es': "La lista oficial ass_contenu_canalisation no incluye ningún "
              "código para aguas pluviales: solo describe aguas residuales. La "
              "información EU/EP la lleva type_reseau (assaep). Dejarlo vacío es "
              "semánticamente correcto; elegir un código solo se justifica si el "
              "destinatario impone una importación PostGIS estricta donde la "
              "columna es NOT NULL.",
        'pt': "A lista oficial ass_contenu_canalisation não tem código para "
              "águas pluviais: descreve apenas águas residuais. A informação "
              "EU/EP é dada por type_reseau (assaep). Deixar vazio é "
              "semanticamente correto; escolher um código só se justifica se o "
              "destinatário impuser uma importação PostGIS estrita onde a coluna "
              "é NOT NULL.",
        'de': "Die offizielle Liste ass_contenu_canalisation enthält keinen Code "
              "für Regenwasser: sie beschreibt nur Schmutzwasser. Die "
              "EU/EP-Information trägt type_reseau (assaep). Leer lassen ist "
              "semantisch korrekt; einen Code zu wählen ist nur gerechtfertigt, "
              "wenn der Empfänger einen strikten PostGIS-Import verlangt, bei dem "
              "die Spalte NOT NULL ist.",
    },
    'se_regards': {
        'fr': "Regards  →  ass_regard", 'en': "Manholes  →  ass_regard",
        'es': "Pozos  →  ass_regard", 'pt': "Caixas  →  ass_regard",
        'de': "Schächte  →  ass_regard",
    },
    'se_tabourets': {
        'fr': "Tabourets  →  ass_point_collecte",
        'en': "Inspection chambers  →  ass_point_collecte",
        'es': "Arquetas  →  ass_point_collecte",
        'pt': "Câmaras  →  ass_point_collecte",
        'de': "Anschlussschächte  →  ass_point_collecte",
    },
    'se_piquages': {
        'fr': "Piquages de branchement  →  ass_raccord",
        'en': "Connection tap-ins  →  ass_raccord",
        'es': "Conexiones de acometida  →  ass_raccord",
        'pt': "Ligações de ramal  →  ass_raccord",
        'de': "Hausanschluss-Anbohrungen  →  ass_raccord",
    },
    'se_piquages_aide': {
        'fr': "Un ass_raccord est créé au point de piquage de chaque "
              "branchement, relié à la conduite piquée par ref_canalisation.",
        'en': "An ass_raccord is created at each connection's tap-in point, "
              "linked to the tapped pipe through ref_canalisation.",
        'es': "Se crea un ass_raccord en el punto de conexión de cada acometida, "
              "vinculado a la tubería mediante ref_canalisation.",
        'pt': "É criado um ass_raccord no ponto de ligação de cada ramal, ligado "
              "à conduta através de ref_canalisation.",
        'de': "Ein ass_raccord wird am Anbohrpunkt jedes Hausanschlusses "
              "erzeugt und über ref_canalisation mit der Leitung verknüpft.",
    },
    'se_anomalie': {
        'fr': "Anomalie", 'en': "Issue", 'es': "Anomalía",
        'pt': "Anomalia", 'de': "Auffälligkeit",
    },
    'se_niveau': {
        'fr': "Niveau", 'en': "Level", 'es': "Nivel", 'pt': "Nível",
        'de': "Stufe",
    },
    'se_objet': {
        'fr': "Objet", 'en': "Object", 'es': "Objeto", 'pt': "Objeto",
        'de': "Objekt",
    },
    'se_controle_aide': {
        'fr': "Double-cliquez sur une ligne pour zoomer sur l'objet dans QGIS. "
              "Cette fenêtre reste ouverte pendant que vous corrigez : le "
              "contrôle se relance tout seul dès que vous y revenez.\nLes objets "
              "bloquants sont ignorés à l'export — leurs colonnes NOT NULL ne "
              "peuvent pas être déduites du dessin.",
        'en': "Double-click a row to zoom to the object in QGIS. This window "
              "stays open while you fix things: the check runs again by itself "
              "as soon as you come back.\nBlocking objects are skipped on "
              "export — their NOT NULL columns cannot be derived from the "
              "drawing.",
        'es': "Haga doble clic en una fila para hacer zoom al objeto en QGIS. "
              "Esta ventana permanece abierta mientras corrige: el control se "
              "relanza solo al volver.\nLos objetos bloqueantes se omiten en la "
              "exportación — sus columnas NOT NULL no pueden deducirse del "
              "dibujo.",
        'pt': "Faça duplo clique numa linha para aproximar o objeto no QGIS. "
              "Esta janela mantém-se aberta enquanto corrige: o controlo repete-"
              "se sozinho quando regressa.\nOs objetos bloqueantes são ignorados "
              "na exportação — as suas colunas NOT NULL não podem ser deduzidas "
              "do desenho.",
        'de': "Doppelklicken Sie eine Zeile, um im QGIS auf das Objekt zu "
              "zoomen. Dieses Fenster bleibt während der Korrektur offen: die "
              "Prüfung läuft bei der Rückkehr von selbst erneut.\nBlockierende "
              "Objekte werden beim Export übersprungen — ihre NOT-NULL-Spalten "
              "lassen sich nicht aus der Zeichnung ableiten.",
    },
    'se_relancer': {
        'fr': "Relancer le contrôle", 'en': "Run the check again",
        'es': "Relanzar el control", 'pt': "Repetir o controlo",
        'de': "Prüfung erneut ausführen",
    },
    'se_controle_echec': {
        'fr': "Le contrôle a échoué : {erreur}", 'en': "The check failed: {erreur}",
        'es': "El control ha fallado: {erreur}", 'pt': "O controlo falhou: {erreur}",
        'de': "Die Prüfung ist fehlgeschlagen: {erreur}",
    },
    'se_aucune_anomalie': {
        'fr': "Aucune anomalie : l'export sera conforme.",
        'en': "No issue: the export will be compliant.",
        'es': "Ninguna anomalía: la exportación será conforme.",
        'pt': "Nenhuma anomalia: a exportação será conforme.",
        'de': "Keine Auffälligkeit: der Export wird konform sein.",
    },
    'se_bilan': {
        'fr': "{bloquants} objet(s) bloquant(s), {avertissements} avertissement(s).",
        'en': "{bloquants} blocking object(s), {avertissements} warning(s).",
        'es': "{bloquants} objeto(s) bloqueante(s), {avertissements} aviso(s).",
        'pt': "{bloquants} objeto(s) bloqueante(s), {avertissements} aviso(s).",
        'de': "{bloquants} blockierende(s) Objekt(e), {avertissements} Warnung(en).",
    },
    'se_champs_obligatoires': {
        'fr': "Champs obligatoires", 'en': "Required fields",
        'es': "Campos obligatorios", 'pt': "Campos obrigatórios",
        'de': "Pflichtfelder",
    },
    'se_non_conformes': {
        'fr': "Objets non conformes", 'en': "Non-compliant objects",
        'es': "Objetos no conformes", 'pt': "Objetos não conformes",
        'de': "Nicht konforme Objekte",
    },
    'se_poursuivre': {
        'fr': "{nb} objet(s) ne peuvent pas être exportés de façon conforme et "
              "seront ignorés.\n\nPoursuivre l'export ?",
        'en': "{nb} object(s) cannot be exported compliantly and will be "
              "skipped.\n\nContinue the export?",
        'es': "{nb} objeto(s) no pueden exportarse de forma conforme y se "
              "omitirán.\n\n¿Continuar la exportación?",
        'pt': "{nb} objeto(s) não podem ser exportados de forma conforme e serão "
              "ignorados.\n\nContinuar a exportação?",
        'de': "{nb} Objekt(e) können nicht konform exportiert werden und werden "
              "übersprungen.\n\nExport fortsetzen?",
    },

    # ─────────────────────────────────────────────────────────────────────
    #  Impression / mise en planches
    # ─────────────────────────────────────────────────────────────────────
    'pt_orienter': {
        'fr': "Planche {n} — orientez avec la souris · 2ᵉ clic pour fixer",
        'en': "Sheet {n} — aim with the mouse · 2nd click to lock",
        'es': "Hoja {n} — oriente con el ratón · 2.º clic para fijar",
        'pt': "Folha {n} — oriente com o rato · 2.º clique para fixar",
        'de': "Blatt {n} — mit der Maus ausrichten · 2. Klick zum Festlegen",
    },
    'pt_ancrage_annule': {
        'fr': "Ancrage annulé", 'en': "Anchor cancelled",
        'es': "Anclaje cancelado", 'pt': "Ancoragem cancelada",
        'de': "Verankerung abgebrochen",
    },
    'pt_feuille_supprimee': {
        'fr': "Planche {n} supprimée — Retour arrière : supprimer la précédente",
        'en': "Sheet {n} removed — Backspace: remove the previous one",
        'es': "Hoja {n} eliminada — Retroceso: eliminar la anterior",
        'pt': "Folha {n} eliminada — Retrocesso: eliminar a anterior",
        'de': "Blatt {n} entfernt — Rücktaste: vorheriges entfernen",
    },
    'pt_feuille_posee': {
        'fr': "Planche {n} posée — 1er clic pour la suivante · clic droit pour "
              "exporter",
        'en': "Sheet {n} placed — click for the next one · right-click to export",
        'es': "Hoja {n} colocada — clic para la siguiente · clic derecho para "
              "exportar",
        'pt': "Folha {n} colocada — clique para a seguinte · clique direito para "
              "exportar",
        'de': "Blatt {n} gesetzt — Klick für das nächste · Rechtsklick zum "
              "Exportieren",
    },
    'pt_aucune_planche': {
        'fr': "Aucune planche posée — placez au moins une planche avant "
              "d'exporter.",
        'en': "No sheet placed — place at least one before exporting.",
        'es': "Ninguna hoja colocada — coloque al menos una antes de exportar.",
        'pt': "Nenhuma folha colocada — coloque pelo menos uma antes de exportar.",
        'de': "Kein Blatt gesetzt — vor dem Export mindestens eines platzieren.",
    },
    'pt_export_dxf': {
        'fr': "Export DXF", 'en': "DXF export", 'es': "Exportación DXF",
        'pt': "Exportação DXF", 'de': "DXF-Export",
    },
    'pt_fichier_existe': {
        'fr': "Le fichier existe déjà :\n\n{chemin}\n\nL'écraser ?",
        'en': "The file already exists:\n\n{chemin}\n\nOverwrite it?",
        'es': "El archivo ya existe:\n\n{chemin}\n\n¿Sobrescribirlo?",
        'pt': "O ficheiro já existe:\n\n{chemin}\n\nSubstituir?",
        'de': "Die Datei existiert bereits:\n\n{chemin}\n\nÜberschreiben?",
    },
    'pt_export_pdf_titre': {
        'fr': "Exporter le plan en PDF", 'en': "Export the plan to PDF",
        'es': "Exportar el plano a PDF", 'pt': "Exportar o plano para PDF",
        'de': "Plan als PDF exportieren",
    },
    'pt_erreur_pdf': {
        'fr': "Erreur lors de la génération du PDF :\n{erreur}",
        'en': "PDF generation failed:\n{erreur}",
        'es': "Error al generar el PDF:\n{erreur}",
        'pt': "Erro ao gerar o PDF:\n{erreur}",
        'de': "Fehler beim Erzeugen des PDF:\n{erreur}",
    },
    'pt_plan_ensemble': {
        'fr': "Plan d'ensemble", 'en': "Overview sheet",
        'es': "Plano de conjunto", 'pt': "Planta de conjunto",
        'de': "Übersichtsplan",
    },
    'pt_plan_ensemble_q': {
        'fr': "Ajouter un plan d'ensemble en première page ?",
        'en': "Add an overview sheet as the first page?",
        'es': "¿Añadir un plano de conjunto como primera página?",
        'pt': "Adicionar uma planta de conjunto como primeira página?",
        'de': "Übersichtsplan als erste Seite hinzufügen?",
    },
    'pt_export_annule': {
        'fr': "Export PDF annulé.", 'en': "PDF export cancelled.",
        'es': "Exportación PDF cancelada.", 'pt': "Exportação PDF cancelada.",
        'de': "PDF-Export abgebrochen.",
    },
    'pt_pdf_exporte': {
        'fr': "PDF exporté — {nb} planche : {chemin}",
        'en': "PDF exported — {nb} sheet(s): {chemin}",
        'es': "PDF exportado — {nb} hoja(s): {chemin}",
        'pt': "PDF exportado — {nb} folha(s): {chemin}",
        'de': "PDF exportiert — {nb} Blatt/Blätter: {chemin}",
    },

    # ─────────────────────────────────────────────────────────────────────
    #  Outils de tracé de profil
    # ─────────────────────────────────────────────────────────────────────
    'po_aide_profil': {
        'fr': "1er clic : regard départ (vert)  ·  2e clic : regard arrivée → "
              "tracé du profil  ·  Échap : annuler",
        'en': "1st click: start manhole (green)  ·  2nd click: end manhole → "
              "draw the profile  ·  Esc: cancel",
        'es': "1.º clic: pozo inicial (verde)  ·  2.º clic: pozo final → trazar "
              "el perfil  ·  Esc: cancelar",
        'pt': "1.º clique: caixa inicial (verde)  ·  2.º clique: caixa final → "
              "traçar o perfil  ·  Esc: cancelar",
        'de': "1. Klick: Startschacht (grün)  ·  2. Klick: Endschacht → Profil "
              "zeichnen  ·  Esc: abbrechen",
    },
    'po_aucun_chemin': {
        'fr': "Aucun chemin trouvé entre les deux regards sélectionnés.\n"
              "Vérifiez que le réseau est correctement connecté.",
        'en': "No path found between the two selected manholes.\nCheck that the "
              "network is properly connected.",
        'es': "No se ha encontrado ningún camino entre los dos pozos "
              "seleccionados.\nCompruebe que la red esté bien conectada.",
        'pt': "Nenhum caminho encontrado entre as duas caixas selecionadas.\n"
              "Verifique se a rede está bem ligada.",
        'de': "Kein Weg zwischen den beiden gewählten Schächten gefunden.\n"
              "Prüfen Sie, ob das Netz korrekt verbunden ist.",
    },
    'po_aide_axe': {
        'fr': "Tracez l'axe de référence : clic gauche = ajouter un point  ·  "
              "Double-clic ou clic droit = terminer  ·  Échap = annuler",
        'en': "Draw the reference axis: left click = add a point  ·  "
              "double-click or right click = finish  ·  Esc = cancel",
        'es': "Trace el eje de referencia: clic izquierdo = añadir un punto  ·  "
              "doble clic o clic derecho = terminar  ·  Esc = cancelar",
        'pt': "Trace o eixo de referência: clique esquerdo = adicionar um ponto  "
              "·  duplo clique ou clique direito = terminar  ·  Esc = cancelar",
        'de': "Referenzachse zeichnen: Linksklick = Punkt hinzufügen  ·  "
              "Doppelklick oder Rechtsklick = beenden  ·  Esc = abbrechen",
    },
    'po_profil_groupe': {
        'fr': "Profil groupé", 'en': "Combined profile", 'es': "Perfil agrupado",
        'pt': "Perfil agrupado", 'de': "Kombiniertes Profil",
    },
    'po_axe_court': {
        'fr': "L'axe tracé est trop court.", 'en': "The drawn axis is too short.",
        'es': "El eje trazado es demasiado corto.",
        'pt': "O eixo traçado é demasiado curto.",
        'de': "Die gezeichnete Achse ist zu kurz.",
    },
    'po_aucune_conduite': {
        'fr': "Aucune conduite EU ou EP trouvée dans le buffer de {rayon} m\n"
              "autour de l'axe tracé.",
        'en': "No EU or EP pipe found within the {rayon} m buffer\naround the "
              "drawn axis.",
        'es': "No se ha encontrado ninguna tubería EU o EP en el búfer de "
              "{rayon} m\nalrededor del eje trazado.",
        'pt': "Nenhuma conduta EU ou EP encontrada no buffer de {rayon} m\nem "
              "torno do eixo traçado.",
        'de': "Keine EU- oder EP-Leitung im {rayon} m-Puffer\num die gezeichnete "
              "Achse gefunden.",
    },

    # ─────────────────────────────────────────────────────────────────────
    #  Enregistrement / chargement de projet
    # ─────────────────────────────────────────────────────────────────────
    'pb_dossier_sauvegarde': {
        'fr': "Choisir le dossier de sauvegarde du projet",
        'en': "Choose the folder to save the project in",
        'es': "Elija la carpeta donde guardar el proyecto",
        'pt': "Escolha a pasta onde guardar o projeto",
        'de': "Ordner zum Speichern des Projekts wählen",
    },
    'pb_nom': {
        'fr': "Nom :", 'en': "Name:", 'es': "Nombre:", 'pt': "Nome:",
        'de': "Name:",
    },
    'pb_nom_projet': {
        'fr': "Nom du projet", 'en': "Project name", 'es': "Nombre del proyecto",
        'pt': "Nome do projeto", 'de': "Projektname",
    },
    'pb_rotation_echec': {
        'fr': "Impossible de faire pivoter les sauvegardes :\n{erreur}\n\nFermez "
              "tout logiciel qui pourrait avoir ouvert ces fichiers, puis "
              "réessayez.",
        'en': "The backup rotation failed:\n{erreur}\n\nClose any program that "
              "might have these files open, then try again.",
        'es': "No se han podido rotar las copias de seguridad:\n{erreur}\n\n"
              "Cierre cualquier programa que pueda tener abiertos estos archivos "
              "y vuelva a intentarlo.",
        'pt': "Não foi possível rodar as cópias de segurança:\n{erreur}\n\nFeche "
              "qualquer programa que possa ter estes ficheiros abertos e tente "
              "novamente.",
        'de': "Die Sicherungsrotation ist fehlgeschlagen:\n{erreur}\n\nSchließen "
              "Sie alle Programme, die diese Dateien geöffnet haben könnten, und "
              "versuchen Sie es erneut.",
    },
    'pb_archive_echec': {
        'fr': "Impossible de créer l'archive .bet :\n{erreur}",
        'en': "The .bet archive could not be created:\n{erreur}",
        'es': "No se ha podido crear el archivo .bet:\n{erreur}",
        'pt': "Não foi possível criar o arquivo .bet:\n{erreur}",
        'de': "Das .bet-Archiv konnte nicht erstellt werden:\n{erreur}",
    },
    'pb_extraction_gpkg': {
        'fr': "Impossible d'extraire le GPKG depuis l'archive :\n{erreur}",
        'en': "The GPKG could not be extracted from the archive:\n{erreur}",
        'es': "No se ha podido extraer el GPKG del archivo:\n{erreur}",
        'pt': "Não foi possível extrair o GPKG do arquivo:\n{erreur}",
        'de': "Das GPKG konnte nicht aus dem Archiv entpackt werden:\n{erreur}",
    },
    'pb_enregistre': {
        'fr': "Projet enregistré :\n{chemin}", 'en': "Project saved:\n{chemin}",
        'es': "Proyecto guardado:\n{chemin}", 'pt': "Projeto guardado:\n{chemin}",
        'de': "Projekt gespeichert:\n{chemin}",
    },
    'pb_avertissements': {
        'fr': "Projet enregistré avec des avertissements :\n{details}\n\n"
              "Fichier : {chemin}",
        'en': "Project saved with warnings:\n{details}\n\nFile: {chemin}",
        'es': "Proyecto guardado con avisos:\n{details}\n\nArchivo: {chemin}",
        'pt': "Projeto guardado com avisos:\n{details}\n\nFicheiro: {chemin}",
        'de': "Projekt mit Warnungen gespeichert:\n{details}\n\nDatei: {chemin}",
    },
    'pb_charger_titre': {
        'fr': "Charger le projet", 'en': "Load the project",
        'es': "Cargar el proyecto", 'pt': "Carregar o projeto",
        'de': "Projekt laden",
    },
    'pb_couches_chargees': {
        'fr': "{nb} couche(s) chargée(s) depuis :\n{chemin}",
        'en': "{nb} layer(s) loaded from:\n{chemin}",
        'es': "{nb} capa(s) cargada(s) desde:\n{chemin}",
        'pt': "{nb} camada(s) carregada(s) de:\n{chemin}",
        'de': "{nb} Layer geladen aus:\n{chemin}",
    },
    'pb_couches_avertissements': {
        'fr': "{nb} couche(s) chargée(s).\nAvertissements :\n{details}",
        'en': "{nb} layer(s) loaded.\nWarnings:\n{details}",
        'es': "{nb} capa(s) cargada(s).\nAvisos:\n{details}",
        'pt': "{nb} camada(s) carregada(s).\nAvisos:\n{details}",
        'de': "{nb} Layer geladen.\nWarnungen:\n{details}",
    },
    'pb_lecture_archive': {
        'fr': "Impossible de lire l'archive .bet :\n{erreur}",
        'en': "The .bet archive could not be read:\n{erreur}",
        'es': "No se ha podido leer el archivo .bet:\n{erreur}",
        'pt': "Não foi possível ler o arquivo .bet:\n{erreur}",
        'de': "Das .bet-Archiv konnte nicht gelesen werden:\n{erreur}",
    },
    'pb_extraction_geopackage': {
        'fr': "Impossible d'extraire le GeoPackage depuis l'archive :\n{erreur}",
        'en': "The GeoPackage could not be extracted from the archive:\n{erreur}",
        'es': "No se ha podido extraer el GeoPackage del archivo:\n{erreur}",
        'pt': "Não foi possível extrair o GeoPackage do arquivo:\n{erreur}",
        'de': "Das GeoPackage konnte nicht aus dem Archiv entpackt werden:\n"
              "{erreur}",
    },
    'pb_lecture_bet': {
        'fr': "Impossible de lire le fichier .bet :\n{erreur}",
        'en': "The .bet file could not be read:\n{erreur}",
        'es': "No se ha podido leer el archivo .bet:\n{erreur}",
        'pt': "Não foi possível ler o ficheiro .bet:\n{erreur}",
        'de': "Die .bet-Datei konnte nicht gelesen werden:\n{erreur}",
    },
    'pb_gpkg_introuvable': {
        'fr': "GeoPackage introuvable :\n{chemin}",
        'en': "GeoPackage not found:\n{chemin}",
        'es': "GeoPackage no encontrado:\n{chemin}",
        'pt': "GeoPackage não encontrado:\n{chemin}",
        'de': "GeoPackage nicht gefunden:\n{chemin}",
    },

    # ─────────────────────────────────────────────────────────────────────
    #  Dessinateur de coupe de tranchées
    # ─────────────────────────────────────────────────────────────────────
    'dt_tranches': {
        'fr': "Tranches", 'en': "Trenches", 'es': "Zanjas", 'pt': "Valas",
        'de': "Gräben",
    },
    'dt_ajouter': {
        'fr': "+ Ajouter", 'en': "+ Add", 'es': "+ Añadir",
        'pt': "+ Adicionar", 'de': "+ Hinzufügen",
    },
    'dt_supprimer': {
        'fr': "Supprimer", 'en': "Remove", 'es': "Eliminar",
        'pt': "Eliminar", 'de': "Entfernen",
    },
    'dt_matplotlib': {
        'fr': "matplotlib non disponible — installer matplotlib pour QGIS",
        'en': "matplotlib unavailable — install matplotlib for QGIS",
        'es': "matplotlib no disponible — instale matplotlib para QGIS",
        'pt': "matplotlib indisponível — instale o matplotlib para o QGIS",
        'de': "matplotlib nicht verfügbar — matplotlib für QGIS installieren",
    },
    'dt_canalisation': {
        'fr': "Canalisation", 'en': "Pipe", 'es': "Tubería", 'pt': "Conduta",
        'de': "Leitung",
    },
    'dt_tranchee': {
        'fr': "Tranchée", 'en': "Trench", 'es': "Zanja", 'pt': "Vala",
        'de': "Graben",
    },
    'dt_remblai': {
        'fr': "Remblai", 'en': "Backfill", 'es': "Relleno", 'pt': "Aterro",
        'de': "Verfüllung",
    },
    'dt_chaussee': {
        'fr': "Chaussée", 'en': "Roadway", 'es': "Calzada", 'pt': "Faixa",
        'de': "Fahrbahn",
    },
    'dt_chaussee_inf': {
        'fr': "Chaussée inférieure (GB/GC)", 'en': "Sub-base (road base)",
        'es': "Base de calzada (GB/GC)", 'pt': "Base da faixa (GB/GC)",
        'de': "Tragschicht (GB/GC)",
    },
    'dt_chaussee_sup': {
        'fr': "Chaussée supérieure (enrobé)", 'en': "Surface course (asphalt)",
        'es': "Capa de rodadura (aglomerado)", 'pt': "Camada de desgaste (betuminoso)",
        'de': "Deckschicht (Asphalt)",
    },
    'dt_exporter_en': {
        'fr': "Exporter en {format}", 'en': "Export as {format}",
        'es': "Exportar en {format}", 'pt': "Exportar em {format}",
        'de': "Als {format} exportieren",
    },
    'dt_erreur_export': {
        'fr': "Erreur export", 'en': "Export error", 'es': "Error de exportación",
        'pt': "Erro de exportação", 'de': "Exportfehler",
    },
    # Libellés du formulaire de la coupe composée (deux-points inclus :
    # l'espace insécable avant « : » n'existe qu'en français)
    'dt_lbl_reseau': {
        'fr': "Réseau :", 'en': "Network:", 'es': "Red:", 'pt': "Rede:",
        'de': "Netz:",
    },
    'dt_lbl_dn': {
        'fr': "DN :", 'en': "DN:", 'es': "DN:", 'pt': "DN:", 'de': "DN:",
    },
    'dt_lbl_materiau': {
        'fr': "Matériau :", 'en': "Material:", 'es': "Material:",
        'pt': "Material:", 'de': "Material:",
    },
    'dt_lbl_prof_fe': {
        'fr': "Prof. fil d'eau :", 'en': "Invert depth:",
        'es': "Prof. de la solera:", 'pt': "Prof. da soleira:",
        'de': "Sohltiefe:",
    },
    'dt_lbl_espace_gauche': {
        'fr': "Espace terrain gauche :", 'en': "Ground gap on left:",
        'es': "Espacio de terreno izquierdo:", 'pt': "Espaço de terreno à esquerda:",
        'de': "Bodenabstand links:",
    },
    'dt_lbl_ecart_gauche': {
        'fr': "Écart gauche tuyau :", 'en': "Left clearance to pipe:",
        'es': "Holgura izquierda del tubo:", 'pt': "Folga esquerda do tubo:",
        'de': "Abstand links zum Rohr:",
    },
    'dt_lbl_ecart_droit': {
        'fr': "Écart droit tuyau :", 'en': "Right clearance to pipe:",
        'es': "Holgura derecha del tubo:", 'pt': "Folga direita do tubo:",
        'de': "Abstand rechts zum Rohr:",
    },
    'dt_lbl_lit_pose': {
        'fr': "Lit de pose :", 'en': "Bedding:", 'es': "Cama:",
        'pt': "Leito:", 'de': "Bettung:",
    },
    'dt_lbl_enrobage': {
        'fr': "Enrobage :", 'en': "Surround:", 'es': "Recubrimiento:",
        'pt': "Envolvimento:", 'de': "Ummantelung:",
    },
    'dt_lbl_remblai': {
        'fr': "Remblai :", 'en': "Backfill:", 'es': "Relleno:",
        'pt': "Aterro:", 'de': "Verfüllung:",
    },
    'dt_lbl_ep_mat': {
        'fr': "Ép. + mat. :", 'en': "Thickness + material:",
        'es': "Esp. + material:", 'pt': "Esp. + material:",
        'de': "Dicke + Material:",
    },
    'dt_cote_enrobage': {
        'fr': "enr. {valeur} m", 'en': "surr. {valeur} m",
        'es': "recub. {valeur} m", 'pt': "envol. {valeur} m",
        'de': "Umm. {valeur} m",
    },

    # ─────────────────────────────────────────────────────────────────────
    #  Fenêtre Annotation
    # ─────────────────────────────────────────────────────────────────────
    'an_titre': {
        'fr': "Annotation", 'en': "Annotation", 'es': "Anotación",
        'pt': "Anotação", 'de': "Anmerkung",
    },
    'an_gras': {
        'fr': "Gras", 'en': "Bold", 'es': "Negrita", 'pt': "Negrito",
        'de': "Fett",
    },
    'an_italique': {
        'fr': "Italique", 'en': "Italic", 'es': "Cursiva", 'pt': "Itálico",
        'de': "Kursiv",
    },
    'an_souligne': {
        'fr': "Souligné", 'en': "Underline", 'es': "Subrayado",
        'pt': "Sublinhado", 'de': "Unterstrichen",
    },
    'an_aligner_gauche': {
        'fr': "Aligner à gauche", 'en': "Align left", 'es': "Alinear a la izquierda",
        'pt': "Alinhar à esquerda", 'de': "Linksbündig",
    },
    'an_centrer': {
        'fr': "Centrer", 'en': "Center", 'es': "Centrar", 'pt': "Centrar",
        'de': "Zentriert",
    },
    'an_aligner_droite': {
        'fr': "Aligner à droite", 'en': "Align right", 'es': "Alinear a la derecha",
        'pt': "Alinhar à direita", 'de': "Rechtsbündig",
    },
    'an_dlg_couleur_texte': {
        'fr': "Couleur du texte", 'en': "Text colour", 'es': "Color del texto",
        'pt': "Cor do texto", 'de': "Textfarbe",
    },
    'an_couleur_fond': {
        'fr': "Couleur du fond", 'en': "Fill colour", 'es': "Color de fondo",
        'pt': "Cor de fundo", 'de': "Füllfarbe",
    },
    'an_couleur_bordure': {
        'fr': "Couleur de la bordure", 'en': "Border colour",
        'es': "Color del borde", 'pt': "Cor do contorno", 'de': "Rahmenfarbe",
    },
    'ct_format_paysage': {
        'fr': "{format} paysage", 'en': "{format} landscape",
        'es': "{format} horizontal", 'pt': "{format} horizontal",
        'de': "{format} Querformat",
    },
    'ct_format_portrait': {
        'fr': "{format} portrait", 'en': "{format} portrait",
        'es': "{format} vertical", 'pt': "{format} vertical",
        'de': "{format} Hochformat",
    },
    'fic_pdf_court': {
        'fr': "PDF (*.pdf)", 'en': "PDF (*.pdf)", 'es': "PDF (*.pdf)",
        'pt': "PDF (*.pdf)", 'de': "PDF (*.pdf)",
    },
    'fic_png_court': {
        'fr': "PNG (*.png)", 'en': "PNG (*.png)", 'es': "PNG (*.png)",
        'pt': "PNG (*.png)", 'de': "PNG (*.png)",
    },
    'ts_fe_extremites_manquants': {
        'fr': "Le FE du regard de départ et/ou d'arrivée est manquant (ou la "
              "longueur totale est nulle) — impossible de calculer la pente.",
        'en': "The invert level of the first and/or last structure is missing "
              "(or the total length is zero) — the slope cannot be computed.",
        'es': "Falta la cota de solera del pozo inicial y/o final (o la longitud "
              "total es nula) — no se puede calcular la pendiente.",
        'pt': "Falta a cota de soleira da câmara inicial e/ou final (ou o "
              "comprimento total é nulo) — não é possível calcular o declive.",
        'de': "Die Sohlhöhe des ersten und/oder letzten Bauwerks fehlt (oder die "
              "Gesamtlänge ist null) — das Gefälle kann nicht berechnet werden.",
    },
    'an_mise_en_forme': {
        'fr': "Mise en forme", 'en': "Formatting", 'es': "Formato",
        'pt': "Formatação", 'de': "Formatierung",
    },
    'an_texte': {
        'fr': "Texte :", 'en': "Text:", 'es': "Texto:", 'pt': "Texto:",
        'de': "Text:",
    },
    'an_texte_ph': {
        'fr': "Tapez votre texte…", 'en': "Type your text…",
        'es': "Escriba su texto…", 'pt': "Escreva o seu texto…",
        'de': "Text eingeben…",
    },
    'an_police_taille': {
        'fr': "Police et taille", 'en': "Font and size", 'es': "Fuente y tamaño",
        'pt': "Tipo de letra e tamanho", 'de': "Schrift und Größe",
    },
    'an_police': {
        'fr': "Police :", 'en': "Font:", 'es': "Fuente:",
        'pt': "Tipo de letra:", 'de': "Schrift:",
    },
    'an_taille_m': {
        'fr': "Taille (m) :", 'en': "Size (m):", 'es': "Tamaño (m):",
        'pt': "Tamanho (m):", 'de': "Größe (m):",
    },
    'an_echelle': {
        'fr': "Échelle :", 'en': "Scale:", 'es': "Escala:", 'pt': "Escala:",
        'de': "Maßstab:",
    },
    'an_taille_libre': {
        'fr': "Taille libre", 'en': "Free size", 'es': "Tamaño libre",
        'pt': "Tamanho livre", 'de': "Freie Größe",
    },
    'an_aide_echelle': {
        'fr': "<i>Une échelle calcule la taille (m) avec la même formule que "
              "« Taille des étiquettes ».</i>",
        'en': "<i>A scale computes the size (m) with the same formula as "
              "“Label size”.</i>",
        'es': "<i>Una escala calcula el tamaño (m) con la misma fórmula que "
              "«Tamaño de las etiquetas».</i>",
        'pt': "<i>Uma escala calcula o tamanho (m) com a mesma fórmula que "
              "«Tamanho dos rótulos».</i>",
        'de': "<i>Ein Maßstab berechnet die Größe (m) mit derselben Formel wie "
              "„Beschriftungsgröße“.</i>",
    },
    'an_couleur_transparence': {
        'fr': "Couleur et transparence", 'en': "Colour and transparency",
        'es': "Color y transparencia", 'pt': "Cor e transparência",
        'de': "Farbe und Transparenz",
    },
    'an_couleur_texte': {
        'fr': "Couleur texte :", 'en': "Text colour:", 'es': "Color del texto:",
        'pt': "Cor do texto:", 'de': "Textfarbe:",
    },
    'an_transparence': {
        'fr': "Transparence (%) :", 'en': "Transparency (%):",
        'es': "Transparencia (%):", 'pt': "Transparência (%):",
        'de': "Transparenz (%):",
    },
    'an_cadre': {
        'fr': "Cadre", 'en': "Frame", 'es': "Marco", 'pt': "Moldura",
        'de': "Rahmen",
    },
    'an_afficher_cadre': {
        'fr': "Afficher un cadre", 'en': "Show a frame", 'es': "Mostrar un marco",
        'pt': "Mostrar uma moldura", 'de': "Rahmen anzeigen",
    },
    'an_fond_rempli': {
        'fr': "Fond rempli", 'en': "Filled background", 'es': "Fondo relleno",
        'pt': "Fundo preenchido", 'de': "Gefüllter Hintergrund",
    },
    'an_fond': {
        'fr': "Fond :", 'en': "Background:", 'es': "Fondo:", 'pt': "Fundo:",
        'de': "Hintergrund:",
    },
    'an_bordure': {
        'fr': "Bordure :", 'en': "Border:", 'es': "Borde:", 'pt': "Bordo:",
        'de': "Rand:",
    },

    # ─────────────────────────────────────────────────────────────────────
    #  Outils de la carte : bandeaux d'aide et messages
    # ─────────────────────────────────────────────────────────────────────
    'ot_aide_cubature_regards': {
        'fr': "1er clic : regard départ (vert)  ·  2e clic : regard arrivée → "
              "calcul  ·  Échap : annuler",
        'en': "1st click: start manhole (green)  ·  2nd click: end manhole → "
              "compute  ·  Esc: cancel",
        'es': "1.º clic: pozo inicial (verde)  ·  2.º clic: pozo final → "
              "calcular  ·  Esc: cancelar",
        'pt': "1.º clique: caixa inicial (verde)  ·  2.º clique: caixa final → "
              "calcular  ·  Esc: cancelar",
        'de': "1. Klick: Startschacht (grün)  ·  2. Klick: Endschacht → "
              "berechnen  ·  Esc: abbrechen",
    },
    'ot_reseaux_differents': {
        'fr': "Les deux regards doivent appartenir au même réseau.\n"
              "Départ : {debut}, arrivée : {fin}.",
        'en': "Both manholes must belong to the same network.\n"
              "Start: {debut}, end: {fin}.",
        'es': "Ambos pozos deben pertenecer a la misma red.\n"
              "Inicio: {debut}, fin: {fin}.",
        'pt': "As duas caixas devem pertencer à mesma rede.\n"
              "Início: {debut}, fim: {fin}.",
        'de': "Beide Schächte müssen zum selben Netz gehören.\n"
              "Start: {debut}, Ende: {fin}.",
    },
    'ot_aucune_conduite_buffer': {
        'fr': "Aucune conduite trouvée dans le buffer de {rayon} m\nautour de "
              "l'axe tracé.",
        'en': "No pipe found within the {rayon} m buffer\naround the drawn axis.",
        'es': "No se ha encontrado ninguna tubería en el búfer de {rayon} m\n"
              "alrededor del eje trazado.",
        'pt': "Nenhuma conduta encontrada no buffer de {rayon} m\nem torno do "
              "eixo traçado.",
        'de': "Keine Leitung im {rayon} m-Puffer\num die gezeichnete Achse "
              "gefunden.",
    },
    'ot_rien_a_afficher': {
        'fr': "Aucun élément à afficher sur le chemin sélectionné.",
        'en': "Nothing to show along the selected path.",
        'es': "Ningún elemento que mostrar en el camino seleccionado.",
        'pt': "Nenhum elemento a mostrar no caminho selecionado.",
        'de': "Nichts entlang des gewählten Wegs anzuzeigen.",
    },
    'ot_aide_branchement': {
        'fr': "Cliquer sur une conduite pour piquer, puis tracer jusqu'à un "
              "ouvrage  ·  Clic droit : terminer  ·  Échap : annuler",
        'en': "Click a pipe to tap into it, then draw to a structure  ·  "
              "Right-click: finish  ·  Esc: cancel",
        'es': "Haga clic en una tubería para conectar, luego trace hasta una "
              "obra  ·  Clic derecho: terminar  ·  Esc: cancelar",
        'pt': "Clique numa conduta para ligar, depois trace até uma estrutura  "
              "·  Clique direito: terminar  ·  Esc: cancelar",
        'de': "Auf eine Leitung klicken zum Anbohren, dann bis zu einem Bauwerk "
              "zeichnen  ·  Rechtsklick: beenden  ·  Esc: abbrechen",
    },
    'ot_premier_point': {
        'fr': "Le premier point doit être sur une conduite ou un regard {reseau}.",
        'en': "The first point must lie on a {reseau} pipe or manhole.",
        'es': "El primer punto debe estar sobre una tubería o un pozo {reseau}.",
        'pt': "O primeiro ponto deve estar sobre uma conduta ou caixa {reseau}.",
        'de': "Der erste Punkt muss auf einer {reseau}-Leitung oder einem "
              "{reseau}-Schacht liegen.",
    },
    'ot_creer_regard': {
        'fr': "Créer un regard", 'en': "Create a manhole", 'es': "Crear un pozo",
        'pt': "Criar uma caixa", 'de': "Schacht erstellen",
    },
    'ot_valeurs_invalides': {
        'fr': "Valeurs numériques invalides.", 'en': "Invalid numeric values.",
        'es': "Valores numéricos no válidos.", 'pt': "Valores numéricos inválidos.",
        'de': "Ungültige Zahlenwerte.",
    },
    'ot_validation': {
        'fr': "Validation", 'en': "Validation", 'es': "Validación",
        'pt': "Validação", 'de': "Prüfung",
    },
    'ot_branch_debut': {
        'fr': "Le premier point du branchement n'est pas situé sur la conduite "
              "principale.",
        'en': "The connection's first point does not lie on the main pipe.",
        'es': "El primer punto de la acometida no está sobre la tubería "
              "principal.",
        'pt': "O primeiro ponto do ramal não está sobre a conduta principal.",
        'de': "Der erste Punkt des Hausanschlusses liegt nicht auf der "
              "Hauptleitung.",
    },
    'ot_branch_fin': {
        'fr': "Le dernier point du branchement doit coïncider avec un regard ou "
              "un tabouret existant.",
        'en': "The connection's last point must coincide with an existing "
              "manhole or inspection chamber.",
        'es': "El último punto de la acometida debe coincidir con un pozo o una "
              "arqueta existente.",
        'pt': "O último ponto do ramal deve coincidir com uma caixa ou câmara "
              "existente.",
        'de': "Der letzte Punkt des Hausanschlusses muss mit einem vorhandenen "
              "Schacht oder Anschlussschacht zusammenfallen.",
    },
    'ot_annotation_collee': {
        'fr': "Annotation collée.", 'en': "Annotation pasted.",
        'es': "Anotación pegada.", 'pt': "Anotação colada.",
        'de': "Anmerkung eingefügt.",
    },
    'ot_impossible_appliquer': {
        'fr': "Impossible d'appliquer : {erreur}", 'en': "Could not apply: {erreur}",
        'es': "No se ha podido aplicar: {erreur}",
        'pt': "Não foi possível aplicar: {erreur}",
        'de': "Konnte nicht angewendet werden: {erreur}",
    },
    'ot_annotation_copiee': {
        'fr': "Annotation copiée — Ctrl+V puis cliquez pour coller.",
        'en': "Annotation copied — Ctrl+V then click to paste.",
        'es': "Anotación copiada — Ctrl+V y haga clic para pegar.",
        'pt': "Anotação copiada — Ctrl+V e clique para colar.",
        'de': "Anmerkung kopiert — Strg+V, dann klicken zum Einfügen.",
    },
    'ot_curseur_annotation': {
        'fr': "Place le curseur sur une annotation avant Ctrl+C.",
        'en': "Hover over an annotation before pressing Ctrl+C.",
        'es': "Sitúe el cursor sobre una anotación antes de Ctrl+C.",
        'pt': "Coloque o cursor sobre uma anotação antes de Ctrl+C.",
        'de': "Vor Strg+C den Zeiger über eine Anmerkung setzen.",
    },
    'ot_presse_papier_vide': {
        'fr': "Presse-papier vide.", 'en': "Clipboard is empty.",
        'es': "Portapapeles vacío.", 'pt': "Área de transferência vazia.",
        'de': "Zwischenablage ist leer.",
    },
    'ot_cliquez_coller': {
        'fr': "Cliquez sur la carte pour coller l'annotation.",
        'en': "Click on the map to paste the annotation.",
        'es': "Haga clic en el mapa para pegar la anotación.",
        'pt': "Clique no mapa para colar a anotação.",
        'de': "Auf die Karte klicken, um die Anmerkung einzufügen.",
    },
    'ot_coller_annule': {
        'fr': "Coller annulé.", 'en': "Paste cancelled.",
        'es': "Pegado cancelado.", 'pt': "Colagem cancelada.",
        'de': "Einfügen abgebrochen.",
    },
    'ot_aide_effacer': {
        'fr': "Clic : supprimer l'élément survolé  ·  Glisser : lasso "
              "multi-sélection + clic droit pour confirmer  ·  Clic droit sur "
              "étiquette : effacer l'étiquette",
        'en': "Click: delete the hovered item  ·  Drag: lasso multi-select + "
              "right-click to confirm  ·  Right-click a label: delete the label",
        'es': "Clic: eliminar el elemento bajo el cursor  ·  Arrastrar: lazo de "
              "selección múltiple + clic derecho para confirmar  ·  Clic derecho "
              "en una etiqueta: borrarla",
        'pt': "Clique: eliminar o elemento sob o cursor  ·  Arrastar: laço de "
              "seleção múltipla + clique direito para confirmar  ·  Clique "
              "direito num rótulo: apagá-lo",
        'de': "Klick: überfahrenes Element löschen  ·  Ziehen: Lasso-Mehrfachwahl "
              "+ Rechtsklick zum Bestätigen  ·  Rechtsklick auf Beschriftung: "
              "Beschriftung löschen",
    },
    'ot_effacer_etiquette': {
        'fr': "Effacer l'étiquette", 'en': "Delete the label",
        'es': "Borrar la etiqueta", 'pt': "Apagar o rótulo",
        'de': "Beschriftung löschen",
    },
    'ot_supprimer_etiquette_q': {
        'fr': "Supprimer l'étiquette de « {nom} » ?",
        'en': "Delete the label of “{nom}”?",
        'es': "¿Eliminar la etiqueta de «{nom}»?",
        'pt': "Eliminar o rótulo de «{nom}»?",
        'de': "Beschriftung von „{nom}“ löschen?",
    },
    'ot_suppr_simple': {
        'fr': "Supprimer ce {type} ?", 'en': "Delete this {type}?",
        'es': "¿Eliminar este {type}?", 'pt': "Eliminar este {type}?",
        'de': "Dieses Element löschen: {type}?",
    },
    'ot_suppr_cascade': {
        'fr': "Supprimer ce {type} et {nb} élément(s) associé(s) (cascade) ?",
        'en': "Delete this {type} and {nb} linked item(s) (cascade)?",
        'es': "¿Eliminar este {type} y {nb} elemento(s) asociado(s) (en cascada)?",
        'pt': "Eliminar este {type} e {nb} elemento(s) associado(s) (em cascata)?",
        'de': "Dieses Element ({type}) und {nb} verknüpfte(s) Element(e) löschen "
              "(Kaskade)?",
    },
    'ct_sans_fe': {
        'fr': "Conduite id={id} ({reseau}) : FE radier manquant — ignorée.",
        'en': "Pipe id={id} ({reseau}): invert level missing — skipped.",
        'es': "Tubería id={id} ({reseau}): falta la cota de solera — omitida.",
        'pt': "Conduta id={id} ({reseau}): falta a cota de soleira — ignorada.",
        'de': "Leitung id={id} ({reseau}): Sohlhöhe fehlt — übersprungen.",
    },
    'ct_sans_tn': {
        'fr': "Conduite id={id} ({reseau}) : TN manquant — ignorée.",
        'en': "Pipe id={id} ({reseau}): ground level missing — skipped.",
        'es': "Tubería id={id} ({reseau}): falta la cota del terreno — omitida.",
        'pt': "Conduta id={id} ({reseau}): falta a cota do terreno — ignorada.",
        'de': "Leitung id={id} ({reseau}): Geländehöhe fehlt — übersprungen.",
    },
    'dxf_aucune_couche': {
        'fr': "Aucune couche vectorielle visible dans la légende.",
        'en': "No vector layer visible in the legend.",
        'es': "Ninguna capa vectorial visible en la leyenda.",
        'pt': "Nenhuma camada vetorial visível na legenda.",
        'de': "Kein Vektorlayer in der Legende sichtbar.",
    },
    'dxf_ouverture_impossible': {
        'fr': "Impossible d'ouvrir {chemin} en écriture",
        'en': "Cannot open {chemin} for writing",
        'es': "No se puede abrir {chemin} para escritura",
        'pt': "Impossível abrir {chemin} para escrita",
        'de': "{chemin} kann nicht zum Schreiben geöffnet werden",
    },
    'dxf_code_retour': {
        'fr': "QgsDxfExport a retourné le code {code}",
        'en': "QgsDxfExport returned code {code}",
        'es': "QgsDxfExport ha devuelto el código {code}",
        'pt': "QgsDxfExport devolveu o código {code}",
        'de': "QgsDxfExport hat den Code {code} zurückgegeben",
    },
    'dxf_etiquettes_decorees': {
        'fr': " — {nb} étiquette(s) décorée(s)", 'en': " — {nb} label(s) decorated",
        'es': " — {nb} etiqueta(s) decorada(s)", 'pt': " — {nb} etiqueta(s) decorada(s)",
        'de': " — {nb} Beschriftung(en) ausgestaltet",
    },
    'fic_dxf': {
        'fr': "DXF (*.dxf)", 'en': "DXF (*.dxf)", 'es': "DXF (*.dxf)",
        'pt': "DXF (*.dxf)", 'de': "DXF (*.dxf)",
    },
    # Contrôle de conformité StaR-Eau
    'sec_rien_a_exporter': {
        'fr': "Aucun objet exportable. Vérifiez que les couches EU/EP sont "
              "chargées et que les conduites sont raccordées à des regards.",
        'en': "Nothing to export. Check that the wastewater/stormwater layers are "
              "loaded and that the pipes are connected to manholes.",
        'es': "Ningún objeto exportable. Compruebe que las capas EU/EP están "
              "cargadas y que las tuberías están conectadas a pozos.",
        'pt': "Nenhum objeto exportável. Verifique que as camadas EU/EP estão "
              "carregadas e que as condutas estão ligadas a câmaras.",
        'de': "Nichts zu exportieren. Prüfen Sie, ob die SW-/RW-Layer geladen sind "
              "und die Leitungen an Schächte angeschlossen sind.",
    },
    'sec_ecriture': {
        'fr': "Écriture de {couche}…", 'en': "Writing {couche}…",
        'es': "Escribiendo {couche}…", 'pt': "A escrever {couche}…",
        'de': "{couche} wird geschrieben…",
    },
    'sec_echec_ecriture': {
        'fr': "Échec de l'écriture de {couche} : {detail}",
        'en': "Failed to write {couche}: {detail}",
        'es': "Fallo al escribir {couche}: {detail}",
        'pt': "Falha ao escrever {couche}: {detail}",
        'de': "Schreiben von {couche} fehlgeschlagen: {detail}",
    },
    'sec_termine': {
        'fr': "Terminé", 'en': "Done", 'es': "Terminado", 'pt': "Concluído",
        'de': "Fertig",
    },
    'sdt_gpkg_verrouille': {
        'fr': "Le GeoPackage de sortie est verrouillé et ne peut pas être "
              "remplacé :\n{chemin}\n\nFermez-le (QGIS, Explorateur, autre "
              "logiciel) ou choisissez un autre nom de sortie.\n({detail})",
        'en': "The output GeoPackage is locked and cannot be replaced:\n{chemin}"
              "\n\nClose it (QGIS, File Explorer, another program) or choose "
              "another output name.\n({detail})",
        'es': "El GeoPackage de salida está bloqueado y no se puede reemplazar:\n"
              "{chemin}\n\nCiérrelo (QGIS, Explorador, otro programa) o elija "
              "otro nombre de salida.\n({detail})",
        'pt': "O GeoPackage de saída está bloqueado e não pode ser substituído:\n"
              "{chemin}\n\nFeche-o (QGIS, Explorador, outro programa) ou escolha "
              "outro nome de saída.\n({detail})",
        'de': "Das Ausgabe-GeoPackage ist gesperrt und kann nicht ersetzt werden:\n"
              "{chemin}\n\nSchließen Sie es (QGIS, Explorer, anderes Programm) "
              "oder wählen Sie einen anderen Ausgabenamen.\n({detail})",
    },
    'sdt_err_ecriture': {
        'fr': "Erreur écriture couche {couche} (code={code}) : {detail}",
        'en': "Error writing layer {couche} (code={code}): {detail}",
        'es': "Error al escribir la capa {couche} (código={code}): {detail}",
        'pt': "Erro ao escrever a camada {couche} (código={code}): {detail}",
        'de': "Fehler beim Schreiben des Layers {couche} (Code={code}): {detail}",
    },
    'sdt_err_chargement': {
        'fr': "Impossible de charger {couche} ({nb} entités écrites) — URI : {uri}",
        'en': "Cannot load {couche} ({nb} features written) — URI: {uri}",
        'es': "No se puede cargar {couche} ({nb} entidades escritas) — URI: {uri}",
        'pt': "Impossível carregar {couche} ({nb} entidades escritas) — URI: {uri}",
        'de': "{couche} kann nicht geladen werden ({nb} Objekte geschrieben) — "
              "URI: {uri}",
    },
    'dxf_ezdxf_manquant': {
        'fr': "ezdxf est requis et son installation automatique a échoué : "
              "{detail}\nInstallez-le manuellement depuis l'OSGeo4W Shell : "
              "« python -m pip install ezdxf »",
        'en': "ezdxf is required and its automatic installation failed: {detail}\n"
              "Install it manually from the OSGeo4W Shell: "
              "“python -m pip install ezdxf”",
        'es': "ezdxf es necesario y su instalación automática ha fallado: {detail}\n"
              "Instálelo manualmente desde el OSGeo4W Shell: "
              "«python -m pip install ezdxf»",
        'pt': "O ezdxf é necessário e a sua instalação automática falhou: {detail}\n"
              "Instale-o manualmente a partir do OSGeo4W Shell: "
              "«python -m pip install ezdxf»",
        'de': "ezdxf wird benötigt und die automatische Installation ist "
              "fehlgeschlagen: {detail}\nInstallieren Sie es manuell in der "
              "OSGeo4W-Shell: „python -m pip install ezdxf“",
    },
    'sec_geom_absente': {
        'fr': "géométrie absente", 'en': "geometry missing",
        'es': "geometría ausente", 'pt': "geometria ausente",
        'de': "Geometrie fehlt",
    },
    'sec_tn_absent': {
        'fr': "terrain naturel non renseigné (z_tampon vide)",
        'en': "ground level not filled in (z_tampon empty)",
        'es': "terreno natural sin indicar (z_tampon vacío)",
        'pt': "terreno natural não indicado (z_tampon vazio)",
        'de': "Geländehöhe nicht angegeben (z_tampon leer)",
    },
    'sec_fe_absent': {
        'fr': "fil d'eau non renseigné (z_radier vide)",
        'en': "invert level not filled in (z_radier empty)",
        'es': "cota de solera sin indicar (z_radier vacío)",
        'pt': "cota de soleira não indicada (z_radier vazio)",
        'de': "Sohlhöhe nicht angegeben (z_radier leer)",
    },
    'sec_geom_invalide': {
        'fr': "géométrie invalide ou vide", 'en': "invalid or empty geometry",
        'es': "geometría no válida o vacía", 'pt': "geometria inválida ou vazia",
        'de': "ungültige oder leere Geometrie",
    },
    'sec_diametre_absent': {
        'fr': "diamètre absent (diametre_equivalent est obligatoire)",
        'en': "diameter missing (diametre_equivalent is mandatory)",
        'es': "diámetro ausente (diametre_equivalent es obligatorio)",
        'pt': "diâmetro ausente (diametre_equivalent é obrigatório)",
        'de': "Durchmesser fehlt (diametre_equivalent ist Pflicht)",
    },
    'sec_materiau_absent': {
        'fr': "matériau non renseigné, le défaut du dialogue sera appliqué",
        'en': "material not filled in, the dialog default will be applied",
        'es': "material sin indicar, se aplicará el valor por defecto del diálogo",
        'pt': "material não indicado, será aplicado o valor por omissão do diálogo",
        'de': "Material nicht angegeben, der Dialog-Standard wird angewendet",
    },
    'sec_extremite_sans_regard': {
        'fr': "extrémité sans regard : noeudinitial/noeudterminal ne peuvent pas "
              "être déduits",
        'en': "end without a manhole: noeudinitial/noeudterminal cannot be derived",
        'es': "extremo sin pozo: noeudinitial/noeudterminal no pueden deducirse",
        'pt': "extremidade sem câmara: noeudinitial/noeudterminal não podem ser "
              "deduzidos",
        'de': "Ende ohne Schacht: noeudinitial/noeudterminal nicht ableitbar",
    },
    'sec_aucune_extremite': {
        'fr': "aucune extrémité raccordée à un ouvrage",
        'en': "no end connected to a structure",
        'es': "ningún extremo conectado a una obra",
        'pt': "nenhuma extremidade ligada a uma estrutura",
        'de': "kein Ende mit einem Bauwerk verbunden",
    },
    'ot_confirmer_suppression': {
        'fr': "Confirmer la suppression", 'en': "Confirm deletion",
        'es': "Confirmar la eliminación", 'pt': "Confirmar a eliminação",
        'de': "Löschen bestätigen",
    },
    'ot_supprimer_selection_q': {
        'fr': "Supprimer {nb} élément(s) sélectionné(s) (cascade incluse) ?",
        'en': "Delete {nb} selected item(s), cascade included?",
        'es': "¿Eliminar {nb} elemento(s) seleccionado(s) (cascada incluida)?",
        'pt': "Eliminar {nb} elemento(s) selecionado(s) (cascata incluída)?",
        'de': "{nb} ausgewählte(s) Element(e) löschen (Kaskade eingeschlossen)?",
    },
    'ot_effacer_annotation': {
        'fr': "Effacer l'annotation", 'en': "Delete the annotation",
        'es': "Borrar la anotación", 'pt': "Apagar a anotação",
        'de': "Anmerkung löschen",
    },
    'ot_supprimer_annotation_q': {
        'fr': "Supprimer l'annotation « {nom} » ?",
        'en': "Delete the annotation “{nom}”?",
        'es': "¿Eliminar la anotación «{nom}»?",
        'pt': "Eliminar a anotação «{nom}»?",
        'de': "Anmerkung „{nom}“ löschen?",
    },
    'ot_aide_coupe': {
        'fr': "Tracez l'axe de coupe : clic gauche = ajouter un point  ·  "
              "Double-clic ou clic droit = terminer  ·  Échap = annuler",
        'en': "Draw the section line: left click = add a point  ·  double-click "
              "or right click = finish  ·  Esc = cancel",
        'es': "Trace el eje de sección: clic izquierdo = añadir un punto  ·  "
              "doble clic o clic derecho = terminar  ·  Esc = cancelar",
        'pt': "Trace o eixo de corte: clique esquerdo = adicionar um ponto  ·  "
              "duplo clique ou clique direito = terminar  ·  Esc = cancelar",
        'de': "Schnittlinie zeichnen: Linksklick = Punkt hinzufügen  ·  "
              "Doppelklick oder Rechtsklick = beenden  ·  Esc = abbrechen",
    },
    'ot_aucune_conduite_coupe': {
        'fr': "Aucune conduite EU ou EP croisée par le trait de coupe.\n"
              "Vérifiez que le trait intersecte bien les conduites.",
        'en': "No EU or EP pipe crossed by the section line.\nCheck that the "
              "line actually intersects the pipes.",
        'es': "Ninguna tubería EU o EP cruzada por la línea de sección.\n"
              "Compruebe que la línea corta realmente las tuberías.",
        'pt': "Nenhuma conduta EU ou EP cruzada pela linha de corte.\nVerifique "
              "se a linha interseta realmente as condutas.",
        'de': "Keine EU- oder EP-Leitung von der Schnittlinie gekreuzt.\nPrüfen "
              "Sie, ob die Linie die Leitungen wirklich schneidet.",
    },
    'ot_erreur_dxf': {
        'fr': "Erreur lors de l'export DXF :\n{erreur}",
        'en': "DXF export failed:\n{erreur}",
        'es': "Error durante la exportación DXF:\n{erreur}",
        'pt': "Erro durante a exportação DXF:\n{erreur}",
        'de': "Fehler beim DXF-Export:\n{erreur}",
    },
    'ot_dxf_symboles': {
        'fr': "DXF écrit, mais symboles ponctuels échoués : {erreur}",
        'en': "DXF written, but point symbols failed: {erreur}",
        'es': "DXF escrito, pero han fallado los símbolos puntuales: {erreur}",
        'pt': "DXF escrito, mas os símbolos pontuais falharam: {erreur}",
        'de': "DXF geschrieben, aber Punktsymbole fehlgeschlagen: {erreur}",
    },
    'ot_dxf_ltscale': {
        'fr': "DXF écrit, mais ltscale EU/EP échoué : {erreur}",
        'en': "DXF written, but EU/EP ltscale failed: {erreur}",
        'es': "DXF escrito, pero ha fallado el ltscale EU/EP: {erreur}",
        'pt': "DXF escrito, mas o ltscale EU/EP falhou: {erreur}",
        'de': "DXF geschrieben, aber EU/EP-ltscale fehlgeschlagen: {erreur}",
    },
    'ot_dxf_etiquettes': {
        'fr': "DXF écrit, mais décoration des étiquettes échouée : {erreur}",
        'en': "DXF written, but label decoration failed: {erreur}",
        'es': "DXF escrito, pero ha fallado la decoración de etiquetas: {erreur}",
        'pt': "DXF escrito, mas a decoração dos rótulos falhou: {erreur}",
        'de': "DXF geschrieben, aber Beschriftungsdekoration fehlgeschlagen: "
              "{erreur}",
    },
    'ot_dxf_exporte': {
        'fr': "DXF 2018 exporté — {nb} couche(s) : {chemin}",
        'en': "DXF 2018 exported — {nb} layer(s): {chemin}",
        'es': "DXF 2018 exportado — {nb} capa(s): {chemin}",
        'pt': "DXF 2018 exportado — {nb} camada(s): {chemin}",
        'de': "DXF 2018 exportiert — {nb} Layer: {chemin}",
    },
    'ot_renum_titre': {
        'fr': "Renumérotation – préfixes et numéros de départ",
        'en': "Renumbering – prefixes and starting numbers",
        'es': "Renumeración – prefijos y números iniciales",
        'pt': "Renumeração – prefixos e números iniciais",
        'de': "Neunummerierung – Präfixe und Startnummern",
    },
    'ot_renum_exemple': {
        'fr': "<i>Exemple : regards dès 00 → REU00, REU01 …  tabourets dès 01 → "
              "EU-BRCHT01, EU-BRCHT02 …</i>",
        'en': "<i>Example: manholes from 00 → REU00, REU01 …  chambers from 01 → "
              "EU-BRCHT01, EU-BRCHT02 …</i>",
        'es': "<i>Ejemplo: pozos desde 00 → REU00, REU01 …  arquetas desde 01 → "
              "EU-BRCHT01, EU-BRCHT02 …</i>",
        'pt': "<i>Exemplo: caixas a partir de 00 → REU00, REU01 …  câmaras a "
              "partir de 01 → EU-BRCHT01, EU-BRCHT02 …</i>",
        'de': "<i>Beispiel: Schächte ab 00 → REU00, REU01 …  "
              "Anschlussschächte ab 01 → EU-BRCHT01, EU-BRCHT02 …</i>",
    },
    'ot_aide_renum': {
        'fr': "1er clic : regard départ (vert)  ·  2e clic : regard arrivée → "
              "dialogue préfixes  ·  Échap : annuler",
        'en': "1st click: start manhole (green)  ·  2nd click: end manhole → "
              "prefix dialog  ·  Esc: cancel",
        'es': "1.º clic: pozo inicial (verde)  ·  2.º clic: pozo final → diálogo "
              "de prefijos  ·  Esc: cancelar",
        'pt': "1.º clique: caixa inicial (verde)  ·  2.º clique: caixa final → "
              "diálogo de prefixos  ·  Esc: cancelar",
        'de': "1. Klick: Startschacht (grün)  ·  2. Klick: Endschacht → "
              "Präfix-Dialog  ·  Esc: abbrechen",
    },
    'ot_renumerotation': {
        'fr': "Renumérotation", 'en': "Renumbering", 'es': "Renumeración",
        'pt': "Renumeração", 'de': "Neunummerierung",
    },

    # ─────────────────────────────────────────────────────────────────────
    #  Configuration rapide et impression
    # ─────────────────────────────────────────────────────────────────────
    'qc_reseau': {
        'fr': "Réseau {code}", 'en': "{code} network", 'es': "Red {code}",
        'pt': "Rede {code}", 'de': "Netz {code}",
    },
    'qc_params_cubature': {
        'fr': "Paramètres de cubature de tranchées",
        'en': "Trench volume parameters",
        'es': "Parámetros de cubicación de zanjas",
        'pt': "Parâmetros de cubagem de valas",
        'de': "Parameter der Grabenmassen",
    },
    'qc_apercu_largeur': {
        'fr': "Aperçu de la largeur", 'en': "Width preview",
        'es': "Vista previa del ancho", 'pt': "Pré-visualização da largura",
        'de': "Breitenvorschau",
    },
    'qc_visualiser_pour': {
        'fr': "Visualiser la largeur pour :", 'en': "Preview the width for:",
        'es': "Visualizar el ancho para:", 'pt': "Visualizar a largura para:",
        'de': "Breite anzeigen für:",
    },
    'qc_params_remblai': {
        'fr': "Paramètres de remblai et chaussée",
        'en': "Backfill and roadway parameters",
        'es': "Parámetros de relleno y calzada",
        'pt': "Parâmetros de aterro e faixa",
        'de': "Parameter für Verfüllung und Fahrbahn",
    },
    'qc_partie_inf': {
        'fr': "Partie inférieure chaussée", 'en': "Road sub-base",
        'es': "Parte inferior de la calzada", 'pt': "Parte inferior da faixa",
        'de': "Untere Fahrbahnschicht",
    },
    'qc_partie_sup': {
        'fr': "Partie supérieure chaussée", 'en': "Road surface course",
        'es': "Parte superior de la calzada", 'pt': "Parte superior da faixa",
        'de': "Obere Fahrbahnschicht",
    },
    'qc_non_configure': {
        'fr': "-- non configuré --", 'en': "-- not configured --",
        'es': "-- sin configurar --", 'pt': "-- não configurado --",
        'de': "-- nicht konfiguriert --",
    },
    'pd_titre': {
        'fr': "Paramètres d'impression", 'en': "Print settings",
        'es': "Parámetros de impresión", 'pt': "Parâmetros de impressão",
        'de': "Druckeinstellungen",
    },
    'pd_placer': {
        'fr': "Placer les planches →", 'en': "Place the sheets →",
        'es': "Colocar las hojas →", 'pt': "Colocar as folhas →",
        'de': "Blätter platzieren →",
    },
    'pd_titre_plan': {
        'fr': "Titre du plan :", 'en': "Drawing title:",
        'es': "Título del plano:", 'pt': "Título da planta:",
        'de': "Plantitel:",
    },
    'pd_format': {
        'fr': "Format :", 'en': "Sheet size:", 'es': "Formato:",
        'pt': "Formato:", 'de': "Format:",
    },
    'pd_orientation': {
        'fr': "Orientation :", 'en': "Orientation:", 'es': "Orientación:",
        'pt': "Orientação:", 'de': "Ausrichtung:",
    },
    'pd_paysage': {
        'fr': "Paysage", 'en': "Landscape", 'es': "Horizontal",
        'pt': "Horizontal", 'de': "Querformat",
    },
    'pd_portrait': {
        'fr': "Portrait", 'en': "Portrait", 'es': "Vertical",
        'pt': "Vertical", 'de': "Hochformat",
    },
    'pd_echelle': {
        'fr': "Échelle :", 'en': "Scale:", 'es': "Escala:",
        'pt': "Escala:", 'de': "Maßstab:",
    },
    'pd_resolution': {
        'fr': "Résolution PDF :", 'en': "PDF resolution:",
        'es': "Resolución PDF:", 'pt': "Resolução PDF:",
        'de': "PDF-Auflösung:",
    },
    'pd_echelle_perso': {
        'fr': "Personnalisée : 1 / …", 'en': "Custom: 1 / …",
        'es': "Personalizada: 1 / …", 'pt': "Personalizada: 1 / …",
        'de': "Benutzerdefiniert: 1 / …",
    },
    'pd_plan_reseau': {
        'fr': "Plan de réseau", 'en': "Network drawing",
        'es': "Plano de red", 'pt': "Planta da rede", 'de': "Netzplan",
    },
    'pd_dpi_legere': {
        'fr': "Légère  –  96 dpi", 'en': "Light  –  96 dpi",
        'es': "Ligera  –  96 ppp", 'pt': "Leve  –  96 ppp",
        'de': "Leicht  –  96 dpi",
    },
    'pd_dpi_legere_note': {
        'fr': "Fichier très léger, qualité réduite",
        'en': "Very small file, reduced quality",
        'es': "Archivo muy ligero, calidad reducida",
        'pt': "Ficheiro muito leve, qualidade reduzida",
        'de': "Sehr kleine Datei, geringere Qualität",
    },
    'pd_dpi_standard': {
        'fr': "Standard  –  150 dpi", 'en': "Standard  –  150 dpi",
        'es': "Estándar  –  150 ppp", 'pt': "Padrão  –  150 ppp",
        'de': "Standard  –  150 dpi",
    },
    'pd_dpi_standard_note': {
        'fr': "Bon compromis taille / qualité (recommandé A1/A0)",
        'en': "Good size / quality trade-off (recommended for A1/A0)",
        'es': "Buen equilibrio tamaño / calidad (recomendado A1/A0)",
        'pt': "Bom compromisso tamanho / qualidade (recomendado A1/A0)",
        'de': "Guter Kompromiss Größe / Qualität (empfohlen für A1/A0)",
    },
    'pd_dpi_bonne': {
        'fr': "Bonne qualité  –  200 dpi", 'en': "Good quality  –  200 dpi",
        'es': "Buena calidad  –  200 ppp", 'pt': "Boa qualidade  –  200 ppp",
        'de': "Gute Qualität  –  200 dpi",
    },
    'pd_dpi_bonne_note': {
        'fr': "Qualité correcte, fichier modéré",
        'en': "Decent quality, moderate file size",
        'es': "Calidad correcta, archivo moderado",
        'pt': "Qualidade correta, ficheiro moderado",
        'de': "Ordentliche Qualität, moderate Dateigröße",
    },
    'pd_dpi_haute': {
        'fr': "Haute qualité  –  300 dpi", 'en': "High quality  –  300 dpi",
        'es': "Alta calidad  –  300 ppp", 'pt': "Alta qualidade  –  300 ppp",
        'de': "Hohe Qualität  –  300 dpi",
    },
    'pd_dpi_haute_note': {
        'fr': "Fichier lourd – à éviter en A1/A0",
        'en': "Heavy file – avoid for A1/A0",
        'es': "Archivo pesado – evitar en A1/A0",
        'pt': "Ficheiro pesado – evitar em A1/A0",
        'de': "Große Datei – bei A1/A0 vermeiden",
    },
    'pd_dpi_perso': {
        'fr': "Personnalisée…", 'en': "Custom…", 'es': "Personalizada…",
        'pt': "Personalizada…", 'de': "Benutzerdefiniert…",
    },
    'pd_dpi_perso_note': {
        'fr': "Saisissez la résolution souhaitée",
        'en': "Enter the resolution you want",
        'es': "Introduzca la resolución deseada",
        'pt': "Introduza a resolução pretendida",
        'de': "Gewünschte Auflösung eingeben",
    },
    'pt_aide_pose': {
        'fr': "{format} {orientation}  ·  1:{echelle}  —  1er clic : ancrer  ·  "
              "orienter  ·  2e clic : fixer  |  Clic droit : exporter  |  "
              "Échap : changer l'échelle",
        'en': "{format} {orientation}  ·  1:{echelle}  —  1st click: anchor  ·  "
              "rotate  ·  2nd click: place  |  Right click: export  |  "
              "Esc: change the scale",
        'es': "{format} {orientation}  ·  1:{echelle}  —  1.er clic: anclar  ·  "
              "orientar  ·  2.º clic: fijar  |  Clic derecho: exportar  |  "
              "Esc: cambiar la escala",
        'pt': "{format} {orientation}  ·  1:{echelle}  —  1.º clique: ancorar  ·  "
              "orientar  ·  2.º clique: fixar  |  Clique direito: exportar  |  "
              "Esc: mudar a escala",
        'de': "{format} {orientation}  ·  1:{echelle}  —  1. Klick: verankern  ·  "
              "drehen  ·  2. Klick: setzen  |  Rechtsklick: exportieren  |  "
              "Esc: Maßstab ändern",
    },
    'pt_rendu_cartes': {
        'fr': "Rendu des cartes…", 'en': "Rendering the maps…",
        'es': "Generando los mapas…", 'pt': "A gerar os mapas…",
        'de': "Karten werden gerendert…",
    },
    'pt_cartouche_ensemble': {
        'fr': "{titre} — Plan d'ensemble", 'en': "{titre} — Overview drawing",
        'es': "{titre} — Plano de conjunto", 'pt': "{titre} — Planta de conjunto",
        'de': "{titre} — Übersichtsplan",
    },
    'pt_ecriture_impossible': {
        'fr': "Impossible d'écrire dans : {chemin}\nVérifiez que le fichier "
              "n'est pas ouvert dans un autre programme.",
        'en': "Cannot write to: {chemin}\nCheck that the file is not open in "
              "another program.",
        'es': "No se puede escribir en: {chemin}\nCompruebe que el archivo no "
              "esté abierto en otro programa.",
        'pt': "Impossível escrever em: {chemin}\nVerifique que o ficheiro não "
              "está aberto noutro programa.",
        'de': "Schreiben nicht möglich: {chemin}\nPrüfen Sie, ob die Datei in "
              "einem anderen Programm geöffnet ist.",
    },
    'pt_nb_feuilles': {
        'fr': "{nb} planche(s)  —  1 : {echelle}",
        'en': "{nb} sheet(s)  —  1 : {echelle}",
        'es': "{nb} hoja(s)  —  1 : {echelle}",
        'pt': "{nb} folha(s)  —  1 : {echelle}",
        'de': "{nb} Blatt  —  1 : {echelle}",
    },
    'pt_ens': {
        'fr': "Ens.", 'en': "Ovw.", 'es': "Conj.", 'pt': "Conj.",
        'de': "Übers.",
    },
    'pt_pdf_impossible': {
        'fr': "Impossible de créer le fichier PDF : {chemin}",
        'en': "Cannot create the PDF file: {chemin}",
        'es': "No se puede crear el archivo PDF: {chemin}",
        'pt': "Impossível criar o ficheiro PDF: {chemin}",
        'de': "PDF-Datei kann nicht erstellt werden: {chemin}",
    },
    'pg_titre': {
        'fr': "Profil groupé EU + EP", 'en': "Combined EU + EP profile",
        'es': "Perfil agrupado EU + EP", 'pt': "Perfil agrupado EU + EP",
        'de': "Kombiniertes EU + EP Profil",
    },
    'pg_exporter_en': {
        'fr': "Exporter le profil groupé en {format}",
        'en': "Export the combined profile as {format}",
        'es': "Exportar el perfil agrupado en {format}",
        'pt': "Exportar o perfil agrupado em {format}",
        'de': "Kombiniertes Profil als {format} exportieren",
    },
    'et_regle_auto': {
        'fr': "{role} – auto", 'en': "{role} – automatic",
        'es': "{role} – automática", 'pt': "{role} – automática",
        'de': "{role} – automatisch",
    },
    'et_regle_epinglee': {
        'fr': "{role} – épinglée", 'en': "{role} – pinned",
        'es': "{role} – fijada", 'pt': "{role} – fixada",
        'de': "{role} – angeheftet",
    },
    'ea_titre': {
        'fr': "Gestion de l'affichage des étiquettes",
        'en': "Label display management",
        'es': "Gestión de la visualización de etiquetas",
        'pt': "Gestão da exibição dos rótulos",
        'de': "Verwaltung der Beschriftungsanzeige",
    },
    'ea_visibilite_contenu': {
        'fr': "Visibilité et contenu des étiquettes",
        'en': "Label visibility and content",
        'es': "Visibilidad y contenido de las etiquetas",
        'pt': "Visibilidade e conteúdo dos rótulos",
        'de': "Sichtbarkeit und Inhalt der Beschriftungen",
    },
    'ea_visibilite_reseau': {
        'fr': "Visibilité par réseau et par type",
        'en': "Visibility by network and type",
        'es': "Visibilidad por red y por tipo",
        'pt': "Visibilidade por rede e por tipo",
        'de': "Sichtbarkeit nach Netz und Typ",
    },
    'ea_infos_affichees': {
        'fr': "Informations affichées dans les étiquettes",
        'en': "Information shown in the labels",
        'es': "Información mostrada en las etiquetas",
        'pt': "Informação mostrada nos rótulos",
        'de': "In den Beschriftungen angezeigte Informationen",
    },

    # ─────────────────────────────────────────────────────────────────────
    #  Derniers bandeaux d'aide des outils de carte
    # ─────────────────────────────────────────────────────────────────────
    'ot_aide_conduite': {
        'fr': "Clic gauche : ajouter un point  ·  Clic droit : terminer  ·  "
              "← : annuler le dernier point  ·  Échap : tout annuler",
        'en': "Left click: add a point  ·  Right click: finish  ·  "
              "←: undo the last point  ·  Esc: cancel everything",
        'es': "Clic izquierdo: añadir un punto  ·  Clic derecho: terminar  ·  "
              "←: deshacer el último punto  ·  Esc: cancelar todo",
        'pt': "Clique esquerdo: adicionar um ponto  ·  Clique direito: terminar  "
              "·  ←: anular o último ponto  ·  Esc: cancelar tudo",
        'de': "Linksklick: Punkt hinzufügen  ·  Rechtsklick: beenden  ·  "
              "←: letzten Punkt zurücknehmen  ·  Esc: alles abbrechen",
    },
    'ot_regard_proche': {
        'fr': "Regard existant à moins de {distance} m — rapprochez le curseur "
              "pour snapper ou vérifiez la connexion.",
        'en': "An existing manhole is within {distance} m — move the cursor "
              "closer to snap, or check the connection.",
        'es': "Hay un pozo existente a menos de {distance} m — acerque el cursor "
              "para ajustar o compruebe la conexión.",
        'pt': "Existe uma caixa a menos de {distance} m — aproxime o cursor para "
              "ajustar ou verifique a ligação.",
        'de': "Vorhandener Schacht unter {distance} m — Zeiger zum Fangen näher "
              "bewegen oder Verbindung prüfen.",
    },
    'ot_aide_move': {
        'fr': "Clic gauche sur un ouvrage, un piquage de branchement ou une "
              "étiquette  ·  2e clic : poser  ·  Échap : annuler",
        'en': "Left click a structure, a connection tap-in or a label  ·  "
              "2nd click: drop  ·  Esc: cancel",
        'es': "Clic izquierdo en una obra, una conexión de acometida o una "
              "etiqueta  ·  2.º clic: soltar  ·  Esc: cancelar",
        'pt': "Clique esquerdo numa estrutura, numa ligação de ramal ou num "
              "rótulo  ·  2.º clique: largar  ·  Esc: cancelar",
        'de': "Linksklick auf ein Bauwerk, eine Anschlussanbohrung oder eine "
              "Beschriftung  ·  2. Klick: absetzen  ·  Esc: abbrechen",
    },
    'ot_aide_move_cible': {
        'fr': "Déplacer vers la conduite ou un regard  ·  Clic : confirmer  ·  "
              "Échap : annuler",
        'en': "Move to the pipe or a manhole  ·  Click: confirm  ·  Esc: cancel",
        'es': "Mover hacia la tubería o un pozo  ·  Clic: confirmar  ·  "
              "Esc: cancelar",
        'pt': "Mover para a conduta ou uma caixa  ·  Clique: confirmar  ·  "
              "Esc: cancelar",
        'de': "Auf die Leitung oder einen Schacht verschieben  ·  Klick: "
              "bestätigen  ·  Esc: abbrechen",
    },
    'ot_aide_copy': {
        'fr': "1er clic : source (bleu)  ·  Clics suivants : cibles (vert)  ·  "
              "Clic droit : appliquer  ·  Échap : annuler",
        'en': "1st click: source (blue)  ·  Next clicks: targets (green)  ·  "
              "Right click: apply  ·  Esc: cancel",
        'es': "1.º clic: origen (azul)  ·  Clics siguientes: destinos (verde)  ·  "
              "Clic derecho: aplicar  ·  Esc: cancelar",
        'pt': "1.º clique: origem (azul)  ·  Cliques seguintes: destinos (verde)  "
              "·  Clique direito: aplicar  ·  Esc: cancelar",
        'de': "1. Klick: Quelle (blau)  ·  Weitere Klicks: Ziele (grün)  ·  "
              "Rechtsklick: anwenden  ·  Esc: abbrechen",
    },
    'ot_aide_insert_regard': {
        'fr': "Survoler une conduite (vert) puis cliquer pour insérer un regard "
              "et couper la conduite",
        'en': "Hover a pipe (green) then click to insert a manhole and split the "
              "pipe",
        'es': "Sitúe el cursor sobre una tubería (verde) y haga clic para "
              "insertar un pozo y cortar la tubería",
        'pt': "Passe sobre uma conduta (verde) e clique para inserir uma caixa e "
              "cortar a conduta",
        'de': "Über eine Leitung fahren (grün) und klicken, um einen Schacht "
              "einzufügen und die Leitung zu teilen",
    },
    'ot_aide_renseignement': {
        'fr': "Survoler un élément pour le mettre en évidence  ·  Clic gauche : "
              "ouvrir le formulaire d'attributs",
        'en': "Hover an item to highlight it  ·  Left click: open the attribute "
              "form",
        'es': "Sitúe el cursor sobre un elemento para resaltarlo  ·  Clic "
              "izquierdo: abrir el formulario de atributos",
        'pt': "Passe sobre um elemento para o realçar  ·  Clique esquerdo: abrir "
              "o formulário de atributos",
        'de': "Über ein Element fahren zum Hervorheben  ·  Linksklick: "
              "Attributformular öffnen",
    },
    'ban_rechercher': {
        'fr': "Rechercher une adresse...", 'en': "Search for an address...",
        'es': "Buscar una dirección...", 'pt': "Procurar um endereço...",
        'de': "Adresse suchen …",
    },
    'ea_etiquettes_role': {
        'fr': "Étiquettes {role} – {reseau}", 'en': "{role} labels – {reseau}",
        'es': "Etiquetas {role} – {reseau}", 'pt': "Rótulos {role} – {reseau}",
        'de': "{role}-Beschriftungen – {reseau}",
    },

    # ─────────────────────────────────────────────────────────────────────
    #  Fenêtre d'import DXF / DWG
    #  Elle était codée en anglais en dur, seule fenêtre du plugin dans ce
    #  cas ; le français devient donc une traduction comme les autres.
    # ─────────────────────────────────────────────────────────────────────
    'dx_titre': {
        'fr': "Convertisseur DAO → SIG", 'en': "CAD to GIS Converter",
        'es': "Conversor CAD → SIG", 'pt': "Conversor CAD → SIG",
        'de': "CAD-nach-GIS-Konverter",
    },
    'dx_entree': {
        'fr': "Fichier DAO d'entrée (DXF/DWG)", 'en': "Input CAD (DXF/DWG)",
        'es': "Archivo CAD de entrada (DXF/DWG)",
        'pt': "Ficheiro CAD de entrada (DXF/DWG)",
        'de': "CAD-Eingabedatei (DXF/DWG)",
    },
    'dx_parcourir': {
        'fr': "Parcourir", 'en': "Browse", 'es': "Examinar",
        'pt': "Procurar", 'de': "Durchsuchen",
    },
    'dx_scanner': {
        'fr': "Analyser les calques", 'en': "Scan Layers",
        'es': "Analizar las capas", 'pt': "Analisar as camadas",
        'de': "Layer scannen",
    },
    'dx_noms_calques': {
        'fr': "Noms de calques (CSV, remplis depuis l'aperçu)",
        'en': "Layer names (CSV, auto-filled from preview)",
        'es': "Nombres de capas (CSV, rellenados desde la vista previa)",
        'pt': "Nomes de camadas (CSV, preenchidos a partir da pré-visualização)",
        'de': "Layernamen (CSV, aus der Vorschau übernommen)",
    },
    'dx_tout_selectionner': {
        'fr': "Tout sélectionner", 'en': "Select All", 'es': "Seleccionar todo",
        'pt': "Selecionar tudo", 'de': "Alle auswählen",
    },
    'dx_effacer': {
        'fr': "Effacer", 'en': "Clear", 'es': "Borrar", 'pt': "Limpar",
        'de': "Leeren",
    },
    'dx_apercu_calques': {
        'fr': "Aperçu des calques", 'en': "Layer Preview",
        'es': "Vista previa de las capas", 'pt': "Pré-visualização das camadas",
        'de': "Layer-Vorschau",
    },
    'dx_epsg_source': {
        'fr': "EPSG source", 'en': "Source EPSG", 'es': "EPSG de origen",
        'pt': "EPSG de origem", 'de': "Quell-EPSG",
    },
    'dx_epsg_cible': {
        'fr': "EPSG cible (facultatif)", 'en': "Target EPSG (optional)",
        'es': "EPSG de destino (opcional)", 'pt': "EPSG de destino (opcional)",
        'de': "Ziel-EPSG (optional)",
    },
    'dx_blocs': {
        'fr': "Traitement des blocs", 'en': "Block handling",
        'es': "Tratamiento de los bloques", 'pt': "Tratamento dos blocos",
        'de': "Blockbehandlung",
    },
    'dx_tol_fusion': {
        'fr': "Tolérance de fusion des lignes", 'en': "Line-merge tolerance",
        'es': "Tolerancia de fusión de líneas",
        'pt': "Tolerância de fusão de linhas",
        'de': "Toleranz für Linienverschmelzung",
    },
    'dx_tol_spline': {
        'fr': "Tolérance des splines", 'en': "Spline tolerance",
        'es': "Tolerancia de las splines", 'pt': "Tolerância das splines",
        'de': "Spline-Toleranz",
    },
    'dx_pilote': {
        'fr': "Pilote de sortie", 'en': "Output driver",
        'es': "Controlador de salida", 'pt': "Controlador de saída",
        'de': "Ausgabetreiber",
    },
    'dx_gpkg_sortie': {
        'fr': "GeoPackage de sortie (GPKG)", 'en': "Output GeoPackage (GPKG)",
        'es': "GeoPackage de salida (GPKG)", 'pt': "GeoPackage de saída (GPKG)",
        'de': "Ausgabe-GeoPackage (GPKG)",
    },
    'dx_convertisseur_dwg': {
        'fr': "Convertisseur DWG préféré", 'en': "DWG converter preference",
        'es': "Conversor DWG preferido", 'pt': "Conversor DWG preferido",
        'de': "Bevorzugter DWG-Konverter",
    },
    'dx_version_dxf': {
        'fr': "Version DXF pour la conversion DWG",
        'en': "DXF version for DWG conversion",
        'es': "Versión DXF para la conversión DWG",
        'pt': "Versão DXF para a conversão DWG",
        'de': "DXF-Version für die DWG-Konvertierung",
    },
    'dx_options': {
        'fr': "Options", 'en': "Options", 'es': "Opciones", 'pt': "Opções",
        'de': "Optionen",
    },
    'dx_ecraser': {
        'fr': "Écraser l'existant", 'en': "Overwrite existing",
        'es': "Sobrescribir lo existente", 'pt': "Substituir o existente",
        'de': "Vorhandenes überschreiben",
    },
    'dx_format_texte': {
        'fr': "Mettre en forme les étiquettes texte (taille / police / "
              "soulignement du DXF)",
        'en': "Format text labels (size / font / underline from DXF)",
        'es': "Formatear las etiquetas de texto (tamaño / fuente / subrayado del "
              "DXF)",
        'pt': "Formatar os rótulos de texto (tamanho / tipo de letra / sublinhado "
              "do DXF)",
        'de': "Textbeschriftungen formatieren (Größe / Schrift / Unterstreichung "
              "aus DXF)",
    },
    'dx_couleurs': {
        'fr': "Appliquer les couleurs des entités DXF (lignes, polygones, points)",
        'en': "Apply DXF entity colors (lines, polygons, points)",
        'es': "Aplicar los colores de las entidades DXF (líneas, polígonos, "
              "puntos)",
        'pt': "Aplicar as cores das entidades DXF (linhas, polígonos, pontos)",
        'de': "Farben der DXF-Objekte übernehmen (Linien, Polygone, Punkte)",
    },
    'dx_3d': {
        'fr': "Inclure la géométrie 3D (coordonnée Z)",
        'en': "Include 3D geometry (Z coordinate)",
        'es': "Incluir la geometría 3D (coordenada Z)",
        'pt': "Incluir a geometria 3D (coordenada Z)",
        'de': "3D-Geometrie einbeziehen (Z-Koordinate)",
    },
    'dx_echelle_texte': {
        'fr': "Échelle du texte :", 'en': "Text scale:",
        'es': "Escala del texto:", 'pt': "Escala do texto:",
        'de': "Textmaßstab:",
    },
    'dx_jeu_caracteres': {
        'fr': "Jeu de caractères :", 'en': "Charset:",
        'es': "Juego de caracteres:", 'pt': "Conjunto de carateres:",
        'de': "Zeichensatz:",
    },
    'dx_lancer': {
        'fr': "Lancer", 'en': "Run", 'es': "Ejecutar", 'pt': "Executar",
        'de': "Starten",
    },
    'dx_choisir_fichier': {
        'fr': "Choisir le fichier DAO", 'en': "Select CAD file",
        'es': "Elegir el archivo CAD", 'pt': "Escolher o ficheiro CAD",
        'de': "CAD-Datei wählen",
    },
    'dx_gpkg_sortie_titre': {
        'fr': "GeoPackage de sortie", 'en': "Output GeoPackage",
        'es': "GeoPackage de salida", 'pt': "GeoPackage de saída",
        'de': "Ausgabe-GeoPackage",
    },
    'dx_dossier_shp': {
        'fr': "Dossier de sortie pour les Shapefiles",
        'en': "Output folder for Shapefiles",
        'es': "Carpeta de salida para los Shapefiles",
        'pt': "Pasta de saída para os Shapefiles",
        'de': "Ausgabeordner für Shapefiles",
    },
    'dx_dossier_shp_label': {
        'fr': "Dossier de sortie (SHP)", 'en': "Output folder (SHP)",
        'es': "Carpeta de salida (SHP)", 'pt': "Pasta de saída (SHP)",
        'de': "Ausgabeordner (SHP)",
    },
    'dx_choisir_dossier': {
        'fr': "Choisir le dossier", 'en': "Select Folder",
        'es': "Elegir la carpeta", 'pt': "Escolher a pasta",
        'de': "Ordner wählen",
    },

    # ─────────────────────────────────────────────────────────────────────
    #  Texte de présentation de la fenêtre À propos
    #  Il provenait de metadata.txt, qui n'existe qu'en français : le
    #  dictionnaire prend le relais, metadata restant le repli.
    # ─────────────────────────────────────────────────────────────────────
    'ab_description': {
        'fr': "CanaPlan est un logiciel de dessin projet qui permet de tracer "
              "des réseaux d'assainissement EU (Eaux Usées) et EP (Eaux "
              "Pluviales) directement dans QGIS, sur un fond de carte importé "
              "par le plugin (BAN, cadastre PCI, orthophoto IGN, OSM, ou plan "
              "DXF/DWG existant), avec continuité géométrique native : chaque "
              "conduite relie deux ouvrages, chaque branchement se recale "
              "automatiquement sur sa conduite mère quand elle bouge.\n\n"
              "L'outil produit les profils en long (EU/EP/groupé), calcule les "
              "volumes de cubature (déblai et matériaux de remblai rapportés), "
              "génère des coupes de tranchée transversales, imprime les plans "
              "au format PDF multi-feuilles avec plan d'ensemble et exporte en "
              "DXF 2018 fidèle.\n\n"
              "Du relevé terrain jusqu'à la livraison, un seul outil couvre "
              "toute la chaîne : import Star-DT / StaR-Elec (DT-DICT), fonds de "
              "plan IGN/BAN/PCI chargés en tâche de fond, et export GeoPackage "
              "conforme au géostandard StaR-Eau V2024 (CNIG/ASTEE).",
        'en': "CanaPlan is a design-drawing tool for laying out wastewater (EU) "
              "and stormwater (EP) sewer networks directly inside QGIS, over a "
              "basemap the plugin loads for you (BAN addresses, PCI cadastre, "
              "IGN orthophoto, OSM, or an existing DXF/DWG drawing), with native "
              "geometric continuity: every pipe joins two structures, and every "
              "service connection re-anchors itself onto its parent pipe when "
              "that pipe moves.\n\n"
              "The plugin produces longitudinal profiles (EU/EP/combined), "
              "computes trench volumes (excavation and imported backfill "
              "materials), generates cross-section drawings, prints multi-sheet "
              "PDF plans with an overview sheet, and exports faithful DXF 2018."
              "\n\n"
              "From field survey to delivery, one tool covers the whole chain: "
              "Star-DT / StaR-Elec (DT-DICT) import, IGN/BAN/PCI basemaps "
              "fetched in the background, and GeoPackage export compliant with "
              "the StaR-Eau V2024 geostandard (CNIG/ASTEE).",
        'es': "CanaPlan es una herramienta de dibujo de proyecto que permite "
              "trazar redes de saneamiento de aguas residuales (EU) y aguas "
              "pluviales (EP) directamente en QGIS, sobre un mapa base que el "
              "propio complemento carga (BAN, catastro PCI, ortofoto IGN, OSM o "
              "un plano DXF/DWG existente), con continuidad geométrica nativa: "
              "cada tubería une dos obras y cada acometida se reajusta "
              "automáticamente sobre su tubería madre cuando esta se mueve.\n\n"
              "La herramienta produce perfiles longitudinales (EU/EP/agrupados), "
              "calcula los volúmenes de cubicación (desmonte y materiales de "
              "relleno aportados), genera secciones transversales de zanja, "
              "imprime los planos en PDF multihoja con plano de conjunto y "
              "exporta en DXF 2018 fiel.\n\n"
              "Del levantamiento de campo a la entrega, una sola herramienta "
              "cubre toda la cadena: importación Star-DT / StaR-Elec (DT-DICT), "
              "mapas base IGN/BAN/PCI cargados en segundo plano y exportación "
              "GeoPackage conforme al geoestándar StaR-Eau V2024 (CNIG/ASTEE).",
        'pt': "CanaPlan é uma ferramenta de desenho de projeto que permite "
              "traçar redes de saneamento de águas residuais (EU) e águas "
              "pluviais (EP) diretamente no QGIS, sobre um mapa base que o "
              "próprio módulo carrega (BAN, cadastro PCI, ortofoto IGN, OSM ou "
              "uma planta DXF/DWG existente), com continuidade geométrica "
              "nativa: cada conduta liga duas estruturas e cada ramal "
              "reajusta-se automaticamente à sua conduta principal quando esta "
              "se desloca.\n\n"
              "A ferramenta produz perfis longitudinais (EU/EP/agrupados), "
              "calcula os volumes de cubagem (escavação e materiais de aterro "
              "aplicados), gera cortes transversais de vala, imprime as plantas "
              "em PDF multifolha com planta de conjunto e exporta em DXF 2018 "
              "fiel.\n\n"
              "Do levantamento de campo à entrega, uma só ferramenta cobre toda "
              "a cadeia: importação Star-DT / StaR-Elec (DT-DICT), mapas base "
              "IGN/BAN/PCI carregados em segundo plano e exportação GeoPackage "
              "conforme ao geopadrão StaR-Eau V2024 (CNIG/ASTEE).",
        'de': "CanaPlan ist ein Entwurfswerkzeug zum Zeichnen von "
              "Schmutzwasser- (EU) und Regenwasserkanalnetzen (EP) direkt in "
              "QGIS, über einer Hintergrundkarte, die die Erweiterung selbst "
              "lädt (BAN, PCI-Kataster, IGN-Orthofoto, OSM oder eine vorhandene "
              "DXF/DWG-Zeichnung), mit nativer geometrischer Kontinuität: Jede "
              "Leitung verbindet zwei Bauwerke, und jeder Hausanschluss richtet "
              "sich automatisch neu an seiner Hauptleitung aus, wenn diese "
              "verschoben wird.\n\n"
              "Das Werkzeug erzeugt Längsschnitte (EU/EP/kombiniert), berechnet "
              "die Massen (Aushub und eingebaute Verfüllmaterialien), erstellt "
              "Grabenquerschnitte, druckt mehrblättrige PDF-Pläne mit "
              "Übersichtsplan und exportiert originalgetreues DXF 2018.\n\n"
              "Von der Feldaufnahme bis zur Übergabe deckt ein einziges "
              "Werkzeug die gesamte Kette ab: Star-DT- / StaR-Elec-Import "
              "(DT-DICT), im Hintergrund geladene IGN/BAN/PCI-Hintergrundkarten "
              "und GeoPackage-Export konform zum Geostandard StaR-Eau V2024 "
              "(CNIG/ASTEE).",
    },
    'ab_version': {
        'fr': "version {version}", 'en': "version {version}",
        'es': "versión {version}", 'pt': "versão {version}",
        'de': "Version {version}",
    },
    'cb_total_ligne': {
        'fr': "{nb} élément(s)  —  Surf. ouv. totale : {surface} m²  —  "
              "Déblai total : {deblai} m³",
        'en': "{nb} item(s)  —  Total open area: {surface} m²  —  "
              "Total excavation: {deblai} m³",
        'es': "{nb} elemento(s)  —  Sup. abierta total: {surface} m²  —  "
              "Desmonte total: {deblai} m³",
        'pt': "{nb} elemento(s)  —  Sup. aberta total: {surface} m²  —  "
              "Escavação total: {deblai} m³",
        'de': "{nb} Element(e)  —  Offene Fläche gesamt: {surface} m²  —  "
              "Aushub gesamt: {deblai} m³",
    },
}
