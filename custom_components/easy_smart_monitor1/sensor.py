import logging
import time
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
    """Configura as entidades de sensor e diagnóstico v1.0.11."""
    coordinator = hass.data[DOMAIN][entry.entry_id]
    equipments = entry.data.get("equipments", [])

    entities = []
    for equip in equipments:
        # Sensores de Telemetria
        for sensor_cfg in equip.get("sensors", []):
            if sensor_cfg.get("tipo") not in ["sirene", "porta"]:
                entities.append(EasySmartMonitorEntity(coordinator, entry, equip, sensor_cfg))

        # Sensores de Diagnóstico Automáticos
        entities.append(EasySmartDiagnosticSensor(coordinator, equip, "conexao"))
        entities.append(EasySmartDiagnosticSensor(coordinator, equip, "sincro"))

    if entities:
        async_add_entities(entities)

class EasySmartMonitorEntity(CoordinatorEntity, SensorEntity):
    """Entidade de telemetria que respeita os novos controles de hardware."""

    def __init__(self, coordinator, entry, equip, sensor_cfg):
        super().__init__(coordinator)
        self.entry = entry
        self._equip = equip
        self._config = sensor_cfg
        self._attr_unique_id = f"esm_{sensor_cfg['uuid']}"
        self._attr_name = f"{equip['nome']} {sensor_cfg['tipo'].capitalize()}"
        self._state = None
        self._tipo = sensor_cfg.get("tipo")
        self._ha_source_entity = sensor_cfg.get("ha_entity_id")

        # Controle de fluxo (v1.0.11)
        self._last_collection_time = 0

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
        mapping = {
            "temperatura": (SensorDeviceClass.TEMPERATURE, "°C", SensorStateClass.MEASUREMENT),
            "energia": (SensorDeviceClass.POWER, "W", SensorStateClass.MEASUREMENT),
            "tensao": (SensorDeviceClass.VOLTAGE, "V", SensorStateClass.MEASUREMENT),
            "corrente": (SensorDeviceClass.CURRENT, "A", SensorStateClass.MEASUREMENT),
            "humidade": (SensorDeviceClass.HUMIDITY, "%", SensorStateClass.MEASUREMENT),
        }

        if self._tipo in mapping:
            d_class, unit, s_class = mapping[self._tipo]
            self._attr_device_class = d_class
            self._attr_native_unit_of_measurement = unit
            self._attr_state_class = s_class
        else:
            self._attr_icon = "mdi:information-variant"

    @property
    def native_value(self):
        return self._state

    def _get_equip_config(self):
        """Busca as configurações em tempo real do entry.data (Controles)."""
        for e in self.entry.data.get("equipments", []):
            if e["uuid"] == self._equip["uuid"]:
                return e
        return {}

    async def async_added_to_hass(self) -> None:
        """Listener que agora respeita os switches e inputs numéricos."""
        await super().async_added_to_hass()

        @callback
        def _state_listener(event):
            new_state = event.data.get("new_state")
            if new_state is None or new_state.state in ["unknown", "unavailable"]:
                return

            # 1. Verificação de Equipamento Ativo (Switch 1)
            config = self._get_equip_config()
            is_active = config.get("ativo", True)
            if not is_active:
                _LOGGER.debug("Coleta ignorada: %s está desativado.", self._equip["nome"])
                return

            # 2. Verificação de Intervalo de Coleta (Number 2)
            intervalo = config.get("intervalo_coleta", 10)
            now = time.time()
            if now - self._last_collection_time < intervalo:
                return # Ignora se estiver dentro do intervalo de carência

            # Processamento do valor
            raw_val = new_state.state
            has_unit = getattr(self, "_attr_native_unit_of_measurement", None)

            if has_unit is not None:
                try:
                    self._state = float(raw_val)
                except (ValueError, TypeError):
                    self._state = raw_val
            else:
                self._state = raw_val

            # Atualiza o timestamp da última coleta bem-sucedida
            self._last_collection_time = now

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
    """Sensores de diagnóstico permanecem ativos para monitorar o sistema."""
    def __init__(self, coordinator, equip, diag_type):
        super().__init__(coordinator)
        self._equip = equip
        self._diag_type = diag_type
        self._attr_unique_id = f"esm_diag_{diag_type}_{equip['uuid']}"
        self._attr_entity_category = EntityCategory.DIAGNOSTIC
        self._attr_name = f"{equip['nome']} {'Status API' if diag_type == 'conexao' else 'Última Sincronização'}"
        self._attr_device_info = DeviceInfo(identifiers={(DOMAIN, equip["uuid"])})

    @property
    def native_value(self):
        if self._diag_type == "conexao":
            return "Conectado" if self.coordinator.last_sync_success else "Erro de Rede"
        return self.coordinator.last_sync_time