# main.py
import asyncio
import snmp_agent
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
from contextlib import asynccontextmanager
from datetime import datetime, timedelta
import snmp  # arquivo snmp.py

# ---------------- SNMP SERVER ----------------
async def run_snmp_server():
    sv = snmp_agent.Server(handler=snmp.snmp_handler, host='0.0.0.0', port=161)
    await sv.start()
    try:
        while True:
            await asyncio.sleep(3600)
    except asyncio.CancelledError:
        await sv.stop()
        print("[SNMP] Servidor encerrado.")

# ---------------- LIFESPAN ----------------
@asynccontextmanager
async def lifespan(app: FastAPI):
    db_task = asyncio.create_task(periodic_db_sync())
    snmp_task = asyncio.create_task(run_snmp_server())

    yield  # entrega o controle à aplicação

    # shutdown
    db_task.cancel()
    snmp_task.cancel()
    for t in (db_task, snmp_task):
        try:
            await t
        except asyncio.CancelledError:
            pass
    print("[SYSTEM] Tasks de background finalizadas.")

# ---------------- APP ----------------
app = FastAPI(lifespan=lifespan)

# ---------------- DATABASE ----------------
db = DB_Manager()

# ---------------- MAC VENDOR ----------------
mac_vendor = MacVendor()

# ---------------- SCANNERS ----------------
available_scanners: list[BaseScanner] = []
merged_devices: list[Device] = []

devices_lock = Lock()
scan_state_lock = asyncio.Lock()
scan_in_progress = False

def device_already_merged(dev: Device) -> bool:
    for d in merged_devices:
        if d.ip == dev.ip:
            if dev.mac and not d.mac:
                d.mac = dev.mac
            return True
    return False

def on_device_discover(device: Device):
    vendor = mac_vendor.obter_fabricante_mac(device.mac)
    device.vendor = vendor
    dispositivo = {
        'ip': device.ip,
        'mac': device.mac or None,
        'fabricante': device.vendor,
        'so': device.so,
        'servicos': device.services or []
    }
    with devices_lock:
        if not device_already_merged(device):
            merged_devices.append(device)
        db.registrar_dispositivo(dispositivo, tipo='up')

# ---------------- PERIODIC DB SYNC ----------------
async def periodic_db_sync():
    while True:
        await asyncio.sleep(60)  # espera 1 minuto
        db.apply_sync_operations()

# ---------------- DETECT NETWORKS & INIT SCANNERS ----------------
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

# ---------------- RUN/STOP SCANNERS ----------------
async def run_scanners_in_background():
    print("[BACKGROUND] Iniciando scanners em executor...")
    loop = asyncio.get_running_loop()
    tasks = [
        loop.run_in_executor(None, scanner.start_scan)
        for scanner in available_scanners
        if scanner.get_status() != ScanStatus.Scanning
    ]
    if tasks:
        await asyncio.gather(*tasks)
    print("[BACKGROUND] Todos os scanners foram iniciados.")

async def stop_scanners_in_background():
    print("[BACKGROUND] Parando scanners em executor...")
    loop = asyncio.get_running_loop()
    tasks = [
        loop.run_in_executor(None, scanner.stop_scan)
        for scanner in available_scanners
        if scanner.get_status() == ScanStatus.Scanning
    ]
    if tasks:
        await asyncio.gather(*tasks)
    print("[BACKGROUND] Todos os scanners foram parados.")

    # Atualiza estado
    global scan_in_progress
    async with scan_state_lock:
        scan_in_progress = False

# ---------------- FASTAPI ENDPOINTS ----------------
@app.get("/scan/start")
async def start_scan(background_tasks: BackgroundTasks):
    with devices_lock:
        merged_devices.clear()
    async with scan_state_lock:
        global scan_in_progress
        scan_in_progress = True

    background_tasks.add_task(lambda: asyncio.create_task(run_scanners_in_background()))
    return {"message": "Scan task scheduled", "status": "ok"}

@app.get("/scan/stop")
async def stop_scan(background_tasks: BackgroundTasks):
    background_tasks.add_task(lambda: asyncio.create_task(stop_scanners_in_background()))
    return {"message": "Stop task scheduled", "status": "ok"}

@app.get("/scan/status")
async def scan_status():
    running = sum(1 for s in available_scanners if s.get_status() == ScanStatus.Scanning)
    async with scan_state_lock:
        global scan_in_progress
        if running == 0 and scan_in_progress:
            scan_in_progress = False
    return {"scanning": running}

@app.get("/networks")
def list_networks():
    return [{"interface": n.interface, "ip": str(n.ip.network_address), "netmask": str(n.ip.netmask), "prefix": n.ip.prefixlen} for n in networks]

@app.get("/devices")
def list_devices():
    return db.exibir_dispositivos_agregados()

@app.get("/devices/{ip}/history")
def device_history(ip: str):
    for device in db.exibir_dispositivos_agregados():
        if device['ip'] == ip:
            return device
    return {"error": "Device not found"}

@app.get("/scan/discovered_devices")
def list_discovered_devices():
    active_devices = []
    with devices_lock:
        all_devices = db.exibir_dispositivos_agregados()
        cutoff = datetime.now() - timedelta(minutes=5)
        for device in all_devices:
            last_seen = device.get('last_seen')
            if last_seen:
                try:
                    if datetime.fromisoformat(last_seen) > cutoff:
                        active_devices.append(device)
                except ValueError:
                    if datetime.strptime(last_seen, "%Y-%m-%d %H:%M:%S") > cutoff:
                        active_devices.append(device)
    return active_devices

@app.get("/operations")
def list_operations():
    ops = db.listar_operations()
    return [
        {"ip": op["ip"], "status": op["status"], "timestamp": op["timestamp"].isoformat() if isinstance(op["timestamp"], datetime) else str(op["timestamp"])}
        for op in ops
    ]

# ---------------- SIGNAL HANDLER ----------------
def stop_all_scans(signum, frame):
    print("\n[SYSTEM] Ctrl+C detectado. Parando todos os scans ativos...")
    for scanner in available_scanners:
        try:
            scanner.stop_scan()
        except Exception as e:
            print(f"[ERROR] Falha ao parar scanner {scanner.id}: {e}")
    print("[SYSTEM] Todos os scanners foram parados. Saindo.")
    import sys
    sys.exit(0)

signal.signal(signal.SIGINT, stop_all_scans)

# ---------------- MAIN ----------------
if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=80)
