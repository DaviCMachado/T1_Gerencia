import sys
from pathlib import Path

from PySide6.QtWidgets import (
    QApplication, QWidget, QPushButton, QLabel, QStackedWidget,
    QVBoxLayout, QScrollArea
)
from PySide6.QtCore import QSize, QTimer, Qt
from PySide6.QtGui import QMovie

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
        self.label = QLabel("Descoberta na Rede X.X.X.X", self)
        self.status_label = QLabel("Escaneando...", self)
        
        # Adiciona o QLabel para o círculo girando
        self.loading_label = QLabel(self)
        self.loading_movie = QMovie(":/qt-project.org/images/loading.gif")
        self.loading_label.setMovie(self.loading_movie)
        
        self.btn_principal = QPushButton("Voltar", self)
        self.btn_principal.clicked.connect(self.voltar_para_principal)

        # Simula o escaneamento por 5 segundos
        self.timer = QTimer(self)
        self.timer.setSingleShot(True)
        self.timer.timeout.connect(self.scanning_finished)

        self.update_widget_positions()
        self.start_scanning()

    def start_scanning(self):
        self.loading_movie.start()
        self.status_label.setText("Escaneando...")
        self.btn_principal.setEnabled(False)
        self.timer.start(5000)  # 5 segundos

    def scanning_finished(self):
        self.loading_movie.stop()
        self.status_label.setText("Escaneamento Concluído!")
        self.btn_principal.setEnabled(True)
        # TODO: Adicionar aqui a lógica para mostrar os resultados

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

        # Posicionamento e dimensionamento do status_label
        largura_status = int(largura_tela * 0.8)
        altura_status = int(altura_tela * 0.1)
        self.status_label.setGeometry(int(largura_tela * 0.1), int(altura_tela * 0.3),
                                     largura_status, altura_status)

        # Posicionamento e dimensionamento do círculo girando
        largura_loading = int(largura_tela * 0.1)
        altura_loading = int(altura_tela * 0.1)
        pos_x_loading = int((largura_tela - largura_loading) / 2)
        pos_y_loading = int(altura_tela * 0.45)
        self.loading_label.setGeometry(pos_x_loading, pos_y_loading, largura_loading, altura_loading)

        # Posicionamento e dimensionamento do Botão Principal
        largura_btn = int(largura_tela * 0.4)
        altura_btn = int(altura_tela * 0.1)
        pos_x_btn_principal = int((largura_tela - largura_btn) / 2)
        pos_y_btn_principal = int(altura_tela * 0.7)
        self.btn_principal.setGeometry(pos_x_btn_principal, pos_y_btn_principal, 
                                       largura_btn, altura_btn)

    def voltar_para_principal(self):
        self.stacked_widget.setCurrentIndex(0)

class TelaHistoricos(QWidget):
    def __init__(self, stacked_widget):
        super().__init__()
        self.stacked_widget = stacked_widget
        self.label = QLabel("Histórico de Redes", self)
        self.btn_principal = QPushButton("Voltar", self)
        self.btn_principal.clicked.connect(self.voltar_para_principal)

        # Cria uma área de rolagem para os históricos
        self.scroll_area = QScrollArea(self)
        self.scroll_area.setWidgetResizable(True)
        self.scroll_content = QWidget(self.scroll_area)
        self.scroll_layout = QVBoxLayout(self.scroll_content)
        self.scroll_area.setWidget(self.scroll_content)

        # Exemplo de redes para o histórico
        redes_historicas = ["Rede-192.168.1.0", "CLARO_5G985GF4", "Rede-172.16.0.0", 
                            "Rede-8.8.8.8", "eduroam", "Rede-52.0.0.1", "Rede-1.1.1.1"]

        # Cria os botões de expansão para cada rede
        for i, rede in enumerate(redes_historicas):
            self.add_historico_item(rede, f"Histórico detalhado da {rede}")

        self.update_widget_positions()

    def add_historico_item(self, nome_rede, conteudo_historico):
        btn = QPushButton(f"▼ {nome_rede}")
        btn.setStyleSheet("text-align: left; padding: 10px; font-size: 16px;")
        
        content = QLabel(conteudo_historico)
        content.setStyleSheet("padding: 10px; border: 2px solid #ccc; background-color: #f033f0;")
        content.hide() # Esconde o conteúdo por padrão
        
        def toggle_content():
            if content.isHidden():
                content.show()
                btn.setText(f"▲ {nome_rede}")
            else:
                content.hide()
                btn.setText(f"▼ {nome_rede}")

        btn.clicked.connect(toggle_content)
        self.scroll_layout.addWidget(btn)
        self.scroll_layout.addWidget(content)

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

        # Posicionamento da área de rolagem
        self.scroll_area.setGeometry(int(largura_tela * 0.1), int(altura_tela * 0.25),
                                     int(largura_tela * 0.8), int(altura_tela * 0.5))
        
        # Posicionamento e dimensionamento do Botão Principal
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
        self.setWindowTitle("Navegação de Telas Responsiva")
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
