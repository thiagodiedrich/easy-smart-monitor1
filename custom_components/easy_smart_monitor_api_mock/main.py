from fastapi import FastAPI, HTTPException, Depends, Header, Request
from pydantic import BaseModel
from typing import List, Optional, Union
import uvicorn
import time
from datetime import datetime, timedelta
from jose import jwt, JWTError

app = FastAPI(title="Easy Smart Monitor Mock Server")

# --- CONFIGURAÇÕES ---
SECRET_KEY = "segredo_super_secreto_do_mock"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 2 # Expira rápido para você testar o refresh
REFRESH_TOKEN_EXPIRE_DAYS = 7

# Credenciais Aceitas
VALID_USER = "admin"
VALID_PASS = "123456"

# --- MODELOS DE DADOS ---
class LoginRequest(BaseModel):
    username: str
    password: str

class TelemetryItem(BaseModel):
    equip_uuid: str
    sensor_uuid: str
    tipo: str
    valor: Optional[Union[float, int, str]] = None
    status: Optional[str] = None
    timestamp: str

# --- FUNÇÕES AUXILIARES ---
def create_token(data: dict, expires_delta: timedelta):
    to_encode = data.copy()
    expire = datetime.utcnow() + expires_delta
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

def verify_token(token: str):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except JWTError:
        raise HTTPException(status_code=401, detail="Token inválido ou expirado")

# --- ENDPOINTS ---

@app.get("/")
def home():
    return {"status": "online", "msg": "Easy Smart Monitor Mock API está rodando!"}

@app.post("/auth/login")
def login(data: LoginRequest):
    print(f"-> Tentativa de Login: {data.username} / {data.password}")
    
    if data.username == VALID_USER and data.password == VALID_PASS:
        # Gera tokens
        access_token = create_token({"sub": data.username}, timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES))
        refresh_token = create_token({"sub": data.username, "type": "refresh"}, timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS))
        
        return {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "token_type": "bearer",
            "expires_in": ACCESS_TOKEN_EXPIRE_MINUTES * 60
        }
    
    raise HTTPException(status_code=401, detail="Credenciais inválidas")

@app.post("/auth/refresh")
def refresh_token_endpoint(authorization: str = Header(None)):
    """
    Espera receber o Refresh Token no Header: 'Authorization: Bearer <refresh_token>'
    """
    if not authorization:
        raise HTTPException(status_code=401, detail="Header Authorization ausente")

    token = authorization.replace("Bearer ", "")
    payload = verify_token(token) # Se falhar aqui, retorna 401

    if payload.get("type") != "refresh":
        raise HTTPException(status_code=401, detail="Token não é do tipo refresh")

    print(f"-> Refresh Token validado para: {payload.get('sub')}. Gerando novo Access Token...")

    # Gera novo access token
    new_access_token = create_token({"sub": payload.get("sub")}, timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES))
    
    return {
        "access_token": new_access_token,
        "token_type": "bearer",
        "expires_in": ACCESS_TOKEN_EXPIRE_MINUTES * 60
    }

@app.post("/api/telemetry")
def receive_telemetry(payload: List[TelemetryItem], authorization: str = Header(None)):
    """
    Recebe o lote de dados da fila. Valida o token de acesso.
    """
    if not authorization:
        raise HTTPException(status_code=401, detail="Não autorizado")
    
    # Valida Access Token
    token = authorization.replace("Bearer ", "")
    try:
        verify_token(token)
    except HTTPException:
        print("-> ERRO: Token de acesso expirado recebido na telemetria!")
        raise # Retorna 401 para forçar a integração a usar o refresh

    # Se chegou aqui, o token é válido
    print(f"\n[RECEBIDO] Pacote com {len(payload)} itens:")
    for item in payload:
        val = item.valor if item.valor is not None else item.status
        print(f"   - {item.timestamp} | {item.tipo}: {val} (Equip: ...{item.equip_uuid[-6:]})")

    return {"status": "success", "received": len(payload)}

# Para rodar localmente se precisar
if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)