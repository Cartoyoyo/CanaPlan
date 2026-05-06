# -*- coding: utf-8 -*-
"""
Bridge between CadToGisDialog and the AnotherDXF2Shape OGR engine.
"""

import os
import uuid

from qgis.core import (
    QgsCoordinateReferenceSystem, QgsVectorFileWriter,
    QgsCoordinateTransformContext, QgsVectorLayer, QgsProject,
)
from qgis.PyQt.QtCore import QSettings

from .fnc4all import (
    EZUTempDir, addFehler, getFehler, resetFehler,
    addHinweis, getHinweis, resetHinweis, hinweislog,
)
from .qt_compat import QGIS_VERSION_INT
from .clsDXFTools import EineDXF, ProjDaten4Dat


class UIAdapter:
    """Maps CadToGisDialog.log() onto the progress interface expected by EineDXF."""

    def __init__(self, log_fn):
        self._log = log_fn

    def FormRunning(self, b):        pass
    def SetDatAktionGesSchritte(self, n): pass
    def SetDatAktionText(self, s):   self._log(str(s) if s else "")
    def SetDatAktionAktSchritt(self, n): pass
    def SetAktionGesSchritte(self, n): pass
    def SetAktionText(self, s):      self._log(str(s) if s else "")
    def SetAktionAktSchritt(self, n): pass


def run_adxf_import(
    dxf_path: str,
    out_path: str,
    src_epsg,                    # int or str like "IGNF:RGF93CC46"
    out_form: str,               # "GPKG" or "SHP"
    log_fn,                      # callable(str)
    target_layers=None,          # list[str] or None → all layers
    overwrite: bool = False,
    by_layer: bool = True,       # split output by DXF layer name
    format_text: bool = True,    # parse text size/font/underline
    use_color_line: bool = True,
    use_color_poly: bool = False,
    use_color_point: bool = False,
    txt_factor: float = 1.0,     # text size multiplier
    charset: str = "utf-8",
    gen_3d: bool = False,
    raw_code: bool = False,
):
    """
    Import a DXF using the OGR/GDAL QGIS Processing engine.

    Returns the output directory / GPKG path actually written.
    """
    def say(s):
        try:
            log_fn(str(s) if s else "")
        except Exception:
            pass

    ui = UIAdapter(say)

    # Normalise output directory
    if out_form == "GPKG":
        out_dir = os.path.dirname(os.path.abspath(out_path)).replace("\\", "/") + "/"
    else:
        out_dir = os.path.abspath(out_path).replace("\\", "/").rstrip("/") + "/"

    os.makedirs(out_dir, exist_ok=True)

    # Build source CRS
    if isinstance(src_epsg, int) or (isinstance(src_epsg, str) and str(src_epsg).isdigit()):
        crs_str = f"EPSG:{src_epsg}"
    else:
        crs_str = str(src_epsg) if src_epsg else "EPSG:4326"
    src_crs = QgsCoordinateReferenceSystem(crs_str)
    if not src_crs.isValid():
        src_crs = QgsCoordinateReferenceSystem("EPSG:4326")
        say(f"CRS '{crs_str}' invalid, falling back to EPSG:4326")

    # Persist / restore QGIS projection settings
    crs_art1   = QSettings().value('/Projections/defaultBehavior')
    crs_art2   = QSettings().value('/app/projections/unknownCrsBehavior')
    crs_defval = QSettings().value('/Projections/layerDefaultCrs')
    QSettings().setValue('/Projections/defaultBehavior',         'useGlobal')
    QSettings().setValue('/app/projections/unknownCrsBehavior',  'UseDefaultCrs')
    QSettings().setValue('/Projections/layerDefaultCrs',          src_crs.authid())

    # Create a temp memory layer → get its .prj file for SHP output
    mem_lay  = QgsVectorLayer(f'LineString?crs={src_crs.authid()}', '', 'memory')
    mem_shp  = EZUTempDir() + str(uuid.uuid4()) + '.shp'
    if QGIS_VERSION_INT < 31003:
        QgsVectorFileWriter.writeAsVectorFormat(
            mem_lay, mem_shp, None, mem_lay.crs(), "ESRI Shapefile")
    else:
        opts = QgsVectorFileWriter.SaveVectorOptions()
        opts.driverName = "ESRI Shapefile"
        QgsVectorFileWriter.writeAsVectorFormatV2(
            mem_lay, mem_shp, QgsCoordinateTransformContext(), opts)

    qprj = mem_shp[:-3] + 'qpj'
    if not os.path.exists(qprj):
        qprj = mem_shp[:-3] + 'prj'

    resetFehler()
    resetHinweis()

    try:
        AktList, AktOpt, ProjektName, Kern = ProjDaten4Dat(
            dxf_path, False, by_layer, True, out_form)

        # Remove any pre-existing group with the same name
        rNode = QgsProject.instance().layerTreeRoot()
        for node in list(rNode.children()):
            if str(type(node)) == "<class 'qgis._core.QgsLayerTreeGroup'>":
                if node.name() == ProjektName:
                    rNode.removeChildNode(node)

        # Overwrite existing GPKG if requested
        if overwrite and out_form == "GPKG":
            candidate = out_dir + Kern + '.gpkg'
            if os.path.exists(candidate):
                try:
                    os.remove(candidate)
                except Exception:
                    pass

        say(f"<b>Engine OGR/GDAL — {out_form} — {os.path.basename(dxf_path)}</b>")
        try:
            iface.mapCanvas().setRenderFlag(False)
        except Exception:
            pass

        grpProjekt = rNode.addGroup(ProjektName)
        grpProjekt.setExpanded(True)

        EineDXF(
            uiParent        = ui,
            mLay_crs        = mem_lay.crs(),
            bZielSave       = True,
            sOutForm        = out_form,
            grpProjekt      = grpProjekt,
            AktList         = AktList,
            Kern            = Kern,
            AktOpt          = AktOpt,
            DXFDatNam       = dxf_path,
            zielPfadOrDatei = out_dir,
            qPrjDatName     = qprj,
            sOrgCharSet     = charset,
            bLayer          = by_layer,
            bFormatText     = format_text,
            bUseColor4Point = use_color_point,
            bUseColor4Line  = use_color_line,
            bUseColor4Poly  = use_color_poly,
            dblFaktor       = txt_factor,
            chkTransform    = False,
            DreiPassPunkte  = None,
            bGen3D          = gen_3d,
            txtErsatz4Tab   = ' ',
            bRawCode        = raw_code,
            target_layers   = target_layers,
        )

    except Exception as ex:
        import traceback as _tb
        say(f"<span style='color:#b00'><b>Error:</b> {ex}</span>")
        say(f"<pre>{_tb.format_exc()}</pre>")
    finally:
        QSettings().setValue('/Projections/defaultBehavior',        crs_art1)
        QSettings().setValue('/app/projections/unknownCrsBehavior', crs_art2)
        QSettings().setValue('/Projections/layerDefaultCrs',         crs_defval)

    # Report warnings / errors
    for h in getHinweis():
        say(f"<i>Note: {h}</i>")
    for e in getFehler():
        say(f"<span style='color:#b00'>Error: {e}</span>")
    resetFehler()
    resetHinweis()

    # Clean up temp memory shapefile
    base = mem_shp[:-4]
    for ext in ('.shp', '.shx', '.dbf', '.prj', '.qpj', '.cpg'):
        try:
            f = base + ext
            if os.path.exists(f):
                os.remove(f)
        except Exception:
            pass

    say("<b>Done.</b>")

    # Return path info (best-effort)
    if out_form == "GPKG":
        return out_dir + Kern + '.gpkg'
    return out_dir
