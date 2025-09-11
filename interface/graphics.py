import requests
import matplotlib.pyplot as plt
import matplotlib.animation as animation
from collections import defaultdict
from datetime import datetime
from itertools import cycle
import itertools

# ---------------- URLs da API ----------------
DEVICES_HISTORY_URL = "http://localhost/devices"
CURRENTLY_DISCOVERED_URL = "http://localhost/scan/discovered_devices"
OPERATIONS_URL = "http://localhost/operations"

# ---------------- Estruturas -----------------
known_devices_history = defaultdict(lambda: {'times': [], 'statuses': []})
device_order = []
MAX_POINTS = 1000  # limita histórico

def get_json_data(url):
    try:
        r = requests.get(url, timeout=5)
        if r.status_code == 200:
            return r.json()
    except requests.exceptions.RequestException as e:
        print(f"Erro ao conectar {url}: {e}")
    return None



def get_json_data(url):
    try:
        response = requests.get(url, timeout=5)
        if response.status_code == 200:
            return response.json()
    except requests.exceptions.RequestException as e:
        print(f"Erro ao conectar à API em {url}: {e}")
    return None

def plot_static_history():
    print("Gerando gráfico estático a partir de /operations...")
    ops = get_json_data(OPERATIONS_URL)
    if not ops:
        print("Sem dados de operações.")
        return

    # Agrupa por IP
    by_ip = defaultdict(lambda: {"times": [], "statuses": []})
    for op in ops:
        ip = op["ip"]
        status = 1 if op["status"] in ("up", "novo_dispositivo") else 0
        ts = datetime.fromisoformat(op["timestamp"])
        by_ip[ip]["times"].append(ts)
        by_ip[ip]["statuses"].append(status)

    # Plot
    plt.style.use('seaborn-v0_8-darkgrid')
    fig, ax = plt.subplots(figsize=(14, 8))

    OFFSET_STEP = 0.03  # Deslocamento vertical entre as linhas
    colors = itertools.cycle(plt.cm.tab20.colors)  # Paleta de cores cíclica

    for i, (ip, data) in enumerate(by_ip.items()):
        offset = i * OFFSET_STEP
        shifted_statuses = [s + offset for s in data["statuses"]]
        ax.step(data["times"], shifted_statuses, where="post",
                label=ip, color=next(colors), linewidth=1.6)
        ax.scatter(data["times"], shifted_statuses, color="black", s=10)

    ax.set_title('Histórico Completo de Status (deslocado por dispositivo)', fontsize=16)
    ax.set_xlabel('Tempo', fontsize=12)
    ax.set_ylabel('Status (0=Down, 1=Up + offset)', fontsize=12)

    # Ticks originais para referência
    ax.set_yticks([0, 1])
    ax.set_yticklabels(['Down', 'Up'])
    ax.set_ylim(-0.2, 1.2 + len(by_ip) * OFFSET_STEP)

    # Legenda externa
    ax.legend(title="Dispositivos", bbox_to_anchor=(1.02, 1), loc="upper left")
    fig.autofmt_xdate()
    plt.tight_layout(rect=[0, 0, 0.82, 1])
    plt.show()



# ---------------- Gráfico Dinâmico -----------------
def update_dynamic_plot(frame, ax):
    online_data = get_json_data(CURRENTLY_DISCOVERED_URL)
    if online_data is None:
        return

    online_ips = {d['ip'] for d in online_data}
    now = datetime.now()

    for ip in online_ips:
        if ip not in device_order:
            device_order.append(ip)
            known_devices_history[ip]['times'].append(now)
            known_devices_history[ip]['statuses'].append(1)

    for ip in device_order:
        hist = known_devices_history[ip]
        status = 1 if ip in online_ips else 0
        hist['statuses'].append(status)
        hist['times'].append(now)
        if len(hist['times']) > MAX_POINTS:
            hist['times'] = hist['times'][-MAX_POINTS:]
            hist['statuses'] = hist['statuses'][-MAX_POINTS:]

    ax.clear()
    plt.style.use('seaborn-v0_8-darkgrid')
    OFFSET_STEP = 0.03
    for i, ip in enumerate(device_order):
        h = known_devices_history[ip]
        if not h['times']:
            continue
        offset = i * OFFSET_STEP
        shifted = [s + offset for s in h['statuses']]
        ax.plot(h['times'], shifted, marker='.', linestyle='-', label=ip)

    ax.set_title('Status em Tempo Real', fontsize=16)
    ax.set_xlabel('Tempo', fontsize=12)
    ax.set_ylabel('Status', fontsize=12)
    ax.set_yticks([0, 1])
    ax.set_yticklabels(['Down', 'Up'])
    ax.set_ylim(-0.1, 1.1 + len(device_order) * OFFSET_STEP)
    ax.legend(title="Dispositivos", bbox_to_anchor=(1.04, 1), loc="upper left")
    fig.autofmt_xdate()
    plt.tight_layout(rect=[0, 0, 0.85, 1])

# ---------------- Execução -----------------
if __name__ == "__main__":
    plot_static_history()
    print("\nIniciando gráfico dinâmico... (Ctrl+C para parar)")
    fig, ax = plt.subplots(figsize=(12, 7))
    plt.style.use('seaborn-v0_8-darkgrid')
    ani = animation.FuncAnimation(fig, update_dynamic_plot, fargs=(ax,), interval=3000)
    plt.show()
