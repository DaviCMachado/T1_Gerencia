from pathlib import Path
import sys
import asyncio
import random
import os
from typing import List, Any

# garante que a pasta pai (service) esteja no sys.path para importar snmp.py
_root_dir = Path(__file__).resolve().parent
_service_dir = str(_root_dir.parent)
if _service_dir not in sys.path:
    sys.path.insert(0, _service_dir)

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

# importa handler e contextos já criados no service/snmp.py
# espera-se que exista service/snmp.py contendo handler(s)
import snmp as snmp_service
# classes auxiliares do pacote snmp local (ajuste se o seu projeto tiver nomes diferentes)
try:
    import snmp_agent.snmp as snmp_lib
    from snmp_agent.snmp import SNMPRequest, VariableBinding, Integer, OctetString, Null, VERSION
except Exception:
    # fallback: tente importar nomes diretamente do módulo snmp_service se já os exporta
    SNMPRequest = getattr(snmp_service, "SNMPRequest", None)
    VariableBinding = getattr(snmp_service, "VariableBinding", None)
    Integer = getattr(snmp_service, "Integer", None)
    OctetString = getattr(snmp_service, "OctetString", None)
    Null = getattr(snmp_service, "Null", None)
    VERSION = getattr(snmp_service, "VERSION", None)

# try import pysnmp async API
try:
    from pysnmp.hlapi.asyncio import (
        SnmpEngine, CommunityData, UdpTransportTarget, ContextData,
        ObjectType, ObjectIdentity, get_cmd, set_cmd, Integer as PInteger, OctetString as POctetString, Null as PNull
    )
    _HAS_PYSNMP = True
except Exception as ex:
    print("pysnmp import error:", ex)
    _HAS_PYSNMP = False

app = FastAPI()

# monta /static para servir outros assets se existir
root_dir = Path(__file__).parent
static_dir = root_dir / "static"
if static_dir.exists():
    app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")


async def _maybe_await(func, *args, **kwargs):
    """Chama func; await se for coroutine."""
    res = func(*args, **kwargs)
    if asyncio.iscoroutine(res):
        return await res
    return res


async def call_snmp_handler(context, vbs: List[Any]):
    """
    Monta um objeto SNMPRequest (quando as classes existirem) e chama o handler do módulo snmp_service.
    Retorna um dicionário serializável com o resultado.
    """
    # monta request_id aleatório
    request_id = random.randint(1, 2**30)
    req_obj = None
    if SNMPRequest is not None:
        try:
            req_obj = SNMPRequest(
                version=(VERSION.V2C if VERSION is not None else 1),
                community="public",
                context=context,
                request_id=request_id,
                non_repeaters=0,
                max_repetitions=0,
                variable_bindings=vbs
            )
        except Exception:
            req_obj = None

    # se o módulo snmp_service expõe uma função helper para criar PDU, tente usá-la
    handler = getattr(snmp_service, "snmp_handler", None)
    if handler is None:
        return {"error": "snmp_handler not found in snmp module"}

    # chama handler (assume que aceita um objeto SNMPRequest ou os vbs diretamente)
    try:
        if req_obj is not None:
            resp = await _maybe_await(handler, req_obj)
        else:
            # fallback: chamar com (context, vbs)
            resp = await _maybe_await(handler, context, vbs)
    except Exception as e:
        return {"error": "handler raised exception", "detail": str(e)}

    # tenta extrair variable_bindings do response
    vbl = getattr(resp, "variable_bindings", None)
    if vbl is None:
        # se resp for dicionário serializável, devolve diretamente
        if isinstance(resp, dict):
            return resp
        # fallback formatação
        try:
            return {"raw": repr(resp)}
        except Exception:
            return {"raw": str(resp)}

    out = []
    for vb in vbl:
        oid = getattr(vb, "oid", getattr(vb, "name", None))
        val_obj = getattr(vb, "value", None)
        val = None
        tname = None
        if val_obj is not None:
            tname = val_obj.__class__.__name__
            # valor pode estar em atributo .value ou str()
            val = getattr(val_obj, "value", None)
            if val is None:
                try:
                    val = str(val_obj)
                except Exception:
                    val = None
        out.append({"oid": oid, "value": val, "type": tname})
    return {"variable_bindings": out}


# OIDs extracted from your MIB (desc.mib)
# Base: enterprises(1.3.6.1.4.1).42 -> discoveryMIB
# autoDiscovery = discoveryMIB.1 -> 1.3.6.1.4.1.42.1
# scanners = autoDiscovery.1 -> 1.3.6.1.4.1.42.1.1
# actions = scanners.1 -> 1.3.6.1.4.1.42.1.1.1

# Fully qualified OIDs for actions
SCANNER_START_OID = "1.3.6.1.4.1.42.1.1.1.1"
SCANNER_STOP_OID = "1.3.6.1.4.1.42.1.1.1.2"
SCANNER_RESTART_OID = "1.3.6.1.4.1.42.1.1.1.3"

# Metrics (status counters): scanners.status -> 1.3.6.1.4.1.42.1.2
RUNNING_COUNT_OID = "1.3.6.1.4.1.42.1.1.2.1"
IDLE_COUNT_OID = "1.3.6.1.4.1.42.1.1.2.2"
FINISHED_COUNT_OID = "1.3.6.1.4.1.42.1.1.2.3"

# SNMP target config (overridable via env)
_SNMP_HOST = os.environ.get("SNMP_AGENT_HOST", "127.0.0.1")
_SNMP_PORT = int(os.environ.get("SNMP_AGENT_PORT", "161"))
_SNMP_COMMUNITY = os.environ.get("SNMP_COMMUNITY", "public")
 

async def pysnmp_get(oids: List[str]):
    if not _HAS_PYSNMP:
        return {"error": "pysnmp not installed"}
    try:
        engine = SnmpEngine()
        object_types = [ObjectType(ObjectIdentity(str(oid))) for oid in oids]
        target = await UdpTransportTarget.create((_SNMP_HOST, _SNMP_PORT))
        errorIndication, errorStatus, errorIndex, varBinds = await get_cmd(
            engine,
            CommunityData(_SNMP_COMMUNITY, mpModel=1),  # SNMPv2c
            target,
            ContextData(),
            *object_types
        )
        if errorIndication:
            return {"error": str(errorIndication)}
        if errorStatus:
            return {"error": str(errorStatus.prettyPrint())}
        out = []
        for name, val in varBinds:
            out.append({"oid": str(name), "value": str(val), "type": val.__class__.__name__})
        return {"variable_bindings": out}
    except Exception as e:
        return {"error": "exception in pysnmp_get", "detail": str(e)}


async def pysnmp_set(pairs: List[dict]):
    """
    pairs: [{'oid': '1.2.3', 'type': 'Integer', 'value': 1}, ...]
    """
    if not _HAS_PYSNMP:
        return {"error": "pysnmp not installed"}
    try:
        engine = SnmpEngine()
        object_types = []
        for p in pairs:
            oid = str(p.get("oid"))
            typ = p.get("type", "Integer")
            val = p.get("value")
            # map types to pysnmp types
            if typ == "Integer":
                v = PInteger(int(val))
            elif typ == "OctetString":
                v = POctetString(str(val))
            elif typ == "Null":
                v = PNull()
            else:
                # fallback: try Integer then OctetString
                try:
                    v = PInteger(int(val))
                except Exception:
                    v = POctetString(str(val))
            object_types.append(ObjectType(ObjectIdentity(oid), v))

        target = await UdpTransportTarget.create((_SNMP_HOST, _SNMP_PORT))
        errorIndication, errorStatus, errorIndex, varBinds = await set_cmd(
            engine,
            CommunityData(_SNMP_COMMUNITY, mpModel=1),
            target,
            ContextData(),
            *object_types
        )
        if errorIndication:
            return {"error": str(errorIndication)}
        if errorStatus:
            return {"error": str(errorStatus.prettyPrint())}
        out = []
        for name, val in varBinds:
            out.append({"oid": str(name), "value": str(val), "type": val.__class__.__name__})
        return {"variable_bindings": out}
    except Exception as e:
        return {"error": "exception in pysnmp_set", "detail": str(e)}


@app.get("/", response_class=HTMLResponse)
def ui_index():
    # serve a página web index.html localizada na mesma pasta deste módulo
    index_path = root_dir / "index.html"
    if index_path.exists():
        return HTMLResponse(index_path.read_text(encoding="utf-8"))
    return HTMLResponse("<h3>UI not found. Create web/index.html</h3>")


@app.post("/api/scan/start")
async def api_scan_start():
    """Start scanners: perform SNMP SET to scannerStart OID = 1"""
    # these MIB objects are scalar OBJECT-TYPEs; use the instance suffix .0 for SET
    pairs = [{"oid": f"{SCANNER_START_OID}", "type": "Integer", "value": 1}]
    res = await pysnmp_set(pairs)
    return JSONResponse(res)


@app.post("/api/scan/stop")
async def api_scan_stop():
    pairs = [{"oid": f"{SCANNER_STOP_OID}", "type": "Integer", "value": 1}]
    res = await pysnmp_set(pairs)
    return JSONResponse(res)


@app.post("/api/scan/restart")
async def api_scan_restart():
    pairs = [{"oid": f"{SCANNER_RESTART_OID}", "type": "Integer", "value": 1}]
    res = await pysnmp_set(pairs)
    return JSONResponse(res)


@app.get("/api/metrics")
async def api_metrics():
    """Consulta alguns OIDs de métricas (GET). Ajuste as OIDs conforme sua MIB."""
    # these are scalar counters; request their instance (.0)
    req_oids = [f"{RUNNING_COUNT_OID}", f"{IDLE_COUNT_OID}", f"{FINISHED_COUNT_OID}"]
    res = await pysnmp_get(req_oids)
    return JSONResponse(res)


@app.post("/api/snmp/get")
async def api_snmp_get(req: Request):
    """Permite GET genérico por lista de OIDs (body: {'oids': ['1.2.3', ...]})"""
    body = await req.json()
    oids = body.get("oids", [])
    if not isinstance(oids, list) or len(oids) == 0:
        return JSONResponse({"error": "expecting JSON with 'oids': [..]"}, status_code=400)
    res = await pysnmp_get([str(o) for o in oids])
    return JSONResponse(res)


@app.post("/api/snmp/set")
async def api_snmp_set(req: Request):
    """
    Permite SET genérico.
    Body: {'pairs': [{'oid':'1.2.3','type':'Integer','value':1}, ...]}
    Tipos suportados dependem das classes disponíveis (Integer, OctetString, etc).
    """
    body = await req.json()
    pairs = body.get("pairs", [])
    if not isinstance(pairs, list) or len(pairs) == 0:
        return JSONResponse({"error": "expecting JSON with 'pairs': [..]"}, status_code=400)
    # Validate pairs minimally and pass to pysnmp_set
    valid = []
    for p in pairs:
        oid = str(p.get("oid"))
        typ = p.get("type", "Integer")
        if "value" not in p:
            return JSONResponse({"error": "each pair must include 'value'"}, status_code=400)
        val = p.get("value")
        valid.append({"oid": oid, "type": typ, "value": val})
    res = await pysnmp_set(valid)
    return JSONResponse(res)


if __name__ == "__main__":
    # permite executar diretamente: python web_server.py
    import uvicorn
    uvicorn.run("web.web_server:app", host="127.0.0.1", port=8080, reload=True)