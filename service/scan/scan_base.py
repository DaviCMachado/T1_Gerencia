from abc import ABC, abstractmethod
from enum import Enum
from device import Device
import psutil
import ipaddress


class ScanStatus(Enum):
    Stopped = "stopped"
    Scanning = "scanning"
    Completed = "completed"

class Network:
    interface: str
    ip: ipaddress.IPv4Network | ipaddress.IPv6Network

    def __init__(self, interface: str, ip: ipaddress.IPv4Network | ipaddress.IPv6Network):
        self.interface = interface
        self.ip = ip

    @staticmethod
    def get_local_networks():
        redes = []
        addrs = psutil.net_if_addrs()

        for iface, infos in addrs.items():
            for info in infos:
                if info.family == 2: # 2 eh ipv4, 23 eh ipv6, o resto ignora
                    if info.address and info.netmask:
                        network_ip = ipaddress.IPv4Network(f"{info.address}/{info.netmask}", strict=False)
                        redes.append(Network(interface=iface, ip=network_ip))
        return redes

class BaseScanner(ABC):
    '''
    Classe base abstrata para todas as estratégias de escaneamento da rede
    '''

    def __init__(self, id: str, network: Network):
        self.id = id
        self.network = network

    id: str
    '''
    Identificador deste scanner na aplicacao. Apena para fins de logging.
    '''

    network: Network
    '''
    Rede a ser escaneada.
    '''

    @abstractmethod
    def start_scan(self) -> None:
        '''
        Inicia o processo de escaneamento da rede
        '''
        pass

    @abstractmethod
    def stop_scan(self) -> None:
        '''
        Para o processo de escaneamento da rede
        '''
        pass

    @abstractmethod
    def get_status(self) -> ScanStatus:
        '''
        Retorna o status atual da varredura da rede. Pode ser "idle", "scanning", ou "completed"
        '''
        pass

    known_devices: list[Device] = []

    def get_devices(self) -> list[Device]:
        '''
        Retorna uma lista com os dispositivos descobertos por este scan.
        '''
        return self.known_devices
    
    def clear_devices(self) -> None:
        '''
        Limpa a lista de dispositivos conhecidos por este scan.
        '''
        self.known_devices = []
