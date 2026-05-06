from qgis.PyQt import sip


def layer_ok(layer):
    """Retourne True si l'objet QgsVectorLayer C++ est encore vivant."""
    return layer is not None and not sip.isdeleted(layer)
