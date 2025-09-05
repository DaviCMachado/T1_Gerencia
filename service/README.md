# Serviço de Gerência de Redes

Código do serviço que lida com a toda a lógica da gerência de redes
e os requisitos definidos em aula. Para integração, ver a [documentação
da api](./API.md) ou utilizar a [interface gráfica](../interface/README.md).

## Tecnologias

Foi utilizado Python junto com a biblioteca [FastAPI](https://fastapi.tiangolo.com/) para a construção do serviço.

## Como executar

Digite `uvicorn main:app` no terminal na pasta `service/` para iniciar o servidor.

## Endpoints

### Scan

* **GET** `/scan/start`: Inicia o processo de scanning na rede. Retorna um objeto no formato:
    ```json
    {
        "message": "Scan started",
        "status": "ok"
    }
    ```
    Se o status for diferente de `"ok"`, é necessário verificar o campo `"message"` para entender o erro.
* **GET** `/scan/stop`: Termina todos os scanners que estão executando. Retorna um objeto no formato:
    ```json
    {
        "message": "Scan stopped",
        "status": "ok"
    }
    ```
    Se o status for diferente de `"ok"`, é necessário verificar o campo `"message"` para entender o erro.

* **GET** `/scan/status`: Retorna quantos scanners ainda estão executando. Retorna um objeto no formato:
    ```json
    {
        "scanning": 4,
        "completed": 1,
        "stopped": 0
    }
    ```

### Redes

* **GET** `/networks/`: Retorna quais sao as interfaces de rede que estão registradas no serviço remoto. Retorna uma lista no formato:
    ```json
    [
        {
            "interface": "Ethernet",
            "ip": "192.168.0.0",
            "netmask": "255.255.255.0",
            "prefix": "24"
        },
        // ...
    ]
    ```

### Relatórios

## Sobre o DB

A coluna "flag" é utilizada para saber se um dispositivo é novo ou conhecido em uma rede,
a partir da seguinte lógica: 0 == conhecido, 1 == novo;

A coluna status nos diz se o dispostivo respondeu ao scanning naquele momento, 
então usamos: status == up | down;