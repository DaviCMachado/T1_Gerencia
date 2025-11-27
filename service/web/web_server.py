from pathlib import Path
import sys
import asyncio
import random
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


# Exemplo de OID usado no seu SNMP local; ajuste conforme seu MIB
ACTIONS_OID = "1.3.6.1.4.1.42.1.1"


@app.get("/", response_class=HTMLResponse)
def ui_index():
    # serve a página web index.html localizada na mesma pasta deste módulo
    index_path = root_dir / "index.html"
    if index_path.exists():
        return HTMLResponse(index_path.read_text(encoding="utf-8"))
    return HTMLResponse("<h3>UI not found. Create web/index.html</h3>")


@app.post("/api/scan/start")
async def api_scan_start():
    """Clique 'start' -> traduz para um SET em ACTIONS_OID.1 = 1"""
    if VariableBinding is None or Integer is None:
        return JSONResponse({"error": "SNMP helper classes not available"}, status_code=500)
    vb = VariableBinding(f"{ACTIONS_OID}.1", Integer(1))
    res = await call_snmp_handler(getattr(snmp_service, "SnmpSetContext", lambda: None)(), [vb])
    return JSONResponse(res)


@app.post("/api/scan/stop")
async def api_scan_stop():
    if VariableBinding is None or Integer is None:
        return JSONResponse({"error": "SNMP helper classes not available"}, status_code=500)
    vb = VariableBinding(f"{ACTIONS_OID}.2", Integer(1))
    res = await call_snmp_handler(getattr(snmp_service, "SnmpSetContext", lambda: None)(), [vb])
    return JSONResponse(res)


@app.post("/api/scan/restart")
async def api_scan_restart():
    if VariableBinding is None or Integer is None:
        return JSONResponse({"error": "SNMP helper classes not available"}, status_code=500)
    vb = VariableBinding(f"{ACTIONS_OID}.3", Integer(1))
    res = await call_snmp_handler(getattr(snmp_service, "SnmpSetContext", lambda: None)(), [vb])
    return JSONResponse(res)


@app.get("/api/metrics")
async def api_metrics():
    """Consulta alguns OIDs de métricas (GET). Ajuste as OIDs conforme sua MIB."""
    req_oids = [
        "1.3.6.1.4.1.42.1.2.1",
        "1.3.6.1.4.1.42.1.2.2",
        "1.3.6.1.4.1.42.1.2.3",
    ]
    if VariableBinding is None or Null is None:
        return JSONResponse({"error": "SNMP helper classes not available"}, status_code=500)
    vbs = [VariableBinding(oid, Null()) for oid in req_oids]
    res = await call_snmp_handler(getattr(snmp_service, "SnmpGetContext", lambda: None)(), vbs)
    return JSONResponse(res)


@app.post("/api/snmp/get")
async def api_snmp_get(req: Request):
    """Permite GET genérico por lista de OIDs (body: {'oids': ['1.2.3', ...]})"""
    body = await req.json()
    oids = body.get("oids", [])
    if not isinstance(oids, list) or len(oids) == 0:
        return JSONResponse({"error": "expecting JSON with 'oids': [..]"}, status_code=400)
    if VariableBinding is None or Null is None:
        return JSONResponse({"error": "SNMP helper classes not available"}, status_code=500)
    vbs = [VariableBinding(str(o), Null()) for o in oids]
    res = await call_snmp_handler(getattr(snmp_service, "SnmpGetContext", lambda: None)(), vbs)
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
    vbs = []
    for p in pairs:
        oid = str(p.get("oid"))
        typ = p.get("type", "Integer")
        val = p.get("value")
        if typ == "Integer" and Integer is not None:
            vbs.append(VariableBinding(oid, Integer(val)))
        elif typ == "OctetString" and OctetString is not None:
            vbs.append(VariableBinding(oid, OctetString(val)))
        else:
            # fallback: try to construct with provided class in snmp_service
            cls = getattr(snmp_service, typ, None)
            if cls is not None:
                vbs.append(VariableBinding(oid, cls(val)))
            else:
                return JSONResponse({"error": f"unsupported type {typ} or missing class"}, status_code=400)
    res = await call_snmp_handler(getattr(snmp_service, "SnmpSetContext", lambda: None)(), vbs)
    return JSONResponse(res)


if __name__ == "__main__":
    # permite executar diretamente: python web_server.py
    import uvicorn
    uvicorn.run("web.web_server:app", host="127.0.0.1", port=8080, reload=True)