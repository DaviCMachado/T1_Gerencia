from scan_base import BaseScanner, ScanStatus, Network

class PingScanner(BaseScanner):

    def __init__(self, id: str, network: Network) -> None:
        super().__init__(id, network)

    def start_scan(self) -> None:
        pass

    def stop_scan(self) -> None:
        pass

    def get_status(self) -> ScanStatus:
        pass
