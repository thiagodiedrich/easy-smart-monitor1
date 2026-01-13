🧊 Easy Smart Monitor v1.0.11
Integração avançada para monitoramento industrial de freezers e geladeiras no Home Assistant. Desenvolvida para garantir que nenhum dado de telemetria seja perdido, mesmo em condições de instabilidade de rede.

✨ Funcionalidades Principais
Persistência Atômica (Fila Offline): Sistema de fila em disco que armazena os dados localmente caso o servidor API esteja offline, enviando tudo em lote (bulk) assim que a conexão é restaurada.

Controle Total por Equipamento: Cada dispositivo possui controles individuais de ativação e parâmetros de segurança.

Gestão de Sirene Inteligente: Alerta sonoro/visual baseado no tempo de abertura da porta, com timer configurável via interface.

Diagnóstico em Tempo Real: Sensores dedicados para monitorar a saúde da conexão com a API e o tamanho da fila de espera.

🛠️ Controles do Dispositivo (v1.0.11)
A partir da versão 1.0.11, cada equipamento monitorado apresenta quatro controles principais na aba de configurações:

Equipamento Ativo (Switch): Ativa ou interrompe globalmente a coleta e o envio de dados para este freezer específico.

Intervalo de Coleta (Number): Define o tempo mínimo (em segundos) entre as leituras dos sensores para evitar sobrecarga de dados.

Sirene Ativa (Switch): Habilita ou desabilita o disparo do alarme de "Problema" para a porta aberta.

Tempo Porta Aberta (Number): Define quantos segundos a porta pode permanecer aberta antes que a Sirene mude para o estado de alerta.

🚀 Instalação
Manual
Baixe o repositório.

Copie a pasta easy_smart_monitor1 para dentro do diretório custom_components do seu Home Assistant.

Reinicie o Home Assistant.

Vá em Configurações > Dispositivos e Serviços > Adicionar Integração e procure por "Easy Smart Monitor".

⚙️ Configuração
Durante o fluxo de configuração, você será guiado para:

Inserir o Host da API e suas credenciais de acesso.

Cadastrar seus equipamentos (Freezers/Geladeiras).

Vincular as entidades existentes no seu HA (sensores de temperatura, sensores de porta Zigbee/ESP32, etc.) aos tipos de grandeza da integração.

📊 Arquitetura de Dados
A integração utiliza o padrão Coordinator do Home Assistant para gerenciar as atualizações de estado e o Async Client para comunicações não bloqueantes.

Snippet de código

graph TD
    A[Sensores HA] --> B{Filtro de Intervalo}
    B -->|Ativo| C[Fila Local .json]
    C --> D{Conexão API}
    D -->|Sucesso| E[Limpar Fila]
    D -->|Falha| F[Manter no Disco]
📝 Especificações Técnicas
Domínio: easy_smart_monitor1

Requisitos: aiohttp (utiliza a versão do Core)

Dependências: http

Persistência: Armazenada em /config/.storage/easy_smart_monitor1_queue.json

👤 Autor
Thiago Diedrich - @thiagodiedrich