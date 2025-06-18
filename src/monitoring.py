import time
import subprocess
import platform
import psutil
import requests
from datetime import datetime
from PyQt5.QtCore import QThread, pyqtSignal

# Platform-specific imports
if platform.system() == 'Windows':
    try:
        import wmi
    except ImportError:
        wmi = None
else:
    wmi = None


class DataCollectorThread(QThread):
    data_updated = pyqtSignal(dict)

    def __init__(self, poll_interval_ms, parent=None):
        super().__init__(parent)
        self.poll_interval_s = poll_interval_ms / 1000.0
        self._running = True
        self.wmi_instance = None
        if platform.system() == 'Windows' and wmi:
            try:
                self.wmi_instance = wmi.WMI(namespace="root\\OpenHardwareMonitor")
            except Exception:
                self.wmi_instance = None

    def stop(self):
        self._running = False

    def get_cpu_temperature(self):
        try:
            if hasattr(psutil, "sensors_temperatures"):
                temps = psutil.sensors_temperatures()
                if not temps: return None
                if 'coretemp' in temps: return temps['coretemp'][0].current
                if 'k10temp' in temps: return temps['k10temp'][0].current
                if 'cpu_thermal' in temps: return temps['cpu_thermal'][0].current
                if temps: return list(temps.values())[0][0].current
            if self.wmi_instance:
                for sensor in self.wmi_instance.Sensor():
                    if sensor.SensorType == 'Temperature' and 'cpu' in sensor.Name.lower():
                        return float(sensor.Value)
        except Exception:
            return None
        return None

    def get_gpu_info(self):
        if platform.system() == "Windows":
            try:
                startupinfo = subprocess.STARTUPINFO()
                startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
                output = subprocess.check_output(
                    ['nvidia-smi', '--query-gpu=utilization.gpu,temperature.gpu,memory.used,memory.total',
                     '--format=csv,noheader,nounits'], stderr=subprocess.DEVNULL, text=True, startupinfo=startupinfo)
                v = output.strip().split(',')
                return {'load': float(v[0]), 'temp': float(v[1]), 'mem_used': float(v[2]), 'mem_total': float(v[3])}
            except (FileNotFoundError, subprocess.CalledProcessError):
                pass
            except Exception as e:
                print(f"Error with nvidia-smi: {e}")
            if self.wmi_instance:
                try:
                    gpu_info = {}
                    for sensor in self.wmi_instance.Sensor():
                        if 'gpu' in sensor.Name.lower():
                            if sensor.SensorType == 'Temperature': gpu_info['temp'] = float(sensor.Value)
                            if sensor.SensorType == 'Load' and 'core' in sensor.Name.lower(): gpu_info['load'] = float(
                                sensor.Value)
                    return gpu_info if gpu_info else None
                except Exception:
                    return None
        elif platform.system() == "Linux":
            try:
                output = subprocess.check_output(
                    ['nvidia-smi', '--query-gpu=utilization.gpu,temperature.gpu,memory.used,memory.total',
                     '--format=csv,noheader,nounits'], stderr=subprocess.DEVNULL, text=True)
                v = output.strip().split(',')
                return {'load': float(v[0]), 'temp': float(v[1]), 'mem_used': float(v[2]), 'mem_total': float(v[3])}
            except (FileNotFoundError, subprocess.CalledProcessError):
                return None
        return None

    def run(self):
        while self._running:
            data_bundle = {'timestamp': datetime.now()}
            try:
                # CPU data
                data_bundle['cpu'] = {
                    'percent': psutil.cpu_percent(interval=None),
                    'frequency': psutil.cpu_freq()._asdict() if psutil.cpu_freq() else None,
                    'cores_physical': psutil.cpu_count(logical=False),
                    'cores_logical': psutil.cpu_count(logical=True),
                    'temperature': self.get_cpu_temperature()
                }

                # Memory data
                data_bundle['memory'] = {
                    'virtual': psutil.virtual_memory()._asdict(),
                    'swap': psutil.swap_memory()._asdict()
                }

                # Disk data
                partitions = psutil.disk_partitions(all=False)
                disk_data = {}
                for part in partitions:
                    if not (('fixed' in part.opts if platform.system() == 'Windows' else part.device.startswith(
                            ('/dev/sd', '/dev/nvme')))):
                        continue
                    try:
                        disk_data[part.mountpoint.replace(":", "_drive")] = psutil.disk_usage(part.mountpoint)._asdict()
                    except Exception:
                        continue
                data_bundle['disk'] = disk_data

                # GPU data
                data_bundle['gpu'] = self.get_gpu_info()

                # Network data
                net_io_pernic = psutil.net_io_counters(pernic=True)
                data_bundle['network'] = {k.replace(":", "_").replace(" ", "_"): v._asdict() for k, v in
                                          net_io_pernic.items()}
            except Exception as e:
                print(f"Error collecting data: {e}")

            self.data_updated.emit(data_bundle)
            time.sleep(self.poll_interval_s)


class SpeedTestThread(QThread):
    result_ready = pyqtSignal(str)

    def run(self):
        try:
            self.result_ready.emit("Running speed test...")
            test_file_url = "http://speedtest.tele2.net/1MB.zip"
            start_time = time.time()
            with requests.get(test_file_url, stream=True, timeout=20) as r:
                r.raise_for_status()
                total_length = 0
                for chunk in r.iter_content(chunk_size=8192):
                    if chunk: total_length += len(chunk)
            duration = time.time() - start_time
            if duration > 0:
                speed_mbps = (total_length * 8) / (duration * 1024 * 1024)
                result_text = (f"Downloaded {total_length / 1024:.2f} KB in {duration:.2f} seconds\n"
                               f"Download Speed: {speed_mbps:.2f} Mbps")
            else:
                result_text = "Speed test failed: duration was zero."
            self.result_ready.emit(result_text)
        except requests.RequestException as e:
            self.result_ready.emit(f"Speed test failed: Network error\n{str(e)}")
        except Exception as e:
            self.result_ready.emit(f"Speed test failed: An unexpected error occurred.\n{str(e)}")