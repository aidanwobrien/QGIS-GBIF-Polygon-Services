Plugin Builder Results

Your plugin GBIFServices was created in:
    /Users/aidanobrien/Desktop/coding/qgis-plugin-dev/gbif_services

Your QGIS plugin directory is located at:
    /Users/aidanobrien/Library/Application Support/QGIS/QGIS3/profiles/default/python/plugins

What's Next:

  * Copy the entire directory containing your new plugin to the QGIS plugin
    directory

  * Compile the resources file using pyrcc5

  * Run the tests (``make test``)

  * Test the plugin by enabling it in the QGIS plugin manager

  * Customize it by editing the implementation file: ``gbif_services.py``

  * Create your own custom icon, replacing the default icon.png

  * Modify your user interface by opening GBIFServices_dialog_base.ui in Qt Designer

  * You can use the Makefile to compile your Ui and resource files when
    you make changes. This requires GNU make (gmake)

For more information, see the PyQGIS Developer Cookbook at:
http://www.qgis.org/pyqgis-cookbook/index.html

(C) 2011-2018 GeoApt LLC - geoapt.com


---- Aidans Notes ----

- All icons are 24pixels x 24pixels

1. Use Plugin Builder 3 Within QGIS to make the plugin structure
2. In terminal, navigate to the directory where you made the plugin
3. Set up python virtual environments 
     $ python3 -m vent py_env
     $ source py_env/bin/activate
4. Install pyrcc5
     $ pip install PyQt5
5. Compile resource file. Convert the .qrc resource file to Python file using pyrcc5
     $ pyrcc5 resources.qrc -o resources.py
6. Create a Symlink - Make a symbolic link in the QGIS plugin directory pointing to the plugin development directory
     $ cd /Users/<username>/Library/Application\ Support/QGIS/QGIS3/profiles/default/python/plugins
     $ ln -s <plugin development directory>
7. Verify the symlink with ls -l Users/<username>/Library/Application \ Support/QGIS/QGIS3/profiles/defualt/python/plugins
8. Restart QGIS

Remember, if you change the icon.png, you’ll have to recompile the resources.qrc
