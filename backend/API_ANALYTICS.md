# API Analytics - Endpoints Otimizados v1.0.0

## 🎯 Objetivo

Endpoints centralizados para consultas analíticas otimizadas usando Continuous Aggregates do TimescaleDB.

**Versão**: 1.0.0 Estável

**Todas as regras de negócio centralizadas na API!** ✅

## 📊 Endpoints Disponíveis

### 1. Histórico de Equipamento

**GET** `/api/v1/analytics/equipment/:equipmentUuid/history`

Retorna histórico de telemetria de um equipamento.

**Query Parameters:**
- `period` (string): `hour` | `day` | `raw` (default: `hour`)
- `start_date` (ISO 8601): Data inicial (default: 7 dias atrás)
- `end_date` (ISO 8601): Data final (default: agora)
- `sensor_type` (string): Filtrar por tipo de sensor (opcional)

**Exemplo:**
```bash
curl -X GET \
  "http://localhost:8000/api/v1/analytics/equipment/550e8400-e29b-41d4-a716-446655440000/history?period=hour&start_date=2024-01-01T00:00:00Z" \
  -H "Authorization: Bearer <token>"
```

**Resposta:**
```json
{
  "equipment_uuid": "550e8400-e29b-41d4-a716-446655440000",
  "period": "hour",
  "start_date": "2024-01-01T00:00:00Z",
  "end_date": "2024-01-08T00:00:00Z",
  "data": [
    {
      "time": "2024-01-01T00:00:00Z",
      "sensor_uuid": "660e8400-e29b-41d4-a716-446655440001",
      "sensor_name": "Sensor Temperatura",
      "sensor_type": "temperatura",
      "sensor_unit": "°C",
      "avg_value": 25.5,
      "max_value": 26.0,
      "min_value": 25.0,
      "sample_count": 3600,
      "active_minutes": 60,
      "median_value": 25.5,
      "p95_value": 25.8
    }
  ]
}
```

### 2. Histórico de Sensor

**GET** `/api/v1/analytics/sensor/:sensorUuid/history`

Retorna histórico de um sensor específico.

**Query Parameters:**
- `period` (string): `hour` | `day` | `raw` (default: `hour`)
- `start_date` (ISO 8601): Data inicial (default: 7 dias atrás)
- `end_date` (ISO 8601): Data final (default: agora)

**Exemplo:**
```bash
curl -X GET \
  "http://localhost:8000/api/v1/analytics/sensor/660e8400-e29b-41d4-a716-446655440001/history?period=day" \
  -H "Authorization: Bearer <token>"
```

### 3. Estatísticas de Equipamento

**GET** `/api/v1/analytics/equipment/:equipmentUuid/stats`

Retorna estatísticas agregadas de um equipamento (otimizado para dashboards).

**Query Parameters:**
- `period` (string): `24h` | `7d` | `30d` | `1y` (default: `24h`)
- `sensor_type` (string): Filtrar por tipo de sensor (opcional)

**Exemplo:**
```bash
curl -X GET \
  "http://localhost:8000/api/v1/analytics/equipment/550e8400-e29b-41d4-a716-446655440000/stats?period=7d" \
  -H "Authorization: Bearer <token>"
```

**Resposta:**
```json
{
  "equipment_uuid": "550e8400-e29b-41d4-a716-446655440000",
  "period": "7d",
  "start_date": "2024-01-01T00:00:00Z",
  "end_date": "2024-01-08T00:00:00Z",
  "sensors": [
    {
      "sensor_uuid": "660e8400-e29b-41d4-a716-446655440001",
      "sensor_name": "Sensor Temperatura",
      "sensor_type": "temperatura",
      "sensor_unit": "°C",
      "overall_avg": 25.5,
      "overall_max": 30.0,
      "overall_min": 20.0,
      "total_samples": 604800,
      "active_periods": 168
    }
  ]
}
```

### 4. Dados para Home Assistant

**GET** `/api/v1/analytics/home-assistant/:equipmentUuid`

Endpoint otimizado para integração Home Assistant.

**Query Parameters:**
- `hours` (integer): Últimas N horas (1-168, default: 24)
- `sensor_type` (string): Filtrar por tipo de sensor (opcional)

**Exemplo:**
```bash
curl -X GET \
  "http://localhost:8000/api/v1/analytics/home-assistant/550e8400-e29b-41d4-a716-446655440000?hours=48" \
  -H "Authorization: Bearer <token>"
```

**Resposta:**
```json
{
  "equipment_uuid": "550e8400-e29b-41d4-a716-446655440000",
  "period_hours": 48,
  "data": [
    {
      "time": "2024-01-07T00:00:00Z",
      "sensor_uuid": "660e8400-e29b-41d4-a716-446655440001",
      "sensor_name": "Sensor Temperatura",
      "sensor_type": "temperatura",
      "unit": "°C",
      "value": 25.5,
      "max": 26.0,
      "min": 25.0,
      "samples": 3600
    }
  ]
}
```

## ⚡ Performance

### Otimizações Aplicadas

1. **Continuous Aggregates**: Queries usam views pré-calculadas
2. **Índices Otimizados**: Índices compostos em `(equipment_id, bucket)` e `(sensor_id, bucket)`
3. **Real-Time Aggregation**: TimescaleDB combina dados materializados com dados brutos recentes
4. **Connection Pooling**: Pool de 20 conexões reutilizáveis

### Tempos de Resposta Esperados

- **Histórico (24h)**: 10-50ms
- **Histórico (7d)**: 50-200ms
- **Histórico (30d)**: 100-500ms
- **Estatísticas**: 20-100ms
- **Home Assistant**: 10-50ms

## 🔒 Segurança

- ✅ Autenticação JWT obrigatória
- ✅ Validação de parâmetros
- ✅ Sanitização de inputs
- ✅ Rate limiting aplicado
- ✅ Logs estruturados para auditoria

## 📝 Regras de Negócio Centralizadas

Todas as regras de negócio estão na API:

1. **Validação de Períodos**: Apenas períodos válidos aceitos
2. **Cálculo de Datas**: Datas padrão calculadas automaticamente
3. **Seleção de Views**: View otimizada escolhida automaticamente baseada no período
4. **Formatação de Respostas**: Formato consistente para todos os endpoints
5. **Filtros**: Filtros aplicados de forma segura (prepared statements)

**Nenhuma regra de negócio no frontend ou Home Assistant!** ✅

## 🚀 Uso no Dashboard

```javascript
// Exemplo: Buscar histórico de temperatura
const response = await fetch(
  `/api/v1/analytics/equipment/${equipmentUuid}/history?period=hour&sensor_type=temperatura`,
  {
    headers: {
      'Authorization': `Bearer ${token}`
    }
  }
);

const { data } = await response.json();

// Usar dados diretamente no gráfico
chart.data = data.map(row => ({
  x: new Date(row.time),
  y: row.avg_value
}));
```

## 🏠 Uso no Home Assistant

```python
# Exemplo: Integração Home Assistant
response = requests.get(
    f"{API_URL}/api/v1/analytics/home-assistant/{equipment_uuid}?hours=24",
    headers={"Authorization": f"Bearer {token}"}
)

data = response.json()["data"]

# Criar sensores no Home Assistant
for row in data:
    sensor = {
        "state": row["value"],
        "attributes": {
            "unit_of_measurement": row["unit"],
            "max": row["max"],
            "min": row["min"]
        }
    }
    # Atualizar sensor no Home Assistant
```

---

**API Analytics pronta para uso!** 🚀
