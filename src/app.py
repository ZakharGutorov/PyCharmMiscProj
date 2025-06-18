import time
import random
import platform
import os
from datetime import datetime
from collections import deque
from PyQt5.QtCore import QTimer, Qt, pyqtSlot
from PyQt5.QtWidgets import QMainWindow, QVBoxLayout, QHBoxLayout, QWidget, QTabWidget, QMessageBox, QFrame, QPushButton, QLabel

from monitoring import DataCollectorThread, SpeedTestThread
from widgets import DashboardTab, CpuTab, MemoryTab, DiskTab, GpuTab, NetworkTab, MultiDeviceTab, AlertsTab, ReportsTab, SettingsTab, ToolsTab
from utils import load_settings, save_settings


class SystemMonitorApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("System Monitor")
        self.setGeometry(100, 100, 1400, 900)

        # Инициализация данных
        self.max_graph_points = 100
        self.time_points = deque(maxlen=self.max_graph_points)
        self.cpu_usage_points = deque(maxlen=self.max_graph_points)
        self.cpu_temp_points = deque(maxlen=self.max_graph_points)
        self.gpu_load_points = deque(maxlen=self.max_graph_points)
        self.gpu_temp_points = deque(maxlen=self.max_graph_points)
        self.mem_usage_points = deque(maxlen=self.max_graph_points)
        self.historical_data = deque(maxlen=2000)
        self.last_net_io = None
        self.last_update_time = None
        self.simulated_devices = []
        self.alert_history = deque(maxlen=100)
        self.last_alert_time = {}
        self.alerts_enabled = True
        self.initialized_tabs = set()
        self.speed_test_thread = SpeedTestThread()

        # Загрузка настроек
        self.settings = load_settings()

        # Создание интерфейса
        self.init_ui()
        self.init_monitoring()

        # Дополнительный таймер
        self.aux_timer = QTimer(self)
        self.aux_timer.timeout.connect(self.update_simulated_devices_view)
        self.aux_timer.start(3000)

    def init_ui(self):
        # Основной виджет и layout
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        main_layout = QHBoxLayout(main_widget)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # Боковая панель
        self.init_sidebar(main_layout)

        # Область контента
        self.init_content_area(main_layout)

        # Статус бар
        self.statusBar().showMessage("Ready")

    def init_sidebar(self, main_layout):
        self.sidebar = QFrame()
        self.sidebar.setFixedWidth(200)
        self.sidebar.setStyleSheet("background-color: #2c3e50; color: white;")
        sidebar_layout = QVBoxLayout(self.sidebar)
        sidebar_layout.setContentsMargins(10, 10, 10, 10)
        sidebar_layout.setSpacing(8)
        buttons = [
            ("Dashboard", lambda: self.tabs.setCurrentIndex(0)), ("CPU", lambda: self.tabs.setCurrentIndex(1)),
            ("Memory", lambda: self.tabs.setCurrentIndex(2)), ("Disk", lambda: self.tabs.setCurrentIndex(3)),
            ("GPU", lambda: self.tabs.setCurrentIndex(4)), ("Network", lambda: self.tabs.setCurrentIndex(5)),
            ("Multi-Device", lambda: self.tabs.setCurrentIndex(6)), ("Alerts", lambda: self.tabs.setCurrentIndex(7)),
            ("Reports", lambda: self.tabs.setCurrentIndex(8)), ("Settings", lambda: self.tabs.setCurrentIndex(9)),
            ("Tools", lambda: self.tabs.setCurrentIndex(10))
        ]
        for text, handler in buttons:
            btn = QPushButton(text)
            btn.setStyleSheet("""
                QPushButton { background-color: #34495e; color: white; border: none; padding: 12px; text-align: left; border-radius: 5px; }
                QPushButton:hover { background-color: #4a6b8a; }
                QPushButton:pressed { background-color: #5a82a8; }
            """)
            btn.clicked.connect(handler)
            sidebar_layout.addWidget(btn)
        sidebar_layout.addStretch()
        main_layout.addWidget(self.sidebar)

    def init_content_area(self, main_layout):
        self.content_area = QFrame()
        self.content_area.setStyleSheet("background-color: #ecf0f1;")
        content_layout = QVBoxLayout(self.content_area)
        self.tabs = QTabWidget()
        self.tabs.tabBar().setVisible(False)

        # Создание вкладок
        self.tabs.addTab(DashboardTab(self), "Dashboard")
        self.tabs.addTab(CpuTab(self), "CPU")
        self.tabs.addTab(MemoryTab(self), "Memory")
        self.tabs.addTab(DiskTab(self), "Disk")
        self.tabs.addTab(GpuTab(self), "GPU")
        self.tabs.addTab(NetworkTab(self), "Network")
        self.tabs.addTab(MultiDeviceTab(self), "Multi-Device")
        self.tabs.addTab(AlertsTab(self), "Alerts")
        self.tabs.addTab(ReportsTab(self), "Reports")
        self.tabs.addTab(SettingsTab(self), "Settings")
        self.tabs.addTab(ToolsTab(self), "Tools")

        self.multi_device_tab = self.tabs.widget(6)

        self.tabs.currentChanged.connect(self.on_tab_changed)
        content_layout.addWidget(self.tabs)
        main_layout.addWidget(self.content_area)
        self.on_tab_changed(0)

    def on_tab_changed(self, index):
        if index in self.initialized_tabs:
            return

        # Инициализация вкладки при первом переходе
        tab = self.tabs.widget(index)
        if hasattr(tab, 'init_ui'):
            tab.init_ui()
        self.initialized_tabs.add(index)

    def init_monitoring(self):
        poll_interval = self.settings.get('poll_interval', 2000)
        self.data_collector = DataCollectorThread(poll_interval, self)
        self.data_collector.data_updated.connect(self.handle_data_update)
        self.data_collector.start()

    @pyqtSlot(dict)
    def handle_data_update(self, data):
        self.historical_data.append(data)
        now = data['timestamp']
        self.time_points.append(now)

        # Обновление данных
        cpu_data = data.get('cpu', {})
        self.cpu_usage_points.append(cpu_data.get('percent'))
        self.cpu_temp_points.append(cpu_data.get('temperature'))

        mem_data = data.get('memory', {}).get('virtual', {})
        self.mem_usage_points.append(mem_data.get('percent'))

        gpu_info = data.get('gpu') or {}
        self.gpu_load_points.append(gpu_info.get('load'))
        self.gpu_temp_points.append(gpu_info.get('temp'))

        # Проверка на предупреждения
        self.check_for_alerts(data)

        # Обновление текущей вкладки
        self.update_current_tab()

    def check_for_alerts(self, data):
        cpu_temp = data.get('cpu', {}).get('temperature')
        if cpu_temp and cpu_temp > self.settings['cpu_temp_threshold']:
            self.trigger_alert('CPU', f"High temperature: {cpu_temp:.0f}°C")

        mem_percent = data.get('memory', {}).get('virtual', {}).get('percent')
        if mem_percent and mem_percent > self.settings['ram_threshold']:
            self.trigger_alert('Memory', f'High usage: {mem_percent:.0f}%')

        gpu_info = data.get('gpu')
        if gpu_info and gpu_info.get('temp') and gpu_info.get('temp') > self.settings['gpu_temp_threshold']:
            self.trigger_alert('GPU', f"High temperature: {gpu_info.get('temp'):.0f}°C")

        for mount, usage in data.get('disk', {}).items():
            if usage['percent'] > self.settings['disk_threshold']:
                self.trigger_alert('Disk', f"High usage on {mount.replace('_drive', ':')}: {usage['percent']:.0f}%")

    def trigger_alert(self, component, message):
        if not self.alerts_enabled:
            return

        alert_key = f"{component}-{message.split(':')[0]}"
        now = time.time()
        if now - self.last_alert_time.get(alert_key, 0) < 300:  # 5 минут
            return

        self.last_alert_time[alert_key] = now
        alert_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self.alert_history.appendleft({'time': alert_time, 'component': component, 'message': message})

        # Показ всплывающего окна
        if self.settings.get('popup_alerts', True):
            QMessageBox.warning(self, f"{component} Alert", message)

    def update_current_tab(self):
        index = self.tabs.currentIndex()
        if index in self.initialized_tabs:
            tab = self.tabs.widget(index)
            if hasattr(tab, 'update_data'):
                tab.update_data(
                    self.historical_data,
                    self.time_points,
                    self.cpu_usage_points,
                    self.cpu_temp_points,
                    self.gpu_load_points,
                    self.gpu_temp_points,
                    self.mem_usage_points,
                    self.alert_history
                )

    def discover_network_devices(self):
        """Simulate network device discovery"""
        self.statusBar().showMessage("Discovering network devices...")
        self.populate_simulated_devices()
        QTimer.singleShot(2000, lambda: self.statusBar().showMessage("Ready"))

    def populate_simulated_devices(self):
        """Create simulated devices"""
        self.simulated_devices.clear()
        for i, name in enumerate(["WEB-SRV-01", "DB-MASTER", "APP-WORKER", "NAS-STORAGE", "DEV-CLIENT"]):
            self.simulated_devices.append({
                'name': name,
                'ip': f'192.168.1.{10 + i}',
                'status': 'Online',
                'cpu': random.randint(5, 70),
                'ram': random.randint(20, 80)
            })
        self.update_simulated_devices_view()

    def update_simulated_devices_view(self):
        """Update the multi-device tab with current device data"""
        if hasattr(self, 'multi_device_tab'):
            self.multi_device_tab.update_devices(self.simulated_devices)

    def closeEvent(self, event):
        reply = QMessageBox.question(
            self,
            'Exit',
            'Are you sure you want to exit?',
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )

        if reply == QMessageBox.Yes:
            self.aux_timer.stop()
            if self.speed_test_thread.isRunning():
                self.speed_test_thread.quit()
                self.speed_test_thread.wait()

            self.data_collector.stop()
            self.data_collector.wait()
            save_settings(self.settings)
            event.accept()
        else:
            event.ignore()