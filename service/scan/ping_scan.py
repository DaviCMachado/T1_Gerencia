from time import sleep
from scan.scan_base import BaseScanner, ScanStatus, Network
from threading import Thread, Event
from scapy.all import sr1, IP, ICMP
from ipaddress import IPv4Address
from device import Device, DeviceStatus
from datetime import datetime

class PingScanner(BaseScanner):

    def __init__(self, id: str, network: Network) -> None:
        super().__init__(id, network)

    def start_scan(self) -> None:
        print("started ping scanner id:", self.id, " network:", self.network.interface, f"{self.network.ip.network_address}/{self.network.ip.prefixlen}")
        self.stop_event = Event()
        self.finished = False  
        self.thread = Thread(target=self.__scan)
        self.thread.start()

    def __scan(self):
        for host in self.network.ip.hosts():
            if self.stop_event.is_set():
                self.finished = False
                return
            print(f"Pinging {host.exploded}...")
            if self.__ping(host):
                device = Device()
                device.ip = host.exploded
                device.last_seen = datetime.now()
                device.mac = None
                device.so = None
                device.status = DeviceStatus.ONLINE
                device.services = []
                self._add_device(host)
                print(f"Host {host} is online")
            else:
                pass
                
        self.finished = True
        
    def __ping(self, host: IPv4Address) -> bool:
        packet = IP(dst=host.exploded)/ICMP()
        reply = sr1(packet, timeout=1, verbose=0)
        return reply is not None

    def stop_scan(self) -> None:
        print("stopping ping scanner id:", self.id)
        self.stop_event.set()
        self.thread.join()
        print("stopped ping scanner id:", self.id)

    def get_status(self) -> ScanStatus:
        if hasattr(self, 'finished') and self.finished:
            return ScanStatus.Completed
        if (hasattr(self, 'stop_event') and self.stop_event.is_set()) or (not hasattr(self, 'thread') or not self.thread.is_alive()) or not hasattr(self, 'stop_event'):
            return ScanStatus.Stopped
        return ScanStatus.Scanning
