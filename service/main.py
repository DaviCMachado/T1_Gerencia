# MUDANÇA 1: Importar BackgroundTasks
from fastapi import FastAPI, BackgroundTasks
from scan.scan_base import BaseScanner, ScanStatus, Network
from scan.ping_scan import PingScanner
from scan.arp_scan import ArpScanner
from device import Device
from db_manager import DB_Manager
from threading import Lock
import signal
import uvicorn
from mac_vendor import MacVendor

app = FastAPI()

# --- Banco ---
db = DB_Manager()

# --- MAC Vendor warm-up ---
mac_vendor = MacVendor()

# --- Controle de scanners ---
available_scanners: list[BaseScanner] = []
merged_devices: list[Device] = []
devices_lock = Lock()
scan_state_lock = Lock()
scan_in_progress = False

def device_already_merged(dev: Device) -> bool:
    for d in merged_devices:
        if d.ip == dev.ip:
            if dev.mac and not d.mac:
                d.mac = dev.mac
            return True
    return False

def on_device_discover(device: Device):
    dispositivo = {
        'ip': device.ip, 'mac': device.mac or None,
        'fabricante': mac_vendor.obter_fabricante_mac(device.mac),
        'so': device.so, 'servicos': device.services or []
    }
    with devices_lock:
        if not device_already_merged(device):
            merged_devices.append(device)
            db.registrar_dispositivo(dispositivo, tipo='up')
        else:
            db.registrar_dispositivo(dispositivo, tipo='up')

def add_offline_devices():
    print("[SYSTEM] Finalizando scan e verificando dispositivos offline...")
    all_db_devices = db.exibir_dispositivos() 
    with devices_lock:
        detected_ips = {d.ip for d in merged_devices}
        for dev_tuple in all_db_devices:
            ip, mac, _, _ = dev_tuple
            if ip not in detected_ips:
                print(f"[SYSTEM] Dispositivo {ip} ficou offline.")
                db.registrar_dispositivo({'ip': ip, 'mac': mac}, tipo='down')
    print("[SYSTEM] Verificação de offline concluída.")

# --- Detectar redes e Instanciar scanners (sem alterações) ---
try:
    networks: list[Network] = Network.get_local_networks()
    print(f"Detected {len(networks)} networks:")
    for net in networks:
        print(f" - Interface: {net.interface}, Network: {net.ip.network_address}/{net.ip.prefixlen}")
        ping = PingScanner(f"ping-scanner-{net.interface}-{net.ip}", net)
        arp = ArpScanner(f"arp-scanner-{net.interface}-{net.ip}", net)
        ping.register_discovery_callback(on_device_discover)
        arp.register_discovery_callback(on_device_discover)
        available_scanners.append(ping)
        available_scanners.append(arp)
except Exception as e:
    print(f"ERRO CRÍTICO ao iniciar scanners: {e}")

# --- Funções auxiliares para as tarefas de longa duração ---
def run_scanners_in_background():
    """Esta função contém a lógica que bloqueava o servidor."""
    print("[BACKGROUND] Iniciando scanners em segundo plano...")
    for scanner in available_scanners:
        if scanner.get_status() != ScanStatus.Scanning:
            scanner.start_scan() # Esta é a chamada demorada
    print("[BACKGROUND] Todos os scanners foram iniciados.")

def stop_scanners_in_background():
    """Função para parar os scanners em segundo plano, se necessário."""
    print("[BACKGROUND] Parando scanners em segundo plano...")
    for scanner in available_scanners:
        if scanner.get_status() == ScanStatus.Scanning:
            scanner.stop_scan()
    print("[BACKGROUND] Comando de parada enviado a todos os scanners.")
    # Força a finalização e marcação de offline
    with scan_state_lock:
        global scan_in_progress
        if scan_in_progress:
            add_offline_devices()
            scan_in_progress = False


# ------------------- FastAPI endpoints -------------------

# Modifiquei os endpoints para usar BackgroundTasks
@app.get("/scan/start")
async def start_scan(background_tasks: BackgroundTasks):
    with devices_lock:
        merged_devices.clear()
    
    print("[API] Recebida requisição para iniciar o scan. Agendando tarefa em segundo plano.")
    
    with scan_state_lock:
        global scan_in_progress
        scan_in_progress = True
    
    # Adiciona a função demorada para ser executada em segundo plano
    background_tasks.add_task(run_scanners_in_background)
    
    # Retorna imediatamente para a GUI
    return {"message": "Scan task scheduled", "status": "ok"}


@app.get("/scan/stop")
async def stop_scan(background_tasks: BackgroundTasks):
    print("[API] Recebida requisição para parar o scan. Agendando tarefa em segundo plano.")
    background_tasks.add_task(stop_scanners_in_background)
    return {"message": "Stop task scheduled", "status": "ok"}


@app.get("/scan/status")
def scan_status():
    running = sum(1 for scanner in available_scanners if scanner.get_status() == ScanStatus.Scanning)
    with scan_state_lock:
        global scan_in_progress
        if running == 0 and scan_in_progress:
            add_offline_devices()
            scan_in_progress = False
    return {"scanning": running}

@app.get("/networks")
def list_networks():
    return [{"interface": n.interface, "ip": str(n.ip.network_address), "netmask": str(n.ip.netmask), "prefix": n.ip.prefixlen} for n in networks]

@app.get("/devices")
def list_devices():
    print("[API] Servindo dados de dispositivos agregados.")
    return db.exibir_dispositivos_agregados()

@app.get("/devices/{ip}/history")
def device_history(ip: str):
    all_devices = db.exibir_dispositivos_agregados()
    for device in all_devices:
        if device['ip'] == ip:
            return device
    return {"error": "Device not found"}

@app.get("/scan/discovered_devices")
def list_discovered_devices():
    """Retorna a lista de dispositivos encontrados APENAS na sessão de scan atual."""
    with devices_lock:
        # Converte a lista de objetos Device em uma lista de dicionários para ser enviada como JSON
        return [dev.to_dict() for dev in merged_devices]



def stop_all_scans(signum, frame):
    print("\n[SYSTEM] Ctrl+C detectado. Parando todos os scans ativos...")
    for scanner in available_scanners:
        try:
            scanner.stop_scan()
        except Exception as e:
            print(f"[ERROR] Falha ao parar scanner {scanner.id}: {e}")
    add_offline_devices()
    print("[SYSTEM] Todos os scanners foram parados. Saindo.")
    import sys
    sys.exit(0)

signal.signal(signal.SIGINT, stop_all_scans)

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=80)