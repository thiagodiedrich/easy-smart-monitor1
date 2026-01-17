from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.entity import DeviceInfo

from .const import (
    DOMAIN,
    DEFAULT_EQUIPAMENTO_ATIVO,
    DEFAULT_SIRENE_ATIVA,
    NAME,
    VERSION
)

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback) -> None:
    coordinator = hass.data[DOMAIN][entry.entry_id]
    equipments = entry.data.get("equipments", [])

    entities = []
    for equip in equipments:
        # 1. Switch Mestre do Equipamento (Sempre Visível)
        entities.append(EasySmartSwitch(coordinator, entry, equip, "ativo", "Equipamento Ativo", "mdi:power"))
        
        # 2. Switch de Sirene (Sempre Visível, mas bloqueado se não houver sirene física)
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
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, equip["uuid"])},
            name=f"{equip['nome']} ({equip.get('local', 'Sem Local')})",
            manufacturer=NAME,
            model=f"Monitor Industrial v{VERSION}",
            suggested_area=equip.get("local"),
        )

    @property
    def is_on(self) -> bool:
        # Busca o estado atual dentro do dicionário do equipamento no config_entry
        for e in self.entry.data.get("equipments", []):
            if e["uuid"] == self.equip["uuid"]:
                # Retorna o valor salvo ou o padrão correspondente
                default = DEFAULT_SIRENE_ATIVA if self.key == "sirene_ativa" else DEFAULT_EQUIPAMENTO_ATIVO
                return e.get(self.key, default)
        return True

    @property
    def available(self) -> bool:
        """Retorna se o switch está disponível para uso."""
        # O switch principal sempre está disponível
        if self.key == "ativo":
            return True
            
        # O switch de sirene só fica disponível se houver um sensor tipo 'sirene' físico vinculado
        for e in self.entry.data.get("equipments", []):
            if e["uuid"] == self.equip["uuid"]:
                has_physical_siren = any(s.get("tipo") == "sirene" for s in e.get("sensors", []))
                return has_physical_siren
        return False

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
