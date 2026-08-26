import os
from qgis.PyQt.QtCore import QObject, QSettings, Qt, QVariant
from qgis.PyQt.QtGui import QIcon, QColor
from qgis.PyQt.QtWidgets import QAction, QActionGroup, QMenu, QMessageBox
from qgis.core import (
    QgsProject, QgsVectorLayer, QgsField, QgsWkbTypes,
    QgsSymbol, QgsSimpleLineSymbolLayer, QgsSimpleMarkerSymbolLayer,
    QgsSingleSymbolRenderer, QgsLayerTreeGroup,
    QgsProperty, QgsSymbolLayer, QgsUnitTypes,
)

from .tools import i18n

SKETCHES_PREFIX = "CanaPlan/"

class ReseauAssainissementPlugin(QObject):
    def __init__(self, iface):
        super().__init__()
        self.iface = iface
        self.plugin_dir = os.path.dirname(__file__)
        self.actions = []
        self.action_dict = {}
        self.tools = {}  # pour garder réf aux map tools

        # Translator (optionnel, désactivé pour l'instant)
        # self.translator = QTranslator()
        # locale = QSettings().value('locale/userLocale', 'fr_FR')[0:2]
        # self.translator.load(os.path.join(self.plugin_dir, 'i18n', f'reseau_{locale}.qm'))
        # QCoreApplication.installTranslator(self.translator)

    def initGui(self):
        """Création de la barre d'outils et des actions."""
        # Purge des GeoJSON temporaires (fonds WFS) des sessions précédentes
        try:
            from .tools.wfs_utils import purge_temp_dir
            purge_temp_dir()
        except Exception:
            pass


        # Groupe pour les outils de dessin (non exclusif pour permettre le toggle)
        self.tool_group = QActionGroup(self.iface.mainWindow())
        self.tool_group.setExclusive(False)

        # Actions
        self.action_dict['conduite_eu'] = self._add_action(
            "conduite_eu.svg",
            "Dessiner une conduite EU",
            self.run_conduite_eu,
            checkable=True
        )
        self.action_dict['conduite_ep'] = self._add_action(
            "conduite_ep.svg",
            "Dessiner une conduite EP",
            self.run_conduite_ep,
            checkable=True
        )
        self.action_dict['branchement_eu'] = self._add_action(
            "branchement_eu.svg",
            "Dessiner un branchement EU",
            self.run_branchement_eu,
            checkable=True
        )
        self.action_dict['branchement_ep'] = self._add_action(
            "branchement_ep.svg",
            "Dessiner un branchement EP",
            self.run_branchement_ep,
            checkable=True
        )
        self.action_dict['renseignement'] = self._add_action(
            "renseignement.svg",
            "Renseigner un élément",
            self.run_renseignement,
            checkable=True
        )
        self.action_dict['insert_regard'] = self._add_action(
            "insert_regard.svg",
            "Insérer un regard sur conduite",
            self.run_insert_regard,
            checkable=True
        )
        self.action_dict['delete'] = self._add_action(
            "delete.svg",
            "Effacer un élément",
            self.run_delete,
            checkable=True
        )
        self.action_dict['move'] = self._add_action(
            "move.svg",
            "Déplacer un ouvrage",
            self.run_move,
            checkable=True
        )
        self.action_dict['copy_attributes'] = self._add_action(
            "copy_attrib.svg",
            "Copier les attributs",
            self.run_copy_attributes,
            checkable=True
        )
        self.action_dict['profil_eu'] = self._add_action(
            "profil.svg",
            "Profil en long EU",
            self.run_profil_eu,
            checkable=True
        )
        self.action_dict['coupe_eu'] = self._add_action(
            "profil.svg",
            "Coupe transversale EU",
            self.run_coupe_eu,
            checkable=True
        )
        self.action_dict['profil_ep'] = self._add_action(
            "profil.svg",
            "Profil en long EP",
            self.run_profil_ep,
            checkable=True
        )
        self.action_dict['coupe_ep'] = self._add_action(
            "profil.svg",
            "Coupe transversale EP",
            self.run_coupe_ep,
            checkable=True
        )
        self.action_dict['renommer_eu'] = self._add_action(
            "renommer.svg",
            "Renuméroter regards/tabourets EU",
            self.run_renommer_eu,
            checkable=True
        )
        self.action_dict['renommer_ep'] = self._add_action(
            "renommer.svg",
            "Renuméroter regards/tabourets EP",
            self.run_renommer_ep,
            checkable=True
        )
        self.action_dict['profil_groupe'] = self._add_action(
            "profil.svg",
            "Profil groupé EU + EP",
            self.run_profil_groupe,
            checkable=True
        )
        self.action_dict['coupe_transversale'] = self._add_action(
            "profil.svg",
            "Coupe transversale des tranchées",
            self.run_coupe_transversale,
            checkable=True
        )
        self.action_dict['cubature'] = self._add_action(
            "config.svg",
            "Cubature / Remblai tranchées",
            self.run_cubature,
            checkable=True
        )
        self.action_dict['coupe_tranchee_composee'] = self._add_action(
            "profil.svg",
            "Dessinateur – Coupe de tranchées composée",
            self.run_coupe_tranchee_composee,
            checkable=False
        )
        self.action_dict['creer_etiquettes'] = self._add_action(
            "etiquettes.svg",
            "Créer les étiquettes",
            self.creer_etiquettes,
            checkable=False
        )
        self.action_dict['afficher_etiquettes'] = self._add_action(
            "etiquettes_toggle.svg",
            "Afficher / Masquer les étiquettes",
            self.toggle_affichage_etiquettes,
            checkable=True
        )
        self.action_dict['taille_etiquettes'] = self._add_action(
            "etiquettes.svg",
            "Taille des étiquettes",
            self.run_taille_etiquettes,
            checkable=False
        )
        self.action_dict['forcer_etiquettes'] = self._add_action(
            "etiquettes_toggle.svg",
            "Forcer toutes les étiquettes visibles (décalage auto)",
            self.run_forcer_etiquettes,
            checkable=True
        )
        self.action_dict['affichage_etiquettes'] = self._add_action(
            "etiquettes.svg",
            "Gestion de l'affichage des étiquettes",
            self.run_affichage_etiquettes,
            checkable=False
        )
        self.action_dict['annotation'] = self._add_action(
            "etiquettes.svg",
            "Placer une annotation texte",
            self.run_annotation,
            checkable=True
        )
        for key, label, cb in [
            ('nouveau_projet_assistant', "Créer un projet avec l'assistant", self.run_nouveau_projet_assistant),
            ('fond_projet',            'Mise en place fond de projet',  self.run_fond_projet),
            ('enregistrer_projet_sous','Enregistrer sous',              self.run_enregistrer_projet_sous),
            ('ban_vecteur',            'BAN Adresses',        self.run_ban_vecteur),
            ('nom_voie',               'Noms de rue BD TOPO (emprise)', self.run_nom_voie),
        ]:
            self.action_dict[key] = self._add_action(
                "config.svg", label, cb, checkable=False)

        self.action_dict['pci_parcelles'] = self._add_action(
            "config.svg",
            "PCI Vecteur Parcelles",
            self.run_pci_parcelles,
            checkable=False
        )
        self.action_dict['pci_bati'] = self._add_action(
            "config.svg",
            "PCI Vecteur Bâti",
            self.run_pci_bati,
            checkable=False
        )
        self.action_dict['ortho_ign'] = self._add_action(
            "config.svg",
            "Ortho IGN (BD ORTHO nationale)",
            self.run_ortho_ign,
            checkable=False
        )
        self.action_dict['osm_desature'] = self._add_action(
            "config.svg",
            "OSM Desature",
            self.run_osm_desature,
            checkable=False
        )
        self.action_dict['enregistrer_projet'] = self._add_action(
            "config.svg",
            "Enregistrer le projet",
            self.run_enregistrer_projet,
            checkable=False
        )
        self.action_dict['projets_recents'] = self._add_action(
            "config.svg",
            "Projets récents…",
            self.run_projets_recents,
            checkable=False
        )
        self.action_dict['charger_projet'] = self._add_action(
            "config.svg",
            "Charger un projet",
            self.run_charger_projet,
            checkable=False
        )
        self.action_dict['imprimer'] = self._add_action(
            "config.svg",
            "Imprimer / Exporter PDF/DXF",
            self.run_imprimer,
            checkable=False
        )
        self.action_dict['import_dxf'] = self._add_action(
            "config.svg",
            "Importer DXF / DWG",
            self.run_import_dxf,
            checkable=False
        )
        self.action_dict['import_star_dt'] = self._add_action(
            "config.svg",
            "Importer Star-DT (GML)",
            self.run_import_star_dt,
            checkable=False
        )

        self.action_dict['export_stareau'] = self._add_action(
            "config.svg",
            "Exporter au format StaR-Eau",
            self.run_export_stareau,
            checkable=False
        )

        self.action_dict['tableau_saisie'] = self._add_action(
            "config.svg",
            "Tableau de saisie - pente",
            self.show_tableau_saisie,
            checkable=False
        )

        self.action_dict['config'] = self._add_action(
            "config.svg",
            "Configurer les couches",
            self.show_config_dialog,
            checkable=False
        )

        # Ajouter aussi dans le menu, organisé par catégories (même
        # regroupement que le panneau latéral)
        self.menu = self.iface.pluginMenu().addMenu("CanaPlan")

        # Bascule affichage/masquage du panneau latéral : c'est la seule
        # interface du plugin, il faut pouvoir le rouvrir après fermeture.
        # L'action est créée après le panneau, en fin d'initGui.
        self.menu.addSeparator()

        menu_groups = [
            ('grp_projet', ['nouveau_projet_assistant', 'projets_recents', 'enregistrer_projet', 'enregistrer_projet_sous', 'charger_projet', 'import_dxf', 'import_star_dt']),
            ('grp_general', ['renseignement', 'tableau_saisie', 'insert_regard', 'move', 'copy_attributes', 'delete', 'config']),
            ('grp_eu', ['conduite_eu', 'branchement_eu', 'profil_eu', 'coupe_eu', 'renommer_eu']),
            ('grp_ep', ['conduite_ep', 'branchement_ep', 'profil_ep', 'coupe_ep', 'renommer_ep']),
            ('grp_etiquettes', ['creer_etiquettes', 'afficher_etiquettes', 'taille_etiquettes', 'forcer_etiquettes', 'affichage_etiquettes', 'annotation']),
            ('grp_sorties', ['imprimer', 'profil_groupe', 'coupe_transversale', 'cubature', 'coupe_tranchee_composee', 'export_stareau']),
            ('grp_fond', ['fond_projet', 'osm_desature', 'ortho_ign', 'pci_parcelles', 'pci_bati', 'ban_vecteur', 'nom_voie']),
        ]
        self.submenus = []
        # (sous-menu, clé i18n) : le titre est reposé à chaque changement de langue
        self._submenus_i18n = []
        for cle_titre, keys in menu_groups:
            submenu = self.menu.addMenu(i18n.tr(cle_titre))
            for key in keys:
                action = self.action_dict.get(key)
                if action is not None:
                    submenu.addAction(action)
            self.submenus.append(submenu)
            self._submenus_i18n.append((submenu, cle_titre))

        # « À propos » est ajouté au menu après le sous-menu Langue, pour
        # rester la toute dernière entrée de la liste.
        self.action_dict['about'] = self._add_action(
            "config.svg",
            "À propos",
            self.show_about_dialog,
            checkable=False,
            add_to_toolbar=False,
        )

        # Synchronise le bouton avec l'état actuel du moteur d'étiquettes
        from .gui.etiquettes import get_force_all_labels
        action_force = self.action_dict.get('forcer_etiquettes')
        if action_force is not None:
            action_force.blockSignals(True)
            action_force.setChecked(get_force_all_labels())
            action_force.blockSignals(False)

        # Panneau latéral
        from .gui.side_panel import SidePanel
        self.side_panel = SidePanel(self, self.iface.mainWindow())
        self.iface.addDockWidget(Qt.DockWidgetArea.LeftDockWidgetArea, self.side_panel)

        # Unique icône du plugin, dans la barre d'outils Extensions de QGIS :
        # elle allume et éteint le panneau latéral. toggleViewAction() est
        # déjà cochable et Qt la garde synchronisée avec l'état réel du dock,
        # y compris quand l'utilisateur ferme le panneau par sa croix.
        toggle_panel = self.side_panel.toggleViewAction()
        toggle_panel.setText(i18n.tr('toggle_panel'))
        toggle_panel.setIcon(
            QIcon(os.path.join(self.plugin_dir, "icon", "icon.png")))
        toggle_panel.setToolTip(i18n.tr('toggle_panel_tip'))
        self.action_dict['toggle_panel'] = toggle_panel
        self.menu.insertAction(self.menu.actions()[0], toggle_panel)
        self.iface.addToolBarIcon(toggle_panel)

        self._build_language_menu()

        self.menu.addSeparator()
        self.menu.addAction(self.action_dict['about'])

        i18n.signaux.langue_changee.connect(self._retranslate)
        self._retranslate()

    def _build_language_menu(self):
        """Sous-menu Langue : cases à cocher exclusives, 'auto' en tête."""
        self.menu_langue = QMenu(i18n.tr('langue'), self.menu)
        self.menu.addMenu(self.menu_langue)
        self._groupe_langue = QActionGroup(self.menu_langue)
        self._groupe_langue.setExclusive(True)
        self._actions_langue = []
        courante = i18n.preference()
        for code, _libelle in i18n.CHOIX:
            action = self.menu_langue.addAction(i18n.libelle_choix(code))
            action.setCheckable(True)
            action.setChecked(code == courante)
            self._groupe_langue.addAction(action)
            action.triggered.connect(
                lambda _checked=False, c=code: i18n.definir(c))
            self._actions_langue.append((action, code))

    def _retranslate(self, *_args):
        """Repose tous les libellés dans la langue courante.

        Appelé en fin d'initGui et à chaque changement de langue. Les clés
        i18n portent le même nom que les clés de action_dict ; une action sans
        traduction garde le libellé français écrit dans le code.
        """
        for cle, action in self.action_dict.items():
            if cle in i18n.TR:
                action.setText(i18n.tr(cle))
        self.action_dict['toggle_panel'].setToolTip(i18n.tr('toggle_panel_tip'))
        for submenu, cle_titre in self._submenus_i18n:
            submenu.setTitle(i18n.tr(cle_titre))
        self.menu_langue.setTitle(i18n.tr('langue'))
        for action, code in self._actions_langue:
            action.setText(i18n.libelle_choix(code))
            action.setChecked(code == i18n.preference())
        panel = getattr(self, 'side_panel', None)
        if panel is not None:
            panel.retranslate()

    def unload(self):
        """Supprime la barre d'outils, les actions et les rubber bands."""
        import sip
        self._cleanup_tools()
        from .tools.projet_bet import cleanup_plugin_resources
        cleanup_plugin_resources(self)
        # Le dialogue StaR-Eau est non modal : il survivrait au rechargement
        # du plugin s'il n'etait pas ferme explicitement.
        dlg = getattr(self, '_stareau_dlg', None)
        if dlg is not None and not sip.isdeleted(dlg):
            dlg.close()
            dlg.deleteLater()
        self._stareau_dlg = None
        try:
            i18n.signaux.langue_changee.disconnect(self._retranslate)
        except (TypeError, RuntimeError):
            pass                       # jamais connecté, ou déjà détruit
        toggle_panel = self.action_dict.get('toggle_panel')
        if toggle_panel is not None:
            self.iface.removeToolBarIcon(toggle_panel)
        self.iface.removeDockWidget(self.side_panel)
        self.side_panel.deleteLater()
        for action in self.actions:
            self.iface.removePluginMenu("CanaPlan", action)
        self.actions.clear()
        # Suppression synchrone (sip.delete) pour éviter le warning de
        # widget dupliqué au rechargement : deleteLater() est asynchrone et
        # laisse l'ancien menu vivant quand le nouveau initGui s'exécute.
        try:
            if self.menu is not None and not sip.isdeleted(self.menu):
                sip.delete(self.menu)
        except Exception:
            pass
        self.menu = None

    def _cleanup_tools(self):
        """Nettoie tous les rubber bands des outils actifs."""
        for tool in self.tools.values():
            if tool is not None:
                tool.deactivate()
        self.tools.clear()
        self.iface.mapCanvas().refresh()

    def _add_action(self, icon_name, text, callback, checkable=False,
                    add_to_toolbar=False):
        """Crée une action du plugin, référencée par le menu et le panneau.

        add_to_toolbar est conservé pour ne pas casser les appels existants :
        le plugin n'a plus de barre d'outils, le paramètre est sans effet.
        """
        icon_path = os.path.join(self.plugin_dir, "icon", icon_name)
        action = QAction(QIcon(icon_path), text, self.iface.mainWindow())
        action.setCheckable(checkable)
        if checkable:
            action.toggled.connect(callback)
            self.tool_group.addAction(action)
        else:
            action.triggered.connect(callback)
        self.actions.append(action)
        return action

    def show_about_dialog(self):
        from .gui.about_dialog import AboutDialog
        dlg = AboutDialog(self.plugin_dir, self.iface.mainWindow())
        dlg.exec_()

    # --- Définition des champs par type de couche ---

    LAYER_DEFINITIONS = {
        'conduite': {
            'geom': 'LineString',
            'fields': [
                ('diametre', QVariant.Double, 'Diamètre (mm)'),
                ('materiau', QVariant.String, 'Matériau'),
                ('longueur', QVariant.Double, 'Longueur (m)'),
                ('pente', QVariant.Double, 'Pente (%)'),
            ],
        },
        'branchement': {
            'geom': 'LineString',
            'fields': [
                ('id_conduite',   QVariant.Int,    'ID conduite'),
                ('pk_debut',      QVariant.Double, 'PK piquage'),
                ('cote_piquage',  QVariant.Double, 'Cote piquage (m NGF)'),
                ('diametre',      QVariant.Double, 'Diamètre (mm)'),
                ('materiau',      QVariant.String, 'Matériau'),
                ('longueur',      QVariant.Double, 'Longueur (m)'),
                ('pente',         QVariant.Double, 'Pente (%)'),
                ('sens',          QVariant.String, 'Sens'),
            ],
        },
        'regard': {
            'geom': 'Point',
            'fields': [
                ('nom', QVariant.String, 'Nom'),
                ('tn', QVariant.Double, 'TN (m)'),
                ('fe_radier', QVariant.Double, 'FE radier (m)'),
                ('diametre', QVariant.Double, 'Diamètre (mm)'),
                ('profondeur', QVariant.Double, 'Profondeur (m)'),
            ],
        },
        'tabouret': {
            'geom': 'Point',
            'fields': [
                ('nom', QVariant.String, 'Nom'),
                ('tn', QVariant.Double, 'TN (m)'),
                ('fe_entree', QVariant.Double, 'FE entrée (m)'),
                ('diametre', QVariant.Double, 'Diamètre (mm)'),
                ('profondeur', QVariant.Double, 'Profondeur (m)'),
            ],
        },
    }

    # --- Accueil projet ---

    def _ensure_project_loaded(self):
        """Affiche le dialog d'accueil si aucun projet BET n'est actif."""
        from .tools.projet_bet import project_dir
        if project_dir():
            return
        from .tools.layer_keys import get_layer_id
        for reseau in ('eu', 'ep'):
            if get_layer_id('conduite', reseau):
                return
        from .gui.welcome_dialog import WelcomeDialog
        dlg = WelcomeDialog(self.iface.mainWindow())
        dlg.exec_()
        choice = dlg.chosen()
        if choice == WelcomeDialog.NEW:
            self.run_nouveau_projet_assistant()
        elif choice == WelcomeDialog.OPEN:
            from .tools.projet_bet import load_projet
            load_projet(self, self.iface)

    # --- Dispatchers outils carte ---

    def _run_tool_single(self, checked, key, reseau, ToolClass, needs_iface=False):
        """Active un outil à réseau unique (EU ou EP)."""
        if not checked:
            self._deactivate_current()
            return
        self._ensure_project_loaded()
        couches = self._get_couches(reseau)
        if not couches:
            return
        canvas = self.iface.mapCanvas()
        tool = (ToolClass(canvas, self.iface, reseau, couches)
                if needs_iface else
                ToolClass(canvas, reseau=reseau, couches=couches))
        self._activate_tool(key, tool)

    def _run_tool_dual(self, checked, key, ToolClass, needs_iface=False):
        """Active un outil qui opère sur EU et EP simultanément."""
        if not checked:
            self._deactivate_current()
            return
        self._ensure_project_loaded()
        couches_eu = self._get_couches("EU")
        couches_ep = self._get_couches("EP")
        if not couches_eu or not couches_ep:
            return
        canvas = self.iface.mapCanvas()
        tool = (ToolClass(canvas, self.iface, couches_eu, couches_ep)
                if needs_iface else
                ToolClass(canvas, couches_eu=couches_eu, couches_ep=couches_ep))
        self._activate_tool(key, tool)

    # --- Résolution des couches (avec auto-création) ---

    def _get_couches(self, reseau):
        """Récupère les couches configurées pour le réseau donné (EU ou EP).
        Si une couche n'existe pas ou n'est pas configurée, elle est créée
        automatiquement comme couche mémoire et enregistrée dans la config.
        Retourne un dict {'conduite', 'branchement', 'regard', 'tabouret'}.
        """
        from .tools.layer_keys import get_layer_id, set_layer_id
        project = QgsProject.instance()
        couches = {}

        for role in ('conduite', 'branchement', 'regard', 'tabouret'):
            layer_id = get_layer_id(role, reseau)
            layer = project.mapLayer(layer_id) if layer_id else None

            if not layer:
                layer = self._create_layer(role, reseau)
                project.addMapLayer(layer, False)
                self._get_or_create_group(reseau).addLayer(layer)
                set_layer_id(role, reseau, layer.id())
            else:
                self._ensure_fields(layer, role)

            couches[role] = layer

        return couches

    def _get_or_create_group(self, reseau):
        """Retourne le groupe EU ou EP (le crée en tête de légende si absent)."""
        root = QgsProject.instance().layerTreeRoot()
        group = root.findGroup(reseau)
        if group is None:
            group = root.insertGroup(0, reseau)
        return group

    def _ensure_fields(self, layer, role):
        """Ajoute à la couche les champs manquants définis dans LAYER_DEFINITIONS."""
        defn = self.LAYER_DEFINITIONS.get(role)
        if not defn:
            return
        existing = {f.name() for f in layer.fields()}
        to_add = []
        for field_name, field_type, alias in defn['fields']:
            if field_name not in existing:
                f = QgsField(field_name, field_type)
                f.setAlias(alias)
                to_add.append(f)
        if not to_add:
            return
        dp = layer.dataProvider()
        dp.addAttributes(to_add)
        layer.updateFields()

    # --- Couleurs par réseau ---
    COLORS = {
        'EU': QColor(255, 0, 0),    # rouge
        'EP': QColor(0, 0, 255),    # bleu
    }

    def _create_layer(self, role, reseau):
        """Crée une couche mémoire pour le rôle et le réseau donnés,
        avec la symbologie appropriée."""
        defn = self.LAYER_DEFINITIONS[role]
        crs = QgsProject.instance().crs()
        crs_str = crs.authid() if crs.isValid() else "EPSG:2154"

        uri = f"{defn['geom']}?crs={crs_str}"
        name = f"{role}_{reseau}"
        layer = QgsVectorLayer(uri, name, "memory")

        dp = layer.dataProvider()
        fields = []
        for field_name, field_type, alias in defn['fields']:
            f = QgsField(field_name, field_type)
            f.setAlias(alias)
            fields.append(f)
        dp.addAttributes(fields)
        layer.updateFields()

        self._apply_style(layer, role, reseau)
        return layer

    def _apply_style(self, layer, role, reseau):
        """Applique la symbologie selon le role et le reseau."""
        color = self.COLORS[reseau]

        if role in ('conduite', 'branchement'):
            # Epaisseur proportionnelle au diametre (mm -> m)
            symbol = QgsSymbol.defaultSymbol(QgsWkbTypes.LineGeometry)
            sl = QgsSimpleLineSymbolLayer(color)
            sl.setWidthUnit(QgsUnitTypes.RenderMapUnits)
            sl.setDataDefinedProperty(
                QgsSymbolLayer.PropertyStrokeWidth,
                QgsProperty.fromExpression('coalesce("diametre", 200) / 1000'))
            symbol.changeSymbolLayer(0, sl)

        elif role == 'regard':
            # Cercle de 1m de diametre en unites carte
            symbol = QgsSymbol.defaultSymbol(QgsWkbTypes.PointGeometry)
            ml = QgsSimpleMarkerSymbolLayer(QgsSimpleMarkerSymbolLayer.Circle, 1.0)
            ml.setColor(color)
            ml.setStrokeColor(color)
            ml.setSizeUnit(QgsUnitTypes.RenderMapUnits)
            symbol.changeSymbolLayer(0, ml)

        elif role == 'tabouret':
            # Carre de 0.4m x 0.4m en unites carte
            symbol = QgsSymbol.defaultSymbol(QgsWkbTypes.PointGeometry)
            ml = QgsSimpleMarkerSymbolLayer(QgsSimpleMarkerSymbolLayer.Square, 0.4)
            ml.setColor(color)
            ml.setStrokeColor(color)
            ml.setSizeUnit(QgsUnitTypes.RenderMapUnits)
            symbol.changeSymbolLayer(0, ml)

        else:
            return

        renderer = QgsSingleSymbolRenderer(symbol)
        layer.setRenderer(renderer)
        layer.triggerRepaint()

    # --- Méthodes pour les outils ---

    def _activate_tool(self, key, tool):
        """Active un outil en nettoyant l'ancien et décochant les autres boutons."""
        self._cleanup_tools()
        # Décocher tous les autres boutons sans déclencher leur signal
        sender = self.sender() if hasattr(self, 'sender') else None
        for action in self.tool_group.actions():
            if action is not sender and action.isChecked():
                action.blockSignals(True)
                action.setChecked(False)
                action.blockSignals(False)
        canvas = self.iface.mapCanvas()
        canvas.setMapTool(tool)
        self.tools[key] = tool

    def _deactivate_current(self):
        """Désactive l'outil courant et revient au mode navigation."""
        self._cleanup_tools()
        self.iface.mapCanvas().unsetMapTool(
            self.iface.mapCanvas().mapTool())

    def run_conduite_eu(self, checked):
        from .tools.draw_conduite_tool import DrawConduiteTool
        self._run_tool_single(checked, "conduite_eu", "EU", DrawConduiteTool)

    def run_conduite_ep(self, checked):
        from .tools.draw_conduite_tool import DrawConduiteTool
        self._run_tool_single(checked, "conduite_ep", "EP", DrawConduiteTool)

    def run_branchement_eu(self, checked):
        from .tools.draw_branchement_tool import DrawBranchementTool
        self._run_tool_single(checked, "branchement_eu", "EU", DrawBranchementTool)

    def run_branchement_ep(self, checked):
        from .tools.draw_branchement_tool import DrawBranchementTool
        self._run_tool_single(checked, "branchement_ep", "EP", DrawBranchementTool)

    def run_renseignement(self, checked):
        from .tools.renseignement_tool import RenseignementTool
        self._run_tool_dual(checked, "renseignement", RenseignementTool)

    def run_insert_regard(self, checked):
        from .tools.insert_regard_tool import InsertRegardTool
        self._run_tool_dual(checked, "insert_regard", InsertRegardTool)

    def run_delete(self, checked):
        from .tools.delete_tool import DeleteTool
        self._run_tool_dual(checked, "delete", DeleteTool)

    def run_move(self, checked):
        from .tools.move_tool import MoveTool
        self._run_tool_dual(checked, "move", MoveTool)

    def run_copy_attributes(self, checked):
        from .tools.copy_attributes_tool import CopyAttributesTool
        self._run_tool_dual(checked, "copy_attributes", CopyAttributesTool)

    def run_profil_eu(self, checked):
        from .tools.profil_tool import ProfilTool
        self._run_tool_single(checked, "profil_eu", "EU", ProfilTool, needs_iface=True)

    def run_profil_ep(self, checked):
        from .tools.profil_tool import ProfilTool
        self._run_tool_single(checked, "profil_ep", "EP", ProfilTool, needs_iface=True)

    def run_renommer_eu(self, checked):
        from .tools.renommer_tool import RenommerTool
        self._run_tool_single(checked, "renommer_eu", "EU", RenommerTool, needs_iface=True)

    def run_renommer_ep(self, checked):
        from .tools.renommer_tool import RenommerTool
        self._run_tool_single(checked, "renommer_ep", "EP", RenommerTool, needs_iface=True)

    def run_profil_groupe(self, checked):
        from .tools.profil_groupe_tool import ProfilGroupeTool
        self._run_tool_dual(checked, "profil_groupe", ProfilGroupeTool, needs_iface=True)

    def run_coupe_transversale(self, checked):
        from .tools.coupe_transversale_tool import CoupeTransversaleTool
        self._run_tool_dual(checked, "coupe_transversale", CoupeTransversaleTool, needs_iface=True)

    def run_coupe_eu(self, checked):
        from .tools.coupe_transversale_tool import CoupeTransversaleSingleTool
        self._run_tool_single(checked, "coupe_eu", "EU", CoupeTransversaleSingleTool, needs_iface=True)

    def run_coupe_ep(self, checked):
        from .tools.coupe_transversale_tool import CoupeTransversaleSingleTool
        self._run_tool_single(checked, "coupe_ep", "EP", CoupeTransversaleSingleTool, needs_iface=True)

    def run_cubature(self, checked):
        key = 'cubature'
        if not checked:
            self._deactivate_current()
            return
        from .gui.cubature_dialog import CubatureOptionsDialog, CubatureDialog
        from .config_dialog import get_cubature_config
        from .tools.calc_cubature import calculer_cubature_reseau

        dlg = CubatureOptionsDialog(self.iface.mainWindow())
        if dlg.exec_() != dlg.Accepted:
            self.action_dict[key].setChecked(False)
            return
        opts = dlg.options()
        config = get_cubature_config()

        if opts['bfs'] or opts['axe']:
            couches_eu = self._get_couches("EU")
            couches_ep = self._get_couches("EP")
            if not couches_eu or not couches_ep:
                self.action_dict[key].setChecked(False)
                return
            from .tools.cubature_tool import CubatureTool
            tool = CubatureTool(self.iface.mapCanvas(), self.iface,
                                couches_eu, couches_ep, opts)
            self._activate_tool(key, tool)
        else:
            # Calcul direct sans outil carte
            all_results = []
            reseaux = []
            if opts['perimetre'] in ('tout', 'EU'):
                reseaux.append(('EU', self._get_couches("EU")))
            if opts['perimetre'] in ('tout', 'EP'):
                reseaux.append(('EP', self._get_couches("EP")))

            for reseau, couches in reseaux:
                if not couches:
                    continue
                results = calculer_cubature_reseau(couches, config, reseau)
                if not opts['conduites']:
                    results = [r for r in results if r.get('type') != 'Conduite']
                if not opts['branchements']:
                    results = [r for r in results if r.get('type') != 'Branchement']
                all_results.extend(results)

            if not all_results:
                self.action_dict[key].setChecked(False)
                from qgis.PyQt.QtWidgets import QMessageBox
                QMessageBox.information(
                    None, i18n.tr('msg_cubature_titre'),
                    i18n.tr('msg_aucun_element'))
                return

            dlg_result = CubatureDialog(all_results, config, self.iface.mainWindow())
            dlg_result.show()
            self.action_dict[key].setChecked(False)

    def run_coupe_tranchee_composee(self):
        from .gui.coupe_tranchee_composee_dialog import CoupeTrancheeComposeeDialog
        dlg = CoupeTrancheeComposeeDialog(self.iface.mainWindow())
        dlg.show()

    def creer_etiquettes(self):
        """Configure le moteur d'étiquettes sur toutes les couches."""
        from .gui.etiquettes import apply_etiquettes, apply_label_size_all
        from .tools.calc_pentes import recalc_pentes
        from .tools.projet_bet import _read_label_size
        from qgis.PyQt.QtCore import QSettings

        # Mémorise la taille courante avant de tout recréer
        label_size = _read_label_size(QgsProject.instance(), QSettings())

        for reseau in ("EU", "EP"):
            couches = self._get_couches(reseau)
            recalc_pentes(couches['conduite'], couches['regard'],
                          branchement_layer=couches['branchement'],
                          tabouret_layer=couches['tabouret'])
            for role in ("regard", "tabouret", "conduite", "branchement"):
                self._apply_style(couches[role], role, reseau)
                apply_etiquettes(couches[role], role, reseau)

        # Réapplique la taille mémorisée (et le seuil de dézoom qui va avec)
        if label_size:
            apply_label_size_all(self, label_size['unit'], label_size['value'],
                                 label_size.get('min_scale'))

        # Réapplique la gestion d'affichage (visibilité + champs)
        from .gui.etiquettes import apply_label_display_prefs, apply_label_fields
        from .gui.etiquette_affichage_dialog import prefs_from_dict
        stored = getattr(self, '_label_display_prefs', None)
        if stored:
            full = prefs_from_dict(stored)
            apply_label_display_prefs(self, full['visibility'])
            if full.get('fields'):
                apply_label_fields(self, full['fields'])

        toggle = self.action_dict.get('afficher_etiquettes')
        if toggle is not None:
            toggle.blockSignals(True)
            toggle.setChecked(True)
            toggle.blockSignals(False)

    def run_affichage_etiquettes(self):
        from .gui.etiquette_affichage_dialog import EtiquetteAffichageDialog, prefs_from_dict
        from .gui.etiquettes import (apply_label_display_prefs,
                                      apply_label_fields, get_label_display_prefs)
        current_vis = get_label_display_prefs(self)
        # Récupère les prefs stockées en mémoire (fields) si disponibles
        stored = getattr(self, '_label_display_prefs', None) or {}
        prefs = prefs_from_dict(stored) if stored else prefs_from_dict({'visibility': current_vis})
        # Synchronise la visibilité courante réelle
        for reseau in ('EU', 'EP'):
            for role in ('regard', 'tabouret', 'conduite', 'branchement'):
                prefs['visibility'][reseau][role] = current_vis.get(reseau, {}).get(role, True)

        dlg = EtiquetteAffichageDialog(prefs=prefs, parent=self.iface.mainWindow())
        if dlg.exec_() != EtiquetteAffichageDialog.Accepted:
            return
        new_prefs = dlg.get_prefs()
        self._label_display_prefs = new_prefs
        apply_label_display_prefs(self, new_prefs['visibility'])
        apply_label_fields(self, new_prefs['fields'])
        self.iface.mapCanvas().refresh()

    def run_annotation(self, checked):
        if not checked:
            self._deactivate_current()
            return
        from .tools.annotation_tool import AnnotationTool
        tool = AnnotationTool(self.iface.mapCanvas(), self.iface)
        self._activate_tool("annotation", tool)

    def run_forcer_etiquettes(self, checked):
        from .gui.etiquettes import set_force_all_labels
        # plugin= : le forçage est posé couche par couche sur les seules
        # couches EU/EP, et non sur le moteur d'étiquettes du projet — sinon
        # les fonds BAN, noms de rue et PCI sont forcés eux aussi.
        set_force_all_labels(checked, self.iface.mapCanvas(), plugin=self)

    def run_taille_etiquettes(self):
        from .gui.etiquette_taille_dialog import EtiquetteTailleDialog
        from .gui.etiquettes import apply_label_size_all
        from qgis.PyQt.QtCore import QSettings
        from .gui.etiquettes import get_label_min_scale
        s          = QSettings()
        last_mode  = s.value("CanaPlan/label_size_mode",  "map_units")
        last_value = s.value("CanaPlan/label_size_value", None)
        if last_value is not None:
            try:
                last_value = float(last_value)
            except (ValueError, TypeError):
                last_value = None
        # Le seuil est lu sur les couches, pas dans QSettings : c'est une
        # propriété du projet ouvert, pas une préférence utilisateur.
        last_scale = get_label_min_scale(self)
        dlg = EtiquetteTailleDialog(last_mode, last_value, last_scale,
                                    parent=self.iface.mainWindow())
        if dlg.exec_() != EtiquetteTailleDialog.Accepted:
            return
        mode, value, min_scale = dlg.get_result()
        s.setValue("CanaPlan/label_size_mode",  mode)
        s.setValue("CanaPlan/label_size_value", value)
        apply_label_size_all(self, mode, value, min_scale)

    def toggle_affichage_etiquettes(self, checked):
        """Affiche ou masque les etiquettes ; recalcule les pentes dans tous les cas."""
        from .tools.calc_pentes import recalc_pentes
        for reseau in ("EU", "EP"):
            couches = self._get_couches(reseau)
            recalc_pentes(couches['conduite'], couches['regard'],
                          branchement_layer=couches['branchement'],
                          tabouret_layer=couches['tabouret'])
            for role in ("regard", "tabouret", "conduite", "branchement"):
                layer = couches[role]
                self._apply_style(layer, role, reseau)
                layer.setLabelsEnabled(checked)
                layer.triggerRepaint()

    def run_fond_projet(self, options=None):
        """Ajoute le fond de projet (OSM, Ortho, BAN, Noms de rue, PCI).

        :param options: dict optionnel {'osm', 'ortho', 'ban', 'noms_voie',
            'pci_bati', 'pci_parcelles'} -> bool. Une clé absente vaut True
            (comportement historique du bouton unique : tout est chargé).
            Utilisé par l'assistant de création de projet pour ne charger
            qu'un sous-ensemble choisi par l'utilisateur.
        """
        from qgis.core import QgsRasterLayer, QgsLayerTreeLayer
        from qgis.PyQt.QtGui import QColor

        opt = options or {}
        def _wanted(key):
            return opt.get(key, True)

        project   = QgsProject.instance()
        tree_root = project.layerTreeRoot()
        canvas    = self.iface.mapCanvas()
        saved_extent = canvas.extent()

        project.setBackgroundColor(QColor(255, 255, 255))
        canvas.setCanvasColor(QColor(255, 255, 255))

        existing = {l.name() for l in project.mapLayers().values()}

        def add_bottom(layer):
            project.addMapLayer(layer, False)
            tree_root.insertChildNode(-1, QgsLayerTreeLayer(layer))

        # --- Rasters (immédiats, pas de téléchargement préalable) ---
        # Ordre final légende top→bottom :
        # EU/EP | BAN | Noms | Bâti | Parcelles | OSM | Ortho
        # Canvas gelé le temps de l'insertion : empêche
        # QgsLayerTreeMapCanvasBridge de recadrer sur l'étendue des rasters.
        canvas.freeze(True)
        try:
            osm_name = "OSM Desature"
            if _wanted('osm') and osm_name not in existing:
                lyr = QgsRasterLayer(
                    "crs=EPSG:2154&featureCount=10&format=image/png"
                    "&layers=faded&maxHeight=2048&maxWidth=2048"
                    "&styles=&url=https://osm.datagrandest.fr/mapcache",
                    osm_name, "wms")
                if lyr.isValid():
                    lyr.setOpacity(0.7)
                    lyr.setMaximumScale(1000)
                    lyr.setScaleBasedVisibility(True)
                    add_bottom(lyr)

            ortho_name = "Ortho IGN (BD ORTHO nationale)"
            if _wanted('ortho') and ortho_name not in existing:
                lyr = QgsRasterLayer(
                    "crs=EPSG:2154&featureCount=10&format=image/jpeg"
                    "&layers=ORTHOIMAGERY.ORTHOPHOTOS&maxHeight=2048&maxWidth=2048"
                    "&styles=&url=https://data.geopf.fr/wms-r/wms",
                    ortho_name, "wms")
                if lyr.isValid():
                    lyr.setOpacity(0.75)
                    lyr.setMinimumScale(2000)
                    lyr.setScaleBasedVisibility(True)
                    add_bottom(lyr)
        finally:
            canvas.freeze(False)

        # --- Couches vecteur WFS (asynchrones) ---
        def _has_nom(f):
            p = f.get('properties', {})
            return bool(p.get('nom_voie_ban_gauche')
                        or p.get('nom_voie_ban_droite'))

        requests = []
        if _wanted('ban') and "BAN Adresses" not in existing:
            requests.append({'typename': "BAN.DATA.GOUV:ban",
                             'name': "BAN Adresses", 'prefix': 'bet_fdp_'})
        if _wanted('noms_voie') and "Noms de rue BD TOPO" not in existing:
            requests.append({'typename': "BDTOPO_V3:troncon_de_route",
                             'name': "Noms de rue BD TOPO",
                             'prefix': 'bet_fdp_', 'filter': _has_nom})
        if _wanted('pci_bati') and "PCI - Bati" not in existing:
            requests.append({'typename': "BDTOPO_V3:batiment",
                             'name': "PCI - Bati", 'prefix': 'bet_fdp_'})
        if _wanted('pci_parcelles') and "PCI - Parcelles" not in existing:
            requests.append({
                'typename': "CADASTRALPARCELS.PARCELLAIRE_EXPRESS:parcelle",
                'name': "PCI - Parcelles", 'prefix': 'bet_fdp_'})

        canvas.setExtent(saved_extent)
        canvas.refresh()

        if not requests:
            self.iface.messageBar().pushMessage(
                i18n.tr('fond_projet'), i18n.tr('msg_fond_ok'),
                level=0, duration=6)
            return

        def style_fdp(layer, name):
            if name == "BAN Adresses":
                self._style_ban_layer(layer)
            elif name == "Noms de rue BD TOPO":
                self._style_rue_layer(layer)
            else:
                self._style_pci_layer(layer, name)

        def insert_above_rasters(layer):
            """Insère la couche au-dessus des rasters de fond (OSM/Ortho),
            pour préserver l'ordre BAN/Noms/Bâti/Parcelles | OSM | Ortho."""
            root = QgsProject.instance().layerTreeRoot()
            idx = len(root.children())
            for i, child in enumerate(root.children()):
                if child.name() in (osm_name, ortho_name):
                    idx = i
                    break
            QgsProject.instance().addMapLayer(layer, False)
            root.insertChildNode(idx, QgsLayerTreeLayer(layer))

        self._load_wfs_async("Fond de projet", requests,
                             style_cb=style_fdp, scale_min=5000,
                             insert_cb=insert_above_rasters,
                             restore_extent=(canvas, saved_extent))

    def run_pci_bati(self):
        canvas = self.iface.mapCanvas()
        self._load_wfs_async("PCI - Bâti", [
            {'typename': "BDTOPO_V3:batiment",
             'name': "PCI - Bati", 'prefix': 'bet_pci_'},
        ], style_cb=self._style_pci_layer,
           restore_extent=(canvas, canvas.extent()))

    def run_pci_parcelles(self):
        canvas = self.iface.mapCanvas()
        self._load_wfs_async("PCI - Parcelles", [
            {'typename': "CADASTRALPARCELS.PARCELLAIRE_EXPRESS:parcelle",
             'name': "PCI - Parcelles", 'prefix': 'bet_pci_'},
        ], style_cb=self._style_pci_layer,
           restore_extent=(canvas, canvas.extent()))

    # ------------------------------------------------------------------ WFS asynchrone

    def _load_wfs_async(self, title, requests, style_cb=None,
                        scale_min=None, insert_cb=None,
                        restore_extent=None):
        """Télécharge et ajoute des couches WFS sans bloquer l'interface.

        Le réseau et l'écriture des GeoJSON partent dans une QgsTask
        (progression dans la barre de tâches QGIS, annulable) ; les couches
        sont créées et stylées dans le thread principal à la fin.

        :param requests: liste de dicts (voir tools.wfs_utils.fetch_wfs_async)
        :param style_cb: callable(layer, name) appelé après ajout
        :param scale_min: visibilité par échelle (setMinimumScale)
        :param insert_cb: callable(layer) pour un placement personnalisé
                          dans la légende (défaut : tout en bas)
        :param restore_extent: (canvas, extent) pour reverrouiller l'étendue
                          de la carte après ajout des couches
        """
        from qgis.core import QgsVectorLayer, QgsLayerTreeLayer, QgsMessageLog, Qgis
        from .tools.wfs_utils import current_bbox_l93, fetch_wfs_async

        bbox = current_bbox_l93(self.iface.mapCanvas())
        QgsMessageLog.logMessage(
            f"{title} : bbox envoyée = {bbox}", "CanaPlan", Qgis.Info)
        for req in requests:
            req['bbox'] = bbox

        iface = self.iface

        def on_done(results, errors):
            project   = QgsProject.instance()
            tree_root = project.layerTreeRoot()
            loaded, msgs, insecure = 0, list(errors), False
            if restore_extent is not None:
                restore_extent[0].freeze(True)
            try:
                for res in results:
                    insecure = insecure or res['insecure']
                    if not res['path']:
                        msgs.append(i18n.tr('msg_wfs_vide',
                                                couche=res['name']))
                        continue
                    # Une couche déjà chargée sous le même nom est mise à
                    # jour sur place (nouvelle source de données) plutôt que
                    # remplacée : elle garde sa position dans le
                    # gestionnaire de couches, son id et son style.
                    existing = next(
                        (l for l in project.mapLayers().values()
                         if l.name() == res['name']), None)
                    if existing is not None:
                        existing.setDataSource(res['path'], res['name'], "ogr")
                        if not existing.isValid():
                            msgs.append(i18n.tr('msg_wfs_invalide',
                                                    couche=res['name']))
                            continue
                        layer = existing
                    else:
                        layer = QgsVectorLayer(res['path'], res['name'], "ogr")
                        if not layer.isValid():
                            msgs.append(i18n.tr('msg_wfs_invalide',
                                                    couche=res['name']))
                            continue
                        if insert_cb is not None:
                            insert_cb(layer)
                        else:
                            project.addMapLayer(layer, False)
                            tree_root.insertChildNode(-1, QgsLayerTreeLayer(layer))
                    if style_cb is not None:
                        try:
                            style_cb(layer, res['name'])
                        except Exception as se:
                            msgs.append(f"style {res['name']} : {se}")
                    if scale_min:
                        layer.setMinimumScale(scale_min)
                        layer.setScaleBasedVisibility(True)
                    layer.triggerRepaint()
                    loaded += res['count']
            finally:
                if restore_extent is not None:
                    restore_extent[0].freeze(False)
            if insecure:
                msgs.append(i18n.tr('msg_wfs_tls'))
            msg = i18n.tr('msg_wfs_charges', nb=loaded)
            if msgs:
                msg += "  |  " + " / ".join(msgs)
            iface.messageBar().pushMessage(
                title, msg,
                level=1 if loaded == 0 else 0, duration=6)
            if restore_extent is not None:
                rcanvas, rextent = restore_extent
                rcanvas.setExtent(rextent)
                rcanvas.refresh()

        fetch_wfs_async(title, requests, on_done)
        iface.messageBar().pushMessage(
            title, i18n.tr('msg_telechargement'), level=0, duration=3)

    @staticmethod
    def _make_label_settings(field, is_expr, placement, size=8,
                             rgb=(50, 50, 50)):
        """QgsPalLayerSettings partagés par les styles de fonds vecteur."""
        from qgis.core import (
            QgsPalLayerSettings, QgsTextFormat, QgsUnitTypes,
        )
        from qgis.PyQt.QtGui import QColor, QFont
        pal = QgsPalLayerSettings()
        pal.fieldName    = field
        pal.isExpression = is_expr
        pal.placement    = placement
        pal.enabled      = True
        fmt = QgsTextFormat()
        fmt.setFont(QFont('Arial'))
        fmt.setSizeUnit(QgsUnitTypes.RenderPoints)
        fmt.setSize(size)
        fmt.setColor(QColor(*rgb))
        pal.setFormat(fmt)
        return pal

    def _style_pci_layer(self, layer, layer_name):
        from qgis.core import (
            QgsFillSymbol, QgsSingleSymbolRenderer,
            QgsVectorLayerSimpleLabeling, Qgis,
        )

        if "Parcelles" in layer_name:
            # Contour gris, intérieur transparent
            symbol = QgsFillSymbol.createSimple({
                'color':         '0,0,0,0',
                'outline_color': '80,80,80,255',
                'outline_width': '0.4',
            })
            layer.setRenderer(QgsSingleSymbolRenderer(symbol))

            # Label parcelle — 8 pt fixe
            pal = self._make_label_settings(
                '"section" || "numero"', True, Qgis.LabelPlacement.Horizontal)
            layer.setLabeling(QgsVectorLayerSimpleLabeling(pal))
            layer.setLabelsEnabled(True)
            layer.triggerRepaint()

        elif "Bati" in layer_name:
            # Gris 50 % opacité. NB : la couche s'appelle "PCI - Bati"
            # (sans accent) — l'ancien test "Bâti" ne matchait jamais.
            symbol = QgsFillSymbol.createSimple({
                'color':         '160,160,160,128',
                'outline_color': '100,100,100,200',
                'outline_width': '0.2',
            })
            layer.setRenderer(QgsSingleSymbolRenderer(symbol))

    def _style_ban_layer(self, layer):
        """Points BAN invisibles, étiquette = numéro (8 pt)."""
        from qgis.core import (
            QgsNullSymbolRenderer, QgsVectorLayerSimpleLabeling, Qgis,
        )
        layer.setRenderer(QgsNullSymbolRenderer())
        pal = self._make_label_settings(
            'numero', False, Qgis.LabelPlacement.OverPoint, rgb=(30, 30, 30))
        layer.setLabeling(QgsVectorLayerSimpleLabeling(pal))
        layer.setLabelsEnabled(True)

    def _style_rue_layer(self, layer):
        """Tronçons invisibles, étiquette = nom de voie courbé (8 pt)."""
        from qgis.core import (
            QgsLineSymbol, QgsSingleSymbolRenderer,
            QgsVectorLayerSimpleLabeling, Qgis,
        )
        sym = QgsLineSymbol.createSimple({'color': '0,0,0,0',
                                          'line_style': 'no'})
        layer.setRenderer(QgsSingleSymbolRenderer(sym))
        pal = self._make_label_settings(
            'coalesce("nom_voie_ban_gauche","nom_voie_ban_droite")',
            True, Qgis.LabelPlacement.Curved, rgb=(40, 40, 120))
        layer.setLabeling(QgsVectorLayerSimpleLabeling(pal))
        layer.setLabelsEnabled(True)

    # ------------------------------------------------------------------ helper WFS

    def _wfs_emprise(self, typename, layer_name,
                     wfs_url="https://data.geopf.fr/wfs/ows"):
        """Charge une couche WFS sur l'emprise courante (asynchrone),
        déposée en bas de légende."""
        self._load_wfs_async(layer_name, [{
            'typename': typename, 'name': layer_name,
            'wfs_url': wfs_url, 'prefix': 'bet_wfs_',
        }])

    # ------------------------------------------------------------------ fonds vecteur

    def run_ban_vecteur(self):
        canvas = self.iface.mapCanvas()
        self._load_wfs_async("BAN Adresses", [{
            'typename': "BAN.DATA.GOUV:ban", 'name': "BAN Adresses",
            'prefix': 'bet_ban_',
        }], style_cb=lambda layer, name: self._style_ban_layer(layer),
           restore_extent=(canvas, canvas.extent()))

    def run_nom_voie(self):
        def _has_nom(f):
            p = f.get('properties', {})
            return bool(p.get('nom_voie_ban_gauche')
                        or p.get('nom_voie_ban_droite'))

        canvas = self.iface.mapCanvas()
        self._load_wfs_async("Noms de rue BD TOPO", [{
            'typename': "BDTOPO_V3:troncon_de_route",
            'name': "Noms de rue BD TOPO",
            'prefix': 'bet_rue_', 'filter': _has_nom,
        }], style_cb=lambda layer, name: self._style_rue_layer(layer),
           restore_extent=(canvas, canvas.extent()))



    @staticmethod
    def _remove_orphan_layer(name):
        """Supprime du projet toute couche `name` absente de l'arbre de
        légende (résidu d'un ajout interrompu), pour ne pas bloquer un
        nouvel ajout via le test anti-doublon."""
        project = QgsProject.instance()
        root    = project.layerTreeRoot()
        for lyr in list(project.mapLayers().values()):
            if lyr.name() == name and root.findLayer(lyr.id()) is None:
                project.removeMapLayer(lyr.id())

    def _add_raster_bottom_keep_extent(self, layer):
        """Ajoute un raster en bas de légende sans dézoomer le canvas.

        Une couche WMS ne connaît son étendue réelle qu'après avoir reçu
        les capabilities du serveur (requête réseau asynchrone) ; ce retour
        tardif peut recadrer le canvas bien après notre insertion. On
        verrouille donc l'étendue pendant une courte fenêtre après l'ajout,
        pas seulement une fois, pour absorber ce recadrage différé.
        """
        from qgis.core import QgsLayerTreeLayer
        from qgis.PyQt.QtCore import QTimer
        project = QgsProject.instance()
        canvas  = self.iface.mapCanvas()
        saved_extent = canvas.extent()

        def _lock_extent(*_args):
            if canvas.extent() != saved_extent:
                canvas.blockSignals(True)
                canvas.setExtent(saved_extent)
                canvas.blockSignals(False)
                canvas.refresh()

        canvas.extentsChanged.connect(_lock_extent)

        canvas.freeze(True)
        try:
            project.addMapLayer(layer, False)
            project.layerTreeRoot().insertChildNode(-1, QgsLayerTreeLayer(layer))
        finally:
            canvas.freeze(False)
        canvas.setExtent(saved_extent)
        canvas.refresh()

        QTimer.singleShot(
            2000, lambda: canvas.extentsChanged.disconnect(_lock_extent))

    def run_ortho_ign(self):
        from qgis.core import QgsRasterLayer, QgsLayerTreeLayer
        name   = "Ortho IGN (BD ORTHO nationale)"
        source = (
            "crs=EPSG:2154&featureCount=10&format=image/jpeg"
            "&layers=ORTHOIMAGERY.ORTHOPHOTOS&maxHeight=2048&maxWidth=2048"
            "&styles=&url=https://data.geopf.fr/wms-r/wms"
        )
        self._remove_orphan_layer(name)
        project = QgsProject.instance()
        for lyr in project.mapLayers().values():
            if lyr.name() == name:
                return
        layer = QgsRasterLayer(source, name, "wms")
        if not layer.isValid():
            from qgis.PyQt.QtWidgets import QMessageBox
            QMessageBox.warning(self.iface.mainWindow(),
                                i18n.tr('msg_fond_carte'),
                                i18n.tr('msg_wms_echec', nom=name))
            return
        self._add_raster_bottom_keep_extent(layer)

    def run_osm_desature(self):
        from qgis.core import QgsRasterLayer, QgsLayerTreeLayer
        name   = "OSM Desature"
        source = (
            "crs=EPSG:2154&featureCount=10&format=image/png"
            "&layers=faded&maxHeight=2048&maxWidth=2048"
            "&styles=&url=https://osm.datagrandest.fr/mapcache"
        )
        self._remove_orphan_layer(name)
        project = QgsProject.instance()
        # Évite les doublons
        for lyr in project.mapLayers().values():
            if lyr.name() == name:
                return
        layer = QgsRasterLayer(source, name, "wms")
        if not layer.isValid():
            from qgis.PyQt.QtWidgets import QMessageBox
            QMessageBox.warning(self.iface.mainWindow(),
                                i18n.tr('msg_fond_carte'),
                                i18n.tr('msg_wms_echec', nom=name))
            return
        self._add_raster_bottom_keep_extent(layer)

    def run_nouveau_projet_assistant(self):
        from .gui.project_wizard_dialog import ProjectWizardDialog
        wizard = ProjectWizardDialog(self, self.iface)
        wizard.exec_()

    def run_enregistrer_projet(self):
        from .tools.projet_bet import save_projet
        save_projet(self, self.iface)

    def run_enregistrer_projet_sous(self):
        from .tools.projet_bet import save_projet_sous
        save_projet_sous(self, self.iface)

    def run_charger_projet(self):
        from .tools.projet_bet import load_projet
        load_projet(self, self.iface)

    def run_projets_recents(self):
        """Ouvre la fenêtre de choix parmi les 4 derniers projets."""
        from .gui.recent_projects_dialog import RecentProjectsDialog
        from .tools.projet_bet import load_projet, recent_projects

        dlg = RecentProjectsDialog(recent_projects(), self.iface.mainWindow())
        if dlg.exec_() != RecentProjectsDialog.Accepted:
            return
        bet_path = dlg.selected_path()
        if bet_path:
            load_projet(self, self.iface, bet_path)

    def run_imprimer(self):
        from .gui.export_dialog import ExportDialog
        from .tools.projet_bet import project_dir

        dlg_export = ExportDialog(self.iface.mainWindow(),
                                  default_dir=project_dir())
        if dlg_export.exec_() != ExportDialog.Accepted:
            return
        choices = dlg_export.get_choices()
        # Les réglages du plan sont désormais dans la même fenêtre : plus de
        # PrintDialog à traverser avant d'exporter.
        settings = dlg_export.get_print_settings()

        if choices.get('tout_en_un'):
            self._export_tout_en_un(choices, settings)
            return

        do_plan_pdf  = choices['plan_pdf']
        do_plan_dxf  = choices['plan_dxf']
        do_profil_eu  = choices['profil_eu']
        do_profil_ep  = choices['profil_ep']
        do_profil_grp = choices['profil_groupe']
        do_cubature   = choices['cubature']
        do_coupes     = choices['coupe_eu'] or choices['coupe_ep']

        if not any([do_plan_pdf, do_plan_dxf, do_profil_eu, do_profil_ep,
                    do_profil_grp, do_cubature, do_coupes]):
            return

        # ── Profils en long (export immédiat, sans interaction carte) ──────
        if do_profil_eu or do_profil_ep or do_profil_grp:
            self._export_profils_batch(choices)

        # ── Cubature et coupes types (export immédiat, sans interaction) ───
        # Un seul compte rendu pour les deux : ils partagent le dossier de
        # sortie et l'utilisateur les a demandés d'un même clic.
        msgs = []
        if do_cubature:
            msgs.extend(self._export_cubature_batch(choices))
        if do_coupes:
            msgs.extend(self._export_coupes_batch(choices))
        if msgs:
            from qgis.PyQt.QtWidgets import QMessageBox
            QMessageBox.information(
                self.iface.mainWindow(),
                i18n.tr('msg_export_sorties_ok'),
                "\n".join(msgs) + "\n\n"
                + i18n.tr('msg_dossier', chemin=choices.get('output_dir', '')),
            )

        # ── Plan PDF/DXF → PrintTool ───────────────────────────────────────
        if not do_plan_pdf and not do_plan_dxf:
            return

        out_dir = choices.get('output_dir')

        if do_plan_dxf and not do_plan_pdf:
            self._export_dxf_direct(out_dir=out_dir)
            return

        from .tools.print_tool import PrintTool
        from qgis.core import QgsUnitTypes

        settings['do_pdf']     = do_plan_pdf
        settings['do_dxf']     = do_plan_dxf
        settings['output_dir'] = out_dir

        crs = self.iface.mapCanvas().mapSettings().destinationCrs()
        if crs.mapUnits() != QgsUnitTypes.DistanceMeters:
            from qgis.PyQt.QtWidgets import QMessageBox
            QMessageBox.warning(
                self.iface.mainWindow(), i18n.tr('msg_impression'),
                i18n.tr('msg_crs_non_metrique', crs=crs.authid()),
            )

        if settings.get('cadrage_auto'):
            self._imprimer_cadrage_auto(settings)
            return

        tool = PrintTool(self.iface.mapCanvas(), self.iface, settings)
        self._cleanup_tools()
        self.iface.mapCanvas().setMapTool(tool)
        self.tools['imprimer'] = tool

        from .tools.print_tool import _aide_pose
        self.iface.messageBar().pushMessage(
            i18n.tr('msg_impression'), _aide_pose(settings),
            level=0, duration=0,
        )

    def _export_tout_en_un(self, choices, settings):
        """Bouton « Tout en un » : toutes les sorties dans une archive ZIP.

        Les sorties automatiques (profils, cubature, coupes types) partent
        d'abord dans un dossier de travail. Le cadrage du plan reste posé à la
        main sur la carte, comme pour un export normal : c'est PrintTool qui
        signale la fin, et l'archive est refermée à ce moment-là.
        """
        import os
        import tempfile
        from datetime import datetime
        from qgis.PyQt.QtWidgets import QMessageBox
        from qgis.core import QgsProject, QgsUnitTypes

        out_dir = choices.get('output_dir')
        if not out_dir or not os.path.isdir(out_dir):
            return

        # Nom horodaté : jamais de collision avec un export précédent.
        projet_path = QgsProject.instance().fileName()
        base = (os.path.splitext(os.path.basename(projet_path))[0]
                if projet_path else "CanaPlan")
        base = f"{base}_tout_en_un_{datetime.now():%Y%m%d_%H%M}"

        # Le travail se fait dans le TEMP du système, jamais dans le dossier
        # de l'utilisateur : celui-ci ne doit jamais voir apparaître autre
        # chose que l'archive, même pendant la pose des feuilles.
        try:
            work_dir = tempfile.mkdtemp(prefix="canaplan_tout_en_un_")
        except OSError as e:
            QMessageBox.critical(self.iface.mainWindow(),
                                 i18n.tr('msg_tout_en_un'),
                                 i18n.tr('msg_zip_erreur', erreur=e))
            return

        # « Tout » veut dire tout : les cases du dialogue ne s'appliquent pas,
        # seuls les formats papier retenus par l'utilisateur sont repris.
        sous_choix = dict(choices)
        sous_choix.update({
            'output_dir':            work_dir,
            'profil_eu':             True,
            'profil_ep':             True,
            'profil_groupe':         False,
            'cubature':              True,
            'cubature_perimetre':    'tout',
            'cubature_conduites':    True,
            'cubature_branchements': True,
            'cubature_pdf':          True,
            'cubature_xlsx':         True,
            'cubature_csv':          False,
            'cubature_remblai':      True,
            'coupe_eu':              True,
            'coupe_ep':              True,
        })

        msgs = []
        msgs.extend(self._export_profils_batch(sous_choix, silencieux=True))
        msgs.extend(self._export_cubature_batch(sous_choix))
        msgs.extend(self._export_coupes_batch(sous_choix))

        # ── Plan PDF + DXF : cadrage posé par l'utilisateur ────────────────
        from .tools.print_tool import PrintTool, _aide_pose

        settings = dict(settings)   # ne pas polluer les réglages de l'appelant
        settings['do_pdf']     = True
        settings['do_dxf']     = True
        settings['output_dir'] = work_dir
        # Les fichiers partent dans le TEMP et sont supprimés après archivage :
        # les ouvrir afficherait un PDF et lancerait AutoCAD sur des fichiers
        # qui n'existeront plus dans la seconde.
        settings['open_after'] = False

        crs = self.iface.mapCanvas().mapSettings().destinationCrs()
        if crs.mapUnits() != QgsUnitTypes.DistanceMeters:
            QMessageBox.warning(
                self.iface.mainWindow(), i18n.tr('msg_impression'),
                i18n.tr('msg_crs_non_metrique', crs=crs.authid()),
            )

        cloture = lambda: self._finaliser_zip(work_dir, out_dir, base, msgs)

        if settings.get('cadrage_auto'):
            # Le ZIP se referme de la même façon : c'est PrintTool qui
            # signale la fin, qu'il ait été nourri par des clics ou par le
            # calcul.
            self._imprimer_cadrage_auto(settings, on_finished=cloture)
            return

        tool = PrintTool(
            self.iface.mapCanvas(), self.iface, settings,
            on_finished=cloture,
        )
        self._cleanup_tools()
        self.iface.mapCanvas().setMapTool(tool)
        self.tools['imprimer'] = tool

        self.iface.messageBar().pushMessage(
            i18n.tr('msg_tout_en_un'),
            i18n.tr('msg_tout_en_un_pose') + "  " + _aide_pose(settings),
            level=0, duration=0,
        )

    # Au-delà, on demande confirmation : un export de cette taille prend
    # plusieurs minutes, et le cas vient presque toujours d'une échelle trop
    # grande saisie par erreur.
    _SEUIL_PLANCHES = 20

    def _imprimer_cadrage_auto(self, settings, on_finished=None):
        """Calcule les planches, puis lance l'export sans pose manuelle.

        `on_finished` est transmis à PrintTool, et appelé aussi sur les
        abandons : sans cela, un tout en un interrompu laisserait son dossier
        de travail derrière lui.
        """
        from qgis.PyQt.QtCore import Qt, QSettings
        from qgis.PyQt.QtWidgets import QApplication, QMessageBox
        from qgis.core import QgsProject

        from .tools.cadrage_auto import calculer_planches, marge_depuis_couches
        from .tools.print_tool import PrintTool
        from .tools.projet_bet import _read_label_size

        def abandon():
            if on_finished is not None:
                on_finished()

        # ── Couches à couvrir : le réseau seul ────────────────────────────
        # Les fonds (cadastre, ortho) couvrent tout le département : les
        # inclure ferait cadrer sur eux et non sur le chantier.
        couches = []
        for reseau in ("EU", "EP"):
            jeu = self._get_couches(reseau) or {}
            for cle in ('conduite', 'regard', 'branchement', 'tabouret'):
                couche = jeu.get(cle)
                if couche is not None:
                    couches.append(couche)

        if not couches:
            QMessageBox.warning(self.iface.mainWindow(),
                                i18n.tr('msg_impression'),
                                i18n.tr('msg_cadrage_aucun'))
            abandon()
            return

        # La marge se déduit des étiquettes réellement affichées : c'est
        # leur largeur, et non la géométrie ni la hauteur de la police, qui
        # déborde le plus des planches.
        try:
            label_size = _read_label_size(QgsProject.instance(), QSettings())
        except Exception:
            label_size = None
        marge = marge_depuis_couches(couches, settings['echelle'], label_size)

        self.iface.messageBar().pushMessage(
            i18n.tr('msg_impression'), i18n.tr('msg_cadrage_calcul'),
            level=0, duration=3)

        QApplication.setOverrideCursor(Qt.WaitCursor)
        try:
            planches = calculer_planches(
                couches, settings['w_mm'], settings['h_mm'],
                settings['echelle'], marge_mm=marge)
        except Exception as e:
            QApplication.restoreOverrideCursor()
            QMessageBox.critical(self.iface.mainWindow(),
                                 i18n.tr('msg_impression'),
                                 i18n.tr('msg_erreur_detail', detail=e))
            abandon()
            return
        finally:
            QApplication.restoreOverrideCursor()

        if not planches:
            QMessageBox.warning(self.iface.mainWindow(),
                                i18n.tr('msg_impression'),
                                i18n.tr('msg_cadrage_aucun'))
            abandon()
            return

        if len(planches) > self._SEUIL_PLANCHES:
            rep = QMessageBox.question(
                self.iface.mainWindow(), i18n.tr('msg_impression'),
                i18n.tr('msg_cadrage_beaucoup', nb=len(planches),
                        echelle=settings['echelle']),
                QMessageBox.Yes | QMessageBox.No)
            if rep != QMessageBox.Yes:
                abandon()
                return

        tool = PrintTool(self.iface.mapCanvas(), self.iface, settings,
                         on_finished=on_finished)
        self._cleanup_tools()
        self.iface.mapCanvas().setMapTool(tool)
        self.tools['imprimer'] = tool

        tool.definir_feuilles(planches)
        self.iface.messageBar().pushMessage(
            i18n.tr('msg_impression'),
            i18n.tr('msg_cadrage_pret', nb=len(planches),
                    echelle=settings['echelle']),
            level=0, duration=5)
        tool.exporter_maintenant()

    def _finaliser_zip(self, work_dir, out_dir, base, msgs):
        """Zippe le dossier de travail, le supprime, et rend compte."""
        import os
        import shutil
        from qgis.PyQt.QtWidgets import QMessageBox

        fichiers = []
        if os.path.isdir(work_dir):
            for racine, _sous_dossiers, noms in os.walk(work_dir):
                fichiers.extend(os.path.join(racine, n) for n in noms)

        if not fichiers:
            shutil.rmtree(work_dir, ignore_errors=True)
            QMessageBox.warning(self.iface.mainWindow(),
                                i18n.tr('msg_tout_en_un'),
                                i18n.tr('msg_zip_vide'))
            return

        zip_path = os.path.join(out_dir, base + ".zip")
        try:
            shutil.make_archive(os.path.join(out_dir, base), 'zip', work_dir)
        except Exception as e:
            QMessageBox.critical(self.iface.mainWindow(),
                                 i18n.tr('msg_tout_en_un'),
                                 i18n.tr('msg_zip_erreur', erreur=e))
            return
        finally:
            # Le dossier temporaire ne doit jamais survivre, réussite ou non.
            shutil.rmtree(work_dir, ignore_errors=True)

        msgs = list(msgs) + [i18n.tr('msg_zip_ok',
                                     fichier=os.path.basename(zip_path),
                                     nb=len(fichiers))]
        QMessageBox.information(
            self.iface.mainWindow(), i18n.tr('msg_tout_en_un'),
            "\n".join(msgs) + "\n\n"
            + i18n.tr('msg_dossier', chemin=out_dir),
        )

    def _export_cubature_batch(self, choices):
        """Cubature de l'export groupé : calcul sur le réseau, sans carte.

        Les modes axe et BFS ne sont pas repris ici : ils supposent de
        désigner des ouvrages, ce que l'export groupé ne peut pas faire.
        Retourne les lignes de compte rendu à afficher.
        """
        import os
        from qgis.PyQt.QtWidgets import QApplication
        from qgis.PyQt.QtCore import Qt

        from .config_dialog import get_cubature_config
        from .gui.cubature_dialog import CubatureDialog
        from .tools.calc_cubature import calculer_cubature_reseau

        out_dir = choices.get('output_dir')
        if not out_dir or not os.path.isdir(out_dir):
            return []

        formats = {cle: bool(choices.get('cubature_' + cle))
                   for cle in ('pdf', 'xlsx', 'csv')}
        if not any(formats.values()):
            return []

        config    = get_cubature_config()
        perimetre = choices.get('cubature_perimetre', 'tout')

        reseaux = []
        if perimetre in ('tout', 'EU'):
            reseaux.append(('EU', self._get_couches("EU")))
        if perimetre in ('tout', 'EP'):
            reseaux.append(('EP', self._get_couches("EP")))

        all_results = []
        for reseau, couches in reseaux:
            if not couches:
                continue
            results = calculer_cubature_reseau(couches, config, reseau)
            if not choices.get('cubature_conduites', True):
                results = [r for r in results if r.get('type') != 'Conduite']
            if not choices.get('cubature_branchements', True):
                results = [r for r in results if r.get('type') != 'Branchement']
            all_results.extend(results)

        if not all_results:
            return [i18n.tr('msg_cubature_export_vide')]

        QApplication.setOverrideCursor(Qt.WaitCursor)
        try:
            # Le dialogue porte toute la mise en page des exports ; on s'en
            # sert comme moteur de rendu, sans jamais l'afficher.
            dlg = CubatureDialog(
                all_results, config, self.iface.mainWindow(),
                show_remblai=bool(choices.get('cubature_remblai')))
            try:
                ecrits = dlg.exporter_fichiers(out_dir, **formats)
            finally:
                dlg.deleteLater()
        finally:
            QApplication.restoreOverrideCursor()

        if not ecrits:
            return [i18n.tr('msg_cubature_export_vide')]
        return [i18n.tr(
            'msg_cubature_export_ok', nb=len(all_results),
            fichiers=", ".join(os.path.basename(c) for c in ecrits))]

    def _export_coupes_batch(self, choices):
        """Coupes types EU / EP de l'export groupé.

        Retourne les lignes de compte rendu à afficher.
        """
        import os
        from qgis.PyQt.QtWidgets import QApplication
        from qgis.PyQt.QtCore import Qt

        from .config_dialog import get_cubature_config
        from .tools.coupe_type import exporter_coupe_type

        out_dir = choices.get('output_dir')
        if not out_dir or not os.path.isdir(out_dir):
            return []

        demandes = [r for r in ('EU', 'EP') if choices.get('coupe_' + r.lower())]
        if not demandes:
            return []

        config = get_cubature_config()
        msgs   = []

        QApplication.setOverrideCursor(Qt.WaitCursor)
        try:
            for reseau in demandes:
                couches = self._get_couches(reseau)
                path = None
                if couches:
                    path, _stats = exporter_coupe_type(
                        couches, config, reseau, out_dir,
                        fmt=choices.get('coupe_fichier', 'pdf'),
                        paper=choices.get('coupe_papier', 'a4_paysage'),
                        parent=self.iface.mainWindow(),
                    )
                msgs.append(
                    i18n.tr('msg_coupe_export_ok', reseau=reseau,
                            fichier=os.path.basename(path)) if path
                    else i18n.tr('msg_coupe_export_vide', reseau=reseau))
        except Exception as e:
            msgs.append(i18n.tr('msg_erreur_detail', detail=e))
        finally:
            QApplication.restoreOverrideCursor()

        return msgs

    def _export_profils_batch(self, choices, silencieux=False):
        """Export batch des profils en long vers des PDF dans le dossier choisi.

        Retourne les lignes de compte rendu. `silencieux` les renvoie sans les
        afficher, pour que l'export tout en un n'empile pas les fenêtres.
        """
        import os
        from qgis.PyQt.QtWidgets import QApplication, QMessageBox
        from qgis.PyQt.QtCore import Qt

        out_dir = choices.get('output_dir')
        if not out_dir or not os.path.isdir(out_dir):
            return []

        QApplication.setOverrideCursor(Qt.WaitCursor)
        msgs = []
        try:
            from .tools.profil_batch import export_profils_eu_ep, export_profils_groupe

            if choices['profil_eu']:
                couches_eu = self._get_couches("EU")
                n_ok, n_skip, out_path = export_profils_eu_ep(
                    couches_eu, "EU", choices['profil_eu_format'], out_dir)
                if n_ok:
                    msgs.append(i18n.tr(
                        'msg_profils_ok', reseau="EU", nb=n_ok,
                        fichier=os.path.basename(out_path)))
                else:
                    msgs.append(i18n.tr('msg_profils_vide', reseau="EU"))

            if choices['profil_ep']:
                couches_ep = self._get_couches("EP")
                n_ok, n_skip, out_path = export_profils_eu_ep(
                    couches_ep, "EP", choices['profil_ep_format'], out_dir)
                if n_ok:
                    msgs.append(i18n.tr(
                        'msg_profils_ok', reseau="EP", nb=n_ok,
                        fichier=os.path.basename(out_path)))
                else:
                    msgs.append(i18n.tr('msg_profils_vide', reseau="EP"))

            if choices['profil_groupe']:
                couches_eu = self._get_couches("EU")
                couches_ep = self._get_couches("EP")
                ok, out_path = export_profils_groupe(
                    couches_eu, couches_ep, choices['profil_groupe_format'], out_dir,
                    reseau_ref=choices['profil_groupe_reseau'])
                msgs.append(
                    i18n.tr('msg_profil_groupe_ok',
                            fichier=os.path.basename(out_path)) if ok
                    else i18n.tr('msg_profil_groupe_vide'))

        except Exception as e:
            msgs.append(i18n.tr('msg_erreur_detail', detail=e))
        finally:
            QApplication.restoreOverrideCursor()

        if msgs and not silencieux:
            QMessageBox.information(
                self.iface.mainWindow(),
                i18n.tr('msg_export_profils_ok'),
                "\n".join(msgs) + "\n\n"
                + i18n.tr('msg_dossier', chemin=out_dir),
            )
        return msgs

    def _export_dxf_direct(self, out_dir=None):
        """Export DXF direct sans PrintDialog ni placement de feuilles.
        Utilise l'emprise visible du canvas et l'échelle de tracé 1/200.
        Si out_dir est fourni et valide, écrit directement dedans sans demander.
        """
        from qgis.core import QgsRectangle
        from .tools.projet_bet import project_dir
        from .tools.dxf_export import run_export_dxf_with_ui

        canvas = self.iface.mapCanvas()
        project = QgsProject.instance()

        extent = QgsRectangle(canvas.extent())
        scale_denom = 200.0

        titre = project.title() or "Plan_de_reseau"
        default_name = titre.replace(" ", "_") + ".dxf"

        if out_dir and os.path.isdir(out_dir):
            dxf_path = os.path.join(out_dir, default_name)
        else:
            from qgis.PyQt.QtWidgets import QFileDialog
            start_dir = project_dir() or os.path.expanduser("~")
            dxf_path, _ = QFileDialog.getSaveFileName(
                self.iface.mainWindow(),
                i18n.tr('msg_export_dxf_titre'),
                os.path.join(start_dir, default_name),
                "DXF (*.dxf)",
            )
            if not dxf_path:
                return

        run_export_dxf_with_ui(
            self.iface, dxf_path, extent, scale_denom,
            with_label_decorations=True, force_2d=True, open_after=True,
        )

    def run_import_dxf(self):
        from .tools.dxf_convert.ui_dialog import CadToGisDialog
        dlg = CadToGisDialog(self.iface)
        dlg.exec_()

    def run_export_stareau(self):
        """Ouvre le dialogue d'export StaR-Eau (CNIG/ASTEE).

        Volontairement NON modal : le controle de conformite renvoie vers des
        objets a corriger dans QGIS. Un dialogue modal empecherait justement
        de les corriger, et le bouton « Relancer le controle » ne pourrait
        jamais rien detecter de nouveau.
        """
        import sip
        from .gui.stareau_export_dialog import StarEauExportDialog

        dlg = getattr(self, '_stareau_dlg', None)
        if dlg is not None and not sip.isdeleted(dlg):
            dlg.run_check()
            dlg.show()
            dlg.raise_()
            dlg.activateWindow()
            return

        dlg = StarEauExportDialog(self.iface, self.iface.mainWindow())
        dlg.accepted.connect(self._do_export_stareau)
        self._stareau_dlg = dlg
        dlg.show()
        dlg.raise_()
        dlg.activateWindow()

    def _do_export_stareau(self):
        """Genere le GeoPackage une fois le dialogue valide."""
        from qgis.PyQt.QtWidgets import QApplication, QMessageBox
        from qgis.PyQt.QtCore import Qt
        from .tools.stareau_export import export_stareau

        dlg = getattr(self, '_stareau_dlg', None)
        if dlg is None:
            return

        out_path = dlg.output_path()
        QApplication.setOverrideCursor(Qt.WaitCursor)
        try:
            path, stats = export_stareau(dlg.params(), out_path)
        except Exception as e:
            QMessageBox.warning(
                self.iface.mainWindow(), "StaR-Eau",
                i18n.tr('msg_erreur_export', erreur=e))
            return
        finally:
            QApplication.restoreOverrideCursor()

        detail = ", ".join(f"{name} : {count}"
                           for name, count in stats.get('couches', {}).items())
        self.iface.messageBar().pushMessage(
            "StaR-Eau",
            i18n.tr('msg_export_stareau_ok',
                    fichier=os.path.basename(path), detail=detail),
            level=0, duration=8)

    def run_import_star_dt(self):
        from .gui.star_dt_dialog import StarDtDialog
        from .tools.star_dt_import import import_star_dt
        dlg = StarDtDialog(self.iface.mainWindow())
        if dlg.exec_() != StarDtDialog.Accepted:
            return
        paths = dlg.file_paths()
        out = dlg.output_path()
        types = dlg.get_selected_types()
        if not paths or not types or not out:
            return
        try:
            created = import_star_dt(paths, out, selected_types=types)
        except Exception as e:
            from qgis.PyQt.QtWidgets import QMessageBox
            QMessageBox.warning(
                self.iface.mainWindow(), "Star-DT",
                i18n.tr('msg_erreur_import', erreur=e))
            return
        if created:
            self.iface.messageBar().pushMessage(
                "Star-DT",
                i18n.tr('msg_import_ok', couches=len(created),
                        fichiers=len(paths), dossier=out),
                level=0, duration=5)
        else:
            self.iface.messageBar().pushMessage(
                "Star-DT", i18n.tr('msg_rien_a_importer'),
                level=1, duration=4)

    def show_config_dialog(self):
        from .config_dialog import ConfigDialog
        dialog = ConfigDialog(self.iface)
        dialog.exec_()

    def show_tableau_saisie(self):
        self._ensure_project_loaded()
        couches_eu = self._get_couches("EU")
        couches_ep = self._get_couches("EP")
        if not couches_eu or not couches_ep:
            return
        from .gui.tableau_saisie_dialog import TableauSaisieDialog
        self._tableau_saisie_dialog = TableauSaisieDialog(
            couches_eu, couches_ep, iface=self.iface, parent=self.iface.mainWindow())
        self._tableau_saisie_dialog.show()
        self._tableau_saisie_dialog.raise_()
        self._tableau_saisie_dialog.activateWindow()