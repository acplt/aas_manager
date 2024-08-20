#  Copyright (C) 2021  Igor Garmaev, garmaev@gmx.net
#
#  This program is made available under the terms of the GNU General Public License as published by
#  the Free Software Foundation, either version 3 of the License, or (at your option) any later version.
#
#  This program is distributed in the hope that it will be useful, but WITHOUT ANY WARRANTY;
#  without even the implied warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.
#
#  A copy of the GNU General Public License is available at http://www.gnu.org/licenses/

import sys
import logging
import time

from PyQt6 import QtWidgets
from PyQt6.QtWidgets import *
from PyQt6 import QtWebEngineWidgets
from PyQt6.QtCore import Qt
from PyQt6.QtTest import QTest

                        
from basyx.aas.model import AssetAdministrationShell, ConceptDescription, Submodel, Property, \
    Entity, Capability, Operation, RelationshipElement, AnnotatedRelationshipElement, Range, Blob, File, \
    ReferenceElement, DataElement, AdministrativeInformation, AbstractObjectStore, \
    Namespace, SubmodelElementCollection, SubmodelElement, ModelReference, Referable, Identifiable, \
    Key, Qualifier, BasicEventElement, SubmodelElementList, datatypes, LangStringSet, DictObjectStore


logging.basicConfig(level=logging.INFO, filename="log.log", filemode="w",
                    format="%(asctime)s | %(levelname)s | %(message)s")
        
def find_focused_widget():
    app = QApplication.instance()
    if app is not None:
        focused_widget = app.focusWidget()
        if focused_widget is not None:
            print("Widget with focus:", focused_widget)
        else:
            print("No widget currently has focus.")
            
def main():
    app = QtWidgets.QApplication(sys.argv)
    from aas_editor.editorApp import EditorApp as CurrentApp
    
    fileToOpen = sys.argv[1] if len(sys.argv) > 1 else None

    window = CurrentApp(fileToOpen)
    
    window.show()
    window.mainTreeView.setFocus()
                
    tree = window.mainTreeView
    
    prev_time = time.time()
    while True:
        from aas_editor import dialogs
        app.processEvents()
        current_time = time.time()
        if int(current_time) != int(prev_time):
        
            tree = window.mainTreeView
            
            tree.setFocusPolicy(Qt.StrongFocus)
            QTest.mouseClick(tree, Qt.LeftButton)
            tree.setFocus(Qt.NoFocusReason) 
                    
            tree.expandAll()
            
            model = tree.model()
            root = model.index(0, 0)
            
            if (int(current_time) - int(prev_time)) > 100:
                break
            
            elif root.isValid():
                root_data = model.data(root)
                print(f"Iterating Through {root_data}")
                for row in range(model.rowCount(root)):
                    item_index = model.index(row, 0, root)
                    item_data = model.data(item_index)
            
                    if item_data == 'submodels':
                        tree.setCurrentIndex(item_index)
                        app.processEvents()
                        time.sleep(1)
                        dialog = dialogs.AddObjDialog(Submodel, parent=tree, objVal=None, title='', rmDefParams=False)
                        dialog.show()
                        
                        time.sleep(1)
                        app.processEvents()
                        time.sleep(1)
                        
                        app.processEvents()
                        dialog.accept()
                        obj = tree._getObjFromDialog(dialog)
                        dialog.deleteLater()
                        result = tree._setItemData(item_index, obj, 1130)   
                        
                        time.sleep(1)
                        app.processEvents()
                        time.sleep(1)
                        
                        tree.onDelClear()
                        
                        time.sleep(1)
                        app.processEvents()
                        time.sleep(1)
                        
                    elif item_data == 'shells':
                        tree.setCurrentIndex(item_index)
                        app.processEvents()
                        dialog = dialogs.AddObjDialog(AssetAdministrationShell, parent=tree, objVal=None, title='', rmDefParams=False)
                        dialog.show()
                        
                        time.sleep(1)
                        app.processEvents()
                        time.sleep(1)
                        
                        dialog.reject()
                        dialog.deleteLater()
                        
                        time.sleep(1)
                        app.processEvents()
                        time.sleep(1)
                       
                    elif item_data == 'fileStore':
                        tree.setCurrentIndex(item_index)
                        app.processEvents()
                        dialog = dialogs.AddObjDialog(File, parent=tree, objVal=None, title='', rmDefParams=False)
                        dialog.show()

                        time.sleep(1)
                        app.processEvents()
                        time.sleep(1)
                        
                        dialog.reject()
                        dialog.deleteLater()
                        
                        time.sleep(1)
                        app.processEvents()
                        time.sleep(1)
                        
                    elif item_data == 'concept_descriptions':
                        tree.setCurrentIndex(item_index)
                        app.processEvents()
                        dialog = dialogs.AddObjDialog(ConceptDescription, parent=tree, objVal=None, title='', rmDefParams=False)
                        dialog.show()

                        time.sleep(1)
                        app.processEvents()
                        time.sleep(1)
                        
                        dialog.reject()
                        dialog.deleteLater()
                        
                        time.sleep(1)
                        app.processEvents()
                        time.sleep(1)

if __name__ == "__main__":
    main()
