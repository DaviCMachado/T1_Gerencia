import os

# if linux check root
if os.name != 'nt' and os.geteuid() != 0:
    print("Por favor inicie como root usando sudo")
    input("Digite ENTER para sair.")
    sys.exit()
# if windows check admin
if os.name == 'nt':
    import ctypes, sys
    if not ctypes.windll.shell32.IsUserAnAdmin():
        # nao funciona
        #ctypes.windll.shell32.ShellExecuteW(None, "runas", sys.executable, " ".join(sys.argv), None, 1)
        print("Por favor inicie como administrador.")
        input("Digite ENTER para sair.")
        sys.exit()


from fastapi import FastAPI
from scan.scan_base import BaseScanner, ScanStatus, Network
from scan.ping_scan import PingScanner
from scan.arp_scan import ArpScanner
from device import Device

app = FastAPI()

def on_device_discover(device: Device):
    # aqui a gente verifica se eles sao novos ou ja conhecidos e atualiza o banco de dados
    # usar metodo is_same(self, other). is_same faz checagem soh por ip e mac opcionalmente. alguns scanners podem nao pegar mac
    pass

networks: list[Network] = Network.get_local_networks() 

print(f"Detected {len(networks)} networks:")
for net in networks:
    print(f" - Interface: {net.interface}, Network: {net.ip.network_address}/{net.ip.prefixlen}, Netmask: {net.ip.netmask}")

available_scanners: list[BaseScanner] = []
for net in networks:
    # instancia os scanners
    ping = PingScanner(f"ping-scanner-{net.interface}-{net.ip}", net)
    arp = ArpScanner(f"arp-scanner-{net.interface}-{net.ip}", net)

    # define callback de descoberta
    ping.register_discovery_callback(on_device_discover)
    arp.register_discovery_callback(on_device_discover)

    # registra eles no repositorio
    available_scanners.append(ping)
    available_scanners.append(arp)

@app.get("/scan/start")
async def start_scan():
    for scanner in available_scanners:
        if(scanner.get_status() != ScanStatus.Scanning):
            scanner.start_scan()
    
    return {
        "message": "Scan started",
        "status": "ok"
    }

@app.get("/scan/stop")
async def stop_scan():

    for scanner in available_scanners:
        if(scanner.get_status() == ScanStatus.Scanning):
            scanner.stop_scan()
    
    return {
        "message": "Scan stopped",
        "status": "ok"
    }

@app.get("/scan/status")
def scan_status():
    running = 0
    completed = 0
    stopped = 0
    for scanner in available_scanners:
        status = scanner.get_status()
        if(status == ScanStatus.Scanning):
            running += 1
        elif(status == ScanStatus.Completed):
            completed += 1
        elif(status == ScanStatus.Stopped):
            stopped += 1
    return {
        "scanning": running,
        "completed": completed,
        "stopped": stopped
    }

@app.get("/networks")
def list_networks():
    return [
        {
            "interface": net.interface,
            "ip": net.ip.network_address,
            "netmask": net.ip.netmask,
            "prefix": net.ip.prefixlen
        } for net in networks
    ]

@app.get("/known_devices")
def list_known_devices():
    devices = []
    # substituir este metodo com dispositivos registrados no banco de dados
    # callback on_device_discover deve atualizar o banco de dados
    # e remover duplicatas detectadas pelos scanners
    for scanner in available_scanners:
        devices.extend(scanner.get_devices())
    return devices
