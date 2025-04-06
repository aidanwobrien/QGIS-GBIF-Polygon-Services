import requests
import processing

from qgis.core import (
    QgsProject,
    QgsVectorLayer,
    QgsField,
    QgsFeature,
    QgsGeometry,
    QgsPointXY,
    QgsFields,
)

from qgis.PyQt.QtCore import QVariant
from qgis.PyQt.QtWidgets import QDialog, QVBoxLayout, QLabel, QDialogButtonBox, QFormLayout
from qgis.gui import QgsMapLayerComboBox
from qgis.core import QgsMapLayerProxyModel
from qgis.core import QgsMapLayerProxyModel, Qgis, QgsMessageLog

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


# ---------- Fetching Data ----------
def fetch_gbif_data(url):
    response = requests.get(url)
    return response.json()


# ---------- Create In-Memory Layer ----------
def create_gbif_layer(polygon, layer_id):
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

    base_url = (
        'https://api.gbif.org/v1/occurrence/search?'
        f'geometry=POLYGON(({min_x}%20{min_y},{max_x}%20{min_y},{max_x}%20{max_y},{min_x}%20{max_y},{min_x}%20{min_y}))'
        '&limit=300'
    )

    offset = 0
    total_records = 0

    while True:
        url = f"{base_url}&offset={offset}"
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

        total_records += len(data['results'])
        if len(data['results']) == 0:
            break

        offset += 300

    return result_layer, total_records


# ---------- Clipping Layer ----------
def clipping(input_layer, overlay_layer, layer_id, pyqgis_group):
    layer_clip = processing.run('qgis:clip', {
        'INPUT': input_layer,
        'OVERLAY': overlay_layer,
        'OUTPUT': "memory:"
    })["OUTPUT"]

    layer_clip.setName(f'result{layer_id}')
    layer_clip_result = QgsProject.instance().addMapLayer(layer_clip, False)

    feature_count = len([f for f in layer_clip.getFeatures()])
    QgsMessageLog.logMessage(f"{feature_count} GBIF occurrences within polygon layer {layer_id} have been added to the map.", 
                            "GBIF-Services", 
                            level=Qgis.Info)
    print(f"{feature_count} GBIF occurrences within polygon layer {layer_id} have been added to the map.")

    return pyqgis_group.addLayer(layer_clip_result)


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
        self.setWindowTitle("Select Layer for Query")
        self.setMinimumSize(500, 100)

        self.map_layer_combo_box = QgsMapLayerComboBox()
        self.map_layer_combo_box.setCurrentIndex(-1)
        self.map_layer_combo_box.setFilters(QgsMapLayerProxyModel.VectorLayer)

        layout = QFormLayout()
        layout.addWidget(self.map_layer_combo_box)
        self.setLayout(layout)

        self.button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        self.button_box.accepted.connect(self.validate_and_accept)
        self.button_box.rejected.connect(self.reject)
        layout.addWidget(self.button_box)

    def validate_and_accept(self):
        if self.map_layer_combo_box.currentLayer():
            self.accept()
        else:
            QgsMessageLog.logMessage("No layer selected!", "GBIF-Services", level=Qgis.Info)
            print("No layer selected!")
            self.reject()

    def get_selected_layer(self):
        layer = self.map_layer_combo_box.currentLayer()
        if layer:
            return layer, layer.name()
        return None, None
