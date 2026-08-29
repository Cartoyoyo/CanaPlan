# -*- coding: utf-8 -*-
# Adapted from AnotherDXF2Shape/clsDBase.py
# Changes: relative imports updated; fnc4ADXF2Shape → fnc4adxf

from osgeo import ogr
import locale

from qgis.PyQt.QtCore import QCoreApplication
from qgis.core import (
    QgsVectorLayer,
    QgsVectorFileWriter,
    QgsCoordinateTransformContext,
)

from .fnc4all import *
from .fnc4adxf import *
from .... import errlog


def tr(message):
    return QCoreApplication.translate('clsDXFTools', message)


def ZahlTextSplit(zt):
    try:
        z = ""; t = ""; f = -1; isText = False
        for c in zt:
            if c not in "01234567890.-":
                isText = True
            if isText:
                t += c
            else:
                z += c
        f = float(z)
    except Exception as _err:
        errlog.ignored(_err, "clsDBase.ZahlTextSplit:35")
    return f, t


def fnctxtOGRtoQGIS(cArt):
    mapping = {1:2,2:1,3:0,4:5,5:4,6:3,7:8,8:7,9:6,10:2,11:1,12:0}
    return mapping.get(cArt, 0)


def trennArtDaten(ArtDaten):
    sDaten = ""; sArt = ""; inDaten = False
    for c in ArtDaten[:-1]:
        if c == '(' and not inDaten:
            inDaten = True; c = ''
        if inDaten:
            sDaten += c
        else:
            sArt += c
    return sArt, sDaten


def csvSplit(csvZeile, trenn=',', tKenn='"', tKennDel=True, bOnlyFirst=False):
    inString = False; mask = ""; s = ''; sb = False
    for c in csvZeile:
        if c == tKenn and not sb:
            inString = not inString
        if c == trenn and inString and not sb:
            if mask == "":
                mask = "$$"
                while mask in csvZeile:
                    mask += '$'
            s += mask
        else:
            if not (tKennDel and not sb and c == tKenn):
                s += c
        sb = (c == "\\")
    arr = s.split(trenn)
    if mask:
        arr = [a.replace(mask, trenn) for a in arr]
    if bOnlyFirst and len(arr) > 2:
        arr = [arr[0], trenn.join(arr[1:])]
    return arr


def splitText(fText, TxtType):
    underline = False; bs = False; uText = r""
    ignor = False; font = ""; color = ""
    delSemi = False; inFont = False; inColor = False
    inIngnorieren = False; inHText = False
    aktText = fText; FlNum = False; aktSize = None

    if TxtType in ("TEXT", "UNDEF"):
        if "%%u".upper() in aktText.upper():
            underline = True
            aktText = aktText.replace('%%u', '').replace('%%U', '')
        for src, dst in [('%%d','°'),('%%p','±'),('%%c','Ø'),('%%D','°'),('%%P','±'),('%%C','Ø')]:
            aktText = aktText.replace(src, dst)

    if TxtType in ("MTEXT", "UNDEF"):
        aktText = DecodeDXFUTF(aktText)
        for src, dst in [('%%d','°'),('%%p','±'),('%%c','Ø'),('%%D','°'),('%%P','±'),('%%C','Ø')]:
            aktText = aktText.replace(src, dst)
        for c in aktText:
            if bs and c.upper() == 'H':  c=''; ignor=True; inHText=True; delSemi=True
            if bs and c.upper() == 'O':  c=''; ignor=True
            if bs and c.upper() == 'L':  c=''; underline=True; ignor=True
            if bs and c == 'S':          c=''; ignor=True; delSemi=True; FlNum=True
            if bs and c.upper() == 'F':  ignor=True; inFont=True; delSemi=True
            if bs and c.upper() == 'C':  ignor=True; inColor=True; delSemi=True
            if bs and c == 'p':          ignor=True; inIngnorieren=True; delSemi=True
            if bs and c == 'A':          ignor=True; inIngnorieren=True; delSemi=True
            if bs and c == 'W':          ignor=True; inIngnorieren=True; delSemi=True
            if bs and c == 'P':          ignor=True; c="\n"
            if c == ';' and delSemi:
                c=''; inFont=False; inColor=False; inIngnorieren=False; inHText=False; delSemi=False
            if not bs and (c == '{' or c == '}'):
                c=''
            else:
                ignor = True
            if c == '\\':
                if bs:
                    uText += '\\\\'; bs=False
                else:
                    bs=True
            else:
                if not ignor:
                    if bs: uText += '\\'
                if inFont:      font += c
                elif inColor:   color += c
                elif inHText:
                    aktSize = c if aktSize is None else aktSize + c
                elif not inIngnorieren:
                    uText += c
                bs = False
            ignor = False
        aktText = uText
    return aktText, underline, font, FlNum, aktSize, color


def ShapeCodepage2Utf8(OrgShpDat, TargetShpDat, OrgCodePage):
    TargetCodePage = "utf8"
    if OrgCodePage == "System":
        OrgCodePage = locale.getdefaultlocale()[1]
    oLayer = QgsVectorLayer(OrgShpDat, '', 'ogr')
    oLayer.setProviderEncoding(OrgCodePage)
    oLayer.dataProvider().setEncoding(OrgCodePage)
    if myQGIS_VERSION_INT() < 31003:
        QgsVectorFileWriter.writeAsVectorFormat(oLayer, TargetShpDat, TargetCodePage, oLayer.crs(), "ESRI Shapefile")
    else:
        options = QgsVectorFileWriter.SaveVectorOptions()
        options.driverName = "ESRI Shapefile"
        options.fileEncoding = TargetCodePage
        QgsVectorFileWriter.writeAsVectorFormatV2(oLayer, TargetShpDat, QgsCoordinateTransformContext(), options)


def attTableEdit(sOutForm, inpDat, bFormat, sCharSet, gpkgTable=None, txtErsatz4Tab=' '):
    if sCharSet == "System":
        sCharSet = locale.getdefaultlocale()[1]

    source = ogr.Open(inpDat, update=True)
    if source is None:
        addFehler(tr('ogr: can not open: ') + inpDat)
        return

    if sOutForm == "SHP":
        layer = source.GetLayer()
        if layer is None:
            source.Destroy()
            addFehler(tr('ogr: layer not found: ') + inpDat)
            return
    else:
        layer = source.GetLayerByName(gpkgTable)
        if layer is None:
            source.Destroy()
            hinweislog(tr('ogr: layer not found: ') + inpDat + '(' + gpkgTable + ')')
            return

    laydef = layer.GetLayerDefn()
    if laydef is None:
        source.Destroy()
        addFehler(tr('ogr: laydef not found: ') + inpDat)
        return

    Found = any(laydef.GetFieldDefn(i).GetName() == 'ogr_style' for i in range(laydef.GetFieldCount()))
    if not Found:
        addFehler(tr("missing field 'ogr_style': ") + inpDat)
        return

    existing_fields = {laydef.GetFieldDefn(i).GetName() for i in range(laydef.GetFieldCount())}
    for fname, ftype in [('font', ogr.OFTString), ('angle', ogr.OFTReal), ('size', ogr.OFTReal),
                          ('size_u', ogr.OFTString), ('anchor', ogr.OFTString), ('color', ogr.OFTString),
                          ('underline', ogr.OFTInteger), ('plaintext', ogr.OFTString), ('fcolor', ogr.OFTString),
                          ('flnum', ogr.OFTInteger), ('bold', ogr.OFTInteger), ('italic', ogr.OFTInteger),
                          ('dx', ogr.OFTReal), ('dx_u', ogr.OFTString), ('dy', ogr.OFTReal), ('dy_u', ogr.OFTString)]:
        if fname not in existing_fields:
            layer.CreateField(ogr.FieldDefn(fname, ftype))

    layer.StartTransaction()
    feature = layer.GetNextFeature()
    while feature:
        try:
            TxtType = "UNDEF"
            SubClass = feature.GetField('SubClasses')
            if SubClass is not None:
                if "AcDbMText" in SubClass: TxtType = "MTEXT"
                if "AcDbText"  in SubClass: TxtType = "TEXT"

            att = feature.GetField('ogr_style')
            try:
                aktHandle = feature.GetField('EntityHand')
            except:
                aktHandle = feature.GetField('EntityHandle')

            if att is None:
                addHinweis(tr("missing field 'ogr_style' in: ") + inpDat)
            elif att[-1] != ')':
                addHinweis(tr("incomplete field 'ogr_style' at EntityHandle: ") + str(aktHandle or ""))
            else:
                sArt, sDaten = trennArtDaten(att)
                params = csvSplit(sDaten)
                for param in params:
                    arr = csvSplit(param, ":", None, None, True)
                    if len(arr) == 2:
                        f = arr[0]; w = arr[1]
                        if f == "c":
                            if w == "#ffffff": w = "#f0f0f0"
                            feature.SetField('color', w[:7])
                        if f == "fc":
                            if w == "#000000": w = "#f0f0f0"
                            feature.SetField('fcolor', w[:7])
                        if f == "f":  feature.SetField('font', w)
                        if f == "a":
                            dWin = float(w)
                            if dWin >= 360: dWin -= 360
                            feature.SetField('angle', dWin)
                        if f == "p" and sArt == "LABEL":
                            feature.SetField('anchor', fnctxtOGRtoQGIS(int(w)))
                        if f == "s":
                            z, t = ZahlTextSplit(w)
                            feature.SetField('size', z); feature.SetField('size_u', t)
                        if f == "dx":
                            z, t = ZahlTextSplit(w)
                            feature.SetField('dx', z); feature.SetField('dx_u', t)
                        if f == "dy":
                            z, t = ZahlTextSplit(w)
                            feature.SetField('dy', z); feature.SetField('dy_u', t)

                        if sArt == "LABEL":
                            AktText = feature.GetField('Text')
                            if AktText is None:
                                addHinweis(tr('missing Text: ') + inpDat)
                            else:
                                dummy = AktText; AktText = ""; bDecodeError = False
                                for c in dummy:
                                    if ord(c) > 54000:
                                        c = "?"; bDecodeError = True
                                    AktText += c
                                if bDecodeError:
                                    addFehler(tr("Wrong char in 'ogr_style' at EntityHandle: ") + str(aktHandle or "") + tr(" (Check your choose charset)") + tryDecode(dummy, sCharSet))
                                if bFormat:
                                    t, underline, font, FlNum, aktSize, color = splitText(AktText, TxtType)
                                    t = t.replace('^I', txtErsatz4Tab)
                                    feature.SetField('plaintext', t)
                                    if aktSize is not None: feature.SetField('size', aktSize)
                                    if color:
                                        try:
                                            color = hex(int(color[1:])).replace('0x', '#')
                                            if color == "#ffffff": color = "#f0f0f0"
                                            feature.SetField('color', color)
                                        except:
                                            feature.SetField('color', '#FEHLER#')
                                    if font:
                                        afont = font.split('|')
                                        for p in afont:
                                            if p[:1] == 'f': feature.SetField('font', p[1:])
                                            if p[:1] == 'b': feature.SetField('bold', p[1:])
                                            if p[:1] == 'i': feature.SetField('italic', p[1:])
                                    feature.SetField('underline', underline)
                                    feature.SetField('flnum', FlNum)
                                else:
                                    feature.SetField('plaintext', AktText)
                                    feature.SetField('underline', False)
                    else:
                        addFehler(tr("incomplete field 'ogr_style': ") + tryDecode(param, sCharSet))
                layer.SetFeature(feature)
        except:
            subLZF('ogr_style:' + str(att))
        feature = layer.GetNextFeature()
    layer.CommitTransaction()
    source.Destroy()
