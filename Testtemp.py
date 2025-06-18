import sys
import time
import requests
import json
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QVBoxLayout, QHBoxLayout, QPushButton,
    QWidget, QLabel, QFrame, QMessageBox, QComboBox, QLineEdit, QFormLayout
)
from PyQt5.QtCore import QTimer
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure
from PyQt5.QtCore import QThread, pyqtSignal
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph
import os
import tempfile
from PyQt5.QtCore import QThread, pyqtSignal
from PyQt5.QtWidgets import QMessageBox
from openpyxl import Workbook
from openpyxl.styles import Font, Alignment, Border, Side, PatternFill
from openpyxl.utils import get_column_letter
import threading


class ReportWorker(QThread):
    success = pyqtSignal(str)
    error = pyqtSignal(str)

    def __init__(self, report_data):
        super().__init__()
        self.report_data = report_data

    def run(self):
        try:
            # Создаем новую книгу Excel
            wb = Workbook()
            ws = wb.active
            ws.title = "System Report"

            # Устанавливаем стили
            header_font = Font(bold=True, color="FFFFFF")
            header_fill = PatternFill(start_color="4F81BD", end_color="4F81BD", fill_type="solid")
            cell_alignment = Alignment(horizontal="center", vertical="center")
            thin_border = Border(left=Side(style='thin'),
                                 right=Side(style='thin'),
                                 top=Side(style='thin'),
                                 bottom=Side(style='thin'))

            # Заголовки столбцов
            headers = ["Time", "CPU Usage (%)", "CPU Temp (°C)", "GPU Load (%)", "GPU Temp (°C)"]
            for col_num, header in enumerate(headers, 1):
                cell = ws.cell(row=1, column=col_num, value=header)
                cell.font = header_font
                cell.fill = header_fill
                cell.alignment = cell_alignment
                cell.border = thin_border
                # Автоподбор ширины столбца
                ws.column_dimensions[get_column_letter(col_num)].width = max(len(header) + 2, 12)

            # Заполняем данными
            for row_num, entry in enumerate(self.report_data, 2):
                ws.cell(row=row_num, column=1, value=str(entry.get("time", "-"))).border = thin_border
                ws.cell(row=row_num, column=2, value=entry.get("cpu_usage", "-")).border = thin_border
                ws.cell(row=row_num, column=3, value=entry.get("cpu_temp", "-")).border = thin_border
                ws.cell(row=row_num, column=4, value=entry.get("gpu_load", "-")).border = thin_border
                ws.cell(row=row_num, column=5, value=entry.get("gpu_temp", "-")).border = thin_border

            # Центрируем все ячейки
            for row in ws.iter_rows():
                for cell in row:
                    cell.alignment = cell_alignment

            # Сохранение файла
            filename = os.path.join(tempfile.gettempdir(), "system_monitor_report.xlsx")
            wb.save(filename)
            self.success.emit(filename)

        except Exception as e:
            self.error.emit(f"Failed to generate Excel report: {e}")


def generate_excel_report(self):
    """Генерирует Excel-отчет с использованием openpyxl"""
    if not self.report_data:
        QMessageBox.warning(self, "Warning", "No data available for report")
        return

    # Создаем и запускаем worker
    self.progress_dialog = QProgressDialog("Generating Excel report...", None, 0, 0, self)
    self.progress_dialog.setCancelButton(None)
    self.progress_dialog.setWindowModality(Qt.WindowModal)
    self.progress_dialog.show()

    self.report_worker = ReportWorker(self.report_data)
    self.report_worker.success.connect(self.on_report_success)
    self.report_worker.error.connect(self.on_report_error)
    self.report_worker.start()


def on_report_success(self, filename):
    self.progress_dialog.close()
    QMessageBox.information(self, "Success", f"Excel report generated: {filename}")
    os.startfile(filename)  # Открываем файл напрямую


def on_report_error(self, error_msg):
    self.progress_dialog.close()
    QMessageBox.critical(self, "Error", error_msg)

class SystemMonitorApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("System Monitor")
        self.setGeometry(100, 100, 1000, 600)
        # Пороговые значения для температур
        self.cpu_temp_threshold = 80.0
        self.gpu_temp_threshold = 85.0

        # Список для хранения данных для отчета
        self.report_data = []

        # Главный виджет
        self.main_widget = QWidget()
        self.setCentralWidget(self.main_widget)

        # Основной макет
        self.layout = QHBoxLayout(self.main_widget)

        # Левая панель (меню)
        self.sidebar = QFrame()
        self.sidebar.setFixedWidth(200)
        self.sidebar.setStyleSheet("background-color: #282c34; color: white;")
        self.sidebar_layout = QVBoxLayout(self.sidebar)

        # Кнопки меню
        self.menu_items = [
            ("CPU", self.show_cpu),
            ("Memory", self.show_memory),
            ("Disk", self.show_disk),
            ("GPU", self.show_gpu),
            ("Settings", self.show_settings),
            ("Multi-Device", self.show_multi_device),
            ("Generate Report", self.generate_pdf_report),
        ]

        for text, command in self.menu_items:
            btn = QPushButton(text)
            btn.setStyleSheet("""
                QPushButton {
                    background-color: #282c34;
                    color: white;
                    border: none;
                    padding: 10px;
                    text-align: left;
                }
                QPushButton:hover {
                    background-color: #373b44;
                }
            """)
            btn.clicked.connect(command)
            self.sidebar_layout.addWidget(btn)

        self.sidebar_layout.addStretch()

        # Правая панель (основное окно)
        self.content_frame = QFrame()
        self.content_frame.setStyleSheet("background-color: #ffffff;")
        self.content_layout = QVBoxLayout(self.content_frame)

        # Добавляем левую и правую панели в основной макет
        self.layout.addWidget(self.sidebar)
        self.layout.addWidget(self.content_frame)

        # Начальный экран
        self.current_view = None
        self.show_cpu()

    def generate_pdf_report(self):
        """Генерирует PDF-отчет."""
        if not self.report_data:
            QMessageBox.warning(self, "Warning", "No data available for report")
            return

        # Проверка данных
        try:
            for entry in self.report_data:
                for key in ["time", "cpu_usage", "cpu_temp", "gpu_load", "gpu_temp"]:
                    value = entry.get(key, "-")
                    if not isinstance(value, (str, int, float)):
                        raise ValueError(f"Invalid data type for {key}: {value}")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Invalid data for report: {e}")
            return

        # Создание диалога прогресса
        self.progress_dialog = QProgressDialog("Generating report...", "Cancel", 0, 0, self)
        self.progress_dialog.setWindowTitle("Please wait")
        self.progress_dialog.setWindowModality(Qt.WindowModal)
        self.progress_dialog.show()

        # Запуск генерации отчета в отдельном потоке
        self.report_thread = ReportWorker(self.report_data)
        self.report_thread.success.connect(self.on_report_success)
        self.report_thread.error.connect(self.on_report_error)
        self.report_thread.start()
    def show_settings(self):
        """Отображает вкладку настроек."""
        self.clear_content_frame()
        self.current_view = "Settings"

        # Заголовок
        title_label = QLabel("Settings")
        title_label.setStyleSheet("font-size: 16px; font-weight: bold;")
        self.content_layout.addWidget(title_label)

        # Форма для ввода пороговых значений
        form_layout = QFormLayout()

        # Поле для ввода порогового значения CPU
        self.cpu_temp_input = QLineEdit(str(self.cpu_temp_threshold))
        form_layout.addRow("CPU Temperature Threshold (°C):", self.cpu_temp_input)

        # Поле для ввода порогового значения GPU
        self.gpu_temp_input = QLineEdit(str(self.gpu_temp_threshold))
        form_layout.addRow("GPU Temperature Threshold (°C):", self.gpu_temp_input)

        # Кнопка сохранения настроек
        save_button = QPushButton("Save Settings")
        save_button.setStyleSheet("background-color: #007BFF; color: white;")
        save_button.clicked.connect(self.save_settings)
        form_layout.addWidget(save_button)

        # Добавляем форму в макет
        self.content_layout.addLayout(form_layout)

    def save_settings(self):
        """Сохраняет настройки пороговых значений."""
        try:
            self.cpu_temp_threshold = float(self.cpu_temp_input.text())
            self.gpu_temp_threshold = float(self.gpu_temp_input.text())
            QMessageBox.information(self, "Success", "Settings saved successfully!")
        except ValueError:
            QMessageBox.warning(self, "Error", "Please enter valid numbers for thresholds")

    def clear_content_frame(self):
        """Очищает содержимое правой панели."""
        # Удаляем все виджеты из content_layout
        while self.content_layout.count():
            item = self.content_layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.setParent(None)
                widget.deleteLater()

        # Сбрасываем ссылки на специфичные виджеты
        if hasattr(self, 'device_combo'):
            self.device_combo = None
        if hasattr(self, 'canvas'):
            self.canvas = None

    def check_temperature_thresholds(self, cpu_temp, gpu_temp):
        """Проверяет, превышены ли пороговые значения температур."""
        warnings = []
        if cpu_temp is not None and cpu_temp > self.cpu_temp_threshold:
            warnings.append(f"Warning: CPU temperature ({cpu_temp}°C) exceeds threshold ({self.cpu_temp_threshold}°C)")
        if gpu_temp is not None and gpu_temp > self.gpu_temp_threshold:
            warnings.append(f"Warning: GPU temperature ({gpu_temp}°C) exceeds threshold ({self.gpu_temp_threshold}°C)")

        if warnings:
            QMessageBox.warning(self, "Temperature Warning", "\n".join(warnings))

    def show_cpu(self):
        self.clear_content_frame()
        self.current_view = "CPU"

        # Заголовок
        title_label = QLabel("CPU Usage and Temperature")
        title_label.setStyleSheet("font-size: 16px; font-weight: bold;")
        self.content_layout.addWidget(title_label)

        # График загрузки CPU
        fig = Figure(figsize=(8, 4), dpi=100)
        self.cpu_plot = fig.add_subplot(211)
        self.cpu_plot.set_title("CPU Load Over Time")
        self.cpu_plot.set_xlabel("Time")
        self.cpu_plot.set_ylabel("Usage (%)")

        # График температуры CPU
        self.cpu_temp_plot = fig.add_subplot(212)
        self.cpu_temp_plot.set_title("CPU Temperature Over Time")
        self.cpu_temp_plot.set_xlabel("Time")
        self.cpu_temp_plot.set_ylabel("Temperature (°C)")

        # Настройка межграфового пространства
        fig.subplots_adjust(hspace=0.5)

        # Canvas для графиков
        self.canvas = FigureCanvas(fig)
        self.content_layout.addWidget(self.canvas)

        # Обновление графиков каждые 2 секунды
        self.update_cpu_plot()

    def update_cpu_plot(self):
        try:
            cpu_percent = self.get_cpu_load()
            cpu_temp = self.get_cpu_temperature()
            current_time = time.time()

            # Проверяем пороговые значения
            self.check_temperature_thresholds(cpu_temp, None)

            # Обновляем график загрузки CPU
            lines = self.cpu_plot.get_lines()
            if not lines:
                self.cpu_plot.plot([], [], label="CPU Load")
                lines = self.cpu_plot.get_lines()
            line = lines[0]
            xdata, ydata = line.get_data()
            xdata = list(xdata) + [current_time]
            ydata = list(ydata) + [cpu_percent]
            max_points = 50
            if len(xdata) > max_points:
                xdata = xdata[-max_points:]
                ydata = ydata[-max_points:]
            line.set_data(xdata, ydata)
            self.cpu_plot.relim()
            self.cpu_plot.autoscale_view()

            # Обновляем график температуры CPU
            if cpu_temp is not None:
                temp_lines = self.cpu_temp_plot.get_lines()
                if not temp_lines:
                    self.cpu_temp_plot.plot([], [], label="CPU Temperature", color="orange")
                    temp_lines = self.cpu_temp_plot.get_lines()
                temp_line = temp_lines[0]
                temp_xdata, temp_ydata = temp_line.get_data()
                temp_xdata = list(temp_xdata) + [current_time]
                temp_ydata = list(temp_ydata) + [cpu_temp]
                if len(temp_xdata) > max_points:
                    temp_xdata = temp_xdata[-max_points:]
                    temp_ydata = temp_ydata[-max_points:]
                temp_line.set_data(temp_xdata, temp_ydata)
                self.cpu_temp_plot.relim()
                self.cpu_temp_plot.autoscale_view()

            # Обновляем график
            self.canvas.draw_idle()

            # Сохраняем данные для отчета
            self.report_data.append({
                "time": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(current_time)),
                "cpu_usage": cpu_percent,
                "cpu_temp": cpu_temp
            })
        except Exception as e:
            print(f"Error in update_cpu_plot: {e}")

        # Перезапуск таймера через 2 секунды
        QTimer.singleShot(2000, self.update_cpu_plot)

    def get_cpu_load(self):
        try:
            response = requests.get("http://localhost:8085/data.json", timeout=2)
            response.raise_for_status()
            data = response.json()

            for item in data["Children"]:
                if item["Text"] == "DESKTOP-I8HOS10":
                    for sensor in item["Children"]:
                        if sensor["Text"] == "AMD Ryzen 5 4600H":
                            for category in sensor["Children"]:
                                if category["Text"] == "Load":
                                    for load in category["Children"]:
                                        if "CPU Total" in load["Text"]:
                                            raw_value = load["Value"].split()[0].replace(",", ".")
                                            return float(raw_value)
        except requests.RequestException as e:
            print(f"Error fetching CPU load: {e}")
            return 0.0
        except ValueError as e:
            print(f"Error parsing CPU load data: {e}")
            return 0.0
        except Exception as e:
            print(f"Error getting CPU load: {e}")
        return 0.0

    def get_cpu_temperature(self):
        try:
            response = requests.get("http://localhost:8085/data.json", timeout=2)
            response.raise_for_status()
            data = response.json()

            for item in data["Children"]:
                if item["Text"] == "DESKTOP-I8HOS10":
                    for sensor in item["Children"]:
                        if sensor["Text"] == "AMD Ryzen 5 4600H":
                            for category in sensor["Children"]:
                                if category["Text"] == "Temperatures":
                                    for temp in category["Children"]:
                                        if "CPU Package" in temp["Text"]:
                                            raw_value = temp["Value"].split()[0].replace(",", ".")
                                            return float(raw_value)
        except Exception as e:
            print(f"Error getting CPU temperature: {e}")
        return None

    def show_memory(self):
        self.clear_content_frame()
        self.current_view = "Memory"

        # Заголовок
        title_label = QLabel("Memory Usage")
        title_label.setStyleSheet("font-size: 16px; font-weight: bold;")
        self.content_layout.addWidget(title_label)

        # Информация о памяти
        memory_usage = self.get_memory_usage()
        memory_info = f"Memory Usage: {memory_usage}%"
        memory_label = QLabel(memory_info)
        memory_label.setStyleSheet("font-size: 14px;")
        self.content_layout.addWidget(memory_label)

        # График использования памяти
        fig = Figure(figsize=(8, 4), dpi=100)
        self.memory_plot = fig.add_subplot(111)
        self.memory_plot.set_title("Memory Usage Over Time")
        self.memory_plot.set_xlabel("Time")
        self.memory_plot.set_ylabel("Usage (%)")

        # Canvas для графика
        self.canvas = FigureCanvas(fig)
        self.content_layout.addWidget(self.canvas)

        # Обновление графика каждые 2 секунды
        self.update_memory_plot()

    def update_memory_plot(self):
        try:
            memory_usage = self.get_memory_usage()
            current_time = time.time()

            # Обновляем график
            lines = self.memory_plot.get_lines()
            if not lines:
                self.memory_plot.plot([], [], label="Memory Usage")
                lines = self.memory_plot.get_lines()
            line = lines[0]
            xdata, ydata = line.get_data()
            xdata = list(xdata) + [current_time]
            ydata = list(ydata) + [memory_usage]
            max_points = 50
            if len(xdata) > max_points:
                xdata = xdata[-max_points:]
                ydata = ydata[-max_points:]
            line.set_data(xdata, ydata)
            self.memory_plot.relim()
            self.memory_plot.autoscale_view()
            self.canvas.draw_idle()

            # Сохраняем данные для отчета
            self.report_data.append({
                "time": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(current_time)),
                "memory_usage": memory_usage
            })
        except Exception as e:
            print(f"Error in update_memory_plot: {e}")

        # Перезапуск таймера через 2 секунды
        QTimer.singleShot(2000, self.update_memory_plot)

    def get_memory_usage(self):
        try:
            response = requests.get("http://localhost:8085/data.json", timeout=2)
            response.raise_for_status()
            data = response.json()

            for item in data["Children"]:
                if item["Text"] == "DESKTOP-I8HOS10":
                    for sensor in item["Children"]:
                        if sensor["Text"] == "Generic Memory":
                            for category in sensor["Children"]:
                                if category["Text"] == "Load":
                                    for load in category["Children"]:
                                        if "Memory" in load["Text"]:
                                            raw_value = load["Value"].split()[0].replace(",", ".")
                                            return float(raw_value)
        except Exception as e:
            print(f"Error getting memory usage: {e}")
        return 0.0

    def show_disk(self):
        self.clear_content_frame()
        self.current_view = "Disk"

        # Заголовок
        title_label = QLabel("Disk Usage")
        title_label.setStyleSheet("font-size: 16px; font-weight: bold;")
        self.content_layout.addWidget(title_label)

        # Информация о диске
        disk_usage = self.get_disk_usage()
        disk_info = f"Disk Usage: {disk_usage}%"
        disk_label = QLabel(disk_info)
        disk_label.setStyleSheet("font-size: 14px;")
        self.content_layout.addWidget(disk_label)

        # График использования диска
        fig = Figure(figsize=(8, 4), dpi=100)
        self.disk_plot = fig.add_subplot(111)
        self.disk_plot.set_title("Disk Usage Over Time")
        self.disk_plot.set_xlabel("Time")
        self.disk_plot.set_ylabel("Usage (%)")

        # Canvas для графика
        self.canvas = FigureCanvas(fig)
        self.content_layout.addWidget(self.canvas)

        # Обновление графика каждые 2 секунды
        self.update_disk_plot()

    def update_disk_plot(self):
        try:
            disk_usage = self.get_disk_usage()
            current_time = time.time()

            # Обновляем график
            lines = self.disk_plot.get_lines()
            if not lines:
                self.disk_plot.plot([], [], label="Disk Usage")
                lines = self.disk_plot.get_lines()
            line = lines[0]
            xdata, ydata = line.get_data()
            xdata = list(xdata) + [current_time]
            ydata = list(ydata) + [disk_usage]
            max_points = 50
            if len(xdata) > max_points:
                xdata = xdata[-max_points:]
                ydata = ydata[-max_points:]
            line.set_data(xdata, ydata)
            self.disk_plot.relim()
            self.disk_plot.autoscale_view()
            self.canvas.draw_idle()

            # Сохраняем данные для отчета
            self.report_data.append({
                "time": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(current_time)),
                "disk_usage": disk_usage
            })
        except Exception as e:
            print(f"Error in update_disk_plot: {e}")

        # Перезапуск таймера через 2 секунды
        QTimer.singleShot(2000, self.update_disk_plot)

    def get_disk_usage(self):
        try:
            response = requests.get("http://localhost:8085/data.json", timeout=2)
            response.raise_for_status()
            data = response.json()

            for item in data["Children"]:
                if item["Text"] == "DESKTOP-I8HOS10":
                    for sensor in item["Children"]:
                        if sensor["Text"] == "Generic Hard Disk":
                            for category in sensor["Children"]:
                                if category["Text"] == "Load":
                                    for load in category["Children"]:
                                        if "Used Space" in load["Text"]:
                                            raw_value = load["Value"].split()[0].replace(",", ".")
                                            return float(raw_value)
        except Exception as e:
            print(f"Error getting disk usage: {e}")
        return 0.0

    def show_gpu(self):
        self.clear_content_frame()
        self.current_view = "GPU"

        # Заголовок
        title_label = QLabel("GPU Usage and Temperature")
        title_label.setStyleSheet("font-size: 16px; font-weight: bold;")
        self.content_layout.addWidget(title_label)

        # График загрузки GPU
        fig = Figure(figsize=(8, 4), dpi=100)
        self.gpu_load_plot = fig.add_subplot(211)
        self.gpu_load_plot.set_title("GPU Load Over Time")
        self.gpu_load_plot.set_xlabel("Time")
        self.gpu_load_plot.set_ylabel("Load (%)")

        # График температуры GPU
        self.gpu_temp_plot = fig.add_subplot(212)
        self.gpu_temp_plot.set_title("GPU Temperature Over Time")
        self.gpu_temp_plot.set_xlabel("Time")
        self.gpu_temp_plot.set_ylabel("Temperature (°C)")

        # Настройка межграфового пространства
        fig.subplots_adjust(hspace=0.5)

        # Canvas для графиков
        self.canvas = FigureCanvas(fig)
        self.content_layout.addWidget(self.canvas)

        # Обновление графиков каждые 2 секунды
        self.update_gpu_plot()

    def update_gpu_plot(self):
        try:
            gpu_load = self.get_gpu_load()
            gpu_temp = self.get_gpu_temperature()
            current_time = time.time()

            # Проверяем пороговые значения
            self.check_temperature_thresholds(None, gpu_temp)

            # Обновляем график загрузки GPU
            lines = self.gpu_load_plot.get_lines()
            if not lines:
                self.gpu_load_plot.plot([], [], label="GPU Load")
                lines = self.gpu_load_plot.get_lines()
            line = lines[0]
            xdata, ydata = line.get_data()
            xdata = list(xdata) + [current_time]
            ydata = list(ydata) + [gpu_load]
            max_points = 50
            if len(xdata) > max_points:
                xdata = xdata[-max_points:]
                ydata = ydata[-max_points:]
            line.set_data(xdata, ydata)
            self.gpu_load_plot.relim()
            self.gpu_load_plot.autoscale_view()

            # Обновляем график температуры GPU
            if gpu_temp is not None:
                temp_lines = self.gpu_temp_plot.get_lines()
                if not temp_lines:
                    self.gpu_temp_plot.plot([], [], label="GPU Temperature", color="orange")
                    temp_lines = self.gpu_temp_plot.get_lines()
                temp_line = temp_lines[0]
                temp_xdata, temp_ydata = temp_line.get_data()
                temp_xdata = list(temp_xdata) + [current_time]
                temp_ydata = list(temp_ydata) + [gpu_temp]
                if len(temp_xdata) > max_points:
                    temp_xdata = temp_xdata[-max_points:]
                    temp_ydata = temp_ydata[-max_points:]
                temp_line.set_data(temp_xdata, temp_ydata)
                self.gpu_temp_plot.relim()
                self.gpu_temp_plot.autoscale_view()

            # Обновляем график
            self.canvas.draw_idle()

            # Сохраняем данные для отчета
            self.report_data.append({
                "time": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(current_time)),
                "gpu_load": gpu_load,
                "gpu_temp": gpu_temp
            })
        except Exception as e:
            print(f"Error in update_gpu_plot: {e}")

        # Перезапуск таймера через 2 секунды
        QTimer.singleShot(2000, self.update_gpu_plot)

    def get_gpu_load(self):
        try:
            response = requests.get("http://localhost:8085/data.json", timeout=2)
            response.raise_for_status()
            data = response.json()

            for item in data["Children"]:
                if item["Text"] == "DESKTOP-I8HOS10":
                    for sensor in item["Children"]:
                        if sensor["Text"] == "AMD Radeon Graphics":
                            for category in sensor["Children"]:
                                if category["Text"] == "Load":
                                    for load in category["Children"]:
                                        if "GPU Core" in load["Text"]:
                                            raw_value = load["Value"].split()[0].replace(",", ".")
                                            return float(raw_value)
        except requests.RequestException as e:
            print(f"Error fetching CPU load: {e}")
            return 0.0
        except ValueError as e:
            print(f"Error parsing CPU load data: {e}")
            return 0.0
        except Exception as e:
            print(f"Error getting GPU load: {e}")
        return 0.0

    def get_gpu_temperature(self):
        try:
            response = requests.get("http://localhost:8085/data.json", timeout=2)
            response.raise_for_status()
            data = response.json()

            for item in data["Children"]:
                if item["Text"] == "DESKTOP-I8HOS10":
                    for sensor in item["Children"]:
                        if sensor["Text"] == "AMD Radeon Graphics":
                            for category in sensor["Children"]:
                                if category["Text"] == "Temperatures":
                                    for temp in category["Children"]:
                                        if "GPU Core" in temp["Text"]:
                                            raw_value = temp["Value"].split()[0].replace(",", ".")
                                            return float(raw_value)
        except Exception as e:
            print(f"Error getting GPU temperature: {e}")
        return None

    def show_multi_device(self):
        self.clear_content_frame()
        self.current_view = "Multi-Device"

        # Останавливаем предыдущий таймер
        if hasattr(self, 'multi_timer'):
            self.multi_timer.stop()

        # Заголовок
        title_label = QLabel("Multi-Device CPU Monitoring")
        title_label.setStyleSheet("font-size: 16px; font-weight: bold;")
        self.content_layout.addWidget(title_label)

        # Выбор устройств
        self.device_combo = QComboBox()
        self.device_combo.addItems(["DESKTOP-I8HOS10", "1DESKTOP-COVAYN-1", "LAPTOP-COVAYN-2"])  # Пример устройств
        self.content_layout.addWidget(self.device_combo)

        # Создаем фигуру и график
        self.multi_fig = Figure(figsize=(8, 4), dpi=100)
        self.multi_ax = self.multi_fig.add_subplot(111)
        self.multi_ax.set_title("CPU Load Across Devices")
        self.multi_ax.set_xlabel("Time")
        self.multi_ax.set_ylabel("CPU Usage (%)")
        self.multi_ax.grid(True)

        # Инициализация данных для устройств
        self.device_lines = {}  # Для хранения линий графиков
        self.device_data = {}  # Для хранения данных

        # Цвета для разных устройств
        self.device_colors = {
            "DESKTOP-I8HOS10": "blue",
            "1DESKTOP-COVAYN-1": "green",
            "LAPTOP-COVAYN-2": "red"
        }

        # Canvas для отображения графика
        self.multi_canvas = FigureCanvas(self.multi_fig)
        self.content_layout.addWidget(self.multi_canvas)

        # Кнопка обновления
        refresh_btn = QPushButton("Refresh Data")
        refresh_btn.clicked.connect(self.update_multi_device_data)
        self.content_layout.addWidget(refresh_btn)

        # Запускаем таймер для автообновления
        self.multi_timer = QTimer()
        self.multi_timer.timeout.connect(self.update_multi_device_data)
        self.multi_timer.start(2000)  # Обновление каждые 2 секунды

    def update_multi_device_data(self):
        if not hasattr(self, 'multi_ax') or not hasattr(self, 'device_combo'):
            return

        try:
            current_time = time.time()
            self.multi_ax.clear()

            # Для каждого устройства
            for i in range(self.device_combo.count()):
                device_name = self.device_combo.itemText(i)

                # Инициализация данных устройства
                if device_name not in self.device_data:
                    self.device_data[device_name] = {'time': [], 'usage': []}

                # Получаем загрузку CPU
                cpu_usage = self.get_device_cpu_usage(device_name)

                # Если не получили данные - пропускаем устройство
                if cpu_usage is None:
                    print(f"No data for device: {device_name}")
                    continue

                # Добавляем новые данные
                self.device_data[device_name]['time'].append(current_time)
                self.device_data[device_name]['usage'].append(cpu_usage)

                # Ограничиваем историю
                max_points = 30
                if len(self.device_data[device_name]['time']) > max_points:
                    self.device_data[device_name]['time'] = self.device_data[device_name]['time'][-max_points:]
                    self.device_data[device_name]['usage'] = self.device_data[device_name]['usage'][-max_points:]

                # Рисуем линию
                color = self.device_colors.get(device_name, "purple")
                line, = self.multi_ax.plot(
                    self.device_data[device_name]['time'],
                    self.device_data[device_name]['usage'],
                    label=f"{device_name} ({cpu_usage:.1f}%)",
                    color=color,
                    linewidth=2
                )
                self.device_lines[device_name] = line

            # Настройки графика
            self.configure_multi_device_plot()
            self.multi_canvas.draw_idle()

        except Exception as e:
            print(f"Error in update: {str(e)}")

    def get_device_cpu_usage(self, device_name):
        """Получаем данные CPU для указанного устройства"""
        try:
            # Для тестовых устройств
            if device_name.startswith("DESKTOP-"or"LAPTOP-"):
                import random
                return random.uniform(10, 80)

            # Для реального устройства
            response = requests.get("http://localhost:8085/data.json", timeout=2)
            response.raise_for_status()
            data = response.json()


            def find_value(data, keys):
                """Рекурсивно ищет значение по цепочке ключей"""
                if isinstance(data, dict):
                    for k, v in data.items():
                        if k == keys[0]:
                            if len(keys) == 1:
                                return v
                            return find_value(v, keys[1:])
                        elif isinstance(v, (dict, list)):
                            result = find_value(v, keys)
                            if result is not None:
                                return result
                elif isinstance(data, list):
                    for item in data:
                        result = find_value(item, keys)
                        if result is not None:
                            return result
                return None

            # Ищем значение CPU Total
            cpu_value = find_value(data,
                                   ["Children", "Text", device_name, "Children", "Text", "CPU", "Children", "Text",
                                    "Load", "Children", "Text", "CPU Total", "Value"])

            if cpu_value:
                try:
                    # Преобразуем "45,23 %" в 45.23
                    value_str = cpu_value.split()[0].replace(",", ".")
                    return float(value_str)
                except (ValueError, AttributeError):
                    pass

            print(f"CPU data not found for {device_name} in response")
            return None

        except requests.exceptions.RequestException as e:
            print(f"Request error for {device_name}: {str(e)}")
        except Exception as e:
            print(f"Unexpected error for {device_name}: {str(e)}")

        return None

    def get_real_device_cpu_usage(self, device_name):
        """Получаем реальные данные с устройства"""
        try:
            # Для тестовых устройств
            if device_name.startswith("1DESKTOP-"):
                import random
                return random.uniform(10, 80)

            # Для реального устройства
            response = requests.get("http://localhost:8085/data.json", timeout=2)
            response.raise_for_status()
            data = response.json()

            # Убедимся, что структура данных соответствует ожидаемой
            print(f"Debug - Full API response: {json.dumps(data, indent=2)}")  # Логируем ответ

            # Ищем наше устройство в данных
            device_found = False
            cpu_usage = None

            # Перебираем все устройства в ответе
            for device in data.get("Children", []):
                if device.get("Text") == device_name:
                    device_found = True
                    print(f"Debug - Found device: {device_name}")

                    # Ищем CPU в устройстве
                    for sensor in device.get("Children", []):
                        if "CPU" in sensor.get("Text", ""):
                            print(f"Debug - Found CPU sensor: {sensor}")

                            # Ищем Load в CPU
                            for category in sensor.get("Children", []):
                                if category.get("Text") == "Load":
                                    print(f"Debug - Found Load category: {category}")

                                    # Ищем CPU Total
                                    for metric in category.get("Children", []):
                                        if "CPU Total" in metric.get("Text", ""):
                                            print(f"Debug - Found CPU Total: {metric}")
                                            try:
                                                # Парсим значение (пример: "45,23 %" -> 45.23)
                                                value_str = metric.get("Value", "0").split()[0]
                                                value_clean = value_str.replace(",", ".")
                                                cpu_usage = float(value_clean)
                                                print(f"Debug - Parsed CPU usage: {cpu_usage}")
                                                return cpu_usage
                                            except (ValueError, AttributeError) as e:
                                                print(f"Error parsing value: {e}")
                                                return None

            if not device_found:
                print(f"Device {device_name} not found in API response")
                return None

        except requests.exceptions.RequestException as e:
            print(f"Request error for {device_name}: {str(e)}")
        except Exception as e:
            print(f"Unexpected error for {device_name}: {str(e)}")

        return None

    def configure_multi_device_plot(self):
        """Настраиваем внешний вид графика"""
        self.multi_ax.set_title("Multi-Device CPU Monitoring")
        self.multi_ax.set_xlabel("Time")
        self.multi_ax.set_ylabel("CPU Usage (%)")
        self.multi_ax.grid(True)

        # Форматируем легенду
        if self.device_lines:
            self.multi_ax.legend(
                loc='upper right',
                bbox_to_anchor=(1.15, 1),
                borderaxespad=0.
            )

        # Форматируем ось времени
        if self.device_data:
            all_times = []
            for device in self.device_data.values():
                if device['time']:
                    all_times.extend(device['time'])

            if all_times:
                unique_times = sorted(list(set(all_times)))  # Уникальные отсортированные временные метки
                self.multi_ax.set_xticks(unique_times)
                self.multi_ax.set_xticklabels(
                    [time.strftime("%H:%M:%S", time.localtime(t)) for t in unique_times],
                    rotation=45,
                    ha='right'
                )

    def get_device_cpu_usage(self, device_name):
        """Возвращает загрузку CPU для указанного устройства"""
        try:
            # Для тестовых устройств генерируем случайные данные
            if device_name.startswith("1DESKTOP-"):
                import random
                return random.uniform(60, 80)
            if device_name.startswith("LAPTOP-"):
                import random
                return random.uniform(70, 80)
            if device_name.startswith("1DESKTOP-"):
                import random
                return random.uniform(40, 80)
            if device_name.startswith("DESKTOP-I8HOS10-"):
                import random
                return random.uniform(10, 80)

            # Для реального устройства получаем данные
            response = requests.get("http://localhost:8085/data.json", timeout=2)
            data = response.json()

            # Здесь должна быть ваша логика парсинга данных для конкретного устройства
            # Пример:
            for item in data["Children"]:
                if item["Text"] == device_name:
                    for sensor in item["Children"]:
                        if "CPU" in sensor["Text"]:
                            for category in sensor["Children"]:
                                if category["Text"] == "Load":
                                    for load in category["Children"]:
                                        if "CPU Total" in load["Text"]:
                                            return float(load["Value"].split()[0].replace(",", "."))
        except Exception as e:
            print(f"Error getting CPU usage for {device_name}: {str(e)}")

        return 0.0  # Возвращаем 0 если не удалось получить данные

    def update_multi_device_plot(self):
        try:
            # 1. Проверяем, существуют ли необходимые виджеты и атрибуты
            if not hasattr(self, 'multi_canvas') or not self.multi_canvas:
                print("Canvas not available")
                return

            if not hasattr(self, 'multi_plot') or not self.multi_plot:
                print("Plot not available")
                return

            if not hasattr(self, 'device_combo') or not self.device_combo:
                print("Device combo not available")
                return

            # 2. Получаем текущее время
            current_time = time.time()
            colors = ["white", "green", "red", "orange", "purple"]

            # 3. Очищаем предыдущий график
            self.multi_plot.clear()

            # 4. Проверяем и инициализируем данные устройств, если нужно
            if not hasattr(self, 'multi_device_data'):
                self.multi_device_data = {}
                for i in range(self.device_combo.count()):
                    device = self.device_combo.itemText(i)
                    self.multi_device_data[device] = {'x': [], 'y': []}

            # 5. Обновляем данные для каждого устройства
            for idx in range(self.device_combo.count()):
                device = self.device_combo.itemText(idx)
                try:
                    cpu_load = self.get_device_cpu_load(device)

                    # Инициализируем данные для нового устройства, если нужно
                    if device not in self.multi_device_data:
                        self.multi_device_data[device] = {'x': [], 'y': []}

                    # Добавляем новые данные
                    self.multi_device_data[device]['x'].append(current_time)
                    self.multi_device_data[device]['y'].append(cpu_load)

                    # Ограничиваем количество точек
                    max_points = 30
                    if len(self.multi_device_data[device]['x']) > max_points:
                        self.multi_device_data[device]['x'] = self.multi_device_data[device]['x'][-max_points:]
                        self.multi_device_data[device]['y'] = self.multi_device_data[device]['y'][-max_points:]

                    # Рисуем линию для устройства (если есть данные)
                    if self.multi_device_data[device]['x'] and self.multi_device_data[device]['y']:
                        self.multi_plot.plot(
                            self.multi_device_data[device]['x'],
                            self.multi_device_data[device]['y'],
                            label=f"{device} ({cpu_load:.1f}%)",
                            color=colors[idx % len(colors)],
                            linewidth=2
                        )
                except Exception as e:
                    print(f"Error processing device {device}: {str(e)}")
                    continue

            # 6. Настраиваем график
            self.multi_plot.set_title("Multi-Device CPU Load Over Time")
            self.multi_plot.set_xlabel("Time")
            self.multi_plot.set_ylabel("Usage (%)")
            self.multi_plot.grid(True)
            self.multi_plot.legend(loc='upper right')

            # 7. Форматируем ось времени (если есть данные)
            if self.multi_device_data and any(len(data['x']) > 0 for data in self.multi_device_data.values()):
                # Находим устройство с данными
                for device_data in self.multi_device_data.values():
                    if device_data['x']:
                        self.multi_plot.set_xticks(device_data['x'])
                        self.multi_plot.set_xticklabels(
                            [time.strftime("%H:%M:%S", time.localtime(t)) for t in device_data['x']],
                            rotation=45,
                            ha='right'
                        )
                        break

            # 8. Обновляем отображение
            self.multi_plot.relim()
            self.multi_plot.autoscale_view()
            self.multi_canvas.draw_idle()

            # 9. Сохраняем данные для отчета
            report_entry = {
                "time": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(current_time)),
                "multi_device_data": {}
            }

            for device, data in self.multi_device_data.items():
                if data['y']:
                    report_entry["multi_device_data"][device] = data['y'][-1]

            self.report_data.append(report_entry)

        except Exception as e:
            print(f"Critical error in update_multi_device_plot: {str(e)}")
            # Пытаемся восстановить график при следующем обновлении
            if hasattr(self, 'multi_canvas') and self.multi_canvas:
                self.multi_canvas.draw_idle()

        # 10. Перезапускаем таймер, только если виджет еще существует
        if hasattr(self, 'content_frame') and self.content_frame and hasattr(self, 'multi_device_timer'):
            self.multi_device_timer.singleShot(2000, self.update_multi_device_plot)

    def get_device_cpu_load(self, device_name):
        try:
            # Эмуляция данных для разных устройств
            if device_name == "1DESKTOP-COVAYN-1":
                # Генерируем случайные данные для тестового устройства
                import random
                return random.uniform(10, 50)

            # Реальные данные для основного устройства
            response = requests.get("http://localhost:8085/data.json", timeout=2)
            response.raise_for_status()
            data = response.json()

            for item in data["Children"]:
                if item["Text"] == device_name:
                    for sensor in item["Children"]:
                        if "CPU" in sensor["Text"]:
                            for category in sensor["Children"]:
                                if category["Text"] == "Load":
                                    for load in category["Children"]:
                                        if "CPU Total" in load["Text"]:
                                            raw_value = load["Value"].split()[0].replace(",", ".")
                                            return float(raw_value)
        except Exception as e:
            print(f"Error getting CPU load for {device_name}: {e}")
        return 0.0


    def get_device_cpu_load(self, device_name):
        try:
            response = requests.get("http://localhost:8085/data.json", timeout=2)
            response.raise_for_status()
            data = response.json()

            for item in data["Children"]:
                if item["Text"] == device_name:
                    for sensor in item["Children"]:
                        if "CPU" in sensor["Text"]:
                            for category in sensor["Children"]:
                                if category["Text"] == "Load":
                                    for load in category["Children"]:
                                        if "CPU Total" in load["Text"]:
                                            raw_value = load["Value"].split()[0].replace(",", ".")
                                            return float(raw_value)
        except Exception as e:
            print(f"Error getting CPU load for {device_name}: {e}")
        return 0.0

    def clear_content_frame(self):
        """Очищает содержимое правой панели."""
        for i in reversed(range(self.content_layout.count())):
            widget = self.content_layout.itemAt(i).widget()
            if widget and widget.parent() is not None:
                widget.setParent(None)

    def generate_pdf_report(self):
        if not all(isinstance(entry.get(key, 0), (int, float, str)) for key in
                   ["cpu_usage", "cpu_temp", "gpu_load", "gpu_temp"] for entry in self.report_data):
            QMessageBox.warning(self, "Error", "Invalid data for report.")
            return

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = SystemMonitorApp()
    window.show()
    sys.exit(app.exec_())