from homeassistant.components.number import NumberEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.entity import DeviceInfo

from .const import DOMAIN

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback) -> None:
    coordinator = hass.data[DOMAIN][entry.entry_id]
    equipments = entry.data.get("equipments", [])

    entities = []
    for equip in equipments:
        entities.append(EasySmartNumber(coordinator, entry, equip, "intervalo_coleta", "Intervalo de Coleta", 10, 3600, 1, "s", "mdi:timer-cog"))
        entities.append(EasySmartNumber(coordinator, entry, equip, "tempo_porta", "Tempo Porta Aberta", 10, 600, 1, "s", "mdi:door-open"))

    async_add_entities(entities)

class EasySmartNumber(NumberEntity):
    def __init__(self, coordinator, entry, equip, key, name, min_val, max_val, step, unit, icon):
        self.coordinator = coordinator
        self.entry = entry
        self.equip = equip
        self.key = key
        self._attr_name = f"{equip['nome']} {name}"
        self._attr_native_min_value = min_val
        self._attr_native_max_value = max_val
        self._attr_native_step = step
        self._attr_native_unit_of_measurement = unit
        self._attr_icon = icon
        self._attr_unique_id = f"esm_num_{key}_{equip['uuid']}"
        self._attr_device_info = DeviceInfo(identifiers={(DOMAIN, equip["uuid"])})

    @property
    def native_value(self) -> float:
        for e in self.entry.data.get("equipments", []):
            if e["uuid"] == self.equip["uuid"]:
                # Retorna o valor salvo ou o padrão (10 para coleta, 120 para porta)
                default = 120 if self.key == "tempo_porta" else 10
                return e.get(self.key, default)
        return 10

    async def async_set_native_value(self, value: float):
        new_data = dict(self.entry.data)
        for e in new_data["equipments"]:
            if e["uuid"] == self.equip["uuid"]:
                e[self.key] = int(value)
        self.hass.config_entries.async_update_entry(self.entry, data=new_data)
        self.async_write_ha_state()