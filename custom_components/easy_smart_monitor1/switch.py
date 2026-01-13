from homeassistant.components.switch import SwitchEntity
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
        entities.append(EasySmartSwitch(coordinator, entry, equip, "ativo", "Equipamento Ativo", "mdi:power"))
        entities.append(EasySmartSwitch(coordinator, entry, equip, "sirene_ativa", "Sirene Ativa", "mdi:alarm-bell"))

    async_add_entities(entities)

class EasySmartSwitch(SwitchEntity):
    def __init__(self, coordinator, entry, equip, key, name, icon):
        self.coordinator = coordinator
        self.entry = entry
        self.equip = equip
        self.key = key
        self._attr_name = f"{equip['nome']} {name}"
        self._attr_icon = icon
        self._attr_unique_id = f"esm_sw_{key}_{equip['uuid']}"
        self._attr_device_info = DeviceInfo(identifiers={(DOMAIN, equip["uuid"])})

    @property
    def is_on(self) -> bool:
        # Busca o estado atual dentro do dicionário do equipamento no config_entry
        for e in self.entry.data.get("equipments", []):
            if e["uuid"] == self.equip["uuid"]:
                return e.get(self.key, True)
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