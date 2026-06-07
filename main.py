import os
from qgis.PyQt.QtCore import QObject, QSettings, Qt, QVariant
from qgis.PyQt.QtGui import QIcon, QColor
from qgis.PyQt.QtWidgets import QAction, QActionGroup, QMessageBox
from qgis.core import (
    QgsProject, QgsVectorLayer, QgsField, QgsWkbTypes,
    QgsSymbol, QgsSimpleLineSymbolLayer, QgsSimpleMarkerSymbolLayer,
    QgsSingleSymbolRenderer, QgsLayerTreeGroup,
    QgsProperty, QgsSymbolLayer, QgsUnitTypes,
)

SKETCHES_PREFIX = "BET_HUMIDE/"

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
        self.toolbar = self.iface.addToolBar("Réseau Assainissement")
        self.toolbar.setObjectName("ReseauAssainissementToolBar")

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
            "Cubature tranchées",
            self.run_cubature,
            checkable=True
        )
        self.action_dict['remblai'] = self._add_action(
            "config.svg",
            "Remblai tranchées",
            self.run_remblai,
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
            ('fond_projet',            'Mise en place fond de projet',  self.run_fond_projet),
            ('enregistrer_projet_sous','Enregistrer sous',              self.run_enregistrer_projet_sous),
            ('ban_vecteur',            'BAN Adresses',        self.run_ban_vecteur),
            ('nom_voie',               'Noms de rue BD TOPO (emprise)', self.run_nom_voie),
        ]:
            self.action_dict[key] = self._add_action(
                "config.svg", label, cb, checkable=False)

        self.action_dict['pci_emprise'] = self._add_action(
            "config.svg",
            "PCI Vecteur – Parcelles & Bâti (emprise)",
            self.run_pci_emprise,
            checkable=False
        )
        self.action_dict['ortho_2022'] = self._add_action(
            "config.svg",
            "Ortho 2022",
            self.run_ortho_2022,
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

        # Séparateur avant config
        self.toolbar.addSeparator()
        self.action_dict['config'] = self._add_action(
            "config.svg",
            "Configurer les couches",
            self.show_config_dialog,
            checkable=False
        )

        # Ajouter aussi dans le menu
        self.menu = self.iface.pluginMenu().addMenu("Réseau Assainissement")
        for action in self.actions:
            self.menu.addAction(action)

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

    def unload(self):
        """Supprime la barre d'outils, les actions et les rubber bands."""
        import sip
        self._cleanup_tools()
        from .tools.projet_bet import cleanup_plugin_resources
        cleanup_plugin_resources(self)
        self.iface.removeDockWidget(self.side_panel)
        self.side_panel.deleteLater()
        for action in self.actions:
            self.iface.removePluginMenu("Réseau Assainissement", action)
        self.actions.clear()
        # Suppression synchrone (sip.delete) pour éviter le warning de
        # widget dupliqué au rechargement : deleteLater() est asynchrone et
        # laisse l'ancienne toolbar vivante quand le nouveau initGui s'exécute.
        for widget in (self.menu, self.toolbar):
            try:
                if widget is not None and not sip.isdeleted(widget):
                    sip.delete(widget)
            except Exception:
                pass
        self.menu = None
        self.toolbar = None

    def _cleanup_tools(self):
        """Nettoie tous les rubber bands des outils actifs."""
        for tool in self.tools.values():
            if tool is not None:
                tool.deactivate()
        self.tools.clear()
        self.iface.mapCanvas().refresh()

    def _add_action(self, icon_name, text, callback, checkable=False):
        """Ajoute une action à la barre d'outils et au menu."""
        icon_path = os.path.join(self.plugin_dir, "icon", icon_name)
        action = QAction(QIcon(icon_path), text, self.iface.mainWindow())
        action.setCheckable(checkable)
        if checkable:
            action.toggled.connect(callback)
            self.tool_group.addAction(action)
        else:
            action.triggered.connect(callback)
        self.toolbar.addAction(action)
        self.actions.append(action)
        return action

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
        s = QSettings()
        for reseau in ('eu', 'ep'):
            if s.value(f"BET_HUMIDE/couche_conduite_{reseau}"):
                return
        from .gui.welcome_dialog import WelcomeDialog
        dlg = WelcomeDialog(self.iface.mainWindow())
        dlg.exec_()
        choice = dlg.chosen()
        if choice == WelcomeDialog.NEW:
            from .tools.projet_bet import save_projet_sous
            save_projet_sous(self, self.iface)
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
        s = QSettings()
        project = QgsProject.instance()
        couches = {}

        for role in ('conduite', 'branchement', 'regard', 'tabouret'):
            setting_key = SKETCHES_PREFIX + f"couche_{role}_{reseau.lower()}"
            layer_id = s.value(setting_key)
            layer = project.mapLayer(layer_id) if layer_id else None

            if not layer:
                layer = self._create_layer(role, reseau)
                project.addMapLayer(layer, False)
                self._get_or_create_group(reseau).addLayer(layer)
                s.setValue(setting_key, layer.id())
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
        if not checked:
            self._deactivate_current()
            return
        from .gui.cubature_dialog import CubatureOptionsDialog, CubatureDialog
        from .config_dialog import get_cubature_config
        from .tools.calc_cubature import calculer_cubature_reseau

        dlg = CubatureOptionsDialog(self.iface.mainWindow())
        if dlg.exec_() != dlg.Accepted:
            self.action_dict['cubature'].setChecked(False)
            return
        opts = dlg.options()
        config = get_cubature_config()

        if opts['bfs'] or opts['axe']:
            couches_eu = self._get_couches("EU")
            couches_ep = self._get_couches("EP")
            if not couches_eu or not couches_ep:
                self.action_dict['cubature'].setChecked(False)
                return
            from .tools.cubature_tool import CubatureTool
            tool = CubatureTool(self.iface.mapCanvas(), self.iface,
                                couches_eu, couches_ep, opts, show_remblai=False)
            self._activate_tool("cubature", tool)
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
                self.action_dict['cubature'].setChecked(False)
                from qgis.PyQt.QtWidgets import QMessageBox
                QMessageBox.information(
                    None, "Cubature tranchées",
                    "Aucun élément trouvé dans le périmètre sélectionné.")
                return

            dlg_result = CubatureDialog(all_results, config, self.iface.mainWindow(),
                                         show_remblai=False)
            dlg_result.show()
            self.action_dict['cubature'].setChecked(False)

    def run_remblai(self, checked):
        if not checked:
            self._deactivate_current()
            return
        from .gui.cubature_dialog import CubatureOptionsDialog, CubatureDialog
        from .config_dialog import get_cubature_config
        from .tools.calc_cubature import calculer_cubature_reseau

        dlg = CubatureOptionsDialog(self.iface.mainWindow())
        dlg.setWindowTitle("Remblai de tranchées")
        if dlg.exec_() != dlg.Accepted:
            self.action_dict['remblai'].setChecked(False)
            return
        opts = dlg.options()
        config = get_cubature_config()

        if opts['bfs'] or opts['axe']:
            couches_eu = self._get_couches("EU")
            couches_ep = self._get_couches("EP")
            if not couches_eu or not couches_ep:
                self.action_dict['remblai'].setChecked(False)
                return
            from .tools.cubature_tool import CubatureTool
            tool = CubatureTool(self.iface.mapCanvas(), self.iface,
                                couches_eu, couches_ep, opts, show_remblai=True)
            self._activate_tool("remblai", tool)
        else:
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
                self.action_dict['remblai'].setChecked(False)
                from qgis.PyQt.QtWidgets import QMessageBox
                QMessageBox.information(
                    None, "Remblai tranchées",
                    "Aucun élément trouvé dans le périmètre sélectionné.")
                return

            dlg_result = CubatureDialog(all_results, config, self.iface.mainWindow(),
                                         show_remblai=True)
            dlg_result.show()
            self.action_dict['remblai'].setChecked(False)

    def run_coupe_tranchee_composee(self):
        from .gui.coupe_tranchee_composee_dialog import CoupeTrancheeComposeeDialog
        dlg = CoupeTrancheeComposeeDialog(self.iface.mainWindow())
        dlg.show()

    def creer_etiquettes(self):
        """Configure le moteur d'étiquettes sur toutes les couches."""
        from .gui.etiquettes import apply_etiquettes, apply_label_size_all, get_force_all_labels
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

        # Réapplique la taille mémorisée
        if label_size:
            apply_label_size_all(self, label_size['unit'], label_size['value'])

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
        set_force_all_labels(checked, self.iface.mapCanvas())

    def run_taille_etiquettes(self):
        from .gui.etiquette_taille_dialog import EtiquetteTailleDialog
        from .gui.etiquettes import apply_label_size_all
        from qgis.PyQt.QtCore import QSettings
        s          = QSettings()
        last_mode  = s.value("BET_HUMIDE/label_size_mode",  "map_units")
        last_value = s.value("BET_HUMIDE/label_size_value", None)
        if last_value is not None:
            try:
                last_value = float(last_value)
            except (ValueError, TypeError):
                last_value = None
        dlg = EtiquetteTailleDialog(last_mode, last_value,
                                    parent=self.iface.mainWindow())
        if dlg.exec_() != EtiquetteTailleDialog.Accepted:
            return
        mode, value = dlg.get_result()
        s.setValue("BET_HUMIDE/label_size_mode",  mode)
        s.setValue("BET_HUMIDE/label_size_value", value)
        apply_label_size_all(self, mode, value)

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

    def run_fond_projet(self):
        import json, tempfile, os, ssl
        import urllib.request
        from qgis.core import (
            QgsRasterLayer, QgsVectorLayer, QgsLayerTreeLayer,
            QgsCoordinateReferenceSystem, QgsCoordinateTransform,
            QgsFillSymbol, QgsLineSymbol, QgsNullSymbolRenderer, QgsSingleSymbolRenderer,
            QgsPalLayerSettings, QgsVectorLayerSimpleLabeling, QgsTextFormat,
            QgsUnitTypes, Qgis,
        )
        from qgis.PyQt.QtWidgets import QApplication
        from qgis.PyQt.QtCore import Qt
        from qgis.PyQt.QtGui import QColor, QFont

        project   = QgsProject.instance()
        tree_root = project.layerTreeRoot()
        canvas    = self.iface.mapCanvas()

        project.setBackgroundColor(QColor(255, 255, 255))
        canvas.setCanvasColor(QColor(255, 255, 255))

        existing = {l.name() for l in project.mapLayers().values()}

        # Ajoute la couche EN BAS de la légende (sous toutes les couches existantes).
        # Les couches EU/EP déjà présentes restent automatiquement en tête.
        # Ordre final légende top→bottom : EU/EP | BAN | Noms | Bâti | Parcelles | OSM | Ortho
        def add_bottom(layer):
            project.addMapLayer(layer, False)
            tree_root.insertChildNode(-1, QgsLayerTreeLayer(layer))

        # --- emprise courante en L93 ---
        ext     = canvas.extent()
        crs_src = canvas.mapSettings().destinationCrs()
        crs_l93 = QgsCoordinateReferenceSystem("EPSG:2154")
        if crs_src.authid().upper() != "EPSG:2154":
            ext = QgsCoordinateTransform(crs_src, crs_l93, project).transformBoundingBox(ext)
        bbox = (f"{ext.xMinimum():.2f},{ext.yMinimum():.2f},"
                f"{ext.xMaximum():.2f},{ext.yMaximum():.2f},EPSG:2154")

        ssl_ctx = ssl.create_default_context()
        ssl_ctx.check_hostname = False
        ssl_ctx.verify_mode    = ssl.CERT_NONE

        def fetch(typename):
            url = (
                "https://data.geopf.fr/wfs/ows?SERVICE=WFS&VERSION=2.0.0"
                f"&REQUEST=GetFeature&TYPENAMES={typename}&BBOX={bbox}"
                "&SRSNAME=EPSG:2154&outputFormat=application/json&COUNT=5000"
            )
            with urllib.request.urlopen(url, timeout=30, context=ssl_ctx) as r:
                return json.loads(r.read().decode('utf-8')).get('features', [])

        def to_layer(features, name):
            tmp = tempfile.NamedTemporaryFile(mode='w', suffix='.geojson', delete=False,
                                              encoding='utf-8', prefix='bet_fdp_')
            json.dump({"type": "FeatureCollection",
                       "crs": {"type": "name", "properties": {"name": "urn:ogc:def:crs:EPSG::2154"}},
                       "features": features}, tmp, ensure_ascii=False)
            tmp.close()
            return QgsVectorLayer(tmp.name, name, "ogr")

        def label_cfg(field, is_expr, placement, size=8, rgb=(50, 50, 50)):
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

        errors = []
        QApplication.setOverrideCursor(Qt.WaitCursor)
        try:
            # 1. BAN Adresses (la plus haute des couches fond de carte)
            if "BAN Adresses" not in existing:
                try:
                    feats = fetch("BAN.DATA.GOUV:ban")
                    if feats:
                        lyr = to_layer(feats, "BAN Adresses")
                        if lyr.isValid():
                            lyr.setRenderer(QgsNullSymbolRenderer())
                            pal = label_cfg('numero', False, Qgis.LabelPlacement.OverPoint, rgb=(30, 30, 30))
                            lyr.setLabeling(QgsVectorLayerSimpleLabeling(pal))
                            lyr.setLabelsEnabled(True)
                            lyr.setMinimumScale(5000)
                            lyr.setScaleBasedVisibility(True)
                            add_bottom(lyr)
                except Exception as e:
                    errors.append(f"BAN:{e}")

            # 2. Noms de rue
            if "Noms de rue BD TOPO" not in existing:
                try:
                    feats = [f for f in fetch("BDTOPO_V3:troncon_de_route")
                             if f.get('properties', {}).get('nom_voie_ban_gauche')
                             or f.get('properties', {}).get('nom_voie_ban_droite')]
                    if feats:
                        lyr = to_layer(feats, "Noms de rue BD TOPO")
                        if lyr.isValid():
                            sym = QgsLineSymbol.createSimple({'color': '0,0,0,0', 'line_style': 'no'})
                            lyr.setRenderer(QgsSingleSymbolRenderer(sym))
                            pal = label_cfg('coalesce("nom_voie_ban_gauche","nom_voie_ban_droite")',
                                            True, Qgis.LabelPlacement.Curved, rgb=(40, 40, 120))
                            lyr.setLabeling(QgsVectorLayerSimpleLabeling(pal))
                            lyr.setLabelsEnabled(True)
                            lyr.setMinimumScale(5000)
                            lyr.setScaleBasedVisibility(True)
                            add_bottom(lyr)
                except Exception as e:
                    errors.append(f"Noms de rue:{e}")

            # 3. PCI Bâti
            if "PCI - Bati" not in existing:
                try:
                    feats = fetch("BDTOPO_V3:batiment")
                    if feats:
                        lyr = to_layer(feats, "PCI - Bati")
                        if lyr.isValid():
                            sym = QgsFillSymbol.createSimple({'color': '160,160,160,128', 'outline_color': '100,100,100,200', 'outline_width': '0.2'})
                            lyr.setRenderer(QgsSingleSymbolRenderer(sym))
                            lyr.setMinimumScale(5000)
                            lyr.setScaleBasedVisibility(True)
                            add_bottom(lyr)
                except Exception as e:
                    errors.append(f"Bâti:{e}")

            # 4. PCI Parcelles
            if "PCI - Parcelles" not in existing:
                try:
                    feats = fetch("BDPARCELLAIRE-VECTEUR_WLD_BDD_WGS84G:parcelle")
                    if feats:
                        lyr = to_layer(feats, "PCI - Parcelles")
                        if lyr.isValid():
                            sym = QgsFillSymbol.createSimple({'color': '0,0,0,0', 'outline_color': '80,80,80,255', 'outline_width': '0.4'})
                            lyr.setRenderer(QgsSingleSymbolRenderer(sym))
                            pal = label_cfg('"section" || "numero"', True, Qgis.LabelPlacement.Horizontal)
                            lyr.setLabeling(QgsVectorLayerSimpleLabeling(pal))
                            lyr.setLabelsEnabled(True)
                            lyr.setMinimumScale(5000)
                            lyr.setScaleBasedVisibility(True)
                            add_bottom(lyr)
                except Exception as e:
                    errors.append(f"Parcelles:{e}")

            # 5. OSM désaturé (cohabite avec Ortho entre 1:1000 et 1:2000)
            osm_name = "OSM Desature"
            if osm_name not in existing:
                lyr = QgsRasterLayer(
                    "crs=EPSG:2154&featureCount=10&format=image/png"
                    "&layers=faded&maxHeight=256&maxWidth=256"
                    "&styles=&url=https://osm.datagrandest.fr/mapcache",
                    osm_name, "wms")
                if lyr.isValid():
                    lyr.setOpacity(0.7)
                    lyr.setMaximumScale(1000)
                    lyr.setScaleBasedVisibility(True)
                    add_bottom(lyr)

            # 6. Ortho 2022 (tout en bas)
            ortho_name = "Ortho 2022"
            if ortho_name not in existing:
                lyr = QgsRasterLayer(
                    "crs=epsg:2154&featureCount=10&format=image/jpeg"
                    "&layers=ortho_2022&maxHeight=256&maxWidth=256"
                    "&styles=&url=http://tiles.craig.fr/ortho/service",
                    ortho_name, "wms")
                if lyr.isValid():
                    lyr.setOpacity(0.75)
                    lyr.setMinimumScale(2000)
                    lyr.setScaleBasedVisibility(True)
                    add_bottom(lyr)

        finally:
            QApplication.restoreOverrideCursor()

        msg = "Fond de projet mis en place"
        if errors:
            msg += " | " + " / ".join(errors)
        self.iface.messageBar().pushMessage("Fond de projet", msg, level=0, duration=6)

    def run_pci_emprise(self):
        import json, tempfile, os, ssl
        import urllib.request
        from qgis.core import (
            QgsVectorLayer, QgsLayerTreeLayer,
            QgsCoordinateReferenceSystem, QgsCoordinateTransform,
            QgsFillSymbol, QgsSingleSymbolRenderer,
            QgsPalLayerSettings, QgsVectorLayerSimpleLabeling, QgsTextFormat,
        )
        from qgis.PyQt.QtWidgets import QApplication, QMessageBox
        from qgis.PyQt.QtCore import Qt
        from qgis.PyQt.QtGui import QColor, QFont

        canvas   = self.iface.mapCanvas()
        extent   = canvas.extent()
        crs_src  = canvas.mapSettings().destinationCrs()
        crs_2154 = QgsCoordinateReferenceSystem("EPSG:2154")

        if crs_src.authid().upper() != "EPSG:2154":
            tr     = QgsCoordinateTransform(crs_src, crs_2154, QgsProject.instance())
            extent = tr.transformBoundingBox(extent)

        bbox = (f"{extent.xMinimum():.2f},{extent.yMinimum():.2f},"
                f"{extent.xMaximum():.2f},{extent.yMaximum():.2f},EPSG:2154")

        LAYERS = [
            ("BDPARCELLAIRE-VECTEUR_WLD_BDD_WGS84G:parcelle", "PCI - Parcelles",
             "https://data.geopf.fr/wfs/ows"),
            ("BDTOPO_V3:batiment", "PCI - Bati",
             "https://data.geopf.fr/wfs/ows"),
        ]

        ssl_ctx = ssl.create_default_context()
        ssl_ctx.check_hostname = False
        ssl_ctx.verify_mode    = ssl.CERT_NONE

        errors    = []
        loaded    = 0
        project   = QgsProject.instance()
        tree_root = project.layerTreeRoot()

        QApplication.setOverrideCursor(Qt.WaitCursor)
        try:
            for typename, layer_name, wfs_url in LAYERS:
                url = (
                    f"{wfs_url}?SERVICE=WFS&VERSION=2.0.0&REQUEST=GetFeature"
                    f"&TYPENAMES={typename}&BBOX={bbox}"
                    f"&SRSNAME=EPSG:2154&outputFormat=application/json&COUNT=5000"
                )
                try:
                    with urllib.request.urlopen(url, timeout=30,
                                                context=ssl_ctx) as resp:
                        data = json.loads(resp.read().decode('utf-8'))
                    features = data.get('features', [])
                    if not features:
                        errors.append(f"{layer_name} : 0 objet dans l'emprise")
                        continue

                    geojson = {
                        "type": "FeatureCollection",
                        "crs":  {"type": "name", "properties": {
                                    "name": "urn:ogc:def:crs:EPSG::2154"}},
                        "features": features,
                    }
                    tmp = tempfile.NamedTemporaryFile(
                        mode='w', suffix='.geojson', delete=False,
                        encoding='utf-8', prefix='bet_pci_')
                    json.dump(geojson, tmp, ensure_ascii=False)
                    tmp.close()

                    layer = QgsVectorLayer(tmp.name, layer_name, "ogr")
                    if not layer.isValid():
                        errors.append(f"{layer_name} : couche invalide")
                        os.unlink(tmp.name)
                        continue

                    project.addMapLayer(layer, False)
                    tree_root.insertChildNode(-1, QgsLayerTreeLayer(layer))
                    loaded += len(features)

                    try:
                        self._style_pci_layer(layer, layer_name)
                    except Exception as se:
                        errors.append(f"style {layer_name} : {se}")

                except Exception as e:
                    errors.append(f"{layer_name} : {e}")

        finally:
            QApplication.restoreOverrideCursor()

        if loaded == 0:
            QMessageBox.warning(
                self.iface.mainWindow(), "PCI Vecteur",
                "Aucune donnée trouvée dans l'emprise courante.\n"
                + "\n".join(errors))
            return

        msg = f"{loaded} objet(s) chargé(s)"
        if errors:
            msg += "  |  Avertissements : " + " / ".join(errors)
        self.iface.messageBar().pushMessage(
            "PCI Vecteur", msg, level=0, duration=5)

    def _style_pci_layer(self, layer, layer_name):
        from qgis.core import (
            QgsFillSymbol, QgsSingleSymbolRenderer,
            QgsPalLayerSettings, QgsVectorLayerSimpleLabeling, QgsTextFormat,
            QgsUnitTypes,
        )
        from qgis.PyQt.QtGui import QColor, QFont

        if "Parcelles" in layer_name:
            # Contour gris, intérieur transparent
            symbol = QgsFillSymbol.createSimple({
                'color':         '0,0,0,0',
                'outline_color': '80,80,80,255',
                'outline_width': '0.4',
            })
            layer.setRenderer(QgsSingleSymbolRenderer(symbol))

                # Label parcelle — 8 pt fixe
            pal = QgsPalLayerSettings()
            pal.fieldName    = '"section" || "numero"'
            pal.isExpression = True
            from qgis.core import Qgis
            pal.placement    = Qgis.LabelPlacement.Horizontal
            pal.enabled      = True

            fmt = QgsTextFormat()
            fmt.setFont(QFont('Arial'))
            fmt.setSizeUnit(QgsUnitTypes.RenderPoints)
            fmt.setSize(8)
            fmt.setColor(QColor(50, 50, 50))
            pal.setFormat(fmt)

            layer.setLabeling(QgsVectorLayerSimpleLabeling(pal))
            layer.setLabelsEnabled(True)
            layer.triggerRepaint()

        elif "Bâti" in layer_name:
            # Gris 50 % opacité
            symbol = QgsFillSymbol.createSimple({
                'color':         '160,160,160,128',
                'outline_color': '100,100,100,200',
                'outline_width': '0.2',
            })
            layer.setRenderer(QgsSingleSymbolRenderer(symbol))

    # ------------------------------------------------------------------ helper WFS

    def _wfs_emprise(self, typename, layer_name,
                     wfs_url="https://data.geopf.fr/wfs/ows"):
        """Charge une couche WFS sur l'emprise courante, la dépose en bas de légende."""
        import json, tempfile, os, ssl
        import urllib.request
        from qgis.core import (
            QgsVectorLayer, QgsLayerTreeLayer,
            QgsCoordinateReferenceSystem, QgsCoordinateTransform,
        )
        from qgis.PyQt.QtWidgets import QApplication, QMessageBox
        from qgis.PyQt.QtCore import Qt

        # Contexte SSL sans vérification (certificats auto-signés sur certains serveurs)
        _ssl_ctx = ssl.create_default_context()
        _ssl_ctx.check_hostname = False
        _ssl_ctx.verify_mode    = ssl.CERT_NONE

        canvas   = self.iface.mapCanvas()
        extent   = canvas.extent()
        crs_src  = canvas.mapSettings().destinationCrs()
        crs_2154 = QgsCoordinateReferenceSystem("EPSG:2154")

        if crs_src.authid().upper() != "EPSG:2154":
            tr     = QgsCoordinateTransform(crs_src, crs_2154, QgsProject.instance())
            extent = tr.transformBoundingBox(extent)

        bbox = (f"{extent.xMinimum():.2f},{extent.yMinimum():.2f},"
                f"{extent.xMaximum():.2f},{extent.yMaximum():.2f},EPSG:2154")

        url = (f"{wfs_url}?SERVICE=WFS&VERSION=2.0.0&REQUEST=GetFeature"
               f"&TYPENAMES={typename}&BBOX={bbox}"
               f"&SRSNAME=EPSG:2154&outputFormat=application/json&COUNT=5000")

        QApplication.setOverrideCursor(Qt.WaitCursor)
        try:
            with urllib.request.urlopen(url, timeout=20,
                                        context=_ssl_ctx) as resp:
                data = json.loads(resp.read().decode('utf-8'))
        except Exception as e:
            QMessageBox.warning(self.iface.mainWindow(), layer_name,
                                f"Erreur lors du chargement WFS :\n{e}")
            return
        finally:
            QApplication.restoreOverrideCursor()

        features = data.get('features', [])
        if not features:
            self.iface.messageBar().pushMessage(
                layer_name, "Aucun objet dans l'emprise courante.",
                level=1, duration=4)
            return

        geojson = {
            "type": "FeatureCollection",
            "crs":  {"type": "name", "properties": {
                        "name": "urn:ogc:def:crs:EPSG::2154"}},
            "features": features,
        }
        tmp = tempfile.NamedTemporaryFile(
            mode='w', suffix='.geojson', delete=False,
            encoding='utf-8', prefix='bet_wfs_')
        json.dump(geojson, tmp, ensure_ascii=False)
        tmp.close()

        layer = QgsVectorLayer(tmp.name, layer_name, "ogr")
        if not layer.isValid():
            QMessageBox.warning(self.iface.mainWindow(), layer_name,
                                "Impossible de créer la couche depuis les données WFS.")
            os.unlink(tmp.name)
            return

        project = QgsProject.instance()
        project.addMapLayer(layer, False)
        project.layerTreeRoot().insertChildNode(-1, QgsLayerTreeLayer(layer))
        self.iface.messageBar().pushMessage(
            layer_name, f"{len(features)} objet(s) chargé(s)",
            level=0, duration=5)

    # ------------------------------------------------------------------ fonds vecteur

    def run_ban_vecteur(self):
        import json, tempfile, os, ssl
        import urllib.request
        from qgis.core import (
            QgsVectorLayer, QgsLayerTreeLayer,
            QgsCoordinateReferenceSystem, QgsCoordinateTransform,
            QgsMarkerSymbol, QgsSingleSymbolRenderer,
            QgsPalLayerSettings, QgsVectorLayerSimpleLabeling, QgsTextFormat,
            QgsUnitTypes,
        )
        from qgis.PyQt.QtWidgets import QApplication, QMessageBox
        from qgis.PyQt.QtCore import Qt
        from qgis.PyQt.QtGui import QColor, QFont

        layer_name = "BAN Adresses"
        canvas   = self.iface.mapCanvas()
        extent   = canvas.extent()
        crs_src  = canvas.mapSettings().destinationCrs()
        crs_2154 = QgsCoordinateReferenceSystem("EPSG:2154")
        if crs_src.authid().upper() != "EPSG:2154":
            tr     = QgsCoordinateTransform(crs_src, crs_2154, QgsProject.instance())
            extent = tr.transformBoundingBox(extent)

        bbox = (f"{extent.xMinimum():.2f},{extent.yMinimum():.2f},"
                f"{extent.xMaximum():.2f},{extent.yMaximum():.2f},EPSG:2154")

        ssl_ctx = ssl.create_default_context()
        ssl_ctx.check_hostname = False
        ssl_ctx.verify_mode    = ssl.CERT_NONE

        url = (
            "https://data.geopf.fr/wfs/ows?SERVICE=WFS&VERSION=2.0.0&REQUEST=GetFeature"
            f"&TYPENAMES=BAN.DATA.GOUV:ban&BBOX={bbox}"
            "&SRSNAME=EPSG:2154&outputFormat=application/json&COUNT=5000"
        )

        QApplication.setOverrideCursor(Qt.WaitCursor)
        try:
            with urllib.request.urlopen(url, timeout=20, context=ssl_ctx) as resp:
                data = json.loads(resp.read().decode('utf-8'))
        except Exception as e:
            QMessageBox.warning(self.iface.mainWindow(), layer_name,
                                f"Erreur WFS :\n{e}")
            return
        finally:
            QApplication.restoreOverrideCursor()

        features = data.get('features', [])
        if not features:
            self.iface.messageBar().pushMessage(
                layer_name, "Aucun objet dans l'emprise.", level=1, duration=4)
            return

        geojson = {
            "type": "FeatureCollection",
            "crs":  {"type": "name", "properties": {
                        "name": "urn:ogc:def:crs:EPSG::2154"}},
            "features": features,
        }
        tmp = tempfile.NamedTemporaryFile(
            mode='w', suffix='.geojson', delete=False,
            encoding='utf-8', prefix='bet_ban_')
        json.dump(geojson, tmp, ensure_ascii=False)
        tmp.close()

        layer = QgsVectorLayer(tmp.name, layer_name, "ogr")
        if not layer.isValid():
            QMessageBox.warning(self.iface.mainWindow(), layer_name,
                                "Couche invalide.")
            os.unlink(tmp.name)
            return

        project = QgsProject.instance()
        project.addMapLayer(layer, False)
        project.layerTreeRoot().insertChildNode(-1, QgsLayerTreeLayer(layer))

        # Point invisible
        from qgis.core import QgsNullSymbolRenderer
        layer.setRenderer(QgsNullSymbolRenderer())

        # Label numéro — 8 pt fixe
        pal = QgsPalLayerSettings()
        pal.fieldName    = 'numero'
        pal.isExpression = False
        from qgis.core import Qgis
        pal.placement    = Qgis.LabelPlacement.OverPoint
        pal.enabled      = True

        fmt = QgsTextFormat()
        fmt.setFont(QFont('Arial'))
        fmt.setSizeUnit(QgsUnitTypes.RenderPoints)
        fmt.setSize(8)
        fmt.setColor(QColor(30, 30, 30))
        pal.setFormat(fmt)

        layer.setLabeling(QgsVectorLayerSimpleLabeling(pal))
        layer.setLabelsEnabled(True)
        layer.triggerRepaint()

        self.iface.messageBar().pushMessage(
            layer_name, f"{len(features)} adresse(s) chargée(s)",
            level=0, duration=5)

    def run_nom_voie(self):
        import json, tempfile, os, ssl
        import urllib.request
        from qgis.core import (
            QgsVectorLayer, QgsLayerTreeLayer,
            QgsCoordinateReferenceSystem, QgsCoordinateTransform,
            QgsLineSymbol, QgsSingleSymbolRenderer,
            QgsPalLayerSettings, QgsVectorLayerSimpleLabeling, QgsTextFormat,
            QgsUnitTypes, Qgis,
        )
        from qgis.PyQt.QtWidgets import QApplication, QMessageBox
        from qgis.PyQt.QtCore import Qt
        from qgis.PyQt.QtGui import QColor, QFont

        layer_name = "Noms de rue BD TOPO"
        canvas   = self.iface.mapCanvas()
        extent   = canvas.extent()
        crs_src  = canvas.mapSettings().destinationCrs()
        crs_2154 = QgsCoordinateReferenceSystem("EPSG:2154")
        if crs_src.authid().upper() != "EPSG:2154":
            tr     = QgsCoordinateTransform(crs_src, crs_2154, QgsProject.instance())
            extent = tr.transformBoundingBox(extent)

        bbox = (f"{extent.xMinimum():.2f},{extent.yMinimum():.2f},"
                f"{extent.xMaximum():.2f},{extent.yMaximum():.2f},EPSG:2154")

        ssl_ctx = ssl.create_default_context()
        ssl_ctx.check_hostname = False
        ssl_ctx.verify_mode    = ssl.CERT_NONE

        url = (
            "https://data.geopf.fr/wfs/ows?SERVICE=WFS&VERSION=2.0.0&REQUEST=GetFeature"
            f"&TYPENAMES=BDTOPO_V3:troncon_de_route&BBOX={bbox}"
            "&SRSNAME=EPSG:2154&outputFormat=application/json&COUNT=5000"
        )

        QApplication.setOverrideCursor(Qt.WaitCursor)
        try:
            with urllib.request.urlopen(url, timeout=30, context=ssl_ctx) as resp:
                data = json.loads(resp.read().decode('utf-8'))
        except Exception as e:
            QMessageBox.warning(self.iface.mainWindow(), layer_name,
                                f"Erreur WFS :\n{e}")
            return
        finally:
            QApplication.restoreOverrideCursor()

        # Ne garder que les tronçons avec un nom
        features = [
            f for f in data.get('features', [])
            if f.get('properties', {}).get('nom_voie_ban_gauche')
            or f.get('properties', {}).get('nom_voie_ban_droite')
        ]
        if not features:
            self.iface.messageBar().pushMessage(
                layer_name, "Aucun nom de rue dans l'emprise.", level=1, duration=4)
            return

        geojson = {
            "type": "FeatureCollection",
            "crs":  {"type": "name", "properties": {
                        "name": "urn:ogc:def:crs:EPSG::2154"}},
            "features": features,
        }
        tmp = tempfile.NamedTemporaryFile(
            mode='w', suffix='.geojson', delete=False,
            encoding='utf-8', prefix='bet_rue_')
        json.dump(geojson, tmp, ensure_ascii=False)
        tmp.close()

        layer = QgsVectorLayer(tmp.name, layer_name, "ogr")
        if not layer.isValid():
            QMessageBox.warning(self.iface.mainWindow(), layer_name, "Couche invalide.")
            os.unlink(tmp.name)
            return

        project = QgsProject.instance()
        project.addMapLayer(layer, False)
        project.layerTreeRoot().insertChildNode(-1, QgsLayerTreeLayer(layer))

        # Ligne transparente
        symbol = QgsLineSymbol.createSimple({
            'color': '0,0,0,0', 'line_style': 'no'
        })
        layer.setRenderer(QgsSingleSymbolRenderer(symbol))

        # Label nom de rue courbé le long de la ligne — 8 pt fixe
        pal = QgsPalLayerSettings()
        pal.fieldName    = 'coalesce("nom_voie_ban_gauche", "nom_voie_ban_droite")'
        pal.isExpression = True
        pal.placement    = Qgis.LabelPlacement.Curved
        pal.enabled      = True

        fmt = QgsTextFormat()
        fmt.setFont(QFont('Arial'))
        fmt.setSizeUnit(QgsUnitTypes.RenderPoints)
        fmt.setSize(8)
        fmt.setColor(QColor(40, 40, 120))
        pal.setFormat(fmt)

        layer.setLabeling(QgsVectorLayerSimpleLabeling(pal))
        layer.setLabelsEnabled(True)
        layer.triggerRepaint()

        self.iface.messageBar().pushMessage(
            layer_name, f"{len(features)} tronçon(s) nommé(s) chargé(s)",
            level=0, duration=5)



    def run_ortho_2022(self):
        from qgis.core import QgsRasterLayer, QgsLayerTreeLayer
        name   = "Ortho 2022"
        source = (
            "crs=epsg:2154&featureCount=10&format=image/jpeg"
            "&layers=ortho_2022&maxHeight=256&maxWidth=256"
            "&styles=&url=http://tiles.craig.fr/ortho/service"
        )
        project = QgsProject.instance()
        for lyr in project.mapLayers().values():
            if lyr.name() == name:
                return
        layer = QgsRasterLayer(source, name, "wms")
        if not layer.isValid():
            from qgis.PyQt.QtWidgets import QMessageBox
            QMessageBox.warning(self.iface.mainWindow(), "Fond de carte",
                                f"Impossible de charger la couche WMS :\n{name}")
            return
        project.addMapLayer(layer, False)
        project.layerTreeRoot().insertChildNode(-1, QgsLayerTreeLayer(layer))

    def run_osm_desature(self):
        from qgis.core import QgsRasterLayer, QgsLayerTreeLayer
        name   = "OSM Desature"
        source = (
            "crs=EPSG:2154&featureCount=10&format=image/png"
            "&layers=faded&maxHeight=256&maxWidth=256"
            "&styles=&url=https://osm.datagrandest.fr/mapcache"
        )
        project = QgsProject.instance()
        # Évite les doublons
        for lyr in project.mapLayers().values():
            if lyr.name() == name:
                return
        layer = QgsRasterLayer(source, name, "wms")
        if not layer.isValid():
            from qgis.PyQt.QtWidgets import QMessageBox
            QMessageBox.warning(self.iface.mainWindow(), "Fond de carte",
                                f"Impossible de charger la couche WMS :\n{name}")
            return
        # Ajout en bas de la légende (fond de carte sous toutes les couches)
        project.addMapLayer(layer, False)
        project.layerTreeRoot().insertChildNode(-1, QgsLayerTreeLayer(layer))

    def run_enregistrer_projet(self):
        from .tools.projet_bet import save_projet
        save_projet(self, self.iface)

    def run_enregistrer_projet_sous(self):
        from .tools.projet_bet import save_projet_sous
        save_projet_sous(self, self.iface)

    def run_charger_projet(self):
        from .tools.projet_bet import load_projet
        load_projet(self, self.iface)

    def run_imprimer(self):
        from .gui.export_dialog import ExportDialog
        from .tools.projet_bet import project_dir

        dlg_export = ExportDialog(self.iface.mainWindow(),
                                  default_dir=project_dir())
        if dlg_export.exec_() != ExportDialog.Accepted:
            return
        choices = dlg_export.get_choices()

        do_plan_pdf  = choices['plan_pdf']
        do_plan_dxf  = choices['plan_dxf']
        do_profil_eu  = choices['profil_eu']
        do_profil_ep  = choices['profil_ep']
        do_profil_grp = choices['profil_groupe']

        if not any([do_plan_pdf, do_plan_dxf, do_profil_eu, do_profil_ep, do_profil_grp]):
            return

        # ── Profils en long (export immédiat, sans interaction carte) ──────
        if do_profil_eu or do_profil_ep or do_profil_grp:
            self._export_profils_batch(choices)

        # ── Plan PDF/DXF → PrintDialog + PrintTool ─────────────────────────
        if not do_plan_pdf and not do_plan_dxf:
            return

        out_dir = choices.get('output_dir')

        if do_plan_dxf and not do_plan_pdf:
            self._export_dxf_direct(out_dir=out_dir)
            return

        from .gui.print_dialog import PrintDialog
        from .tools.print_tool import PrintTool
        from qgis.core import QgsUnitTypes

        dlg = PrintDialog(self.iface.mainWindow())
        if dlg.exec_() != PrintDialog.Accepted:
            return

        settings = dlg.get_settings()
        settings['do_pdf']     = do_plan_pdf
        settings['do_dxf']     = do_plan_dxf
        settings['output_dir'] = out_dir

        crs = self.iface.mapCanvas().mapSettings().destinationCrs()
        if crs.mapUnits() != QgsUnitTypes.DistanceMeters:
            from qgis.PyQt.QtWidgets import QMessageBox
            QMessageBox.warning(
                self.iface.mainWindow(), "Impression",
                f"Le CRS du projet ({crs.authid()}) n'est pas en mètres.\n"
                "Les dimensions des feuilles risquent d'être incorrectes.\n"
                "Recommandé : EPSG:2154 (RGF93 / Lambert-93).",
            )

        tool = PrintTool(self.iface.mapCanvas(), self.iface, settings)
        self._cleanup_tools()
        self.iface.mapCanvas().setMapTool(tool)
        self.tools['imprimer'] = tool

        fmt = settings['format']
        ori = settings['orientation']
        ech = settings['echelle']
        self.iface.messageBar().pushMessage(
            "Impression",
            f"{fmt} {ori}  ·  1:{ech:,}  —  "
            "1er clic : ancrer  ·  orienter  ·  2e clic : fixer  |  Clic droit : exporter  |  Échap : changer l'échelle".replace(",", " "),
            level=0, duration=0,
        )

    def _export_profils_batch(self, choices):
        """Export batch des profils en long vers des PDF dans le dossier choisi."""
        import os
        from qgis.PyQt.QtWidgets import QApplication, QMessageBox
        from qgis.PyQt.QtCore import Qt

        out_dir = choices.get('output_dir')
        if not out_dir or not os.path.isdir(out_dir):
            return

        QApplication.setOverrideCursor(Qt.WaitCursor)
        msgs = []
        try:
            from .tools.profil_batch import export_profils_eu_ep, export_profils_groupe

            if choices['profil_eu']:
                couches_eu = self._get_couches("EU")
                n_ok, n_skip, out_path = export_profils_eu_ep(
                    couches_eu, "EU", choices['profil_eu_format'], out_dir)
                if n_ok:
                    msgs.append(f"Profils EU : {n_ok} page(s) → {os.path.basename(out_path)}")
                else:
                    msgs.append("Profils EU : aucune conduite trouvée")

            if choices['profil_ep']:
                couches_ep = self._get_couches("EP")
                n_ok, n_skip, out_path = export_profils_eu_ep(
                    couches_ep, "EP", choices['profil_ep_format'], out_dir)
                if n_ok:
                    msgs.append(f"Profils EP : {n_ok} page(s) → {os.path.basename(out_path)}")
                else:
                    msgs.append("Profils EP : aucune conduite trouvée")

            if choices['profil_groupe']:
                couches_eu = self._get_couches("EU")
                couches_ep = self._get_couches("EP")
                ok, out_path = export_profils_groupe(
                    couches_eu, couches_ep, choices['profil_groupe_format'], out_dir,
                    reseau_ref=choices['profil_groupe_reseau'])
                msgs.append(
                    f"Profil groupé → {os.path.basename(out_path)}" if ok
                    else "Profil groupé : aucune conduite trouvée")

        except Exception as e:
            msgs.append(f"Erreur : {e}")
        finally:
            QApplication.restoreOverrideCursor()

        if msgs:
            QMessageBox.information(
                self.iface.mainWindow(),
                "Export profils terminé",
                "\n".join(msgs) + f"\n\nDossier : {out_dir}",
            )

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
                "Exporter le plan en DXF 2018",
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

    def run_import_star_dt(self):
        from .gui.star_dt_dialog import StarDtDialog
        from .tools.star_dt_import import import_star_dt
        dlg = StarDtDialog(self.iface.mainWindow())
        if dlg.exec_() != StarDtDialog.Accepted:
            return
        path = dlg.file_path()
        out = dlg.output_path()
        types = dlg.get_selected_types()
        if not path or not types or not out:
            return
        try:
            created = import_star_dt(path, out, selected_types=types)
        except Exception as e:
            from qgis.PyQt.QtWidgets import QMessageBox
            QMessageBox.warning(
                self.iface.mainWindow(), "Star-DT",
                f"Erreur lors de l'import :\n{e}")
            return
        if created:
            self.iface.messageBar().pushMessage(
                "Star-DT",
                f"{len(created)} couche(s) importee(s) dans {out}",
                level=0, duration=5)
        else:
            self.iface.messageBar().pushMessage(
                "Star-DT", "Aucun element a importer.",
                level=1, duration=4)

    def show_config_dialog(self):
        from .config_dialog import ConfigDialog
        dialog = ConfigDialog(self.iface)
        dialog.exec_()