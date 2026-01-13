import logging
from datetime import datetime
from homeassistant.components.sensor import (
    SensorEntity,
    SensorStateClass,
    SensorDeviceClass
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.event import async_track_state_change_event
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.helpers.entity import DeviceInfo, EntityCategory

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback) -> None:
    """Configura as entidades de sensor e diagnóstico v1.0.10."""
    coordinator = hass.data[DOMAIN][entry.entry_id]
    equipments = entry.data.get("equipments", [])

    entities = []
    for equip in equipments:
        # 1. Sensores de Telemetria (Definidos pelo Usuário)
        for sensor_cfg in equip.get("sensors", []):
            if sensor_cfg.get("tipo") not in ["sirene", "porta"]:
                entities.append(EasySmartMonitorEntity(coordinator, equip, sensor_cfg))

        # 2. Sensores de Diagnóstico Automáticos
        entities.append(EasySmartDiagnosticSensor(coordinator, equip, "conexao"))
        entities.append(EasySmartDiagnosticSensor(coordinator, equip, "sincro"))

    if entities:
        async_add_entities(entities)

class EasySmartMonitorEntity(CoordinatorEntity, SensorEntity):
    """Entidade para monitoramento de telemetria."""

    def __init__(self, coordinator, equip, sensor_cfg):
        super().__init__(coordinator)
        self._equip = equip
        self._config = sensor_cfg
        self._attr_unique_id = f"esm_{sensor_cfg['uuid']}"
        self._attr_name = f"{equip['nome']} {sensor_cfg['tipo'].capitalize()}"
        self._state = None
        self._tipo = sensor_cfg.get("tipo")
        self._ha_source_entity = sensor_cfg.get("ha_entity_id")

        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, equip["uuid"])},
            name=equip["nome"],
            manufacturer="Easy Smart",
            model="Monitor v1",
            suggested_area=equip.get("local"),
        )

        self._setup_sensor_type()

    def _setup_sensor_type(self):
        """Define as propriedades do sensor conforme o tipo."""
        if self._tipo == "temperatura":
            self._attr_device_class = SensorDeviceClass.TEMPERATURE
            self._attr_native_unit_of_measurement = "°C"
            self._attr_state_class = SensorStateClass.MEASUREMENT
        elif self._tipo == "energia":
            self._attr_device_class = SensorDeviceClass.POWER
            self._attr_native_unit_of_measurement = "W"
            self._attr_state_class = SensorStateClass.MEASUREMENT
        elif self._tipo == "tensao":
            self._attr_device_class = SensorDeviceClass.VOLTAGE
            self._attr_native_unit_of_measurement = "V"
            self._attr_state_class = SensorStateClass.MEASUREMENT
        elif self._tipo == "corrente":
            self._attr_device_class = SensorDeviceClass.CURRENT
            self._attr_native_unit_of_measurement = "A"
            self._attr_state_class = SensorStateClass.MEASUREMENT
        elif self._tipo == "humidade":
            self._attr_device_class = SensorDeviceClass.HUMIDITY
            self._attr_native_unit_of_measurement = "%"
            self._attr_state_class = SensorStateClass.MEASUREMENT
        elif self._tipo == "status":
            self._attr_device_class = None
            self._attr_native_unit_of_measurement = None
            self._attr_state_class = None
            self._attr_icon = "mdi:information-variant"

    @property
    def native_value(self):
        return self._state

    async def async_added_to_hass(self) -> None:
        """Listener para capturar mudanças na entidade original."""
        await super().async_added_to_hass()

        @callback
        def _state_listener(event):
            new_state = event.data.get("new_state")
            if new_state is None or new_state.state in ["unknown", "unavailable"]:
                return

            raw_val = new_state.state

            # CORREÇÃO DO ATRIBUTO: Verificando se existe unidade de medida definida
            # Usamos getattr para segurança extra contra erros de atributo
            has_unit = getattr(self, "_attr_native_unit_of_measurement", None)

            if has_unit is not None:
                try:
                    self._state = float(raw_val)
                except (ValueError, TypeError):
                    _LOGGER.error("Erro em %s: '%s' não é numérico", self.entity_id, raw_val)
                    self._state = raw_val
            else:
                self._state = raw_val

            # Envia via coordenador para a fila da API
            self.coordinator.async_add_telemetry({
                "equip_uuid": self._equip["uuid"],
                "sensor_uuid": self._config["uuid"],
                "tipo": self._tipo,
                "status": str(raw_val),
                "timestamp": datetime.now().isoformat()
            })
            self.async_write_ha_state()

        self.async_on_remove(async_track_state_change_event(self.hass, self._ha_source_entity, _state_listener))


class EasySmartDiagnosticSensor(CoordinatorEntity, SensorEntity):
    """Sensores de diagnóstico (Status API / Sincronia)."""

    def __init__(self, coordinator, equip, diag_type):
        super().__init__(coordinator)
        self._equip = equip
        self._diag_type = diag_type
        self._attr_unique_id = f"esm_diag_{diag_type}_{equip['uuid']}"
        self._attr_entity_category = EntityCategory.DIAGNOSTIC

        if diag_type == "conexao":
            self._attr_name = f"{equip['nome']} Status API"
            self._attr_icon = "mdi:cloud-sync"
        else:
            self._attr_name = f"{equip['nome']} Última Sincronia"
            self._attr_icon = "mdi:clock-check-outline"

        self._attr_device_info = DeviceInfo(identifiers={(DOMAIN, equip["uuid"])})

    @property
    def native_value(self):
        """Lê os dados do coordenador de saúde."""
        if self._diag_type == "conexao":
            return "Conectado" if self.coordinator.last_sync_success else "Erro de Rede"
        return self.coordinator.last_sync_time