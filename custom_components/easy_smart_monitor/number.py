from homeassistant.components.number import NumberEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.exceptions import ServiceValidationError

from .const import (
    DOMAIN,
    DEFAULT_INTERVALO_COLETA,
    DEFAULT_TEMPO_PORTA_ABERTA
)

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback) -> None:
    coordinator = hass.data[DOMAIN][entry.entry_id]
    equipments = entry.data.get("equipments", [])

    entities = []
    for equip in equipments:
        # Trava na UI: Permitimos o ajuste, mas validamos no código para garantir o mínimo de 30s
        entities.append(EasySmartNumber(coordinator, entry, equip, "intervalo_coleta", "Intervalo de Coleta", 1, 3600, 1, "s", "mdi:timer-cog"))
        
        # Verifica se o equipamento possui sensores do tipo 'porta' e 'sirene'
        sensors = equip.get("sensors", [])
        has_door = any(s.get("tipo") == "porta" for s in sensors)
        has_siren = any(s.get("tipo") == "sirene" for s in sensors)

        if has_door and has_siren:
            entities.append(EasySmartNumber(coordinator, entry, equip, "tempo_porta", "Tempo Porta Aberta", 1, 600, 1, "s", "mdi:door-open"))

    async_add_entities(entities)

class EasySmartNumber(NumberEntity):
    def __init__(self, coordinator, entry, equip, key, name, min_val, max_val, step, unit, icon):
        self.coordinator = coordinator
        self.entry = entry
        self.equip = equip
        self.key = key
        self._attr_translation_key = key
        self._attr_has_entity_name = True
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
                # Retorna o valor salvo ou o padrão das constantes
                default = DEFAULT_TEMPO_PORTA_ABERTA if self.key == "tempo_porta" else DEFAULT_INTERVALO_COLETA
                return e.get(self.key, default)
        return DEFAULT_INTERVALO_COLETA

    async def async_set_native_value(self, value: float):
        # Validação de segurança para o Intervalo de Coleta
        if self.key == "intervalo_coleta" and value < 30:
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="intervalo_coleta_baixo"
            )
        
        # Validação de segurança para o Tempo de Porta
        if self.key == "tempo_porta" and value < 10:
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="tempo_porta_baixo"
            )

        new_data = dict(self.entry.data)
        for e in new_data["equipments"]:
            if e["uuid"] == self.equip["uuid"]:
                e[self.key] = int(value)
        
        # Atualiza a entrada e força o reload para que os sensores reiniciem seus timers
        self.hass.config_entries.async_update_entry(self.entry, data=new_data)
        await self.hass.config_entries.async_reload(self.entry.entry_id)
        self.async_write_ha_state()