from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.entity import DeviceInfo

from .const import (
    DOMAIN,
    DEFAULT_EQUIPAMENTO_ATIVO,
    DEFAULT_SIRENE_ATIVA,
    CONF_SENSORS,
    CONF_SENSOR_ATIVO
)

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback) -> None:
    coordinator = hass.data[DOMAIN][entry.entry_id]
    equipments = entry.data.get("equipments", [])

    entities = []
    for equip in equipments:
        # 1. Switch Mestre do Equipamento
        entities.append(EasySmartSwitch(coordinator, entry, equip, "ativo", "Equipamento Ativo", "mdi:power"))
        
        # 2. Switches Individuais para cada Sensor
        sensors = equip.get(CONF_SENSORS, [])
        for sensor_cfg in sensors:
            entities.append(EasySmartSensorSwitch(coordinator, entry, equip, sensor_cfg))

        # 3. Switch de Sirene (se existir sensor do tipo sirene)
        has_siren = any(s.get("tipo") == "sirene" for s in sensors)
        if has_siren:
            entities.append(EasySmartSwitch(coordinator, entry, equip, "sirene_ativa", "Sirene Ativa", "mdi:alarm-bell"))

    async_add_entities(entities)

class EasySmartSwitch(SwitchEntity):
    # ... (mantém a classe existente)
    def __init__(self, coordinator, entry, equip, key, name, icon):
        self.coordinator = coordinator
        self.entry = entry
        self.equip = equip
        self.key = key
        self._attr_translation_key = key
        self._attr_has_entity_name = True
        self._attr_icon = icon
        self._attr_unique_id = f"esm_sw_{key}_{equip['uuid']}"
        self._attr_device_info = DeviceInfo(identifiers={(DOMAIN, equip["uuid"])})

    @property
    def is_on(self) -> bool:
        # Busca o estado atual dentro do dicionário do equipamento no config_entry
        for e in self.entry.data.get("equipments", []):
            if e["uuid"] == self.equip["uuid"]:
                # Retorna o valor salvo ou o padrão correspondente
                default = DEFAULT_SIRENE_ATIVA if self.key == "sirene_ativa" else DEFAULT_EQUIPAMENTO_ATIVO
                return e.get(self.key, default)
        return True

    async def async_turn_on(self, **kwargs):
        await self._update_entry(True)

    async def async_turn_off(self, **kwargs):
        await self._update_entry(False)

    async def _update_entry(self, state):
        new_data = dict(self.entry.data)
        for e in new_data["equipments"]:
            if e["uuid"] == self.equip["uuid"]:
                e[self.key] = state
        self.hass.config_entries.async_update_entry(self.entry, data=new_data)
        self.async_write_ha_state()


class EasySmartSensorSwitch(SwitchEntity):
    """Switch para habilitar/desabilitar o monitoramento de um sensor individual."""

    def __init__(self, coordinator, entry, equip, sensor_cfg):
        self.coordinator = coordinator
        self.entry = entry
        self.equip = equip
        self.sensor_cfg = sensor_cfg
        
        tipo = sensor_cfg.get("tipo", "sensor").capitalize()
        self._attr_name = f"Monitorar {tipo}"
        self._attr_unique_id = f"esm_sw_sensor_{sensor_cfg['uuid']}"
        self._attr_has_entity_name = True
        self._attr_translation_key = "sensor_monitor"
        self._attr_translation_placeholders = {"sensor_name": tipo}
        self._attr_icon = "mdi:eye-check" if self.is_on else "mdi:eye-off-outline"
        
        self._attr_device_info = DeviceInfo(identifiers={(DOMAIN, equip["uuid"])})

    @property
    def is_on(self) -> bool:
        # Procura o sensor específico dentro da config
        for e in self.entry.data.get("equipments", []):
            if e["uuid"] == self.equip["uuid"]:
                for s in e.get("sensors", []):
                    if s["uuid"] == self.sensor_cfg["uuid"]:
                        return s.get(CONF_SENSOR_ATIVO, True)
        return True

    async def async_turn_on(self, **kwargs):
        await self._update_sensor_state(True)

    async def async_turn_off(self, **kwargs):
        await self._update_sensor_state(False)

    async def _update_sensor_state(self, state):
        new_data = dict(self.entry.data)
        for e in new_data["equipments"]:
            if e["uuid"] == self.equip["uuid"]:
                for s in e["sensors"]:
                    if s["uuid"] == self.sensor_cfg["uuid"]:
                        s[CONF_SENSOR_ATIVO] = state
        
        self.hass.config_entries.async_update_entry(self.entry, data=new_data)
        self._attr_icon = "mdi:eye-check" if state else "mdi:eye-off-outline"
        self.async_write_ha_state()