from time import sleep
from scan.scan_base import BaseScanner, ScanStatus, Network
from threading import Thread, Event

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
        count = 0
        while(not self.stop_event.is_set()):
            sleep(1)
            count += 1
            print("Ping", count)

    def stop_scan(self) -> None:
        self.stop_event.set()
        self.thread.join()

    def get_status(self) -> ScanStatus:
        if hasattr(self, 'finished') and self.finished:
            return ScanStatus.Completed
        if (hasattr(self, 'stop_event') and self.stop_event.is_set()) or (not hasattr(self, 'thread') or not self.thread.is_alive()) or not hasattr(self, 'stop_event'):
            return ScanStatus.Stopped
        return ScanStatus.Scanning
