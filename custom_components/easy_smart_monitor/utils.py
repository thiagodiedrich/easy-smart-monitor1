import logging
from datetime import datetime
from homeassistant.core import HomeAssistant, State
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er
from .const import (
    DOMAIN,
    CONF_ATIVO,
    CONF_INTERVALO_COLETA,
    CONF_SIRENE_ATIVA,
    CONF_TEMPO_PORTA,
    DEFAULT_EQUIPAMENTO_ATIVO,
    DEFAULT_INTERVALO_COLETA,
    DEFAULT_SIRENE_ATIVA,
    DEFAULT_TEMPO_PORTA_ABERTA
)

_LOGGER = logging.getLogger(__name__)

def get_sensor_payload(hass: HomeAssistant, equip: dict, sensor_cfg: dict, state_obj: State) -> dict:
    """Gera o payload detalhado de telemetria seguindo o padrão solicitado."""
    
    # 1. Dados do Equipamento
    is_ativo = equip.get(CONF_ATIVO, DEFAULT_EQUIPAMENTO_ATIVO)
    equip_status = "ATIVO" if is_ativo else "INATIVO"
    
    # 2. Dados do Registro de Dispositivos para o Sensor (Entidade Fonte)
    sensor_fabricante = "Desconhecido"
    sensor_modelo = "Desconhecido"
    sensor_firmware = "N/A"
    sensor_via_hub = False
    serial = "N/A"
    
    ent_reg = er.async_get(hass)
    dev_reg = dr.async_get(hass)
    
    source_entity_id = sensor_cfg.get("ha_entity_id")
    entity_entry = ent_reg.async_get(source_entity_id)
    
    if entity_entry and entity_entry.device_id:
        device_entry = dev_reg.async_get(entity_entry.device_id)
        if device_entry:
            sensor_fabricante = device_entry.manufacturer or "Desconhecido"
            sensor_modelo = device_entry.model or "Desconhecido"
            sensor_firmware = device_entry.sw_version or "N/A"
            sensor_via_hub = device_entry.via_device_id is not None
            # Tenta pegar um serial/id de hardware dos identificadores
            for identifier in device_entry.identifiers:
                if identifier[0] != DOMAIN:
                    serial = identifier[1]
                    break

    # 3. Atributos da Entidade
    attrs = state_obj.attributes if state_obj else {}
    
    # 4. Montagem do Sub-objeto Sensor
    sensor_data = {
        "sensor_uuid": sensor_cfg.get("uuid"),
        "sensor_nome": attrs.get("friendly_name", source_entity_id),
        "sensor_status": "ATIVO" if is_ativo else "INATIVO", # Segue o status do equipamento
        "sensor_tipo": attrs.get("device_class", sensor_cfg.get("tipo", "desconhecido")),
        "sensor_unidade": attrs.get("unit_of_measurement", ""),
        "sensor_telemetria": state_obj.state if state_obj else "unknown",
        "sensor_datahora_coleta": datetime.now().isoformat(),
        "sensor_bateria_pct": attrs.get("battery_level"),
        "sensor_sinal_lqi": attrs.get("linkquality"),
        "sensor_sinal_rssi": attrs.get("rssi"),
        "sensor_voltagem_bateria": attrs.get("voltage"),
        "sensor_voltagem": attrs.get("voltage"),
        "sensor_corrente": attrs.get("current"),
        "sensor_potencia": attrs.get("power"),
        "sensor_fabricante": sensor_fabricante,
        "sensor_modelo": sensor_modelo,
        "sensor_firmware": sensor_firmware,
        "sensor_id_hardware": serial,
        "sensor_via_hub": sensor_via_hub
    }

    # 5. Payload Final
    return {
        "equip_uuid": equip.get("uuid"),
        "equip_nome": equip.get("nome"),
        "equip_local": equip.get("local"),
        "equip_status": equip_status,
        "equip_intervalo_coleta": equip.get(CONF_INTERVALO_COLETA, DEFAULT_INTERVALO_COLETA),
        "equip_sirene_ativa": "SIM" if equip.get(CONF_SIRENE_ATIVA, DEFAULT_SIRENE_ATIVA) else "NÃO",
        "equip_sirete_tempo": equip.get(CONF_TEMPO_PORTA, DEFAULT_TEMPO_PORTA_ABERTA),
        "sensor": sensor_data
    }
