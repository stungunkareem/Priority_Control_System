from PyQt5.QtWidgets import QApplication, QMainWindow, QTableWidgetItem, QComboBox, QMessageBox, QVBoxLayout, QDialog
from PyQt5.QtCore import Qt, QTimer, QThread, pyqtSignal
from PyQt5 import uic
import sys
import os
import psutil
import pyqtgraph as pg
import numpy as np

PRIORITY_CLASSES = {
    'Low': psutil.IDLE_PRIORITY_CLASS,
    'Below Normal': psutil.BELOW_NORMAL_PRIORITY_CLASS,
    'Normal': psutil.NORMAL_PRIORITY_CLASS,
    'Above Normal': psutil.ABOVE_NORMAL_PRIORITY_CLASS,
    'High': psutil.HIGH_PRIORITY_CLASS,
    'Real Time': psutil.REALTIME_PRIORITY_CLASS
}

PRIORITY_ORDER = {
    'Low': 1,
    'Below Normal': 2,
    'Normal': 3,
    'Above Normal': 4,
    'High': 5,
    'Real Time': 6
}

def get_priority_name(nice_value):
    for name, value in PRIORITY_CLASSES.items():
        if value == nice_value:
            return name
    return 'Normal'

script_dir = os.path.dirname(os.path.abspath(__file__))

class ProcessUpdater(QThread):
    process_updated = pyqtSignal(list)
    def run(self):
        while True:  
            process_info = []
            for proc in psutil.process_iter(['pid', 'name', 'nice', 'status', 'cpu_percent', 'memory_info']):
                try:
                    pid = str(proc.info['pid'])
                    name = proc.info['name']
                    status = proc.info['status']
                    if status == psutil.STATUS_RUNNING:
                        priority = get_priority_name(proc.info['nice'])
                        cpu_usage = str(int(proc.info['cpu_percent']/(psutil.cpu_count(logical=False)*2)))
                        memory_usage = proc.info['memory_info'].rss / 1024
                        process_info.append((pid, name, priority, cpu_usage, memory_usage))
                except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                    pass

            self.process_updated.emit(process_info)
            self.sleep(1)

class AppDemo(QMainWindow):
    def __init__(self):
        super().__init__()
        uic.loadUi(script_dir+'\\test.ui', self)
        self.setup_ui()
        self.setup_process_updater()
        self.setup_table_sorting()
        self.setup_button()
        self.setup_selection_change()
        self.lock_window_resizing()

    def setup_ui(self):
        self.current_sort_column = None
        self.current_sort_order = None
        self.process_info = []
        self.process_updater = ProcessUpdater()
        self.process_updater.process_updated.connect(self.update_table)
        self.graph_widget = pg.PlotWidget(title="Memory Utilization")
        self.graph_data = np.zeros(60)
        self.graph_curve = self.graph_widget.plot(self.graph_data, pen=pg.mkPen('b', width=2))
        self.graph_widget.setBackground('w')
        self.graph_widget.showGrid(x=True, y=True)
        self.graph_widget.setYRange(0, 100, padding=0)
        self.graph_widget.setXRange(0, 60, padding=0)
        self.graph_timer = QTimer()
        self.graph_timer.timeout.connect(self.update_graph)

    def setup_process_updater(self):
        self.process_updater.start()

    def setup_table_sorting(self):
        self.tableWidget.horizontalHeader().sectionClicked.connect(self.sort_table)

    def setup_button(self):
        self.pushButton.clicked.connect(self.exit_program)
        self.pushButton_2.setEnabled(False)
        self.pushButton_2.clicked.connect(self.end_selected_process)
        self.pushButton_3.clicked.connect(self.show_memory_usage_graph)

    def lock_window_resizing(self):
        self.setFixedSize(self.size())

    def exit_program(self):
        reply = QMessageBox.question(self, 'Exit Confirmation', 'Are you sure you want to exit?',
                                     QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        if reply == QMessageBox.Yes:
            QApplication.quit()

    def update_process_info(self):
        process_info = []
        for proc in psutil.process_iter(['pid', 'name', 'nice', 'status', 'cpu_percent', 'memory_info']):
            try:
                pid = str(proc.info['pid'])
                name = proc.info['name']
                status = proc.info['status']
                if status == psutil.STATUS_RUNNING:
                    priority = get_priority_name(proc.info['nice'])
                    cpu_usage = str(int(proc.info['cpu_percent']/(psutil.cpu_count(logical=False)*2)))
                    memory_usage = proc.info['memory_info'].rss / 1024
                    process_info.append((pid, name, priority, cpu_usage, memory_usage))
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                pass

        self.update_table(process_info)

    def update_table(self, process_info):
        for row in reversed(range(self.tableWidget.rowCount())):
            pid_item = self.tableWidget.item(row, 0)
            if pid_item.text() not in [proc[0] for proc in process_info]:
                self.tableWidget.removeRow(row)

        existing_pids = [pid_item.text() for row in range(self.tableWidget.rowCount()) for pid_item in
                         [self.tableWidget.item(row, 0)]]
        for pid, name, priority, cpu_usage, memory_usage in process_info:
            if pid not in existing_pids:
                row_position = self.tableWidget.rowCount()
                self.tableWidget.insertRow(row_position)

                pid_item = QTableWidgetItem()
                pid_item.setData(Qt.DisplayRole, int(pid))
                pid_item.setFlags(pid_item.flags() & ~Qt.ItemIsEditable)
                self.tableWidget.setItem(row_position, 0, pid_item)

                name_item = QTableWidgetItem(name)
                name_item.setFlags(name_item.flags() & ~Qt.ItemIsEditable)
                self.tableWidget.setItem(row_position, 1, name_item)

                priority_combo = QComboBox()
                priority_combo.addItems(PRIORITY_CLASSES.keys())
                priority_combo.setCurrentText(priority)
                priority_combo.activated.connect(lambda index, pid=pid: self.on_priority_changed(index, pid))
                self.tableWidget.setCellWidget(row_position, 2, priority_combo)

                priority_item = QTableWidgetItem(priority)
                priority_item.setData(Qt.DisplayRole, PRIORITY_ORDER[priority])
                priority_item.setFlags(priority_item.flags() & ~Qt.ItemIsEditable)
                self.tableWidget.setItem(row_position, 2, priority_item)

                cpu_usage_item = QTableWidgetItem(cpu_usage)
                cpu_usage_item.setFlags(cpu_usage_item.flags() & ~Qt.ItemIsEditable)
                self.tableWidget.setItem(row_position, 3, cpu_usage_item)

                memory_usage_item = QTableWidgetItem()
                memory_usage_item.setData(Qt.DisplayRole, float(memory_usage))
                memory_usage_item.setFlags(memory_usage_item.flags() & ~Qt.ItemIsEditable)
                self.tableWidget.setItem(row_position, 4, memory_usage_item)

            else:
                row = existing_pids.index(pid)
                priority_combo = self.tableWidget.cellWidget(row, 2)
                priority_combo.setCurrentText(priority)
                self.tableWidget.item(row, 2).setData(Qt.DisplayRole, PRIORITY_ORDER[priority])
                self.tableWidget.item(row, 3).setText(cpu_usage)
                self.tableWidget.item(row, 4).setData(Qt.DisplayRole, float(memory_usage))

        self.process_info = process_info

        if self.current_sort_column is not None:
            self.tableWidget.sortItems(self.current_sort_column, self.current_sort_order)

    def on_priority_changed(self, index, pid):
        priority_name = list(PRIORITY_CLASSES.keys())[index]
        new_priority = PRIORITY_CLASSES[priority_name]
        confirmation = QMessageBox.question(self, 'Confirmation', f'Are you sure you want to change the priority of process with PID {pid} to {priority_name}?\nNote that Changes may cause Instability to the system',
                                            QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        if confirmation == QMessageBox.Yes:
            try:
                process = psutil.Process(int(pid))
                process.nice(new_priority)
                QMessageBox.question(self, 'Changing Priority', f"Changed priority of process with PID {pid} to {priority_name}",
                                     QMessageBox.Ok | QMessageBox.Ok)
                self.update_process_info()
            except (psutil.NoSuchProcess, psutil.AccessDenied) as e:
                QMessageBox.question(self, 'Changing Priority', f"Error changing priority: {e}",
                                     QMessageBox.Ok | QMessageBox.Ok)

    def sort_table(self, column):
        if self.current_sort_column == column:
            self.current_sort_order = Qt.DescendingOrder if self.current_sort_order == Qt.AscendingOrder else Qt.AscendingOrder
        else:
            self.current_sort_column = column
            self.current_sort_order = Qt.AscendingOrder
        self.tableWidget.sortItems(column, self.current_sort_order)

    def closeEvent(self, event):
        reply = QMessageBox.question(self, 'Exit Confirmation', 'Are you sure you want to exit?',
                                     QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        if reply == QMessageBox.Yes:
            event.accept()
        else:
            event.ignore()

    def setup_selection_change(self):
        self.tableWidget.itemSelectionChanged.connect(self.handle_selection_change)

    def handle_selection_change(self):
        selected_indexes = self.tableWidget.selectionModel().selectedIndexes()
        if any(index.column() in [0, 1] for index in selected_indexes):
            self.pushButton_2.setEnabled(True)
        else:
            self.pushButton_2.setEnabled(False)

    def end_selected_process(self):
        selected_indexes = self.tableWidget.selectionModel().selectedIndexes()
        if any(index.column() in [0, 1] for index in selected_indexes):
            row = selected_indexes[0].row()
            pid_item = self.tableWidget.item(row, 0)
            pid = int(pid_item.text())
            try:
                process = psutil.Process(pid)
                process.terminate()
                QMessageBox.question(self, 'Process Termination', 'The Process terminated sucessfully!',
                                     QMessageBox.Ok | QMessageBox.Ok)
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess) as e:
                QMessageBox.question(self, 'Process Termination', 'The process cannot be terminated!',
                                     QMessageBox.Ok | QMessageBox.Ok)

    def show_memory_usage_graph(self):
        graph_dialog = QDialog(self)
        graph_dialog.setWindowTitle("Memory Usage Graph")
        layout = QVBoxLayout()
        layout.addWidget(self.graph_widget)
        graph_dialog.setLayout(layout)
        graph_dialog.setFixedSize(600, 400)  
        graph_dialog.setModal(False)
        graph_dialog.show()
        self.graph_timer.start(1000)

    def update_graph(self):
        self.graph_data = np.roll(self.graph_data, -1)
        self.graph_data[-1] = psutil.virtual_memory().percent
        self.graph_curve.setData(self.graph_data)

        for item in self.graph_widget.items():
            if isinstance(item, pg.TextItem):
                self.graph_widget.removeItem(item)

        current_value = self.graph_data[-1]

        text_item = pg.TextItem(text=f'Current Value: {current_value:.2f}', color=(0, 0, 0), anchor=(1, 1))
        text_item.setPos(len(self.graph_data) - 1, current_value)
        self.graph_widget.addItem(text_item)

        QTimer.singleShot(2000, lambda: self.graph_widget.removeItem(text_item))


if __name__ == '__main__':
    app = QApplication(sys.argv)
    demo = AppDemo()
    demo.show()
    sys.exit(app.exec_())
