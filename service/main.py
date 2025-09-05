from fastapi import FastAPI
from scan.scan_base import BaseScanner, ScanStatus, Network
from scan.ping_scan import PingScanner

app = FastAPI()

networks: list[Network] = Network.get_local_networks() 
available_scanners: list[BaseScanner] = []
for net in networks:
    available_scanners.append(PingScanner(f"ping-scanner-{net.ip}", net))
    # adicionar aqui outros tipos de scanners mais avancados


@app.get("/scan/start")
def start_scan():
    for scanner in available_scanners:
        if(scanner.get_status() != ScanStatus.Scanning):
            scanner.start_scan()
    
    return {
        "message": "Scan started",
        "status": "ok"
    }

@app.get("/scan/stop")
def stop_scan():

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
    for scanner in available_scanners:
        devices.extend(scanner.get_devices())
    return devices
