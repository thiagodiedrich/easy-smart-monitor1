# 🧊 Easy Smart Monitor v1.0.14

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-orange.svg)](https://github.com/hacs/integration)
[![version](https://img.shields.io/badge/version-1.0.14-green.svg)](https://github.com/thiagodiedrich/easy_smart_monitor)
[![maintainer](https://img.shields.io/badge/maintainer-@thiagodiedrich-blue.svg)](https://github.com/thiagodiedrich)

**Integração profissional para monitoramento industrial de freezers, geladeiras e câmaras frias no Home Assistant.**

Desenvolvida com foco em **integridade de dados**, esta integração garante que nenhuma leitura crítica de temperatura ou energia seja perdida, mesmo em condições de instabilidade de rede.

## ✨ Funcionalidades Principais

* **🛡️ Persistência de Fila (Offline Queue):**
    * Se a API cair, os dados são salvos imediatamente no disco local do Home Assistant.
    * Recuperação automática assim que a conexão retorna.
* **⚡ Gerenciamento Dinâmico de Equipamentos:**
    * Adicione e remova equipamentos (Freezers/Câmaras) diretamente pelo menu de opções, sem precisar reinstalar a integração.
    * **Novo (v1.0.13):** Remoção limpa de dispositivos. Ao excluir um equipamento, ele e todas as suas entidades somem do Home Assistant instantaneamente.
* **⚙️ Controles de Hardware Nativos:**
    * Switches para ativar/desativar equipamentos individualmente.
    * Controle de sirene integrado com lógica local.
* **📊 Diagnósticos em Tempo Real:**
    * Sensores dedicados para monitorar a saúde da conexão e tamanho da fila.

---

## 🛠️ Painel de Controle e Automação

Cada equipamento adicionado ao Easy Smart Monitor gera automaticamente um dispositivo com 4 controles vitais:

1.  **Switch Equipamento Ativo:**
    * **ON:** Coleta e envia dados normalmente.
    * **OFF:** Pausa a coleta imediatamente (útil para manutenção ou degelo).
2.  **Switch Sirene Ativa:**
    * Habilita ou desabilita a lógica de disparo de alarme sonoro para este equipamento.
3.  **Number Intervalo de Coleta (120s Padrão):**
    * Define a frequência de envio de dados. Padrão ajustado para evitar sobrecarga de banco de dados.
4.  **Number Tempo Porta Aberta (120s Padrão):**
    * Define o tempo limite para a porta ficar aberta antes de disparar o alarme.

---

## 🚀 Instalação

### Pré-requisitos
* Home Assistant Core 2024.1 ou superior.
* Acesso à pasta `custom_components`.

### Passo a Passo
1.  Baixe o código fonte da versão mais recente (v1.0.14).
2.  Copie a pasta **`easy_smart_monitor`** para dentro do diretório `/config/custom_components/` do seu Home Assistant.
3.  **Reinicie o Home Assistant**.
4.  Vá em **Configurações > Dispositivos e Serviços > Adicionar Integração**.
5.  Pesquise por **"Easy Smart Monitor"**.
6.  Siga o fluxo de configuração visual.

---

## ⚙️ Gerenciamento (Menu de Opções)

Para adicionar novos freezers ou remover sensores, clique em **Configurar** no card da integração:

1.  **Gerenciar Equipamentos:**
    * Adicionar Novo: Cria um novo dispositivo.
    * Remover: Exclui o dispositivo e limpa o registro do Home Assistant.
2.  **Gerenciar Sensores:**
    * Vincule sensores existentes do HA (Zigbee, Tuya, ESPHome) ao equipamento.
3.  **Intervalo de Sincronia (API):**
    * Ajuste a frequência com que o pacote de dados acumulados é enviado ao servidor.

---

## 📝 Changelog

### v1.0.14 (Estável)
* [x] **Internacionalização (i18n):** Suporte total a traduções (PT-BR / EN-US).
* [x] **Sensores Físicos:** Suporte a botões de reset físico e sirenes de hardware.
* [x] **Lógica de Segurança:** Alerta de porta aberta agora dispara apenas em sirenes físicas e pode ser resetado via botão.
* [x] **UX:** Melhoria visual no fluxo de configuração com seletores de tipos traduzidos.

### v1.0.13
* [x] **Fix de Persistência:** Resolvido problema onde equipamentos sumiam após reiniciar o HA.
* [x] **Limpeza de Registro:** Ao remover um equipamento ou sensor, ele agora é deletado fisicamente do `device_registry` e `entity_registry`.
* [x] **Fluxo Atômico:** Criação de equipamento e sensores num passo unificado para evitar recarregamentos desnecessários.

### v1.0.12
* [x] Estabilização do Config Flow com seletores visuais.
* [x] Renomeação do domínio para `easy_smart_monitor`.
* [x] Ajuste de intervalos padrão (120s) para performance.

---

## 👤 Autor

* **Desenvolvedor:** Thiago Diedrich ([@thiagodiedrich](https://github.com/thiagodiedrich))
* **Licença:** MIT

---
*Easy Smart Monitor - Inteligência Industrial ao seu alcance.*