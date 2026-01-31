FROM node:20-alpine

WORKDIR /app

# Copiar arquivos de dependências
COPY package*.json ./

# Instalar apenas dependências de produção (--omit=dev substitui o obsoleto --only=production).
# Usa npm install porque npm ci exige package-lock.json; para builds reproduzíveis, gere o lock e use: npm ci --omit=dev
RUN npm install --omit=dev

# Copiar código
COPY . .

# Usar o usuário não-root já presente na imagem node:alpine (evita conflito de UID/GID no Alpine)
RUN chown -R node:node /app

USER node

EXPOSE 8000

CMD ["node", "src/app.js"]
