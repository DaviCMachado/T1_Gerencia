# --- snmp_patch.py ---
import asyncio
import snmp_agent
from snmp_agent.snmp import ASN1, SNMPRequest, SNMPResponse, VariableBinding, Integer, OctetString, Null

from main import available_scanners, run_scanners_in_background, stop_scanners_in_background, ScanStatus, db

class SnmpGetContext:
    pdu_type = ASN1.GET_REQUEST.code  # 160

# --- 1. Classe de contexto para SET ---
class SnmpSetContext:
    pdu_type = ASN1.SET_REQUEST.code  # 163

# --- 2. Patch do decode_request ---
def decode_request_patch(data: bytes) -> SNMPRequest:
    from snmp_agent.snmp import Decoder, VERSION, SnmpGetContext, SnmpGetNextContext, SnmpGetBulkContext

    decoder = Decoder(data=data)

    # --- Version & community ---
    decoder.enter()
    _, _value = decoder.read()
    version_code: int = _value
    if VERSION.V1.code == version_code:
        version = VERSION.V1
    elif VERSION.V2C.code == version_code:
        version = VERSION.V2C
    else:
        raise NotImplementedError(f"SNMP Version code '{version_code}' not implemented")
    _, _value = decoder.read()
    community = _value.decode()

    # --- PDU type ---
    _tag = decoder.peek()
    _pdu_type_code = _tag.cls | _tag.typ | _tag.nr
    print(f"[SNMP PATCH] pdu_type detectado: {_pdu_type_code}")  # <- seu print

    if ASN1.GET_REQUEST.code == _pdu_type_code:
        context = SnmpGetContext()
    elif ASN1.GET_NEXT_REQUEST.code == _pdu_type_code:
        context = SnmpGetNextContext()
    elif ASN1.GET_BULK_REQUEST.code == _pdu_type_code:
        context = SnmpGetBulkContext()
    elif ASN1.SET_REQUEST.code == _pdu_type_code:
        context = SnmpSetContext()
    else:
        raise NotImplementedError(f"PDU-TYPE code '{_pdu_type_code}' not implemented")

    decoder.enter()
    _, _value = decoder.read()
    request_id: int = _value

    # non_repeaters / max_repetitions
    non_repeaters = max_repetitions = 0
    if isinstance(context, SnmpGetBulkContext):
        _, _value = decoder.read()
        non_repeaters = _value
        _, _value = decoder.read()
        max_repetitions = _value
    else:
        _, _ = decoder.read()
        _, _ = decoder.read()

    # --- Variable bindings ---
    decoder.enter()
    variable_bindings = []
    while not decoder.eof():
        decoder.enter()
        _, oid_value = decoder.read()
        oid: str = oid_value
        _, val = decoder.read()

        # Detecta valor real no SET, senão Null
        if isinstance(context, SnmpSetContext):
            # Por simplicidade, tratamos Integer apenas
            value = Integer(val)
        else:
            value = Null()

        variable_bindings.append(VariableBinding(oid=oid, value=value))
        decoder.leave()
    decoder.leave()
    decoder.leave()
    decoder.leave()

    return SNMPRequest(
        version=version,
        community=community,
        context=context,
        request_id=request_id,
        non_repeaters=non_repeaters,
        max_repetitions=max_repetitions,
        variable_bindings=variable_bindings
    )

# --- 3. Aplica patch ---
snmp_agent.snmp.decode_request = decode_request_patch

# --- 4. Handler SNMP para SET ---
ACTIONS_OID = "1.3.6.1.4.1.42.1.1.1"


# --- garante que OIDs estejam ordenados ---
def parse_oid(oid_str):
    try:
        return tuple(int(x) for x in str(oid_str).split('.'))
    except Exception:
        return tuple()

async def snmp_handler(req: SNMPRequest):
    vbs = []
    is_set = isinstance(req.context, SnmpSetContext)

    for vb in req.variable_bindings:
        oid = vb.oid
        value = vb.value

        print(f"[SNMP HANDLER] pdu_type: {getattr(req.context, 'pdu_type', None)}")  # seu print de pdu

        if is_set:
            print("[SNMP HANDLER] Processando SetRequest...")
            # --- TRATAMENTO SETREQUEST ---
            if oid == f"{ACTIONS_OID}.1" and isinstance(value, Integer) and value.value == 1:
                print("[SNMP] SetRequest: scannerStart")
                asyncio.create_task(run_scanners_in_background())
                vbs.append(VariableBinding(oid, Integer(1)))

            elif oid == f"{ACTIONS_OID}.2" and isinstance(value, Integer) and value.value == 1:
                print("[SNMP] SetRequest: scannerStop")
                asyncio.create_task(stop_scanners_in_background())
                vbs.append(VariableBinding(oid, Integer(1)))

            elif oid == f"{ACTIONS_OID}.3" and isinstance(value, Integer) and value.value == 1:
                print("[SNMP] SetRequest: scannerRestart")
                async def restart():
                    await stop_scanners_in_background()
                    await run_scanners_in_background()
                asyncio.create_task(restart())
                vbs.append(VariableBinding(oid, Integer(1)))

            else:
                # Read-only ou OID desconhecido -> erro
                print(f"[SNMP] SetRequest: OID não gravável ou inválido. OID: {oid}")
                vbs.append(VariableBinding(oid, OctetString("notWritable")))

        else:
            print("[SNMP HANDLER] Processando GetRequest...")
            if oid == "1.3.6.1.4.1.42.1.1.2.1":  # runningCount
                running = sum(1 for s in available_scanners if s.get_status() == ScanStatus.Scanning)
                vbs.append(VariableBinding(oid, Integer(running)))
            elif oid == "1.3.6.1.4.1.42.1.1.2.2":  # idleCount
                idle = sum(1 for s in available_scanners if s.get_status() == ScanStatus.Idle)
                vbs.append(VariableBinding(oid, Integer(idle)))
            elif oid == "1.3.6.1.4.1.42.1.1.2.3":  # finishedCount
                finished = sum(1 for s in available_scanners if s.get_status() == ScanStatus.Finished)
                vbs.append(VariableBinding(oid, Integer(finished)))

            elif oid.startswith("1.3.6.1.4.1.42.1.2.1.1"):  # tabela de dispositivos
                table_oid_base = "1.3.6.1.4.1.42.1.2.1.1"
                all_devices = db.exibir_dispositivos_agregados()

                if not all_devices:
                    print("[SNMP] Nenhum dispositivo encontrado na base de dados.")

                # monta todas as entradas da tabela
                table_entries = []
                for idx, dev in enumerate(all_devices, start=1):
                    table_entries.append((f"{table_oid_base}.1.{idx}", Integer(idx)))
                    table_entries.append((f"{table_oid_base}.2.{idx}", OctetString(dev['ip'])))
                    status_val = {"active": 1, "inactive": 2, "unknown": 3}.get(dev.get('status', 'unknown'), 3)
                    table_entries.append((f"{table_oid_base}.3.{idx}", Integer(status_val)))

                table_entries.sort(key=lambda t: parse_oid(t[0]))

                # prepara contador para OIDs beyond table (um único base por resposta)
                if table_entries:
                    last_oid_parsed = parse_oid(table_entries[-1][0])
                    # base para incrementar o último componente e garantir OIDs strictamente crescentes
                    next_oid_counter = last_oid_parsed[-1] + 1
                else:
                    # se tabela vazia, cria base a partir do OID pedido (usar 1 como fallback)
                    next_oid_counter = 1

                # busca a entrada para cada OID pedido
                for req_vb in req.variable_bindings:
                    req_oid_parsed = parse_oid(req_vb.oid)
                    found = False

                    if getattr(req.context, "pdu_type", None) == ASN1.GET_REQUEST.code:
                        # GET: retorna valor exato se existir
                        for e_oid, e_val in table_entries:
                            if parse_oid(e_oid) == req_oid_parsed:
                                vbs.append(VariableBinding(e_oid, e_val))
                                found = True
                                break
                        if not found:
                            vbs.append(VariableBinding(req_vb.oid, OctetString("noSuchName")))

                    else:
                        # GETNEXT / GETBULK: retorna a próxima entrada > req_oid
                        for e_oid, e_val in table_entries:
                            if parse_oid(e_oid) > req_oid_parsed:
                                vbs.append(VariableBinding(e_oid, e_val))
                                found = True
                                break

                        if not found:
                            # fim da tabela -> devolver endOfMibView com OID incremental único
                            if table_entries:
                                next_oid = '.'.join(map(str, last_oid_parsed[:-1] + (next_oid_counter,)))
                                next_oid_counter += 1  # incrementa para próximo beyond table na mesma resposta
                            else:
                                # tabela vazia: devolve endOfMibView usando req OID com sufixo incremental
                                next_oid = '.'.join(map(str, req_oid_parsed + (next_oid_counter,)))
                                next_oid_counter += 1

                            # vbs.append(VariableBinding(next_oid, Null(Null.END_OF_MIB_VIEW)))
                            vbs.append(VariableBinding(next_oid, OctetString("End of Mib View")))

            else:
                vbs.append(VariableBinding(oid, OctetString("noSuchName")))

    vbs.sort(key=lambda vb: parse_oid(getattr(vb, 'oid', vb)))

    # --- Cria resposta SNMP sempre válida ---
    response = req.create_response(vbs)

    if not response:
        response = "DB VAZIO"

    return response