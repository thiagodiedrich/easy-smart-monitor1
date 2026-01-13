import logging
import asyncio
from datetime import datetime
from typing import Optional

from homeassistant.components.binary_sensor import (
    BinarySensorEntity,
    BinarySensorDeviceClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.event import async_track_state_change_event
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, SIREN_DELAY

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(
    hass: HomeAssistant, 
    entry: ConfigEntry, 
    async_add_entities: AddEntitiesCallback
) -> None:
    """Configura as entidades de sensor binário (Sirene)."""
    coordinator = hass.data[DOMAIN][entry.entry_id]
    equipments = entry.data.get("equipments", [])
    
    entities = []
    for equip in equipments:
        for sensor_cfg in equip.get("sensors", []):
            if sensor_cfg["tipo"] == "sirene":
                entities.append(EasySmartSirenEntity(coordinator, equip, sensor_cfg))
    
    if entities:
        async_add_entities(entities)

class EasySmartSirenEntity(CoordinatorEntity, BinarySensorEntity):
    """Entidade de Sirene que monitora a porta e dispara após o delay configurado."""

    def __init__(self, coordinator, equip, sensor_cfg):
        super().__init__(coordinator)
        self._equip = equip
        self._config = sensor_cfg
        self._attr_unique_id = f"esm_siren_{sensor_cfg['uuid']}"
        self._attr_name = f"Alerta Sirene {equip['nome']}"
        self._attr_device_class = BinarySensorDeviceClass.SAFETY
        self._is_on = False
        self._timer_task: Optional[asyncio.Task] = None

    async def async_added_to_hass(self) -> None:
        """Inicia o monitoramento do sensor de porta vinculado."""
        await super().async_added_to_hass()
        
        @callback
        def _door_monitor(event):
            new_state = event.data.get("new_state")
            if not new_state:
                return

            # Verifica