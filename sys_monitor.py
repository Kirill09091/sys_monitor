import tkinter as tk
from tkinter import ttk
import psutil
import platform
import os
from collections import deque
import threading # Для запуска иконки в системном трее в отдельном потоке
import json # Для сохранения и загрузки настроек
import time # Для расчета времени работы и сетевой активности
import subprocess # Для пинга

# Импорт для иконки системного трея
try:
    from pystray import Icon as pystray_Icon, MenuItem as pystray_MenuItem
    from PIL import Image, ImageDraw
    PYSTRAY_AVAILABLE = True
except ImportError:
    print("Библиотеки 'pystray' или 'Pillow' не найдены. Иконка в трее не будет работать.")
    print("Установите их: pip install pystray Pillow")
    PYSTRAY_AVAILABLE = False

# Импорт для операций с реестром Windows
if platform.system() == "Windows":
    import winreg

# --- Глобальные переменные для сглаживания загрузки CPU ---
cpu_history = deque(maxlen=10)

# --- Глобальные переменные для управления окном ---
is_maximized = False
original_geometry = ""
tray_icon = None # Переменная для хранения объекта иконки в трее

# --- Глобальные переменные для циклического отображения в трее ---
stat_cycle_index = 0
stat_display_messages = [] # Будет хранить текущие сообщения для всплывающей подсказки

# --- Глобальные переменные для расчета сетевой активности ---
last_net_bytes_sent_per_nic = {} # Хранит отправленные байты для каждой сетевой карты
last_net_bytes_recv_per_nic = {} # Хранит полученные байты для каждой сетевой карты
last_net_time = 0

# --- Глобальные переменные для расчета дискового ввода-вывода ---
last_disk_io_read_bytes = 0
last_disk_io_write_bytes = 0
last_disk_io_time = 0

# --- Глобальная переменная для результата пинга ---
ping_result = None
ping_in_progress = False

# --- Время запуска приложения ---
app_start_time = time.time()

# --- Путь к файлу конфигурации ---
CONFIG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'config.json')

# --- Функции для сохранения/загрузки конфигурации ---
def load_config(profile_name=None):
    """
    Загружает настройки из файла конфигурации.
    Если указано profile_name, загружает этот профиль.
    В противном случае загружает текущий активный профиль.
    """
    try:
        with open(CONFIG_FILE, 'r') as f:
            full_config = json.load(f)
            profiles = full_config.get('profiles', {})
            current_active_profile_name = full_config.get('current_profile', 'Default')

            if not profiles: # Если профилей нет, создаем профиль по умолчанию
                profiles['Default'] = {
                    'ram_display_mode': 'percent',
                    'selected_disk': 'C:\\',
                    'selected_net_nic': 'All', # По умолчанию для всех сетевых карт
                    'topmost': True,
                    'run_on_startup': False,
                    'update_interval': '5',
                    'show_cpu': True,
                    'show_ram': True,
                    'show_disk': True,
                    'show_net': False, # По умолчанию False
                    'show_total_processes': True,
                    'show_user_processes': True,
                    'show_uptime': True,
                    'show_cpu_freq': True,
                    'show_top_process': True,
                    'show_physical_cores': True,
                    'show_logical_cores': True,
                    'show_swap_usage': True,
                    'show_top_ram_process': True,
                    'show_app_uptime': True,
                    'show_real_time': True,
                    'show_cpu_temp': False, # По умолчанию False
                    'show_fan_speed': False, # По умолчанию False
                    'show_battery_status': True,
                    'show_cpu_times': True,
                    'show_per_cpu_usage': True,
                    'show_network_latency': False, # По умолчанию False
                    'show_process_states': True,
                    'show_disk_io': True # Новая настройка по умолчанию
                }
                current_active_profile_name = 'Default'
                save_config(profile_name='Default', initial_save=True) # Сохраняем профиль по умолчанию

            if profile_name is None:
                profile_to_load = profiles.get(current_active_profile_name, profiles['Default'])
            else:
                profile_to_load = profiles.get(profile_name, profiles['Default'])
                current_active_profile_name = profile_name # Обновляем текущий активный профиль

            # Применяем загруженные настройки к переменным Tkinter
            ram_display_var.set(profile_to_load.get('ram_display_mode', 'percent'))
            
            # Проверяем, существует ли выбранный диск, иначе устанавливаем первый доступный
            default_disk = psutil.disk_partitions()[0].mountpoint if psutil.disk_partitions() else 'N/A'
            disk_var.set(profile_to_load.get('selected_disk', default_disk))
            if disk_var.get() not in [p.mountpoint for p in psutil.disk_partitions()]:
                disk_var.set(default_disk)

            # selected_net_nic больше не используется для отображения, но сохраняется для совместимости
            net_nic_var.set(profile_to_load.get('selected_net_nic', 'All')) 


            topmost_var.set(profile_to_load.get('topmost', True))
            window.attributes('-topmost', topmost_var.get())
            startup_var.set(profile_to_load.get('run_on_startup', False))
            update_interval_var.set(profile_to_load.get('update_interval', '5'))
            
            show_cpu_var.set(profile_to_load.get('show_cpu', True))
            show_ram_var.set(profile_to_load.get('show_ram', True))
            show_disk_var.set(profile_to_load.get('show_disk', True))
            show_net_var.set(profile_to_load.get('show_net', False)) # Остается False
            show_total_processes_var.set(profile_to_load.get('show_total_processes', True))
            show_user_processes_var.set(profile_to_load.get('show_user_processes', True))
            show_uptime_var.set(profile_to_load.get('show_uptime', True))
            show_cpu_freq_var.set(profile_to_load.get('show_cpu_freq', True))
            show_top_process_var.set(profile_to_load.get('show_top_process', True))
            show_physical_cores_var.set(profile_to_load.get('show_physical_cores', True))
            show_logical_cores_var.set(profile_to_load.get('show_logical_cores', True))
            show_swap_usage_var.set(profile_to_load.get('show_swap_usage', True))
            show_top_ram_process_var.set(profile_to_load.get('show_top_ram_process', True))
            show_app_uptime_var.set(profile_to_load.get('show_app_uptime', True))
            show_real_time_var.set(profile_to_load.get('show_real_time', True))
            show_cpu_temp_var.set(False) # Остается False
            show_fan_speed_var.set(False) # Остается False
            show_battery_status_var.set(profile_to_load.get('show_battery_status', True))
            show_cpu_times_var.set(profile_to_load.get('show_cpu_times', True))
            show_per_cpu_usage_var.set(profile_to_load.get('show_per_cpu_usage', True))
            show_network_latency_var.set(False) # Остается False
            show_process_states_var.set(profile_to_load.get('show_process_states', True))
            show_disk_io_var.set(profile_to_load.get('show_disk_io', True)) # Загружаем значение

            return full_config
    except (FileNotFoundError, json.JSONDecodeError):
        # Создаем конфигурацию по умолчанию, если файл не найден или поврежден
        default_config = {
            'ram_display_mode': 'percent',
            'selected_disk': psutil.disk_partitions()[0].mountpoint if psutil.disk_partitions() else 'C:\\',
            'selected_net_nic': 'All',
            'topmost': True,
            'run_on_startup': False,
            'update_interval': '5',
            'show_cpu': True,
            'show_ram': True,
            'show_disk': True,
            'show_net': False, # По умолчанию False
            'show_total_processes': True,
            'show_user_processes': True,
            'show_uptime': True,
            'show_cpu_freq': True,
            'show_top_process': True,
            'show_physical_cores': True,
            'show_logical_cores': True,
            'show_swap_usage': True,
            'show_top_ram_process': True,
            'show_app_uptime': True,
            'show_real_time': True,
            'show_cpu_temp': False,
            'show_fan_speed': False,
            'show_battery_status': True,
            'show_cpu_times': True,
            'show_per_cpu_usage': True,
            'show_network_latency': False, # По умолчанию False
            'show_process_states': True,
            'show_disk_io': True
        }
        full_config = {'current_profile': 'Default', 'profiles': {'Default': default_config}}
        try:
            with open(CONFIG_FILE, 'w') as f:
                json.dump(full_config, f, indent=4)
        except Exception as e:
            print(f"Ошибка сохранения конфигурации по умолчанию: {e}")
        return full_config

def save_config(profile_name=None, initial_save=False):
    """
    Сохраняет текущие настройки в файл конфигурации.
    Если указано profile_name, сохраняет как новый профиль или обновляет существующий.
    Если initial_save=True, это начальное сохранение профиля по умолчанию.
    """
    current_settings = {
        'ram_display_mode': ram_display_var.get(),
        'selected_disk': disk_var.get(),
        'selected_net_nic': 'All', # Больше не используется для отображения, но сохраняем значение по умолчанию
        'topmost': topmost_var.get(),
        'run_on_startup': startup_var.get(),
        'update_interval': update_interval_var.get(),
        'show_cpu': show_cpu_var.get(),
        'show_ram': show_ram_var.get(),
        'show_disk': show_disk_var.get(),
        'show_net': False, # Остается False
        'show_total_processes': show_total_processes_var.get(),
        'show_user_processes': show_user_processes_var.get(),
        'show_uptime': show_uptime_var.get(),
        'show_cpu_freq': show_cpu_freq_var.get(),
        'show_top_process': show_top_process_var.get(),
        'show_physical_cores': show_physical_cores_var.get(),
        'show_logical_cores': show_logical_cores_var.get(),
        'show_swap_usage': show_swap_usage_var.get(),
        'show_top_ram_process': show_top_ram_process_var.get(),
        'show_app_uptime': show_app_uptime_var.get(),
        'show_real_time': show_real_time_var.get(),
        'show_cpu_temp': False, # Остается False
        'show_fan_speed': False, # Остается False
        'show_battery_status': show_battery_status_var.get(),
        'show_cpu_times': show_cpu_times_var.get(),
        'show_per_cpu_usage': show_per_cpu_usage_var.get(),
        'show_network_latency': False, # Остается False
        'show_process_states': show_process_states_var.get(),
        'show_disk_io': show_disk_io_var.get() # Сохраняем значение
    }

    full_config = {}
    try:
        with open(CONFIG_FILE, 'r') as f:
            full_config = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        pass # Файл не существует или поврежден, создаем новый

    profiles = full_config.get('profiles', {})
    
    if profile_name:
        profiles[profile_name] = current_settings
        full_config['current_profile'] = profile_name
    elif 'current_profile' in full_config and not initial_save:
        # Обновляем текущий активный профиль, если он существует
        current_active_profile_name = full_config['current_profile']
        if current_active_profile_name in profiles:
            profiles[current_active_profile_name] = current_settings
        else: # Если текущий профиль был удален или не существует, сохраняем как "Default"
            profiles['Default'] = current_settings
            full_config['current_profile'] = 'Default'
    else: # Если нет текущего профиля и не начальное сохранение, сохраняем как "Default"
        profiles['Default'] = current_settings
        full_config['current_profile'] = 'Default'

    full_config['profiles'] = profiles

    try:
        with open(CONFIG_FILE, 'w') as f:
            json.dump(full_config, f, indent=4)
    except Exception as e:
        print(f"Ошибка сохранения конфигурации: {e}")
        display_error_message(f"Ошибка сохранения конфига: {e}")

# --- Функции для получения системных метрик ---

def get_cpu_usage():
    """Возвращает текущую загрузку CPU в процентах."""
    try:
        return psutil.cpu_percent(interval=None)
    except Exception as e:
        display_error_message(f"Ошибка CPU: {e}")
        return 0.0

def get_per_cpu_usage():
    """Возвращает использование CPU для каждого ядра в процентах."""
    try:
        return psutil.cpu_percent(interval=None, percpu=True)
    except Exception as e:
        display_error_message(f"Ошибка по ядрам CPU: {e}")
        return []

def get_ram_usage():
    """Возвращает текущее использование RAM в процентах и ГБ."""
    try:
        virtual_memory = psutil.virtual_memory()
        percent = virtual_memory.percent
        used_gb = virtual_memory.used / (1024**3)
        total_gb = virtual_memory.total / (1024**3)
        return percent, used_gb, total_gb
    except Exception as e:
        display_error_message(f"Ошибка RAM: {e}")
        return 0.0, 0.0, 0.0

def get_disk_usage(path):
    """
    Возвращает использованное и общее дисковое пространство в ГБ,
    и процент использования.
    """
    try:
        disk = psutil.disk_usage(path)
        used_gb = disk.used / (1024**3) # Конвертируем байты в ГБ
        total_gb = disk.total / (1024**3) # Конвертируем байты в ГБ
        free_gb = disk.free / (1024**3) # Свободно в ГБ
        percent = disk.percent
        return used_gb, total_gb, free_gb, percent
    except Exception as e:
        display_error_message(f"Ошибка диска {path}: {e}")
        return 0.0, 0.0, 0.0, 0.0 # Возвращаем нули в случае ошибки

def get_disk_io_speeds():
    """Возвращает общую скорость чтения и записи диска в отформатированных строках."""
    global last_disk_io_read_bytes, last_disk_io_write_bytes, last_disk_io_time
    read_speed_str = "0 B/s"
    write_speed_str = "0 B/s"
    current_time = time.time()

    try:
        total_io = psutil.disk_io_counters()

        if last_disk_io_time != 0 and (current_time - last_disk_io_time) > 0:
            time_diff = current_time - last_disk_io_time
            
            read_speed_bytes_sec = (total_io.read_bytes - last_disk_io_read_bytes) / time_diff
            write_speed_bytes_sec = (total_io.write_bytes - last_disk_io_write_bytes) / time_diff

            read_speed_str = format_bytes_per_second(read_speed_bytes_sec)
            write_speed_str = format_bytes_per_second(write_speed_bytes_sec)

        last_disk_io_read_bytes = total_io.read_bytes
        last_disk_io_write_bytes = total_io.write_bytes
        last_disk_io_time = current_time

    except Exception as e:
        # display_error_message(f"Ошибка Disk I/O: {e}") # Слишком часто для status_label
        pass
    return read_speed_str, write_speed_str

def get_cpu_info():
    """Возвращает количество физических и логических ядер CPU."""
    try:
        physical_cores = psutil.cpu_count(logical=False)
        logical_cores = psutil.cpu_count(logical=True)
        return physical_cores, logical_cores
    except Exception as e:
        display_error_message(f"Ошибка ядер/потоков CPU: {e}")
        return 0, 0

def get_cpu_frequency():
    """Возвращает текущую, минимальную и максимальную частоту CPU."""
    try:
        freq = psutil.cpu_freq()
        if freq:
            return freq.current, freq.min, freq.max
        return None, None, None
    except Exception as e:
        display_error_message(f"Ошибка частоты CPU: {e}")
        return None, None, None

def get_cpu_temperature():
    """Возвращает температуру CPU."""
    try:
        temps = psutil.sensors_temperatures()
        if 'coretemp' in temps: # Для большинства Intel CPUs
            for entry in temps['coretemp']:
                if 'cpu' in entry.label.lower() or 'package' in entry.label.lower():
                    return entry.current
        elif 'k10temp' in temps: # Для большинства AMD CPUs
             for entry in temps['k10temp']:
                if 'cpu' in entry.label.lower() or 'tctl' in entry.label.lower():
                    return entry.current
        # Можно добавить другие проверки для разных систем
        return None
    except Exception as e:
        # display_error_message(f"Ошибка температуры CPU: {e}") # Слишком часто
        return None

def get_fan_speed():
    """Возвращает скорость вентилятора."""
    try:
        fans = psutil.sensors_fans()
        if fans:
            for name, entries in fans.items():
                for entry in entries:
                    return entry.current # Возвращаем первую найденную скорость вентилятора
        return None
    except Exception as e:
        # display_error_message(f"Ошибка скорости вентилятора: {e}") # Слишком часто
        return None

def get_swap_usage():
    """Возвращает использование файла подкачки в процентах."""
    try:
        swap = psutil.swap_memory()
        return swap.percent
    except Exception as e:
        display_error_message(f"Ошибка Swap: {e}")
        return 0.0

def get_top_ram_process():
    """Возвращает процесс, потребляющий больше всего RAM."""
    top_ram_process_name = "N/A"
    top_ram_percent = 0.0
    try:
        processes = []
        for p in psutil.process_iter(['pid', 'name', 'memory_percent']):
            try:
                processes.append(p.info)
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                pass
        
        if processes:
            processes.sort(key=lambda x: x['memory_percent'], reverse=True)
            if processes[0]['memory_percent'] > 0:
                top_ram_process_name = processes[0]['name']
                top_ram_percent = processes[0]['memory_percent']
        return top_ram_process_name, top_ram_percent
    except Exception as e:
        display_error_message(f"Ошибка топ-процессов RAM: {e}")
        return "N/A", 0.0

def get_process_counts():
    """Возвращает общее количество процессов и количество пользовательских процессов."""
    total_processes = 0
    user_processes = 0
    try:
        total_processes = len(psutil.pids())
        current_user = psutil.Process(os.getpid()).username() # Получаем имя текущего пользователя
        
        for p in psutil.process_iter(['username']):
            try:
                if p.info['username'] == current_user:
                    user_processes += 1
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                pass
        return total_processes, user_processes
    except Exception as e:
        display_error_message(f"Ошибка подсчета процессов: {e}")
        return 0, 0

def get_process_states():
    """Возвращает количество процессов в различных состояниях."""
    running = 0
    sleeping = 0
    zombie = 0
    stopped = 0
    other = 0
    try:
        for p in psutil.process_iter(['status']):
            try:
                status = p.info['status']
                if status == psutil.STATUS_RUNNING:
                    running += 1
                elif status == psutil.STATUS_SLEEPING:
                    sleeping += 1
                elif status == psutil.STATUS_ZOMBIE:
                    zombie += 1
                elif status == psutil.STATUS_STOPPED:
                    stopped += 1
                else:
                    other += 1
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                pass
        return running, sleeping, zombie, stopped, other
    except Exception as e:
        display_error_message(f"Ошибка статусов процессов: {e}")
        return 0, 0, 0, 0, 0

def get_battery_status():
    """Возвращает статус батареи: процент, состояние, оставшееся время."""
    try:
        battery = psutil.sensors_battery()
        if battery:
            percent = battery.percent
            power_plugged = battery.power_plugged
            secsleft = battery.secsleft
            
            status = "Заряжается" if power_plugged else "Разряжается"
            if secsleft == psutil.POWER_TIME_UNLIMITED:
                time_left = "Неограниченно"
            elif secsleft == psutil.POWER_TIME_UNKNOWN:
                time_left = "Неизвестно"
            else:
                time_left = format_uptime(secsleft)
            return percent, status, time_left
        return None, None, None
    except AttributeError:
        # psutil.sensors_battery() может быть недоступен на настольных ПК или некоторых ОС
        return None, None, None
    except Exception as e:
        display_error_message(f"Ошибка батареи: {e}")
        return None, None, None

def get_cpu_times():
    """Возвращает время CPU в пользовательском, системном и режиме простоя."""
    try:
        cpu_times = psutil.cpu_times()
        return cpu_times.user, cpu_times.system, cpu_times.idle
    except Exception as e:
        display_error_message(f"Ошибка времени CPU: {e}")
        return None, None, None

# --- Функции для управления окном ---

def do_minimize():
    """Сворачивает окно (скрывает его) и показывает иконку в трее."""
    window.withdraw() # Скрывает окно
    if PYSTRAY_AVAILABLE and tray_icon:
        tray_icon.visible = True

def do_close():
    """Полностью закрывает приложение."""
    exit_application() # Теперь кнопка '✕' полностью закрывает приложение

def exit_application():
    """Полностью закрывает приложение."""
    save_config() # Сохраняем настройки при выходе
    if PYSTRAY_AVAILABLE and tray_icon:
        tray_icon.stop() # Останавливаем иконку в трее
    window.destroy() # Уничтожаем окно Tkinter

def toggle_topmost():
    """Переключает состояние "поверх всех окон"."""
    current_state = window.attributes('-topmost')
    window.attributes('-topmost', not current_state)
    save_config() # Сохраняем изменение

def add_to_startup():
    """Добавляет приложение в автозагрузку Windows через реестр."""
    if platform.system() == "Windows":
        try:
            script_path = os.path.abspath(__file__)
            python_exe_path = os.path.join(os.path.dirname(os.sys.executable), 'pythonw.exe')
            command = f'"{python_exe_path}" "{script_path}"'
            
            key = winreg.OpenKey(winreg.HKEY_CURRENT_USER,
                                 r"SOFTWARE\Microsoft\Windows\CurrentVersion\Run",
                                 0, winreg.KEY_SET_VALUE)
            winreg.SetValueEx(key, "ПроцессМастер", 0, winreg.REG_SZ, command) # Обновленное имя
            winreg.CloseKey(key)
            status_label.config(text="Добавлено в автозагрузку.", fg="green")
            return True
        except Exception as e:
            status_label.config(text=f"Ошибка: {e}", fg="red")
            print(f"Error adding to startup: {e}")
            return False
    status_label.config(text="Только для Windows.", fg="orange")
    return False

def remove_from_startup():
    """Удаляет приложение из автозагрузки Windows через реестр."""
    if platform.system() == "Windows":
        try:
            key = winreg.OpenKey(winreg.HKEY_CURRENT_USER,
                                 r"SOFTWARE\Microsoft\Windows\CurrentVersion\Run",
                                 0, winreg.KEY_SET_VALUE)
            winreg.DeleteValue(key, "ПроцессМастер") # Обновленное имя
            winreg.CloseKey(key)
            status_label.config(text="Удалено из автозагрузки.", fg="green")
            return True
        except FileNotFoundError:
            status_label.config(text="Не найдено в автозагрузке.", fg="orange")
            print("Application not found in startup.")
            return True
        except Exception as e:
            status_label.config(text=f"Ошибка: {e}", fg="red")
            print(f"Error removing from startup: {e}")
            return False
    status_label.config(text="Только для Windows.", fg="orange")
    return False

def check_startup_status():
    """Проверяет, добавлено ли приложение в автозагрузку Windows."""
    if platform.system() == "Windows":
        try:
            key = winreg.OpenKey(winreg.HKEY_CURRENT_USER,
                                 r"SOFTWARE\Microsoft\Windows\CurrentVersion\Run",
                                 0, winreg.KEY_READ)
            winreg.QueryValueEx(key, "ПроцессМастер") # Обновленное имя
            winreg.CloseKey(key)
            return True
        except FileNotFoundError:
            return False
        except Exception as e:
            print(f"Error checking startup: {e}")
            return False
    return False

def run_on_startup_toggle():
    """Переключает состояние "Запуск при старте Windows"."""
    if startup_var.get():
        if not add_to_startup():
            startup_var.set(False) # Снимаем галочку, если не удалось
    else:
        if not remove_from_startup():
            startup_var.set(True) # Ставим галочку, если не удалось
    save_config() # Сохраняем изменение

def format_bytes_per_second(bytes_per_sec):
    """Форматирует скорость в читаемый формат (Б/с, КБ/с, МБ/с, ГБ/с)."""
    if bytes_per_sec < 1024:
        return f"{bytes_per_sec:.1f} Б/с"
    elif bytes_per_sec < 1024**2:
        return f"{bytes_per_sec / 1024:.1f} КБ/с"
    elif bytes_per_sec < 1024**3:
        return f"{bytes_per_sec / (1024**2):.1f} МБ/с"
    else:
        return f"{bytes_per_sec / (1024**3):.1f} ГБ/с"

def format_uptime(seconds):
    """Форматирует время работы системы."""
    days = int(seconds // (24 * 3600))
    seconds %= (24 * 3600)
    hours = int(seconds // 3600)
    seconds %= 3600
    minutes = int(seconds // 60)
    seconds %= 60
    
    parts = []
    if days > 0:
        parts.append(f"{days}д")
    if hours > 0:
        parts.append(f"{hours:02}ч")
    if minutes > 0:
        parts.append(f"{minutes:02}м")
    
    if not parts: # Если меньше минуты
        return f"{int(seconds):02}с"
    return " ".join(parts)

def display_error_message(message):
    """Отображает сообщение об ошибке в строке состояния и скрывает его через 5 секунд."""
    status_label.config(text=message, fg="red")
    status_label.after(5000, lambda: status_label.config(text="")) # Очищаем через 5 секунд

# --- Обновление интерфейса ---

def _run_ping_in_thread():
    """Запускает пинг в отдельном потоке, чтобы не блокировать GUI."""
    global ping_result, ping_in_progress
    if ping_in_progress:
        return
    ping_in_progress = True
    try:
        # Пингуем Google DNS (8.8.8.8)
        if platform.system() == "Windows":
            command = ["ping", "-n", "1", "8.8.8.8"]
        else: # Linux/macOS
            command = ["ping", "-c", "1", "8.8.8.8"]
        
        result = subprocess.run(command, capture_output=True, text=True, timeout=5)
        
        if result.returncode == 0:
            # Парсим вывод для получения времени пинга
            output = result.stdout
            if "time=" in output:
                start = output.find("time=") + 5
                end = output.find("ms", start)
                ping_time = float(output[start:end])
                ping_result = f"{ping_time:.0f} ms"
            else:
                ping_result = "Успешно (без времени)"
        else:
            ping_result = "Недоступно"
    except subprocess.TimeoutExpired:
        ping_result = "Таймаут"
    except Exception as e:
        ping_result = f"Ошибка: {e}"
    finally:
        ping_in_progress = False


def update_stats():
    """Обновляет все метрики в окне и всплывающей подсказке системного трея."""
    global stat_cycle_index, stat_display_messages, last_net_bytes_sent_per_nic, last_net_bytes_recv_per_nic, last_net_time, ping_result

    # CPU
    if show_cpu_var.get():
        cpu_frame.pack(pady=5, fill='x', padx=10)
        current_cpu_usage = get_cpu_usage()
        cpu_history.append(current_cpu_usage)
        smoothed_cpu_usage = sum(cpu_history) / len(cpu_history) if cpu_history else 0
        cpu_label.config(text=f'Загрузка CPU: {smoothed_cpu_usage:.1f}%')
        cpu_progress['value'] = smoothed_cpu_usage
        percentage_label_cpu.config(text='Проценты')
    else:
        cpu_frame.pack_forget()
        smoothed_cpu_usage = 0.0 # Для всплывающей подсказки, если скрыто
        cpu_label.config(text='')
        cpu_progress['value'] = 0
        percentage_label_cpu.config(text='')

    # Per-CPU Usage
    if show_per_cpu_usage_var.get():
        per_cpu_frame.pack(pady=5, fill='x', padx=10)
        per_cpu_usages = get_per_cpu_usage()
        
        if per_cpu_usages:
            for i, usage in enumerate(per_cpu_usages):
                if i < len(per_cpu_widgets): # Убеждаемся, что виджет существует для этого ядра
                    core_label, core_progress = per_cpu_widgets[i]
                    core_label.config(text=f'Ядро {i}: {usage:.1f}%')
                    core_progress['value'] = usage
    else:
        per_cpu_frame.pack_forget()


    # RAM
    if show_ram_var.get():
        ram_frame.pack(pady=5, fill='x', padx=10)
        ram_display_frame.pack(pady=2, anchor='w', padx=10)
        ram_percent, ram_used_gb, ram_total_gb = get_ram_usage()
        if ram_display_var.get() == 'percent':
            ram_label.config(text=f'Использование RAM: {ram_percent:.1f}%')
            ram_progress['value'] = ram_percent
            percentage_label_ram.config(text='Проценты')
        else: # 'gb'
            ram_label.config(text=f'Использование RAM: {ram_used_gb:.1f}/{ram_total_gb:.1f} ГБ')
            ram_progress['value'] = (ram_used_gb / ram_total_gb) * 100 if ram_total_gb > 0 else 0
            percentage_label_ram.config(text='ГБ')
    else:
        ram_frame.pack_forget()
        ram_display_frame.pack_forget()
        ram_percent = 0.0 # Для всплывающей подсказки, если скрыто
        ram_label.config(text='')
        ram_progress['value'] = 0
        percentage_label_ram.config(text='')

    # Disk
    if show_disk_var.get():
        disk_frame.pack(pady=5, fill='x', padx=10)
        disk_select_frame.pack(pady=2, anchor='w', padx=10)
        disk_display_frame.pack(pady=2, anchor='w', padx=10)
        selected_disk_path = disk_var.get()
        used_disk, total_disk, free_disk, disk_percent = get_disk_usage(selected_disk_path)
        if disk_display_var.get() == 'used':
            disk_label.config(text=f'Использование Диска ({selected_disk_path}): {used_disk:.1f}/{total_disk:.0f} ГБ')
            disk_progress['value'] = disk_percent
            gb_label_disk.config(text='ГБ (Использовано)')
        else: # 'free'
            disk_label.config(text=f'Свободно на Диске ({selected_disk_path}): {free_disk:.1f}/{total_disk:.0f} ГБ')
            disk_progress['value'] = (free_disk / total_disk) * 100 if total_disk > 0 else 0
            gb_label_disk.config(text='ГБ (Свободно)')
    else:
        disk_frame.pack_forget()
        disk_select_frame.pack_forget()
        disk_display_frame.pack_forget()
        disk_percent = 0.0 # Для всплывающей подсказки, если скрыто
        disk_label.config(text='')
        disk_progress['value'] = 0
        gb_label_disk.config(text='')

    # Disk I/O
    if show_disk_io_var.get():
        disk_io_frame.pack(pady=5, fill='x', padx=10)
        read_speed, write_speed = get_disk_io_speeds()
        disk_read_label.config(text=f'Disk Read: {read_speed}')
        disk_write_label.config(text=f'Disk Write: {write_speed}')
    else:
        disk_io_frame.pack_forget()
        disk_read_label.config(text='')
        disk_write_label.config(text='')

    # Network Activity
    if show_net_var.get():
        net_frame.pack(pady=5, fill='x', padx=10)
        try:
            current_net_io = psutil.net_io_counters(pernic=True)
            total_bytes_sent = sum(nic.bytes_sent for nic in current_net_io.values())
            total_bytes_recv = sum(nic.bytes_recv for nic in current_net_io.values())
            
            if 'All' not in last_net_bytes_sent_per_nic:
                last_net_bytes_sent_per_nic['All'] = total_bytes_sent
                last_net_bytes_recv_per_nic['All'] = total_bytes_recv

            upload_speed_str = "0 Б/с"
            download_speed_str = "0 Б/с"
            current_time = time.time()

            if last_net_time != 0 and (current_time - last_net_time) > 0:
                time_diff = current_time - last_net_time
                upload_speed_bytes_sec = (total_bytes_sent - last_net_bytes_sent_per_nic['All']) / time_diff
                download_speed_bytes_sec = (total_bytes_recv - last_net_bytes_recv_per_nic['All']) / time_diff
                
                upload_speed_str = format_bytes_per_second(upload_speed_bytes_sec)
                download_speed_str = format_bytes_per_second(download_speed_bytes_sec)
            
            last_net_bytes_sent_per_nic['All'] = total_bytes_sent
            last_net_bytes_recv_per_nic['All'] = total_bytes_recv
            last_net_time = current_time

            net_upload_label.config(text=f'Upload: {upload_speed_str}')
            net_download_label.config(text=f'Download: {download_speed_str}')
        except Exception as e:
            net_upload_label.config(text='Upload: N/A')
            net_download_label.config(text='Download: N/A')
            display_error_message(f"Ошибка сети: {e}")
    else:
        net_frame.pack_forget()
        upload_speed_str = "N/A" # Для всплывающей подсказки, если скрыто
        download_speed_str = "N/A" # Для всплывающей подсказки, если скрыто
        net_upload_label.config(text='')
        net_download_label.config(text='')

    # Network Latency (Ping)
    if show_network_latency_var.get():
        network_latency_frame.pack(pady=5, fill='x', padx=10)
        if not ping_in_progress:
            threading.Thread(target=_run_ping_in_thread, daemon=True).start()
        network_latency_label.config(text=f'Пинг (8.8.8.8): {ping_result if ping_result else "..."}')
    else:
        network_latency_frame.pack_forget()
        network_latency_label.config(text='')
        ping_result = None # Для всплывающей подсказки, если скрыто

    # CPU Temperature
    cpu_temp = None
    if show_cpu_temp_var.get():
        cpu_temp_frame.pack(pady=5, fill='x', padx=10)
        cpu_temp = get_cpu_temperature()
        if cpu_temp is not None:
            cpu_temp_label.config(text=f'Температура CPU: {cpu_temp:.1f}°C')
        else:
            cpu_temp_label.config(text='Температура CPU: N/A')
    else:
        cpu_temp_frame.pack_forget()
        cpu_temp_label.config(text='')

    # Fan Speed
    fan_speed = None
    if show_fan_speed_var.get():
        fan_speed_frame.pack(pady=5, fill='x', padx=10)
        fan_speed = get_fan_speed()
        if fan_speed is not None:
            fan_speed_label.config(text=f'Скорость вентилятора: {fan_speed} RPM')
        else:
            fan_speed_label.config(text='Скорость вентилятора: N/A')
    else:
        fan_speed_frame.pack_forget()
        fan_speed_label.config(text='')


    # Total Processes
    total_processes = "N/A"
    if show_total_processes_var.get():
        total_processes_frame.pack(pady=5, fill='x', padx=10)
        total_processes, _ = get_process_counts() # Получаем только общее количество
        total_processes_label.config(text=f'Всего процессов: {total_processes}')
    else:
        total_processes_frame.pack_forget()
        total_processes_label.config(text='')

    # User Processes
    user_processes = "N/A"
    if show_user_processes_var.get():
        user_processes_frame.pack(pady=5, fill='x', padx=10)
        _, user_processes = get_process_counts() # Получаем только пользовательские процессы
        user_processes_label.config(text=f'Пользовательских процессов: {user_processes}')
    else:
        user_processes_frame.pack_forget()
        user_processes_label.config(text='')

    # Process States
    if show_process_states_var.get():
        process_states_frame.pack(pady=5, fill='x', padx=10)
        running, sleeping, zombie, stopped, other = get_process_states()
        process_states_label.config(text=f'Процессы: Зап.:{running}, Сп.:{sleeping}, Зомби:{zombie}, Ост.:{stopped}, Др.:{other}')
    else:
        process_states_frame.pack_forget()
        process_states_label.config(text='')

    # Uptime
    if show_uptime_var.get():
        uptime_frame.pack(pady=5, fill='x', padx=10)
        try:
            boot_time_timestamp = psutil.boot_time()
            uptime_seconds = time.time() - boot_time_timestamp
            uptime_str = format_uptime(uptime_seconds)
            uptime_label.config(text=f'Uptime: {uptime_str}')
        except Exception as e:
            uptime_label.config(text='Uptime: N/A')
            display_error_message(f"Ошибка Uptime: {e}")
    else:
        uptime_frame.pack_forget()
        uptime_str = "N/A" # Для всплывающей подсказки, если скрыто
        uptime_label.config(text='')

    # CPU Cores and Threads
    physical_cores = "N/A"
    logical_cores = "N/A"
    if show_physical_cores_var.get() or show_logical_cores_var.get():
        physical_cores, logical_cores = get_cpu_info()
        
        if show_physical_cores_var.get():
            physical_cores_frame.pack(pady=5, fill='x', padx=10)
            physical_cores_label.config(text=f'Физ. ядер: {physical_cores}')
        else:
            physical_cores_frame.pack_forget()
            physical_cores_label.config(text='')

        if show_logical_cores_var.get():
            logical_cores_frame.pack(pady=5, fill='x', padx=10)
            logical_cores_label.config(text=f'Лог. потоков: {logical_cores}')
        else:
            logical_cores_frame.pack_forget()
            logical_cores_label.config(text='')
    else:
        physical_cores_frame.pack_forget()
        logical_cores_frame.pack_forget()
        physical_cores_label.config(text='')
        logical_cores_label.config(text='')

    # CPU Frequency
    current_freq, min_freq, max_freq = None, None, None
    if show_cpu_freq_var.get():
        cpu_freq_frame.pack(pady=5, fill='x', padx=10)
        current_freq, min_freq, max_freq = get_cpu_frequency()
        if current_freq is not None:
            cpu_freq_label.config(text=f'Частота CPU: {current_freq:.0f} МГц (Мин: {min_freq:.0f}, Макс: {max_freq:.0f})')
        else:
            cpu_freq_label.config(text='Частота CPU: N/A')
    else:
        cpu_freq_frame.pack_forget()
        cpu_freq_label.config(text='')

    # Battery Status
    battery_percent = None
    battery_status = None
    battery_time_left = None
    if show_battery_status_var.get():
        battery_status_frame.pack(pady=5, fill='x', padx=10)
        battery_percent, battery_status, battery_time_left = get_battery_status()
        if battery_percent is not None:
            battery_status_label.config(text=f'Батарея: {battery_percent:.1f}% ({battery_status}, {battery_time_left})')
        else:
            battery_status_label.config(text='Батарея: N/A')
    else:
        battery_status_frame.pack_forget()
        battery_status_label.config(text='')

    # CPU Times
    cpu_user_time = None
    cpu_system_time = None
    cpu_idle_time = None
    if show_cpu_times_var.get():
        cpu_times_frame.pack(pady=5, fill='x', padx=10)
        cpu_user_time, cpu_system_time, cpu_idle_time = get_cpu_times()
        if cpu_user_time is not None:
            cpu_times_label.config(text=f'CPU Time: User {cpu_user_time:.1f}s, System {cpu_system_time:.1f}s, Idle {cpu_idle_time:.1f}s')
        else:
            cpu_times_label.config(text='CPU Time: N/A')
    else:
        cpu_times_frame.pack_forget()
        cpu_times_label.config(text='')

    # Swap Usage
    swap_percent = 0.0
    if show_swap_usage_var.get():
        swap_usage_frame.pack(pady=5, fill='x', padx=10)
        swap_percent = get_swap_usage()
        swap_usage_label.config(text=f'Swap: {swap_percent:.1f}%')
    else:
        swap_usage_frame.pack_forget()
        swap_usage_label.config(text='')

    # Top RAM Process
    top_ram_process_name = "N/A"
    top_ram_percent = 0.0
    if show_top_ram_process_var.get():
        top_ram_process_frame.pack(pady=5, fill='x', padx=10)
        top_ram_process_name, top_ram_percent = get_top_ram_process()
        if top_ram_process_name != "N/A":
            top_ram_process_label.config(text=f'Топ RAM: {top_ram_process_name} ({top_ram_percent:.1f}%)')
        else:
            top_ram_process_label.config(text='Топ RAM: Нет активных')
    else:
        top_ram_process_frame.pack_forget()
        top_ram_process_label.config(text='')


    # Top CPU Process
    if show_top_process_var.get():
        top_process_frame.pack(pady=5, fill='x', padx=10)
        top_cpu_process_name = "N/A"
        top_cpu_percent = 0.0
        try:
            processes = []
            # Используем interval=0.1 для cpu_percent для более точных мгновенных значений
            for p in psutil.process_iter(['pid', 'name', 'cpu_percent']):
                try:
                    processes.append(p.info)
                except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                    pass
            
            if processes:
                # Сортируем по cpu_percent
                processes.sort(key=lambda x: x['cpu_percent'], reverse=True)
                if processes[0]['cpu_percent'] > 0: # Показываем только если процесс действительно что-то потребляет
                    top_cpu_process_name = processes[0]['name']
                    top_cpu_percent = processes[0]['cpu_percent']
                    top_cpu_process_label.config(text=f'Топ CPU: {top_cpu_process_name} ({top_cpu_percent:.1f}%)')
                else:
                    top_cpu_process_label.config(text='Топ CPU: Нет активных')
            else:
                top_cpu_process_label.config(text='Топ CPU: N/A')
        except Exception as e:
            top_cpu_process_label.config(text='Топ CPU: Ошибка')
            display_error_message(f"Ошибка топ-процессов: {e}")
    else:
        top_process_frame.pack_forget()
        top_cpu_process_name = "N/A" # Для всплывающей подсказки, если скрыто
        top_cpu_percent = 0.0 # Для всплывающей подсказки, если скрыто
        top_cpu_process_label.config(text='')

    # App Uptime
    app_uptime_str = "N/A"
    if show_app_uptime_var.get():
        app_uptime_frame.pack(pady=5, fill='x', padx=10)
        app_uptime_seconds = time.time() - app_start_time
        app_uptime_str = format_uptime(app_uptime_seconds)
        app_uptime_label.config(text=f'Время работы приложения: {app_uptime_str}')
    else:
        app_uptime_frame.pack_forget()
        app_uptime_label.config(text='')

    # Real Time
    current_time_str = "N/A"
    if show_real_time_var.get():
        real_time_frame.pack(pady=5, fill='x', padx=10)
        current_time_str = time.strftime("%H:%M:%S")
        real_time_label.config(text=f'Текущее время: {current_time_str}')
    else:
        real_time_frame.pack_forget()
        real_time_label.config(text='')

    # --- Обновление всплывающей подсказки системного трея ---
    stat_display_messages = []
    if show_cpu_var.get(): stat_display_messages.append(f'CPU: {smoothed_cpu_usage:.1f}%')
    if show_ram_var.get(): stat_display_messages.append(f'RAM: {ram_percent:.1f}%')
    if show_disk_var.get(): stat_display_messages.append(f'Disk: {disk_percent:.1f}% ({disk_var.get()})')
    if show_disk_io_var.get():
        read_speed, write_speed = get_disk_io_speeds() # Получаем последние значения для всплывающей подсказки
        stat_display_messages.append(f'Disk I/O: R:{read_speed}, W:{write_speed}')
    # Removed network and ping from tooltip
    # Removed CPU Temp and Fan Speed from tooltip
    if show_total_processes_var.get(): stat_display_messages.append(f'Всего процессов: {total_processes}')
    if show_user_processes_var.get(): stat_display_messages.append(f'Пользовательских процессов: {user_processes}')
    if show_process_states_var.get(): stat_display_messages.append(f'Процессы: Зап.:{running}, Сп.:{sleeping}') # Упрощено для всплывающей подсказки
    if show_uptime_var.get(): stat_display_messages.append(f'Uptime: {uptime_str}')
    if show_physical_cores_var.get(): stat_display_messages.append(f'Физ. ядер: {physical_cores}')
    if show_logical_cores_var.get(): stat_display_messages.append(f'Лог. потоков: {logical_cores}')
    if show_cpu_freq_var.get() and current_freq is not None: stat_display_messages.append(f'Частота CPU: {current_freq:.0f} МГц')
    if show_battery_status_var.get() and battery_percent is not None: stat_display_messages.append(f'Батарея: {battery_percent:.1f}%')
    if show_cpu_times_var.get() and cpu_user_time is not None: stat_display_messages.append(f'CPU Time: U {cpu_user_time:.1f}s, S {cpu_system_time:.1f}s, I {cpu_idle_time:.1f}s')
    if show_swap_usage_var.get(): stat_display_messages.append(f'Swap: {swap_percent:.1f}%')
    if show_top_ram_process_var.get() and top_ram_process_name != "N/A" and top_ram_process_name != "Нет активных":
        stat_display_messages.append(f'Топ RAM: {top_ram_process_name} ({top_ram_percent:.1f}%)')
    if show_top_process_var.get() and top_cpu_process_name != "N/A" and top_cpu_process_name != "Нет активных":
        stat_display_messages.append(f'Топ CPU: {top_cpu_process_name} ({top_cpu_percent:.1f}%)')
    if show_app_uptime_var.get(): stat_display_messages.append(f'Время работы приложения: {app_uptime_str}')
    if show_real_time_var.get(): stat_display_messages.append(f'Время: {current_time_str}')


    if stat_display_messages:
        current_tooltip_content = stat_display_messages[stat_cycle_index]
        stat_cycle_index = (stat_cycle_index + 1) % len(stat_display_messages)

        # Формируем всплывающую подсказку с именем приложения и текущей метрикой
        full_tooltip_text = f"ПроцессМастер: {current_tooltip_content}" # Обновленное имя

        if PYSTRAY_AVAILABLE and tray_icon and tray_icon.visible:
            tray_icon.tooltip = full_tooltip_text
    else:
        full_tooltip_text = "ПроцессМастер" # По умолчанию, если данных нет

    # Планируем следующее обновление через выбранный интервал
    update_interval_ms = int(update_interval_var.get()) * 1000
    window.after(update_interval_ms, update_stats)

# --- Функции системного трея ---

def create_tray_icon():
    """Создает и запускает иконку системного трея."""
    global tray_icon
    if not PYSTRAY_AVAILABLE:
        return

    # Создаем более красивую иконку (стилизованное перо)
    icon_image = Image.new('RGBA', (64, 64), (0, 0, 0, 0)) # Прозрачный фон
    draw = ImageDraw.Draw(icon_image)

    # Рисуем стилизованное перо
    # Основная линия пера
    draw.line((20, 10, 30, 50), fill='#61dafb', width=4)
    draw.line((30, 50, 40, 10), fill='#61dafb', width=4)
    
    # Детали пера
    draw.line((25, 20, 15, 25), fill='#61dafb', width=2)
    draw.line((25, 25, 15, 30), fill='#61dafb', width=2)
    draw.line((25, 30, 15, 35), fill='#61dafb', width=2)

    draw.line((35, 20, 45, 25), fill='#61dafb', width=2)
    draw.line((35, 25, 45, 30), fill='#61dafb', width=2)
    draw.line((35, 30, 45, 35), fill='#61dafb', width=2)

    menu = (
        # Используем window.after для вызова deiconify в основном потоке Tkinter
        pystray_MenuItem('Показать монитор', lambda icon, item: window.after(0, lambda: (window.deiconify(), setattr(icon, 'visible', False)))),
        pystray_MenuItem('Выход', lambda icon, item: exit_application())
    )

    # Инициализируем всплывающую подсказку с базовым именем, она будет обновляться функцией update_stats
    tray_icon = pystray_Icon("ПроцессМастер", icon_image, "ПроцессМастер", menu) # Обновленное имя
    tray_icon.run() # Эта функция блокирующая, поэтому запускаем в отдельном потоке

# --- Настройка главного окна ---

window = tk.Tk()
window.title('ПроцессМастер') # Обновленное имя
window.geometry('350x650') # Увеличена высота для новых полей, но сделана изменяемой
window.resizable(True, True) # Разрешаем изменение размера окна
window.overrideredirect(False) # Обеспечиваем нативные декорации окна и видимость на панели задач

# Устанавливаем темную тему и синюю рамку
window.configure(bg='#282c34', bd=2, relief='solid', highlightbackground='#61dafb', highlightthickness=1)

# Стили для виджетов ttk (полосы прогресса)
style = ttk.Style()
style.theme_use('clam')
style.configure("blue.Horizontal.TProgressbar",
                troughcolor='#44475a',
                background='#61dafb',
                bordercolor='#61dafb',
                lightcolor='#61dafb',
                darkcolor='#61dafb',
                thickness=15)

# Стиль для меток
label_font = ('Inter', 12, 'bold')
label_fg = '#f8f8f2'
label_bg = '#282c34'

# --- BooleanVars for visibility control (used in settings_window) ---
# Moved these to before load_config() call
ram_display_var = tk.StringVar(value='percent')
disk_paths = [p.mountpoint for p in psutil.disk_partitions()]
disk_var = tk.StringVar(value=disk_paths[0] if disk_paths else 'N/A')
net_nic_options = ['All'] # Keep for compatibility, but not used for display
net_nic_var = tk.StringVar(value='All') # Keep for compatibility, but not used for display

topmost_var = tk.BooleanVar(value=True)
startup_var = tk.BooleanVar(value=False) # Will be updated by check_startup_status()
update_interval_var = tk.StringVar(value='5') # Default 5 seconds

show_cpu_var = tk.BooleanVar(value=True)
show_ram_var = tk.BooleanVar(value=True)
show_disk_var = tk.BooleanVar(value=True)
show_net_var = tk.BooleanVar(value=False) # По умолчанию False
show_total_processes_var = tk.BooleanVar(value=True)
show_user_processes_var = tk.BooleanVar(value=True)
show_uptime_var = tk.BooleanVar(value=True)
show_cpu_freq_var = tk.BooleanVar(value=True)
show_top_process_var = tk.BooleanVar(value=True)
show_physical_cores_var = tk.BooleanVar(value=True)
show_logical_cores_var = tk.BooleanVar(value=True)
show_swap_usage_var = tk.BooleanVar(value=True)
show_top_ram_process_var = tk.BooleanVar(value=True)
show_app_uptime_var = tk.BooleanVar(value=True)
show_real_time_var = tk.BooleanVar(value=True)
show_cpu_temp_var = tk.BooleanVar(value=False) # По умолчанию False
show_fan_speed_var = tk.BooleanVar(value=False) # По умолчанию False
show_battery_status_var = tk.BooleanVar(value=True)
show_cpu_times_var = tk.BooleanVar(value=True)
show_per_cpu_usage_var = tk.BooleanVar(value=True)
show_network_latency_var = tk.BooleanVar(value=False) # По умолчанию False
show_process_states_var = tk.BooleanVar(value=True)
show_disk_io_var = tk.BooleanVar(value=True) # Новая переменная

# --- Load settings on startup ---
initial_config_data = load_config() # Загружаем все профили и текущий активный
# Settings are already applied within load_config

# Update startup_var after loading config
startup_var.set(check_startup_status())

# Set "always on top" on startup based on loaded config
window.attributes('-topmost', topmost_var.get())


# --- Create Canvas for scrolling ---
main_canvas = tk.Canvas(window, bg=label_bg, highlightthickness=0)
main_canvas.pack(side='left', fill='both', expand=True)

# --- Create Scrollbar and bind it to Canvas ---
scrollbar = ttk.Scrollbar(window, orient='vertical', command=main_canvas.yview)
scrollbar.pack(side='right', fill='y')

main_canvas.configure(yscrollcommand=scrollbar.set)
# Bind mouse wheel for scrolling
main_canvas.bind_all("<MouseWheel>", lambda event: main_canvas.yview_scroll(int(-1*(event.delta/120)), "units"))


# --- Create Frame inside Canvas, where all widgets will be added ---
content_frame = tk.Frame(main_canvas, bg=label_bg)
main_canvas.create_window((0, 0), window=content_frame, anchor='nw')

# --- Виджеты для CPU ---
cpu_frame = tk.Frame(content_frame, bg=label_bg)
# cpu_frame.pack(pady=5, fill='x', padx=10) # Упаковывается условно в update_stats

cpu_label = tk.Label(cpu_frame, text='Загрузка CPU: --%', font=label_font, fg=label_fg, bg=label_bg)
cpu_label.grid(row=0, column=0, sticky='w', padx=5)

cpu_progress = ttk.Progressbar(cpu_frame, style="blue.Horizontal.TProgressbar", orient='horizontal', mode='determinate')
cpu_progress.grid(row=0, column=1, sticky='ew', padx=5)
cpu_frame.grid_columnconfigure(1, weight=1)

percentage_label_cpu = tk.Label(cpu_frame, text='Проценты', font=('Inter', 10), fg='#999999', bg=label_bg)
percentage_label_cpu.grid(row=1, column=0, columnspan=2, sticky='w', padx=5)

# --- Виджеты для использования по ядрам CPU ---
per_cpu_frame = tk.Frame(content_frame, bg=label_bg)
# per_cpu_frame.pack(pady=5, fill='x', padx=10) # Упаковывается условно в update_stats

# Глобальный список для хранения пар (Метка, Полоса прогресса) для каждого ядра
per_cpu_widgets = []
# Предварительно создаем метки и полосы прогресса для каждого ядра
num_logical_cores = psutil.cpu_count(logical=True)
if num_logical_cores:
    tk.Label(per_cpu_frame, text='Загрузка по ядрам:', font=label_font, fg=label_fg, bg=label_bg).pack(anchor='w')
    for i in range(num_logical_cores):
        core_frame = tk.Frame(per_cpu_frame, bg=label_bg)
        core_frame.pack(fill='x', padx=5, pady=1)
        core_label = tk.Label(core_frame, text=f'Ядро {i}: --%', font=('Inter', 10), fg=label_fg, bg=label_bg)
        core_label.pack(side='left', anchor='w')
        core_progress = ttk.Progressbar(core_frame, style="blue.Horizontal.TProgressbar", orient='horizontal', mode='determinate', value=0)
        core_progress.pack(side='right', fill='x', expand=True, padx=5)
        per_cpu_widgets.append((core_label, core_progress))


# --- Виджеты для RAM ---
ram_frame = tk.Frame(content_frame, bg=label_bg)
# ram_frame.pack(pady=5, fill='x', padx=10) # Упаковывается условно в update_stats

ram_label = tk.Label(ram_frame, text='Использование RAM: --%', font=label_font, fg=label_fg, bg=label_bg)
ram_label.grid(row=0, column=0, sticky='w', padx=5)

ram_progress = ttk.Progressbar(ram_frame, style="blue.Horizontal.TProgressbar", orient='horizontal', mode='determinate')
ram_progress.grid(row=0, column=1, sticky='ew', padx=5)
ram_frame.grid_columnconfigure(1, weight=1)

percentage_label_ram = tk.Label(ram_frame, text='Проценты', font=('Inter', 10), fg='#999999', bg=label_bg)
percentage_label_ram.grid(row=1, column=0, columnspan=2, sticky='w', padx=5)

ram_display_frame = tk.Frame(content_frame, bg=label_bg)
# ram_display_frame.pack(pady=2, anchor='w', padx=10) # Упаковывается условно в update_stats

ram_percent_radio = tk.Radiobutton(ram_display_frame, text='Проценты', variable=ram_display_var, value='percent',
                                   font=('Inter', 10), fg=label_fg, bg=label_bg, selectcolor=label_bg,
                                   activebackground=label_bg, activeforeground='#61dafb', command=lambda: (update_stats(), save_config()))
ram_percent_radio.pack(side='left', padx=5)

ram_gb_radio = tk.Radiobutton(ram_display_frame, text='ГБ', variable=ram_display_var, value='gb',
                              font=('Inter', 10), fg=label_fg, bg=label_bg, selectcolor=label_bg,
                              activebackground=label_bg, activeforeground='#61dafb', command=lambda: (update_stats(), save_config()))
ram_gb_radio.pack(side='left', padx=5)


# --- Виджеты для Диска ---
disk_frame = tk.Frame(content_frame, bg=label_bg)
# disk_frame.pack(pady=5, fill='x', padx=10) # Упаковывается условно в update_stats

disk_label = tk.Label(disk_frame, text='Использование Диска (C:\\): --/-- ГБ', font=label_font, fg=label_fg, bg=label_bg)
disk_label.grid(row=0, column=0, sticky='w', padx=5)

disk_progress = ttk.Progressbar(disk_frame, style="blue.Horizontal.TProgressbar", orient='horizontal', mode='determinate')
disk_progress.grid(row=0, column=1, sticky='ew', padx=5)
disk_frame.grid_columnconfigure(1, weight=1)

gb_label_disk = tk.Label(disk_frame, text='ГБ', font=('Inter', 10), fg='#999999', bg=label_bg)
gb_label_disk.grid(row=1, column=0, columnspan=2, sticky='w', padx=5)

disk_select_frame = tk.Frame(content_frame, bg=label_bg)
# disk_select_frame.pack(pady=2, anchor='w', padx=10) # Упаковывается условно в update_stats

disk_combobox_label = tk.Label(disk_select_frame, text='Выбрать диск:', font=('Inter', 10), fg=label_fg, bg=label_bg)
disk_combobox_label.pack(side='left', padx=5)

disk_combobox = ttk.Combobox(disk_select_frame, textvariable=disk_var, values=disk_paths, state='readonly',
                             font=('Inter', 10), width=10)
disk_combobox.pack(side='left', padx=5)
disk_combobox.bind("<<ComboboxSelected>>", lambda event: (update_stats(), save_config())) # Обновляем при выборе диска и сохраняем


disk_display_var = tk.StringVar(value='used')
disk_display_frame = tk.Frame(content_frame, bg=label_bg)
# disk_display_frame.pack(pady=2, anchor='w', padx=10) # Упаковывается условно в update_stats

disk_used_radio = tk.Radiobutton(disk_display_frame, text='Использовано', variable=disk_display_var, value='used',
                                 font=('Inter', 10), fg=label_fg, bg=label_bg, selectcolor=label_bg,
                                 activebackground=label_bg, activeforeground='#61dafb', command=lambda: (update_stats(), save_config()))
disk_used_radio.pack(side='left', padx=5)

disk_free_radio = tk.Radiobutton(disk_display_frame, text='Свободно', variable=disk_display_var, value='free',
                                 font=('Inter', 10), fg=label_fg, bg=label_bg, selectcolor=label_bg,
                                 activebackground=label_bg, activeforeground='#61dafb', command=lambda: (update_stats(), save_config()))
disk_free_radio.pack(side='left', padx=5)

# --- Виджеты для дискового ввода-вывода ---
disk_io_frame = tk.Frame(content_frame, bg=label_bg)
# disk_io_frame.pack(pady=5, fill='x', padx=10) # Упаковывается условно в update_stats

disk_read_label = tk.Label(disk_io_frame, text='Disk Read: --', font=label_font, fg=label_fg, bg=label_bg)
disk_read_label.pack(side='left', padx=5)

disk_write_label = tk.Label(disk_io_frame, text='Disk Write: --', font=label_font, fg=label_fg, bg=label_bg)
disk_write_label.pack(side='right', padx=5)


# --- Виджеты для сетевой активности ---
net_frame = tk.Frame(content_frame, bg=label_bg)
# net_frame.pack(pady=5, fill='x', padx=10) # Упаковывается условно в update_stats

net_upload_label = tk.Label(net_frame, text='Upload: --', font=label_font, fg=label_fg, bg=label_bg)
net_upload_label.pack(side='left', padx=5)

net_download_label = tk.Label(net_frame, text='Download: --', font=label_font, fg=label_fg, bg=label_bg)
net_download_label.pack(side='right', padx=5)

# --- Виджеты для сетевой задержки (Пинг) ---
network_latency_frame = tk.Frame(content_frame, bg=label_bg)
# network_latency_frame.pack(pady=5, fill='x', padx=10) # Упаковывается условно в update_stats

network_latency_label = tk.Label(network_latency_frame, text='Пинг (8.8.8.8): N/A', font=label_font, fg=label_fg, bg=label_bg)
network_latency_label.pack(side='left', padx=5)


# --- Виджеты для температуры CPU ---
cpu_temp_frame = tk.Frame(content_frame, bg=label_bg)
# cpu_temp_frame.pack(pady=5, fill='x', padx=10) # Упаковывается условно в update_stats
cpu_temp_label = tk.Label(cpu_temp_frame, text='Температура CPU: N/A', font=label_font, fg=label_fg, bg=label_bg)
cpu_temp_label.pack(side='left', padx=5)

# --- Виджеты для скорости вентилятора ---
fan_speed_frame = tk.Frame(content_frame, bg=label_bg)
# fan_speed_frame.pack(pady=5, fill='x', padx=10) # Упаковывается условно в update_stats
fan_speed_label = tk.Label(fan_speed_frame, text='Скорость вентилятора: N/A', font=label_font, fg=label_fg, bg=label_bg)
fan_speed_label.pack(side='left', padx=5)


# --- Виджеты для общего количества процессов ---
total_processes_frame = tk.Frame(content_frame, bg=label_bg)
# total_processes_frame.pack(pady=5, fill='x', padx=10) # Упаковывается условно в update_stats

total_processes_label = tk.Label(total_processes_frame, text='Всего процессов: --', font=label_font, fg=label_fg, bg=label_bg)
total_processes_label.pack(side='left', padx=5)

# --- Виджеты для пользовательских процессов ---
user_processes_frame = tk.Frame(content_frame, bg=label_bg)
# user_processes_frame.pack(pady=5, fill='x', padx=10) # Упаковывается условно в update_stats

user_processes_label = tk.Label(user_processes_frame, text='Пользовательских процессов: --', font=label_font, fg=label_fg, bg=label_bg)
user_processes_label.pack(side='left', padx=5)

# --- Виджеты для состояний процессов ---
process_states_frame = tk.Frame(content_frame, bg=label_bg)
# process_states_frame.pack(pady=5, fill='x', padx=10) # Упаковывается условно в update_stats

process_states_label = tk.Label(process_states_frame, text='Процессы: Зап.:--, Сп.:--, Зомби:--, Ост.:--, Др.:--', font=label_font, fg=label_fg, bg=label_bg)
process_states_label.pack(side='left', padx=5)


# --- Виджеты для времени работы системы ---
uptime_frame = tk.Frame(content_frame, bg=label_bg)
# uptime_frame.pack(pady=5, fill='x', padx=10) # Упаковывается условно в update_stats

uptime_label = tk.Label(uptime_frame, text='Uptime: --', font=label_font, fg=label_fg, bg=label_bg)
uptime_label.pack(side='left', padx=5)

# --- Виджеты для физических ядер CPU ---
physical_cores_frame = tk.Frame(content_frame, bg=label_bg)
# physical_cores_frame.pack(pady=5, fill='x', padx=10) # Упаковывается условно в update_stats

physical_cores_label = tk.Label(physical_cores_frame, text='Физ. ядер: --', font=label_font, fg=label_fg, bg=label_bg)
physical_cores_label.pack(side='left', padx=5)

# --- Виджеты для логических ядер CPU (потоков) ---
logical_cores_frame = tk.Frame(content_frame, bg=label_bg)
# logical_cores_frame.pack(pady=5, fill='x', padx=10) # Упаковывается условно в update_stats

logical_cores_label = tk.Label(logical_cores_frame, text='Лог. потоков: --', font=label_font, fg=label_fg, bg=label_bg)
logical_cores_label.pack(side='left', padx=5)

# --- Виджеты для частоты CPU ---
cpu_freq_frame = tk.Frame(content_frame, bg=label_bg)
# cpu_freq_frame.pack(pady=5, fill='x', padx=10) # Упаковывается условно в update_stats

cpu_freq_label = tk.Label(cpu_freq_frame, text='Частота CPU: N/A', font=label_font, fg=label_fg, bg=label_bg)
cpu_freq_label.pack(side='left', padx=5)


# --- Виджеты для статуса батареи ---
battery_status_frame = tk.Frame(content_frame, bg=label_bg)
# battery_status_frame.pack(pady=5, fill='x', padx=10) # Упаковывается условно в update_stats

battery_status_label = tk.Label(battery_status_frame, text='Батарея: N/A', font=label_font, fg=label_fg, bg=label_bg)
battery_status_label.pack(side='left', padx=5)

# --- Виджеты для времени CPU ---
cpu_times_frame = tk.Frame(content_frame, bg=label_bg)
# cpu_times_frame.pack(pady=5, fill='x', padx=10) # Упаковывается условно в update_stats

cpu_times_label = tk.Label(cpu_times_frame, text='CPU Time: N/A', font=label_font, fg=label_fg, bg=label_bg)
cpu_times_label.pack(side='left', padx=5)


# --- Виджеты для использования Swap ---
swap_usage_frame = tk.Frame(content_frame, bg=label_bg)
# swap_usage_frame.pack(pady=5, fill='x', padx=10) # Упаковывается условно в update_stats

swap_usage_label = tk.Label(swap_usage_frame, text='Swap: N/A', font=label_font, fg=label_fg, bg=label_bg)
swap_usage_label.pack(side='left', padx=5)

# --- Виджет для топ-процесса RAM ---
top_ram_process_frame = tk.Frame(content_frame, bg=label_bg)
# top_ram_process_frame.pack(pady=5, fill='x', padx=10) # Упаковывается условно в update_stats

top_ram_process_label = tk.Label(top_ram_process_frame, text='Топ RAM: N/A', font=label_font, fg=label_fg, bg=label_bg)
top_ram_process_label.pack(side='left', padx=5)


# --- Виджет для топ-процесса CPU ---
top_process_frame = tk.Frame(content_frame, bg=label_bg)
# top_process_frame.pack(pady=5, fill='x', padx=10) # Упаковывается условно в update_stats

top_cpu_process_label = tk.Label(top_process_frame, text='Топ CPU: N/A', font=label_font, fg=label_fg, bg=label_bg)
top_cpu_process_label.pack(side='left', padx=5)

# --- Виджет для времени работы приложения ---
app_uptime_frame = tk.Frame(content_frame, bg=label_bg)
# app_uptime_frame.pack(pady=5, fill='x', padx=10) # Упаковывается условно в update_stats

app_uptime_label = tk.Label(app_uptime_frame, text='Время работы приложения: --', font=label_font, fg=label_fg, bg=label_bg)
app_uptime_label.pack(side='left', padx=5)

# --- Виджет для текущего времени ---
real_time_frame = tk.Frame(content_frame, bg=label_bg)
# real_time_frame.pack(pady=5, fill='x', padx=10) # Упаковывается условно в update_stats

real_time_label = tk.Label(real_time_frame, text='Текущее время: --', font=label_font, fg=label_fg, bg=label_bg)
real_time_label.pack(side='left', padx=5)


# --- Чекбокс "Поверх всех окон" ---
topmost_checkbox = tk.Checkbutton(content_frame, text='Поверх всех окон', variable=topmost_var,
                                  command=toggle_topmost, font=label_font,
                                  fg=label_fg, bg=label_bg, selectcolor=label_bg,
                                  activebackground=label_bg, activeforeground='#61dafb')
topmost_checkbox.pack(pady=10, anchor='w', padx=10)

# --- Чекбокс "Запуск при старте Windows" ---
startup_checkbox = tk.Checkbutton(content_frame, text='Запуск при старте Windows', variable=startup_var,
                                  command=run_on_startup_toggle, font=label_font,
                                  fg=label_fg, bg=label_bg, selectcolor=label_bg,
                                  activebackground=label_bg, activeforeground='#61dafb')
startup_checkbox.pack(pady=5, anchor='w', padx=10)

# --- Выбор интервала обновления ---
update_interval_options = ['1', '2', '3', '5', '10'] # Секунды

interval_frame = tk.Frame(content_frame, bg=label_bg)
interval_frame.pack(pady=5, anchor='w', padx=10)

interval_label = tk.Label(interval_frame, text='Интервал обновления (сек):', font=('Inter', 10), fg=label_fg, bg=label_bg)
interval_label.pack(side='left', padx=5)

interval_combobox = ttk.Combobox(interval_frame, textvariable=update_interval_var, values=update_interval_options, state='readonly',
                                 font=('Inter', 10), width=5)
interval_combobox.pack(side='left', padx=5)
interval_combobox.bind("<<ComboboxSelected>>", lambda event: (update_stats(), save_config())) # Обновляем при выборе и сохраняем

# --- Кнопка настроек ---
settings_button = tk.Button(content_frame, text='Настройки', font=label_font, fg='white', bg='#61dafb', # Синяя кнопка
                            activebackground='#4fa0d2', activeforeground='white',
                            bd=0, command=lambda: open_settings_window(), width=15, height=1)
settings_button.pack(pady=10)


# --- Метка состояния для сообщений о запуске и ошибках ---
status_label = tk.Label(content_frame, text="", font=('Inter', 9), fg='white', bg=label_bg)
status_label.pack(pady=2, anchor='w', padx=10)


def update_profile_dropdown(profile_combobox, profile_status_label):
    """Обновляет выпадающий список профилей."""
    full_config = load_config() # Загружаем полную конфигурацию
    profile_names = list(full_config.get('profiles', {}).keys())
    profile_combobox['values'] = profile_names
    current_active_profile = full_config.get('current_profile', 'Default')
    if current_active_profile in profile_names:
        profile_combobox.set(current_active_profile)
    elif profile_names:
        profile_combobox.set(profile_names[0]) # Если текущий не найден, выбираем первый
    else:
        profile_combobox.set("") # Если профилей нет

def save_profile_action(profile_name_entry, profile_combobox, profile_status_label):
    """Сохраняет текущие настройки в новый или существующий профиль."""
    profile_name = profile_name_entry.get().strip()
    if not profile_name:
        profile_status_label.config(text="Имя профиля не может быть пустым!", fg="red")
        return

    save_config(profile_name=profile_name)
    update_profile_dropdown(profile_combobox, profile_status_label)
    profile_status_label.config(text=f"Профиль '{profile_name}' сохранен.", fg="green")
    update_stats() # Обновляем главное окно, чтобы убедиться, что все синхронизировано

def load_profile_action(profile_combobox, profile_status_label):
    """Загружает выбранный профиль."""
    profile_name = profile_combobox.get()
    if not profile_name:
        profile_status_label.config(text="Выберите профиль для загрузки.", fg="red")
        return
    
    # Загружаем выбранный профиль
    load_config(profile_name=profile_name)
    profile_status_label.config(text=f"Профиль '{profile_name}' загружен.", fg="green")
    update_stats() # Применяем настройки к главному окну

def delete_profile_action(profile_combobox, profile_status_label):
    """Удаляет выбранный профиль."""
    profile_name = profile_combobox.get()
    if not profile_name:
        profile_status_label.config(text="Выберите профиль для удаления.", fg="red")
        return
    if profile_name == "Default":
        profile_status_label.config(text="Нельзя удалить профиль 'Default'!", fg="red")
        return

    try:
        with open(CONFIG_FILE, 'r') as f:
            full_config = json.load(f)
        profiles = full_config.get('profiles', {})
        if profile_name in profiles:
            del profiles[profile_name]
            full_config['profiles'] = profiles
            if full_config.get('current_profile') == profile_name:
                full_config['current_profile'] = 'Default' # Переключаемся на Default, если активный удален
            with open(CONFIG_FILE, 'w') as f:
                json.dump(full_config, f, indent=4)
            profile_status_label.config(text=f"Профиль '{profile_name}' удален.", fg="green")
            update_profile_dropdown(profile_combobox, profile_status_label)
            load_profile_action(profile_combobox, profile_status_label) # Загружаем Default или другой активный
        else:
            profile_status_label.config(text=f"Профиль '{profile_name}' не найден.", fg="orange")
    except Exception as e:
        profile_status_label.config(text=f"Ошибка удаления: {e}", fg="red")
        print(f"Error deleting profile: {e}")

# Глобальная переменная для метки состояния описания в окне настроек
description_status_label = None

def export_descriptions_to_txt():
    """Экспортирует описания метрик в TXT файл и пытается его открыть."""
    global description_status_label
    descriptions = {
        'Загрузка CPU': 'Процент использования центрального процессора. Высокие значения указывают на активную работу.',
        'Использование RAM': 'Процент или объем используемой оперативной памяти. Важный показатель для общей производительности системы.',
        'Использование Диска': 'Процент или объем используемого пространства на выбранном диске. Помогает отслеживать свободное место.',
        'Скорость Диска (Чтение/Запись)': 'Скорость чтения и записи данных на всех дисках в системе.',
        'Всего процессов': 'Общее количество всех запущенных процессов в системе.',
        'Пользовательских процессов': 'Количество процессов, запущенных текущим пользователем. Может помочь отличить фоновые системные процессы от активных приложений.',
        'Статус процессов': 'Разбивка процессов по их текущему состоянию: Запущенные (Running), Спящие (Sleeping), Зомби (Zombie), Остановленные (Stopped) и Другие.',
        'Время работы системы': 'Общее время, прошедшее с момента последнего запуска операционной системы.',
        'Частота CPU': 'Текущая, минимальная и максимальная тактовая частота центрального процессора в МГц.',
        'Загрузка CPU по ядрам': 'Процент использования каждого отдельного логического ядра процессора. Помогает выявить неравномерную нагрузку.',
        'Топ-процесс CPU': 'Название процесса, который в данный момент потребляет наибольшую долю ресурсов CPU.',
        'Физические ядра CPU': 'Количество физических ядер в центральном процессоре.',
        'Логические потоки CPU': 'Общее количество логических потоков (включая гипертрейдинг) в центральном процессоре.',
        'Использование Swap': 'Процент использования файла подкачки (виртуальной памяти) на диске. Высокое использование может указывать на нехватку RAM.',
        'Топ-процесс RAM': 'Название процесса, который в данный момент потребляет наибольший объем оперативной памяти.',
        'Время работы приложения': 'Время, прошедшее с момента запуска приложения "ПроцессМастер".',
        'Текущее время': 'Текущее системное время в формате ЧЧ:ММ:СС.',
        'Статус батареи': 'Процент заряда батареи, ее текущее состояние (заряжается/разряжается) и примерное оставшееся время работы (только для ноутбуков).',
        'Время CPU (User/System/Idle)': 'Разбивка времени, которое CPU проводит в пользовательском режиме (выполнение программ), системном режиме (выполнение задач ОС) и режиме простоя.'
    }

    file_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'metric_descriptions.txt')
    
    try:
        with open(file_path, 'w', encoding='utf-8') as f:
            for title, desc in descriptions.items():
                f.write(f"{title}:\n")
                f.write(f"  {desc}\n\n")
        
        if description_status_label:
            description_status_label.config(text=f"Описание сохранено в '{os.path.basename(file_path)}'", fg="green")
            description_status_label.after(5000, lambda: description_status_label.config(text="")) # Очищаем через 5 секунд

        # Пытаемся открыть файл
        if platform.system() == "Windows":
            os.startfile(file_path)
        elif platform.system() == "Darwin": # macOS
            subprocess.Popen(['open', file_path])
        else: # Linux и другие Unix-подобные
            subprocess.Popen(['xdg-open', file_path])

    except Exception as e:
        if description_status_label:
            description_status_label.config(text=f"Ошибка при сохранении/открытии: {e}", fg="red")
            description_status_label.after(5000, lambda: description_status_label.config(text="")) # Очищаем через 5 секунд
        print(f"Error exporting descriptions: {e}")


def open_settings_window():
    """Открывает отдельное окно настроек."""
    global description_status_label # Делаем доступной
    settings_window = tk.Toplevel(window)
    settings_window.title("Настройки отображения и профилей")
    settings_window.geometry("400x900") # Увеличена высота окна настроек
    settings_window.resizable(False, False)
    settings_window.configure(bg='#282c34', bd=2, relief='solid', highlightbackground='#61dafb', highlightthickness=1)

    # Заголовок окна настроек
    settings_title_label = tk.Label(settings_window, text='Настройки', font=('Inter', 10, 'bold'), fg='#f8f8f2', bg='#1e1e1e')
    settings_title_label.pack(fill='x', side='top', pady=5)

    # Создаем Notebook (интерфейс с вкладками)
    notebook = ttk.Notebook(settings_window)
    notebook.pack(pady=10, padx=10, fill='both', expand=True)

    # Вкладка 1: Настройки отображения метрик
    display_settings_frame = tk.Frame(notebook, bg=label_bg)
    notebook.add(display_settings_frame, text="Показатели")
    
    # Создаем Canvas и полосу прокрутки для вкладки "Показатели"
    display_canvas = tk.Canvas(display_settings_frame, bg=label_bg, highlightthickness=0)
    display_canvas.pack(side='left', fill='both', expand=True)
    display_scrollbar = ttk.Scrollbar(display_settings_frame, orient='vertical', command=display_canvas.yview)
    display_scrollbar.pack(side='right', fill='y')
    display_canvas.configure(yscrollcommand=display_scrollbar.set)

    display_content_frame = tk.Frame(display_canvas, bg=label_bg)
    display_content_frame_id = display_canvas.create_window((0, 0), window=display_content_frame, anchor='nw')

    # Настраиваем сетку для фрейма содержимого
    display_content_frame.grid_columnconfigure(0, weight=1)
    display_content_frame.grid_columnconfigure(1, weight=1)

    # Функция для обновления области прокрутки и ширины фрейма содержимого для вкладки "Показатели"
    def _on_display_canvas_configure(event):
        display_canvas.configure(scrollregion=display_canvas.bbox("all"))
        display_canvas.itemconfig(display_content_frame_id, width=event.width)

    display_canvas.bind('<Configure>', _on_display_canvas_configure)
    display_content_frame.bind('<Configure>', lambda e: display_canvas.configure(scrollregion=display_canvas.bbox("all")))


    # Список (текст, переменная) для чекбоксов для упрощения создания и удаления отдельных команд
    checkbox_configs = [
        ('Загрузка CPU', show_cpu_var),
        ('Использование RAM', show_ram_var),
        ('Использование Диска', show_disk_var),
        ('Скорость Диска (Чтение/Запись)', show_disk_io_var),
        ('Всего процессов', show_total_processes_var),
        ('Пользовательских процессов', show_user_processes_var),
        ('Статус процессов', show_process_states_var),
        ('Время работы системы', show_uptime_var),
        ('Частота CPU', show_cpu_freq_var),
        ('Загрузка CPU по ядрам', show_per_cpu_usage_var),
        ('Топ-процесс CPU', show_top_process_var),
        ('Физические ядра CPU', show_physical_cores_var),
        ('Логические потоки CPU', show_logical_cores_var),
        ('Использование Swap', show_swap_usage_var),
        ('Топ-процесс RAM', show_top_ram_process_var),
        ('Время работы приложения', show_app_uptime_var),
        ('Текущее время', show_real_time_var),
        ('Статус батареи', show_battery_status_var),
        ('Время CPU (User/System/Idle)', show_cpu_times_var),
        # Удалены: 'Сетевая активность', 'Сетевая задержка (Пинг)', 'Температура CPU', 'Скорость вентилятора'
    ]

    # Создаем чекбоксы без прямых команд, теперь внутри display_content_frame
    row_idx = 0
    col_idx = 0
    for text, var in checkbox_configs:
        # Изменено selectcolor на label_bg для удаления синего выделения
        chk = tk.Checkbutton(display_content_frame, text=text, variable=var, font=('Inter', 10), fg=label_fg, bg=label_bg, selectcolor=label_bg, activebackground=label_bg, activeforeground='#61dafb') 
        chk.grid(row=row_idx, column=col_idx, sticky='w', padx=5, pady=2)
        col_idx = 1 - col_idx # Переключаем столбец
        if col_idx == 0: # Если перешли на первый столбец, увеличиваем строку
            row_idx += 1

    # Добавляем кнопку "Применить" для применения всех изменений, теперь внутри display_content_frame
    apply_button = tk.Button(display_content_frame, text='Применить изменения', font=('Inter', 10, 'bold'), fg='white', bg='#61dafb',
                             activebackground='#4fa0d2', activeforeground='white',
                             bd=0, command=lambda: (save_config(), update_stats())) # Применяем изменения и обновляем главное окно
    apply_button.grid(row=row_idx + 1, column=0, columnspan=2, pady=10)


    # Вкладка 2: Описание метрик
    descriptions_tab_frame = tk.Frame(notebook, bg=label_bg)
    notebook.add(descriptions_tab_frame, text="Описание показателей")

    # Заменили canvas/scrollbar/labels на кнопку и метку состояния
    export_button = tk.Button(descriptions_tab_frame, text="Открыть описание в TXT", font=('Inter', 10, 'bold'), fg='white', bg='#61dafb',
                              activebackground='#4fa0d2', activeforeground='white',
                              bd=0, command=export_descriptions_to_txt)
    export_button.pack(pady=20, padx=10)

    description_status_label = tk.Label(descriptions_tab_frame, text="", font=('Inter', 9), fg='white', bg=label_bg)
    description_status_label.pack(pady=5, padx=10)

    # --- Управление профилями ---
    profile_frame = tk.LabelFrame(settings_window, text="Управление профилями", font=('Inter', 10, 'bold'), fg='#61dafb', bg=label_bg, bd=1, relief='solid')
    profile_frame.pack(pady=10, padx=10, fill='x', anchor='w')

    profile_label = tk.Label(profile_frame, text="Выбрать профиль:", font=('Inter', 10), fg=label_fg, bg=label_bg)
    profile_label.pack(pady=5, padx=5, anchor='w')

    profile_combobox = ttk.Combobox(profile_frame, state='readonly', font=('Inter', 10), width=25)
    profile_combobox.pack(pady=2, padx=5, fill='x')
    profile_status_label = tk.Label(profile_frame, text="", font=('Inter', 9), fg='white', bg=label_bg) # Локальный статус для профилей
    profile_status_label.pack(pady=2, anchor='w', padx=5)
    update_profile_dropdown(profile_combobox, profile_status_label) # Обновляем при открытии окна

    load_profile_button = tk.Button(profile_frame, text="Загрузить профиль", font=('Inter', 10, 'bold'), fg='white', bg='#61dafb',
                                    activebackground='#4fa0d2', activeforeground='white',
                                    bd=0, command=lambda: load_profile_action(profile_combobox, profile_status_label))
    load_profile_button.pack(pady=5, padx=5, fill='x')

    profile_name_entry_label = tk.Label(profile_frame, text="Имя нового профиля:", font=('Inter', 10), fg=label_fg, bg=label_bg)
    profile_name_entry_label.pack(pady=5, padx=5, anchor='w')
    profile_name_entry = tk.Entry(profile_frame, font=('Inter', 10), bg='#44475a', fg='#f8f8f2', insertbackground='#f8f8f2')
    profile_name_entry.pack(pady=2, padx=5, fill='x')

    save_profile_button = tk.Button(profile_frame, text="Сохранить профиль", font=('Inter', 10, 'bold'), fg='white', bg='#61dafb',
                                    activebackground='#4fa0d2', activeforeground='white',
                                    bd=0, command=lambda: save_profile_action(profile_name_entry, profile_combobox, profile_status_label))
    save_profile_button.pack(pady=5, padx=5, fill='x')

    delete_profile_button = tk.Button(profile_frame, text="Удалить профиль", font=('Inter', 10, 'bold'), fg='white', bg='#ff5555',
                                      activebackground='#cc4444', activeforeground='white',
                                      bd=0, command=lambda: delete_profile_action(profile_combobox, profile_status_label))
    delete_profile_button.pack(pady=5, padx=5, fill='x')

    # Информация о создателе
    creator_label = tk.Label(settings_window, text="Создатель: Кирилл", font=('Inter', 9), fg='#999999', bg=label_bg)
    creator_label.pack(pady=10)

    # Кнопка закрытия окна настроек
    # Эта кнопка теперь просто закроет окно, полагаясь на кнопку "Применить" для сохранения изменений
    close_settings_button = tk.Button(settings_window, text="Закрыть", font=('Inter', 10, 'bold'), fg='white', bg='#61dafb',
                                      activebackground='#4fa0d2', activeforeground='white',
                                      bd=0, command=settings_window.destroy)
    close_settings_button.pack(pady=10)


# --- Запускаем первое обновление и главный цикл ---
# Инициализируем сетевые счетчики перед первым обновлением
# Это теперь обрабатывается для каждой сетевой карты в update_stats, но инициализируем глобальное время
last_net_time = time.time()

# Привязываем событие <Configure> к content_frame, чтобы Canvas обновлял scrollregion
content_frame.bind(
    "<Configure>",
    lambda e: main_canvas.configure(
        scrollregion=main_canvas.bbox("all")
    )
)

update_stats() # Вызываем update_stats после загрузки конфигурации для применения настроек видимости

# Запускаем иконку в трее в отдельном потоке, чтобы не блокировать основной поток Tkinter
if PYSTRAY_AVAILABLE:
    tray_thread = threading.Thread(target=create_tray_icon, daemon=True)
    tray_thread.start()

window.mainloop()
