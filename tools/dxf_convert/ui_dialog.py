# -*- coding: utf-8 -*-

import os, shutil, traceback
from qgis.PyQt.QtWidgets import (QDialog, QFileDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton,
    QComboBox, QDoubleSpinBox, QSpinBox, QCheckBox, QWidget, QTextBrowser, QGridLayout, QListWidget, QListWidgetItem)
from qgis.PyQt.QtCore import Qt, QCoreApplication
from qgis.core import QgsVectorLayer, QgsProject
from .services.dwg_support import dwg_to_temp_dxf_auto, check_dwg_converter_available, get_converter_help

# OGR fallback imports
try:
    from osgeo import ogr, gdal, osr
    try:
        ogr.UseExceptions()
    except Exception:
        pass
    try:
        gdal.SetConfigOption("DXF_INLINE_BLOCKS", "YES")
        gdal.SetConfigOption("DXF_CLOSED_LINE_AS_POLYGON", "TRUE")
    except Exception:
        pass
except Exception:
    ogr = None
    gdal = None
    osr = None

def _ogr_list_layers(dxf_path: str):
    names = []
    if ogr is None or not os.path.exists(dxf_path):
        return names
    ds = ogr.Open(dxf_path, 0)
    if ds is None:
        return names
    lyr = ds.GetLayerByName("entities") or (ds.GetLayer(0) if ds.GetLayerCount() else None)
    if lyr is None:
        ds = None; return names
    try:
        res = ds.ExecuteSQL("SELECT DISTINCT Layer FROM entities")
        if res:
            for f in res:
                v = f.GetField("Layer")
                if v:
                    names.append(str(v))
            ds.ReleaseResultSet(res)
    except Exception:
        pass
    if not names:
        seen = set()
        lyr.ResetReading()
        for f in lyr:
            try:
                v = f.GetField("Layer")
                if v and v not in seen:
                    seen.add(v); names.append(str(v))
            except Exception:
                pass
    ds = None
    return sorted(set(names))

class CadToGisDialog(QDialog):
    # EPSG presets: (display label, code passed to pyproj/geopandas)
    _EPSG_PRESETS = [
        ("RGF93 CC46  —  EPSG:3946",  "3946"),
        ("RGF93 CC45  —  EPSG:3945",  "3945"),
        ("RGF93 CC47  —  EPSG:3947",  "3947"),
        ("RGF93 CC44  —  EPSG:3944",  "3944"),
        ("RGF93 CC48  —  EPSG:3948",  "3948"),
        ("Lambert-93  —  EPSG:2154",  "2154"),
        ("WGS84       —  EPSG:4326",  "4326"),
    ]

    def _fill_epsg_combo(self, combo):
        for label, code in self._EPSG_PRESETS:
            combo.addItem(label, code)

    def _apply_epsg_to_combo(self, combo, code: str):
        """Select the matching preset if found, otherwise write the raw code."""
        for i in range(combo.count()):
            if combo.itemData(i) == code:
                combo.setCurrentIndex(i)
                return
        combo.setEditText(code)

    def _parse_epsg(self, widget, default=None):
        # Handle QSpinBox
        try:
            return int(widget.value())
        except Exception:
            pass
        # Handle QComboBox: prefer userData (preset code), else currentText
        try:
            data = widget.currentData()
            txt = str(data).strip() if data is not None else widget.currentText().strip()
        except AttributeError:
            try:
                txt = widget.text().strip()
            except Exception:
                return default
        if not txt:
            return default
        try:
            return int(txt)
        except ValueError:
            return txt  # CRS string like "IGNF:RGF93CC46" (typed manually)
        
    def __init__(self, parent_or_iface):
        # Accept either QgisInterface or a QWidget (e.g., QMainWindow)
        try:
            from qgis.utils import iface as _global_iface
        except Exception:
            _global_iface = None
        parent = None
        self.iface = None
        # If we got a QgisInterface-like object
        if hasattr(parent_or_iface, 'mainWindow') and callable(getattr(parent_or_iface, 'mainWindow')):
            self.iface = parent_or_iface
            try:
                parent = parent_or_iface.mainWindow()
            except Exception:
                parent = None
        else:
            # Assume it's already a QWidget parent (e.g., QMainWindow)
            parent = parent_or_iface
            self.iface = _global_iface
        super().__init__(parent)

        self.setWindowTitle("CAD to GIS Converter")
        self.setMinimumWidth(860)

        grid = QGridLayout()

        # Row 0: Input + buttons
        grid.addWidget(QLabel("Input CAD (DXF/DWG)"), 0, 0)
        self.in_edit = QLineEdit()
        self.in_edit.editingFinished.connect(lambda: (
            self._auto_suggest_output(self.in_edit.text().strip()),
            self._apply_detected_dxf_version(self.in_edit.text().strip()),
        ))
        btn_in = QPushButton("Browse"); btn_in.clicked.connect(self.browse_input)
        btn_scan = QPushButton("Scan Layers"); btn_scan.clicked.connect(self.scan_layers)
        wrap = QWidget(); hb = QHBoxLayout(wrap); hb.setContentsMargins(0,0,0,0)
        hb.addWidget(self.in_edit); hb.addWidget(btn_in); hb.addWidget(btn_scan)
        grid.addWidget(wrap, 0, 1, 1, 2)

        # Row 1: Layers CSV + control buttons
        grid.addWidget(QLabel("Layer names (CSV, auto-filled from preview)"), 1, 0)
        self.layers_edit = QLineEdit()
        btn_select_all = QPushButton("Select All"); btn_select_all.clicked.connect(self.select_all_layers)
        btn_clear = QPushButton("Clear"); btn_clear.clicked.connect(self.clear_layers_selection)
        wrap2 = QWidget(); hb2 = QHBoxLayout(wrap2); hb2.setContentsMargins(0,0,0,0)
        hb2.addWidget(self.layers_edit); hb2.addWidget(btn_select_all); hb2.addWidget(btn_clear)
        grid.addWidget(wrap2, 1, 1, 1, 2)

        # Row 2: Layer preview list
        grid.addWidget(QLabel("Layer Preview"), 2, 0, Qt.AlignTop)
        self.layer_list = QListWidget()
        self.layer_list.setSelectionMode(self.layer_list.MultiSelection)
        self.layer_list.itemSelectionChanged.connect(self.sync_layers_csv_from_preview)
        self.layer_list.itemChanged.connect(self.sync_layers_csv_from_preview)
        grid.addWidget(self.layer_list, 2, 1, 1, 2)

        # Row 3: Source EPSG
        grid.addWidget(QLabel("Source EPSG"), 3, 0)
        self.src_epsg = QComboBox(); self.src_epsg.setEditable(True)
        self._fill_epsg_combo(self.src_epsg)
        self.src_epsg.setCurrentIndex(-1); self.src_epsg.setEditText("")
        grid.addWidget(self.src_epsg, 3, 1, 1, 2)

        # Row 4: Target EPSG
        grid.addWidget(QLabel("Target EPSG (optional)"), 4, 0)
        self.tgt_epsg = QComboBox(); self.tgt_epsg.setEditable(True)
        self._fill_epsg_combo(self.tgt_epsg)
        self.tgt_epsg.setCurrentIndex(-1); self.tgt_epsg.setEditText("")
        grid.addWidget(self.tgt_epsg, 4, 1, 1, 2)

        # Row 5: Block mode
        grid.addWidget(QLabel("Block handling"), 5, 0)
        self.block_mode = QComboBox(); self.block_mode.addItems(["keep-merge", "explode"])
        grid.addWidget(self.block_mode, 5, 1, 1, 2)

        # Row 6: Merge tolerance (default 0.0)
        grid.addWidget(QLabel("Line-merge tolerance"), 6, 0)
        self.merge_tol = QDoubleSpinBox(); self.merge_tol.setDecimals(6); self.merge_tol.setRange(0.0, 1e9); self.merge_tol.setValue(0.0)
        grid.addWidget(self.merge_tol, 6, 1, 1, 2)

        # Row 7: Spline tolerance
        grid.addWidget(QLabel("Spline tolerance"), 7, 0)
        self.spline_tol = QDoubleSpinBox(); self.spline_tol.setDecimals(6); self.spline_tol.setRange(0.0, 1e6); self.spline_tol.setValue(0.2)
        grid.addWidget(self.spline_tol, 7, 1, 1, 2)

        # Row 8: Driver
        grid.addWidget(QLabel("Output driver"), 8, 0)
        self.driver = QComboBox(); self.driver.addItems(["GPKG","ESRI Shapefile"])
        grid.addWidget(self.driver, 8, 1, 1, 2)

        # Row 9: Output path
        self.out_label = QLabel("Output GeoPackage (GPKG)")
        grid.addWidget(self.out_label, 9, 0)
        self.out_edit = QLineEdit()
        self.btn_out = QPushButton("Browse"); self.btn_out.clicked.connect(self.browse_output)
        wrap3 = QWidget(); hb3 = QHBoxLayout(wrap3); hb3.setContentsMargins(0,0,0,0)
        hb3.addWidget(self.out_edit); hb3.addWidget(self.btn_out)
        grid.addWidget(wrap3, 9, 1, 1, 2)

        # Row 10: DWG options
        grid.addWidget(QLabel("DWG converter preference"), 10, 0)
        self.dwg_pref = QComboBox(); self.dwg_pref.addItems(["auto","oda","libredwg"])
        grid.addWidget(self.dwg_pref, 10, 1, 1, 2)

        grid.addWidget(QLabel("DXF version for DWG conversion"), 11, 0)
        self.dxf_version = QComboBox(); self.dxf_version.setEditable(True)
        # (label affiché, valeur passée à ODA/libredwg, code AutoCAD interne)
        self._DXF_VERSIONS = [
            ("DXF 2018 (AC1032)", "ACAD2018", "AC1032"),
            ("DXF 2013 (AC1027)", "ACAD2013", "AC1027"),
            ("DXF 2010 (AC1024)", "ACAD2010", "AC1024"),
            ("DXF 2007 (AC1021)", "ACAD2007", "AC1021"),
            ("DXF 2004 (AC1018)", "ACAD2004", "AC1018"),
            ("DXF 2000 (AC1015)", "ACAD2000", "AC1015"),
        ]
        for label, value, _ in self._DXF_VERSIONS:
            self.dxf_version.addItem(label, value)
        self.dxf_version.setCurrentIndex(1)  # défaut ACAD2013
        grid.addWidget(self.dxf_version, 11, 1, 1, 2)

        # Row 12: Options
        grid.addWidget(QLabel("Options"), 12, 0, Qt.AlignTop)
        options_wrap = QWidget(); fl = QVBoxLayout(options_wrap); fl.setContentsMargins(0,0,0,0)
        self.chk_overwrite = QCheckBox("Overwrite existing"); self.chk_overwrite.setChecked(False)
        self.chk_text_attrs = QCheckBox("Format text labels (size / font / underline from DXF)"); self.chk_text_attrs.setChecked(True)
        self.chk_colors = QCheckBox("Apply DXF entity colors (lines, polygons, points)"); self.chk_colors.setChecked(True)
        self.chk_3d = QCheckBox("Include 3D geometry (Z coordinate)"); self.chk_3d.setChecked(False)
        fl.addWidget(self.chk_overwrite)
        fl.addWidget(self.chk_text_attrs)
        fl.addWidget(self.chk_colors)
        fl.addWidget(self.chk_3d)

        # Text scale + charset on the same line
        scale_row = QWidget(); hbs = QHBoxLayout(scale_row); hbs.setContentsMargins(0,0,0,0)
        hbs.addWidget(QLabel("Text scale:"))
        self.txt_scale = QDoubleSpinBox(); self.txt_scale.setDecimals(2); self.txt_scale.setRange(0.01, 100.0); self.txt_scale.setValue(1.0)
        self.txt_scale.setFixedWidth(80)
        hbs.addWidget(self.txt_scale)
        hbs.addSpacing(20)
        hbs.addWidget(QLabel("Charset:"))
        self.charset = QComboBox()
        self.charset.addItems(["utf-8", "cp1252", "latin-1", "cp850", "ascii", "System"])
        hbs.addWidget(self.charset)
        hbs.addStretch(1)
        fl.addWidget(scale_row)

        grid.addWidget(options_wrap, 12, 1, 1, 2)

        # Row 13: Run
        run_bar = QWidget(); hb4 = QHBoxLayout(run_bar); hb4.setContentsMargins(0,0,0,0)
        self.btn_run = QPushButton("Run"); self.btn_run.clicked.connect(self.run_convert)
        hb4.addStretch(1); hb4.addWidget(self.btn_run)
        grid.addWidget(run_bar, 13, 0, 1, 3)

        # Row 14: Log/HTML
        self.out_html = QTextBrowser(); self.out_html.setOpenExternalLinks(True)
        grid.addWidget(self.out_html, 14, 0, 1, 3)

        self.driver.currentIndexChanged.connect(self.on_driver_changed)
        self.on_driver_changed()

        lay = QVBoxLayout(self); lay.addLayout(grid)

    def _get_dxf_version(self) -> str:
        """Renvoie le code ACAD à passer aux convertisseurs DWG (ODA/libredwg)."""
        data = self.dxf_version.currentData()
        if data:
            return str(data)
        txt = self.dxf_version.currentText().strip()
        return txt or "ACAD2013"

    def _detect_dxf_version(self, cad_path: str):
        """Détecte la version d'un fichier DXF/DWG. Retourne ('ACAD2013', 'AC1027') ou (None, None)."""
        if not cad_path or not os.path.isfile(cad_path):
            return None, None
        ext = os.path.splitext(cad_path)[1].lower()
        ac_code = None
        try:
            if ext == ".dwg":
                # Les 6 premiers octets d'un DWG donnent la version (ex: 'AC1032')
                with open(cad_path, "rb") as f:
                    head = f.read(6)
                ac_code = head.decode("ascii", errors="ignore").strip()
            elif ext == ".dxf":
                # Recherche $ACADVER dans l'en-tête (texte ou binaire)
                with open(cad_path, "rb") as f:
                    chunk = f.read(8192)
                idx = chunk.find(b"$ACADVER")
                if idx >= 0:
                    tail = chunk[idx:idx + 200]
                    import re
                    m = re.search(rb"AC10\d{2}", tail)
                    if m:
                        ac_code = m.group(0).decode("ascii")
        except Exception:
            return None, None

        if not ac_code:
            return None, None
        for _label, value, code in self._DXF_VERSIONS:
            if code == ac_code:
                return value, code
        return None, ac_code

    def _apply_detected_dxf_version(self, cad_path: str):
        value, code = self._detect_dxf_version(cad_path)
        if value:
            for i in range(self.dxf_version.count()):
                if self.dxf_version.itemData(i) == value:
                    self.dxf_version.setCurrentIndex(i)
                    self.log(f"<span style='color:#060'><b>DXF version detected:</b> {value} ({code})</span>")
                    return
        elif code:
            self.log(f"<i>DXF version found ({code}) but not in dropdown — keeping current selection.</i>")

    def browse_input(self):
        p, _ = QFileDialog.getOpenFileName(self, "Select CAD file", "", "CAD (*.dxf *.dwg);;DXF (*.dxf);;DWG (*.dwg)")
        if p:
            self.in_edit.setText(p)
            self._auto_suggest_output(p)
            self._apply_detected_dxf_version(p)
            self.scan_layers()

    def _auto_suggest_output(self, cad_path: str):
        """Auto-fill output path only if the field is currently empty."""
        if self.out_edit.text().strip():
            return
        base = os.path.splitext(cad_path)[0]
        if self.driver.currentText() == "GPKG":
            self.out_edit.setText(base + ".gpkg")
        else:
            self.out_edit.setText(os.path.dirname(cad_path))

    def _detect_source_crs(self, dxf_path: str):
        """
        Detect source CRS from DXF/DWG.
        1. Try OGR embedded SRS metadata.
        2. Heuristic from coordinate extent (French projections + WGS84).
        Returns a CRS string (e.g. "2154", "IGNF:RGF93CC46", "4326") or None.
        """
        try:
            from osgeo import ogr
        except Exception:
            return None

        ds = None
        try:
            ds = ogr.Open(dxf_path, 0)
            if ds is None:
                return None
            lyr = ds.GetLayerByName("entities") or (ds.GetLayer(0) if ds.GetLayerCount() else None)
            if lyr is None:
                return None

            # 1 — explicit SRS from file metadata
            srs = lyr.GetSpatialRef()
            if srs and not srs.IsEmpty():
                code = srs.GetAuthorityCode(None)
                auth = srs.GetAuthorityName(None)
                if code and auth:
                    return f"{auth}:{code}"

            # 2 — heuristic from extent
            ext = lyr.GetExtent()  # (minX, maxX, minY, maxY)
            if not ext:
                return None
            minX, maxX, minY, maxY = ext
            cx = (minX + maxX) / 2
            cy = (minY + maxY) / 2

            # WGS84 geographic
            if -180 <= cx <= 180 and -90 <= cy <= 90 and (maxX - minX) < 20:
                return "4326"

            # Lambert-93 EPSG:2154 — false_easting=700000 false_northing=6600000
            if 90_000 <= cx <= 1_300_000 and 5_800_000 <= cy <= 7_300_000:
                return "2154"

            # RGF93 CC zones EPSG:3942-3950 — false_easting=1700000
            # false_northing = (zone-40)*1_000_000 + 200_000
            if 1_300_000 <= cx <= 2_100_000:
                for zone in range(42, 51):
                    y0 = (zone - 40) * 1_000_000 + 200_000
                    if y0 - 700_000 <= cy <= y0 + 700_000:
                        return str(3900 + zone)  # EPSG:3942-3950

            return None
        except Exception:
            return None
        finally:
            ds = None

    def browse_output(self):
        if self.driver.currentText() == "GPKG":
            p, _ = QFileDialog.getSaveFileName(self, "Output GeoPackage", "", "GeoPackage (*.gpkg)")
        else:
            p = QFileDialog.getExistingDirectory(self, "Output folder for Shapefiles")
        if p: self.out_edit.setText(p)

    def on_driver_changed(self):
        if self.driver.currentText() == "GPKG":
            self.out_label.setText("Output GeoPackage (GPKG)")
            self.btn_out.setText("Browse")
            # Update auto-suggested path extension if it was auto-filled
            cur = self.out_edit.text().strip()
            if cur and cur.lower().endswith(".shp"):
                self.out_edit.setText(os.path.splitext(cur)[0] + ".gpkg")
        else:
            self.out_label.setText("Output folder (SHP)")
            self.btn_out.setText("Select Folder")
            cur = self.out_edit.text().strip()
            if cur and cur.lower().endswith(".gpkg"):
                self.out_edit.setText(os.path.dirname(cur))

    def log(self, msg):
        if msg:
            self.out_html.append(msg.replace("\n","<br>"))
            try:
            # 滾到最底，確保新訊息可見
                self.out_html.moveCursor(self.out_html.textCursor().End)
            except Exception:
                pass
        # ★ 關鍵：立即處理事件，讓 UI 不必等任務結束才重畫
            QCoreApplication.processEvents()

    def sync_layers_csv_from_preview(self):
        names = set()
        for i in range(self.layer_list.count()):
            it = self.layer_list.item(i)
            if it.checkState() == Qt.Checked or it.isSelected():
                names.add(it.text())
        self.layers_edit.setText(", ".join(sorted(names)))

    def select_all_layers(self):
        self.layer_list.blockSignals(True)
        for i in range(self.layer_list.count()):
            it = self.layer_list.item(i)
            it.setSelected(True)
            it.setCheckState(Qt.Checked)
        self.layer_list.blockSignals(False)
        self.sync_layers_csv_from_preview()

    def clear_layers_selection(self):
        self.layer_list.blockSignals(True)
        for i in range(self.layer_list.count()):
            it = self.layer_list.item(i)
            it.setSelected(False)
            it.setCheckState(Qt.Unchecked)
        self.layer_list.blockSignals(False)
        self.sync_layers_csv_from_preview()

    def scan_layers(self):
        self.layer_list.clear()
        cad_path = self.in_edit.text().strip()
        if not cad_path or not os.path.isfile(cad_path):
            self.log("<span style='color:#b00'>Please pick a valid DXF/DWG first.</span>")
            return

        # Verifier la disponibilite d'un convertisseur pour les DWG
        if cad_path.lower().endswith(".dwg") and not check_dwg_converter_available():
            self.log(f"<div style='color:#b00'><b>{get_converter_help()}</b></div>")
            return

        temp_dir = None
        try:
            src_for_scan = cad_path
            if cad_path.lower().endswith(".dwg"):
                self.log("Converting DWG → temporary DXF for layer scan ...")
                src_for_scan = dwg_to_temp_dxf_auto(cad_path, prefer=self.dwg_pref.currentText(),
                                                    dxf_version=self._get_dxf_version())
                temp_dir = os.path.dirname(src_for_scan)

            names = []
            try:
                import ezdxf
                self.log("<b>Reading layers via ezdxf ...</b>")
                doc = ezdxf.readfile(src_for_scan)
                names = sorted([str(t.dxf.name) for t in doc.layers])
            except ImportError:
                pass
            except Exception as e:
                self.log(f"<i>ezdxf layer scan failed:</i> {e}")
            if not names:
                self.log("Trying OGR fallback ...")
                names = _ogr_list_layers(src_for_scan)

            if not names:
                self.log("<i>No layers found.</i>")
            else:
                for nm in names:
                    it = QListWidgetItem(nm); it.setCheckState(Qt.Unchecked)
                    self.layer_list.addItem(it)
                self.log(f"Found {len(names)} layer(s).")

            # Auto-detect source CRS
            detected = self._detect_source_crs(src_for_scan)
            if detected:
                self._apply_epsg_to_combo(self.src_epsg, detected)
                label = next((lbl for lbl, code in self._EPSG_PRESETS if code == detected), detected)
                self.log(f"<span style='color:#060'><b>Source CRS detected:</b> {label}</span>")
            else:
                self.log("<i>Source CRS not detected — please set it manually.</i>")
        except Exception as e:
            tb = traceback.format_exc()
            self.log(f"<div style='color:#b00'><b>Layer scan failed:</b> {e}</div>")
            self.log(f"<pre>{tb}</pre>")
        finally:
            if temp_dir and os.path.isdir(temp_dir):
                shutil.rmtree(temp_dir, ignore_errors=True)

    def _setup_qgis_labels(self, layer, text_color=None):
        """
        Enable QGIS labeling on a layer that has a 'text' field (TEXT/MTEXT from DXF).
        Uses the 'rotation' field if present. text_color is a QColor or None.
        """
        try:
            from qgis.core import (QgsPalLayerSettings, QgsVectorLayerSimpleLabeling,
                                   QgsTextFormat, QgsProperty)
            from qgis.PyQt.QtGui import QFont, QColor

            field_names = [f.name() for f in layer.fields()]
            field_lower = {f.lower(): f for f in field_names}

            if "text" not in field_lower:
                return

            text_field = field_lower["text"]

            settings = QgsPalLayerSettings()
            settings.fieldName = text_field
            settings.enabled = True
            settings.placement = QgsPalLayerSettings.OverPoint

            fmt = QgsTextFormat()
            fmt.setFont(QFont("Arial", 7))
            fmt.setSize(7)
            fmt.setColor(text_color if text_color else QColor(30, 30, 30))
            settings.setFormat(fmt)

            if "rotation" in field_lower:
                dp = settings.dataDefinedProperties()
                dp.setProperty(QgsPalLayerSettings.LabelRotation,
                               QgsProperty.fromField(field_lower["rotation"]))
                settings.setDataDefinedProperties(dp)

            settings.displayAll = True
            layer.setLabeling(QgsVectorLayerSimpleLabeling(settings))
            layer.setLabelsEnabled(True)
        except Exception:
            pass

    def run_convert(self):
        try:
            self.btn_run.setEnabled(False)
            from .services.adxf.wrapper import run_adxf_import

            cad_path = self.in_edit.text().strip()
            if not cad_path or not os.path.isfile(cad_path):
                raise RuntimeError(f"File not found: {cad_path}")

            # Verifier la disponibilite d'un convertisseur pour les DWG
            if cad_path.lower().endswith(".dwg") and not check_dwg_converter_available():
                self.log(f"<div style='color:#b00'><b>{get_converter_help()}</b></div>")
                return

            layers_csv = self.layers_edit.text().strip()
            target_layers = [s.strip() for s in layers_csv.split(',') if s.strip()] or None
            src_epsg = self._parse_epsg(self.src_epsg) or 4326
            driver = self.driver.currentText()
            out_form = "GPKG" if driver == "GPKG" else "SHP"
            out_path = self.out_edit.text().strip()
            if not out_path:
                raise RuntimeError("Please specify output path.")
            dwg_pref   = self.dwg_pref.currentText()
            dxf_version = self._get_dxf_version()
            overwrite  = self.chk_overwrite.isChecked()
            use_colors = self.chk_colors.isChecked()

            # DWG → temp DXF
            input_for_convert = cad_path
            temp_dir = None
            if cad_path.lower().endswith(".dwg"):
                self.log("Converting DWG → temporary DXF ...")
                temp_dxf = dwg_to_temp_dxf_auto(cad_path, prefer=dwg_pref, dxf_version=dxf_version)
                input_for_convert = temp_dxf
                temp_dir = os.path.dirname(temp_dxf)

            try:
                self.log("<b>Starting OGR/GDAL conversion engine ...</b>")
                run_adxf_import(
                    dxf_path        = input_for_convert,
                    out_path        = out_path,
                    src_epsg        = src_epsg,
                    out_form        = out_form,
                    log_fn          = lambda s: self.log(s or ""),
                    target_layers   = target_layers,
                    overwrite       = overwrite,
                    by_layer        = True,
                    format_text     = self.chk_text_attrs.isChecked(),
                    use_color_line  = use_colors,
                    use_color_poly  = use_colors,
                    use_color_point = use_colors,
                    txt_factor      = float(self.txt_scale.value()),
                    charset         = self.charset.currentText(),
                    gen_3d          = self.chk_3d.isChecked(),
                    raw_code        = False,
                )
            finally:
                if temp_dir and os.path.isdir(temp_dir):
                    shutil.rmtree(temp_dir, ignore_errors=True)

        except Exception as e:
            tb = traceback.format_exc()
            self.out_html.append(f"<div style='color:#b00'><b>ERROR:</b> {e}</div><pre>{tb}</pre>")
        finally:
            self.btn_run.setEnabled(True)
