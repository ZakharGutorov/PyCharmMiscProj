from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame, QTableWidget, QTableWidgetItem,
    QGroupBox, QPushButton, QTextEdit, QHeaderView, QFormLayout, QComboBox, QSpinBox,
    QCheckBox, QProgressDialog, QTabWidget, QApplication, QMessageBox
)
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QFont, QColor
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure
import matplotlib.dates as mdates
import random
import os
import tempfile
import platform
import subprocess
import psutil
from datetime import datetime
from reports import generate_pdf_report, generate_xml_report, generate_excel_report
from utils import run_disk_cleanup, check_disk_health, run_ping_test, save_settings


class DashboardTab(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent = parent
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)

        # Overview group
        overview_group = QGroupBox("System Overview")
        overview_layout = QHBoxLayout(overview_group)
        self.cpu_overview = QLabel("<b>CPU:</b> Loading...")
        self.memory_overview = QLabel("<b>Memory:</b> Loading...")
        self.disk_overview = QLabel("<b>Disk:</b> Loading...")
        self.gpu_overview = QLabel("<b>GPU:</b> Loading...")
        overview_layout.addWidget(self.cpu_overview)
        overview_layout.addWidget(self.memory_overview)
        overview_layout.addWidget(self.disk_overview)
        overview_layout.addWidget(self.gpu_overview)
        layout.addWidget(overview_group)

        # Charts
        charts_layout = QHBoxLayout()
        self.cpu_fig = Figure(figsize=(5, 3), dpi=100)
        self.cpu_canvas = FigureCanvas(self.cpu_fig)
        self.gpu_fig = Figure(figsize=(5, 3), dpi=100)
        self.gpu_canvas = FigureCanvas(self.gpu_fig)
        charts_layout.addWidget(self.cpu_canvas)
        charts_layout.addWidget(self.gpu_canvas)
        layout.addLayout(charts_layout)

        # CPU chart setup
        self.cpu_ax = self.cpu_fig.add_subplot(111)
        self.cpu_usage_line, = self.cpu_ax.plot([], [], color='tab:blue', label='Usage')
        self.cpu_ax2 = self.cpu_ax.twinx()
        self.cpu_temp_line, = self.cpu_ax2.plot([], [], color='tab:red', label='Temp')
        self.setup_chart_axes(self.cpu_ax, self.cpu_ax2, 'CPU (%)', 'Temp (°C)', "CPU Monitor")

        # GPU chart setup
        self.gpu_ax = self.gpu_fig.add_subplot(111)
        self.gpu_load_line, = self.gpu_ax.plot([], [], color='tab:green', label='Load')
        self.gpu_ax2 = self.gpu_ax.twinx()
        self.gpu_temp_line, = self.gpu_ax2.plot([], [], color='tab:orange', label='Temp')
        self.setup_chart_axes(self.gpu_ax, self.gpu_ax2, 'GPU (%)', 'Temp (°C)', "GPU Monitor")

        # Alerts
        alerts_group = QGroupBox("Recent Alerts")
        alerts_layout = QVBoxLayout(alerts_group)
        self.alerts_table = QTableWidget(5, 3)
        self.alerts_table.setHorizontalHeaderLabels(["Time", "Component", "Message"])
        self.alerts_table.horizontalHeader().setStretchLastSection(True)
        self.alerts_table.setEditTriggers(QTableWidget.NoEditTriggers)
        alerts_layout.addWidget(self.alerts_table)
        layout.addWidget(alerts_group)

    def setup_chart_axes(self, ax1, ax2, label1, label2, title):
        ax1.set_title(title)
        ax1.set_ylabel(label1, color=ax1.get_lines()[0].get_color())
        ax1.tick_params(axis='y', labelcolor=ax1.get_lines()[0].get_color())
        ax1.set_ylim(0, 105)
        ax1.grid(True, linestyle='--', alpha=0.6)
        ax2.set_ylabel(label2, color=ax2.get_lines()[0].get_color())
        ax2.tick_params(axis='y', labelcolor=ax2.get_lines()[0].get_color())
        ax2.set_ylim(20, 105)
        ax1.xaxis.set_major_formatter(mdates.DateFormatter('%H:%M:%S'))
        ax1.figure.tight_layout()

    def update_data(self, historical_data, time_points, cpu_usage_points, cpu_temp_points,
                    gpu_load_points, gpu_temp_points, mem_usage_points, alert_history):
        # Update overview
        data = historical_data[-1]
        cpu_data = data.get('cpu', {})
        cpu_percent = cpu_data.get('percent', 0)
        cpu_temp = cpu_data.get('temperature')
        temp_str = f"{cpu_temp:.0f}°C" if cpu_temp is not None else "N/A"
        self.cpu_overview.setText(f"<b>CPU:</b> {cpu_percent:.1f}% | {temp_str}")

        mem_data = data.get('memory', {}).get('virtual', {})
        if mem_data:
            self.memory_overview.setText(
                f"<b>Memory:</b> {mem_data.get('percent', 0)}% ({mem_data.get('used', 0) / 1e9:.1f}/{mem_data.get('total', 0) / 1e9:.1f} GB)")

        disk_usage_map = data.get('disk', {})
        root_disk = os.path.abspath(os.sep)
        disk_usage = disk_usage_map.get(root_disk.replace(":", "_drive"))
        if disk_usage:
            self.disk_overview.setText(f"<b>Disk ({root_disk}):</b> {disk_usage['percent']}%")

        gpu_info = data.get('gpu', {})
        load_str = f"{gpu_info.get('load', 0):.0f}%" if gpu_info and 'load' in gpu_info and gpu_info[
            'load'] is not None else "N/A"
        temp_str = f"{gpu_info.get('temp', 0):.0f}°C" if gpu_info and 'temp' in gpu_info and gpu_info[
            'temp'] is not None else "N/A"
        self.gpu_overview.setText(f"<b>GPU:</b> {load_str} | {temp_str}")

        # Update charts
        self.update_chart(self.cpu_usage_line, time_points, cpu_usage_points,
                          self.cpu_temp_line, time_points, cpu_temp_points,
                          self.cpu_ax, self.cpu_canvas)

        self.update_chart(self.gpu_load_line, time_points, gpu_load_points,
                          self.gpu_temp_line, time_points, gpu_temp_points,
                          self.gpu_ax, self.gpu_canvas)

        # Update alerts
        self.alerts_table.clearContents()
        self.alerts_table.setRowCount(min(5, len(alert_history)))
        for i, alert in enumerate(list(alert_history)[:5]):
            self.alerts_table.setItem(i, 0, QTableWidgetItem(alert['time']))
            self.alerts_table.setItem(i, 1, QTableWidgetItem(alert['component']))
            self.alerts_table.setItem(i, 2, QTableWidgetItem(alert['message']))

    def update_chart(self, line1, x1_data, y1_data, line2, x2_data, y2_data, ax, canvas):
        valid_points1 = [(t, v) for t, v in zip(x1_data, y1_data) if v is not None]
        if valid_points1:
            line1.set_data(*zip(*valid_points1))
        else:
            line1.set_data([], [])

        valid_points2 = [(t, v) for t, v in zip(x2_data, y2_data) if v is not None]
        if valid_points2:
            line2.set_data(*zip(*valid_points2))
        else:
            line2.set_data([], [])

        if x1_data:
            ax.set_xlim(x1_data[0], x1_data[-1])
            canvas.draw_idle()


class CpuTab(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent = parent
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        self.fig = Figure(figsize=(10, 5), dpi=100)
        self.canvas = FigureCanvas(self.fig)
        layout.addWidget(self.canvas)

        self.ax = self.fig.add_subplot(111)
        self.usage_line, = self.ax.plot([], [], color='tab:blue', label='Usage')
        self.ax2 = self.ax.twinx()
        self.temp_line, = self.ax2.plot([], [], color='tab:red', label='Temp')

        # Chart setup
        self.ax.set_title("CPU Full History")
        self.ax.set_ylabel('CPU (%)', color='tab:blue')
        self.ax.tick_params(axis='y', labelcolor='tab:blue')
        self.ax.set_ylim(0, 105)
        self.ax.grid(True, linestyle='--', alpha=0.6)
        self.ax2.set_ylabel('Temp (°C)', color='tab:red')
        self.ax2.tick_params(axis='y', labelcolor='tab:red')
        self.ax2.set_ylim(20, 105)
        self.ax.xaxis.set_major_formatter(mdates.DateFormatter('%H:%M:%S'))
        self.fig.tight_layout()

        self.table = QTableWidget(1, 4)
        self.table.setHorizontalHeaderLabels(["Cores (P/L)", "Current Speed", "Max Speed", "Usage"])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        layout.addWidget(self.table)

    def update_data(self, historical_data, time_points, cpu_usage_points, cpu_temp_points,
                    *args, **kwargs):
        # Update chart
        valid_usage = [(t, v) for t, v in zip(time_points, cpu_usage_points) if v is not None]
        valid_temp = [(t, v) for t, v in zip(time_points, cpu_temp_points) if v is not None]

        if valid_usage:
            self.usage_line.set_data(*zip(*valid_usage))
        if valid_temp:
            self.temp_line.set_data(*zip(*valid_temp))

        if time_points:
            self.ax.set_xlim(time_points[0], time_points[-1])
            self.canvas.draw_idle()

        # Update table
        data = historical_data[-1].get('cpu', {})
        freq = data.get('frequency', {})
        self.table.setItem(0, 0, QTableWidgetItem(
            f"{data.get('cores_physical', 'N/A')}/{data.get('cores_logical', 'N/A')}"))
        self.table.setItem(0, 1, QTableWidgetItem(f"{freq.get('current', 0):.2f} MHz" if freq else "N/A"))
        self.table.setItem(0, 2, QTableWidgetItem(f"{freq.get('max', 0):.2f} MHz" if freq else "N/A"))
        self.table.setItem(0, 3, QTableWidgetItem(f"{data.get('percent', 0):.1f}%"))


# Аналогичные классы для MemoryTab, DiskTab, GpuTab, NetworkTab с соответствующим кодом
class MemoryTab(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent = parent
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)

        # Chart
        self.fig = Figure(figsize=(10, 5), dpi=100)
        self.canvas = FigureCanvas(self.fig)
        layout.addWidget(self.canvas)

        self.ax = self.fig.add_subplot(111)
        self.usage_line, = self.ax.plot([], [], 'g-', label="RAM Usage (%)")
        self.ax.set_ylim(0, 105)
        self.ax.set_ylabel("Usage (%)")
        self.ax.grid(True)
        self.ax.legend()
        self.ax.set_title("Memory Usage History")
        self.ax.xaxis.set_major_formatter(mdates.DateFormatter('%H:%M:%S'))
        self.fig.tight_layout()

        # Memory table
        self.table = QTableWidget(2, 4)
        self.table.setHorizontalHeaderLabels(["Total", "Used", "Free", "Usage %"])
        self.table.setVerticalHeaderLabels(["RAM", "Swap"])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        layout.addWidget(self.table)

    def update_data(self, historical_data, time_points, *args, **kwargs):
        if not historical_data:
            return

        data = historical_data[-1]
        mem_data = data.get('memory', {})
        mem = mem_data.get('virtual', {})
        swap = mem_data.get('swap', {})

        # Update chart
        valid_points = [(t, v) for t, v in zip(time_points, self.parent.mem_usage_points) if v is not None]
        if valid_points:
            self.usage_line.set_data(*zip(*valid_points))
            if time_points:
                self.ax.set_xlim(time_points[0], time_points[-1])
                self.canvas.draw_idle()

        # Update table
        if mem:
            self.table.setItem(0, 0, QTableWidgetItem(f"{mem.get('total', 0) / 1e9:.2f} GB"))
            self.table.setItem(0, 1, QTableWidgetItem(f"{mem.get('used', 0) / 1e9:.2f} GB"))
            self.table.setItem(0, 2, QTableWidgetItem(f"{mem.get('free', 0) / 1e9:.2f} GB"))
            self.table.setItem(0, 3, QTableWidgetItem(f"{mem.get('percent', 0):.1f}%"))

        if swap:
            self.table.setItem(1, 0, QTableWidgetItem(f"{swap.get('total', 0) / 1e9:.2f} GB"))
            self.table.setItem(1, 1, QTableWidgetItem(f"{swap.get('used', 0) / 1e9:.2f} GB"))
            self.table.setItem(1, 2, QTableWidgetItem(f"{swap.get('free', 0) / 1e9:.2f} GB"))
            self.table.setItem(1, 3, QTableWidgetItem(f"{swap.get('percent', 0):.1f}%"))


class DiskTab(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent = parent
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        self.table = QTableWidget(0, 5)
        self.table.setHorizontalHeaderLabels(["Mountpoint", "Total", "Used", "Free", "Usage %"])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setStretchLastSection(True)
        layout.addWidget(self.table)

    def update_data(self, historical_data, *args, **kwargs):
        if not historical_data:
            return

        disk_usages = historical_data[-1].get('disk', {})
        self.table.setRowCount(len(disk_usages))

        for i, (mount, usage) in enumerate(disk_usages.items()):
            # Format mountpoint for display
            display_mount = mount.replace('_drive', ':')

            self.table.setItem(i, 0, QTableWidgetItem(display_mount))
            self.table.setItem(i, 1, QTableWidgetItem(f"{usage.get('total', 0) / 1e9:.2f} GB"))
            self.table.setItem(i, 2, QTableWidgetItem(f"{usage.get('used', 0) / 1e9:.2f} GB"))
            self.table.setItem(i, 3, QTableWidgetItem(f"{usage.get('free', 0) / 1e9:.2f} GB"))
            self.table.setItem(i, 4, QTableWidgetItem(f"{usage.get('percent', 0):.1f}%"))


class GpuTab(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent = parent
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)

        # Chart
        self.fig = Figure(figsize=(10, 5), dpi=100)
        self.canvas = FigureCanvas(self.fig)
        layout.addWidget(self.canvas)

        self.ax = self.fig.add_subplot(111)
        self.load_line, = self.ax.plot([], [], color='tab:green', label='Load')
        self.ax2 = self.ax.twinx()
        self.temp_line, = self.ax2.plot([], [], color='tab:orange', label='Temp')

        # Chart setup
        self.ax.set_title("GPU Full History")
        self.ax.set_ylabel('GPU Load (%)', color='tab:green')
        self.ax.tick_params(axis='y', labelcolor='tab:green')
        self.ax.set_ylim(0, 105)
        self.ax.grid(True, linestyle='--', alpha=0.6)
        self.ax2.set_ylabel('Temp (°C)', color='tab:orange')
        self.ax2.tick_params(axis='y', labelcolor='tab:orange')
        self.ax2.set_ylim(20, 105)
        self.ax.xaxis.set_major_formatter(mdates.DateFormatter('%H:%M:%S'))
        self.fig.tight_layout()

        # GPU info table
        self.table = QTableWidget(0, 2)
        self.table.setHorizontalHeaderLabels(["Metric", "Value"])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        layout.addWidget(self.table)

    def update_data(self, historical_data, time_points, *args, gpu_load_points, gpu_temp_points, **kwargs):
        if not historical_data:
            return

        # Update chart
        valid_load = [(t, v) for t, v in zip(time_points, gpu_load_points) if v is not None]
        valid_temp = [(t, v) for t, v in zip(time_points, gpu_temp_points) if v is not None]

        if valid_load:
            self.load_line.set_data(*zip(*valid_load))
        if valid_temp:
            self.temp_line.set_data(*zip(*valid_temp))

        if time_points:
            self.ax.set_xlim(time_points[0], time_points[-1])
            self.canvas.draw_idle()

        # Update table
        gpu_info = historical_data[-1].get('gpu', {})
        self.table.setRowCount(len(gpu_info))

        for i, (key, value) in enumerate(gpu_info.items()):
            display_key = key.replace('_', ' ').title()
            self.table.setItem(i, 0, QTableWidgetItem(display_key))

            # Format values appropriately
            if 'mem' in key and value > 1000:  # Memory values
                display_value = f"{value / 1024:.1f} GB" if value > 1024 * 100 else f"{value:.0f} MB"
            elif 'temp' in key or 'load' in key:  # Temperature or load
                display_value = f"{value:.1f}°C" if 'temp' in key else f"{value:.1f}%"
            else:
                display_value = str(value)

            self.table.setItem(i, 1, QTableWidgetItem(display_value))

        # If no GPU data available
        if not gpu_info:
            self.table.setRowCount(1)
            self.table.setItem(0, 0, QTableWidgetItem("GPU Information"))
            self.table.setItem(0, 1, QTableWidgetItem("Not available"))


class NetworkTab(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent = parent
        self.last_net_io = None
        self.last_update_time = None
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        self.table = QTableWidget(0, 5)
        self.table.setHorizontalHeaderLabels(
            ["Interface", "Sent (Total)", "Recv (Total)", "Sent (Rate)", "Recv (Rate)"]
        )
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setStretchLastSection(True)
        layout.addWidget(self.table)

    def update_data(self, historical_data, *args, **kwargs):
        if not historical_data:
            return

        current_data = historical_data[-1]
        current_time = current_data['timestamp']
        current_io = current_data.get('network', {})

        if not current_io:
            self.table.setRowCount(0)
            return

        self.table.setRowCount(len(current_io))

        for i, (iface, counters) in enumerate(current_io.items()):
            # Format interface name
            display_iface = iface.replace('_', ' ').title()

            # Format total values
            sent_total = counters.get('bytes_sent', 0)
            recv_total = counters.get('bytes_recv', 0)
            sent_total_str = self.format_bytes(sent_total)
            recv_total_str = self.format_bytes(recv_total)

            # Calculate rates
            sent_rate_str, recv_rate_str = "N/A", "N/A"
            if self.last_net_io and self.last_update_time:
                time_delta = (current_time - self.last_update_time).total_seconds()
                if time_delta > 0 and iface in self.last_net_io:
                    last_counters = self.last_net_io[iface]
                    sent_rate = (sent_total - last_counters.get('bytes_sent', 0)) / time_delta
                    recv_rate = (recv_total - last_counters.get('bytes_recv', 0)) / time_delta
                    sent_rate_str = self.format_bytes(sent_rate) + "/s"
                    recv_rate_str = self.format_bytes(recv_rate) + "/s"

            # Add items to table
            self.table.setItem(i, 0, QTableWidgetItem(display_iface))
            self.table.setItem(i, 1, QTableWidgetItem(sent_total_str))
            self.table.setItem(i, 2, QTableWidgetItem(recv_total_str))
            self.table.setItem(i, 3, QTableWidgetItem(sent_rate_str))
            self.table.setItem(i, 4, QTableWidgetItem(recv_rate_str))

        # Save for next update
        self.last_net_io = current_io
        self.last_update_time = current_time

    def format_bytes(self, size):
        """Convert bytes to human-readable format"""
        for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
            if size < 1024.0:
                if unit == 'B':
                    return f"{size:.0f} {unit}"
                return f"{size:.2f} {unit}"
            size /= 1024.0
        return f"{size:.2f} PB"


class MultiDeviceTab(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent = parent
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)

        # Button layout
        button_layout = QHBoxLayout()
        discover_btn = QPushButton("Discover Devices")
        discover_btn.clicked.connect(self.parent.discover_network_devices)
        button_layout.addWidget(discover_btn)
        button_layout.addStretch()
        layout.addLayout(button_layout)

        # Devices table
        self.table = QTableWidget(0, 5)
        self.table.setHorizontalHeaderLabels(["Device Name", "IP Address", "Status", "CPU %", "RAM %"])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.setSortingEnabled(True)
        layout.addWidget(self.table)

    def update_devices(self, devices):
        """Update the table with device information"""
        self.table.setSortingEnabled(False)
        self.table.setRowCount(len(devices))

        for i, device in enumerate(devices):
            self.table.setItem(i, 0, QTableWidgetItem(device['name']))
            self.table.setItem(i, 1, QTableWidgetItem(device['ip']))

            # Status with color coding
            status_item = QTableWidgetItem(device['status'])
            if device['status'] == 'Online':
                status_item.setForeground(QColor('green'))
            else:
                status_item.setForeground(QColor('red'))
            self.table.setItem(i, 2, status_item)

            # CPU usage with color coding
            cpu_item = QTableWidgetItem(f"{device['cpu']}%")
            if device['cpu'] > 80:
                cpu_item.setForeground(QColor('red'))
            elif device['cpu'] > 60:
                cpu_item.setForeground(QColor('orange'))
            self.table.setItem(i, 3, cpu_item)

            # RAM usage with color coding
            ram_item = QTableWidgetItem(f"{device['ram']}%")
            if device['ram'] > 90:
                ram_item.setForeground(QColor('red'))
            elif device['ram'] > 75:
                ram_item.setForeground(QColor('orange'))
            self.table.setItem(i, 4, ram_item)

            self.table.setSortingEnabled(True)





class AlertsTab(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        self.table = QTableWidget(0, 3)
        self.table.setHorizontalHeaderLabels(["Time", "Component", "Message"])
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.setSortingEnabled(True)
        layout.addWidget(self.table)

    def update_data(self, *args, alert_history=None, **kwargs):
        if alert_history is None:
            return

        self.table.setSortingEnabled(False)
        self.table.setRowCount(len(alert_history))
        for i, alert in enumerate(alert_history):
            self.table.setItem(i, 0, QTableWidgetItem(alert['time']))
            self.table.setItem(i, 1, QTableWidgetItem(alert['component']))
            self.table.setItem(i, 2, QTableWidgetItem(alert['message']))
        self.table.setSortingEnabled(True)


class ReportsTab(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent = parent
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        group = QGroupBox("Generate Report")
        form_layout = QFormLayout(group)
        self.report_type_combo = QComboBox()
        self.report_type_combo.addItems(["System Summary"])
        form_layout.addRow("Report Type:", self.report_type_combo)
        group.setLayout(form_layout)

        button_layout = QHBoxLayout()
        pdf_button = QPushButton("Generate PDF")
        pdf_button.clicked.connect(self.generate_pdf)
        xml_button = QPushButton("Generate XML")
        xml_button.clicked.connect(self.generate_xml)
        excel_button = QPushButton("Generate Excel")
        excel_button.clicked.connect(self.generate_excel)
        button_layout.addWidget(pdf_button)
        button_layout.addWidget(xml_button)
        button_layout.addWidget(excel_button)

        layout.addWidget(group)
        layout.addLayout(button_layout)
        layout.addStretch()

    def generate_pdf(self):
        try:
            filename = generate_pdf_report(self.parent.dashboard_tab.cpu_fig, self.parent.dashboard_tab.gpu_fig)
            QMessageBox.information(self, "Success", f"PDF report generated: {filename}")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to generate PDF: {str(e)}")

    def generate_xml(self):
        try:
            filename = generate_xml_report(self.parent.historical_data)
            QMessageBox.information(self, "Success", f"XML report generated: {filename}")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to generate XML: {str(e)}")

    def generate_excel(self):
        try:
            filename = generate_excel_report(self.parent.historical_data)
            QMessageBox.information(self, "Success", f"Excel report generated: {filename}")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to generate Excel: {str(e)}")


class SettingsTab(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent = parent
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        tabs = QTabWidget()

        # General tab
        general_tab = QWidget()
        general_layout = QFormLayout(general_tab)
        self.poll_map = {
            "1 second": 1000, "2 seconds": 2000, "5 seconds": 5000,
            "10 seconds": 10000, "30 seconds": 30000
        }
        self.poll_combo = QComboBox()
        self.poll_combo.addItems(self.poll_map.keys())
        general_layout.addRow("Polling Interval:", self.poll_combo)
        tabs.addTab(general_tab, "General")

        # Alerts tab
        alert_tab = QWidget()
        alert_layout = QFormLayout(alert_tab)
        self.cpu_temp_spin = QSpinBox()
        self.cpu_temp_spin.setRange(50, 120)
        self.cpu_temp_spin.setSuffix(" °C")
        self.gpu_temp_spin = QSpinBox()
        self.gpu_temp_spin.setRange(50, 120)
        self.gpu_temp_spin.setSuffix(" °C")
        self.ram_spin = QSpinBox()
        self.ram_spin.setRange(50, 100)
        self.ram_spin.setSuffix(" %")
        self.disk_spin = QSpinBox()
        self.disk_spin.setRange(50, 100)
        self.disk_spin.setSuffix(" %")
        self.popup_check = QCheckBox("Show popup alerts")
        alert_layout.addRow("CPU Temp Threshold:", self.cpu_temp_spin)
        alert_layout.addRow("GPU Temp Threshold:", self.gpu_temp_spin)
        alert_layout.addRow("RAM Usage Threshold:", self.ram_spin)
        alert_layout.addRow("Disk Usage Threshold:", self.disk_spin)
        alert_layout.addRow(self.popup_check)
        tabs.addTab(alert_tab, "Alerts")

        layout.addWidget(tabs)

        save_btn = QPushButton("Save Settings")
        save_btn.clicked.connect(self.save_settings)
        layout.addWidget(save_btn, 0, Qt.AlignRight)

        self.load_settings()

    def load_settings(self):
        settings = self.parent.settings
        rev_map = {v: k for k, v in self.poll_map.items()}
        self.poll_combo.setCurrentText(rev_map.get(settings.get('poll_interval', 2000), "2 seconds"))
        self.cpu_temp_spin.setValue(settings.get('cpu_temp_threshold', 80))
        self.gpu_temp_spin.setValue(settings.get('gpu_temp_threshold', 85))
        self.ram_spin.setValue(settings.get('ram_threshold', 90))
        self.disk_spin.setValue(settings.get('disk_threshold', 90))
        self.popup_check.setChecked(settings.get('popup_alerts', True))

    def save_settings(self):
        try:
            self.parent.settings['poll_interval'] = self.poll_map[self.poll_combo.currentText()]
            self.parent.settings['cpu_temp_threshold'] = self.cpu_temp_spin.value()
            self.parent.settings['gpu_temp_threshold'] = self.gpu_temp_spin.value()
            self.parent.settings['ram_threshold'] = self.ram_spin.value()
            self.parent.settings['disk_threshold'] = self.disk_spin.value()
            self.parent.settings['popup_alerts'] = self.popup_check.isChecked()

            save_settings(self.parent.settings)
            QMessageBox.information(self, "Success", "Settings saved successfully")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to save settings: {str(e)}")


class ToolsTab(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent = parent
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)

        # Disk cleanup
        disk_group = QGroupBox("Disk Cleanup")
        disk_layout = QVBoxLayout(disk_group)
        self.temp_check = QCheckBox("Delete temporary files")
        self.temp_check.setChecked(True)
        self.cache_check = QCheckBox("Clear system cache")
        disk_layout.addWidget(self.temp_check)
        disk_layout.addWidget(self.cache_check)
        cleanup_btn = QPushButton("Run Cleanup")
        cleanup_btn.clicked.connect(self.run_cleanup)
        disk_layout.addWidget(cleanup_btn)
        layout.addWidget(disk_group)

        # Diagnostics
        diag_group = QGroupBox("Diagnostics")
        diag_layout = QVBoxLayout(diag_group)
        btn_layout = QHBoxLayout()
        disk_btn = QPushButton("Disk Health")
        disk_btn.clicked.connect(self.check_disk)
        ping_btn = QPushButton("Ping Test")
        ping_btn.clicked.connect(self.run_ping)
        speed_btn = QPushButton("Speed Test")
        speed_btn.clicked.connect(self.run_speed_test)
        btn_layout.addWidget(disk_btn)
        btn_layout.addWidget(ping_btn)
        btn_layout.addWidget(speed_btn)
        diag_layout.addLayout(btn_layout)

        self.output = QTextEdit()
        self.output.setReadOnly(True)
        self.output.setFont(QFont("Courier", 9))
        diag_layout.addWidget(self.output)
        layout.addWidget(diag_group)

    def run_cleanup(self):
        paths = []
        if self.temp_check.isChecked():
            paths.append(tempfile.gettempdir())
        if self.cache_check.isChecked():
            if platform.system() == 'Windows':
                paths.append(os.path.join(os.environ['LOCALAPPDATA'], 'Temp'))
            else:
                paths.append(os.path.expanduser('~/.cache'))

        if not paths:
            QMessageBox.warning(self, "Warning", "No cleanup options selected")
            return

        log = run_disk_cleanup(paths)
        self.output.setPlainText("\n".join(log))
        QMessageBox.information(self, "Success", "Cleanup completed")

    def check_disk(self):
        result = check_disk_health()
        self.output.setPlainText(result)

    def run_ping(self):
        result = run_ping_test("8.8.8.8")
        self.output.setPlainText(result)

    def run_speed_test(self):
        if not self.parent.speed_test_thread.isRunning():
            self.output.setPlainText("Starting speed test...")
            self.parent.speed_test_thread.result_ready.connect(self.output.setPlainText)
            self.parent.speed_test_thread.start()
        else:
            QMessageBox.warning(self, "Warning", "Speed test already in progress")