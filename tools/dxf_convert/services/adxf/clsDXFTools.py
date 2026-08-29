# -*- coding: utf-8 -*-
# Adapted from AnotherDXF2Shape/clsDXFTools.py
# Changes:
#   - relative imports updated (fnc4ADXF2Shape → fnc4adxf)
#   - EineDXF gains optional target_layers parameter for SQL layer filtering

import os, uuid
from glob import glob
from shutil import copyfile, move

from qgis.core import *
from qgis.utils import *
from qgis.PyQt.QtWidgets import QMessageBox
from qgis.PyQt.QtCore import QCoreApplication, QSettings
from qgis.PyQt.QtSql import QSqlDatabase, QSqlQuery, QSqlError

from .qt_compat import QT6, QGIS3, QGIS4, QGIS_VERSION_INT, MsgBox_Yes, MsgBox_No
from .fnc4all import *
from .fnc4adxf import *
from .clsDBase import *
from .TransformTools import *
from .... import errlog


def tr(message):
    return QCoreApplication.translate('clsDXFTools', message)


def EditQML(datname):
    with open(datname, 'r') as f:
        data = f.read()
    data = data.replace('labelsEnabled="0"', 'labelsEnabled="1"')
    with open(datname, 'w') as f:
        f.write(data)


def labelingDXF(qLayer, bFormatText, bUseColor4Point, dblFaktor):
    qLayer.setCustomProperty("labeling", "pal")
    qLayer.setCustomProperty("labeling/displayAll", "true")
    qLayer.setCustomProperty("labeling/enabled", "true")
    if bFormatText:
        qLayer.setCustomProperty("labeling/fieldName", "plaintext")
        qLayer.setCustomProperty("labeling/dataDefined/Underline", "1~~1~~\"underline\"~~")
        qLayer.setCustomProperty("labeling/dataDefined/Bold",      "1~~1~~\"bold\"~~")
        qLayer.setCustomProperty("labeling/dataDefined/Italic",    "1~~1~~\"italic\"~~")
    else:
        qLayer.setCustomProperty("labeling/fieldName", "Text")
    if bUseColor4Point:
        qLayer.setCustomProperty("labeling/dataDefined/Color", "1~~1~~\"color\"~~")
    sf = "%.1f" % dblFaktor
    sf = "1~~1~~" + sf + " * \"size\"~~"
    qLayer.setCustomProperty("labeling/dataDefined/Size",   sf)
    qLayer.setCustomProperty("labeling/dataDefined/Family", "1~~1~~\"font\"~~")
    qLayer.setCustomProperty("labeling/fontSizeInMapUnits", "True")
    qLayer.setCustomProperty("labeling/fontSizeUnit",       "MapUnit")
    qLayer.setCustomProperty("labeling/dataDefined/Rotation", "1~~1~~\"angle\"~~")
    qLayer.setCustomProperty("labeling/dataDefined/OffsetQuad", "1~~1~~\"anchor\"~~")
    sf = "%.1f" % dblFaktor
    sf = sf + " * \"size\""
    qLayer.setCustomProperty(
        "labeling/dataDefined/OffsetXY",
        "1~~1~~array(\"dx\"+" + sf + "/4*sin(if(\"angle\" is NULL,0,\"angle\")*pi()/180),-\"dy\"+"+sf+"/4*cos(if(\"angle\" is NULL,0,\"angle\")*pi()/180))~~"
    )
    qLayer.setCustomProperty("labeling/obstacle", "false")
    qLayer.setCustomProperty("labeling/placement", "1")
    qLayer.setCustomProperty("labeling/placementFlags", "0")
    qLayer.setCustomProperty("labeling/textTransp", "0")
    qLayer.setCustomProperty("labeling/upsidedownLabels", "2")
    qLayer.removeCustomProperty("labeling/ddProperties")


def kat4Layer(layer, bUseColor4Line, bUseColor4Poly):
    fni = layer.dataProvider().fieldNameIndex('Layer')
    unique_values = layer.dataProvider().uniqueValues(fni)
    categories = []
    for AktLayerNam in unique_values:
        if AktLayerNam == NULL:
            AktLayerNam = ""
        symbol = QgsSymbol.defaultSymbol(layer.geometryType())
        layer_style = {}
        symbol_layer = None
        if layer.geometryType() == 1 and bUseColor4Line:
            layer_style = {"color_dd_active":"1","color_dd_expression":"\"color\"","color_dd_field":"color","color_dd_useexpr":"0"}
            symbol_layer = QgsSimpleLineSymbolLayer.create(layer_style)
        if layer.geometryType() == 2 and bUseColor4Poly:
            layer_style = {"color_dd_active":"1","color_dd_expression":"\"fcolor\"","color_dd_field":"fcolor","color_dd_useexpr":"0","outline":"1, 234, 3"}
            symbol_layer = QgsSimpleFillSymbolLayer.create(layer_style)
        layer.setOpacity(0.5)
        if symbol_layer is not None:
            symbol.changeSymbolLayer(0, symbol_layer)
        if layer.geometryType() == 0:
            symbol.setSize(0.1)
        categories.append(QgsRendererCategory(AktLayerNam, symbol, AktLayerNam))
    return QgsCategorizedSymbolRenderer('Layer', categories)


def DelShapeDatBlock(shpDat):
    try:
        os.remove(shpDat)
        for rest in glob(shpDat[0:-4] + '.*'):
            os.remove(rest)
        return True
    except OSError as _err:
        errlog.ignored(_err, "clsDXFTools.DelShapeDatBlock:103")


def DelZielDateien(delDatArr, sOutForm):
    if not delDatArr:
        return True
    s = "\n".join(delDatArr)
    antw = QMessageBox.question(None, tr("Overwriting the following files"), s, MsgBox_Yes | MsgBox_No, MsgBox_No)
    if antw != MsgBox_Yes:
        return None
    for dat in delDatArr:
        try:
            os.remove(dat)
            if sOutForm == "SHP":
                base = os.path.splitext(dat)[0]
                for rest in glob(base + '.*'):
                    if os.path.exists(rest):
                        os.remove(rest)
        except OSError as e:
            QMessageBox.critical(None, tr("DZD: file remove error"), f"Error: {e.filename} - {e.strerror}.")
            return None
    return True


def ProjDaten4Dat(AktDXFDatNam, bCol, bLayer, bZielSave, sOutForm):
    pList1 = (
        "P:POINT:LIKE '%POINT%'",
        "L:LINESTRING:LIKE '%LINE%'",
        "F:POLYGON:LIKE '%POLYGON%'",
    )
    o1 = " --config DXF_TRANSLATE_ESCAPE_SEQUENCES FALSE --config DXF_MERGE_BLOCK_GEOMETRIES FALSE --config DXF_INLINE_BLOCKS TRUE "
    pList2 = (
        "eP:POINT:LIKE '%POINT%'",
        "eL:LINESTRING:LIKE '%LINE%'",
        "eF:POLYGON:LIKE '%POLYGON%'",
        "cP:POINT:= 'GEOMETRYCOLLECTION'",
        "cL:LINESTRING:= 'GEOMETRYCOLLECTION'",
        "cF:POLYGON:= 'GEOMETRYCOLLECTION'",
    )
    o2 = " --config DXF_TRANSLATE_ESCAPE_SEQUENCES FALSE --config DXF_MERGE_BLOCK_GEOMETRIES TRUE --config DXF_INLINE_BLOCKS TRUE -dim 2 "
    (dummy, ProjektName) = os.path.split(AktDXFDatNam)
    ProjektName = ProjektName + '_' + sOutForm
    if bCol:
        AktList = pList2; AktOpt = o2; ProjektName += '(GC-'
    else:
        AktList = pList1; AktOpt = o1; ProjektName += '('
    ProjektName += 'byLay)' if bLayer else 'byKat)'
    if bZielSave:
        Kern = ProjektName[0:-4] if ProjektName[-4:] == ".dxf" else ProjektName
    else:
        Kern = str(uuid.uuid4())
    return AktList, AktOpt, ProjektName, Kern


def _layer_in_clause(target_layers):
    """Clause « AND Layer IN (...) » pour l'option -sql d'ogr2ogr.

    Deux niveaux de citation s'empilent ici, et c'est le piege : la clause
    part dans -sql "select ... where ...", donc entre GUILLEMETS, et les noms
    de calques y sont entre APOSTROPHES. Doubler les apostrophes (ce que fait
    la ligne ci-dessous) protege la chaine SQL, mais pas l'option : un nom
    contenant un guillemet refermerait le -sql et la suite du nom serait lue
    comme des options ogr2ogr supplementaires.

    Les noms viennent soit du DXF, soit du parametre « layers » saisi a la
    main dans l'algorithme de traitement — donc d'une source non maitrisee.
    Le guillemet etant de toute facon interdit dans un nom de calque DXF, on
    ecarte ces noms au lieu d'essayer de les echapper.
    """
    noms = [str(l) for l in target_layers if '"' not in str(l)]
    ecartes = [str(l) for l in target_layers if '"' in str(l)]
    if ecartes:
        addHinweis(tr("Layer name with a quote character ignored: ")
                   + ", ".join(ecartes))
    if not noms:
        return ""
    in_list = ",".join("'" + n.replace("'", "''") + "'" for n in noms)
    return " AND Layer IN (" + in_list + ")"


def EineDXF(uiParent, mLay_crs, bZielSave, sOutForm, grpProjekt, AktList, Kern, AktOpt,
            DXFDatNam, zielPfadOrDatei, qPrjDatName, sOrgCharSet, bLayer, bFormatText,
            bUseColor4Point, bUseColor4Line, bUseColor4Poly, dblFaktor,
            chkTransform, DreiPassPunkte, bGen3D, txtErsatz4Tab, bRawCode,
            target_layers=None):
    """
    Import one DXF via OGR/GDAL Processing into QGIS.

    target_layers: optional list of DXF layer names to import (None = all).
    """
    import processing
    from processing.core.Processing import Processing

    if sOutForm not in ("SHP", "GPKG"):
        errbox("Formatfehler: '" + sOutForm + "'")
        return False

    sCharSet = sOrgCharSet
    myGroups = {}

    # Build layers SQL clause
    layers_sql = _layer_in_clause(target_layers) if target_layers else ""

    if ifAscii(DXFDatNam):
        korrDXFDatNam = DXFDatNam
    else:
        uiParent.SetAktionGesSchritte(2)
        uiParent.SetAktionText(tr("Copy DXF-File"))
        uiParent.SetAktionAktSchritt(1)
        korrDXFDatNam = EZUTempDir() + str(uuid.uuid4()) + '.dxf'
        copyfile(DXFDatNam, korrDXFDatNam)

    optGCP = ""
    if chkTransform and DreiPassPunkte:
        for p in range(len(DreiPassPunkte)):
            optGCP += " -gcp "
            for k in range(len(DreiPassPunkte[p])):
                optGCP += str(DreiPassPunkte[p][k][0]) + " " + str(DreiPassPunkte[p][k][1]) + " "
        if optGCP[-5:] == "-gcp ":
            optGCP = optGCP[:-5]

    zE = 0
    uiParent.SetAktionGesSchritte(len(AktList))

    if sOutForm == "GPKG":
        gpkgdat = zielPfadOrDatei + Kern + '.gpkg'
        korrGPKGDatNam = gpkgdat if bZielSave else (EZUTempDir() + str(uuid.uuid4()) + '.gpkg')

    for p in AktList:
        zE += 1
        v = p.split(":")
        uiParent.SetAktionText(tr("Edit Entity: " + Kern + v[0]))
        uiParent.SetAktionAktSchritt(zE)

        if sOutForm == "SHP":
            iOutForm = 0
            shpdat  = zielPfadOrDatei + Kern + v[0] + '.shp'
            qmldat  = zielPfadOrDatei + Kern + v[0] + '.qml'
        if sOutForm == "GPKG":
            qmldat   = EZUTempDir() + str(uuid.uuid4()) + '.qml'
            gpkgTable = Kern + v[0]

        if sOutForm == "SHP":
            if bZielSave:
                korrSHPDatNam = EZUTempDir() + str(uuid.uuid4()) + '.shp'
            else:
                korrSHPDatNam = shpdat

        bKonvOK = False
        try:
            if sOutForm == "SHP":
                # SQL du dialecte OGR sur un fichier DXF, pas une base de
                # donnees : -sql est le seul moyen d'obtenir le pseudo-champ
                # ogr_style. Seul layers_sql est variable, et il est construit
                # par _layer_in_clause() qui gere les deux niveaux de citation.
                opt = ('-skipfailures %s -nlt %s %s -sql "select *, ogr_style from entities where OGR_GEOMETRY %s%s"') % (  # nosec B608
                    AktOpt, v[1], optGCP, v[2], layers_sql)
                if bGen3D:
                    opt += ' -dim 3 '
                pList = {'INPUT': korrDXFDatNam, 'OPTIONS': opt, 'OUTPUT': korrSHPDatNam}
                pAntw = processing.run('gdal:convertformat', pList)
                if os.path.exists(korrSHPDatNam):
                    bKonvOK = True

            if sOutForm == "GPKG":
                if sCharSet == "System":
                    import locale as _loc
                    ogrCharSet = _loc.getdefaultlocale()[1]
                else:
                    ogrCharSet = sCharSet
                ogrCharSet = ogrCharSet.upper()
                opt = '-append -update --config DXF_ENCODING "' + ogrCharSet + '" '
                if mLay_crs.toProj4() != "":
                    opt += '-a_srs "' + mLay_crs.toProj4() + '" '
                if bRawCode:
                    opt += '--config DXF_INCLUDE_RAW_CODE_VALUES TRUE '
                # Meme remarque que pour SHP ci-dessus.
                opt += ('%s -nlt %s %s -sql "select *, ogr_style from entities where OGR_GEOMETRY %s%s" -nln "%s"') % (  # nosec B608
                    AktOpt, v[1], optGCP, v[2], layers_sql, gpkgTable)
                if bGen3D:
                    opt += ' -dim 3 '
                pList = {'INPUT': korrDXFDatNam, 'OPTIONS': opt, 'OUTPUT': korrGPKGDatNam}
                pAntw = processing.run('gdal:convertformat', pList)
                if os.path.exists(korrGPKGDatNam):
                    bKonvOK = True
        except:
            addFehler(tr("Error processing: " + DXFDatNam))
            return False

        if pAntw is None:
            addFehler(tr("process 'gdalogr:convertformat' could not start please restart QGIS"))
        else:
            if sOutForm == "SHP":
                aktShapeName = korrSHPDatNam
                korrSHPDatNam = EZUTempDir() + str(uuid.uuid4()) + '.shp'
                if os.path.exists(qPrjDatName):
                    copyfile(qPrjDatName, aktShapeName[0:-3] + "qpj")
                    copyfile(qPrjDatName, aktShapeName[0:-3] + "prj")
                ShapeCodepage2Utf8(aktShapeName, korrSHPDatNam, sOrgCharSet)
                sCharSet = "utf-8"

            if bKonvOK:
                if sOutForm == "SHP":
                    attTableEdit(sOutForm, korrSHPDatNam, bFormatText, sCharSet, txtErsatz4Tab=txtErsatz4Tab)
                    if korrSHPDatNam != shpdat:
                        move(korrSHPDatNam, shpdat)
                        for rest in glob(korrSHPDatNam[0:-4] + '.*'):
                            move(rest, shpdat[0:-4] + rest[-4:])
                    if os.path.exists(qPrjDatName):
                        copyfile(qPrjDatName, aktShapeName[0:-3] + "qpj")
                        copyfile(qPrjDatName, aktShapeName[0:-3] + "prj")
                    Layer = QgsVectorLayer(shpdat, "entities" + v[0], "ogr")
                    Layer.setProviderEncoding(sCharSet)
                    Layer.dataProvider().setEncoding(sCharSet)

                if sOutForm == "GPKG":
                    attTableEdit(sOutForm, korrGPKGDatNam, bFormatText, sCharSet, gpkgTable, txtErsatz4Tab)
                    sLayer = "%s|layername=%s" % (korrGPKGDatNam, gpkgTable)
                    Layer = QgsVectorLayer(sLayer, "entities" + v[0], "ogr")
                    Layer.setCrs(mLay_crs)
                    if Layer.featureCount() < 0:
                        Layer = None

                if Layer:
                    bLayerMitDaten = False
                    if Layer.featureCount() > 0:
                        koo = Layer.extent()
                        if koo.xMinimum() == 0 and koo.yMinimum() == 0 and koo.xMaximum() == 0 and koo.yMaximum() == 0:
                            addHinweis("Empty coordinates for " + opt)
                        else:
                            bLayerMitDaten = True
                    else:
                        addHinweis("No entities for " + opt)

                    if bLayerMitDaten:
                        if not bLayer:
                            Layer = QgsProject.instance().addMapLayer(Layer, False)
                            ml = grpProjekt.addLayer(Layer)
                            ml.setExpanded(False)
                            Rend = kat4Layer(Layer, bUseColor4Line, bUseColor4Poly)
                            if Rend is not None:
                                Layer.setRenderer(Rend)
                            else:
                                addFehler("Categorization for  " + opt + " could not be executed")
                            if Layer.geometryType() == 0:
                                labelingDXF(Layer, bFormatText, bUseColor4Point, dblFaktor)
                                Layer.saveNamedStyle(qmldat)
                                EditQML(qmldat)
                                Layer.loadNamedStyle(qmldat)
                        else:
                            fni = Layer.dataProvider().fieldNameIndex('Layer')
                            unique_values = Layer.dataProvider().uniqueValues(fni)
                            zL = 0
                            for AktLayerNam in unique_values:
                                OrgLayerNam = AktLayerNam
                                if AktLayerNam == NULL:
                                    AktLayerNam = "NULL"
                                else:
                                    AktLayerNam = DecodeDXFUTF(AktLayerNam)
                                uiParent.SetAktionGesSchritte(len(unique_values))
                                uiParent.SetAktionText("Edit Layer: " + AktLayerNam)
                                uiParent.SetAktionAktSchritt(zL)
                                zL += 1
                                if sOutForm == "SHP":
                                    Layer = QgsVectorLayer(shpdat, AktLayerNam + '(' + v[0] + ')', "ogr")
                                    Layer.setProviderEncoding(sCharSet)
                                    Layer.dataProvider().setEncoding(sCharSet)
                                    if OrgLayerNam == NULL:
                                        Layer.setSubsetString("Layer is Null")
                                    else:
                                        Layer.setSubsetString("Layer = '" + OrgLayerNam + "'")
                                else:
                                    Layer = QgsVectorLayer(sLayer, AktLayerNam + '(' + v[0] + ')', "ogr")
                                    Layer.setCrs(mLay_crs)
                                    if OrgLayerNam == NULL:
                                        Layer.setSubsetString("Layer is Null")
                                    else:
                                        Layer.setSubsetString("Layer = '" + OrgLayerNam + "'")
                                    if Layer.featureCount() < 0:
                                        Layer = None

                                Layer = QgsProject.instance().addMapLayer(Layer, False)
                                if AktLayerNam not in myGroups:
                                    gL = grpProjekt.addGroup(AktLayerNam)
                                    myGroups[AktLayerNam] = gL
                                    gL.addLayer(Layer)
                                    gL.setExpanded(False)
                                else:
                                    myGroups[AktLayerNam].addLayer(Layer)

                                if Layer.geometryType() == 0:
                                    symbol = QgsSymbol.defaultSymbol(Layer.geometryType())
                                    Layer.setRenderer(QgsSingleSymbolRenderer(symbol))
                                    symbol.setSize(0.1)
                                    labelingDXF(Layer, bFormatText, bUseColor4Point, dblFaktor)
                                    Layer.saveNamedStyle(qmldat)
                                    EditQML(qmldat)
                                    Layer.loadNamedStyle(qmldat)

                                if Layer.geometryType() == 1 and bUseColor4Line:
                                    registry = QgsSymbolLayerRegistry()
                                    lineMeta = registry.symbolLayerMetadata("SimpleLine")
                                    symbol = QgsSymbol.defaultSymbol(Layer.geometryType())
                                    renderer = QgsRuleBasedRenderer(symbol)
                                    root_rule = renderer.rootRule()
                                    rule = root_rule.children()[0].clone()
                                    symbol.deleteSymbolLayer(0)
                                    qmap = {"color_dd_active":"1","color_dd_expression":"\"color\"","color_dd_field":"color","color_dd_useexpr":"0"}
                                    lineLayer = lineMeta.createSymbolLayer(qmap)
                                    symbol.appendSymbolLayer(lineLayer)
                                    rule.setSymbol(symbol)
                                    rule.appendChild(rule)
                                    Layer.setRenderer(renderer)

                                if Layer.geometryType() == 2 and bUseColor4Poly:
                                    registry = QgsSymbolLayerRegistry()
                                    fillMeta = registry.symbolLayerMetadata("SimpleFill")
                                    symbol = QgsSymbol.defaultSymbol(Layer.geometryType())
                                    renderer = QgsRuleBasedRenderer(symbol)
                                    root_rule = renderer.rootRule()
                                    rule = root_rule.children()[0].clone()
                                    symbol.deleteSymbolLayer(0)
                                    qmap = {"color_dd_active":"1","color_dd_expression":"\"fcolor\"","color_dd_field":"fcolor","color_dd_useexpr":"0"}
                                    lineLayer = fillMeta.createSymbolLayer(qmap)
                                    symbol.appendSymbolLayer(lineLayer)
                                    rule.setSymbol(symbol)
                                    rule.appendChild(rule)
                                    Layer.setRenderer(renderer)
                                    Layer.setOpacity(0.5)

                            if sOutForm == "SHP":
                                Layer.saveNamedStyle(qmldat)
                            else:
                                Layer.dataProvider().createSpatialIndex()
                                Layer.saveStyleToDatabase(gpkgTable, gpkgTable, True, "")
                    else:
                        Layer = None
                        if sOutForm == "SHP":
                            if not DelShapeDatBlock(shpdat):
                                DelShapeDatBlock(shpdat)
                else:
                    addHinweis(tr("Option '%s' could not be executed") % opt)
            else:
                if sOutForm == "SHP":
                    addFehler(tr("Creation '%s' failed. Please look to the QGIS log message panel (OGR)") % shpdat)
                else:
                    addFehler(tr("Creation '%s' failed. Please look to the QGIS log message panel (OGR)") % korrGPKGDatNam)

    uiParent.SetAktionGesSchritte(2)
    uiParent.SetAktionText(tr("Switch on the display"))
    uiParent.SetAktionAktSchritt(1)
    try:
        iface.mapCanvas().setRenderFlag(True)
    except Exception as _err:
        errlog.ignored(_err, "clsDXFTools.EineDXF:457")
    return True
