const express = require('express');
const jwt = require('jsonwebtoken');
const bodyParser = require('body-parser');
const cors = require('cors');

const app = express();
const PORT = 3000;

// --- CONFIGURAÇÕES ---
const SECRET_KEY = "segredo_super_secreto_node";
const ACCESS_TOKEN_EXPIRE = '2m'; // 2 minutos (teste de refresh)
const REFRESH_TOKEN_EXPIRE = '7d';

// Credenciais Aceitas
const VALID_USER = "admin";
const VALID_PASS = "123456";

// Middlewares
app.use(cors());
app.use(bodyParser.json());

// --- FUNÇÃO DE DATA/HORA (Pt-BR) ---
const getNow = () => {
    // Retorna string formatada: "14/01/2026 15:30:45"
    return new Date().toLocaleString('pt-BR');
};

// --- MIDDLEWARE DE LOG GERAL ---
// Isso aqui vai rodar para QUALQUER requisição que chegar
app.use((req, res, next) => {
    console.log(`\n[${getNow()}] 📡 RECEBIDO: ${req.method} ${req.originalUrl}`);
    next(); // Passa para a próxima rota
});

// --- FUNÇÕES AUXILIARES ---
const generateTokens = (username) => {
    // expiresIn no jwt.sign aceita string ('2m')
    const accessToken = jwt.sign({ sub: username, type: 'access' }, SECRET_KEY, { expiresIn: ACCESS_TOKEN_EXPIRE });
    const refreshToken = jwt.sign({ sub: username, type: 'refresh' }, SECRET_KEY, { expiresIn: REFRESH_TOKEN_EXPIRE });
    
    // Calcula segundos para informar no JSON de resposta (120s)
    const expiresIn = 120; 

    return { accessToken, refreshToken, expiresIn };
};

// --- ROTAS DA API ---

// 1. Rota de Saúde
app.get('/', (req, res) => {
    res.json({ status: "online", msg: "Easy Smart Mock (Node.js) está rodando!" });
    console.log(`Servidor Mock rodando online, acessou /`);
});

// 2. Login
app.post('/auth/login', (req, res) => {
    const { username, password } = req.body;

    console.log(`-> Tentativa de Login: ${username} / ${password}`);

    if (username === VALID_USER && password === VALID_PASS) {
        const tokens = generateTokens(username);
        
        return res.json({
            access_token: tokens.accessToken,
            refresh_token: tokens.refreshToken,
            token_type: "bearer",
            expires_in: tokens.expiresIn
        });
    }

    return res.status(401).json({ detail: "Credenciais inválidas" });
});

// 3. Refresh Token
app.post('/auth/refresh', (req, res) => {
    const authHeader = req.headers['authorization'];
    const token = authHeader && authHeader.split(' ')[1]; // Remove "Bearer "

    if (!token) return res.status(401).json({ detail: "Token ausente" });

    jwt.verify(token, SECRET_KEY, (err, user) => {
        if (err) {
            console.log("-> Erro no Refresh: Token inválido ou expirado");
            return res.status(401).json({ detail: "Token inválido" });
        }

        if (user.type !== 'refresh') {
            return res.status(401).json({ detail: "Token não é do tipo refresh" });
        }

        console.log(`-> Refresh validado para: ${user.sub}. Gerando novo Access Token...`);
        
        const newAccessToken = jwt.sign(
            { sub: user.sub, type: 'access' }, 
            SECRET_KEY, 
            { expiresIn: ACCESS_TOKEN_EXPIRE }
        );

        return res.json({
            access_token: newAccessToken,
            token_type: "bearer",
            expires_in: 120
        });
    });
});

// 4. Receber Telemetria
app.post('/api/telemetria/bulk', (req, res) => {
    const authHeader = req.headers['authorization'];
    const token = authHeader && authHeader.split(' ')[1];

    if (!token) return res.status(401).json({ detail: "Não autorizado" });

    jwt.verify(token, SECRET_KEY, (err, user) => {
        if (err) {
            console.log("-> ALERTA: Token de acesso expirado recebido na telemetria! O HA deve tentar refresh agora.");
            return res.status(401).json({ detail: "Token expirado" });
        }

        const payload = req.body;
        console.log(`\n[RECEBIDO] Pacote com ${payload.length} itens:`);
        
        if (Array.isArray(payload)) {
            payload.forEach(item => {
                const val = item.valor !== undefined ? item.valor : item.status;
                const equipShort = item.equip_uuid ? `...${item.equip_uuid.slice(-6)}` : 'N/A';
                console.log(`   - ${item.timestamp} | ${item.tipo}: ${val} (Equip: ${equipShort})`);
            });
        
        // --- AQUI ESTÁ A MUDANÇA PARA VER O JSON INTEIRO ---
        console.log("---------------------------------------------------");
        
        console.log(`\n[RECEBIDO] Pacote com ${payload.length} itens. Estrutura Completa:`);
        
        // JSON.stringify(objeto, replacer, indentação)
        console.log(JSON.stringify(payload, null, 2)); 
        
        console.log("---------------------------------------------------");
        } else {
            console.log("   Payload não é uma lista:", payload);
        }

        return res.json({ status: "success", received: payload.length });
    });
});

// --- ROTA 404 (CATCH-ALL) ---
// Adicionado aqui, APÓS todas as rotas definidas, mas ANTES do app.listen
app.use((req, res) => {
    console.log(`\n[404] ALERTA: Tentativa de acesso em rota inexistente!`);
    console.log(`      Método: ${req.method}`);
    console.log(`      URL:    ${req.originalUrl}`);
    
    res.status(404).json({ 
        error: "Not Found", 
        message: "Esta rota não existe no Mock Server",
        path: req.originalUrl 
    });
});

// --- INICIAR SERVIDOR ---
app.listen(PORT, () => {
    console.log(`Servidor Mock rodando em http://localhost:${PORT}`);
});