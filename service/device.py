from service.mac_vendor import MacVendor
from enum import Enum
from datetime import datetime

class DeviceStatus(Enum):
    ONLINE = "online"
    OFFLINE = "offline"
    UNKNOWN = "unknown"

class DeviceService:
    '''
    Representa um servico que um dispositivo esta executando atualmente ou ja executou.
    '''

    port: int
    '''
    Numero da porta do servico (1-65535).
    '''

    protocol: str
    '''
    Nome chave do protocolo (tcp, udp, icmp, etc).
    '''

    name: str
    '''
    Nome do servico (http, ftp, ssh, etc).
    '''

    version: str | None
    '''
    Versao do servico, se identificada.
    '''

    start_date: datetime
    '''
    Data e hora em que o servico foi inicialmente detectado no dispositivo.
    '''

    last_seen: datetime
    '''
    Data e hora em que o servico foi mais recentemente detectado no dispositivo.
    '''

class Device:
    '''
    Classe que representa um dispositivo na rede.
    '''

    id: int
    ''' 
    Id numerico unico para cada dispositivo. Eh autoincrementado no banco de dados integrado.
    '''

    ip: str
    '''
    Endereco IP do dispositivo na rede. Pode ser IPv4 ou IPv6.
    '''

    mac: str
    '''
    Endereco MAC do dispositivo na rede.
    '''

    so: str | None
    '''
    Sistema operacional do dispositivo, se identificado.
    '''

    status: DeviceStatus
    '''
    Status atual do dispositivo na rede (online, offline, unknown).
    '''

    services: list[DeviceService]
    '''
    Lista de servicos que o dispositivo esta executando atualmente ou ja executou.
    '''

    last_seen: datetime
    '''
    Data e hora em que o dispositivo foi mais recentemente detectado na rede.
    '''

    def get_fabricante(self) -> str:
        '''
        Retorna o nome do fabricante do dispositivo com base no endereco MAC.
        '''
        return MacVendor().obter_fabricante_mac(self.mac)
        
    def is_same(self, other: object) -> bool:
        if not isinstance(other, Device):
            return False
        return (self.ip == other.ip and
                self.mac == other.mac)