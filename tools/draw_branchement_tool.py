# tools/draw_branchement_tool.py

import math

from qgis.core import (
    QgsPointXY, QgsGeometry, QgsFeature, QgsWkbTypes,
    QgsVectorLayer, QgsProject, QgsDistanceArea
)
from qgis.gui import QgsMapToolEmitPoint, QgsRubberBand
from qgis.PyQt.QtCore import Qt, pyqtSignal
from qgis.PyQt.QtWidgets import QMessageBox, QDialog, QFormLayout, QLineEdit, QDialogButtonBox, QToolTip
from qgis.PyQt.QtGui import QColor

from . import i18n

from .spatial_utils import nearest_point_feature, nearest_line_feature


class DrawBranchementTool(QgsMapToolEmitPoint):
    """
    Outil de dessin d'un branchement (EU ou EP).
    Premier clic sur une conduite du même réseau, puis tracé libre,
    dernier clic sur un tabouret ou regard du même réseau.
    """
    finished = pyqtSignal()  # signal émis quand l'outil a terminé

    def __init__(self, canvas, reseau, couches):
        """
        :param canvas: QgsMapCanvas
        :param reseau: "EU" ou "EP"
        :param couches: dict avec les clés 'conduite', 'regard', 'tabouret', 'branchement'
                       contenant les QgsVectorLayer correspondants.
        """
        super().__init__(canvas)
        self.canvas = canvas
        self.reseau = reseau
        self.conduite_layer = couches['conduite']       # couche des conduites principales
        self.regard_layer = couches['regard']           # couche des regards
        self.tabouret_layer = couches['tabouret']       # couche des tabourets
        self.branchement_layer = couches['branchement'] # couche où sera stocké le branchement

        # État interne
        self.points = []            # points cliqués (en coordonnées canvas)
        self.snapped_points = []    # points après snapping/projection
        self.id_conduite = None     # id de la conduite piquée
        self.pk_debut = None        # pk du point de piquage

        # Rubber band pour le tracé temporaire
        self.rubber = QgsRubberBand(self.canvas, QgsWkbTypes.LineGeometry)
        color = QColor(255, 0, 0) if reseau == "EU" else QColor(0, 0, 255)
        self.rubber.setColor(color)
        self.rubber.setWidth(2)

        # Indicateur de snap : croix au point projeté
        self.snap_cross = QgsRubberBand(self.canvas, QgsWkbTypes.LineGeometry)
        self.snap_cross.setColor(QColor(0, 200, 0))
        self.snap_cross.setWidth(2)

        # Indicateur de snap : traits perpendiculaires sur la conduite
        self.snap_ticks = QgsRubberBand(self.canvas, QgsWkbTypes.LineGeometry)
        self.snap_ticks.setColor(QColor(0, 200, 0))
        self.snap_ticks.setWidth(2)

        # Surlignage orange de la conduite ciblée
        self.highlight_band = QgsRubberBand(self.canvas, QgsWkbTypes.LineGeometry)
        self.highlight_band.setColor(QColor(255, 140, 0))
        self.highlight_band.setWidth(4)

    def activate(self):
        super().activate()
        self.canvas.setCursor(Qt.CrossCursor)
        from qgis.utils import iface
        iface.messageBar().pushMessage(
            f"Branchement {self.reseau}",
            i18n.tr('ot_aide_branchement'),
            level=0, duration=0,
        )

    def deactivate(self):
        from qgis.utils import iface
        iface.messageBar().clearWidgets()
        QToolTip.hideText()
        self.rubber.reset(QgsWkbTypes.LineGeometry)
        self.snap_cross.reset(QgsWkbTypes.LineGeometry)
        self.snap_ticks.reset(QgsWkbTypes.LineGeometry)
        self.highlight_band.reset(QgsWkbTypes.LineGeometry)
        self.points = []
        super().deactivate()

    def canvasMoveEvent(self, event):
        point = self.toMapCoordinates(event.pos())

        if len(self.points) == 0:
            # Pas encore de point posé : afficher l'indicateur de snap sur conduite
            pk_info = self._update_snap_indicator(point)
            if pk_info is not None:
                pk, total_len = pk_info
                texte = (f"{pk:.2f} m / {total_len - pk:.2f} m"
                          .replace('.', ','))
                QToolTip.showText(event.globalPos(), texte, self.canvas)
            else:
                QToolTip.hideText()
        else:
            # Tracé en cours : masquer les indicateurs et mettre à jour le rubber band
            self.snap_cross.reset(QgsWkbTypes.LineGeometry)
            self.snap_ticks.reset(QgsWkbTypes.LineGeometry)
            self.highlight_band.reset(QgsWkbTypes.LineGeometry)
            temp_points = self.snapped_points.copy()
            temp_points.append(point)
            self.rubber.setToGeometry(QgsGeometry.fromPolylineXY(temp_points), None)

            longueur = QgsGeometry.fromPolylineXY(temp_points).length()
            texte = f"{longueur:.2f} m".replace('.', ',')

            angle = self._angle_amont(temp_points)
            if angle is not None:
                deviation = 180.0 - angle
                texte += f"  ·  {angle:.0f}° / {deviation:.0f}°"

            if len(temp_points) >= 3:
                angle_sommet = self._compute_angle(
                    temp_points[-3], temp_points[-2], temp_points[-1])
                deviation_sommet = 180.0 - angle_sommet
                texte += f"  ·  {angle_sommet:.0f}° / {deviation_sommet:.0f}°"

            QToolTip.showText(event.globalPos(), texte, self.canvas)

    @staticmethod
    def _compute_angle(p_prev, p_vertex, p_next):
        """Angle (en degrés) au sommet p_vertex entre les segments p_prev-p_vertex
        et p_vertex-p_next. 180° = alignement droit, 90° = angle droit."""
        ax = p_prev.x() - p_vertex.x()
        ay = p_prev.y() - p_vertex.y()
        bx = p_next.x() - p_vertex.x()
        by = p_next.y() - p_vertex.y()
        dot = ax * bx + ay * by
        det = ax * by - ay * bx
        return abs(math.degrees(math.atan2(det, dot)))

    def _angle_amont(self, temp_points):
        """Angle (0-180°) entre la direction amont de la conduite piquée et
        le premier segment du branchement (piquage -> premier point tracé)."""
        if self.id_conduite is None or len(temp_points) < 2:
            return None

        try:
            cond_geom = self.conduite_layer.getFeature(self.id_conduite).geometry()
        except Exception:
            return None
        if cond_geom.isEmpty():
            return None

        total_len = cond_geom.length()
        if total_len <= 0:
            return None

        delta = min(0.5, total_len * 0.01)
        pk = self.pk_debut
        p_pk   = cond_geom.interpolate(pk).asPoint()
        p_back = cond_geom.interpolate(max(0, pk - delta)).asPoint()
        amont_vec = (p_back.x() - p_pk.x(), p_back.y() - p_pk.y())

        p0, p1 = temp_points[0], temp_points[1]
        branch_vec = (p1.x() - p0.x(), p1.y() - p0.y())

        norm_a = math.hypot(*amont_vec)
        norm_b = math.hypot(*branch_vec)
        if norm_a < 1e-9 or norm_b < 1e-9:
            return None

        dot = amont_vec[0] * branch_vec[0] + amont_vec[1] * branch_vec[1]
        cos_a = max(-1.0, min(1.0, dot / (norm_a * norm_b)))
        return math.degrees(math.acos(cos_a))

    def _update_snap_indicator(self, cursor_point):
        self.snap_cross.reset(QgsWkbTypes.LineGeometry)
        self.snap_ticks.reset(QgsWkbTypes.LineGeometry)
        self.highlight_band.reset(QgsWkbTypes.LineGeometry)

        detect_tol = 200 * self.canvas.mapUnitsPerPixel()
        regard_tol  =  10 * self.canvas.mapUnitsPerPixel()

        # ── Priorité regard à 5 px ──────────────────────────────────────────
        r_feat, _ = nearest_point_feature(
            self.regard_layer, cursor_point, regard_tol)
        nearest_regard_pt = (QgsPointXY(r_feat.geometry().asPoint())
                             if r_feat is not None else None)

        snap_from = nearest_regard_pt if nearest_regard_pt is not None \
                    else cursor_point

        # ── Conduite la plus proche (rayon = seuil d'affichage + marge regard)
        best_feat, best_proj, best_dist = nearest_line_feature(
            self.conduite_layer, snap_from, detect_tol + regard_tol)

        if best_feat is None:
            return None

        # Distance de référence pour le seuil d'affichage = curseur réel → conduite
        sq_ref, _, _, _ = best_feat.geometry().closestSegmentWithContext(cursor_point)
        if math.sqrt(sq_ref) > detect_tol:
            return None

        # Quand regard prioritaire, le point projeté devient la position du regard
        if snap_from is not cursor_point:
            best_proj = nearest_regard_pt

        # ── Surlignage orange de la conduite ────────────────────────────────
        self.highlight_band.setToGeometry(best_feat.geometry(), None)

        cross_size = 15 * self.canvas.mapUnitsPerPixel()
        cross_h = [QgsPointXY(best_proj.x() - cross_size, best_proj.y()),
                   QgsPointXY(best_proj.x() + cross_size, best_proj.y())]
        cross_v = [QgsPointXY(best_proj.x(), best_proj.y() - cross_size),
                   QgsPointXY(best_proj.x(), best_proj.y() + cross_size)]

        if snap_from is not cursor_point:
            # Mode regard : croix seule, pas de tirets vers le curseur
            self.snap_cross.setToGeometry(
                QgsGeometry.fromMultiPolylineXY([cross_h, cross_v]), None)
            return None
        else:
            # Mode conduite : tirets curseur→proj + croix + perpendiculaire
            self.snap_ticks.setToGeometry(
                QgsGeometry.fromPolylineXY([cursor_point, best_proj]), None)

            pk        = best_feat.geometry().lineLocatePoint(QgsGeometry.fromPointXY(best_proj))
            total_len = best_feat.geometry().length()
            delta = min(0.5, total_len * 0.01)
            p1 = best_feat.geometry().interpolate(max(0, pk - delta)).asPoint()
            p2 = best_feat.geometry().interpolate(min(total_len, pk + delta)).asPoint()
            dx, dy   = p2.x() - p1.x(), p2.y() - p1.y()
            seg_len  = math.sqrt(dx * dx + dy * dy)

            if seg_len > 1e-12:
                perp_x, perp_y = -dy / seg_len, dx / seg_len
                tick = cross_size * 1.5
                perp_tick = [
                    QgsPointXY(best_proj.x() - perp_x * tick, best_proj.y() - perp_y * tick),
                    QgsPointXY(best_proj.x() + perp_x * tick, best_proj.y() + perp_y * tick),
                ]
                self.snap_cross.setToGeometry(
                    QgsGeometry.fromMultiPolylineXY([cross_h, cross_v, perp_tick]), None)
            else:
                self.snap_cross.setToGeometry(
                    QgsGeometry.fromMultiPolylineXY([cross_h, cross_v]), None)

            return (pk, total_len)

    def canvasReleaseEvent(self, event):
        point = self.toMapCoordinates(event.pos())

        # Clic droit : ajouter le point final et terminer
        if event.button() == Qt.RightButton:
            if len(self.points) == 0:
                return
            self.points.append(point)
            self.snapped_points.append(point)
            self._finish()
            return

        if event.button() != Qt.LeftButton:
            return

        if len(self.points) == 0:
            # Priorité regard, sinon piquage sur conduite
            result = self._snap_to_regard(point) or self._snap_to_conduite(point)
            if not result:
                QMessageBox.warning(None, i18n.tr('erreur'),
                    i18n.tr('ot_premier_point', reseau=self.reseau))
                return
            snapped_point, id_conduite, pk = result
            self.snapped_points.append(snapped_point)
            self.points.append(point)
            self.id_conduite = id_conduite
            self.pk_debut = pk
            self.rubber.addPoint(snapped_point)

        else:
            # Points intermédiaires
            self.points.append(point)
            self.snapped_points.append(point)
            self.rubber.addPoint(point)

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Escape:
            self._cancel()
        elif event.key() in (Qt.Key_Return, Qt.Key_Enter):
            self._finish()

    def _reset(self):
        """Réinitialise l'état pour un nouveau tracé (outil reste actif)."""
        QToolTip.hideText()
        self.rubber.reset(QgsWkbTypes.LineGeometry)
        self.snap_cross.reset(QgsWkbTypes.LineGeometry)
        self.snap_ticks.reset(QgsWkbTypes.LineGeometry)
        self.highlight_band.reset(QgsWkbTypes.LineGeometry)
        self.points = []
        self.snapped_points = []
        self.id_conduite = None
        self.pk_debut = None

    def _cancel(self):
        """Annule le tracé en cours."""
        self._reset()
        self.deactivate()

    def _finish(self):
        """Finalise le branchement."""
        if len(self.snapped_points) < 2:
            self._cancel()
            return

        # Créer un tabouret au point final
        last_point = self.snapped_points[-1]
        self._create_tabouret(last_point)

        # Validation topologique finale
        if not self._validate_topology():
            self._cancel()
            return

        # Création du branchement
        self._create_branchement()
        self._reset()

    def _snap_to_regard(self, point):
        """
        Accroche au regard le plus proche (10 px). Trouve la conduite connectée
        et retourne (point_regard, id_conduite, pk) ou None.
        """
        tol_regard   = 10  * self.canvas.mapUnitsPerPixel()
        tol_connexion = 0.5  # 50 cm pour relier regard ↔ extrémité conduite

        r_feat, _ = nearest_point_feature(self.regard_layer, point, tol_regard)
        if r_feat is None:
            return None
        best_pt = QgsPointXY(r_feat.geometry().asPoint())

        # Trouve la conduite dont une extrémité coïncide avec ce regard
        best_feat, best_proj, best_dist = nearest_line_feature(
            self.conduite_layer, best_pt, tol_connexion)

        if best_feat is None:
            return None

        pk = self._compute_pk(best_feat.geometry(), best_pt)
        return (best_pt, best_feat.id(), pk)

    def _snap_to_conduite(self, point):
        """
        Cherche la conduite la plus proche. Priorité regard à 5 px.
        Retourne (point_projeté, id_conduite, pk) ou None.
        """
        tolerance  = 200 * self.canvas.mapUnitsPerPixel()
        regard_tol =  10 * self.canvas.mapUnitsPerPixel()

        # ── Priorité regard à 5 px ──────────────────────────────────────────
        r_feat, _ = nearest_point_feature(self.regard_layer, point, regard_tol)
        nearest_regard_pt = (QgsPointXY(r_feat.geometry().asPoint())
                             if r_feat is not None else None)

        snap_from = nearest_regard_pt if nearest_regard_pt is not None \
                    else point

        best_feat, best_proj, best_dist = nearest_line_feature(
            self.conduite_layer, snap_from, tolerance + regard_tol)

        # Vérifier la distance avec le curseur réel
        if best_feat is None:
            return None
        sq_ref, _, _, _ = best_feat.geometry().closestSegmentWithContext(point)
        if math.sqrt(sq_ref) > tolerance:
            return None

        # Quand regard prioritaire, utiliser sa position comme point de piquage
        final_proj = QgsPointXY(nearest_regard_pt if snap_from is not point else best_proj)
        pk = self._compute_pk(best_feat.geometry(), final_proj)
        return (final_proj, best_feat.id(), pk)

    def _snap_to_ouvrage(self, point):
        """
        Cherche l'ouvrage (regard ou tabouret) le plus proche.
        Retourne le point de l'ouvrage ou None si hors tolérance.
        """
        tolerance = 200 * self.canvas.mapUnitsPerPixel()
        best_point = None
        best_dist = float('inf')
        for layer in (self.regard_layer, self.tabouret_layer):
            feat, dist = nearest_point_feature(layer, point, tolerance)
            if feat is not None and dist < best_dist:
                best_dist = dist
                best_point = feat.geometry().asPoint()
        return best_point

    def _compute_pk(self, line_geom, point):
        """Calcule l'abscisse curviligne du point projeté sur la ligne."""
        da = QgsDistanceArea()
        da.setSourceCrs(self.conduite_layer.crs(), QgsProject.instance().transformContext())
        # Utiliser la méthode lineLocatePoint
        return line_geom.lineLocatePoint(QgsGeometry.fromPointXY(point))

    def _create_tabouret(self, point):
        """Crée un tabouret au point donné (valeurs à renseigner plus tard)."""
        if not self.tabouret_layer.isEditable():
            self.tabouret_layer.startEditing()
        feat = QgsFeature(self.tabouret_layer.fields())
        feat.setGeometry(QgsGeometry.fromPointXY(point))
        self.tabouret_layer.addFeature(feat)
        self.tabouret_layer.commitChanges()

    def _create_regard(self, point):
        """Crée un regard au point donné (avec formulaire simplifié)."""
        dlg = QDialog()
        dlg.setWindowTitle(i18n.tr('ot_creer_regard'))
        layout = QFormLayout(dlg)
        tn_edit = QLineEdit()
        fe_edit = QLineEdit()
        diam_edit = QLineEdit()
        layout.addRow(i18n.tr('ot_lbl_tn'), tn_edit)
        layout.addRow(i18n.tr('ot_lbl_fe_radier'), fe_edit)
        layout.addRow(i18n.tr('ot_lbl_diametre'), diam_edit)
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(dlg.accept)
        buttons.rejected.connect(dlg.reject)
        layout.addRow(buttons)

        if dlg.exec_() == QDialog.Accepted:
            try:
                tn = float(tn_edit.text())
                fe = float(fe_edit.text())
            except:
                QMessageBox.warning(None, i18n.tr('erreur'), i18n.tr('ot_valeurs_invalides'))
                return
            feat = QgsFeature(self.regard_layer.fields())
            feat.setGeometry(QgsGeometry.fromPointXY(point))
            feat.setAttribute('tn', tn)
            feat.setAttribute('fe_radier', fe)
            feat.setAttribute('diametre', diam_edit.text() or None)
            self.regard_layer.addFeature(feat)

    def _validate_topology(self):
        """Vérifie que le premier point est bien sur la conduite
           et le dernier sur un ouvrage."""
        # Premier point
        first = self.snapped_points[0]
        tolerance = 0.001
        if not self.conduite_layer.boundingBoxOfSelected().isNull():
            pass  # on pourrait vérifier la distance exacte
        # On va projeter à nouveau et vérifier la distance
        (sq_d, proj, av, lo) = self.conduite_layer.getFeature(self.id_conduite).geometry().closestSegmentWithContext(first)
        if first.distance(proj) > tolerance:
            QMessageBox.warning(None, i18n.tr('ot_validation'),
                i18n.tr('ot_branch_debut'))
            return False

        # Dernier point
        last = self.snapped_points[-1]
        # chercher dans regards et tabourets
        found = False
        for layer in (self.regard_layer, self.tabouret_layer):
            feat, _ = nearest_point_feature(layer, QgsPointXY(last), tolerance)
            if feat is not None:
                found = True
                break
        if not found:
            QMessageBox.warning(None, i18n.tr('ot_validation'),
                i18n.tr('ot_branch_fin'))
            return False
        return True

    def _create_branchement(self):
        """Crée le branchement avec longueur et cote piquage calculées automatiquement."""
        geom = QgsGeometry.fromPolylineXY(self.snapped_points)
        feat = QgsFeature(self.branchement_layer.fields())
        feat.setGeometry(geom)
        feat.setAttribute('id_conduite', self.id_conduite)
        feat.setAttribute('pk_debut',    self.pk_debut)
        feat.setAttribute('sens',        "piquage -> ouvrage")

        # Longueur = longueur de la géométrie
        fields = self.branchement_layer.fields()
        if fields.indexOf('longueur') >= 0:
            feat.setAttribute('longueur', round(geom.length(), 2))

        # Cote piquage = interpolation FE amont/aval à la position pk_debut
        if fields.indexOf('cote_piquage') >= 0:
            cote = self._calc_cote_piquage()
            if cote is not None:
                feat.setAttribute('cote_piquage', round(cote, 3))

        # Diamètre et matériau par défaut
        from ..config_dialog import get_default_params
        defaults = get_default_params()
        key = f"branchement_{self.reseau.lower()}"
        if fields.indexOf('diametre') >= 0 and defaults[key]['diametre']:
            feat.setAttribute('diametre', defaults[key]['diametre'])
        if fields.indexOf('materiau') >= 0 and defaults[key]['materiau']:
            feat.setAttribute('materiau', defaults[key]['materiau'])

        if not self.branchement_layer.isEditable():
            self.branchement_layer.startEditing()
        self.branchement_layer.addFeature(feat)
        self.branchement_layer.commitChanges()

        self.finished.emit()

    def _calc_cote_piquage(self):
        """
        Interpolation linéaire de la cote radier au point de piquage.
        cote = FE_amont + (FE_aval - FE_amont) × (pk_debut / longueur_conduite)
        """
        try:
            conduite_feat = self.conduite_layer.getFeature(self.id_conduite)
        except Exception:
            return None

        cond_geom = conduite_feat.geometry()
        if cond_geom.isEmpty():
            return None

        cond_len = cond_geom.length()
        if cond_len <= 0:
            return None

        line   = cond_geom.asPolyline()
        pt_dep = QgsPointXY(line[0])
        pt_arr = QgsPointXY(line[-1])

        tol = 0.05
        def _fe_at(pt):
            r, _ = nearest_point_feature(self.regard_layer, pt, tol)
            if r is None:
                return None
            try:
                return float(r['fe_radier'])
            except (TypeError, ValueError):
                return None

        fe_dep = _fe_at(pt_dep)
        fe_arr = _fe_at(pt_arr)

        if fe_dep is None or fe_arr is None:
            return None

        return fe_dep + (fe_arr - fe_dep) * (self.pk_debut / cond_len)