### Arquivo usado para testarmos SNMP via linha de comando de forma simples. ###
### Basicamente roda os comandos snmpset, snmpget e snmpwalk e exibe os resultados. ###
### Necessita instalar net-snmp, testado no windows          ###
### No momento, compreende toda a nossa MIB               ###

import subprocess
import time

# --- Configurações globais ---
COMMUNITY = "public"
HOST = "localhost"

# Intervalos de espera em segundos
PAUSE_AFTER_START = 10  # espera após iniciar scanners antes de consultar status
PAUSE_SET = 3          # tempo entre cada SETREQUEST (exceto start scanner)
PAUSE_GET = 3          # tempo entre cada GETREQUEST
PAUSE_WALK = 3         # tempo entre cada WALK

# OIDs da MIB
OID_BASE = "1.3.6.1.4.1.42.1.1"       # scanner actions
COUNTERS_OIDS = {
    "runningCount": "1.3.6.1.4.1.42.1.2.1",
    "idleCount": "1.3.6.1.4.1.42.1.2.2",
    "finishedCount": "1.3.6.1.4.1.42.1.2.3"
}
DEVICES_OID = "1.3.6.1.4.1.42.1.2.1.1"  # device table base

# --- Funções utilitárias ---
def run_snmp_command(cmd):
    print(f"\nExecutando: {' '.join(cmd)}")
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        return result.stdout.strip()
    except subprocess.CalledProcessError as e:
        if e.stdout:
            print(e.stdout)
        if e.stderr:
            print(f"Erro protocolar (ignorado): {e.stderr.strip()}")
        return e.stdout.strip() if e.stdout else None

def snmp_set(oid, value, description="", pause_after=True):
    print(f"\nSETREQUEST {oid} = {value}")
    if description:
        print(f"Descrição: {description}")
    cmd = ["snmpset", "-v2c", "-c", COMMUNITY, HOST, oid, "i", str(value)]
    output = run_snmp_command(cmd)
    if output:
        print(f"Resultado: {output}")
    if pause_after:
        time.sleep(PAUSE_SET)

def snmp_get(oid, description=""):
    print(f"\nGETREQUEST {oid}")
    if description:
        print(f"Descrição: {description}")
    cmd = ["snmpget", "-v2c", "-c", COMMUNITY, HOST, oid]
    output = run_snmp_command(cmd)
    if output:
        print(f"Resultado: {output}")
    time.sleep(PAUSE_GET)
    return output

def snmp_walk(oid, description=""):
    print(f"\nWALK {oid}")
    if description:
        print(f"Descrição: {description}")
    cmd = ["snmpwalk", "-v2c", "-c", COMMUNITY, HOST, oid]
    output = run_snmp_command(cmd)
    time.sleep(PAUSE_WALK)
    return output

def print_scanner_status():
    running = snmp_get(COUNTERS_OIDS["runningCount"], "Quantidade de scanners rodando")
    idle = snmp_get(COUNTERS_OIDS["idleCount"], "Quantidade de scanners ociosos")
    finished = snmp_get(COUNTERS_OIDS["finishedCount"], "Quantidade de scanners que já terminaram")
    print(f"\nStatus dos scanners -> Rodando: {running.split()[-1]}, Ociosos: {idle.split()[-1]}, Finalizados: {finished.split()[-1]}")

# --- Main ---
def main():
    print("=== INÍCIO DO TESTE SNMP ===")

    # --- Inicia scanners (tempo exclusivo) ---
    snmp_set(f"{OID_BASE}.1", 1, "Inicia todos os scanners cadastrados", pause_after=False)
    time.sleep(PAUSE_AFTER_START)

    # --- Status após iniciar scanners ---
    print("\n--- STATUS DOS SCANNERS APÓS INICIAR ---")
    print_scanner_status()

    # --- Tabela de dispositivos ---
    devices_output = snmp_walk(DEVICES_OID, "Exibe tabela de dispositivos descobertos pelo agente")
    
    # --- Para scanners ---
    snmp_set(f"{OID_BASE}.2", 1, "Para todos os scanners que estão rodando", pause_after=True)

    # --- Status após parar scanners ---
    print("\n--- STATUS DOS SCANNERS APÓS PARAR ---")
    print_scanner_status()

    # --- Construir e exibir tabela de dispositivos ---
    if devices_output:
        devices = {}
        for line in devices_output.splitlines():
            parts = line.split(" = ")
            if len(parts) != 2:
                continue
            oid, val = parts
            oid_parts = oid.strip().split(".")
            row = oid_parts[-1]
            col = oid_parts[-2]
            devices.setdefault(row, {})[col] = val

        print("\n=== TABELA DE DISPOSITIVOS ===")
        print(f"{'Índice':<6} {'IP':<16} {'Status':<10}")
        for row, cols in sorted(devices.items()):
            ip = cols.get('2', 'N/A')
            status_map = {'1': 'ONLINE', '2': 'OFFLINE', '3': 'UNKNOWN'}
            status = status_map.get(cols.get('3', '3').split(':')[1].strip(), 'UNKNOWN') if '3' in cols else 'UNKNOWN'
            idx = cols.get('1', row)
            print(f"{idx:<6} {ip:<16} {status:<10}")

    print("\n=== FIM DO TESTE SNMP ===")

if __name__ == "__main__":
    main()
