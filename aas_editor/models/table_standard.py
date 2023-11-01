#  Copyright (C) 2021  Igor Garmaev, garmaev@gmx.net
#
#  This program is made available under the terms of the GNU General Public License as published by
#  the Free Software Foundation, either version 3 of the License, or (at your option) any later version.
#
#  This program is distributed in the hope that it will be useful, but WITHOUT ANY WARRANTY;
#  without even the implied warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.
#
#  A copy of the GNU General Public License is available at http://www.gnu.org/licenses/

import copy
import logging
import traceback
from collections import namedtuple, deque
from enum import Enum
from typing import Any, Iterable, Union, AbstractSet, List

from PyQt5.QtCore import QAbstractItemModel, QVariant, QModelIndex, Qt, QItemSelection, QSize, \
    QPersistentModelIndex
from PyQt5.QtGui import QFont

from aas_editor.models import DetailedInfoItem, StandardItem, PackTreeViewItem
from aas_editor.package import Package
from aas_editor.settings.app_settings import NAME_ROLE, OBJECT_ROLE, ATTRIBUTE_COLUMN, \
    VALUE_COLUMN, PACKAGE_ROLE, PACK_ITEM_ROLE, DEFAULT_FONT, ADD_ITEM_ROLE, CLEAR_ROW_ROLE, \
    DATA_CHANGE_FAILED_ROLE, IS_LINK_ROLE, TYPE_COLUMN, \
    TYPE_CHECK_ROLE, TYPE_ROLE, UNDO_ROLE, REDO_ROLE, MAX_UNDOS, UPDATE_ROLE, TYPE_HINT_COLUMN, COLUMN_NAME_ROLE, \
    LINKED_ITEM_ROLE, COPY_ROLE
from aas_editor.settings import NOT_GIVEN
from aas_editor.settings.colors import LINK_BLUE, CHANGED_BLUE, RED, NEW_GREEN
from aas_editor.utils.util import delAASParents

from aas_editor.utils.util_classes import ClassesInfo
from aas_editor.additional.classes import DictItem
from aas_editor.utils.util_type import isIterable

SetDataItem = namedtuple("SetDataItem", ("index", "value", "role"))


class StandardTable(QAbstractItemModel):
    currFont = QFont(DEFAULT_FONT)

    def __init__(self, columns=("Item",), rootItem: StandardItem = None):
        super(StandardTable, self).__init__()
        self._rootItem = rootItem
        self._columns = columns
        self.lastErrorMsg = ""
        self.undo: deque[SetDataItem] = deque(maxlen=MAX_UNDOS)
        self.redo: List[SetDataItem] = []
        self.changedItems: List[QModelIndex] = []

    def index(self, row: int, column: int = 0, parent: QModelIndex = QModelIndex()) -> QModelIndex:
        if not self.hasIndex(row, column, parent):
            return QModelIndex()
        parentObj = self.objByIndex(parent)
        return self.createIndex(row, column, parentObj.children()[row])

    def parent(self, child: QModelIndex) -> QModelIndex:
        if not child.isValid():
            return QModelIndex()

        try:
            childObj = self.objByIndex(child)
            parentObj = childObj.parent()
        except (RuntimeError, AttributeError) as e:
            logging.exception(e)
            return QModelIndex()

        if parentObj == self._rootItem or not parentObj:
            return QModelIndex()

        grandParentObj = parentObj.parent()
        row = grandParentObj.children().index(parentObj)
        return self.createIndex(row, 0, parentObj)

    def rowCount(self, parent: QModelIndex = QModelIndex()) -> int:
        return len(self.objByIndex(parent).children())

    def columnCount(self, parent: QModelIndex = QModelIndex()) -> int:
        return len(self._columns)

    def headerData(self, section: int, orientation: Qt.Orientation, role: int = ...) -> Any:
        if role != Qt.DisplayRole:
            return None
        if orientation == Qt.Horizontal:
            return self._columns[section]

    def flags(self, index: QModelIndex) -> Qt.ItemFlags:
        if not index.isValid() or index.data(Qt.DisplayRole) is None:
            return Qt.NoItemFlags

        if index.column() in (TYPE_COLUMN, TYPE_HINT_COLUMN):
            return Qt.ItemIsEnabled | Qt.ItemIsSelectable

        return Qt.ItemIsEditable | Qt.ItemIsEnabled | Qt.ItemIsSelectable

    def hasChildren(self, parent: QModelIndex = ...) -> bool:
        return True if self.rowCount(parent) else False

    def objByIndex(self, index: QModelIndex):
        if not index.isValid():
            return self._rootItem
        return index.internalPointer()

    def iterItems(self, parent: QModelIndex = QModelIndex()) -> QModelIndex:
        def recurse(parent: QModelIndex):
            for row in range(self.rowCount(parent)):
                childIndex = self.index(row, 0, parent)
                yield childIndex
                child = self.objByIndex(childIndex)
                if child.children():
                    yield from recurse(childIndex)
        yield from recurse(parent)

    def match(self, start: QModelIndex, role: int, value: Any, hits: int = ...,
              flags: Union[Qt.MatchFlags, Qt.MatchFlag] = ...) -> List[QModelIndex]:
        kwargs = {}
        if hits is not ...:
            kwargs["hits"] = hits
        if flags is not ...:
            kwargs["flags"] = flags

        if role == OBJECT_ROLE and hits != 0:
            res = []
            for item in self.iterItems(start):
                logging.info("match for: %s", item.data(NAME_ROLE))
                try:
                    if (item.data(OBJECT_ROLE) is value) or (item.data(OBJECT_ROLE) == value):
                        res.append(item)
                except AttributeError:
                    continue
                if hits == len(res):
                    break
            return res
        elif role == TYPE_ROLE and hits != 0:
            res = []
            for item in self.iterItems(start):
                logging.info("match for: %s", item.data(NAME_ROLE))
                try:
                    if issubclass(value, item.data(TYPE_ROLE)):
                        res.append(item)
                except AttributeError:
                    continue
                if hits == len(res):
                    break
            return res
        elif role == Qt.DisplayRole and hits != 0:
            res = []
            for item in self.iterItems(start):
                logging.info("match for: %s", item.data(NAME_ROLE))
                try:
                    if value == item.data(Qt.DisplayRole):
                        res.append(item)
                except AttributeError:
                    continue
                if hits == len(res):
                    break
            return res
        else:
            return super(StandardTable, self).match(start, role, value, **kwargs)

    def addItem(self, obj: Union[Package, 'SubmodelElement', Iterable],
                parent: QModelIndex = QModelIndex()):
        parent = parent.siblingAtColumn(0)
        parentItem = self.objByIndex(parent)
        parentObj = parentItem.data(OBJECT_ROLE)
        parentObjCls = type(parentObj)
        parentName = parent.data(NAME_ROLE)

        kwargs = {
            "obj": obj,
            "parent": parentItem,
        }
        if isinstance(obj, Package):
            kwargs["parent"] = self._rootItem
            kwargs["new"] = False
            itemTyp = PackTreeViewItem
        elif parentName in Package.addableAttrs():
            package: Package = parent.data(PACKAGE_ROLE)
            package.add(obj)
            itemTyp = PackTreeViewItem
        elif ClassesInfo.changedParentObject(parentObjCls): #FIXME: Refactor
            parentObj = getattr(parentObj, ClassesInfo.changedParentObject(parentObjCls))
            parentObj.add(obj)
            itemTyp = PackTreeViewItem
        elif isinstance(parentObj, AbstractSet):
            parentObj.add(obj)
            itemTyp = DetailedInfoItem
        elif isinstance(parentObj, list):
            parentObj.append(obj)
            itemTyp = DetailedInfoItem
        elif isinstance(parentObj, dict):
            parentObj[obj.key] = obj.value
            itemTyp = DetailedInfoItem
        else:
            raise AttributeError(
                f"Object couldn't be added: parent obj type is not appendable: {type(parentObj)}")
        return self._addItem(parent, itemTyp, kwargs)

    def _addItem(self, parent: QModelIndex, itemTyp, kwargs):
        self.beginInsertRows(parent, self.rowCount(parent), self.rowCount(parent))
        item = itemTyp(**kwargs)
        self.endInsertRows()
        itemIndex = self.index(item.row(), 0, parent)
        self.undo.append(SetDataItem(index=QPersistentModelIndex(itemIndex), value=NOT_GIVEN, role=CLEAR_ROW_ROLE))
        self.redo.clear()
        return itemIndex

    def insertRows(self, row: int, count: int, parent: QModelIndex = ...) -> bool:
        self.beginInsertRows(parent, row, row + count - 1)
        self.endInsertRows()
        return True

    def update(self, index: QModelIndex):
        """Update item: remove all children rows, then add updated rows"""
        if not index.isValid():
            return QVariant()
        if self.hasChildren(index):
            self.beginRemoveRows(index, 0, max(self.rowCount(index)-1, 0))
            self.removeRows(0, self.rowCount(index), index)
            self.endRemoveRows()
            self.rowsRemoved.emit(index, 0, max(self.rowCount(index)-1, 0))
            self.dataChanged.emit(index, index.child(self.rowCount(index) - 1,
                                                     self.columnCount(index) - 1))

        self.objByIndex(index).populate()
        if self.hasChildren(index):
            self.beginInsertRows(index, 0, max(self.rowCount(index)-1, 0))
            self.endInsertRows()
            self.rowsInserted.emit(index, 0, max(self.rowCount(index)-1, 0))
            self.dataChanged.emit(index, index.child(self.rowCount(index)-1, self.columnCount(index)-1))
        else:
            self.dataChanged.emit(index, index)
        return True

    def data(self, index: QModelIndex, role: int = ...) -> Any:
        if role == Qt.ForegroundRole:
            return self._getFgColor(index)
        if role == Qt.FontRole:
            return self._getFont(index)
        if role == Qt.SizeHintRole:
            fontSize = self.currFont.pointSize()
            return QSize(-1, int((fontSize+2)*1.9))
        if role == Qt.TextAlignmentRole:
            return Qt.AlignLeft | Qt.AlignVCenter
        if role == DATA_CHANGE_FAILED_ROLE:
            return self.lastErrorMsg
        if role == UNDO_ROLE:
            return self.undo
        if role == REDO_ROLE:
            return self.redo
        if role == COLUMN_NAME_ROLE:
            column = index.column()
            return self._columns[column]
        if role == LINKED_ITEM_ROLE:
            return self.getLinkedItem(index)
        if role == COPY_ROLE:
            try:
                if index.column() in (ATTRIBUTE_COLUMN, VALUE_COLUMN):
                    objToCopy = index.data(OBJECT_ROLE)
                    objToCopy = copy.deepcopy(objToCopy) #FIXME
                    delAASParents(objToCopy)  # TODO check if there is a better solution to del aas parents
                    return objToCopy
                elif index.column() in (TYPE_COLUMN, TYPE_HINT_COLUMN):
                    return index.data(Qt.DisplayRole)
                else:
                    objToCopy = index.data(Qt.EditRole)
                    objToCopy = copy.deepcopy(objToCopy)
                    delAASParents(objToCopy)  # TODO check if there is a better solution to del aas parents
                    return objToCopy
            except Exception as e:
                tb = traceback.format_exc()
                self.lastErrorMsg = f"Error occurred copying {index.data(NAME_ROLE)}: {e}\n\n{tb}"
                logging.exception(self.lastErrorMsg)
                self.dataChanged.emit(index, index, [DATA_CHANGE_FAILED_ROLE])
        else:
            item = self.objByIndex(index)
            column = index.column()
            return item.data(role, column, column_name=self._columns[column])

    def _getFgColor(self, index: QModelIndex):
        column = index.column()
        # color fg in red if obj type and typehint don't fit
        if column in (VALUE_COLUMN, TYPE_COLUMN) and not index.data(TYPE_CHECK_ROLE):
            return RED
        elif index.data(IS_LINK_ROLE):
            return LINK_BLUE
        elif column == ATTRIBUTE_COLUMN:
            if self.objByIndex(index).new:
                return NEW_GREEN
            elif self.objByIndex(index).changed:
                return CHANGED_BLUE
        return QVariant()

    def _getFont(self, index: QModelIndex):
        font = QFont(self.currFont)
        if index.data(IS_LINK_ROLE):
            font.setUnderline(True)
        elif index.column() == ATTRIBUTE_COLUMN:
            font.setBold(True)
            font.setUnderline(True)
        elif index.column() not in (TYPE_COLUMN, TYPE_HINT_COLUMN):
            font.setItalic(True)
        return font

    def getLinkedItem(self, index: QModelIndex) -> QModelIndex:
        if not index.data(IS_LINK_ROLE):
            return QModelIndex()
        try:
            reference = self.data(index, OBJECT_ROLE)
            objStore = self.data(index, PACKAGE_ROLE).objStore
            obj = reference.resolve(objStore)
            linkedPackItem, = self.data(index, PACK_ITEM_ROLE).model().match(QModelIndex(), OBJECT_ROLE, obj, hits=1)
            return linkedPackItem
        except AttributeError:
            return QModelIndex()

    def setData(self, index: QModelIndex, value: Any, role: int = ...) -> bool:
        if isinstance(index, QPersistentModelIndex):
            index = QModelIndex(index)
        if not index.isValid() and role not in (Qt.FontRole, ADD_ITEM_ROLE, UNDO_ROLE, REDO_ROLE):
            return QVariant()
        elif role == Qt.FontRole:
            if isinstance(value, QFont):
                font = QFont(value)
                self.currFont.setPointSize(font.pointSize())
                self.dataChanged.emit(self.index(0), self.index(self.rowCount()))
                return True
        elif role == ADD_ITEM_ROLE:
            try:
                self.addItem(value, index)
                return True
            except Exception as e:
                tb = traceback.format_exc()
                self.lastErrorMsg = f"Error occurred while adding item to {index.data(NAME_ROLE)}: {e}\n\n{tb}"
                logging.exception(self.lastErrorMsg)
                self.dataChanged.emit(index, index, [DATA_CHANGE_FAILED_ROLE])
        elif role == CLEAR_ROW_ROLE:
            try:
                parent = index.parent()
                self.clearRow(index.row(), parent, value)
                self.dataChanged.emit(parent, parent)
                return True
            except Exception as e:
                tb = traceback.format_exc()
                self.lastErrorMsg = f"{index.data(NAME_ROLE)} could not be deleted or set to default: {e}\n\n{tb}"
                self.dataChanged.emit(index, index, [DATA_CHANGE_FAILED_ROLE])
        elif role == Qt.EditRole:
            try:
                newValue, oldValue = self.editItem(index, value)
                self.setChanged(index)
                self.update(index)
                self.undo.append(SetDataItem(index=QPersistentModelIndex(index), value=oldValue, role=role))
                self.redo.clear()
                return True
            except Exception as e:
                tb = traceback.format_exc()
                self.lastErrorMsg = f"Error occurred while setting {getattr(self.objByIndex(index), 'objectName', 'UNKNOWN_OBJECT')}: {e}\n\n{tb}"
                self.dataChanged.emit(index, index, [DATA_CHANGE_FAILED_ROLE])
        elif role == UNDO_ROLE:
            if value == NOT_GIVEN and self.undo:
                lastUndo: SetDataItem = self.undo.pop()
                tempRedoList = self.redo
                self.redo = []
                if self.setData(*lastUndo):
                    self.redo = tempRedoList
                    self.redo.append(self.undo.pop())
                    return True
            elif isIterable(value):
                self.undo = deque(value)
                return True
        elif role == REDO_ROLE:
            if value == NOT_GIVEN and self.redo:
                lastRedo: SetDataItem = self.redo.pop()
                tempRedoList = self.redo
                self.redo = []
                if self.setData(*lastRedo):
                    self.redo = tempRedoList
                    return True
            elif isIterable(value):
                self.redo = list(value)
                return True
        elif role == UPDATE_ROLE:
            self.update(index)
        else:
            raise ValueError(f"Unknown role: {role}")
        return False

    def editItem(self, index: QModelIndex, value):
        newValue = None if str(value) == "None" else value
        item = self.objByIndex(index)

        parentObj = item.parentObj
        if ClassesInfo.changedParentObject(type(parentObj)) and index.parent().isValid():
            parentObj = getattr(parentObj, ClassesInfo.changedParentObject(type(parentObj)))

        if isinstance(parentObj, list):
            oldValue = item.obj
            objIndex = parentObj.index(item.obj)
            parentObj[objIndex] = newValue
            item.obj = newValue
        elif isinstance(parentObj, AbstractSet):
            oldValue = item.obj
            parentObj.remove(item.obj)
            parentObj.add(newValue)
            item.obj = newValue
        elif isinstance(item.obj, DictItem):
            oldValue: DictItem = item.obj
            item.obj = newValue
            if newValue.key != oldValue.key:
                parentObj.pop(oldValue.key)
            parentObj.update([item.obj])
        else:
            oldValue = getattr(parentObj, item.objName)
            try:
                setattr(parentObj, item.objName, newValue)
            except TypeError as e:
                # FIXME: Warning:pyi40aas specific code part for setting Property.value
                try:
                    valueTypeItem = self.match(QModelIndex(), Qt.DisplayRole, "value_type", 1)[0]
                    self.setData(valueTypeItem, type(newValue), Qt.EditRole)
                except IndexError:
                    raise e
                setattr(parentObj, item.objName, newValue)
            item.obj = getattr(parentObj, item.objName)
        return newValue, oldValue

    def setChanged(self, topLeft: QModelIndex, bottomRight: QModelIndex = None):
        """Set the item and all parents as changed"""
        self._setChanged(True, topLeft, bottomRight)

    def setUnchanged(self, topLeft: QModelIndex, bottomRight: QModelIndex = None):
        self._setChanged(False, topLeft, bottomRight)

    def _setChanged(self, changed: bool, topLeft: QModelIndex, bottomRight: QModelIndex):
        bottomRight = topLeft if bottomRight is None else bottomRight
        if topLeft.isValid() and bottomRight.isValid():
            selection = QItemSelection(topLeft, bottomRight)
            for index in selection.indexes():
                self.objByIndex(index).changed = changed
                if changed:
                    self.changedItems.append(index)
                else:
                    self.changedItems.append(index)

                if index.parent().isValid():
                    self.setChanged(index.parent())
                else:
                    packItem: QModelIndex = index.data(PACK_ITEM_ROLE)
                    if packItem and packItem.isValid():
                        packItem.model().dataChanged.emit(packItem, packItem)

    def removeRows(self, row: int, count: int, parent: QModelIndex = ...) -> bool:
        parentItem = self.objByIndex(parent)

        self.beginRemoveRows(parent, row, row+count-1)
        for n in range(count):
            child = parentItem.children()[row]
            child.setParent(None)
            # child.deleteLater()
        self.endRemoveRows()
        return True

    def clearRows(self, row: int, count: int,
                  parent: QModelIndex = ..., defaultVal=NOT_GIVEN) -> bool:
        """Delete rows if they are children of Iterable else set to Default"""
        parentItem = self.objByIndex(parent)
        parentObj = parentItem.data(OBJECT_ROLE)

        # if parentObj is Submodel and the parentObj is not rootItem
        # set submodel_element as parentObj
        if parent.isValid():
            try:
                parentAttr = ClassesInfo.changedParentObject(type(parentObj))
                parentObj = getattr(parentObj, parentAttr)
            except AttributeError:
                pass

        for currRow in range(row+count-1, row-1, -1):
            child = parentItem.children()[currRow]
            if isinstance(parentObj, (list, dict, AbstractSet)):
                if isinstance(parentObj, list):
                    oldValue = parentObj.pop(currRow)
                elif isinstance(parentObj, dict):
                    oldValue: DictItem = child.data(OBJECT_ROLE)
                    parentObj.pop(oldValue.key)
                elif isinstance(parentObj, AbstractSet):
                    parentObj.discard(child.obj)
                    oldValue = child.obj
                self.removeRow(currRow, parent)
                self.undo.append(SetDataItem(index=QPersistentModelIndex(parent), value=oldValue, role=ADD_ITEM_ROLE))
                self.redo.clear()
            else:
                if not defaultVal == NOT_GIVEN:
                    index = self.index(currRow, 0, parent)
                    self.setData(index, defaultVal, Qt.EditRole)
                elif isinstance(child.obj, Package):
                    # close package
                    oldValue = child.obj
                    self.removeRow(currRow, parent)
                    self.undo.append(
                        SetDataItem(index=QPersistentModelIndex(parent), value=oldValue,
                                    role=ADD_ITEM_ROLE))
                    self.redo.clear()
                else:
                    raise TypeError(
                        f"Unknown parent object type: "
                        f"object could not be deleted or set to default: "
                        f"{type(parentObj)}")
        return True

    def clearRow(self, row: int, parent: QModelIndex = ..., defaultVal=NOT_GIVEN) -> bool:
        """Delete row if it is child of Iterable else set to Default"""
        return self.clearRows(row, 1, parent, defaultVal)
