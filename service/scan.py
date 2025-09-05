import nmap
import socket
import ipaddress
import json
from pathlib import Path
import sqlite3
from datetime import datetime
from mac_vendor import MacVendor

class Scanner:
    def __init__(self, db_file=None, mac_vendors_file=None):
        self.DB_FILE = db_file or (Path(__file__).parent / "historico_redes.db")
        self.MAC_VENDORS_FILE = mac_vendors_file or (Path(__file__).parent.parent / "data/mac-vendors.json")
        self.vendors = self.carregar_mac_vendors()
        self.criar_banco()

    # ------------------- Banco de dados -------------------
    def criar_banco(self):
        conn = sqlite3.connect(self.DB_FILE)
        c = conn.cursor()
        c.execute('''
            CREATE TABLE IF NOT EXISTS dispositivos (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ip TEXT,
                mac TEXT,
                fabricante TEXT,
                so TEXT,
                status TEXT,
                portas_servicos TEXT,
                data_hora TEXT,
                flag INTEGER
            )
        ''')
        conn.commit()
        conn.close()

    def registrar_dispositivo(self, dispositivo):
        """Registra ou atualiza um dispositivo, acumulando histórico. Flag: 1 = novo, 0 = conhecido"""
        conn = sqlite3.connect(self.DB_FILE)
        c = conn.cursor()
        
        c.execute("SELECT id, portas_servicos, status, data_hora, fabricante, so FROM dispositivos WHERE ip=? AND mac=?",
                (dispositivo['ip'], dispositivo['mac_address']))
        row = c.fetchone()
        
        agora = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        if row:
            # Dispositivo conhecido
            id_dispositivo = row[0]
            flag = 0
            historico_status = row[2] + f"; {dispositivo.get('status','N/D')}"
            historico_datas = row[3] + f"; {agora}"
            historico_portas = json.loads(row[1]) if row[1] else []

            for novo_serv in dispositivo.get('servicos', []):
                encontrado = False
                for h in historico_portas:
                    if (h['porta'] == novo_serv['porta'] and
                        h['protocolo'] == novo_serv['protocolo'] and
                        h['nome'] == novo_serv['nome']):
                        h['data_fim'] = agora
                        encontrado = True
                        break
                if not encontrado:
                    historico_portas.append({
                        'porta': novo_serv['porta'],
                        'protocolo': novo_serv['protocolo'],
                        'nome': novo_serv['nome'],
                        'versao': novo_serv.get('versao',''),
                        'data_inicio': agora,
                        'data_fim': agora
                    })

            c.execute('''
                UPDATE dispositivos
                SET fabricante=?, so=?, status=?, portas_servicos=?, data_hora=?, flag=?
                WHERE id=?
            ''', (
                dispositivo.get('fabricante') or row[4] or "N/D",
                dispositivo.get('so') or row[5] or "Desconhecido",
                historico_status,
                json.dumps(historico_portas, ensure_ascii=False),
                historico_datas,
                flag,
                id_dispositivo
            ))
        else:
            # Novo dispositivo
            flag = 1
            servicos_com_datas = []
            for s in dispositivo.get('servicos', []):
                servicos_com_datas.append({
                    'porta': s['porta'],
                    'protocolo': s['protocolo'],
                    'nome': s['nome'],
                    'versao': s.get('versao',''),
                    'data_inicio': agora,
                    'data_fim': agora
                })

            c.execute('''
                INSERT INTO dispositivos (ip, mac, fabricante, so, status, portas_servicos, data_hora, flag)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                dispositivo['ip'],
                dispositivo['mac_address'],
                dispositivo.get('fabricante') or "N/D",
                dispositivo.get('so') or "Desconhecido",
                dispositivo.get('status','N/D'),
                json.dumps(servicos_com_datas, ensure_ascii=False),
                agora,
                flag
            ))

        conn.commit()
        conn.close()





    def exibir_historico(self):
        conn = sqlite3.connect(self.DB_FILE)
        c = conn.cursor()
        c.execute("SELECT ip, mac, fabricante, so, status, portas_servicos, data_hora, flag FROM dispositivos")
        rows = c.fetchall()
        conn.close()
        return rows
    
    def limpar_historico(self):
        """Zera o histórico de dispositivos na rede."""
        conn = sqlite3.connect(self.DB_FILE)
        c = conn.cursor()

        # Confirma que a tabela existe e limpa os dados
        c.execute("DELETE FROM dispositivos")
        conn.commit()
        conn.close()

    # ------------------- MAC Vendors -------------------
    

    # ------------------- Rede -------------------
    def obter_faixa_ip_local(self):
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            local_ip = s.getsockname()[0]
            s.close()
            ip_interface = ipaddress.ip_interface(f"{local_ip}/24")
            return str(ip_interface.network)
        except Exception as e:
            print(f"Não foi possível obter a faixa de IP local. Usando 192.168.1.0/24 como padrão. Detalhes: {e}")
            return "192.168.1.0/24"

    # ------------------- Scan -------------------

    def descobrir_hosts_na_rede(self, faixa_ip=None, scan_detalhado=False):
        faixa_ip = faixa_ip or self.obter_faixa_ip_local()
        nm = nmap.PortScanner()
        arguments = "-sS -sV -O -p 22,80,443" if scan_detalhado else "-sn"

        try:
            nm.scan(hosts=faixa_ip, arguments=arguments)
        except nmap.nmap.PortScannerError as e:
            print(f"Erro: {e}")
            return {}

        # Recupera todos os dispositivos já cadastrados
        conn = sqlite3.connect(self.DB_FILE)
        c = conn.cursor()
        c.execute("SELECT ip, mac FROM dispositivos")
        dispositivos_cadastrados = {(row[0], row[1]) for row in c.fetchall()}
        conn.close()

        hosts_descobertos = {}
        detectados_hoje = set()

        for host in nm.all_hosts():
            mac = nm[host]['addresses'].get('mac', 'N/A')
            so = "Desconhecido"
            if scan_detalhado and 'osmatch' in nm[host] and nm[host]['osmatch']:
                so = nm[host]['osmatch'][0]['name']

            dispositivo = {
                'ip': host,
                'status': 'up',
                'mac_address': mac,
                'fabricante': MacVendor.obter_fabricante_mac(mac),
                'so': so,
                'servicos': []
            }

            if scan_detalhado:
                for proto in nm[host].all_protocols():
                    for porta, servico in nm[host][proto].items():
                        dispositivo['servicos'].append({
                            'porta': porta,
                            'protocolo': proto,
                            'nome': servico['name'],
                            'versao': servico.get('version', '')
                        })

            detectados_hoje.add((host, mac))
            self.registrar_dispositivo(dispositivo)
            hosts_descobertos[host] = dispositivo

        # Atualiza status para 'down' para dispositivos não detectados
        for ip, mac in dispositivos_cadastrados:
            if (ip, mac) not in detectados_hoje:
                self.registrar_dispositivo({
                    'ip': ip,
                    'mac_address': mac,
                    'status': 'down',
                    'fabricante': None,
                    'so': None,
                    'servicos': []
                })

        return hosts_descobertos
