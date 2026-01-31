# Guia de Implantação: Frontend (Vite + React) no aaPanel

Este guia descreve como realizar o deploy do frontend gerado pelo Lovable no aaPanel utilizando o servidor web Nginx.

## Pré-requisitos

1. aaPanel instalado e funcional.
2. Nginx instalado no aaPanel (App Store).
3. Node.js instalado no aaPanel (via Node.js Version Manager na App Store).

## Passo 1: Preparação do Código (Local)

Antes de enviar para o servidor, certifique-se de que o arquivo `.env` está configurado corretamente para produção.

1. No arquivo `frontend-lovable/.env`, ajuste a URL da API para o endereço de produção:
   ```env
   VITE_API_URL=https://sua-api-producao.com/api/v1
   VITE_MODE=production
   ```

2. Instale as dependências e gere a build de produção:
   ```bash
   npm install
   npm run build
   ```
   Isso criará uma pasta chamada `dist/` dentro de `frontend-lovable/`.

## Passo 2: Upload para o aaPanel

1. No painel do aaPanel, vá em **Files**.
2. Navegue até o diretório onde deseja hospedar o site (ex: `/www/wwwroot/seu-projeto-frontend`).
3. Faça o upload do conteúdo da pasta `dist/` (apenas o conteúdo interno da pasta) para este diretório.

## Passo 3: Configuração do Site no aaPanel

1. Vá em **Website** > **Add site**.
2. Preencha o domínio (ex: `monitor.seudominio.com`).
3. No campo **Root directory**, selecione a pasta onde você fez o upload (ex: `/www/wwwroot/seu-projeto-frontend`).
4. Em **FTP** e **Database**, selecione "No" (já que é um site estático).
5. Clique em **Submit**.

## Passo 4: Configuração do Nginx (SPA Routing)

Como esta é uma aplicação Single Page Application (SPA), o Nginx precisa redirecionar todas as rotas para o `index.html`.

1. Na lista de sites, clique no nome do domínio que você acabou de criar.
2. Vá em **Config**.
3. Localize a seção de configuração e adicione o seguinte bloco dentro do bloco `server { ... }` ou verifique se já existe um `location /`:

   ```nginx
   location / {
     try_files $uri $uri/ /index.html;
   }
   ```

4. Clique em **Save**.

## Passo 5: SSL (Opcional, mas Recomendado)

1. Ainda nas configurações do site, vá em **SSL**.
2. Selecione **Let's Encrypt**.
3. Selecione seu domínio e clique em **Apply**.
4. Ative o **Force HTTPS**.

## Passo 6: Verificação

Acesse o seu domínio no navegador. O frontend deve carregar e ser capaz de se comunicar com a API configurada no `VITE_API_URL`.

---

---

## Opção 2: Docker (Recomendado para Isolamento)

Se você prefere usar Docker, criamos um `Dockerfile` otimizado.

1.  **Construir a imagem:**
    ```bash
    docker build -t easysmart_frontend .
    ```

2.  **Rodar o container:**
    ```bash
    docker run -d -p 8081:80 --name easysmart_frontend easysmart_frontend
    ```
    Ou usando Docker Compose:
    ```bash
    docker compose up -d
    ```
    O frontend estará disponível em `http://seu-ip:8081`.

---

### Dicas de Troubleshooting

- **Erro 404 ao atualizar a página:** Verifique se o Passo 4 (SPA Routing) foi aplicado corretamente.
- **Erro de CORS:** Certifique-se de que o domínio do frontend está na lista de origens permitidas (Whitelist) do seu Backend.
- **Variáveis de Ambiente:** Lembre-se que no Vite, as variáveis `VITE_*` são injetadas no momento da build. Se você mudar o `.env`, precisará rodar `npm run build` novamente e fazer o upload dos arquivos.
