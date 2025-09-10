import sys
from pathlib import Path
import json
import threading
from collections import defaultdict
from PySide6.QtWidgets import (
    QApplication, QWidget, QPushButton, QLabel, QStackedWidget,
    QVBoxLayout, QScrollArea
)
from PySide6.QtCore import QSize, QTimer, Qt
from PySide6.QtGui import QMovie
import requests
from PySide6.QtCore import QThread, Signal

# Adiciona a raiz do projeto ao sys.path
sys.path.append(str(Path(__file__).parent.parent))

API_BASE = "http://localhost:80"  # ou IP do servidor


# --- Classe para rodar o scan em uma thread separada ---
class ThreadScan(QThread):
    progresso = Signal(str)
    parcial = Signal(list)      # MUDANÇA: Novo sinal para resultados parciais
    finalizado = Signal(list)
    terminado = Signal()

    def __init__(self):
        super().__init__()
        self._cancelado = False

    def run(self):
        import time
        try:
            requests.get(f"{API_BASE}/scan/start", timeout=5)
        except Exception as e:
            self.progresso.emit(f"Erro ao iniciar scan: {e}")
            self.terminado.emit()
            return

        loop_counter = 0
        while not self._cancelado:
            try:
                # 1. Verifica o status geral do scan
                status_response = requests.get(f"{API_BASE}/scan/status", timeout=5)
                status = status_response.json()
                scanning = status.get("scanning", 0)
                self.progresso.emit(f"Scanners ativos: {scanning}")

                # 2. MUDANÇA: A cada 2 loops (~5-6 segundos), busca os dispositivos encontrados
                loop_counter += 1
                if loop_counter >= 2:
                    try:
                        devices_response = requests.get(f"{API_BASE}/scan/discovered_devices", timeout=5)
                        partial_devices = devices_response.json()
                        self.parcial.emit(partial_devices) # Emite o sinal com a lista parcial
                    except Exception as e:
                        print(f"[AVISO] Não foi possível obter a lista parcial de dispositivos: {e}")
                    loop_counter = 0 # Reinicia o contador

                if scanning == 0:
                    break
                
            except Exception as e:
                print(f"[AVISO] Falha no loop de status: {e}")
            
            time.sleep(3) # Aumentei um pouco o sleep

        # Pega a lista final COMPLETA do banco (com status 'down', etc.)
        if not self._cancelado:
            try:
                final_devices = requests.get(f"{API_BASE}/devices", timeout=10).json()
                self.finalizado.emit(final_devices)
            except Exception as e:
                self.progresso.emit(f"Erro ao buscar dispositivos finais: {e}")

        self.terminado.emit()

    def cancelar(self):
        self._cancelado = True
        threading.Thread(target=self._stop_scan_http, daemon=True).start()

    def _stop_scan_http(self):
        try:
            requests.get(f"{API_BASE}/scan/stop", timeout=5)
        except Exception:
            pass


# --- 1. Definindo as "telas" da aplicação ---

class TelaPrincipal(QWidget):
    def __init__(self, stacked_widget):
        super().__init__()
        self.stacked_widget = stacked_widget
        self.label = QLabel("Kiri NetScanning", self)
        self.btn_descoberta = QPushButton("Descoberta de Rede", self)
        self.btn_historicos = QPushButton("Históricos de Rede", self)
        
        self.btn_descoberta.clicked.connect(self.ir_para_descoberta)
        self.btn_historicos.clicked.connect(self.ir_para_historicos)

        # Atualiza a posição inicial dos widgets
        self.update_widget_positions()

    def resizeEvent(self, event):
        self.update_widget_positions()
        super().resizeEvent(event)

    def update_widget_positions(self):
        largura_tela = self.width()
        altura_tela = self.height()

        # Posicionamento e dimensionamento do rótulo
        self.label.setStyleSheet("font-size: 20px; font-weight: bold;")
        self.label.setGeometry(int(largura_tela * 0.1), int(altura_tela * 0.1), 
                               int(largura_tela * 0.8), int(altura_tela * 0.1))

        # Posicionamento e dimensionamento dos botões
        largura_btn = int(largura_tela * 0.4)
        altura_btn = int(altura_tela * 0.1)
        pos_x_btn = int((largura_tela - largura_btn) / 2)
        
        pos_y_btn_descoberta = int(altura_tela * 0.4)
        pos_y_btn_historicos = int(altura_tela * 0.55)
        
        self.btn_descoberta.setGeometry(pos_x_btn, pos_y_btn_descoberta, 
                                        largura_btn, altura_btn)
        self.btn_historicos.setGeometry(pos_x_btn, pos_y_btn_historicos, 
                                       largura_btn, altura_btn)

    def ir_para_descoberta(self):
        # Índice 1 no QStackedWidget
        self.stacked_widget.setCurrentIndex(1)

    def ir_para_historicos(self):
        # Índice 2 no QStackedWidget
        self.stacked_widget.setCurrentIndex(2)

class TelaDescoberta(QWidget):
    def __init__(self, stacked_widget):
        super().__init__()
        self.stacked_widget = stacked_widget
        # MUDANÇA: Inicializa a thread como None para sabermos se há um scan ativo
        self.scan_thread = None 

        # Pega a rede atual
        try:
            redes = requests.get(f"{API_BASE}/networks").json()
            ip = redes[0]['ip'] if redes else "Desconhecido"
        except Exception:
            ip = "Erro ao buscar rede"
        self.label = QLabel(f"Rede Atual: {ip}", self)
        self.label.setStyleSheet("font-size: 18px; font-weight: bold;")
        self.status_label = QLabel("", self)
        self.status_label.setStyleSheet("font-size: 14px;")
        self.loading_label = QLabel(self)
        self.loading_movie = QMovie(":/qt-project.org/images/loading.gif")
        self.loading_label.setMovie(self.loading_movie)
        self.btn_principal = QPushButton("Voltar", self)
        self.btn_principal.clicked.connect(self.voltar_para_principal)
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

    def iniciar_scan(self):
        # MUDANÇA 1: Verificação de segurança
        # Não permite iniciar um novo scan se um objeto de thread (mesmo que parando) ainda existir.
        if self.scan_thread is not None:
            print("[AVISO] Tentativa de iniciar um scan enquanto outro está finalizando. Aguarde.")
            return

        self.btn_iniciar.setEnabled(False)
        self.btn_parar.setEnabled(True)
        self.loading_movie.start()
        self.status_label.setText("Iniciando scan...")

        self.scan_thread = ThreadScan()
        self.scan_thread.progresso.connect(self.atualizar_status)
        self.scan_thread.parcial.connect(self.atualizar_lista_dispositivos)
        self.scan_thread.finalizado.connect(self.atualizar_lista_dispositivos)
        self.scan_thread.terminado.connect(self.scan_terminado)
        self.scan_thread.start()

    def parar_scan(self):
        if self.scan_thread and self.scan_thread.isRunning():
            self.status_label.setText("Cancelando scan...")
            
            # MUDANÇA 2: Bloqueia ambos os botões para criar um estado "finalizando"
            self.btn_iniciar.setEnabled(False)
            self.btn_parar.setEnabled(False)
            
            self.scan_thread.cancelar()

    def scan_terminado(self):
        self.loading_movie.stop()
        self.btn_iniciar.setEnabled(True) # O botão Iniciar só é reativado AQUI
        self.btn_parar.setEnabled(False)
        
        # Esta linha é a mais importante: ela libera o caminho para um novo scan
        self.scan_thread = None
        
        if "Cancelando" in self.status_label.text():
            self.status_label.setText("Scan parado pelo usuário.")
        elif "encontrados" not in self.status_label.text():
             self.status_label.setText("Scan finalizado.")

    def voltar_para_principal(self):
        if self.scan_thread and self.scan_thread.isRunning():
            self.parar_scan()
        self.stacked_widget.setCurrentIndex(0)

    def atualizar_status(self, mensagem):
        self.status_label.setText(mensagem)

    def atualizar_lista_dispositivos(self, hosts):
        for i in reversed(range(self.scroll_layout.count())):
            self.scroll_layout.itemAt(i).widget().setParent(None)
        for info in hosts:
            texto = (
                f"IP: {info.get('ip', 'N/A')}\n"
                f"MAC: {info.get('mac', 'N/A')}\n"
                f"Fabricante: {info.get('fabricante', 'N/A')}\n"
                f"SO: {info.get('so', 'N/A')}"
            )
            texto += "\nStatus: Online"
            label = QLabel(texto)
            label.setStyleSheet("font-size: 14px; padding: 5px; border: 1px solid #555; color: #FFF; background: #101010;")
            label.setWordWrap(True)
            self.scroll_layout.addWidget(label)
        if "Scanners ativos" in self.status_label.text():
            self.status_label.setText(self.status_label.text().split(" | ")[0] + f" | {len(hosts)} dispositivos encontrados")

    def resizeEvent(self, event):
        self.update_widget_positions()
        super().resizeEvent(event)

    def update_widget_positions(self):
        largura_tela = self.width()
        altura_tela = self.height()
        self.label.setGeometry(int(largura_tela*0.1), int(altura_tela*0.05), int(largura_tela*0.8), 30)
        self.status_label.setGeometry(int(largura_tela*0.1), int(altura_tela*0.12), int(largura_tela*0.8), 30)
        loading_x = (largura_tela - 40) / 2
        self.loading_label.setGeometry(int(loading_x), int(altura_tela*0.11), 40, 40)
        self.btn_iniciar.setGeometry(int(largura_tela*0.1), int(altura_tela*0.2), int(largura_tela*0.35), 30)
        self.btn_parar.setGeometry(int(largura_tela*0.55), int(altura_tela*0.2), int(largura_tela*0.35), 30)
        self.scroll_area.setGeometry(int(largura_tela*0.1), int(altura_tela*0.3), int(largura_tela*0.8), int(altura_tela*0.55))
        self.btn_principal.setGeometry(int(largura_tela*0.3), int(altura_tela*0.88), int(largura_tela*0.4), 30)



class CollapsibleDeviceWidget(QWidget):
    """
    Um widget que contém um botão de cabeçalho e uma área de conteúdo que pode ser expandida/recolhida.
    """
    def __init__(self, device_data):
        super().__init__()
        self.device_data = device_data

        # Layout principal do widget
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # 1. Cabeçalho (Botão Clicável)
        ip = self.device_data.get('ip', 'N/A')
        fabricante = self.device_data.get('fabricante', 'Desconhecido')
        self.header_btn = QPushButton(f"▶ IP: {ip} ({fabricante})")
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

        # 2. Área de Conteúdo (Inicialmente Oculta)
        self.content_widget = QWidget()
        content_layout = QVBoxLayout(self.content_widget)
        
        content_label = QLabel(self._format_content_text())
        content_label.setStyleSheet("padding: 10px; border: 1px solid #555; border-top: none; color: #FFF; background: #1E1E1E;")
        content_label.setWordWrap(True)
        content_label.setTextInteractionFlags(Qt.TextSelectableByMouse) # Permite copiar o texto
        content_layout.addWidget(content_label)
        self.content_widget.setVisible(False)

        # Adiciona os widgets ao layout principal
        layout.addWidget(self.header_btn)
        layout.addWidget(self.content_widget)

    def _format_content_text(self):
        """Formata o texto detalhado do dispositivo a partir do dicionário de dados."""
        d = self.device_data
        
        # O DB_Manager agora retorna os dados ordenados, então podemos confiar na ordem
        datas = d.get('data_hora', '').split('; ') if d.get('data_hora') else []
        status_list = d.get('status', '').split('; ') if d.get('status') else []
        
        status_por_data = []
        for data, status in zip(datas, status_list):
            status_por_data.append(f"  - {data} | Status: {status}")

        status_formatado = "\n".join(status_por_data)

        portas_formatadas = "Nenhum serviço detectado."
        try:
            portas_str = d.get('portas_servicos')
            if portas_str:
                portas = json.loads(portas_str)
                if portas:
                    portas_formatadas = ""
                    for p in portas:
                        portas_formatadas += f"  - {p.get('porta','?')}/{p.get('protocolo','?')} -> {p.get('nome','?')} {p.get('versao','')}\n"
        except (json.JSONDecodeError, TypeError):
            portas_formatadas = "Erro ao ler dados de serviços."

        # Usando formatação HTML simples para negrito
        conteudo = (
            f"<b>MAC:</b> {d.get('mac', 'N/A')}<br>"
            f"<b>SO Detectado:</b> {d.get('so', 'Desconhecido')}<br>"
            f"<b>Status do Dispositivo:</b> {'Novo' if d.get('flag') else 'Conhecido'}<br><br>"
            f"<b>Histórico de Status:</b><br>{status_formatado.replace(chr(10), '<br>')}<br><br>"
            f"<b>Últimos Serviços Detectados:</b><br>{portas_formatadas.replace(chr(10), '<br>')}"
        )
        return conteudo

    def toggle_content(self):
        """Alterna a visibilidade da área de conteúdo e atualiza o ícone do botão."""
        is_visible = self.content_widget.isVisible()
        self.content_widget.setVisible(not is_visible)
        
        ip = self.device_data.get('ip', 'N/A')
        fabricante = self.device_data.get('fabricante', 'Desconhecido')
        if is_visible:
            self.header_btn.setText(f"▶ IP: {ip} ({fabricante})")
        else:
            self.header_btn.setText(f"▼ IP: {ip} ({fabricante})")

# --- TELA HISTÓRICOS ---
class TelaHistoricos(QWidget):
    def __init__(self, stacked_widget):
        super().__init__()
        self.stacked_widget = stacked_widget
        
        self.label = QLabel("Histórico de Redes", self)
        self.resumo_label = QLabel("", self)
        self.resumo_label.setStyleSheet("font-size: 16px; font-weight: bold; color: #FFD700;")
        
        self.btn_principal = QPushButton("Voltar", self)
        self.btn_principal.clicked.connect(self.voltar_para_principal)

        self.scroll_area = QScrollArea(self)
        self.scroll_area.setWidgetResizable(True)
        self.scroll_content = QWidget(self.scroll_area)
        self.scroll_layout = QVBoxLayout(self.scroll_content)
        self.scroll_layout.setSpacing(5) # Espaçamento entre os widgets dos dispositivos
        self.scroll_layout.setAlignment(Qt.AlignTop) # Alinha os itens no topo
        self.scroll_area.setWidget(self.scroll_content)

        self.update_widget_positions()

    def showEvent(self, event):
        """Chamado toda vez que a tela é exibida para garantir dados atualizados."""
        self.atualizar_historico()
        super().showEvent(event)

    def atualizar_historico(self):
        """Recarrega os dados do banco e popula a tela com widgets expansíveis."""
        # 1. Limpa widgets antigos da tela
        for i in reversed(range(self.scroll_layout.count())):
            widget_to_remove = self.scroll_layout.itemAt(i).widget()
            if widget_to_remove:
                widget_to_remove.setParent(None)

        # 2. Busca dados atualizados da API
        redes_historicas = self.carregar_historico()
        
        total_dispositivos = sum(len(dispositivos) for dispositivos in redes_historicas.values())
        if not redes_historicas or total_dispositivos == 0:
            self.resumo_label.setText("Nenhum histórico de dispositivos encontrado.")
            label_vazio = QLabel("Nenhum histórico disponível.", self)
            label_vazio.setStyleSheet("font-size: 16px; padding: 10px; color: #FFF;")
            label_vazio.setAlignment(Qt.AlignCenter)
            self.scroll_layout.addWidget(label_vazio)
        else:
            self.resumo_label.setText(f"Total de Dispositivos no Histórico: {total_dispositivos}")
            
            # 3. Cria os widgets expansíveis para cada dispositivo
            for rede, dispositivos in redes_historicas.items():
                # Adiciona um label para separar as redes
                rede_label = QLabel(f"Rede: {rede}.0/24")
                rede_label.setStyleSheet("font-size: 16px; font-weight: bold; color: #A0A0FF; margin-top: 10px; border-bottom: 1px solid #555; padding-bottom: 5px;")
                self.scroll_layout.addWidget(rede_label)

                # Adiciona um widget expansível para cada dispositivo na rede
                for device_data in dispositivos:
                    device_widget = CollapsibleDeviceWidget(device_data)
                    self.scroll_layout.addWidget(device_widget)

    def carregar_historico(self):
        """Retorna um dicionário {rede: [dispositivos]} obtido da API."""
        try:
            # Usando a variável API_BASE definida no topo do seu arquivo
            resp = requests.get(f"{API_BASE}/devices", timeout=10).json()
        except (requests.exceptions.RequestException, json.JSONDecodeError) as e:
            print(f"[ERRO] TelaHistoricos: Não foi possível carregar o histórico: {e}")
            self.resumo_label.setText("Erro ao carregar histórico.")
            return {} # Retorna um dicionário vazio em caso de erro

        redes = defaultdict(list)
        if not isinstance(resp, list):
            return {}

        for dev in resp:
            ip = dev.get("ip")
            if not ip:
                continue
            prefixo = ".".join(ip.split(".")[:3])
            redes[prefixo].append(dev)
        return redes
        
    def voltar_para_principal(self):
        self.stacked_widget.setCurrentIndex(0)
    
    def resizeEvent(self, event):
        self.update_widget_positions()
        super().resizeEvent(event)

    def update_widget_positions(self):
        largura_tela = self.width()
        altura_tela = self.height()
        
        self.label.setStyleSheet("font-size: 20px; font-weight: bold;")
        self.label.setGeometry(int(largura_tela * 0.1), int(altura_tela * 0.05), 
                             int(largura_tela * 0.8), int(altura_tela * 0.05))

        self.resumo_label.setGeometry(int(largura_tela * 0.1), int(altura_tela * 0.12),
                                      int(largura_tela * 0.8), 30)

        self.scroll_area.setGeometry(int(largura_tela * 0.1), int(altura_tela * 0.2),
                                     int(largura_tela * 0.8), int(altura_tela * 0.65))
        
        largura_btn = int(largura_tela * 0.4)
        altura_btn = 35
        pos_x_btn_principal = int((largura_tela - largura_btn) / 2)
        pos_y_btn_principal = int(altura_tela * 0.9)
        self.btn_principal.setGeometry(pos_x_btn_principal, pos_y_btn_principal, 
                                     largura_btn, altura_btn)



# --- 2. Classe principal da Aplicação ---

class App(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Kiri NetScanning")
        # Define o tamanho inicial da janela
        self.setGeometry(100, 100, 800, 600)

        # Carrega o arquivo CSS
        self.load_stylesheet("styles.css")

        # Cria o QStackedWidget que vai gerenciar as telas
        self.stacked_widget = QStackedWidget(self)
        
        # Adiciona as telas ao QStackedWidget. A ordem aqui define o índice!
        self.stacked_widget.addWidget(TelaPrincipal(self.stacked_widget))
        self.stacked_widget.addWidget(TelaDescoberta(self.stacked_widget))   
        self.stacked_widget.addWidget(TelaHistoricos(self.stacked_widget))    
        
        # Chama a função para posicionar e redimensionar os widgets
        # de acordo com o tamanho inicial da janela
        self.update_widget_geometry()

    def load_stylesheet(self, filename):
        """Carrega o estilo de um arquivo CSS."""
        try:
            # Constrói o caminho absoluto para o arquivo CSS
            base_path = Path(__file__).parent
            filepath = base_path / filename
            with open(filepath, "r") as f:
                self.setStyleSheet(f.read())
        except FileNotFoundError:
            print(f"Erro: O arquivo de estilo '{filename}' não foi encontrado.")

    def resizeEvent(self, event):
        """
        Este método é chamado automaticamente quando a janela é redimensionada.
        """
        self.update_widget_geometry()
        super().resizeEvent(event)

    def update_widget_geometry(self):
        """
        Calcula e aplica a geometria do QStackedWidget com base em porcentagens.
        """
        # Pega a largura e altura atuais da janela
        largura_janela = self.width()
        altura_janela = self.height()
        
        # Define as porcentagens de largura e altura para o widget
        largura_percent = 0.8  # 80% da largura da janela
        altura_percent = 0.8   # 80% da altura da janela

        # Calcula a largura e altura do widget em pixels
        nova_largura = int(largura_janela * largura_percent)
        nova_altura = int(altura_janela * altura_percent)
        
        # Calcula a posição centralizada do widget
        pos_x = int((largura_janela - nova_largura) / 2)
        pos_y = int((altura_janela - nova_altura) / 2)
        
        # Aplica a nova geometria ao QStackedWidget
        self.stacked_widget.setGeometry(pos_x, pos_y, nova_largura, nova_altura)
        

if __name__ == "__main__":
    app = QApplication(sys.argv)
    janela = App()
    janela.show()
    sys.exit(app.exec())
