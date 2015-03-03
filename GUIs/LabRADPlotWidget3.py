import os, sys, time

import PyQt4.Qt as Qt
import PyQt4.QtCore as QtCore

from twisted.internet.defer import inlineCallbacks, returnValue

import numpy as np, matplotlib as mp, matplotlib.pyplot as plt
from matplotlib.backends.backend_qt4agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.backends.backend_qt4agg import NavigationToolbar2QTAgg as NavigationToolbar
from matplotlib.figure import Figure

UPDATE_PERIOD = 1.0         # (in seconds)
DR_LOGGER_CHECK_SKIP = 5    # check the DR Logger every X updates
COLORS = ['red', 'green', 'blue', 'magenta', 'black', 'darkgoldenrod', 'Brown', 'darkslategrey', 'orangered', 'OliveDrab']
plt.rcParams['axes.color_cycle'] = COLORS
PLOT_BACKGROUND = '#E5E5E5' # HTML colors are allowed
NEW_DATASET_SIGNAL = 99901
NEW_DATA_SIGNAL = 99902

HISTORY_TOOLTIP = 'For example: \n60 - last 60 data points \n60s - last 60 seconds \n' + \
                  '60m - last 60 minutes \n60d - last 60 days'
FILTER_TOOLTIP = "Filter out excess points to make graph more responsive.\n" + \
                  "This means not all data will be displayed for long histories or small numbers of points."
                  
NO_SERVER_STYLE = 'QPushButton {color: red; font-weight: bold;}'
NO_SERVER_TEXT = 'Not Running!'
NOT_LOGGING_STYLE = 'QPushButton {color: red; font-weight: bold;}'
NOT_LOGGING_TEXT = 'Not Logging!'
LOGGING_STYLE = 'QPushButton {color: green; font-weight: bold;}'
LOGGING_TEXT = 'Logging'

# A Qt Widget wrapper with some added functionality for selecting parts of a dataset		
class LabRADPlotWidget3(Qt.QWidget):

    def __init__(self, parent, cxn=None, path=[], dataset=None, timer=None, drLoggerName=None):
        """
        A Qt widget that plots a labrad dataset, using Matplotlib.
        """
        # run qwidget init
        Qt.QWidget.__init__(self, parent)
        # create the qt basics
        self.drLoggerName = drLoggerName
        self.drLoggerCounter = 0
        self.layout = Qt.QHBoxLayout(self)
        self.optionsLayout = Qt.QVBoxLayout()
        self.layout.addLayout(self.optionsLayout)
        self.makeOptionsBox()
        # the plots will be in a tabbed window thing
        self.tab = Qt.QTabWidget(self)
        self.layout.addWidget(self.tab)
        # labrad variables
        self.path = path
        self.dataset = dataset
        # start the labrad connection
        if cxn is None:
            self.ownCxn = True
            import labrad
            try:
                cxnDef = labrad.connectAsync(name=labrad.util.getNodeName() + ' Plot Widget')
            except AttributeError:
                import labrad.async
                cxnDef = labrad.async.connectAsync(name=labrad.util.getNodeName() + ' Plot Widget')
            cxnDef.addCallback(self.setCxn)
            self.cxn = None
        else:
            self.ownCxn = False
            self.setCxn(cxn)
        # give us a timer
        if timer is None:
            self.updateTimer = Qt.QTimer()
            self.updateTimer.timeout.connect(self.timerFunc)
            self.updateTimer.start(UPDATE_PERIOD * 1000)
        else:
            self.updateTimer = timer
            self.updateTimer.timeout.connect(self.timerFunc)
            
    def closeEvent(self, event):
        self.destroyPlot()
        self.updateTimer.stop()
        if self.ownCxn:
            self.cxn.disconnect()           
        
    def _makeLine(self):
        line = Qt.QFrame(self);
        line.setFrameShape(Qt.QFrame.HLine);
        line.setFrameShadow(Qt.QFrame.Sunken);
        return line
        
    def makeOptionsBox(self):
        # checkboxes
        self.optionsLayout.addWidget(Qt.QLabel("<b>Options:</b>"))
        self.rescaleYCB = Qt.QCheckBox("Autoscale Y-Axis", self)
        self.rescaleYCB.setChecked(True)
        self.optionsLayout.addWidget(self.rescaleYCB)
        self.rescaleXCB = Qt.QCheckBox("Autoscale X-Axis", self)
        self.rescaleXCB.setChecked(True)
        self.optionsLayout.addWidget(self.rescaleXCB)
        self.zeroXAxisCB = Qt.QCheckBox("Zero X-Axis", self)
        self.xAxisZero = None
        self.optionsLayout.addWidget(self.zeroXAxisCB)
        # history widgets
        self.historyLE = Qt.QLineEdit(self)
        self.historyLE.setFixedWidth(120)
        self.historyLE.setToolTip(HISTORY_TOOLTIP)
        label = Qt.QLabel("History: [?]", self)
        label.setToolTip(HISTORY_TOOLTIP)
        self.optionsLayout.addWidget(self._makeLine())
        self.optionsLayout.addWidget(label)
        self.optionsLayout.addWidget(self.historyLE)
        # units widgets
        tooltip = 'Any LabRAD unit. (Use min for minute.)'
        label = Qt.QLabel("X-Axis unit conversion:", self)
        label.setToolTip(tooltip)
        self.xAxisUnitsLE = Qt.QLineEdit(self)
        self.xAxisUnitsLE.setFixedWidth(120)
        self.xAxisUnitsLE.setToolTip(tooltip)
        self.optionsLayout.addWidget(label)
        self.optionsLayout.addWidget(self.xAxisUnitsLE)
        # point filtering widgets
        self.filterCB = Qt.QCheckBox("Filter points [?]", self)
        self.filterCB.setToolTip(FILTER_TOOLTIP)
        label = Qt.QLabel("Approx. max # points to display:")
        self.maxPointsLE = Qt.QLineEdit(self)
        self.maxPointsLE.setFixedWidth(120)
        self.optionsLayout.addWidget(self._makeLine())
        self.optionsLayout.addWidget(self.filterCB)
        self.optionsLayout.addWidget(label)
        self.optionsLayout.addWidget(self.maxPointsLE)
        # DR Logger server monitoring
        if self.drLoggerName:
            self.optionsLayout.addWidget(self._makeLine())
            self.optionsLayout.addWidget(Qt.QLabel("DR Logger is: "))
            self.drLoggerPB = Qt.QPushButton("Unchecked", self)
            self.drLoggerPB.clicked.connect(self.drLoggerPBClicked)
            self.optionsLayout.addWidget(self.drLoggerPB)
        else:
            self.drLoggerPB = None
        # add stretch to move them all to the top
        self.optionsLayout.addStretch()
        
    def setCxn(self, cxn):
        self.cxn = cxn
        if self.dataset:
            self.loadDataset()
        self.waitingOnLabrad=False
        
    def setDataset(self, path=[], dataset=None):
        if path:
            self.path = path
        if dataset:
            self.dataset = dataset
        self.loadDataset()
        
    def getDataset(self):
        return self.dataset
        
    def loadDataset(self):
        p = self.cxn.data_vault.packet()
        p.cd(self.path)
        p.dir()
        d = p.send()
        d.addCallback(self.loadDatasetCallback)
        
    def loadDatasetCallback(self, response):
        # load up our dataset.
        dsList = response.dir[1]
        if type(self.dataset) == str and not self.dataset in dsList:
            for ds in dsList:
                if self.dataset in ds:
                    self.dataset = ds
                    break
            else:   # note this else is for the for loop, not the if statement
                self.dataset = None
                print "Dataset %s not found!" % self.dataset
        p = self.cxn.data_vault.packet()
        p.open(self.dataset)
        p.send()
        self.rebuildPlot = True
        # automatically switch datasets when new one created in our current directory
        dv = self.cxn.data_vault
        dv.signal__new_dataset(NEW_DATASET_SIGNAL)
        dv.addListener(listener = self.switchDataset, source=None, ID=NEW_DATASET_SIGNAL)
        
    def switchDataset(self, msgContext, newDataset):
        # we've received a signal for a new dataset. switch to it.
        print "Switching dataset to: %s" % newDataset
        self.dataset = newDataset
        p = self.cxn.data_vault.packet()
        p.open(self.dataset)
        p.send()
        
    def timerFunc(self):
        if self.waitingOnLabrad:
            return
        if not self.dataset:
            return
        p = self.cxn.data_vault.packet()
        if self.rebuildPlot:
            p.variables()
        p.get(5000)         # don't grab the whole DS at once, just in case
        d = p.send()
        d.addCallback(self.datavaultCallback)
        # now check on the DR logger
        if self.drLoggerName and self.drLoggerCounter == 0:
            if self.drLoggerName not in self.cxn.servers:
                self.drLoggerCallback(None)
            else:
                p = self.cxn[self.drLoggerName].packet()
                p.select_device()
                p.logging()
                d = p.send()
                d.addCallback(self.drLoggerCallback)
        self.drLoggerCounter += 1
        self.drLoggerCounter %= DR_LOGGER_CHECK_SKIP
        
    def drLoggerCallback(self, response):
        ''' update the DR Logger monitoring stuff.
        if response is None, then there was no DR Logger server '''
        if response is None:
            self.drLoggerPB.setStyleSheet(NO_SERVER_STYLE)
            self.drLoggerPB.setText(NO_SERVER_TEXT)
        elif not response.logging:
            self.drLoggerPB.setStyleSheet(NOT_LOGGING_STYLE)
            self.drLoggerPB.setText(NOT_LOGGING_TEXT)
        elif response.logging:
            self.drLoggerPB.setStyleSheet(LOGGING_STYLE)
            self.drLoggerPB.setText(LOGGING_TEXT)
    
    def drLoggerPBClicked(self):
        if str(self.drLoggerPB.text()) == LOGGING_TEXT:
            self.drLoggerPB.setText('Nothing to do!')
        elif str(self.drLoggerPB.text()) == NOT_LOGGING_TEXT:
            p = self.cxn[self.drLoggerName].packet()
            p.select_device()
            p.logging(True)
            p.send()
            self.drLoggerPB.setText('Starting...')
        elif str(self.drLoggerPB.text()) == NO_SERVER_TEXT:
            # find node
            for s in self.cxn.servers:
                if s.lower().startswith('node'):
                    break
            else:
                self.drLoggerPB.setText('No node found!')
                return
            self.cxn[s].start(self.drLoggerName)
            self.drLoggerPB.setText('Starting...')
        
    def datavaultCallback(self, response):
        self.newData = response.get
        if hasattr(self.newData, 'asarray'): # Backwards compatibility
            self.newData = self.newData.asarray
        if 'variables' in response.settings:
            self.variables = response.variables
            self.xAxisCurrentUnit = self.variables[0][0][1]
        if self.rebuildPlot:
            self.buildPlot()
            self.handleUnitConversion()
            self.handleZeroing()
        else:
            self.handleUnitConversion()
            self.handleZeroing()
            self.plotNewData()

    def destroyPlot(self):
        ''' Delete the current plot. '''
        self.tab.clear()
        self.tabs = {}
        self.canvases = {}
        self.figures = {}
        self.lines = []
        self.linesByLabel = {}

    def buildPlot(self):
        ''' build a new plot. '''
        self.destroyPlot()
        self.dirtyPlots = True
        # parse the variables
        xlabel = '%s [%s]' % (self.variables[0][0])
        labels = []
        legends = {}
        units = {}        
        for legend, label, unit in self.variables[1]:
            if label not in labels:
                labels.append(label)
                legends[label] = [legend]
                units[label] = [unit]
            else:
                legends[label].append(legend)
                units[label].append(units)
        # now make the tabs
        for label in labels:
            # create a widget for the tab
            tab = Qt.QWidget(self.tab)
            layout = Qt.QVBoxLayout(tab)
            # create the matplotlib stuff to go in the widget
            figure = Figure()
            canvas = FigureCanvas(figure)
            canvas.setSizePolicy(Qt.QSizePolicy.Expanding, Qt.QSizePolicy.Expanding)
            layout.addWidget(canvas)
            toolbar = NavigationToolbar(canvas, None)
            layout.addWidget(toolbar)
            # add widget to the tab container
            self.tab.addTab(tab, label)
            # save the tab and figure to self
            self.tabs[label] = tab
            self.canvases[label] = canvas
            self.figures[label] = figure
            self.linesByLabel[label] = []
        # now make the lines
        for i, (legend, label, unit) in enumerate(self.variables[1]):
            fig = self.figures[label]
            if fig.axes:
                ax = fig.axes[0]
            else:
                ax = self.figures[label].add_subplot(111, axisbg=PLOT_BACKGROUND)
            # the data are stored in self.data
            self.data = self.newData.copy()
            line = ax.plot(self.data[:,0], self.data[:,i+1], '.-', label=legend)[0]
            self.lines.append(line)
            self.linesByLabel[label].append(line)
            ax.set_xlabel(xlabel, fontsize=19)
            ax.set_ylabel("%s [%s]" % (label, unit), fontsize=19)
            ax.grid(True, which='major')
            fig.tight_layout()
        self.rescale()
        self.buildLineButtons()
        self.rebuildPlot = False
        
    def plotNewData(self):
        if self.newData is not None and self.newData.shape[0] != 0:
            # update data
            self.data = np.append(self.data, self.newData, axis=0)
        elif not self.dirtyPlots:
            return
        # for each line, figure out which data points to plot
        if self.rescaleXCB.isChecked():
            xmin, xmax = self.handleHistory()
        else:
            label = str(self.tab.tabText(self.tab.currentIndex()))
            xmin, xmax = self.figures[label].axes[0].get_xlim()
        imin, imax = np.searchsorted(self.data[:,0], [xmin, xmax])
        # are we filtering points?
        try:
            if self.filterCB.isChecked():
                points_to_display = int(self.maxPointsLE.text())
            else:
                points_to_display = None
        except ValueError:
            points_to_display = None
        if points_to_display:
            step = max(1, int((imax - imin) / points_to_display))
        else:
            step = 1
        start = imin
        while start % step != (imax-1)%step:
            start += 1
        # now slice out those data points and plot them
        for i, (legend, label, unit) in enumerate(self.variables[1]):
            self.lines[i].set_xdata(self.data[start::step,0])
            self.lines[i].set_ydata(self.data[start::step,i+1])
            d = self.data[-1, i+1]
            if d < 1 and d > 1e-3:
                self.lines[i].my_label.setText('{0:.3f}'.format(d))
            else:
                self.lines[i].my_label.setText('{0:.3g}'.format(d))
        self.newData = None
        self.dirtyPlots = False
        self.rescale()

    def handleZeroing(self):
        # are we zero-ing the x-axis data?
        if self.zeroXAxisCB.isChecked():
            if self.xAxisZero is not None:
                # if we've already done it, just do to new data
                self.newData[:,0] -= self.xAxisZero
            else:
                # if not, do it to all data
                self.xAxisZero = self.data[0,0]
                self.data[:,0] -= self.xAxisZero
                self.newData[:,0] -= self.xAxisZero
                self.dirtyPlots = True
        # have we previously zeroed the data and now we undo it?
        elif self.xAxisZero is not None:
            self.data[:,0] += self.xAxisZero
            self.dirtyPlots = True
            self.xAxisZero = None
            
    def handleUnitConversion(self):
        ''' Note that we only do unit conversion for the (shared) X-axis. '''
        import labrad.units as U
        newUnit = str(self.xAxisUnitsLE.text()).strip()
        currentUnit = U.Unit(self.xAxisCurrentUnit)
        originalUnit = U.Unit(self.variables[0][0][1])
        if not newUnit:
            newUnit = self.variables[0][0][1]
        # if we change units, convert old data
        if newUnit != self.xAxisCurrentUnit:
            try:
                conversion = currentUnit.conversionTupleTo(newUnit)
                self.data[:,0] = (self.data[:,0] + conversion[1]) * conversion[0]
                if self.xAxisZero is not None:
                    self.xAxisZero = (self.xAxisZero + conversion[1])*conversion[0]
                self.xAxisCurrentUnit = newUnit
                for figure in self.figures.values():
                    figure.axes[0].set_xlabel('%s [%s]' % (self.variables[0][0][0], self.xAxisCurrentUnit))
                self.dirtyPlots = True
            except TypeError as e:
                pass
        # run new data through conversion
        if self.newData is not None and self.newData.shape[0] > 0:
            conversion = originalUnit.conversionTupleTo(self.xAxisCurrentUnit)
            self.newData[:,0] = (self.newData[:,0]+conversion[1])*conversion[0]

    def rescale(self):
        ''' scale the plots to show all the data. only use visible lines. account for absolute limits in settings. '''
        for figure in self.figures.values():
            ax = figure.axes[0]            
            if self.rescaleXCB.isChecked():
                xmin, xmax = self.handleHistory()
                ax.set_xlim(xmin, xmax)
            else:
                xmin, xmax = ax.get_xlim()
            if self.rescaleYCB.isChecked():
                xdata = self.data[:,0]
                imin, imax = np.searchsorted(xdata, [xmin, xmax])
                ymax, ymin = None, sys.float_info.max
                for i, l in enumerate(ax.lines):
                    if not l.get_visible():
                        continue
                    ydata = l.get_ydata()
                    ymax, ymin = max(ydata.max(), ymax), min(ydata.min(), ymin)
                if ymax:
                    yrange = ymax-ymin
                    ax.set_ylim(ymin-yrange/10, ymax+yrange/10)
        # and redraw
        for canvas in self.canvases.values():
            canvas.draw()
                
            
    def handleHistory(self):
        import labrad.units as U
        hist = str(self.historyLE.text()).strip()
        xdata = self.data[:,0]
        xunit = self.xAxisCurrentUnit
        xmax = xdata.max()
        try:
            if hist[-1] == 's':
                xmin = xmax - (float(hist[:-1])*U.s)[xunit]
            elif hist[-1] == 'm':
                xmin = xmax - (float(hist[:-1])*U.min)[xunit]
            elif hist[-1] == 'h':
                xmin = xmax - (float(hist[:-1])*U.h)[xunit]
            elif hist[-1] == 'd':
                xmin = xmax - (float(hist[:-1])*U.d)[xunit]
            else:
                xmin = xdata[-int(hist):].min()
            return max(xmin, xdata.min()), xmax
        except (ValueError, IndexError) as e:
            return xdata.min(), xdata.max()
            
    def buildLineButtons(self):
        ''' Create a toggle button for each line on each graph.
            Create a label with the current value underneath. '''
        # the button callback factory
        def make_callback(button):
            ''' wrap the callback in another function to keep the variable
                'button' in the closure. Yay Python!'''
            def callback():
                button._my_line.set_visible(button.isChecked())
                button._my_canvas.draw()
                self.rescale()
            return callback
        
        for label, lines in self.linesByLabel.items():
            # line them up in a row
            layout = Qt.QHBoxLayout()
            dataLayout = Qt.QHBoxLayout()
            for line in lines:
                # button
                button = Qt.QPushButton(unichr(9644) +' '+ line.get_label(), self.tabs[label])
                button.setStyleSheet('QPushButton {color: %s; font-weight: bold; font-size: 16px}' % line.get_color())
                button.setCheckable(True)
                button.setChecked(line.get_visible())
                button.setMinimumHeight(50)
                button._my_line = line
                button._my_canvas = self.canvases[label]
                button.clicked.connect(make_callback(button))
                layout.addWidget(button)
                # label
                lab = Qt.QLabel('0.0', self.tabs[label])
                lab.setStyleSheet('QLabel {font-weight: bold; font-size: 18pt; qproperty-alignment: AlignCenter;}')
                dataLayout.addWidget(lab)
                line.my_label = lab
                
            # add to the tab
            self.tabs[label].layout().addLayout(layout)
            self.tabs[label].layout().addLayout(dataLayout)
        
def make():
    demo = LabRADPlotWidget3(None, path=["", "DR", "Danko"], dataset=25)
    demo.resize(1000, 800)
    demo.show()
    return demo


def main(args):
    app = Qt.QApplication(args)
    
    import qt4reactor
    qt4reactor.install()
    from twisted.internet import reactor
    import labrad, labrad.util
    
    reactor.runReturn()
    demo = make()
    v = app.exec_()
    reactor.threadpool.stop()
    sys.exit(v)

if __name__ == '__main__':
    main(sys.argv)
