import snmp_agent
from snmp_agent import Integer, OctetString, IpAddress
import ipaddress

# base OID (enterprises.42)
BASE_OID = "1.3.6.1.4.1.42"

# tuas actions/status/entries
ACTIONS_OID = f"{BASE_OID}.1.1"
STATUS_OID  = f"{BASE_OID}.1.2"
DEVICES_OID = f"{BASE_OID}.2.1.1"


async def snmp_handler(req: snmp_agent.SNMPRequest) -> snmp_agent.SNMPResponse:
    vbs = []

    for vb in req.variable_bindings:
        oid = vb.oid
        value = vb.value

        # --- ACTIONS (read-write) ---
        if oid == f"{ACTIONS_OID}.1":  # scannerStart
            if isinstance(value, Integer) and value.value == 1:
                print("[SNMP] Trigger scannerStart")
                from main import run_scanners_in_background
                run_scanners_in_background()
            vbs.append(snmp_agent.VariableBinding(oid, Integer(1)))

        elif oid == f"{ACTIONS_OID}.2":  # scannerStop
            if isinstance(value, Integer) and value.value == 1:
                print("[SNMP] Trigger scannerStop")
                from main import stop_scanners_in_background
                stop_scanners_in_background()
            vbs.append(snmp_agent.VariableBinding(oid, Integer(1)))

        elif oid == f"{ACTIONS_OID}.3":  # scannerRestart
            print("[SNMP] Trigger scannerRestart")
            from main import stop_scanners_in_background, run_scanners_in_background
            stop_scanners_in_background()
            run_scanners_in_background()
            vbs.append(snmp_agent.VariableBinding(oid, Integer(1)))

        # --- STATUS (read-only) ---
        elif oid == f"{STATUS_OID}.1":  # runningCount
            from main import available_scanners, ScanStatus
            running = sum(1 for s in available_scanners if s.get_status() == ScanStatus.Scanning)
            vbs.append(snmp_agent.VariableBinding(oid, Integer(running)))

        elif oid == f"{STATUS_OID}.2":  # idleCount
            from main import available_scanners, ScanStatus
            idle = sum(1 for s in available_scanners if s.get_status() == ScanStatus.Idle)
            vbs.append(snmp_agent.VariableBinding(oid, Integer(idle)))

        elif oid == f"{STATUS_OID}.3":  # finishedCount
            from main import available_scanners, ScanStatus
            finished = sum(1 for s in available_scanners if s.get_status() == ScanStatus.Finished)
            vbs.append(snmp_agent.VariableBinding(oid, Integer(finished)))

        # --- DEVICE TABLE (read-only) ---
        elif oid.startswith(DEVICES_OID):
            # OID format: ...2.1.1.1.<index>.<field>
            # example: 1.3.6.1.4.1.42.2.1.1.1.2 (deviceIndex 2)
            parts = oid.split(".")
            try:
                idx = int(parts[-2])
                field = int(parts[-1])
            except:
                continue

            from main import merged_devices
            if 0 <= idx - 1 < len(merged_devices):
                dev = merged_devices[idx - 1]
                if field == 1:  # deviceIndex
                    vbs.append(snmp_agent.VariableBinding(oid, Integer(idx)))
                elif field == 2:  # deviceIP
                    try:
                        ip = ipaddress.ip_address(dev.ip)
                        vbs.append(snmp_agent.VariableBinding(oid, IpAddress(str(ip))))
                    except:
                        vbs.append(snmp_agent.VariableBinding(oid, IpAddress("0.0.0.0")))
                elif field == 3:  # deviceStatus
                    # map status: assume active(1) if online, inactive(2) otherwise
                    vbs.append(snmp_agent.VariableBinding(oid, Integer(1)))
            else:
                vbs.append(snmp_agent.VariableBinding(oid, Integer(0)))  # sem dado

        else:
            # qualquer OID não reconhecido -> noSuchName
            vbs.append(snmp_agent.VariableBinding(oid, OctetString("noSuchName")))
    res = req.create_response(vbs)
    return res