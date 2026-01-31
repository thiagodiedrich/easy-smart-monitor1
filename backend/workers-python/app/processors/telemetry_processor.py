"""
Processador de telemetria.

Processa dados de telemetria recebidos do Kafka e insere no banco de dados.
"""
from datetime import datetime
from typing import List, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
import structlog

from app.models.equipment import Equipment
from app.models.sensor import Sensor
from app.models.telemetry_data import TelemetryData
from app.core.config import settings

logger = structlog.get_logger(__name__)


class TelemetryProcessor:
    """Processador de dados de telemetria."""
    
    async def process_bulk(
        self,
        user_id: int,
        telemetry_data: List[Dict[str, Any]],
        db: AsyncSession,
    ) -> Dict[str, Any]:
        """
        Processa um lote de dados de telemetria.
        
        Args:
            user_id: ID do usuário proprietário
            telemetry_data: Lista de dados de telemetria (formato do cliente)
            db: Sessão do banco de dados
            
        Returns:
            Dicionário com resultado do processamento
        """
        processed = 0
        inserted = 0
        errors: List[str] = []
        
        # Agrupar por equipamento para otimizar
        equipment_map: Dict[str, Dict[str, Any]] = {}
        
        for item in telemetry_data:
            try:
                equip_uuid = item.get("equip_uuid")
                if not equip_uuid:
                    errors.append("Item sem equip_uuid")
                    continue
                
                # Inicializar estrutura do equipamento se não existir
                if equip_uuid not in equipment_map:
                    equipment_map[equip_uuid] = {
                        "equipment": None,
                        "sensors": {},
                        "telemetry_data": [],
                    }
                
                # Processar equipamento
                equipment = equipment_map[equip_uuid]["equipment"]
                if equipment is None:
                    equipment = await self._get_or_create_equipment(
                        user_id,
                        item,
                        db,
                    )
                    equipment_map[equip_uuid]["equipment"] = equipment
                
                # Processar sensores
                sensors_data = item.get("sensor", [])
                if not isinstance(sensors_data, list):
                    sensors_data = [sensors_data]
                
                for sensor_data in sensors_data:
                    sensor_uuid = sensor_data.get("sensor_uuid")
                    if not sensor_uuid:
                        continue
                    
                    if sensor_uuid not in equipment_map[equip_uuid]["sensors"]:
                        sensor = await self._get_or_create_sensor(
                            equipment.id,
                            sensor_data,
                            item,  # Passar item completo para pegar tipo se necessário
                            db,
                        )
                        equipment_map[equip_uuid]["sensors"][sensor_uuid] = sensor
                    else:
                        sensor = equipment_map[equip_uuid]["sensors"][sensor_uuid]
                    
                    # Preparar dados de telemetria
                    telemetry_item = self._prepare_telemetry_data(
                        sensor.id,
                        equipment.id,
                        sensor_data,
                    )
                    equipment_map[equip_uuid]["telemetry_data"].append(telemetry_item)
                
                processed += 1
            
            except Exception as e:
                error_msg = f"Erro ao processar item: {str(e)}"
                logger.error(error_msg, exc_info=e)
                errors.append(error_msg)
        
        # Inserir dados de telemetria em bulk por equipamento
        for equip_uuid, data in equipment_map.items():
            if data["telemetry_data"]:
                try:
                    # Dividir em batches para otimizar
                    batch_size = settings.BULK_INSERT_BATCH_SIZE
                    for i in range(0, len(data["telemetry_data"]), batch_size):
                        batch = data["telemetry_data"][i:i + batch_size]
                        inserted_count = await TelemetryData.bulk_insert(db, batch)
                        inserted += inserted_count
                    
                    # Commit após cada equipamento
                    await db.commit()
                except Exception as e:
                    await db.rollback()
                    error_msg = f"Erro ao inserir telemetria para {equip_uuid}: {str(e)}"
                    logger.error(error_msg, exc_info=e)
                    errors.append(error_msg)
        
        return {
            "processed": processed,
            "inserted": inserted,
            "errors": errors if errors else None,
        }
    
    async def _get_or_create_equipment(
        self,
        user_id: int,
        item: Dict[str, Any],
        db: AsyncSession,
    ) -> Equipment:
        """Busca ou cria um equipamento."""
        equip_uuid = item.get("equip_uuid")
        
        # Buscar equipamento existente
        equipment = await Equipment.get_by_uuid(db, equip_uuid)
        
        if equipment:
            if equipment.user_id != user_id:
                raise ValueError(f"Equipamento {equip_uuid} não pertence ao usuário")
            return equipment
        
        # Criar novo equipamento
        equipment = Equipment(
            uuid=equip_uuid,
            name=item.get("equip_nome", f"Equipamento {equip_uuid[:8]}"),
            location=item.get("equip_local"),
            status=item.get("equip_status", "ATIVO"),
            collection_interval=item.get("equip_intervalo_coleta", 60),
            siren_active=item.get("equip_sirene_ativa", "NÃO") == "SIM",
            siren_time=item.get("equip_sirete_tempo", 120),
            user_id=user_id,
        )
        
        db.add(equipment)
        await db.flush()
        
        logger.info("Equipamento criado", uuid=equipment.uuid, name=equipment.name)
        
        return equipment
    
    async def _get_or_create_sensor(
        self,
        equipment_id: int,
        sensor_data: Dict[str, Any],
        item: Dict[str, Any],
        db: AsyncSession,
    ) -> Sensor:
        """Busca ou cria um sensor."""
        sensor_uuid = sensor_data.get("sensor_uuid")
        if not sensor_uuid:
            raise ValueError("sensor_uuid não encontrado")
        
        # Buscar sensor existente
        sensor = await Sensor.get_by_uuid(db, sensor_uuid)
        
        if sensor:
            if sensor.equipment_id != equipment_id:
                raise ValueError(f"Sensor {sensor_uuid} não pertence ao equipamento")
            return sensor
        
        # Criar novo sensor
        sensor = Sensor(
            uuid=sensor_uuid,
            name=sensor_data.get("sensor_nome", f"Sensor {sensor_uuid[:8]}"),
            type=sensor_data.get("sensor_tipo") or sensor_data.get("tipo", "desconhecido"),
            unit=sensor_data.get("sensor_unidade"),
            status=sensor_data.get("sensor_status", "ATIVO"),
            equipment_id=equipment_id,
            manufacturer=sensor_data.get("sensor_fabricante"),
            model=sensor_data.get("sensor_modelo"),
            firmware=sensor_data.get("sensor_firmware"),
            hardware_id=sensor_data.get("sensor_id_hardware"),
            via_hub=sensor_data.get("sensor_via_hub", False),
        )
        
        db.add(sensor)
        await db.flush()
        
        logger.info("Sensor criado", uuid=sensor.uuid, name=sensor.name, type=sensor.type)
        
        return sensor
    
    def _prepare_telemetry_data(
        self,
        sensor_id: int,
        equipment_id: int,
        sensor_data: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Prepara dados de telemetria para inserção."""
        # Converter timestamp
        timestamp_str = sensor_data.get("sensor_datahora_coleta") or sensor_data.get("timestamp")
        if timestamp_str:
            try:
                timestamp = datetime.fromisoformat(timestamp_str.replace("Z", "+00:00"))
            except (ValueError, AttributeError):
                timestamp = datetime.utcnow()
        else:
            timestamp = datetime.utcnow()
        
        # Extrair valor/status
        valor = sensor_data.get("valor")
        status = sensor_data.get("status")
        
        # Se não tem valor direto, tentar extrair de sensor_telemetria
        if valor is None:
            telemetria = sensor_data.get("sensor_telemetria")
            if telemetria is not None:
                if isinstance(telemetria, (int, float)):
                    valor = float(telemetria)
                elif isinstance(telemetria, str):
                    try:
                        valor = float(telemetria)
                    except (ValueError, TypeError):
                        status = telemetria
        
        # Preparar metadata
        metadata = {}
        if sensor_data.get("sensor_bateria_pct") is not None:
            metadata["battery"] = sensor_data["sensor_bateria_pct"]
        if sensor_data.get("sensor_sinal_rssi") is not None:
            metadata["rssi"] = sensor_data["sensor_sinal_rssi"]
        if sensor_data.get("sensor_sinal_lqi") is not None:
            metadata["lqi"] = sensor_data["sensor_sinal_lqi"]
        if sensor_data.get("sensor_voltagem_bateria") is not None:
            metadata["battery_voltage"] = sensor_data["sensor_voltagem_bateria"]
        
        return {
            "sensor_id": sensor_id,
            "equipment_id": equipment_id,
            "value": valor,
            "status": status,
            "timestamp": timestamp,
            "extra_metadata": metadata if metadata else None,
        }
