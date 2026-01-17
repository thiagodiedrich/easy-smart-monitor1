import logging
from datetime import datetime
from typing import Optional, Any

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


def _safe_number(value: Any) -> Optional[float]:
    """Converte valor para int/float se possível, senão retorna None."""
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    try:
        return float(str(value).replace(",", "."))
    except (TypeError, ValueError):
        return None


def _extract_from_entity(hass: HomeAssistant, entity_id: str, attrs: dict, state: str, device_class: Optional[str]) -> dict:
    """
    Extrai battery, linkquality, rssi, voltage, current, power de uma entidade.
    Considera atributos e, para sensores específicos, o state.
    """
    out = {
        "battery_level": None,
        "linkquality": None,
        "rssi": None,
        "voltage": None,
        "current": None,
        "power": None,
    }
    eid_lower = entity_id.lower()

    # Bateria: atributos battery_level, battery; ou state de sensor com device_class battery
    out["battery_level"] = _safe_number(attrs.get("battery_level") or attrs.get("battery"))
    if out["battery_level"] is None and (device_class == "battery" or "battery" in eid_lower):
        out["battery_level"] = _safe_number(state)
    # Algumas integrações usam 0-1; se valor entre 0 e 1, converter para 0-100
    if out["battery_level"] is not None and 0 <= out["battery_level"] <= 1:
        out["battery_level"] = round(out["battery_level"] * 100, 1)

    # Link quality (Zigbee: linkquality, link_quality)
    out["linkquality"] = _safe_number(attrs.get("linkquality") or attrs.get("link_quality"))

    # RSSI
    out["rssi"] = _safe_number(attrs.get("rssi"))

    # Voltagem: atributo voltage, battery_voltage; ou state de sensor de voltage
    out["voltage"] = _safe_number(attrs.get("voltage") or attrs.get("battery_voltage"))
    if out["voltage"] is None and (device_class == "voltage" or "voltage" in eid_lower or "tensao" in eid_lower):
        out["voltage"] = _safe_number(state)

    # Corrente
    out["current"] = _safe_number(attrs.get("current"))
    if out["current"] is None and (device_class == "current" or "current" in eid_lower or "corrente" in eid_lower):
        out["current"] = _safe_number(state)

    # Potência
    out["power"] = _safe_number(attrs.get("power"))
    if out["power"] is None and (device_class == "power" or "power" in eid_lower or "potencia" in eid_lower or "energia" in eid_lower):
        out["power"] = _safe_number(state)

    return out


def _get_sibling_attributes(
    hass: HomeAssistant,
    ent_reg,
    device_id: str,
    source_entity_id: str,
) -> dict:
    """
    Busca battery, linkquality, rssi, voltage, current, power em todas as entidades
    do mesmo dispositivo (entidades irmãs). Útil quando a entidade de origem (ex. temperatura)
    não tem esses atributos, que costumam estar em outras entidades (ex. sensor de bateria, linkquality).
    """
    result = {
        "battery_level": None,
        "linkquality": None,
        "rssi": None,
        "voltage": None,
        "current": None,
        "power": None,
    }
    try:
        # async_entries_for_device(registry, device_id, include_disabled_entities=False)
        sibling_entries = er.async_entries_for_device(ent_reg, device_id, include_disabled_entities=False)
    except Exception:
        return result

    for entry in sibling_entries:
        if entry.entity_id == source_entity_id:
            continue
        st = hass.states.get(entry.entity_id)
        if not st:
            continue
        attrs = st.attributes or {}
        dc = attrs.get("device_class")
        extracted = _extract_from_entity(hass, entry.entity_id, attrs, st.state or "", dc)
        for k, v in extracted.items():
            if v is not None and result[k] is None:
                result[k] = v
    return result

def get_equipment_header(equip: dict) -> dict:
    """Gera apenas o cabeçalho do equipamento seguindo o padrão solicitado."""
    is_ativo = equip.get(CONF_ATIVO, DEFAULT_EQUIPAMENTO_ATIVO)
    equip_status = "ATIVO" if is_ativo else "INATIVO"
    
    return {
        "equip_uuid": equip.get("uuid"),
        "equip_nome": equip.get("nome"),
        "equip_local": equip.get("local"),
        "equip_status": equip_status,
        "equip_intervalo_coleta": equip.get(CONF_INTERVALO_COLETA, DEFAULT_INTERVALO_COLETA),
        "equip_sirene_ativa": "SIM" if equip.get(CONF_SIRENE_ATIVA, DEFAULT_SIRENE_ATIVA) else "NÃO",
        "equip_sirete_tempo": equip.get(CONF_TEMPO_PORTA, DEFAULT_TEMPO_PORTA_ABERTA)
    }

def get_sensor_data(hass: HomeAssistant, sensor_cfg: dict, state_obj: State, is_ativo: bool) -> dict:
    """Gera apenas os dados técnicos do sensor seguindo o padrão solicitado."""
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

    # Atributos da entidade de origem
    attrs = state_obj.attributes if state_obj else {}
    dc_origin = attrs.get("device_class")

    # 1) Extrair da entidade de origem (temperatura, porta, etc.)
    meta = _extract_from_entity(
        hass, source_entity_id, attrs, (state_obj.state or ""), dc_origin
    )

    # 2) Se a entidade pertence a um dispositivo, buscar também nas entidades irmãs
    #    (battery, linkquality, rssi, voltage, current, power costumam estar em outras entidades)
    if entity_entry and entity_entry.device_id:
        sibling = _get_sibling_attributes(hass, ent_reg, entity_entry.device_id, source_entity_id)
        for k, v in sibling.items():
            if v is not None and meta.get(k) is None:
                meta[k] = v

    # voltage: usar para sensor_voltagem e sensor_voltagem_bateria quando não houver distinção
    voltage = meta.get("voltage")

    return {
        "sensor_uuid": sensor_cfg.get("uuid"),
        "sensor_nome": attrs.get("friendly_name", source_entity_id),
        "sensor_status": "ATIVO" if is_ativo else "INATIVO",
        "sensor_tipo": attrs.get("device_class", sensor_cfg.get("tipo", "desconhecido")),
        "sensor_unidade": attrs.get("unit_of_measurement", ""),
        "sensor_telemetria": state_obj.state if state_obj else "unknown",
        "sensor_datahora_coleta": datetime.now().isoformat(),
        "sensor_bateria_pct": meta.get("battery_level"),
        "sensor_sinal_lqi": meta.get("linkquality"),
        "sensor_sinal_rssi": meta.get("rssi"),
        "sensor_voltagem_bateria": voltage,
        "sensor_voltagem": voltage,
        "sensor_corrente": meta.get("current"),
        "sensor_potencia": meta.get("power"),
        "sensor_fabricante": sensor_fabricante,
        "sensor_modelo": sensor_modelo,
        "sensor_firmware": sensor_firmware,
        "sensor_id_hardware": serial,
        "sensor_via_hub": sensor_via_hub
    }
