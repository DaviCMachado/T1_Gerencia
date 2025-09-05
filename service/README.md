# Serviço de Gerência de Redes

Código do serviço que lida com a toda a lógica da gerência de redes
e os requisitos definidos em aula. Para integração, ver a [documentação
da api](./API.md) ou utilizar a [interface gráfica](../interface/README.md).

## Tecnologias

Foi utilizado Python junto com a biblioteca [FastAPI](https://fastapi.tiangolo.com/) para a construção do serviço.

## Como executar

Digite `fastapi dev main.py` no terminal na pasta `service/` para iniciar o servidor.


## Sobre o DB

A coluna "flag" é utilizada para saber se um dispositivo é novo ou conhecido em uma rede,
a partir da seguinte lógica: 0 == conhecido, 1 == novo;

A coluna status nos diz se o dispostivo respondeu ao scanning naquele momento, 
então usamos: status == up | down;