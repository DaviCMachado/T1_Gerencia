import sqlite3
from pathlib import Path

DB_FILE = Path(__file__).parent / "historico_redes.db"

def limpar_historico():
    """Zera o histórico de dispositivos na rede."""
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()

    # Confirma que a tabela existe e limpa os dados
    c.execute("DELETE FROM dispositivos")
    conn.commit()
    conn.close()

if __name__ == "__main__":
    limpar_historico()
