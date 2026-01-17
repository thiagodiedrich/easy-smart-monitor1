FROM node:20-alpine

WORKDIR /app

# Copiar arquivos de dependências
COPY package*.json ./

# Instalar dependências
RUN npm ci --only=production

# Copiar código
COPY . .

# Criar usuário não-root
RUN addgroup -g 1000 nodeuser && \
    adduser -D -u 1000 -G nodeuser nodeuser && \
    chown -R nodeuser:nodeuser /app

USER nodeuser

EXPOSE 8000

CMD ["node", "src/app.js"]
