import os
import copy
from collections import OrderedDict
import codecs
import time

from .imports import *
from corpustools.exceptions import PCTError, PCTPythonError

from corpustools.corpus.io import (load_binary, download_binary,
                    load_feature_matrix_csv, save_binary, DelimiterError,
                    export_feature_matrix_csv)

from .views import SubTreeView
from .models import FeatureSystemTableModel, FeatureSystemTreeModel

from .widgets import (FileWidget, RadioSelectWidget,SaveFileWidget,
                    TableWidget, CreateClassWidget, FeatureEdit, FeatureCompleter)

from .windows import FunctionWorker, DownloadWorker, PCTDialog
from .helpgui import HelpDialog

class LoadFeatureSystemWorker(FunctionWorker):
    def run(self):
        time.sleep(0.1)
        try:
            system = load_feature_matrix_csv(**self.kwargs)
        except PCTError as e:
            self.errorEncountered.emit(e)
            return
        except Exception as e:
            e = PCTPythonError(e)
            self.errorEncountered.emit(e)
            return
        if self.stopped:
            time.sleep(0.1)
            self.finishedCancelling.emit()
            return
        self.dataReady.emit(system)


def get_systems_list(storage_directory):
    system_dir = os.path.join(storage_directory,'FEATURE')
    systems = [x.split('.')[0] for x in os.listdir(system_dir)]
    return systems

def get_feature_system_styles(storage_directory):
    systems = list()
    for s in get_systems_list(storage_directory):
        deets = s.split('2')
        if len(deets) == 1:
            continue
        systems.append(deets[1])
    return list(set(systems))

def get_transcription_system_styles(storage_directory):
    systems = list()
    for s in get_systems_list(storage_directory):
        deets = s.split('2')
        if len(deets) == 1:
            continue
        systems.append(deets[0])
    return list(set(systems))

def system_name_to_path(storage_directory,name):
    return os.path.join(storage_directory,'FEATURE',name+'.feature')

class FeatureSystemSelect(QGroupBox):
    changed  = Signal()
    def __init__(self,settings,parent=None,default = None, add = False):
        QGroupBox.__init__(self,'Transcription and _features',parent)
        self.settings = settings
        layout = QFormLayout()

        self.transSystem = QComboBox()
        if add:
            self.transSystem.addItem('Custom')
        else:
            self.transSystem.addItem('None')
        if default is not None:
            default_deets = default.split('2')
            if len(default_deets) == 1:
                default_trans = 'None'
                default_feat = 'None'
            else:
                default_trans,default_feat = default_deets

        for i,s in enumerate(get_transcription_system_styles(self.settings['storage'])):
            self.transSystem.addItem(s)
            if default is not None and s == default_trans:
                self.transSystem.setCurrentIndex(i+1)
        self.transSystem.currentIndexChanged.connect(self.toggleTransName)
        layout.addRow(QLabel('Transcription system'),self.transSystem)

        self.transName = QLineEdit()
        if add:
            layout.addRow(QLabel('Transcription system name (if custom)'),self.transName)

        self.featureSystem = QComboBox()
        if add:
            self.featureSystem.addItem('Custom')
        else:
            self.featureSystem.addItem('None')
        for i,s in enumerate(get_feature_system_styles(self.settings['storage'])):
            self.featureSystem.addItem(s)
            if default is not None and s == default_feat:
                self.featureSystem.setCurrentIndex(i+1)
        self.featureSystem.currentIndexChanged.connect(self.toggleFeatName)
        layout.addRow(QLabel('Feature system'),self.featureSystem)

        self.featName = QLineEdit()
        if add:
            layout.addRow(QLabel('Feature system name (if custom)'),self.featName)

        self.setLayout(layout)

    def toggleTransName(self, ind = None):
        if self.transSystem.currentText() == 'Custom':
            self.transName.setDisabled(False)
        else:
            self.transName.setDisabled(True)
        self.changed.emit()

    def toggleFeatName(self, ind = None):
        if self.featureSystem.currentText() == 'Custom':
            self.featName.setDisabled(False)
        else:
            self.featName.setDisabled(True)
        self.changed.emit()

    def value(self):
        trans = self.transSystem.currentText()
        feat = self.featureSystem.currentText()
        if trans == 'None':
            return ''
        if feat == 'None':
            return ''
        if trans == 'Custom':
            trans = self.transName.text()
            if trans == '':
                return ''
        if feat == 'Custom':
            feat = self.featName.text()
            if feat == '':
                return ''
        return '2'.join([trans,feat])

    def path(self):
        if self.value() != '':
            return system_name_to_path(self.settings['storage'], self.value())
        return None

class ExportFeatureSystemDialog(QDialog):
    def __init__(self, parent, corpus):
        QDialog.__init__(self, parent)

        self.specifier = corpus.specifier
        layout = QVBoxLayout()

        inlayout = QFormLayout()

        self.pathWidget = SaveFileWidget('Select file location','Text files (*.txt *.csv)')

        inlayout.addRow('File name:',self.pathWidget)

        self.columnDelimiterEdit = QLineEdit()
        self.columnDelimiterEdit.setText(',')

        inlayout.addRow('Column delimiter:',self.columnDelimiterEdit)

        inframe = QFrame()
        inframe.setLayout(inlayout)

        layout.addWidget(inframe)

        self.acceptButton = QPushButton('Ok')
        self.cancelButton = QPushButton('Cancel')
        acLayout = QHBoxLayout()
        acLayout.addWidget(self.acceptButton)
        acLayout.addWidget(self.cancelButton)
        self.acceptButton.clicked.connect(self.accept)
        self.cancelButton.clicked.connect(self.reject)

        acFrame = QFrame()
        acFrame.setLayout(acLayout)

        layout.addWidget(acFrame)

        self.setLayout(layout)

        self.setWindowTitle('Export feature system')

    def accept(self):
        filename = self.pathWidget.value()

        if filename == '':
            reply = QMessageBox.critical(self,
                    "Missing information", "Please specify a path to save the corpus.")
            return

        colDelim = codecs.getdecoder("unicode_escape")(self.columnDelimiterEdit.text())[0]
        if len(colDelim) != 1:
            reply = QMessageBox.critical(self,
                    "Invalid information", "The column delimiter must be a single character.")
            return

        export_feature_matrix_csv(self.specifier,filename,colDelim)

        QDialog.accept(self)

class AddFeatureDialog(QDialog):
    def __init__(self, parent, specifier):
        QDialog.__init__(self, parent)
        self.specifier = specifier
        layout = QVBoxLayout()

        featureLayout = QFormLayout()
        self.featureEdit = QLineEdit()
        featureLayout.addRow('Feature name',self.featureEdit)
        self.defaultSelect = QComboBox()
        self.defaultSelect.addItem(specifier.default_value)
        for i,v in enumerate(specifier.possible_values):
            if v == specifier.default_value:
                continue
            self.defaultSelect.addItem(v)
        featureLayout.addRow('Default value for this feature:',self.defaultSelect)

        featureFrame = QFrame()
        featureFrame.setLayout(featureLayout)

        layout.addWidget(featureFrame)

        self.acceptButton = QPushButton('Ok')
        self.cancelButton = QPushButton('Cancel')
        acLayout = QHBoxLayout()
        acLayout.addWidget(self.acceptButton)
        acLayout.addWidget(self.cancelButton)
        self.acceptButton.clicked.connect(self.accept)
        self.cancelButton.clicked.connect(self.reject)

        acFrame = QFrame()
        acFrame.setLayout(acLayout)

        layout.addWidget(acFrame)

        self.setLayout(layout)

        self.setWindowTitle('Add feature')

    def accept(self):
        self.featureName = self.featureEdit.text()
        self.defaultValue = self.defaultSelect.currentText()
        if self.featureName == '':
            reply = QMessageBox.critical(self,
                    "Missing information", "Please specify a feature name.")
            return
        if self.featureName in self.specifier.features:
            reply = QMessageBox.critical(self,
                    "Duplicate information", "The feature '{}' is already in the feature system.".format(self.featureName))
            return
        QDialog.accept(self)

class DownloadFeatureMatrixDialog(QDialog):
    def __init__(self, parent, settings):
        QDialog.__init__(self, parent)

        self.settings = settings
        layout = QVBoxLayout()
        inlayout = QHBoxLayout()

        self.transWidget = RadioSelectWidget('Select a transcription system',
                                            OrderedDict([('IPA','ipa'),
                                                        ('ARPABET (CMU)','arpabet'),
                                                        ('XSAMPA','sampa'),
                                                        ('CPA','cpa'),
                                                        ('CELEX','celex'),
                                                        ('DISC','disc'),
                                                        ('Klatt','klatt'),
                                                        ('Buckeye','buckeye')]))

        self.featureWidget = RadioSelectWidget('Select a feature system',
                                        OrderedDict([('Sound Pattern of English (SPE)','spe'),
                                        ('Hayes','hayes')]))

        inlayout.addWidget(self.transWidget)
        inlayout.addWidget(self.featureWidget)

        inframe = QFrame()
        inframe.setLayout(inlayout)

        layout.addWidget(inframe)

        self.acceptButton = QPushButton('Ok')
        self.cancelButton = QPushButton('Cancel')
        self.helpButton = QPushButton('Help')
        acLayout = QHBoxLayout()
        acLayout.addWidget(self.acceptButton)
        acLayout.addWidget(self.cancelButton)
        acLayout.addWidget(self.helpButton)
        self.acceptButton.clicked.connect(self.accept)
        self.cancelButton.clicked.connect(self.reject)
        self.helpButton.clicked.connect(self.help)

        acFrame = QFrame()
        acFrame.setLayout(acLayout)

        layout.addWidget(acFrame)

        self.setLayout(layout)

        self.setWindowTitle('Download feature system')

        self.thread = DownloadWorker()

        self.progressDialog = QProgressDialog('Downloading...','Cancel',0,100,self)
        self.progressDialog.setWindowTitle('Download feature system')
        self.progressDialog.setAutoClose(False)
        self.progressDialog.setAutoReset(False)
        self.progressDialog.canceled.connect(self.thread.stop)
        self.thread.updateProgress.connect(self.updateProgress)
        self.thread.updateProgressText.connect(self.updateProgressText)
        self.thread.finished.connect(self.progressDialog.accept)

    def help(self):
        self.helpDialog = HelpDialog(self,name = 'transcriptions and feature systems',
                                    section = 'downloadable-transcription-and-feature-choices')
        self.helpDialog.exec_()

    def updateProgressText(self, text):
        self.progressDialog.setLabelText(text)
        self.progressDialog.reset()

    def updateProgress(self,progress):
        self.progressDialog.setValue(progress)
        self.progressDialog.repaint()

    def accept(self):
        name = self.transWidget.value() + '2' + self.featureWidget.value()
        if name in get_systems_list(self.settings['storage']):
            msgBox = QMessageBox(QMessageBox.Warning, "Overwrite system",
                    "The system '{}' is already available.  Would you like to overwrite it?".format(name), QMessageBox.NoButton, self)
            msgBox.addButton("Overwrite", QMessageBox.AcceptRole)
            msgBox.addButton("Cancel", QMessageBox.RejectRole)
            if msgBox.exec_() != QMessageBox.AcceptRole:
                return

        self.thread.setParams({'name':name,
                'path':system_name_to_path(self.settings['storage'],name)})

        self.thread.start()

        result = self.progressDialog.exec_()

        self.progressDialog.reset()
        if result:
            QDialog.accept(self)

class EditFeatureMatrixDialog(QDialog):
    def __init__(self, parent, corpus, settings):
        QDialog.__init__(self, parent)
        self.corpus = corpus
        self.settings = settings

        self.specifier = self.corpus.specifier

        layout = QVBoxLayout()

        self.table = TableWidget()
        #self.table.setModel(FeatureSystemTableModel(self.specifier))
        #layout.addWidget(self.table)

        optionLayout = QHBoxLayout()

        changeFrame = QGroupBox('Change feature systems')
        box = QFormLayout()
        default = None
        if self.specifier is not None:
            default = self.specifier.name
        self.changeWidget = FeatureSystemSelect(self.settings,default=default)
        self.changeWidget.changed.connect(self.changeFeatureSystem)
        box.addRow(self.changeWidget)

        changeFrame.setLayout(box)

        optionLayout.addWidget(changeFrame)

        modifyFrame = QGroupBox('Modify the feature system')

        box = QFormLayout()

        self.addSegmentButton = QPushButton('Add segment')
        self.editSegmentButton = QPushButton('Edit segment')
        self.addFeatureButton = QPushButton('Add feature')
        self.addSegmentButton.clicked.connect(self.addSegment)
        self.editSegmentButton.clicked.connect(self.editSegment)
        self.addFeatureButton.clicked.connect(self.addFeature)

        box.addRow(self.addSegmentButton)
        box.addRow(self.editSegmentButton)
        box.addRow(self.addFeatureButton)

        modifyFrame.setLayout(box)

        optionLayout.addWidget(modifyFrame)

        coverageFrame = QGroupBox('Corpus inventory coverage')
        box = QFormLayout()

        self.hideButton = QPushButton('Hide all segments not used by the corpus')
        self.showAllButton = QPushButton('Show all segments')
        self.coverageButton = QPushButton('Check corpus inventory coverage')
        self.hideButton.clicked.connect(self.hide)
        self.showAllButton.clicked.connect(self.showAll)
        self.coverageButton.clicked.connect(self.checkCoverage)

        box.addRow(self.hideButton)
        box.addRow(self.showAllButton)
        box.addRow(self.coverageButton)

        coverageFrame.setLayout(box)

        optionLayout.addWidget(coverageFrame)

        viewFrame = QGroupBox('Display options')
        box = QFormLayout()

        self.displayWidget = QComboBox()
        self.displayWidget.addItem('Matrix')
        self.displayWidget.addItem('Tree')
        self.displayWidget.currentIndexChanged.connect(self.changeDisplay)

        box.addRow('Display mode:',self.displayWidget)

        self.editCategoriesButton = QPushButton('Edit inventory categories')
        self.editCategoriesButton.clicked.connect(self.editCategories)

        box.addRow(self.editCategoriesButton)

        viewFrame.setLayout(box)

        optionLayout.addWidget(viewFrame)

        optionFrame = QFrame()

        optionFrame.setLayout(optionLayout)

        layout.addWidget(optionFrame)

        self.acceptButton = QPushButton('Save changes to this corpus\'s feature system')
        self.cancelButton = QPushButton('Cancel')
        self.helpButton = QPushButton('Help')
        acLayout = QHBoxLayout()
        acLayout.addWidget(self.acceptButton)
        acLayout.addWidget(self.cancelButton)
        acLayout.addWidget(self.helpButton)
        self.acceptButton.clicked.connect(self.accept)
        self.cancelButton.clicked.connect(self.reject)
        self.helpButton.clicked.connect(self.help)

        acFrame = QFrame()
        acFrame.setLayout(acLayout)

        layout.addWidget(acFrame)

        self.setLayout(layout)

        self.setWindowTitle('Edit feature system')

        self.changeDisplay()

    def accept(self):
        if self.specifier is not None:
            path = system_name_to_path(self.settings['storage'],self.specifier.name)
            save_binary(self.specifier, path)
        QDialog.accept(self)

    def help(self):
        self.helpDialog = HelpDialog(self,name = 'transcriptions and feature systems',
                                    section = 'applying-editing-feature-systems')
        self.helpDialog.exec_()

    def editCategories(self):
        if self.specifier is None:
            return
        dialog = EditCategoriesDialog(self, self.specifier)
        if dialog.exec_():
            self.specifier.vowel_feature = dialog.vowel()[0] if dialog.vowel() else None
            self.specifier.voice_feature = dialog.voiced()[0] if dialog.voiced() else None
            self.specifier.diph_feature = dialog.diphthong()[0] if dialog.diphthong() else None
            self.specifier.rounded_feature = dialog.rounded()[0] if dialog.rounded() else None
            p, m, h, b = dialog.value()
            for k,v in p.items():
                self.specifier.places[k] = v
            for k,v in m.items():
                self.specifier.manners[k] = v
            for k,v in h.items():
                self.specifier.height[k] = v
            for k,v in b.items():
                self.specifier.backness[k] = v


    def changeDisplay(self):
        if self.specifier is None:
            return
        mode = self.displayWidget.currentText()
        self.table.deleteLater()
        if mode == 'Tree':
            self.table = SubTreeView()
            self.table.setModel(FeatureSystemTreeModel(self.specifier))
            self.layout().insertWidget(0,self.table)
        elif mode == 'Matrix':
            self.table = TableWidget()
            self.table.setModel(FeatureSystemTableModel(self.specifier))
            self.table.resizeColumnsToContents()
            self.layout().insertWidget(0,self.table)

    def changeFeatureSystem(self):
        path = self.changeWidget.path()
        if path is None:
            self.specifier = None
        else:
            try:
                self.specifier = load_binary(path)
            except OSError:
                return
        self.changeDisplay()

    def addSegment(self):
        if self.specifier is None:
            return
        dialog = EditSegmentDialog(self,self.table.model().specifier)
        if dialog.exec_():
            self.table.model().addSegment(dialog.seg,dialog.featspec)

    def editSegment(self):
        if self.specifier is None:
            return
        if self.displayWidget.currentText() == 'Tree':
            index = self.table.selectionModel().currentIndex()
            seg = self.table.model().data(index,Qt.DisplayRole)
            if seg is None:
                return
            if seg not in self.specifier:
                return
        else:
            selected = self.table.selectionModel().selectedRows()
            if not selected:
                return
            selected = selected[0]
            seg = self.table.model().data(self.table.model().createIndex(selected.row(),0),Qt.DisplayRole)

        dialog = EditSegmentDialog(self,self.table.model().specifier,seg)
        if dialog.exec_():
            self.table.model().addSegment(dialog.seg,dialog.featspec)

    def addFeature(self):
        if self.specifier is None:
            return
        dialog = AddFeatureDialog(self,self.table.model().specifier)
        if dialog.exec_():
            self.table.model().addFeature(dialog.featureName, dialog.defaultValue)

    def hide(self):
        if self.specifier is None:
            return
        self.table.model().filter(self.corpus.inventory)

    def showAll(self):
        if self.specifier is None:
            return
        self.table.model().showAll()

    def checkCoverage(self):
        if self.specifier is None:
            return
        corpus_inventory = self.corpus.inventory
        try:
            feature_inventory = self.specifier.segments
        except AttributeError:
            reply = QMessageBox.warning(self,
                    "Missing feature system", "No feature system has been specified.")
        missing = []
        for seg in corpus_inventory:
            if seg not in feature_inventory:
                missing.append(str(seg))
        if missing:
            reply = QMessageBox.warning(self,
                    "Missing segments", ('The following segments are not specified'
                                        ' for _features: '+', '.join(missing) + '\nIf you'
                                        ' are shown a \'blank\' segment, please ensure'
                                        ' that your segment delimiters are placed'
                                        ' correctly and are never adjacent to each other.'))
            return
        reply = QMessageBox.information(self,
                    "Missing segments", 'All segments are specified for _features!')

class CategoryWidget(QWidget):
    def __init__(self, category, features, specifier, parent = None):
        QWidget.__init__(self, parent)

        self.specifier = specifier
        self.category = category
        layout = QHBoxLayout()

        self.searchWidget = FeatureEdit(self.specifier, clearOnEnter = False)
        self.completer = FeatureCompleter(self.specifier)
        self.searchWidget.setCompleter(self.completer)
        if isinstance(features, dict):
            self.searchWidget.setText(', '.join(v+k for k,v in features.items()))
        elif isinstance(features, list):
            self.searchWidget.setText(', '.join(features))
        elif isinstance(features, str):
            self.searchWidget.setText(features)

        layout.addWidget(self.searchWidget)

        self.previewWidget = QLabel('Mouseover for included segments')
        self.previewWidget.setFrameShape(QFrame.Box)

        self.updateSegments()
        self.searchWidget.featureEntered.connect(self.updateSegments)

        layout.addWidget(self.previewWidget)
        self.setLayout(layout)

    def updateSegments(self, features = None):
        if features is None:
            features = self.searchWidget.features()
        if len(features) == 0:
            self.previewWidget.setToolTip('No included segments')
        else:
            segments = self.specifier.features_to_segments(features)
            self.previewWidget.setToolTip(', '.join(segments))

    def features(self):
        return self.searchWidget.features()

    def value(self):
        return self.category, self.searchWidget.features()

class EditCategoriesDialog(QDialog):
    def __init__(self, parent, specifier):
        QDialog.__init__(self, parent)
        self.specifier = specifier

        layout = QVBoxLayout()
        self.tabWidget = QTabWidget()

        midlayout = QHBoxLayout()

        catlayout = QFormLayout()

        self.vowelWidget = CategoryWidget('Vowel', self.specifier.vowel_feature, specifier)
        catlayout.addRow('Feature specifying vowels',self.vowelWidget)

        self.voiceWidget = CategoryWidget('Voiced', self.specifier.voice_feature, specifier)
        catlayout.addRow('Feature specifying voiced obstruents',self.voiceWidget)

        self.diphWidget = CategoryWidget('Diphthong', self.specifier.diph_feature, specifier)
        catlayout.addRow('Feature specifying diphthongs',self.diphWidget)

        self.roundedWidget = CategoryWidget('Rounded', self.specifier.rounded_feature, specifier)
        catlayout.addRow('Feature specifying rounded vowels',self.roundedWidget)

        catFrame = QWidget()
        catFrame.setLayout(catlayout)
        self.tabWidget.addTab(catFrame,'Major distinctions')


        placesFrame = QWidget()
        placeslayout = QFormLayout()

        self.places = []
        self.manners = []
        self.height = []
        self.backness = []

        for k,v in self.specifier.places.items():
            w = CategoryWidget(k, v, specifier)
            placeslayout.addRow(k, w)
            self.places.append(w)

        placesFrame.setLayout(placeslayout)
        self.tabWidget.addTab(placesFrame,'Places of articulation')

        mannersFrame = QWidget()
        mannerslayout = QFormLayout()
        for k,v in self.specifier.manners.items():
            w = CategoryWidget(k, v, specifier)
            mannerslayout.addRow(k, w)
            self.manners.append(w)

        mannersFrame.setLayout(mannerslayout)
        self.tabWidget.addTab(mannersFrame,'Manners of articulation')

        heightFrame = QWidget()
        heightlayout = QFormLayout()
        for k,v in self.specifier.height.items():
            w = CategoryWidget(k, v, specifier)
            heightlayout.addRow(k, w)
            self.height.append(w)

        heightFrame.setLayout(heightlayout)
        self.tabWidget.addTab(heightFrame,'Vowel height')

        backnessFrame = QWidget()
        backnesslayout = QFormLayout()
        for k,v in self.specifier.backness.items():
            w = CategoryWidget(k, v, specifier)
            backnesslayout.addRow(k, w)
            self.backness.append(w)

        backnessFrame.setLayout(backnesslayout)
        self.tabWidget.addTab(backnessFrame,'Vowel backness')

        midlayout.addWidget(self.tabWidget)

        layout.addLayout(midlayout)

        self.acceptButton = QPushButton('Ok')
        self.cancelButton = QPushButton('Cancel')
        acLayout = QHBoxLayout()
        acLayout.addWidget(self.acceptButton)
        acLayout.addWidget(self.cancelButton)
        self.acceptButton.clicked.connect(self.accept)
        self.cancelButton.clicked.connect(self.reject)

        acFrame = QFrame()
        acFrame.setLayout(acLayout)

        layout.addWidget(acFrame)
        self.setWindowTitle('Edit categories')
        self.setLayout(layout)

    def vowel(self):
        return self.vowelWidget.features()

    def voiced(self):
        return self.voiceWidget.features()

    def rounded(self):
        return self.roundedWidget.features()

    def diphthong(self):
        return self.diphWidget.features()

    def value(self):
        p = {w.category: w.features() for w in self.places}
        m = {w.category: w.features() for w in self.manners}
        h = {w.category: w.features() for w in self.height}
        b = {w.category: w.features() for w in self.backness}
        return p, m, h, b


class EditSegmentDialog(QDialog):
    def __init__(self, parent, specifier, segment = None):
        QDialog.__init__(self, parent)

        self.specifier = specifier
        layout = QVBoxLayout()
        layout.setAlignment(Qt.AlignTop | Qt.AlignLeft)

        featLayout = QGridLayout()
        self.symbolEdit = QLineEdit()
        self.add = True
        if segment is not None:
            self.add = False
            self.symbolEdit.setText(segment)
        box = QFrame()
        lay = QFormLayout()
        lay.setAlignment(Qt.AlignTop | Qt.AlignLeft)
        lay.addRow('Symbol',self.symbolEdit)
        self.setAllSelect = QComboBox()
        self.setAllSelect.addItem(specifier.default_value)
        for i,v in enumerate(specifier.possible_values):
            if v == specifier.default_value:
                continue
            self.setAllSelect.addItem(v)
        self.setAllSelect.currentIndexChanged.connect(self.setAll)
        lay.addRow('Set all feature values to:',self.setAllSelect)
        box.setLayout(lay)
        layout.addWidget(box, alignment = Qt.AlignLeft)
        row = 0
        col = 0
        self.featureSelects = dict()
        for f in specifier.features:
            box = QGroupBox(f)
            box.setFlat(True)
            lay = QVBoxLayout()

            featSel = QComboBox()
            featSel.addItem(specifier.default_value)
            for i,v in enumerate(specifier.possible_values):
                if v == specifier.default_value:
                    continue
                featSel.addItem(v)
            for i in range(featSel.count()):
                if segment is not None and featSel.itemText(i) == specifier[segment][f]:
                    featSel.setCurrentIndex(i)
            lay.addWidget(featSel)
            box.setLayout(lay)
            self.featureSelects[f] = featSel
            featLayout.addWidget(box,row,col)

            col += 1
            if col > 6:
                col = 0
                row += 1

        featBox = QFrame()
        featBox.setLayout(featLayout)
        layout.addWidget(featBox)

        self.acceptButton = QPushButton('Ok')
        self.acceptButton.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        self.cancelButton = QPushButton('Cancel')
        self.cancelButton.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        acLayout = QHBoxLayout()
        acLayout.addWidget(self.acceptButton, alignment = Qt.AlignCenter)
        acLayout.addWidget(self.cancelButton, alignment = Qt.AlignCenter)
        self.acceptButton.clicked.connect(self.accept)
        self.cancelButton.clicked.connect(self.reject)

        acFrame = QFrame()
        acFrame.setLayout(acLayout)

        layout.addWidget(acFrame, alignment = Qt.AlignCenter)

        self.setLayout(layout)
        if segment is not None:
            self.setWindowTitle('Edit segment')
        else:
            self.setWindowTitle('Add segment')

    def setAll(self):
        all_val = self.setAllSelect.currentIndex()
        for v in self.featureSelects.values():
            v.setCurrentIndex(all_val)

    def accept(self):
        self.seg = self.symbolEdit.text()
        if self.seg == '':
            reply = QMessageBox.critical(self,
                    "Missing information", "Please specify a segment symbol.")
            return
        if self.seg in self.specifier and self.add:
            msgBox = QMessageBox(QMessageBox.Warning, "Duplicate symbol",
                    "The symbol '{}' already exists.  Overwrite?".format(self.seg), QMessageBox.NoButton, self)
            msgBox.addButton("Overwrite", QMessageBox.AcceptRole)
            msgBox.addButton("Abort", QMessageBox.RejectRole)
            if msgBox.exec_() != QMessageBox.AcceptRole:
                return
        self.featspec = {f:v.currentText() for f,v in self.featureSelects.items()}
        QDialog.accept(self)

class FeatureClassManager(CreateClassWidget):
    def __init__(self, parent, settings, corpusModel):
        self.corpus = corpusModel.corpus
        super().__init__(parent, self.corpus, class_type='class')

    def accept(self):
        className = self.nameEdit.text()
        className = className.strip()
        className = className.replace(' ', '')
        if className == '':
            reply = QMessageBox.critical(self,
                                         "Missing information", "Please enter a name for the class.")
            return
        elif className in self.corpus.inventory.classes.keys():

            msgBox = QMessageBox(QMessageBox.Warning, "Duplicate class names",
                                 "'{}' is already the name of a class. Please select a new name".format(className))
                                 #QMessageBox.NoButton, self)
            msgBox.addButton("OK", QMessageBox.AcceptRole)
        createType = self.createType.currentText()
        createList = self.createWidget.value()
        if not createList:
            reply = QMessageBox.critical(self,
                                         "Missing information", "Please specify at least one {}.".format(createType[:-1].lower()))
            return
        if createType == 'Features':
            createList = createList[1:-1]
            self.segList = self.corpus.features_to_segments(createList)
        else:
            self.segList = createList
        QDialog.accept(self)


class FeatureMatrixManager(QDialog):
    def __init__(self, parent, settings):
        QDialog.__init__(self, parent)
        layout = QVBoxLayout()
        self.settings = settings
        formLayout = QHBoxLayout()
        listFrame = QGroupBox('Available feature systems')
        listLayout = QGridLayout()

        self.systemsList = QListWidget(self)
        listLayout.addWidget(self.systemsList)
        listFrame.setLayout(listLayout)
        self.getAvailableSystems()

        formLayout.addWidget(listFrame)

        buttonLayout = QVBoxLayout()
        self.downloadButton = QPushButton('Download feature systems')
        self.downloadButton.setAutoDefault(False)
        self.loadFromCsvButton = QPushButton('Create feature system from text file')
        self.loadFromCsvButton.setAutoDefault(False)
        self.removeButton = QPushButton('Remove selected feature system')
        self.removeButton.setAutoDefault(False)
        buttonLayout.addWidget(self.downloadButton)
        buttonLayout.addWidget(self.loadFromCsvButton)
        buttonLayout.addWidget(self.removeButton)

        self.downloadButton.clicked.connect(self.openDownloadWindow)
        self.loadFromCsvButton.clicked.connect(self.openCsvWindow)
        self.removeButton.clicked.connect(self.removeSystem)

        buttonFrame = QFrame()
        buttonFrame.setLayout(buttonLayout)

        formLayout.addWidget(buttonFrame)

        formFrame = QFrame()
        formFrame.setLayout(formLayout)
        layout.addWidget(formFrame)

        self.acceptButton = QPushButton('Done')
        self.helpButton = QPushButton('Help')
        self.acceptButton.setDefault(True)
        acLayout = QHBoxLayout()
        acLayout.addWidget(self.acceptButton)
        acLayout.addWidget(self.helpButton)
        self.acceptButton.clicked.connect(self.accept)
        self.helpButton.clicked.connect(self.help)

        acFrame = QFrame()
        acFrame.setLayout(acLayout)

        layout.addWidget(acFrame)

        self.setLayout(layout)

        self.setWindowTitle('Manage feature systems')

    def help(self):
        self.helpDialog = HelpDialog(self, name = 'transcriptions and feature systems')
        self.helpDialog.exec_()

    def openCsvWindow(self):
        dialog = SystemFromCsvDialog(self,self.settings)
        result = dialog.exec_()
        if result:
            self.getAvailableSystems()

    def openDownloadWindow(self):
        dialog = DownloadFeatureMatrixDialog(self,self.settings)
        result = dialog.exec_()
        if result:
            self.getAvailableSystems()

    def removeSystem(self):
        featureSystem = self.systemsList.currentItem().text()
        msgBox = QMessageBox(QMessageBox.Warning, "Remove system",
                "This will permanently remove '{}'.  Are you sure?".format(featureSystem), QMessageBox.NoButton, self)
        msgBox.addButton("Remove", QMessageBox.AcceptRole)
        msgBox.addButton("Cancel", QMessageBox.RejectRole)
        if msgBox.exec_() != QMessageBox.AcceptRole:
            return
        os.remove(system_name_to_path(self.settings['storage'],featureSystem))
        self.getAvailableSystems()


    def getAvailableSystems(self):
        self.systemsList.clear()
        systems = get_systems_list(self.settings['storage'])
        for s in systems:
            self.systemsList.addItem(s)

class SystemFromCsvDialog(PCTDialog):
    def __init__(self, parent, settings):
        PCTDialog.__init__(self, parent)

        self.settings = settings
        layout = QVBoxLayout()

        formLayout = QFormLayout()


        self.pathWidget = FileWidget('Open feature system csv','Text files (*.txt *.csv)')

        formLayout.addRow(QLabel('Path to feature system'),self.pathWidget)

        self.featureSystemSelect = FeatureSystemSelect(self.settings, add=True)

        formLayout.addRow(self.featureSystemSelect)

        self.columnDelimiterEdit = QLineEdit()
        self.columnDelimiterEdit.setText('\\t')
        formLayout.addRow(QLabel('Column delimiter (enter \'\\t\' for tab)'),self.columnDelimiterEdit)

        formFrame = QFrame()
        formFrame.setLayout(formLayout)
        layout.addWidget(formFrame)

        self.acceptButton = QPushButton('Ok')
        self.cancelButton = QPushButton('Cancel')
        self.helpButton = QPushButton('Help')
        acLayout = QHBoxLayout()
        acLayout.addWidget(self.acceptButton)
        acLayout.addWidget(self.cancelButton)
        acLayout.addWidget(self.helpButton)
        self.acceptButton.clicked.connect(self.accept)
        self.cancelButton.clicked.connect(self.reject)
        self.helpButton.clicked.connect(self.help)

        acFrame = QFrame()
        acFrame.setLayout(acLayout)

        layout.addWidget(acFrame)

        self.setLayout(layout)

        self.setWindowTitle('Create feature system from csv')

        self.thread = LoadFeatureSystemWorker()
        self.thread.errorEncountered.connect(self.handleError)

        self.progressDialog.setWindowTitle('Importing corpus...')
        self.progressDialog.beginCancel.connect(self.thread.stop)
        self.thread.updateProgress.connect(self.progressDialog.updateProgress)
        self.thread.updateProgressText.connect(self.progressDialog.updateText)
        self.thread.dataReady.connect(self.setResults)
        self.thread.dataReady.connect(self.progressDialog.accept)
        self.thread.finishedCancelling.connect(self.progressDialog.reject)

    def help(self):
        self.helpDialog = HelpDialog(self,name = 'transcriptions and feature systems',
                                    section = 'loading-a-custom-feature-system')
        self.helpDialog.exec_()

    def generateKwargs(self):
        kwargs = {}
        path = self.pathWidget.value()
        if path == '':
            reply = QMessageBox.critical(self,
                    "Missing information", "Please specify a path to the csv file.")
            return
        if not os.path.exists(path):
            reply = QMessageBox.critical(self,
                    "Invalid information", "Feature matrix file could not be located. Please verify the path and file name.")
            return
        kwargs['path'] = path
        name = self.featureSystemSelect.value()
        if name == '':
            reply = QMessageBox.critical(self,
                    "Missing information", "Please specify the transcription and feature system.")
            return

        if name in get_systems_list(self.settings['storage']):
            msgBox = QMessageBox(QMessageBox.Warning, "Duplicate name",
                    "A feature system named '{}' already exists.  Overwrite?".format(name), QMessageBox.NoButton, self)
            msgBox.addButton("Overwrite", QMessageBox.AcceptRole)
            msgBox.addButton("Abort", QMessageBox.RejectRole)
            if msgBox.exec_() != QMessageBox.AcceptRole:
                return None
        if not name:
            reply = QMessageBox.critical(self,
                    "Missing information", "Please specify a name for the transcription and feature systems.")
            return
        kwargs['name'] = name
        colDelim = codecs.getdecoder("unicode_escape")(self.columnDelimiterEdit.text())[0]
        if not colDelim:
            reply = QMessageBox.critical(self,
                    "Missing information", "Please specify a column delimiter.")
            return
        kwargs['delimiter'] = colDelim
        return kwargs

    def setResults(self, results):
        self.specifier = results

    def accept(self):
        kwargs = self.generateKwargs()
        if kwargs is None:
            return
        self.thread.setParams(kwargs)

        self.thread.start()

        result = self.progressDialog.exec_()

        self.progressDialog.reset()
        if result:
            if self.specifier is not None:
                save_binary(self.specifier,
                    system_name_to_path(self.settings['storage'],self.specifier.name))
                print('Immediately reloaded after saving binary')
            QDialog.accept(self)


