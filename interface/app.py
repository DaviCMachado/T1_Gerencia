import sys
import json
from pathlib import Path
from collections import defaultdict
from datetime import datetime
import asyncio
import aiohttp
import requests

from PySide6.QtWidgets import (
    QApplication, QWidget, QPushButton, QLabel, QStackedWidget,
    QVBoxLayout, QScrollArea
)
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QMovie
from qasync import QEventLoop

API_BASE = "http://localhost:80"  # ou IP do servidor

def send_start_request():
    try:
        requests.get(f"{API_BASE}/scan/start")
    except Exception as e:
        print(f"[ERRO send_start_request] {e}")

def send_stop_request():
    try:
        requests.get(f"{API_BASE}/scan/stop")
    except Exception as e:
        print(f"[ERRO send_stop_request] {e}")



# ---------- FUNÇÕES ASSÍNCRONAS ----------

async def fetch_json(url):
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as resp:
                return await resp.json()
    except Exception as e:
        print(f"[ERRO fetch_json] {e}")
        return []

# ---------- WIDGET EXPANSÍVEL ----------
class CollapsibleDeviceWidget(QWidget):
    def __init__(self, device_data):
        super().__init__()
        self.device_data = device_data
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        ip = device_data.get("ip", "N/A")
        fab = device_data.get("fabricante", "Desconhecido")
        self.header_btn = QPushButton(f"▶ IP: {ip} ({fab})")
        self.header_btn.setStyleSheet("""
            QPushButton {
                background-color: #333;
                color: #FFF;
                border: 1px solid #555;
                padding: 8px;
                text-align: left;
                font-weight: bold;
                font-size: 14px;
            }
            QPushButton:hover {
                background-color: #444;
            }
        """)
        self.header_btn.clicked.connect(self.toggle_content)

        self.content_widget = QWidget()
        content_layout = QVBoxLayout(self.content_widget)
        content_label = QLabel(self._format_content_text())
        content_label.setWordWrap(True)
        content_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        content_label.setStyleSheet(
            "padding:10px;border:1px solid #555;border-top:none;color:#FFF;background:#1E1E1E;"
        )
        content_layout.addWidget(content_label)
        self.content_widget.setVisible(False)

        layout.addWidget(self.header_btn)
        layout.addWidget(self.content_widget)

    def _format_content_text(self):
        d = self.device_data
        datas = d.get("data_hora", "").split("; ") if d.get("data_hora") else []
        status_list = d.get("status", "").split("; ") if d.get("status") else []
        status_text = "\n".join([f"  - {dt} | Status: {st}" for dt, st in zip(datas, status_list)])
        
        portas_formatadas = "Nenhum serviço detectado."
        try:
            portas = json.loads(d.get("portas_servicos", "[]"))
            if portas:
                portas_formatadas = "\n".join([f"  - {p.get('porta','?')}/{p.get('protocolo','?')} -> {p.get('nome','?')} {p.get('versao','')}" for p in portas])
        except: pass

        conteudo = (
            f"<b>MAC:</b> {d.get('mac','N/A')}<br>"
            f"<b>SO Detectado:</b> {d.get('so','Desconhecido')}<br>"
            f"<b>Status do Dispositivo:</b> {'Novo' if d.get('flag') else 'Conhecido'}<br><br>"
            f"<b>Histórico de Status:</b><br>{status_text.replace(chr(10), '<br>')}<br><br>"
            f"<b>Últimos Serviços Detectados:</b><br>{portas_formatadas.replace(chr(10), '<br>')}"
        )
        return conteudo

    def toggle_content(self):
        vis = self.content_widget.isVisible()
        self.content_widget.setVisible(not vis)
        ip = self.device_data.get("ip", "N/A")
        fab = self.device_data.get("fabricante", "Desconhecido")
        self.header_btn.setText(f"▼ IP: {ip} ({fab})" if not vis else f"▶ IP: {ip} ({fab})")

# ---------- TELAS ----------
class TelaPrincipal(QWidget):
    def __init__(self, stacked_widget):
        super().__init__()
        self.stacked_widget = stacked_widget
        self.titulo_label = QLabel("Kiri NetScanning", self)  # título fixo
        self.horario_label = QLabel("", self)  # label só para horário
        self.btn_descoberta = QPushButton("Descoberta de Rede", self)
        self.btn_historicos = QPushButton("Históricos de Rede", self)
        self.btn_descoberta.clicked.connect(lambda: stacked_widget.setCurrentIndex(1))
        self.btn_historicos.clicked.connect(lambda: stacked_widget.setCurrentIndex(2))
        self.update_widget_positions()

    def resizeEvent(self, event):
        self.update_widget_positions()
        super().resizeEvent(event)

    def update_widget_positions(self):
        w, h = self.width(), self.height()
        self.titulo_label.setGeometry(int(w*0.1), int(h*0.05), int(w*0.8), 30)
        self.horario_label.setGeometry(int(w*0.7), int(h*0.05), int(w*0.25), 30)
        btn_w, btn_h = int(w*0.4), int(h*0.1)
        pos_x = (w - btn_w)//2
        self.btn_descoberta.setGeometry(pos_x, int(h*0.4), btn_w, btn_h)
        self.btn_historicos.setGeometry(pos_x, int(h*0.55), btn_w, btn_h)

class TelaDescoberta(QWidget):
    def __init__(self, stacked_widget):
        super().__init__()
        self.stacked_widget = stacked_widget
        self.scan_task = None
        try:
            redes = requests.get(f"{API_BASE}/networks").json()
            if redes:
                net_info = redes[0]
                ip = net_info.get("ip", "Desconhecido")
                prefix = net_info.get("prefix", 24)  # pega a máscara real
                self.label = QLabel(f"Rede Atual: {ip}/{prefix}", self)
            else:
                self.label = QLabel("Rede Atual: Desconhecida", self)
        except Exception as e:
            self.label = QLabel(f"Erro ao buscar rede: {e}", self)
        self.label = QLabel(f"Rede Atual: {ip}/{prefix}", self)
        self.status_label = QLabel("", self)
        self.loading_label = QLabel(self)
        self.loading_movie = QMovie(":/qt-project.org/images/loading.gif")
        self.loading_label.setMovie(self.loading_movie)
        self.btn_principal = QPushButton("Voltar", self)
        self.btn_principal.clicked.connect(lambda: stacked_widget.setCurrentIndex(0))
        self.btn_iniciar = QPushButton("Iniciar Scan", self)
        self.btn_iniciar.clicked.connect(self.iniciar_scan)
        self.btn_parar = QPushButton("Parar Scan", self)
        self.btn_parar.clicked.connect(self.parar_scan)
        self.btn_parar.setEnabled(False)
        self.scroll_area = QScrollArea(self)
        self.scroll_area.setWidgetResizable(True)
        self.scroll_content = QWidget()
        self.scroll_layout = QVBoxLayout(self.scroll_content)
        self.scroll_area.setWidget(self.scroll_content)
        self.update_widget_positions()

    def resizeEvent(self, event):
        self.update_widget_positions()
        super().resizeEvent(event)

    def update_widget_positions(self):
        w, h = self.width(), self.height()
        self.label.setGeometry(int(w*0.1), int(h*0.05), int(w*0.8), 30)
        self.status_label.setGeometry(int(w*0.1), int(h*0.12), int(w*0.8), 30)
        self.loading_label.setGeometry(int((w-40)/2), int(h*0.11), 40, 40)
        self.btn_iniciar.setGeometry(int(w*0.1), int(h*0.2), int(w*0.35), 30)
        self.btn_parar.setGeometry(int(w*0.55), int(h*0.2), int(w*0.35), 30)
        self.scroll_area.setGeometry(int(w*0.1), int(h*0.3), int(w*0.8), int(h*0.55))
        self.btn_principal.setGeometry(int(w*0.3), int(h*0.88), int(w*0.4), 30)
    
    
    async def scan_loop(self):
        self.status_label.setText("Scan iniciado...")
        try:
            while True:
                data = await fetch_json(f"{API_BASE}/scan/discovered_devices")
                self.atualizar_lista_dispositivos(data)
                await asyncio.sleep(3)
        except asyncio.CancelledError:
            pass


    def iniciar_scan(self):
        if self.scan_task and not self.scan_task.done():
            return
        self.btn_iniciar.setEnabled(False)
        self.btn_parar.setEnabled(True)
        self.loading_movie.start()
        send_start_request()
        self.scan_task = asyncio.create_task(self.scan_loop())

    def parar_scan(self):
        send_stop_request()
        if self.scan_task:
            self.scan_task.cancel()
            self.scan_task = None
            self.loading_movie.stop()
            self.status_label.setText("Scan parado pelo usuário.")
            self.btn_iniciar.setEnabled(True)
            self.btn_parar.setEnabled(False)

    def atualizar_lista_dispositivos(self, hosts):
        # Cria dicionário de widgets existentes
        widgets_existentes = {w.device_data.get("ip"): w for i in range(self.scroll_layout.count())
                            if isinstance((w:=self.scroll_layout.itemAt(i).widget()), CollapsibleDeviceWidget)}

        for info in hosts:
            ip = info.get("ip")
            if ip in widgets_existentes:
                widget = widgets_existentes[ip]
                widget.device_data = info
                widget.content_widget.layout().itemAt(0).widget().setText(widget._format_content_text())
            else:
                widget = CollapsibleDeviceWidget(info)
                self.scroll_layout.addWidget(widget)

        self.status_label.setText(f"Scanners ativos | {len(hosts)} dispositivos encontrados")


class TelaHistoricos(QWidget):
    def __init__(self, stacked_widget):
        super().__init__()
        self.stacked_widget = stacked_widget
        self.label = QLabel("Histórico de Redes", self)
        self.resumo_label = QLabel("", self)
        self.resumo_label.setStyleSheet("font-size: 16px; font-weight: bold; color: #FFD700;")
        self.btn_principal = QPushButton("Voltar", self)
        self.btn_principal.clicked.connect(lambda: stacked_widget.setCurrentIndex(0))
        self.scroll_area = QScrollArea(self)
        self.scroll_area.setWidgetResizable(True)
        self.scroll_content = QWidget()
        self.scroll_layout = QVBoxLayout(self.scroll_content)
        self.scroll_area.setWidget(self.scroll_content)
        self.update_widget_positions()

    def resizeEvent(self, event):
        self.update_widget_positions()
        super().resizeEvent(event)

    def update_widget_positions(self):
        w, h = self.width(), self.height()
        self.label.setGeometry(int(w*0.1), int(h*0.05), int(w*0.8), int(h*0.05))
        self.resumo_label.setGeometry(int(w*0.1), int(h*0.12), int(w*0.8), 30)
        self.scroll_area.setGeometry(int(w*0.1), int(h*0.2), int(w*0.8), int(h*0.65))
        btn_w, btn_h = int(w*0.4), 35
        self.btn_principal.setGeometry(int((w-btn_w)/2), int(h*0.9), btn_w, btn_h)

    async def atualizar_historico_async(self):
        try:
            resp = await fetch_json(f"{API_BASE}/devices")
        except:
            resp = []

        redes = defaultdict(list)
        prefixos = {}  # para guardar o prefixo de cada rede

        for dev in resp:
            ip = dev.get("ip")
            prefix = dev.get("prefix", 24)  # pega o prefix real enviado pelo backend
            if ip:
                prefix_str = ".".join(ip.split(".")[:3])
                redes[prefix_str].append(dev)
                prefixos[prefix_str] = prefix

        total = sum(len(d) for d in redes.values())
        self.resumo_label.setText(f"Total de Dispositivos no Histórico: {total}")

        # Dicionário de widgets existentes
        widgets_existentes = {}
        for i in range(self.scroll_layout.count()):
            w = self.scroll_layout.itemAt(i).widget()
            if isinstance(w, CollapsibleDeviceWidget):
                ip = w.device_data.get("ip")
                widgets_existentes[ip] = w

        for rede, dispositivos in redes.items():
            rede_label = None
            # verifica se já existe label da rede
            for i in range(self.scroll_layout.count()):
                w = self.scroll_layout.itemAt(i).widget()
                if isinstance(w, QLabel) and w.text().startswith(f"Rede: {rede}"):
                    rede_label = w
                    break

            if not rede_label:
                mask = prefixos.get(rede, 24)  # pega o prefix real da rede
                rede_label = QLabel(f"Rede: {rede}.0/{mask}")
                rede_label.setStyleSheet(
                    "font-size:16px;font-weight:bold;color:#A0A0FF;"
                    "margin-top:10px;border-bottom:1px solid #555;padding-bottom:5px;"
                )
                self.scroll_layout.addWidget(rede_label)

            for dev in dispositivos:
                ip = dev.get("ip")
                if ip in widgets_existentes:
                    widget = widgets_existentes[ip]
                    widget.device_data = dev
                    widget.content_widget.layout().itemAt(0).widget().setText(widget._format_content_text())
                else:
                    widget = CollapsibleDeviceWidget(dev)
                    self.scroll_layout.addWidget(widget)



# ---------- APP PRINCIPAL ----------
class App(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Kiri NetScanning")
        self.setGeometry(100,100,800,600)
        self.stacked_widget = QStackedWidget(self)
        self.stacked_widget.addWidget(TelaPrincipal(self.stacked_widget))
        self.tela_descoberta = TelaDescoberta(self.stacked_widget)
        self.stacked_widget.addWidget(self.tela_descoberta)
        self.tela_historicos = TelaHistoricos(self.stacked_widget)
        self.stacked_widget.addWidget(self.tela_historicos)
        self.stacked_widget.setGeometry(0,0,self.width(),self.height())


async def atualizar_label_periodicamente(app_instance):
    while True:
        try:
            tela = app_instance.stacked_widget.currentWidget()
            # Atualiza apenas se a tela for a principal
            if isinstance(tela, TelaPrincipal):
                tela.horario_label.setText(datetime.now().strftime('%H:%M:%S'))
        except Exception as e:
            print(f"[Erro] atualizar_label_periodicamente: {e}")
        await asyncio.sleep(1)


async def atualizar_historico_periodico(app_instance):
    while True:
        try:
            await app_instance.tela_historicos.atualizar_historico_async()
        except Exception as e:
            print(f"[Erro] atualizar_historico_periodico: {e}")
        await asyncio.sleep(10)

async def main():
    janela = App()
    janela.show()
    asyncio.create_task(atualizar_label_periodicamente(janela))
    asyncio.create_task(atualizar_historico_periodico(janela))
    await asyncio.Event().wait()

if __name__=="__main__":
    app = QApplication(sys.argv)
    loop = QEventLoop(app)
    asyncio.set_event_loop(loop)
    with loop:
        loop.run_until_complete(main())
