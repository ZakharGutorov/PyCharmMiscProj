import os
import json
import tempfile
import platform
import subprocess
import psutil


def load_settings():
    path = os.path.join(os.path.expanduser('~'), '.system_monitor_settings.json')
    default_settings = {
        'poll_interval': 2000,
        'cpu_temp_threshold': 80,
        'gpu_temp_threshold': 85,
        'ram_threshold': 90,
        'disk_threshold': 90,
        'popup_alerts': True
    }

    if not os.path.exists(path):
        return default_settings

    try:
        with open(path, 'r') as f:
            return {**default_settings, **json.load(f)}
    except Exception:
        return default_settings


def save_settings(settings):
    path = os.path.join(os.path.expanduser('~'), '.system_monitor_settings.json')
    try:
        with open(path, 'w') as f:
            json.dump(settings, f, indent=4)
    except Exception:
        pass


def run_disk_cleanup(paths):
    log = ["Starting disk cleanup..."]
    total_files = 0
    total_size = 0

    for path in paths:
        if not os.path.exists(path):
            log.append(f"Skipping non-existent path: {path}")
            continue

        log.append(f"Cleaning: {path}")
        files = 0
        size = 0

        for root, dirs, filenames in os.walk(path):
            for filename in filenames:
                try:
                    file_path = os.path.join(root, filename)
                    file_size = os.path.getsize(file_path)
                    os.remove(file_path)
                    files += 1
                    size += file_size
                except Exception as e:
                    log.append(f"Error deleting {file_path}: {str(e)}")

        total_files += files
        total_size += size
        log.append(f"Deleted {files} files ({size / (1024 * 1024):.2f} MB)")

    log.append(f"Total deleted: {total_files} files ({total_size / (1024 * 1024):.2f} MB)")
    return log


def check_disk_health():
    try:
        if platform.system() == 'Windows':
            result = subprocess.run(
                ['chkdsk', 'C:'],
                capture_output=True,
                text=True,
                encoding='cp866' if platform.system() == 'Windows' else 'utf-8'
            )
            return result.stdout + result.stderr
        else:
            disk = next((p.device for p in psutil.disk_partitions() if p.mountpoint == '/'), None)
            if not disk:
                return "Root partition not found"

            result = subprocess.run(
                ['smartctl', '-H', disk],
                capture_output=True,
                text=True
            )
            return result.stdout + result.stderr
    except Exception as e:
        return f"Error: {str(e)}"


def run_ping_test(target):
    try:
        param = '-n' if platform.system() == 'Windows' else '-c'
        result = subprocess.run(
            ['ping', param, '4', target],
            capture_output=True,
            text=True
        )
        return result.stdout + result.stderr
    except Exception as e:
        return f"Error: {str(e)}"