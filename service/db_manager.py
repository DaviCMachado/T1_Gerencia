import sqlite3
import json
from pathlib import Path
from datetime import datetime, timedelta

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
                so TEXT,
                last_seen TEXT
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
    def registrar_dispositivo(self, device: dict, tipo='up'):
        conn = sqlite3.connect(self.DB_FILE)
        c = conn.cursor()
        now = datetime.now().isoformat()

        # busca registro existente
        c.execute("SELECT id, last_seen FROM devices WHERE ip=?", (device['ip'],))
        row = c.fetchone()

        if row:
            device_id, last_seen = row
            # atualiza dados básicos + last_seen
            c.execute("""
                UPDATE devices
                SET mac=?, fabricante=?, so=?, last_seen=?
                WHERE id=?
            """, (
                device.get('mac'),
                device.get('fabricante'),
                device.get('so'),
                now,
                device_id
            ))

            # Verifica o último status
            last_op = c.execute("""
                SELECT tipo FROM operations
                WHERE device_id=? ORDER BY timestamp DESC LIMIT 1
            """, (device_id,)).fetchone()

            if not last_op or last_op[0] == 'down':
                # só insere 'up' se não havia ou se estava down
                portas_json = json.dumps(device.get('servicos', []), ensure_ascii=False)
                c.execute("""
                    INSERT INTO operations (device_id, timestamp, tipo, portas)
                    VALUES (?, ?, 'up', ?)
                """, (device_id, now, portas_json))

        else:
            # dispositivo novo → cria device e operation 'novo_dispositivo'
            c.execute("""
                INSERT INTO devices (ip, mac, fabricante, so, last_seen)
                VALUES (?, ?, ?, ?, ?)
            """, (
                device['ip'],
                device.get('mac'),
                device.get('fabricante'),
                device.get('so'),
                now
            ))
            device_id = c.lastrowid
            portas_json = json.dumps(device.get('servicos', []), ensure_ascii=False)
            c.execute("""
                INSERT INTO operations (device_id, timestamp, tipo, portas)
                VALUES (?, ?, 'novo_dispositivo', ?)
            """, (device_id, now, portas_json))

        conn.commit()
        conn.close()



    # ------------------- Sincronização periódica -------------------
    # método chamado a cada 5 minutos para marcar dispositivos inativos como offline
    def apply_sync_operations(self, offline_minutes=1):
    # def apply_sync_operations(self, offline_minutes=5):
        conn = sqlite3.connect(self.DB_FILE)
        c = conn.cursor()
        now = datetime.now()
        threshold = now - timedelta(minutes=offline_minutes)

        c.execute("SELECT id, last_seen FROM devices")
        for device_id, last_seen in c.fetchall():
            if not last_seen:
                continue
            if datetime.fromisoformat(last_seen) < threshold:
                # pega última operação
                last_op = c.execute("""
                    SELECT tipo FROM operations
                    WHERE device_id=? ORDER BY timestamp DESC LIMIT 1
                """, (device_id,)).fetchone()

                if not last_op or last_op[0] == 'up':
                    # só insere 'down' se o último status era 'up'
                    c.execute("""
                        INSERT INTO operations (device_id, timestamp, tipo, portas)
                        VALUES (?, ?, 'down', '[]')
                    """, (device_id, now.isoformat()))

        conn.commit()
        conn.close()





    # ------------------- Consultas -------------------
    
    def exibir_dispositivos_agregados(self):
        conn = sqlite3.connect(self.DB_FILE)
        conn.row_factory = sqlite3.Row
        c = conn.cursor()
        c.execute("""
            SELECT
                d.ip,
                d.mac,
                d.fabricante,
                d.so,
                d.last_seen,                       
                GROUP_CONCAT(o.timestamp, '; ') AS data_hora,
                GROUP_CONCAT(o.tipo, '; ') AS status,
                (SELECT portas
                FROM operations
                WHERE device_id = d.id
                AND portas IS NOT NULL
                AND portas != '[]'
                ORDER BY timestamp DESC
                LIMIT 1) AS portas_servicos,
                MAX(CASE WHEN o.tipo = 'novo_dispositivo' THEN 1 ELSE 0 END) AS flag
            FROM devices d
            LEFT JOIN operations o ON d.id = o.device_id
            GROUP BY d.id
            ORDER BY d.id
        """)
        rows = c.fetchall()
        conn.close()
        return [dict(row) for row in rows]


    def exibir_dispositivos(self):
        conn = sqlite3.connect(self.DB_FILE)
        c = conn.cursor()
        c.execute("SELECT ip, mac, fabricante, so FROM devices")
        rows = c.fetchall()
        conn.close()
        return rows
    
    def listar_operations(self):
        conn = sqlite3.connect(self.DB_FILE)
        conn.row_factory = sqlite3.Row
        c = conn.cursor()
        c.execute("""
            SELECT d.ip, o.tipo AS status, o.timestamp
            FROM operations o
            JOIN devices d ON o.device_id = d.id
            ORDER BY o.timestamp DESC
        """)
        rows = c.fetchall()
        conn.close()
        return [dict(row) for row in rows]

    def limpar_historico(self):
        conn = sqlite3.connect(self.DB_FILE)
        c = conn.cursor()
        c.execute("DELETE FROM operations")
        c.execute("DELETE FROM devices")
        conn.commit()
        conn.close()
