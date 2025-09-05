from scan.scan_base import BaseScanner, ScanStatus, Network

class ArpScanner(BaseScanner):

    def __init__(self, id: str, network: Network) -> None:
        super().__init__(id, network)

    def start_scan(self) -> None:
        print("started arp scanner id:", self.id, " network:", self.network.interface, f"{self.network.ip.network_address}/{self.network.ip.prefixlen}")
        pass

    def stop_scan(self) -> None:
        pass

    def get_status(self) -> ScanStatus:
        pass
