# tools/annotation_tool.py

from qgis.core import (
    QgsAnnotationPointTextItem,
    QgsTextFormat,
    QgsProject,
    QgsPointXY,
    QgsUnitTypes,
)
from qgis.gui import QgsMapTool
from qgis.PyQt.QtCore import Qt
from qgis.PyQt.QtGui import QFont

_TOL_PX = 20


def freeze_annotations_to_map_units(canvas):
    """Convertit toutes les annotations texte en mètres (RenderMapUnits).

    Pour chaque annotation en pt, calcule l'équivalent en mètres à la
    vue courante du canvas, puis fige l'unité en map units. L'annotation
    suivra alors le zoom (taille proportionnelle au plan, ne grossit plus
    relativement aux conduites au dézoom).

    Retourne le nombre d'annotations converties.
    """
    from qgis.PyQt.QtGui import QGuiApplication

    ann_layer = QgsProject.instance().mainAnnotationLayer()
    mupp = canvas.mapUnitsPerPixel()
    if mupp <= 0:
        return 0
    dpi = canvas.mapSettings().outputDpi()
    if not dpi or dpi <= 0:
        dpi = QGuiApplication.primaryScreen().logicalDotsPerInch()

    converted = 0
    for _id, item in list(ann_layer.items().items()):
        if not isinstance(item, QgsAnnotationPointTextItem):
            continue
        fmt = item.format()
        if fmt.sizeUnit() == QgsUnitTypes.RenderMapUnits:
            continue
        size_px = fmt.size() * dpi / 72.0
        size_m = size_px * mupp
        fmt.setSize(size_m)
        fmt.setSizeUnit(QgsUnitTypes.RenderMapUnits)
        item.setFormat(fmt)
        converted += 1

    if converted:
        canvas.refresh()
    return converted


def find_annotation_at(canvas, click_pt):
    """Retourne (item_id, item) de l'annotation la plus proche du point cliqué,
    ou None si aucune dans la tolérance de _TOL_PX pixels."""
    tol = _TOL_PX * canvas.mapUnitsPerPixel()
    try:
        ann_layer = QgsProject.instance().mainAnnotationLayer()
        best_dist, best = float('inf'), None
        for item_id, item in ann_layer.items().items():
            if not isinstance(item, QgsAnnotationPointTextItem):
                continue
            pt = item.point()
            dist = click_pt.distance(QgsPointXY(pt.x(), pt.y()))
            if dist <= tol and dist < best_dist:
                best_dist = dist
                best = (item_id, item)
        return best
    except Exception:
        return None


def make_text_format(vals):
    """Construit un QgsTextFormat depuis le dict retourné par AnnotationDialog."""
    fmt = QgsTextFormat()
    font = QFont(vals['font'])
    font.setBold(vals.get('bold', False))
    font.setItalic(vals.get('italic', False))
    font.setUnderline(vals.get('underline', False))
    fmt.setFont(font)
    fmt.setSizeUnit(vals.get('size_unit', QgsUnitTypes.RenderPoints))
    fmt.setSize(vals['size'])
    fmt.setColor(vals['color'])
    return fmt


def _set_alignment(item, alignment):
    try:
        item.setAlignment(alignment)
    except AttributeError:
        pass


def _get_alignment(item):
    try:
        return item.alignment()
    except AttributeError:
        return Qt.AlignLeft


def _snapshot_item(item):
    """Sérialise une annotation en dict autonome (pour clipboard interne)."""
    fmt  = item.format()
    font = fmt.font()
    return {
        'text':      item.text(),
        'font':      font.family(),
        'size':      fmt.size(),
        'size_unit': fmt.sizeUnit(),
        'color':     fmt.color(),
        'bold':      font.bold(),
        'italic':    font.italic(),
        'underline': font.underline(),
        'alignment': _get_alignment(item),
    }


def _create_item_from_snapshot(vals, point):
    item = QgsAnnotationPointTextItem(vals['text'], point)
    item.setFormat(make_text_format(vals))
    _set_alignment(item, vals['alignment'])
    return item


class AnnotationTool(QgsMapTool):
    """Clic gauche sur la carte :
    - zone vide            → dialogue de création (texte, police, taille, couleur,
                             gras, italique, souligné, alignement)
    - près d'une annotation → dialogue d'édition pré-rempli avec les valeurs actuelles

    Copier/coller :
    - Ctrl+clic sur une annotation existante  → duplication immédiate avec
      léger décalage (déplaçable ensuite).
    - Ctrl+C (curseur sur une annotation)     → copie dans le presse-papier interne.
    - Ctrl+V                                  → mode coller : le prochain clic
      gauche dépose la copie au point cliqué.
    """

    # Presse-papier interne partagé entre toutes les instances de l'outil
    _clipboard = None

    def __init__(self, canvas, iface):
        super().__init__(canvas)
        self.iface = iface
        self.setCursor(Qt.CrossCursor)
        self._paste_pending = False
        self._cursor_pt = None

    # ------------------------------------------------------------------ helpers

    def _annotation_at_cursor(self):
        if self._cursor_pt is None:
            return None
        return find_annotation_at(self.canvas(), self._cursor_pt)

    def _paste_at(self, point):
        if AnnotationTool._clipboard is None:
            return False
        ann_layer = QgsProject.instance().mainAnnotationLayer()
        item = _create_item_from_snapshot(AnnotationTool._clipboard, point)
        ann_layer.addItem(item)
        return True

    # ------------------------------------------------------------------ events

    def canvasMoveEvent(self, event):
        try:
            self._cursor_pt = self.toMapCoordinates(event.pos())
        except Exception:
            self._cursor_pt = None

    def canvasReleaseEvent(self, event):
        if event.button() != Qt.LeftButton:
            return

        click_pt = self.toMapCoordinates(event.pos())
        ctrl = bool(event.modifiers() & Qt.ControlModifier)

        # Mode coller actif : le prochain clic gauche dépose la copie
        if self._paste_pending:
            self._paste_pending = False
            if self._paste_at(QgsPointXY(click_pt.x(), click_pt.y())):
                self.iface.messageBar().pushMessage(
                    "Annotation", "Annotation collée.", level=0, duration=3)
                self.canvas().refresh()
            return

        existing = find_annotation_at(self.canvas(), click_pt)

        # Ctrl+clic sur une annotation existante : duplication avec petit décalage
        if ctrl and existing is not None:
            _, src = existing
            snap = _snapshot_item(src)
            mupp = self.canvas().mapUnitsPerPixel()
            offset = 30 * mupp  # ~30 px à l'écran
            src_pt = src.point()
            new_pt = QgsPointXY(src_pt.x() + offset, src_pt.y() - offset)
            ann_layer = QgsProject.instance().mainAnnotationLayer()
            ann_layer.addItem(_create_item_from_snapshot(snap, new_pt))
            AnnotationTool._clipboard = snap
            self.canvas().refresh()
            return

        from ..gui.annotation_dialog import AnnotationDialog

        if existing is not None:
            item_id, item = existing
            fmt  = item.format()
            font = fmt.font()
            dlg = AnnotationDialog(
                self.iface.mainWindow(),
                text=item.text(),
                font_name=font.family(),
                size=fmt.size(),
                size_unit=fmt.sizeUnit(),
                color=fmt.color(),
                bold=font.bold(),
                italic=font.italic(),
                underline=font.underline(),
                alignment=_get_alignment(item),
            )
            if dlg.exec_() != AnnotationDialog.Accepted:
                return
            vals = dlg.get_values()
            ann_layer = QgsProject.instance().mainAnnotationLayer()
            old_pt = item.point()
            ann_layer.removeItem(item_id)
            if vals['text']:
                ann_layer.addItem(_create_item_from_snapshot(
                    vals, QgsPointXY(old_pt.x(), old_pt.y())))
        else:
            dlg = AnnotationDialog(self.iface.mainWindow())
            if dlg.exec_() != AnnotationDialog.Accepted:
                return
            vals = dlg.get_values()
            if not vals['text']:
                return
            ann_layer = QgsProject.instance().mainAnnotationLayer()
            ann_layer.addItem(_create_item_from_snapshot(
                vals, QgsPointXY(click_pt.x(), click_pt.y())))

        self.canvas().refresh()

    def keyPressEvent(self, event):
        ctrl = bool(event.modifiers() & Qt.ControlModifier)
        if ctrl and event.key() == Qt.Key_C:
            existing = self._annotation_at_cursor()
            if existing is not None:
                _, item = existing
                AnnotationTool._clipboard = _snapshot_item(item)
                self.iface.messageBar().pushMessage(
                    "Annotation", "Annotation copiée — Ctrl+V puis cliquez pour coller.",
                    level=0, duration=4)
            else:
                self.iface.messageBar().pushMessage(
                    "Annotation",
                    "Place le curseur sur une annotation avant Ctrl+C.",
                    level=1, duration=3)
            event.accept()
            return
        if ctrl and event.key() == Qt.Key_V:
            if AnnotationTool._clipboard is None:
                self.iface.messageBar().pushMessage(
                    "Annotation", "Presse-papier vide.", level=1, duration=3)
            else:
                self._paste_pending = True
                self.iface.messageBar().pushMessage(
                    "Annotation", "Cliquez sur la carte pour coller l'annotation.",
                    level=0, duration=4)
            event.accept()
            return
        if event.key() == Qt.Key_Escape and self._paste_pending:
            self._paste_pending = False
            self.iface.messageBar().pushMessage(
                "Annotation", "Coller annulé.", level=0, duration=2)
            event.accept()
            return
        super().keyPressEvent(event)

    def deactivate(self):
        self._paste_pending = False
        super().deactivate()
