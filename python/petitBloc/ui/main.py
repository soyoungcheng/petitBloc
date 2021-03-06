import operator
import re
import os
from Qt import QtWidgets
from Qt import QtCore
from Qt import QtGui
from Nodz import nodz_main
from . import const
from . import model
from . import graph
from . import paramEditor
from . import packetHistory
from . import logViewer
from . import uiUtil
from . import sceneState
from . import progress
from .. import scene
from .. import blockManager


class MainWindow(QtWidgets.QMainWindow):
    def __init__(self, parent=None):
        super(MainWindow, self).__init__(parent=parent)
        self.__graph = None
        self.__graph_tabs = None
        self.__editor_tabs = None
        self.__run = None
        self.__parm_editor = None
        self.__packet_history = None
        self.__scene_state = None
        self.__log_viewer = None
        self.__networks = {}
        self.__filepath = None
        self.__current_bloc = None
        self.__progress = None
        self.__is_running = False
        self.__initialize()
        self.__setStyleSheet()

    def __setStyleSheet(self):
        qss_path = os.path.abspath(os.path.join(__file__, "../style.qss"))

        if not os.path.isfile(qss_path):
            return

        current_dir = os.path.dirname(__file__)

        style = ""
        with open(qss_path, "r") as f:
            style = f.read()
            style = style.replace('url("', 'url("%s/' % current_dir.replace("\\", "/"))

        self.setStyleSheet(style)

    def __initialize(self):
        ## force reload
        b = blockManager.BlockManager()
        b.reload()

        self.setObjectName(const.ObjectName)

        centeral = QtWidgets.QWidget()
        main_layout = QtWidgets.QVBoxLayout()
        self.setCentralWidget(centeral)
        centeral.setLayout(main_layout)

        # tabs
        self.__editor_tabs = QtWidgets.QTabWidget()
        self.__graph_tabs = QtWidgets.QTabWidget()
        self.__graph_tabs.setTabsClosable(True)

        # scene graph
        ## TODO : USE __new()
        self.__graph = graph.Graph(name=const.RootBoxName, parent=self, isTop=True)
        self.__graph_tabs.addTab(self.__graph, "Scene")
        self.__graph_tabs.tabBar().tabButton(0, QtWidgets.QTabBar.RightSide).hide()
        self.__networks[self.__graph.box()] = {"graph": self.__graph, "init": False}

        # editor tabs
        self.__parm_editor = paramEditor.ParamEditor()
        self.__packet_history = packetHistory.PacketHistory()
        self.__log_viewer = logViewer.LogViewer()
        self.__editor_tabs.addTab(self.__parm_editor, "Param Editor")
        self.__editor_tabs.addTab(self.__packet_history, "Packet History")
        self.__editor_tabs.addTab(self.__log_viewer, "Log")

        main_contents = QtWidgets.QSplitter()
        main_contents.addWidget(self.__graph_tabs)
        main_contents.addWidget(self.__editor_tabs)

        # scene state
        self.__scene_state = sceneState.SceneState()

        main_layout.addWidget(main_contents)
        main_layout.addWidget(self.__scene_state)
        self.__resetTabIndice()

        # menu
        menubar = self.menuBar()
        file_menu = QtWidgets.QMenu("&File", self)
        news_action = file_menu.addAction("&New Scene")
        news_action.setShortcut(QtGui.QKeySequence("Ctrl+N"))
        open_action = file_menu.addAction("&Open")
        open_action.setShortcut(QtGui.QKeySequence("Ctrl+O"))
        save_action = file_menu.addAction("Save")
        save_action.setShortcut(QtGui.QKeySequence("Ctrl+S"))
        save_as_action = file_menu.addAction("Save As")
        save_as_action.setShortcut(QtGui.QKeySequence("Ctrl+Shift+S"))
        import_action = file_menu.addAction("&Import")
        import_action.setShortcut(QtGui.QKeySequence("Ctrl+I"))
        file_menu.addAction(news_action)
        file_menu.addSeparator()
        file_menu.addAction(open_action)
        file_menu.addSeparator()
        file_menu.addAction(save_action)
        file_menu.addAction(save_as_action)
        file_menu.addSeparator()
        file_menu.addAction(import_action)
        news_action.triggered.connect(self.__new)
        save_action.triggered.connect(self.__save)
        save_as_action.triggered.connect(self.__saveAs)
        open_action.triggered.connect(self.__open)
        import_action.triggered.connect(self.__importBox)
        menubar.addMenu(file_menu)

        process_menu = QtWidgets.QMenu("&Blocks", self)
        run_action = process_menu.addAction("&Execute")
        run_action.setShortcut(QtGui.QKeySequence("F5"))
        menubar.addMenu(process_menu)

        setting_menu = QtWidgets.QMenu("Log", self)
        log_group = QtWidgets.QActionGroup(self)
        log_group.setExclusive(True)
        no_log = setting_menu.addAction("No Log")
        error_log = setting_menu.addAction("Error")
        warn_log = setting_menu.addAction("Warning")
        debug_log = setting_menu.addAction("Debug")
        no_log.setCheckable(True)
        error_log.setCheckable(True)
        warn_log.setCheckable(True)
        debug_log.setCheckable(True)
        log_group.addAction(no_log)
        log_group.addAction(error_log)
        log_group.addAction(warn_log)
        log_group.addAction(debug_log)
        error_log.setChecked(True)
        no_log.triggered.connect(self.__noLogTriggered)
        error_log.triggered.connect(self.__errorLogTriggered)
        warn_log.triggered.connect(self.__warnLogTriggered)
        debug_log.triggered.connect(self.__debugLogTriggered)

        menubar.addMenu(setting_menu)

        ## progress
        self.__progress = progress.Progress(self)
        self.__progress.hide()

        run_action.triggered.connect(self.__runTriggered)

        self.__graph_tabs.tabCloseRequested.connect(self.__closeGraphRequest)
        self.__graph_tabs.currentChanged.connect(self.__currentGraphTabChanged)

        self.__parm_editor.BlockRenamed.connect(self.__blockRenamed)

        self.__graph.CurrentNodeChanged.connect(self.__currentBlockChanged)
        self.__graph.ItemDobleClicked.connect(self.__showGraphTab)
        self.__graph.BoxDeleted.connect(self.__boxDeleted)

        self.__graph.BoxCreated.connect(self.__boxCreated)

        self.__setPath(None)

    def __blockRenamed(self, bloc, newName):
        for n_dict in self.__networks.values():
            if n_dict["graph"].renameNode(bloc, newName):
                return

        raise Exception, "Failed to find the node : {}".format(oldName)

    def __noLogTriggered(self):
        self.__log_viewer.setLogLevel(0)

    def __errorLogTriggered(self):
        self.__log_viewer.setLogLevel(1)

    def __warnLogTriggered(self):
        self.__log_viewer.setLogLevel(2)

    def __debugLogTriggered(self):
        self.__log_viewer.setLogLevel(3)

    def __currentGraphTabChanged(self, index):
        widget = None

        for n_dict in self.__networks.values():
            if n_dict.get("index", None) == index:
                widget = n_dict["graph"]
                break

        if widget is None:
            return

        self.__currentBlockChanged(widget.currentBlock())

    def __boxCreated(self, boxBloc, init):
        if self.__networks.has_key(boxBloc):
            return

        grph = graph.SubNet(boxObject=boxBloc)
        grph.ItemDobleClicked.connect(self.__showGraphTab)
        grph.CurrentNodeChanged.connect(self.__currentBlockChanged)
        grph.BoxDeleted.connect(self.__boxDeleted)
        grph.ProxyPortAdded.connect(self.__addProxyPort)
        grph.ProxyPortRemoved.connect(self.__removeProxyPort)
        grph.BoxCreated.connect(self.__boxCreated)

        self.__networks[boxBloc] = {"graph": grph, "init": init}

    def __showGraphTab(self, bloc):
        widget_created = False

        box_data = self.__networks[bloc]

        if box_data.get("index") is None:
            widget_created = True
            index = self.__graph_tabs.addTab(self.__networks[bloc]["graph"], bloc.path())
            self.__networks[bloc]["index"] = index

        self.__graph_tabs.setCurrentIndex(self.__networks[bloc]["index"])

        if self.__networks[bloc]["init"]:
            self.__networks[bloc]["graph"].initProxyNode()
            self.__networks[bloc]["init"] = False

    def __boxDeleted(self, bloc):
        path = bloc.path()

        remove_blocs = []
        remove_widgets = []
        remove_indices = []

        for bloc, n_dict in self.__networks.iteritems():
            if bloc.path().startswith(path):
                remove_blocs.append(bloc)
                widget = n_dict.get("graph")
                index = n_dict.get("index")
                if widget is not None:
                    remove_widgets.append(widget)

                if index is not None:
                    remove_indices.append(index)

        remove_indices.sort()
        remove_indices.reverse()

        while (remove_indices):
            index = remove_indices.pop(0)
            self.__graph_tabs.removeTab(index)

        while (remove_blocs):
            bloc = remove_blocs.pop(0)
            self.__networks.pop(bloc, None)

        while (remove_widgets):
            widget = remove_widgets.pop(0)
            widget.close()
            del widget

        self.__resetTabIndice()

    def __closeGraphRequest(self, index):
        if index <= 0:
            return

        self.__graph_tabs.removeTab(index)
        self.__resetTabIndice()

    def __resetTabIndice(self):
        for n_dict in self.__networks.values():
            index = self.__graph_tabs.indexOf(n_dict["graph"])
            n_dict["index"] = None if index < 0 else index

    def __addProxyPort(self, boxBloc, proxyNode, port):
        par_dict = self.__networks.get(boxBloc.parent(), None)

        if not par_dict:
            return

        node = par_dict["graph"].findNode(boxBloc)

        if port.isInPort():
            par_dict["graph"].createAttribute(node=node, port=port, plug=False, socket=True, preset="attr_preset_1", dataType=port.typeClass(), proxyNode=proxyNode)
        else:
            par_dict["graph"].createAttribute(node=node, port=port, plug=True, socket=False, preset="attr_preset_1", dataType=port.typeClass(), proxyNode=proxyNode)

    def __removeProxyPort(self, boxBloc, proxyNode, name):
        par_dict = self.__networks.get(boxBloc.parent(), None)
        if not par_dict:
            return

        node = par_dict["graph"].findNode(boxBloc)

        par_dict["graph"].deleteAttribute(node, node.attrs.index(name))

    def resizeEvent(self, event):
        if self.__is_running:
            self.__matchProgressSize()

    def __matchProgressSize(self):
        self.__progress.setGeometry(0, 0, self.size().width(), self.size().height())

    def __runTriggered(self):
        self.__is_running = True
        self.__matchProgressSize()

        self.__progress.show()

        self.__graph.boxModel().run(manager=self.__progress.manager())

        graph = None
        index = self.__graph_tabs.currentIndex()

        for n_dict in self.__networks.values():
            if n_dict.get("index") == index:
                n_dict["graph"].update()
                break

        self.__packet_history.refresh()
        self.__graph.boxModel().readLogs()
        if self.__current_bloc is None:
            self.__log_viewer.clear()
        else:
            self.__log_viewer.setLogs(*self.__graph.boxModel().getLogs(self.__current_bloc.path()))

        self.__scene_state.setStates(*self.__graph.boxModel().getState())
        self.__progress.hide()
        self.__is_running = False

    def __getParentGraph(self, path):
        return self.__getGraph(os.path.dirname(path))

    def __getGraph(self, path):
        for bloc, n_dict in self.__networks.iteritems():
            if bloc.path() == path:
                return n_dict["graph"]

        return None

    def __setPath(self, path):
        self.__filepath = path
        if path is None:
            self.setWindowTitle("untitled")
        else:
            self.setWindowTitle(self.__filepath)

    def __new(self):
        while (self.__graph_tabs.count() > 0):
            self.__graph_tabs.removeTab(0)

        for n_dict in self.__networks.values():
            n_dict["graph"].close()
            del n_dict["graph"]

        self.__networks = {}

        self.__graph = graph.Graph(name=const.RootBoxName, parent=self, isTop=True)
        self.__graph_tabs.addTab(self.__graph, "Scene")
        self.__graph_tabs.tabBar().tabButton(0, QtWidgets.QTabBar.RightSide).hide()
        self.__networks[self.__graph.box()] = {"graph": self.__graph, "init": False}

        self.__graph.CurrentNodeChanged.connect(self.__currentBlockChanged)
        self.__graph.ItemDobleClicked.connect(self.__showGraphTab)
        self.__graph.BoxDeleted.connect(self.__boxDeleted)

        self.__graph.BoxCreated.connect(self.__boxCreated)

        self.__resetTabIndice()
        self.__setPath(None)
        self.__graph.boxModel().resetLogs()

    def __save(self):
        if self.__filepath is None:
            self.__saveAs()
            return

        self.__saveData()

    def __saveData(self):
        data = self.__graph.boxModel().serialize()
        for b in data["blocks"]:
            path = uiUtil.AddRootPath(b["path"])
            grph = self.__getParentGraph(path)

            if grph is None:
                raise Exception, "Failed to save : could not find the parent graph - {}".format(path)

            nod = grph.findNodeFromName(self.__shortName(path))
            if nod is None:
                raise Exception, "Failed to save : could not find the node - {}".format(path)

            pos = nod.pos() + nod.nodeCenter
            b["pos"] = [pos.x(), pos.y()]

        scene.Write(self.__filepath, data)

    def __saveAs(self):
        res = QtWidgets.QFileDialog.getSaveFileName(self, "Save", "", "*.blcs")
        if isinstance(res, tuple):
            pth = res[0]
        else:
            pth = res

        if not pth:
            return

        ext = os.path.splitext(pth)[-1]
        if not ext:
            pth += ".blcs"

        self.__setPath(pth)
        self.__saveData()

    def __shortName(self, path):
        return os.path.basename(path)

    def __importBox(self):
        res = QtWidgets.QFileDialog.getOpenFileName(self, "Import", "", "*.blcs")

        if isinstance(res, tuple):
            pth = res[0]
        else:
            pth = res

        if not pth:
            return

        graph = None
        index = self.__graph_tabs.currentIndex()

        for n_dict in self.__networks.values():
            if n_dict["index"] == index:
                graph = n_dict["graph"]
                break

        node = graph.addBlock("Box", blockName=uiUtil.BaseName(pth), position=graph.mapToScene(graph.viewport().rect().center()))

        self.__read(pth, node.block().path())

        self.__resetTabIndice()

    def openScene(self, path):
        self.__new()
        self.__read(path, "/{}".format(const.RootBoxName))

        self.__resetTabIndice()
        self.__setPath(path)

    def __open(self):
        res = QtWidgets.QFileDialog.getOpenFileName(self, "Open", "", "*.blcs")

        if isinstance(res, tuple):
            pth = res[0]
        else:
            pth = res

        if not pth:
            return

        self.__new()
        self.__read(pth, "/{}".format(const.RootBoxName))

        self.__resetTabIndice()
        self.__setPath(pth)
        self.__graph._focus()

    def __read(self, filePath, rootPath):
        reRootNode = re.compile("^[/]{}[/]".format(rootPath.replace("/", "\/")))
        def addRootPath(path):
            if reRootNode.search(path):
                return path

            return "{}/{}".format(rootPath, path)

        data = scene.Read(filePath)

        ## create blocks
        for b in data["blocks"]:
            full_path = addRootPath(b["path"])

            if b["type"] == "SceneContext":
                if "/{}".format(const.RootBoxName) != os.path.dirname(full_path):
                    continue

            short_name = self.__shortName(full_path)
            grph = self.__getParentGraph(full_path)
            bloc = None
            if grph is None:
                raise Exception, "Failed to load : could not find the parent graph - {}".format(full_path)

            if b.get("preservered", False):
                node = grph.findNodeFromName(short_name)
                if node is None:
                    print("Warning : could not find a preservered node : {}".format(full_path))
                    continue

                bloc = node.block()

                pos = b.get("pos")
                if pos:
                    node.setPos(QtCore.QPointF(pos[0], pos[1]) - node.nodeCenter)

            else:
                pos = b.get("pos")
                if pos:
                    posf = QtCore.QPointF(pos[0], pos[1])
                else:
                    posf = grph.mapToScene(grph.viewport().rect().center())

                node = grph.addBlock(b["type"], blockName=short_name, position=posf, init=False)
                if node is None:
                    print("Warning : Unknown block type : {}".format(b["type"]))
                    continue

                bloc = node.block()

            if bloc is not None:
                for k, vv in b.get("params", {}).iteritems():
                    parm = bloc.param(k)
                    if parm is None:
                        print("Warning : {} has not the parameter : {}".format(str(bloc), k))
                        continue

                    if not parm.set(vv["value"]):
                        print("Warning : Failed to set value {}@{} - {}".format(bloc.path(), k, str(vv["value"])))

                    if not parm.setExpression(vv["expression"]):
                        print("Warning : Failed to set expression {}@{} - {}".format(bloc.path(), k, str(vv["expression"])))

                for k, vv in b.get("extraParams", {}).iteritems():
                    type_name = vv["type"]
                    type_class = self.__graph.boxModel().findObjectClass(type_name)
                    if not type_class:
                        print("Warning : unknown parameter type - {}".format(type_name))
                        continue

                    parm = bloc.addExtraParam(type_class, k)
                    if parm is None:
                        print("Warning : Failed to add an extra parameter : {}".format(str(bloc), k))
                        continue

                    if not parm.set(vv["value"]):
                        print("Warning : Failed to set value {}@{} - {}".format(bloc.path(), k, str(vv["value"])))

                    if not parm.setExpression(vv["expression"]):
                        print("Warning : Failed to set expression {}@{} - {}".format(bloc.path(), k, str(vv["expression"])))

        ## proxy ports
        for proxy in data["proxyPorts"]:
            full_path = addRootPath(proxy["path"])
            grph = self.__getGraph(full_path)

            if grph is None:
                raise Exception, "Failed to load : could not find the graph - {}".format(full_path)

            for inp in proxy.get("in", []):
                name = inp["name"]
                type_name = inp["type"]

                type_class = self.__graph.boxModel().findObjectClass(type_name)
                if not type_class:
                    print("Failed to load : unknown port type - {}".format(type_name))

                    continue

                grph.addInputProxy(type_class, name)

            for outp in proxy.get("out", []):
                name = outp["name"]
                type_name = outp["type"]

                type_class = self.__graph.boxModel().findObjectClass(type_name)
                if not type_class:
                    print("Failed to load : unknown port type - {}".format(type_name))

                    continue

                grph.addOutputProxy(type_class, name)

        ## connect ports
        for con in data["connections"]:
            parent = None

            src_node_path, src_port = addRootPath(con["src"]).split(".")
            dst_node_path, dst_port = addRootPath(con["path"]).split(".")
            src_depth = src_node_path.count("/")
            dst_depth = dst_node_path.count("/")
            src_parent = self.__getParentGraph(src_node_path)
            dst_parent = self.__getParentGraph(dst_node_path)

            if src_parent is None or dst_parent is None:
                print("Warning : Failed to connect - could not find the parent graph '{}', '{}'".format(con["src"], con["path"]))
                continue

            if src_parent != dst_parent:
                ## TODO : improve this more smarter
                if src_depth >= dst_depth:
                    src_node_path = uiUtil.ParentPath(src_node_path)
                    src_parent = self.__getParentGraph(src_node_path)

                    if src_parent != dst_parent:
                        dst_node_path = uiUtil.ParentPath(dst_node_path)
                        dst_parent = self.__getParentGraph(dst_node_path)

                        if src_parent != dst_parent:
                            print("Warning : Failed to connect - could not find the parent graph '{}', '{}'".format(con["src"], con["path"]))
                            continue

                else:
                    dst_node_path = uiUtil.ParentPath(dst_node_path)
                    dst_parent = self.__getParentGraph(dst_node_path)

                    if dst_parent != src_parent:
                        src_node_path = uiUtil.ParentPath(src_node_path)
                        src_parent = self.__getParentGraph(src_node_path)

                        if src_parent != dst_parent:
                            print("Warning : Failed to connect - could not find the parent graph '{}', '{}'".format(con["src"], con["path"]))
                            continue

            src_parent.createConnection(self.__shortName(src_node_path), src_port, self.__shortName(dst_node_path), dst_port)

    def __currentBlockChanged(self, bloc):
        self.__current_bloc = bloc

        if not bloc:
            self.__parm_editor.setBlock(None)
            self.__packet_history.setBlock(None)
            self.__log_viewer.clear()
            return

        self.__parm_editor.setBlock(bloc)
        self.__packet_history.setBlock(bloc)
        self.__log_viewer.setLogs(*self.__graph.boxModel().getLogs(bloc.path()))
