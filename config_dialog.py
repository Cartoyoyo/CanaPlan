# Re-export depuis gui/config_dialog — le code vit dans gui/config_dialog.py
from .gui.config_dialog import (  # noqa: F401
    ConfigDialog,
    get_default_params,
    get_cubature_config,
    SKETCHES_PREFIX,
    SETTINGS_KEY,
    MATERIAUX,
    MATERIAUX_REMBLAI,
    INITIAL_DEFAULTS,
    ROLES,
    LABELS,
    TrenchSchemaWidget,
    CubatureSchemaWidget,
    NetworkSchemaWidget,
)
