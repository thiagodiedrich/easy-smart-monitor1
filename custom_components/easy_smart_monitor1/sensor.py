import logging
import asyncio
from datetime import datetime
from typing import Optional, Any, Dict

from homeassistant.components.sensor import (
    SensorEntity,
    SensorStateClass,
    SensorDeviceClass
)
from homeassistant.components.binary_sensor import (
    BinarySensorEntity,
    BinarySensorDeviceClass
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
    """Configura todas as entidades (Sensores e Sirenes) da integração."""
    coordinator = hass.data[DOMAIN][entry.entry_id]
    equipments = entry.data.get("equipments", [])

    entities = []
    for equip in equipments:
        for sensor_cfg in equip.get("sensors", []):
            if sensor_cfg["tipo"] == "sirene":
                entities.append(EasySmartSirenEntity(coordinator, equip, sensor_cfg))
            else:
                entities.append(EasySmartMonitorEntity(coordinator, equip, sensor_cfg))

    if entities:
        async_add_entities(entities)

class EasySmartMonitorEntity(CoordinatorEntity, SensorEntity):
    """Entidade para sensores de medição (Temperatura, Energia, etc)."""

    def __init__(self, coordinator, equip, sensor_cfg):
        super().__init__(coordinator)
        self._equip = equip
        self._config = sensor_cfg
        self._attr_unique_id = f"esm_{sensor_cfg['uuid']}"
        self._attr_name = f"{equip['nome']} {sensor_cfg['tipo'].capitalize()}"
        self._state = None

        # Definição de Classes e Unidades
        tipo = sensor_cfg["tipo"]
        if tipo == "temperatura":
            self._attr_device_class = SensorDeviceClass.TEMPERATURE
            self._attr_state_class = SensorStateClass.MEASUREMENT
            self._attr_native_unit_of_measurement = "°C"
        elif tipo == "energia":
            self._attr_device_class = SensorDeviceClass.POWER
            self._attr_state_class = SensorStateClass.MEASUREMENT
            self._attr_native_unit_of_measurement = "W"
        elif tipo == "tensao":
            self._attr_device_class = SensorDeviceClass.VOLTAGE
            self._attr_state_class = SensorStateClass.MEASUREMENT
            self._attr_native_unit_of_measurement = "V"
        elif tipo == "corrente":
            self._attr_device_class = SensorDeviceClass.CURRENT
            self._attr_state_class = SensorStateClass.MEASUREMENT
            self._attr_native_unit_of_measurement = "A"
        elif tipo == "humidade":
            self._attr_device_class = SensorDeviceClass.HUMIDITY
            self._attr_state_class = SensorStateClass.MEASUREMENT
            self._attr_native_unit_of_measurement = "%"

    async def async_added_to_hass(self) -> None:
        """Monitora o estado da entidade real e envia para a fila."""
        await super().async_added_to_hass()

        @callback
        def _state_listener(event):
            new_state = event.data.get("new_state")
            if new_state is None or new_state.state in ["unknown", "unavailable"]:
                return

            self._state = new_state.state

            # Adiciona à fila de sincronização
            self.coordinator.client.add_to_queue({
                "equip_id": self._equip["id"],
                "equip_uuid": self._equip["uuid"],
                "sensor_id": self._config["id"],
                "sensor_uuid": self._config["uuid"],
                "tipo": self._config["tipo"],
                "status": self._state,
                "timestamp": datetime.now().isoformat()
            })
            self.async_write_ha_state()

        self.async_on_remove(
            async_track_state_change_event(
                self.hass, self._config["ha_entity_id"], _state_listener
            )
        )

    @property
    def native_value(self):
        return self._state

    @property
    def extra_state_attributes(self):
        return {
            "equipamento_nome": self._equip["nome"],
            "localizacao": self._equip["local"],
            "entidade_origem": self._config["ha_entity_id"]
        }

class EasySmartSirenEntity(CoordinatorEntity, BinarySensorEntity):
    """Entidade de Sirene com lógica de delay integrada."""

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
        """Monitora a porta para gerenciar o disparo da sirene."""
        await super().async_added_to_hass()

        @callback
        def _door_monitor(event):
            new_state = event.data.get("new_state")
            if not new_state:
                return

            if new_state.state in ["on", "open", "aberto"]:
                if not self._timer_task or self._timer_task.done():
                    self._timer_task = self.hass.async_create_task(self._run_siren_timer())
            else:
                self._reset_siren()

        # Busca o ID da porta no mesmo equipamento
        porta_id = next(
            (s["ha_entity_id"] for s in self._equip["sensors"] if s["tipo"] == "porta"),
            None
        )

        if porta_id:
            self.async_on_remove(
                async_track_state_change_event(self.hass, porta_id, _door_monitor)
            )

    async def _run_siren_timer(self):
        """Timer assíncrono para o disparo."""
        try:
            await asyncio.sleep(SIREN_DELAY)
            self._is_on = True
            self.async_write_ha_state()
            _LOGGER.warning("SIRENE ATIVADA: Porta de %s aberta há %ss", self._equip['nome'], SIREN_DELAY)
        except asyncio.CancelledError:
            pass

    def _reset_siren(self):
        """Desliga e cancela processos