# tools/annotation_tool.py

from qgis.core import (
    Qgis,
    QgsAnnotationPointTextItem,
    QgsTextFormat,
    QgsTextBackgroundSettings,
    QgsProject,
    QgsPointXY,
)
from qgis.gui import QgsMapTool
from qgis.PyQt.QtCore import Qt, QSizeF
from qgis.PyQt.QtWidgets import QDialog
from qgis.PyQt.QtGui import QFont, QColor

from . import i18n
from . import errlog

_TOL_PX = 20


def _bg_enum(enum_name, member_name):
    """Résout un membre d'énum de QgsTextBackgroundSettings quel que soit le
    style d'exposition PyQGIS (scoped `EnumName.Membre` ou à plat `Membre`
    directement sur la classe) — évite un AttributeError silencieux selon
    la version de QGIS installée."""
    enum_cls = getattr(QgsTextBackgroundSettings, enum_name, None)
    if enum_cls is not None and hasattr(enum_cls, member_name):
        return getattr(enum_cls, member_name)
    return getattr(QgsTextBackgroundSettings, member_name)


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
        if fmt.sizeUnit() == Qgis.RenderUnit.MapUnits:
            continue
        size_px = fmt.size() * dpi / 72.0
        size_m = size_px * mupp
        fmt.setSize(size_m)
        fmt.setSizeUnit(Qgis.RenderUnit.MapUnits)
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
    fmt.setSizeUnit(vals.get('size_unit', Qgis.RenderUnit.Points))
    fmt.setSize(vals['size'])
    fmt.setColor(vals['color'])
    fmt.setOpacity(vals.get('opacity', 1.0))

    bg = QgsTextBackgroundSettings()
    bg.setEnabled(bool(vals.get('frame', False)))
    if bg.enabled():
        bg.setType(_bg_enum('ShapeType', 'ShapeRectangle'))
        bg.setSizeType(_bg_enum('SizeType', 'SizeBuffer'))
        bg.setSize(QSizeF(1.0, 1.0))
        bg.setSizeUnit(Qgis.RenderUnit.Millimeters)
        if vals.get('frame_filled', True):
            bg.setFillColor(vals.get('frame_fill_color') or QColor(255, 255, 255))
        else:
            bg.setFillColor(QColor(0, 0, 0, 0))
        bg.setStrokeColor(vals.get('frame_border_color') or QColor(0, 0, 0))
        bg.setStrokeWidth(0.5)
        bg.setStrokeWidthUnit(Qgis.RenderUnit.Millimeters)
    fmt.setBackground(bg)
    return fmt


def _set_alignment(item, alignment):
    try:
        item.setAlignment(alignment)
    except AttributeError as _err:
        errlog.ignored(_err, "annotation_tool._set_alignment:125")


def _get_alignment(item):
    try:
        return item.alignment()
    except AttributeError:
        return Qt.AlignmentFlag.AlignLeft


def _snapshot_item(item):
    """Sérialise une annotation en dict autonome (pour clipboard interne)."""
    fmt  = item.format()
    font = fmt.font()
    bg   = fmt.background()
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
        'frame':              bg.enabled(),
        'frame_filled':       bg.fillColor().alpha() > 0,
        'frame_fill_color':   bg.fillColor(),
        'frame_border_color': bg.strokeColor(),
        'opacity':            fmt.opacity(),
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
        self.setCursor(Qt.CursorShape.CrossCursor)
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
        if event.button() != Qt.MouseButton.LeftButton:
            return

        click_pt = self.toMapCoordinates(event.pos())
        ctrl = bool(event.modifiers() & Qt.KeyboardModifier.ControlModifier)

        # Mode coller actif : le prochain clic gauche dépose la copie
        if self._paste_pending:
            self._paste_pending = False
            if self._paste_at(QgsPointXY(click_pt.x(), click_pt.y())):
                self.iface.messageBar().pushMessage(
                    "Annotation", i18n.tr('ot_annotation_collee'), level=Qgis.MessageLevel.Info, duration=3)
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

        ann_layer = QgsProject.instance().mainAnnotationLayer()

        if existing is not None:
            item_id, item = existing
            original_point = QgsPointXY(item.point().x(), item.point().y())
            original_snapshot = _snapshot_item(item)
            dlg = AnnotationDialog(
                self.iface.mainWindow(),
                text=original_snapshot['text'],
                font_name=original_snapshot['font'],
                size=original_snapshot['size'],
                size_unit=original_snapshot['size_unit'],
                color=original_snapshot['color'],
                bold=original_snapshot['bold'],
                italic=original_snapshot['italic'],
                underline=original_snapshot['underline'],
                alignment=original_snapshot['alignment'],
                frame=original_snapshot['frame'],
                frame_filled=original_snapshot['frame_filled'],
                frame_fill_color=original_snapshot['frame_fill_color'],
                frame_border_color=original_snapshot['frame_border_color'],
                opacity=original_snapshot['opacity'],
            )

            state = {'item_id': item_id}

            def _apply_live(vals):
                # « Appliquer » : prévisualise sur la carte sans fermer le
                # dialogue ; le texte vide n'efface pas (seul OK le fait).
                if not vals['text']:
                    return
                try:
                    new_item = _create_item_from_snapshot(vals, original_point)
                except Exception as exc:
                    self.iface.messageBar().pushMessage(
                        "Annotation", i18n.tr('ot_impossible_appliquer', erreur=exc),
                        level=Qgis.MessageLevel.Critical, duration=6)
                    return
                ann_layer.removeItem(state['item_id'])
                state['item_id'] = ann_layer.addItem(new_item)
                self.canvas().refresh()

            dlg.applied.connect(_apply_live)
            accepted = dlg.exec() == QDialog.DialogCode.Accepted

            if accepted:
                vals = dlg.get_values()
                if vals['text']:
                    new_item = _create_item_from_snapshot(vals, original_point)
                    ann_layer.removeItem(state['item_id'])
                    ann_layer.addItem(new_item)
                else:
                    ann_layer.removeItem(state['item_id'])
            else:
                # Annulé : restaure l'annotation d'origine (efface les aperçus
                # déposés via « Appliquer »).
                ann_layer.removeItem(state['item_id'])
                ann_layer.addItem(
                    _create_item_from_snapshot(original_snapshot, original_point))
        else:
            dlg = AnnotationDialog(self.iface.mainWindow())

            state = {'item_id': None}

            def _apply_live_new(vals):
                if not vals['text']:
                    return
                try:
                    new_item = _create_item_from_snapshot(
                        vals, QgsPointXY(click_pt.x(), click_pt.y()))
                except Exception as exc:
                    self.iface.messageBar().pushMessage(
                        "Annotation", i18n.tr('ot_impossible_appliquer', erreur=exc),
                        level=Qgis.MessageLevel.Critical, duration=6)
                    return
                if state['item_id'] is not None:
                    ann_layer.removeItem(state['item_id'])
                state['item_id'] = ann_layer.addItem(new_item)
                self.canvas().refresh()

            dlg.applied.connect(_apply_live_new)
            accepted = dlg.exec() == QDialog.DialogCode.Accepted

            if accepted:
                vals = dlg.get_values()
                if vals['text']:
                    new_item = _create_item_from_snapshot(
                        vals, QgsPointXY(click_pt.x(), click_pt.y()))
                    if state['item_id'] is not None:
                        ann_layer.removeItem(state['item_id'])
                    ann_layer.addItem(new_item)
                elif state['item_id'] is not None:
                    ann_layer.removeItem(state['item_id'])
            elif state['item_id'] is not None:
                # Annulé après un aperçu « Appliquer » : retire l'aperçu.
                ann_layer.removeItem(state['item_id'])

        self.canvas().refresh()

    def keyPressEvent(self, event):
        ctrl = bool(event.modifiers() & Qt.KeyboardModifier.ControlModifier)
        if ctrl and event.key() == Qt.Key.Key_C:
            existing = self._annotation_at_cursor()
            if existing is not None:
                _, item = existing
                AnnotationTool._clipboard = _snapshot_item(item)
                self.iface.messageBar().pushMessage(
                    "Annotation", i18n.tr('ot_annotation_copiee'),
                    level=Qgis.MessageLevel.Info, duration=4)
            else:
                self.iface.messageBar().pushMessage(
                    "Annotation",
                    i18n.tr('ot_curseur_annotation'),
                    level=Qgis.MessageLevel.Warning, duration=3)
            event.accept()
            return
        if ctrl and event.key() == Qt.Key.Key_V:
            if AnnotationTool._clipboard is None:
                self.iface.messageBar().pushMessage(
                    "Annotation", i18n.tr('ot_presse_papier_vide'), level=Qgis.MessageLevel.Warning, duration=3)
            else:
                self._paste_pending = True
                self.iface.messageBar().pushMessage(
                    "Annotation", i18n.tr('ot_cliquez_coller'),
                    level=Qgis.MessageLevel.Info, duration=4)
            event.accept()
            return
        if event.key() == Qt.Key.Key_Escape and self._paste_pending:
            self._paste_pending = False
            self.iface.messageBar().pushMessage(
                "Annotation", i18n.tr('ot_coller_annule'), level=Qgis.MessageLevel.Info, duration=2)
            event.accept()
            return
        super().keyPressEvent(event)

    def deactivate(self):
        self._paste_pending = False
        super().deactivate()
