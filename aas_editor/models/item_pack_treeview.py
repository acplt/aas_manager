#  Copyright (C) 2021  Igor Garmaev, garmaev@gmx.net
#
#  This program is made available under the terms of the GNU General Public License as published by
#  the Free Software Foundation, either version 3 of the License, or (at your option) any later version.
#
#  This program is distributed in the hope that it will be useful, but WITHOUT ANY WARRANTY;
#  without even the implied warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.
#
#  A copy of the GNU General Public License is available at http://www.gnu.org/licenses/
#
#  This program is made available under the terms of the GNU General Public License as published by
#  the Free Software Foundation, either version 3 of the License, or (at your option) any later version.
#
#  This program is distributed in the hope that it will be useful, but WITHOUT ANY WARRANTY;
#  without even the implied warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.
#
#  A copy of the GNU General Public License is available at http://www.gnu.org/licenses/
import logging
from types import GeneratorType

from PyQt5.QtCore import Qt
from basyx.aas.adapter.aasx import DictSupplementaryFileContainer

from aas_editor.models import StandardItem
from aas_editor.settings.app_settings import PACKAGE_ROLE, ATTRIBUTE_COLUMN
from aas_editor.utils.util import getDescription
from aas_editor.utils.util_classes import ClassesInfo
from aas_editor.utils.util_type import isIterable
from aas_editor.package import LocalPackage, StoredFile


class PackTreeViewItem(StandardItem):
    def __init__(self, obj, parent, **kwargs):
        super().__init__(obj, parent=parent, **kwargs)
        if isinstance(obj, LocalPackage):
            self.typehint = LocalPackage
            self.package = obj
        else:
            self.package = parent.data(PACKAGE_ROLE)
        self.populate()

    def populate(self):
        kwargs = {
            "parent": self,
            "new": self.new,
        }
        if ClassesInfo.hasPackViewAttrs(type(self.obj)):
            for attr in ClassesInfo.packViewAttrs(type(self.obj)):
                # set package objStore as obj, so that delete works
                itemObj = getattr(self.obj, attr)
                packItem = PackTreeViewItem(itemObj, name=attr, **kwargs)
                if isinstance(itemObj, GeneratorType):
                    packItem.obj = self.obj.objStore
        elif isIterable(self.obj):
            if isinstance(self.obj, DictSupplementaryFileContainer):
                self._populateFileContainer(self.obj, **kwargs)
            else:
                self._populateIterable(self.obj, **kwargs)

    @staticmethod
    def _populateIterable(obj, **kwargs):
        for sub_item_obj in obj:
            PackTreeViewItem(sub_item_obj, **kwargs)

    @staticmethod
    def _populateFileContainer(fileContainer, **kwargs):
        # populate file container
        for name in fileContainer:
            itemObj = StoredFile(name, fileContainer)
            PackTreeViewItem(itemObj, **kwargs)

    def _getEditRoleData(self, column, column_name):
        if column == ATTRIBUTE_COLUMN:
            return self.obj
        return super(PackTreeViewItem, self)._getEditRoleData(column, column_name)
