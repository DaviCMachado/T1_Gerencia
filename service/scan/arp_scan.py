from scan.scan_base import BaseScanner, ScanStatus, Network
from threading import Thread, Event
from time import sleep
from scapy.all import sniff, ARP
from device import Device, DeviceStatus
from datetime import datetime

class ArpScanner(BaseScanner):
    '''
    Scanner que ouve passivamente a rede em busca de pacotes ARP para descobrir dispositivos ativos na rede.
    '''

    def __init__(self, id: str, network: Network) -> None:
        super().__init__(id, network)

    def start_scan(self) -> None:
        print("started arp scanner id:", self.id, " network:", self.network.interface, f"{self.network.ip.network_address}/{self.network.ip.prefixlen}")
        self.stop_event = Event()
        self.thread = Thread(target=self.__scan)
        self.thread.start()
        pass

    def __scan(self):
        sniff(filter="arp",
              prn=self.__handle_packet,
              store=0,
              stop_filter=lambda x: self.stop_event.is_set(),
              iface=self.network.interface)

    def __handle_packet(self, pkt):
        print(f"ArpScanner({self.id}) Captured ARP packet:", pkt.summary())
        if pkt.haslayer(ARP):
            if pkt[ARP].op == 1: # quem tem?
                ip = pkt[ARP].psrc # ip do perguntador
                mac = pkt[ARP].hwsrc # mac do perguntador
                device = Device()
                device.ip = ip
                device.mac = mac
                device.last_seen = datetime.now()
                device.so = None
                device.status = DeviceStatus.ONLINE
                device.services = []
                self._add_device(device)
            elif pkt[ARP].op == 2: # estou aqui
                ip = pkt[ARP].pdst # ip do respondedor
                mac = pkt[ARP].hwdst # mac do respondedor
                device = Device()
                device.ip = ip
                device.mac = mac
                device.last_seen = datetime.now()
                device.so = None
                device.status = DeviceStatus.ONLINE
                device.services = []
                self._add_device(device)
        

    def stop_scan(self) -> None:
        print("stopping arp scanner id:", self.id)
        self.stop_event.set()
        self.thread.join()
        print("stopped arp scanner id:", self.id)

    def get_status(self) -> ScanStatus:
        if (hasattr(self, 'stop_event') and self.stop_event.is_set()) or (not hasattr(self, 'thread') or not self.thread.is_alive()) or not hasattr(self, 'stop_event'):
            return ScanStatus.Stopped
        return ScanStatus.Scanning
