# -*- coding: utf-8 -*-
# Adapted from AnotherDXF2Shape/fnc4all.py
# Changes: fncPluginVersion returns constant; direct os/sys imports

import os
import sys
import re
import time
import traceback
import tempfile
from glob import glob
from itertools import cycle

from qgis.core import QgsProject, QgsMessageLog, Qgis
from qgis.PyQt.QtCore import QSettings, QCoreApplication
from qgis.PyQt.QtWidgets import QApplication, QMessageBox


def myQGIS_VERSION_INT():
    try:
        return Qgis.QGIS_VERSION_INT
    except Exception:
        return 0


def NodeFindByFullName(FullNode, Start=None):
    if Start is None:
        Start = QgsProject.instance().layerTreeRoot()
    sNode = FullNode if isinstance(FullNode, list) else FullNode.split("\t")
    Gefunden = None
    for node in Start.children():
        if node.__class__.__name__ == "QgsLayerTreeGroup":
            if node.name() == sNode[0]:
                if len(sNode) > 1:
                    Gefunden = NodeFindByFullName(sNode[1:], node)
                else:
                    Gefunden = node
    return Gefunden


def toUnicode(text):
    if text is None:
        return ""
    return str(text)


glFehlerListe = []
glHinweisListe = []

def addFehler(Fehler):
    glFehlerListe.append(toUnicode(Fehler))

def getFehler():
    return glFehlerListe

def resetFehler():
    global glFehlerListe
    glFehlerListe = []

def addHinweis(Hinweis):
    glHinweisListe.append(toUnicode(Hinweis))

def getHinweis():
    return glHinweisListe

def getHinweis2String():
    return "\n".join(glHinweisListe)

def resetHinweis():
    global glHinweisListe
    glHinweisListe = []


def fncPluginVersion():
    return "1.0.0"


def subLZF(Sonstiges=None):
    try:
        QgsMessageLog.logMessage(
            traceback.format_exc().replace("\n", "\t") +
            ("\t" + Sonstiges if Sonstiges else ""),
            'EZUSoft:Error'
        )
    except Exception:
        pass
    addFehler(
        "LZF:" + traceback.format_exc().replace("\n", "\t") +
        ("\t" + Sonstiges if Sonstiges else "")
    )


def cut4view(fulltext, zeichen=1500, zeilen=15,
             anhang='\n\n............. and many more .........\n'):
    cut = False
    ctext = fulltext[:zeichen] if len(fulltext) > zeichen else fulltext
    if len(fulltext) > zeichen:
        cut = True
    arr = ctext.split('\n')
    if len(arr) > zeilen:
        cut = True
        ctext = '\n'.join(arr[:zeilen])
    return ctext + anhang if cut else ctext


def errbox(text, p=None):
    su = toUnicode(text)
    QMessageBox.critical(None, "PlugIn Error", cut4view(su))
    try:
        QgsMessageLog.logMessage(su, 'EZUSoft:Error')
    except:
        pass


def msgbox(text):
    su = toUnicode(text)
    QMessageBox.information(None, "PlugIn Hinweis", cut4view(su))
    try:
        QgsMessageLog.logMessage(su, 'EZUSoft:Hinweise')
    except:
        pass


def hinweislog(text, p=None):
    su = toUnicode(text)
    try:
        QgsMessageLog.logMessage(su, 'EZUSoft:Comments')
    except:
        pass


def EZUTempClear(All=None):
    Feh = 0
    Loe = 0
    tmp = EZUTempDir()
    if All:
        for dat in glob(tmp + '*.*'):
            try:
                os.remove(dat)
                Loe += 1
            except:
                Feh += 1
    else:
        for shp in glob(tmp + '*.shp'):
            try:
                os.remove(shp)
                Loe += 1
                for rest in glob(shp[0:-4] + '.*'):
                    os.remove(rest)
                    Loe += 1
            except:
                Feh += 1
    return Loe, Feh


def EZUTempDir():
    tmp = tempfile.gettempdir().replace("\\", "/") + "/{D5E6A1F8-392F-4241-A0BD-5CED09CFABC7}/"
    if not os.path.exists(tmp):
        os.makedirs(tmp)
    if os.path.exists(tmp):
        return tmp
    QMessageBox.critical(None, "Error", f"Temporary directory\n{tmp}\ncannot be created")
    return None


def ifAscii(uText):
    try:
        for char in uText:
            if ord(char) > 128:
                return False
        return True
    except:
        return False


def tryDecode(txt, sCharset):
    try:
        return str(bytes(txt, "utf8").decode(sCharset))
    except:
        return txt


def fncMakeDatName(OrgName):
    v = OrgName.replace("\\", "/")
    return v.replace("//", "/")


def fncXOR(message, key=None):
    if key is None:
        lt = time.localtime()
        key = ("%02i%02i%02i") % (lt[0:3])
    return ''.join(("%0.1X" % (ord(c) ^ ord(k))).zfill(2) for c, k in zip(message, cycle(key)))
