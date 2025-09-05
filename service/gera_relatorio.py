import sqlite3
from pathlib import Path
from datetime import datetime
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from reportlab.platypus import HRFlowable
from reportlab.lib.enums import TA_CENTER


DB_FILE = Path(__file__).parent / "historico_redes.db"
PDF_FILE = Path(__file__).parent.parent / "reports/relatorio_rede.pdf"

def gerar_relatorio_pdf():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("SELECT ip, mac, fabricante, so, status, portas_servicos, data_hora, flag FROM dispositivos")
    rows = c.fetchall()
    conn.close()

    doc = SimpleDocTemplate(str(PDF_FILE), pagesize=A4)
    styles = getSampleStyleSheet()

    # Cria estilos customizados
    estilo_titulo_categoria = ParagraphStyle(
        'TituloCategoria',
        parent=styles['Normal'],
        fontSize=12,
        leading=14,
        spaceAfter=4,
        spaceBefore=8,
        # textColor='darkblue',
        textColor='black',
        fontName='Helvetica-Bold',  # negrito
        bold=True
    )

    # Cria estilo para o subtítulo
    estilo_subtitulo = ParagraphStyle(
        'SubTitulo',
        parent=styles['Normal'],
        fontSize=12,  
        leading=16,
        alignment=TA_CENTER,  # centraliza
        spaceAfter=10,
        spaceBefore=4,
        # fontName='Helvetica-Bold',
        textColor='black'
    )

    estilo_normal = styles['Normal']

    elementos = []

    # Depois do título
    agora = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    elementos.append(Paragraph(f"<b>Relatório de Rede - {agora}</b>", styles['Title']))
    elementos.append(Spacer(1, 12))

    num_dispositivos = len(rows)
    redes_unicas = set(".".join(ip.split(".")[:3]) for ip, *_ in rows)
    num_redes = len(redes_unicas)

    # Subtítulo centralizado
    elementos.append(Paragraph(f"Redes escaneadas: {num_redes} | Dispositivos detectados: {num_dispositivos}", estilo_subtitulo))
    elementos.append(Spacer(1, 20))

    if not rows:
        elementos.append(Paragraph("Nenhum dispositivo registrado no histórico.", estilo_normal))
    else:
       for row in rows:
            ip, mac, fabricante, so, status, portas_servicos, datas, flag = row
            flag_texto = "Novo" if flag else "Conhecido"

            # Formata datas/horários
            datas_lista = datas.split("; ")
            datas_formatadas = "<br/>".join([f"{d.strip()} | Status: {status}" for d in datas_lista])

            # Formata portas/serviços
            try:
                portas = eval(portas_servicos)  # transforma string JSON em lista
                portas_formatadas = ""
                for p in portas:
                    portas_formatadas += f"Porta {p['porta']}/{p['protocolo']} -> {p['nome']} {p.get('versao','')}<br/>"
            except:
                portas_formatadas = portas_servicos

            # Monta parágrafo com espaçamento entre categorias
            elementos.append(Paragraph(f"IP: {ip}", estilo_titulo_categoria))
            elementos.append(Paragraph(f"MAC: {mac}", estilo_normal))
            elementos.append(Paragraph(f"Fabricante: {fabricante}", estilo_normal))
            elementos.append(Paragraph(f"SO: {so}", estilo_normal))
            elementos.append(Spacer(1, 6))

            elementos.append(Paragraph(f"Flag: {flag_texto}", estilo_titulo_categoria))
            elementos.append(Spacer(1, 6))

            elementos.append(Paragraph("Datas/Horários:", estilo_titulo_categoria))
            elementos.append(Paragraph(datas_formatadas, estilo_normal))
            elementos.append(Spacer(1, 6))

            elementos.append(Paragraph("Portas/Serviços:", estilo_titulo_categoria))
            elementos.append(Paragraph(portas_formatadas, estilo_normal))
            elementos.append(Spacer(1, 12))

            # Adiciona linha horizontal separadora entre dispositivos
            elementos.append(HRFlowable(width="100%", thickness=1, color="grey"))
            elementos.append(Spacer(1, 12))  # espaço após a linha

    doc.build(elementos)
    print(f"Relatório gerado em: {PDF_FILE}")

if __name__ == "__main__":
    gerar_relatorio_pdf()
