import logging
import asyncio
from datetime import datetime
from typing import Any

from homeassistant.components.sensor import SensorEntity
from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.event import async_track_state_change_event
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.config_entries import ConfigEntry

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(
    hass: HomeAssistant, 
    entry: ConfigEntry, 
    async_add_entities: AddEntitiesCallback
) -> None:
    """Configura as entidades baseadas nos equipamentos salvos no config_flow."""
    coordinator = hass.data[DOMAIN][entry.entry_id]
    equipments = entry.data.get("equipments", [])
    
    entities = []
    for equip in equipments:
        for sensor in equip.get("sensors", []):
            if sensor["tipo"] == "sirene":
                entities.append(EasySmartSirene(coordinator, equip, sensor))
            else:
                entities.append(EasySmartMonitorSensor(coordinator, equip, sensor))
    
    async_add_entities(entities)

class EasySmartMonitorSensor(CoordinatorEntity, SensorEntity):
    """Representa sensores de Temperatura, Energia, Porta e Botão."""

    def __init__(self, coordinator, equip, sensor_config):
        super().__init__(coordinator)
        self._equip = equip
        self._config = sensor_config
        self._attr_unique_id = f"esm_{sensor_config['uuid']}"
        self._attr_name = f"{equip['nome']} {sensor_config['tipo'].capitalize()}"
        self._state = None

    async def async_added_to_hass(self) -> None:
        """Registra o listener para monitorar a entidade física vinculada."""
        await super().async_added_to_hass()
        
        @callback
        def _state_listener(event):
            new_state = event.data.get("new_state")
            if new_state is None:
                return
            
            self._state = new_state.state
            
            # Alimenta a Fila Local (Persistente)
            self.coordinator.client.add_to_queue({
                "equip_id": self._equip["id"],
                "equip_uuid": self._equip["uuid"],
                "sensor_id": self._config["id"],
                "sensor_uuid": self._config["uuid"],