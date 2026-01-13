import logging
import asyncio
from datetime import datetime
from homeassistant.components.binary_sensor import (
    BinarySensorEntity,
    BinarySensorDeviceClass
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.event import async_track_state_change_event
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.helpers.entity import DeviceInfo

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback) -> None:
    """Configura os sensores binários de Porta e Sirene."""
    coordinator = hass.data[DOMAIN][entry.entry_id]
    equipments = entry.data.get("equipments", [])

    entities = []
    for equip in equipments:
        for sensor_cfg in equip.get("sensors", []):
            tipo = sensor_cfg.get("tipo")
            if tipo == "porta":
                # Criamos o sensor de porta e a sirene associada a ele
                porta_sensor = EasySmartPortaSensor(coordinator, entry, equip, sensor_cfg)
                entities.append(porta_sensor)
                entities.append(EasySmartSireneSensor(coordinator, entry, equip, porta_sensor))

    if entities:
        async_add_entities(entities)

class EasySmartPortaSensor(CoordinatorEntity, BinarySensorEntity):
    """Monitoriza a porta física e gere o temporizador para a sirene."""

    def __init__(self, coordinator, entry, equip, sensor_cfg):
        super().__init__(coordinator)
        self.entry = entry
        self._equip = equip
        self._config = sensor_cfg
        self._attr_unique_id = f"esm_porta_{sensor_cfg['uuid']}"
        self._attr_name = f"{equip['nome']} Porta"
        self._attr_device_class = BinarySensorDeviceClass.DOOR
        self._attr_is_on = False
        self._ha_source_entity = sensor_cfg.get("ha_entity_id")

        # Estado interno para sirene
        self.sirene_deve_tocar = False
        self._timer_task = None

        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, equip["uuid"])},
            name=equip["nome"]
        )

    def _get_equip_config(self):
        """Obtém configurações de 'Equipamento Ativo' e 'Tempo Porta'."""
        for e in self.entry.data.get("equipments", []):
            if e["uuid"] == self._equip["uuid"]:
                return e
        return {}

    async def async_added_to_hass(self) -> None:
        """Monitoriza a entidade de origem para iniciar o temporizador."""
        await super().async_added_to_hass()

        @callback
        def _state_listener(event):
            new_state = event.data.get("new_state")
            if not new_state: return

            config = self._get_equip_config()
            if not config.get("ativo", True): return

            is_open = new_state.state in ["on", "open", "true"]
            self._attr_is_on = is_open

            # Lógica do Temporizador da Sirene
            if is_open:
                self._start_timer(config.get("tempo_porta", 120))
            else:
                self._stop_timer()

            # Envia telemetria da porta
            self.coordinator.async_add_telemetry({
                "equip_uuid": self._equip["uuid"],
                "sensor_uuid": self._config["uuid"],
                "tipo": "porta",
                "status": "aberta" if is_open else "fechada",
                "timestamp": datetime.now().isoformat()
            })
            self.async_write_ha_state()

        self.async_on_remove(async_track_state_change_event(self.hass, self._ha_source_entity, _state_listener))

    def _start_timer(self, delay):
        """Inicia contagem para ativar a sirene."""
        self._stop_timer()
        async def _timer():
            await asyncio.sleep(delay)
            self.sirene_deve_tocar = True
            _LOGGER.warning("Porta de %s aberta por muito tempo! Ativando sinal de sirene.", self._equip['nome'])
            self.coordinator.async_update_listeners() # Notifica a entidade Sirene

        self._timer_task = self.hass.async_create_task(_timer())

    def _stop_timer(self):
        """Cancela o temporizador e desliga o sinal da sirene."""
        if self._timer_task:
            self._timer_task.cancel()
            self._timer_task = None
        self.sirene_deve_tocar = False
        self.coordinator.async_update_listeners()

class EasySmartSireneSensor(CoordinatorEntity, BinarySensorEntity):
    """Entidade de Sirene que depende do estado da porta e do switch 'Sirene Ativa'."""

    def __init__(self, coordinator, entry, equip, porta_sensor):
        super().__init__(coordinator)
        self.entry = entry
        self._equip = equip
        self._porta = porta_sensor
        self._attr_unique_id = f"esm_sirene_{equip['uuid']}"
        self._attr_name = f"{equip['nome']} Sirene"
        self._attr_device_class = BinarySensorDeviceClass.PROBLEM
        self._attr_icon = "mdi:alarm-bell"
        self._attr_device_info = DeviceInfo(identifiers={(DOMAIN, equip["uuid"])})

    @property
    def is_on(self) -> bool:
        """A sirene só liga se: Porta excedeu tempo E Switch 'Sirene Ativa' está ON."""
        # 1. Verifica se o hardware geral está ativo
        config = self._get_config()
        if not config.get("ativo", True): return False

        # 2. Verifica se a Sirene está habilitada nos controlos (Switch 3)
        if not config.get("sirene_ativa", True): return False

        # 3. Verifica o estado vindo do temporizador da porta
        return self._porta.sirene_deve_tocar

    def _get_config(self):
        for e in self.entry.data.get("equipments", []):
            if e["uuid"] == self._equip["uuid"]:
                return e
        return {}