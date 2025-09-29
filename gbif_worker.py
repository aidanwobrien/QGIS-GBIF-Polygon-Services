import requests
import processing
from urllib import request
import os
import json
from datetime import datetime

from qgis.core import (
    QgsProject,
    QgsVectorLayer,
    QgsField,
    QgsFeature,
    QgsGeometry,
    QgsPointXY,
    QgsFields,
)

from qgis.PyQt.QtCore import QVariant, QCoreApplication, Qt
from qgis.PyQt.QtWidgets import (
    QDialog, QVBoxLayout, QLabel, QDialogButtonBox, QFormLayout, QProgressDialog,
    QLineEdit, QWidget, QHBoxLayout, QMessageBox
    )
from qgis.gui import QgsMapLayerComboBox
from qgis.core import QgsMapLayerProxyModel, Qgis, QgsMessageLog, QgsCoordinateTransform, QgsCoordinateReferenceSystem
from PyQt5.QtCore import Qt
from qgis.utils import iface




def add_metadata_to_project(species_name, start_year, end_year, layer_name, pyqgis_group):
    """Create a metadata memory layer and add it to the project layers pane."""
    
    # Make a simple memory table
    vl = QgsVectorLayer("NoGeometry?crs=EPSG:4326", f"{layer_name} Metadata", "memory")
    pr = vl.dataProvider()

    # Define fields
    fields = QgsFields()
    fields.append(QgsField("timestamp", QVariant.String))
    fields.append(QgsField("species_name", QVariant.String))
    fields.append(QgsField("start_year", QVariant.String))
    fields.append(QgsField("end_year", QVariant.String))
    fields.append(QgsField("layer", QVariant.String))
    pr.addAttributes(fields)
    vl.updateFields()

    # Add one record
    feat = QgsFeature()
    feat.setAttributes([
        datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        species_name or "",
        start_year or "",
        end_year or "",
        layer_name or ""
    ])
    pr.addFeature(feat)

    # Add to project
    QgsProject.instance().addMapLayer(vl, False)
    pyqgis_group.addLayer(vl)       
    return vl

# ---------- Group Management ----------
def create_unique_gbif_group():
    projInstance = QgsProject.instance()
    treeRoot = projInstance.layerTreeRoot()
    counter = 0
    group_name = 'GBIF Occurrences-' + str(counter)

    while treeRoot.findGroup(group_name):
        counter += 1
        group_name = 'GBIF Occurrences-' + str(counter)

    return treeRoot.insertGroup(0, group_name)

# ---------- Check Network Connection --------------

def internet_on():
    try:
        request.urlopen('https://api.gbif.org/', timeout=1)
        return True
    except request.URLError as err: 
        return False

# --------- Create Fetching Progress Dialog ----------
def create_progress_dialog(total_estimate, task_name="Fetching GBIF Points..."):
    progress = QProgressDialog(task_name, "Cancel", 0, total_estimate)
    progress.setWindowModality(Qt.WindowModal)  # Modal window so user cannot interact with the map while loading
    progress.setMinimumDuration(0)  # Show dialog immediately
    progress.setValue(0)
    return progress

# ----------- Create Clipping Progress Dialog
def create_clipping_progress_dialog(total_count):
    progress = QProgressDialog("Clipping features...", "Cancel", 0, total_count)
    progress.setWindowModality(Qt.WindowModal)  # Modal window so user cannot interact with the map while clipping
    progress.setMinimumDuration(0)
    progress.setValue(0)
    return progress

# ---------- Fetching Data ----------
def fetch_gbif_data(url):
    response = requests.get(url)
    return response.json()


# ---------- Create In-Memory Layer ----------
def create_gbif_layer(
                        polygon, 
                        layer_id, 
                        species_name, 
                        start_year, 
                        end_year, 
                        progress
                      ):
    

    result_layer = QgsVectorLayer('Point?crs=EPSG:4326', f'GBIF Occurrences-{layer_id}', 'memory')
    provider = result_layer.dataProvider()

    fields = QgsFields()
    fields.append(QgsField('gbifID', QVariant.String))
    fields.append(QgsField('species', QVariant.String))
    fields.append(QgsField('country', QVariant.String))
    fields.append(QgsField('eventDate', QVariant.String))
    fields.append(QgsField('catalogNumber', QVariant.String))
    fields.append(QgsField('identifiedBy', QVariant.String))
    fields.append(QgsField('individualCount', QVariant.String))
    provider.addAttributes(fields)
    result_layer.updateFields()

    extent = polygon.boundingBox()
    min_x, min_y = extent.xMinimum(), extent.yMinimum()
    max_x, max_y = extent.xMaximum(), extent.yMaximum()

    year_param = build_gbif_year_param(start_year, end_year)

    # First get the total count
    count_url = (
        'https://api.gbif.org/v1/occurrence/search?'
        f'geometry=POLYGON(({min_x}%20{min_y},{max_x}%20{min_y},{max_x}%20{max_y},{min_x}%20{max_y},{min_x}%20{min_y}))'
        '&limit=0'
        f'&scientificName={species_name}'
        f'{year_param}'
    )
    count_data = fetch_gbif_data(count_url)
    total_estimate = min(count_data.get('count', 0), 100000)
    if total_estimate == 0:
        return result_layer, 0

    progress.setMaximum(total_estimate)
    progress.setValue(0)

    offset = 0
    added_records = 0

    while True:
        url = (
            'https://api.gbif.org/v1/occurrence/search?'
            f'geometry=POLYGON(({min_x}%20{min_y},{max_x}%20{min_y},{max_x}%20{max_y},{min_x}%20{max_y},{min_x}%20{min_y}))'
            f'&limit=300&offset={offset}'
            f'&scientificName={species_name}'
            f'{year_param}'
        )
        data = fetch_gbif_data(url)

        if 'results' not in data or not data['results']:
            break

        for record in data['results']:
            lat = record.get('decimalLatitude')
            lon = record.get('decimalLongitude')

            if lat is not None and lon is not None:
                feature = QgsFeature()
                feature.setGeometry(QgsGeometry.fromPointXY(QgsPointXY(lon, lat)))
                feature.setAttributes([ 
                    record.get('gbifID', 'Unknown'),
                    record.get('species', 'Unknown'),
                    record.get('country', 'Unknown'),
                    record.get('eventDate', 'Unknown'),
                    record.get('catalogNumber', 'Unknown'),
                    record.get('identifiedBy', 'Unknown'),
                    record.get('individualCount', 'Unknown')
                ])
                provider.addFeatures([feature])
                added_records += 1

                if progress.wasCanceled():
                    return None, 0

                progress.setValue(added_records)
                progress.setLabelText(f"Fetching GBIF Points... {added_records} / {total_estimate}")
                QCoreApplication.processEvents()

        if len(data['results']) < 300:
            break
        offset += 300

    return result_layer, added_records

def build_gbif_year_param(start_year, end_year):
    """Return a properly formatted GBIF year parameter."""
    start_year = start_year.strip() if start_year else ""
    end_year = end_year.strip() if end_year else ""
    current_year = str(datetime.now().year)

    if start_year and end_year:
        return f"&year={start_year},{end_year}"
    elif start_year:
        return f"&year={start_year},{current_year}"
    elif end_year:
        return f"&year=0,{end_year}"
    else:
        return ""

# ---------- Clipping Layer ----------
def clipping(input_layer, overlay_layer, layer_id, pyqgis_group):
    # Create clipping progress dialog
    total_features = len([f for f in input_layer.getFeatures()])
    progress = create_clipping_progress_dialog(total_features)

    layer_clip = processing.run('qgis:clip',
        {'INPUT': input_layer,
        'OVERLAY': overlay_layer,
        'OUTPUT': "memory:"}
    )["OUTPUT"]

    layer_clip.setName('result' + str(layer_id))
    layer_clip_result = QgsProject.instance().addMapLayer(layer_clip, False)

    # count the number of results
    feature_count = len([f for f in layer_clip.getFeatures()])
    QgsMessageLog.logMessage(f"Clipping {feature_count} of the {total_features} fetched records to feature {layer_id}", "GBIF-Services", level=Qgis.Info)

    # Update the clipping progress bar
    progress.setMaximum(total_features)
    progress.setValue(0)

    feature_idx = 0
    for feature in layer_clip.getFeatures():
        feature_idx += 1
        progress.setValue(feature_idx)
        progress.setLabelText(f"Clipping features... {feature_idx} / {feature_count}")
        QCoreApplication.processEvents()

        if progress.wasCanceled():
            # print("Script cancelled during clipping.")
            return None
        
    print(f"{feature_count} GBIF occurrences within polygon feature {layer_id} have been added to the map.")
    iface.messageBar().pushMessage("Results added", f"{feature_count} GBIF occurrences within polygon feature {layer_id} have been added to the map.", level=Qgis.Info)
    QgsMessageLog.logMessage(f"{feature_count} GBIF occurrences within polygon feature {layer_id} have been added to the map", "GBIF-Services", level=Qgis.Info)
        
    pyqgis_group.addLayer(layer_clip_result)

    return layer_clip_result


# ---------- Warning Dialog ----------
class WarningDialog(QDialog):
    def __init__(self, warn_str):
        super().__init__()
        self.setWindowTitle("Query Warning")

        layout = QVBoxLayout()
        layout.addWidget(QLabel(warn_str))

        button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)

        layout.addWidget(button_box)
        self.setLayout(layout)


# ---------- Layer Selection Dialog ----------
class LayerDialog(QDialog):
    def __init__(self):
        super().__init__()

        self.setWindowTitle("Select Filters for Query")
        self.setMinimumWidth(500)
        self.setMinimumHeight(200)

        # Map Layer Selector
        self.map_layer_combo_box = QgsMapLayerComboBox()
        self.map_layer_combo_box.setCurrentIndex(-1)
        self.map_layer_combo_box.setFilters(QgsMapLayerProxyModel.PolygonLayer)

        # Scientific Name Filter
        self.species_text = QLineEdit()
        self.species_text.setPlaceholderText("Filter by scientific name (or leave blank)")
        self.species_text.setToolTip("Filter by scientific name (or leave blank)")

        # Year Range Filter
        self.start_year = QLineEdit()
        self.start_year.setPlaceholderText("e.g. 2000")
        self.start_year.setMaximumWidth(80)

        self.end_year = QLineEdit()
        self.end_year.setPlaceholderText("e.g. 2025")
        self.end_year.setMaximumWidth(80)

        year_range_widget = QWidget()
        year_range_layout = QHBoxLayout(year_range_widget)
        year_range_layout.setContentsMargins(0, 0, 0, 0)
        year_range_layout.setSpacing(10)
        year_range_layout.addWidget(QLabel("Start:"))
        year_range_layout.addWidget(self.start_year)
        year_range_layout.addWidget(QLabel("End:"))
        year_range_layout.addWidget(self.end_year)
        year_range_layout.addStretch()

        # Form Layout
        form_layout = QFormLayout()
        form_layout.setLabelAlignment(Qt.AlignRight)
        form_layout.setFormAlignment(Qt.AlignTop)
        form_layout.setHorizontalSpacing(20)
        form_layout.setVerticalSpacing(12)

        form_layout.addRow("Polygon Layer:", self.map_layer_combo_box)
        form_layout.addRow("Scientific Name:", self.species_text)
        form_layout.addRow("Year Range:", year_range_widget)

        # OK / Cancel buttons
        self.button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        self.button_box.accepted.connect(self.validate_and_accept)
        self.button_box.rejected.connect(self.reject)

        # Main Layout
        main_layout = QVBoxLayout(self)
        main_layout.addLayout(form_layout)
        main_layout.addStretch()
        main_layout.addWidget(self.button_box, alignment=Qt.AlignRight)

    def validate_and_accept(self):
        selected_layer, layer_name = self.get_selected_layer()
        
        if not selected_layer:
            QMessageBox.warning(
                self,
                "No layer selected",
                "Please select a polygon layer before continuing."
            )
            # Reject dialog so run() knows it was cancelled
            # self.reject()
            return
        # Otherwise, accept normally
        self.accept()

    def get_selected_layer(self):
        layer = self.map_layer_combo_box.currentLayer()
        if layer:
            return layer, layer.name()
        return None, None
    
    def get_species(self):
        return self.species_text.text()

    def get_date_range(self):
        return self.start_year.text(), self.end_year.text()
    
