import sqlite3
import json
from pathlib import Path
from datetime import datetime

class DB_Manager:
    def __init__(self, db_file=None, mac_vendors_file=None):
        self.DB_FILE = db_file or (Path(__file__).parent / "historico_redes.db")
        self.MAC_VENDORS_FILE = mac_vendors_file or (Path(__file__).parent.parent / "data/mac-vendors.json")
        self.criar_banco()

    # ------------------- Banco de dados -------------------
    def criar_banco(self):
        conn = sqlite3.connect(self.DB_FILE)
        c = conn.cursor()
        c.execute('''
            CREATE TABLE IF NOT EXISTS devices (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ip TEXT UNIQUE,
                mac TEXT,
                fabricante TEXT,
                so TEXT
            )
        ''')
        c.execute('''
            CREATE TABLE IF NOT EXISTS operations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                device_id INTEGER,
                timestamp TEXT,
                tipo TEXT,
                portas TEXT,
                FOREIGN KEY(device_id) REFERENCES devices(id) ON DELETE CASCADE
            )
        ''')
        conn.commit()
        conn.close()

    # ------------------- Registro de dispositivos -------------------
    def registrar_dispositivo(self, dispositivo, tipo="up"):
        conn = sqlite3.connect(self.DB_FILE)
        c = conn.cursor()
        c.execute("SELECT id, mac, fabricante, so FROM devices WHERE ip=?", (dispositivo['ip'],))
        row = c.fetchone()

        if row:
            device_id = row[0]
            # Atualiza apenas se a nova informação não for nula
            c.execute("""
                UPDATE devices
                SET mac=?, fabricante=?, so=?
                WHERE id=?
            """, (
                dispositivo.get('mac') or row[1],
                dispositivo.get('fabricante') or row[2],
                dispositivo.get('so') or row[3],
                device_id
            ))
        else:
            c.execute("""
                INSERT INTO devices (ip, mac, fabricante, so)
                VALUES (?, ?, ?, ?)
            """, (
                dispositivo['ip'],
                dispositivo.get('mac'),
                dispositivo.get('fabricante') or "N/D",
                dispositivo.get('so') or "Desconhecido"
            ))
            device_id = c.lastrowid
            # Se for a primeira vez que vemos, o tipo deve ser 'novo_dispositivo'
            if tipo == 'up':
                tipo = 'novo_dispositivo'

        portas_json = json.dumps(dispositivo.get('servicos', []), ensure_ascii=False)
        c.execute("""
            INSERT INTO operations (device_id, timestamp, tipo, portas)
            VALUES (?, ?, ?, ?)
        """, (
            device_id,
            datetime.now().strftime('%Y-%m-%d %H:%M:%S'), # Formato mais legível
            tipo,
            portas_json
        ))
        conn.commit()
        conn.close()

    # ------------------- Consultas -------------------
    
    # MUDANÇA PRINCIPAL: ESTA É A FUNÇÃO QUE VOCÊ DEVE USAR NA SUA API
    def exibir_dispositivos_agregados(self):
        """
        Busca todos os dispositivos e agrega seu histórico em um formato ideal para a GUI.
        Retorna uma lista de dicionários.
        """
        conn = sqlite3.connect(self.DB_FILE)
        # Esta linha mágica faz o sqlite retornar resultados que se comportam como dicionários
        conn.row_factory = sqlite3.Row
        c = conn.cursor()
        
        # Query SQL poderosa que já formata os dados como a GUI espera
        c.execute("""
            SELECT
                d.ip,
                d.mac,
                d.fabricante,
                d.so,
                GROUP_CONCAT(o.timestamp, '; ') as data_hora,
                GROUP_CONCAT(o.tipo, '; ') as status,
                -- Pega o último registro de portas que não estava vazio
                (SELECT portas FROM operations WHERE device_id = d.id AND portas IS NOT NULL AND portas != '[]' ORDER BY timestamp DESC LIMIT 1) as portas_servicos,
                -- Cria a flag 'novo' se algum registro for do tipo 'novo_dispositivo'
                MAX(CASE WHEN o.tipo = 'novo_dispositivo' THEN 1 ELSE 0 END) as flag
            FROM
                devices d
            LEFT JOIN
                operations o ON d.id = o.device_id
            GROUP BY
                d.id
            ORDER BY
                d.id
        """)
        
        rows = c.fetchall()
        conn.close()
        
        # Converte a lista de objetos 'Row' em uma lista de dicionários puros para o JSON
        return [dict(row) for row in rows]

    def exibir_dispositivos(self):
        conn = sqlite3.connect(self.DB_FILE)
        c = conn.cursor()
        c.execute("SELECT ip, mac, fabricante, so FROM devices")
        rows = c.fetchall()
        conn.close()
        return rows

    def limpar_historico(self):
        conn = sqlite3.connect(self.DB_FILE)
        c = conn.cursor()
        c.execute("DELETE FROM operations")
        c.execute("DELETE FROM devices")
        conn.commit()
        conn.close()
