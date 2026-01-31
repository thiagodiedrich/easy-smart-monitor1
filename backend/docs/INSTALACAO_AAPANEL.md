# Instalação do Backend Easy Smart Monitor via aaPanel

Este guia descreve como instalar e rodar o backend da API (Gateway Node.js, Workers Python, Kafka, TimescaleDB, Redis, MinIO) usando a **interface gráfica do aaPanel** e, quando necessário, o terminal integrado.

---

## Pré-requisitos

- Servidor com **aaPanel** já instalado (Linux recomendado).
- Acesso à interface web do aaPanel (porta 7800 ou 8888).
- Mínimo recomendado: **2 GB RAM**, **2 vCPUs**, **20 GB disco** (para todos os serviços em Docker).

---

## Passo 1: Instalar o Docker no aaPanel

1. Acesse o **aaPanel** no navegador (ex.: `http://SEU_IP:7800`).
2. No menu lateral, vá em **App Store** (ou **Aplicativos**).
3. Procure por **Docker** e clique em **Instalar**.
4. Aguarde a instalação. Depois, no menu lateral deve aparecer o módulo **Docker**.

Se o Docker não aparecer na App Store, instale manualmente pelo **Terminal** do aaPanel (ou SSH):

```bash
curl -fsSL https://get.docker.com | sh
sudo systemctl enable docker && sudo systemctl start docker
```

---

## Passo 2: Colocar o projeto do backend no servidor

O backend precisa estar em uma pasta no servidor para o `docker-compose` conseguir usar `build` (Gateway e Workers têm Dockerfile).

### Opção A: Upload pelo gerenciador de arquivos do aaPanel

1. No aaPanel, vá em **Files** (Arquivos).
2. Crie uma pasta para o projeto, por exemplo: `/www/wwwroot/easysmart-backend`.
3. Envie (upload) o conteúdo da pasta **backend** do seu projeto:
   - Toda a estrutura: `gateway/`, `workers-python/`, `docker-compose.yml`, `.env.example`, etc.
   - Ou compacte a pasta `backend` no seu PC em `.zip` e use **Upload** + **Unzip** no aaPanel.

### Opção B: Clonar com Git (se o projeto estiver em um repositório)

1. No aaPanel, abra **Terminal** (ou use SSH).
2. Exemplo:

```bash
sudo mkdir -p /www/wwwroot/easysmart-backend
cd /www/wwwroot/easysmart-backend
sudo git clone URL_DO_SEU_REPOSITORIO .
# Se o backend estiver numa subpasta do repositório:
# sudo git clone URL_DO_REPOSITORIO repo && sudo mv repo/backend/* . && sudo rm -rf repo
```

Use o caminho que você definiu (ex.: `/www/wwwroot/easysmart-backend`) nos passos seguintes.

---

## Passo 3: Criar o arquivo `.env`

1. Em **Files**, entre na pasta do backend (ex.: `/www/wwwroot/easysmart-backend`).
2. Localize o arquivo **`.env.example`**.
3. Copie o conteúdo e crie um novo arquivo chamado **`.env`** na mesma pasta (ou renomeie/copie `.env.example` para `.env`).
4. Edite o **`.env`** e ajuste pelo menos:
   - **SECRET_KEY**: use uma chave forte e aleatória com pelo menos 32 caracteres (produção).
   - **POSTGRES_PASSWORD**: senha do banco (ex.: `easysmart_password`).
   - **MINIO_ROOT_USER** e **MINIO_ROOT_PASSWORD**: se quiser outros que não `minioadmin`/`minioadmin`.

Salve o arquivo.

---

## Passo 4: Subir os containers com Docker Compose

O `docker-compose.yml` usa **build** (imagens construídas a partir dos Dockerfiles). Por isso é preciso rodar o Compose **dentro da pasta do backend** no servidor. Isso pode ser feito pelo **Terminal** do aaPanel (ou por SSH).

1. No aaPanel, vá em **Terminal** (ou **Advanced** → **Terminal**).
2. Execute (troque o caminho se tiver usado outro):

```bash
cd /www/wwwroot/easysmart-backend
docker compose up -d --build
```

Ou, se a sua versão usar hífen:

```bash
docker-compose up -d --build
```

3. Aguarde o build das imagens e a subida de todos os serviços (Gateway, Worker, Kafka, Zookeeper, Postgres, Redis, MinIO).
4. Para ver os logs:

```bash
docker compose logs -f
```

Para parar:

```bash
cd /www/wwwroot/easysmart-backend
docker compose down
```

---

## Passo 5: Liberar portas no firewall (aaPanel)

1. No aaPanel, vá em **Security** (Segurança) ou **Firewall**.
2. Libere as portas necessárias para acesso externo (se precisar):
   - **8000** – API (Gateway) – **obrigatório** se for acessar a API de fora.
   - 9000 – MinIO API (opcional).
   - 9001 – MinIO Console (opcional).
   - 5432, 6379, 9092 – em geral **não** é necessário liberar se só o backend usar (acesso local).

Salve as regras.

---

## Passo 6: Rodar as migrações do banco (primeira vez)

Na primeira instalação, crie as tabelas e a estrutura no TimescaleDB:

1. **Terminal** do aaPanel (ou SSH):

```bash
cd /www/wwwroot/easysmart-backend
docker compose run --rm worker python run_migrations.py
```

Use **`run --rm`** (e não `exec`): isso cria um container temporário, roda as migrações e remove o container. Funciona mesmo se o serviço `worker` estiver reiniciando ou parado.

---

## Passo 7: Expor a API por domínio (proxy reverso) – opcional

Para acessar a API por um domínio (ex.: `api.seudominio.com`) com HTTPS:

1. No aaPanel, vá em **Website** (Site).
2. **Add site** (Adicionar site).
3. Domínio: ex. `api.seudominio.com` (ou o que você usar).
4. Após criar o site, clique no nome do site → **Settings** → **Proxy** (ou **Reverse Proxy**).
5. Adicione um proxy:
   - **Proxy name**: ex. `easysmart-api`
   - **Target URL**: `http://127.0.0.1:8000`
   - **Send Domain**: normalmente `$host` ou o próprio domínio.
6. Salve. Se tiver SSL no aaPanel, ative **SSL** para esse site (Let’s Encrypt, etc.).

A API ficará acessível em `https://api.seudominio.com` (ex.: `https://api.seudominio.com/api/v1/health`).

---

## Resumo do que fica disponível

| Serviço        | Porta (host) | Uso                          |
|----------------|--------------|------------------------------|
| API (Gateway)  | 8000         | Endpoints REST, Swagger, auth |
| MinIO API      | 9000         | Storage (Claim Check)        |
| MinIO Console  | 9001         | Interface web MinIO          |
| PostgreSQL     | 5432         | Banco (TimescaleDB)          |
| Redis          | 6379         | Cache, rate limit, locks      |
| Kafka          | 9092         | Fila de telemetria           |

---

## Gerenciando pelo aaPanel depois de subir

- **Docker** → **Container**: você verá os containers do `docker-compose` (gateway, worker, kafka, postgres, redis, minio, zookeeper). Pode iniciar/parar/reiniciar por aqui.
- **Docker** → **Compose**: o aaPanel pode listar projetos Compose. Se o projeto foi criado “à mão” pelo terminal, ele pode aparecer como projeto sem nome; para rebuild/restart, usar o terminal na pasta do backend com `docker compose up -d --build` ou `docker compose restart` continua sendo o mais direto quando há `build`.

---

## Problemas comuns

1. **“Cannot connect to Docker daemon”**  
   - Docker não está instalado ou não está rodando. Reinstale pelo App Store ou use `sudo systemctl start docker`.

2. **Porta 8000 já em uso**  
   - Altere no `docker-compose.yml` a linha `"8000:8000"` para outra, ex.: `"8002:8000"`, e use a nova porta no proxy ou no firewall.

3. **Migrações ou health check falham**  
   - Confirme que o `.env` está na pasta do backend e que `POSTGRES_PASSWORD` (e `DATABASE_URL` se usar) estão corretos. Verifique logs: `docker compose logs postgres` e `docker compose logs worker`.

4. **API 502 ao usar proxy**  
   - Verifique se o Gateway está rodando: `docker compose ps`. Confirme se o proxy do site aponta para `http://127.0.0.1:8000` (ou a porta mapeada do gateway).

Seguindo esses passos, o backend fica instalado e gerenciável pela interface do aaPanel, com a parte de build/Compose feita pelo terminal na pasta do projeto.
