import json
from pathlib import Path

class MacVendor:
    def __init__(self):
        self.vendors = self.carregar_mac_vendors()

    def carregar_mac_vendors(self):
        path = Path(__file__).parent.parent / "data/mac-vendors.json"
        if not path.exists():
            print("⚠️ Arquivo mac-vendors.json não encontrado. Fabricantes não serão identificados.")
            return {}
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        vendors = {}
        for item in data:
            prefixo = item["macPrefix"].replace(":", "").upper()
            vendors[prefixo] = item["vendorName"]
        print(f"✅ Carregado {len(vendors)} fabricantes de MAC.")
        return vendors

    def obter_fabricante_mac(self, mac_address):
            if not mac_address or mac_address == "N/A":
                return "N/A"
            prefixo = mac_address.upper().replace(":", "")[:6]
            return self.vendors.get(prefixo, "Fabricante não encontrado")
    
MacVendor.carregar_mac_vendors()