# Build Stage
FROM node:20-alpine AS build
WORKDIR /app

# Argumentos de build para injetar no Vite durante a compilação
ARG VITE_API_URL
ARG VITE_PORT
ARG VITE_HOST
ARG VITE_ENABLE_CAPTCHA
ARG VITE_MODE

ENV VITE_API_URL=$VITE_API_URL
ENV VITE_PORT=$VITE_PORT
ENV VITE_HOST=$VITE_HOST
ENV VITE_ENABLE_CAPTCHA=$VITE_ENABLE_CAPTCHA
ENV VITE_MODE=$VITE_MODE

# Instala dependências
COPY package*.json ./
RUN npm install

# Copia código e gera build
COPY . .
RUN npm run build

# Production Stage (Padrão Node.js similar ao backend)
FROM node:20-alpine
WORKDIR /app

# Instala o 'serve' para servir os arquivos estáticos de forma estável
RUN npm install -g serve

# Copia apenas a pasta dist gerada
COPY --from=build /app/dist ./dist

# Expõe a porta interna do container
EXPOSE 80

# Comando para rodar o servidor
# -s: Single Page Application mode (redireciona rotas para index.html)
# -l 80: Escuta na porta 80
CMD ["serve", "-s", "dist", "-l", "80"]
