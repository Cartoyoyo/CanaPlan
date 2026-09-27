# tools/schemaep/__init__.py
"""SchemAEP : concepteur de schémas de pièces AEP (eau potable).

Portage Python de la page HTML SchemAEP (projet indépendant). Le moteur
(catalogue, raccordements, contrôles, nomenclature) est en Python pur, sans
Qt ni QGIS, pour être testé seul ; l'interface Qt s'appuie dessus.

Le format de fichier .json est celui de la page HTML : un schéma s'ouvre
dans l'une ou l'autre version.
"""
