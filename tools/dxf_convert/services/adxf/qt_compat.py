# -*- coding: utf-8 -*-
# Copied from AnotherDXF2Shape/qt_compat.py

from qgis.PyQt import QtCore, QtWidgets, QtNetwork
from qgis.core import QgsProject
import qgis

QT_VERSION_STR = QtCore.QT_VERSION_STR
QT6 = QT_VERSION_STR.startswith("6")

AlignLeft   = QtCore.Qt.AlignmentFlag.AlignLeft   if QT6 else QtCore.Qt.AlignLeft
AlignRight  = QtCore.Qt.AlignmentFlag.AlignRight  if QT6 else QtCore.Qt.AlignRight
AlignCenter = QtCore.Qt.AlignmentFlag.AlignCenter if QT6 else QtCore.Qt.AlignCenter

Horizontal = QtCore.Qt.Orientation.Horizontal if QT6 else QtCore.Qt.Horizontal
Vertical   = QtCore.Qt.Orientation.Vertical   if QT6 else QtCore.Qt.Vertical

Checked   = QtCore.Qt.CheckState.Checked   if QT6 else QtCore.Qt.Checked
Unchecked = QtCore.Qt.CheckState.Unchecked if QT6 else QtCore.Qt.Unchecked

Close  = QtWidgets.QDialogButtonBox.StandardButton.Close  if QT6 else QtWidgets.QDialogButtonBox.Close
Ok     = QtWidgets.QDialogButtonBox.StandardButton.Ok     if QT6 else QtWidgets.QDialogButtonBox.Ok
Cancel = QtWidgets.QDialogButtonBox.StandardButton.Cancel if QT6 else QtWidgets.QDialogButtonBox.Cancel
Yes    = QtWidgets.QDialogButtonBox.StandardButton.Yes    if QT6 else QtWidgets.QDialogButtonBox.Yes
No     = QtWidgets.QDialogButtonBox.StandardButton.No     if QT6 else QtWidgets.QDialogButtonBox.No

if QT6:
    ItemFlags         = QtCore.Qt.ItemFlags
    ItemIsSelectable  = QtCore.Qt.ItemFlag.ItemIsSelectable
    ItemIsEnabled     = QtCore.Qt.ItemFlag.ItemIsEnabled
    ItemIsUserCheckable = QtCore.Qt.ItemFlag.ItemIsUserCheckable
    ItemIsTristate    = QtCore.Qt.ItemFlag.ItemIsAutoTristate
    WaitCursor        = QtCore.Qt.CursorShape.WaitCursor
else:
    ItemFlags         = QtCore.Qt.ItemFlags
    ItemIsSelectable  = QtCore.Qt.ItemIsSelectable
    ItemIsEnabled     = QtCore.Qt.ItemIsEnabled
    ItemIsUserCheckable = QtCore.Qt.ItemIsUserCheckable
    ItemIsTristate    = QtCore.Qt.ItemIsTristate
    WaitCursor        = QtCore.Qt.WaitCursor

QGIS_VERSION_INT = int(getattr(qgis.core.Qgis, "QGIS_VERSION_INT", 0))
QGIS3 = QGIS_VERSION_INT < 40000
QGIS4 = QGIS_VERSION_INT >= 40000

def exec_dialog(dialog):
    return dialog.exec() if QT6 else dialog.exec_()

QNetworkAccessManager = QtNetwork.QNetworkAccessManager
QNetworkRequest       = QtNetwork.QNetworkRequest
QNetworkReply         = QtNetwork.QNetworkReply
QUrl       = QtCore.QUrl
QByteArray = QtCore.QByteArray
QTimer     = QtCore.QTimer

if hasattr(QNetworkRequest, "HttpStatusCodeAttribute"):
    HttpStatusCodeAttribute = QNetworkRequest.HttpStatusCodeAttribute
else:
    try:
        HttpStatusCodeAttribute = QNetworkRequest.Attribute.HttpStatusCodeAttribute
    except AttributeError:
        HttpStatusCodeAttribute = None

if hasattr(QNetworkRequest, "RedirectionTargetAttribute"):
    RedirectionTargetAttribute = QNetworkRequest.RedirectionTargetAttribute
else:
    try:
        RedirectionTargetAttribute = QNetworkRequest.Attribute.RedirectionTargetAttribute
    except AttributeError:
        RedirectionTargetAttribute = None

if QT6:
    DontResolveSymlinks = QtWidgets.QFileDialog.Option.DontResolveSymlinks
    ShowDirsOnly        = QtWidgets.QFileDialog.Option.ShowDirsOnly
else:
    DontResolveSymlinks = QtWidgets.QFileDialog.DontResolveSymlinks
    ShowDirsOnly        = QtWidgets.QFileDialog.ShowDirsOnly

if QT6:
    MsgBox_Yes    = QtWidgets.QMessageBox.StandardButton.Yes
    MsgBox_No     = QtWidgets.QMessageBox.StandardButton.No
    MsgBox_Cancel = QtWidgets.QMessageBox.StandardButton.Cancel
else:
    MsgBox_Yes    = QtWidgets.QMessageBox.Yes
    MsgBox_No     = QtWidgets.QMessageBox.No
    MsgBox_Cancel = QtWidgets.QMessageBox.Cancel
