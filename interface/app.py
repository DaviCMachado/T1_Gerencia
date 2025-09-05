import sys
from pathlib import Path
import json

from PySide6.QtWidgets import (
    QApplication, QWidget, QPushButton, QLabel, QStackedWidget,
    QVBoxLayout, QScrollArea
)
from PySide6.QtCore import QSize, QTimer, Qt
from PySide6.QtGui import QMovie
import sqlite3

DB_FILE = Path(__file__).parent.parent / "service/historico_redes.db"

from PySide6.QtCore import QThread, Signal

# Adiciona a raiz do projeto ao sys.path
sys.path.append(str(Path(__file__).parent.parent))
from service.scan import Scanner  # aqui você importa a classe que criamos


# --- Classe para rodar o scan em uma thread separada ---
class ThreadScan(QThread):
    # Sinal para enviar atualizações para a GUI
    progresso = Signal(str)
    finalizado = Signal(dict)

    def __init__(self, scan_detalhado=False):
        super().__init__()
        self.scan_detalhado = scan_detalhado
        self.scanner = Scanner()  # instância do scanner

    def run(self):
        faixa_ip = self.scanner.obter_faixa_ip_local()
        self.progresso.emit(f"Iniciando scan na faixa {faixa_ip}...")
        hosts = self.scanner.descobrir_hosts_na_rede(faixa_ip, scan_detalhado=self.scan_detalhado)
        self.finalizado.emit(hosts)


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
        faixa_ip = Scanner.obter_faixa_ip_local(self)
        self.label = QLabel(f"Rede Atual: {faixa_ip}", self)
        # self.label = QLabel(f"Sua Rede: {faixa_ip}", self)
        self.label.setStyleSheet("font-size: 18px; font-weight: bold;")

        # self.status_label = QLabel("Aguardando...", self)
        self.status_label = QLabel("", self)
        self.status_label.setStyleSheet("font-size: 14px;")
        
        self.loading_label = QLabel(self)
        self.loading_movie = QMovie(":/qt-project.org/images/loading.gif")
        self.loading_label.setMovie(self.loading_movie)
        
        self.btn_principal = QPushButton("Voltar", self)
        self.btn_principal.clicked.connect(self.voltar_para_principal)

        # Botões para escolher tipo de scan
        self.btn_scan_rapido = QPushButton("Scan Rápido", self)
        self.btn_scan_detalhado = QPushButton("Scan Detalhado", self)
        self.btn_scan_rapido.clicked.connect(lambda: self.iniciar_scan(False))
        self.btn_scan_detalhado.clicked.connect(lambda: self.iniciar_scan(True))

        # ScrollArea para resultados
        self.scroll_area = QScrollArea(self)
        self.scroll_area.setWidgetResizable(True)
        self.scroll_content = QWidget()
        self.scroll_layout = QVBoxLayout(self.scroll_content)
        self.scroll_area.setWidget(self.scroll_content)

        self.update_widget_positions()

    def iniciar_scan(self, detalhado):
        self.loading_movie.start()
        self.status_label.setText("Escaneando...")
        self.btn_principal.setEnabled(False)
        self.btn_scan_rapido.setEnabled(False)
        self.btn_scan_detalhado.setEnabled(False)

        # Limpa resultados antigos
        for i in reversed(range(self.scroll_layout.count())):
            self.scroll_layout.itemAt(i).widget().setParent(None)

        # Cria e inicia a thread
        self.thread = ThreadScan(scan_detalhado=detalhado)
        self.thread.progresso.connect(self.atualizar_status)
        self.thread.finalizado.connect(self.scan_concluido)
        self.thread.start()

    def atualizar_status(self, mensagem):
        self.status_label.setText(mensagem)

    def scan_concluido(self, hosts):
        self.loading_movie.stop()
        self.status_label.setText(f"Scan Concluído! {len(hosts)} hosts encontrados.")
        self.btn_principal.setEnabled(True)
        self.btn_scan_rapido.setEnabled(True)
        self.btn_scan_detalhado.setEnabled(True)

        for host, info in hosts.items():
            texto = f"IP: {info['ip']}\nMAC: {info['mac_address']}\nFabricante: {info['fabricante']}\nSO: {info['so']}\nStatus: {info['status']}\n"
            if info['servicos']:
                texto += "Portas/Serviços:\n"
                for s in info['servicos']:
                    texto += f"  - {s['porta']}/{s['protocolo']} -> {s['nome']} {s.get('versao','')}\n"
            label = QLabel(texto)
            label.setStyleSheet("font-size: 14px; padding: 5px; border: 1px solid #555; color: #FFF; background: #101010;")
            label.setWordWrap(True)
            self.scroll_layout.addWidget(label)

    def resizeEvent(self, event):
        self.update_widget_positions()
        super().resizeEvent(event)

    def update_widget_positions(self):
        largura_tela = self.width()
        altura_tela = self.height()
        
        self.label.setGeometry(int(largura_tela*0.1), int(altura_tela*0.05), int(largura_tela*0.8), 30)
        self.status_label.setGeometry(int(largura_tela*0.1), int(altura_tela*0.12), int(largura_tela*0.8), 30)

        self.loading_label.setGeometry(int(largura_tela*0.45), int(altura_tela*0.18), 40, 40)

        self.btn_scan_rapido.setGeometry(int(largura_tela*0.1), int(altura_tela*0.2), int(largura_tela*0.35), 30)
        self.btn_scan_detalhado.setGeometry(int(largura_tela*0.55), int(altura_tela*0.2), int(largura_tela*0.35), 30)

        self.scroll_area.setGeometry(int(largura_tela*0.1), int(altura_tela*0.3), int(largura_tela*0.8), int(altura_tela*0.55))

        self.btn_principal.setGeometry(int(largura_tela*0.3), int(altura_tela*0.88), int(largura_tela*0.4), 30)

    def voltar_para_principal(self):
        self.stacked_widget.setCurrentIndex(0)

class TelaHistoricos(QWidget):
    def __init__(self, stacked_widget):
        super().__init__()
        self.stacked_widget = stacked_widget
        
        # Label principal
        self.label = QLabel("Histórico de Redes", self)
        
        # Label resumo
        self.resumo_label = QLabel("", self)
        self.resumo_label.setStyleSheet("font-size: 16px; font-weight: bold; color: #FFD700;")
        
        self.btn_principal = QPushButton("Voltar", self)
        self.btn_principal.clicked.connect(self.voltar_para_principal)

        # Cria área de rolagem
        self.scroll_area = QScrollArea(self)
        self.scroll_area.setWidgetResizable(True)
        self.scroll_content = QWidget(self.scroll_area)
        self.scroll_layout = QVBoxLayout(self.scroll_content)
        self.scroll_area.setWidget(self.scroll_content)

        # Carrega histórico
        self.redes_historicas = self.carregar_historico_do_db()
        
        # Atualiza label resumo
        total_dispositivos = sum(len(d) for d in self.redes_historicas.values())
        if total_dispositivos == 0:
            self.resumo_label.setText("Nenhum histórico de dispositivos encontrado.")
        else:
            self.resumo_label.setText(f"Dispositivos Escaneados: {total_dispositivos}")

        # Cria os itens para cada rede
        for rede, dispositivos in self.redes_historicas.items():
            self.add_historico_item(rede, dispositivos)

        self.update_widget_positions()

    def showEvent(self, event):
        """Chamado toda vez que a tela é exibida"""
        self.atualizar_historico()
        super().showEvent(event)

    def atualizar_historico(self):
        """Recarrega os dados do banco e atualiza a tela"""
        # Limpa widgets antigos
        for i in reversed(range(self.scroll_layout.count())):
            widget = self.scroll_layout.itemAt(i).widget()
            if widget:
                widget.setParent(None)

        # Busca dados atualizados do banco
        self.redes_historicas = self.carregar_historico_do_db()

        if not self.redes_historicas:
            # Nenhum histórico encontrado
            label = QLabel("Nenhum histórico disponível.", self)
            label.setStyleSheet("font-size: 16px; padding: 10px; color: #FFF;")
            label.setAlignment(Qt.AlignCenter)
            self.scroll_layout.addWidget(label)
        else:
            # Cria os itens para cada rede
            for rede, dispositivos in self.redes_historicas.items():
                self.add_historico_item(rede, dispositivos)

    def carregar_historico_do_db(self):
        """Retorna um dicionário {rede: [dispositivos]}"""
        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()
        c.execute("SELECT ip, mac, fabricante, so, status, portas_servicos, data_hora, flag FROM dispositivos")
        rows = c.fetchall()
        conn.close()

        redes = {}
        for ip, mac, fabricante, so, status, portas_servicos, data_hora, flag in rows:
            rede = ".".join(ip.split(".")[:3]) + ".0/24"
            if rede not in redes:
                redes[rede] = []
            redes[rede].append({
                "ip": ip,
                "mac": mac,
                "fabricante": fabricante,
                "so": so,
                "status": status,
                "portas_servicos": portas_servicos,
                "data_hora": data_hora,
                "flag": flag
            })
        return redes

    def add_historico_item(self, nome_rede, dispositivos):
        for d in dispositivos:
            # separa datas e status
            datas = d['data_hora'].split('; ')
            status_list = d['status'].split('; ')

            # assegura que listas têm o mesmo tamanho
            if len(status_list) < len(datas):
                status_list += ['Desconhecido'] * (len(datas) - len(status_list))
            elif len(status_list) > len(datas):
                datas += ['Desconhecido'] * (len(status_list) - len(datas))

            status_por_data = [f"{datas[i]} | Status: {status_list[i]}" for i in range(len(datas))]

            # portas/serviços com intervalo de detecção
            try:
                portas = json.loads(d['portas_servicos'])
            except:
                portas = []

            portas_formatadas = ""
            for p in portas:
                data_inicio = p.get('data_inicio', datas[0])
                data_fim = p.get('data_fim', datas[-1])
                portas_formatadas += f"  - {p['porta']}/{p['protocolo']} -> {p['nome']} {p.get('versao','')} [{data_inicio} → {data_fim}]\n"

            conteudo = (
                f"IP: {d['ip']}\n"
                f"MAC: {d['mac']}\n"
                f"Fabricante: {d['fabricante']}\n"
                f"SO: {d['so']}\n"
                f"Flag: {'Novo' if d['flag'] else 'Conhecido'}\n"
                f"Datas/Horários com Status:\n" + "\n".join(status_por_data) + "\n"
                f"Portas/Serviços:\n{portas_formatadas}\n"
                "-----------------------------\n"
            )

            label = QLabel(conteudo)
            label.setStyleSheet("padding: 5px; border: 1px solid #555; color: #FFF; background: #101010;")
            label.setWordWrap(True)
            self.scroll_layout.addWidget(label)

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
                                    int(largura_tela * 0.8), int(altura_tela * 0.55))
        
        largura_btn = int(largura_tela * 0.4)
        altura_btn = int(altura_tela * 0.1)
        pos_x_btn_principal = int((largura_tela - largura_btn) / 2)
        pos_y_btn_principal = int(altura_tela * 0.8)
        self.btn_principal.setGeometry(pos_x_btn_principal, pos_y_btn_principal, 
                                    largura_btn, altura_btn)


    def voltar_para_principal(self):
        self.stacked_widget.setCurrentIndex(0)



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
    if not Path("../service/historico_redes.db").exists():
        # Se o banco de dados não existir, cria um novo
        Scanner().criar_banco()

    janela = App()
    janela.show()
    sys.exit(app.exec())
