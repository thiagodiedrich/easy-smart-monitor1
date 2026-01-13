import logging
import time
from datetime import datetime
from typing import Any, Dict

from homeassistant.components.binary_sensor import (
    BinarySensorEntity,
    BinarySensorDeviceClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.event import async_track_state_change_event
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.const import STATE_ON, STATE_OFF, STATE_UNAVAILABLE, STATE_UNKNOWN

from .const import (
    DOMAIN,
    CONF_EQUIPMENTS,
    CONF_SENSORS,
    CONF_ATIVO,
    CONF_SIRENE_ATIVA,
    CONF_TEMPO_PORTA,
    DEFAULT_EQUIPAMENTO_ATIVO,
    DEFAULT_SIRENE_ATIVA,
    DEFAULT_TEMPO_PORTA_ABERTA
)

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback) -> None:
    """Configura os sensores binários (Porta e Sirene Lógica)."""
    coordinator = hass.data[DOMAIN][entry.entry_id]
    equipments = entry.data.get(CONF_EQUIPMENTS, [])

    entities = []

    for equip in equipments:
        # 1. Sensores de Porta (Físicos)
        for sensor_cfg in equip.get(CONF_SENSORS, []):
            if sensor_cfg.get("tipo") == "porta":
                # Cria a entidade que monitora a porta física
                door_entity = EasySmartDoorSensor(coordinator, entry, equip, sensor_cfg)
                entities.append(door_entity)

                # Cria a entidade lógica de Sirene baseada nesta porta
                entities.append(EasySmartSirenSensor(coordinator, entry, equip, door_entity))

    if entities:
        async_add_entities(entities)


class EasySmartDoorSensor(BinarySensorEntity):
    """
    Monitora o estado de uma porta física (aberto/fechado).
    Envia telemetria imediata para a fila.
    """

    def __init__(self, coordinator, entry, equip, sensor_cfg):
        self.coordinator = coordinator
        self.entry = entry
        self._equip = equip
        self._config = sensor_cfg

        self._attr_unique_id = f"esm_porta_{sensor_cfg['uuid']}"
        self._attr_name = f"{equip['nome']} Porta ({sensor_cfg['ha_entity_id'].split('.')[-1]})"
        self._attr_device_class = BinarySensorDeviceClass.DOOR
        self._attr_has_entity_name = False

        self._ha_source_entity = sensor_cfg.get("ha_entity_id")
        self._is_open = False
        self._open_since = 0.0 # Timestamp de quando abriu

        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, equip["uuid"])},
            name=equip["nome"],
            manufacturer="Easy Smart",
            model="Monitor Industrial v1.0.13",
        )

    @property
    def is_on(self):
        """Retorna True se a porta estiver aberta."""
        return self._is_open

    @property
    def open_duration(self):
        """Retorna quantos segundos a porta está aberta (0 se fechada)."""
        if self._is_open:
            return time.time() - self._open_since
        return 0

    def _get_current_equip_config(self) -> Dict[str, Any]:
        """Busca configuração atualizada (para verificar se está Ativo)."""
        for e in self.entry.data.get(CONF_EQUIPMENTS, []):
            if e["uuid"] == self._equip["uuid"]:
                return e
        return self._equip

    async def async_added_to_hass(self) -> None:
        """Registra listener para mudança de estado da porta física e inicializa estado."""
        await super().async_added_to_hass()

        # 1. Tenta inicializar o estado com o valor atual da entidade fonte
        initial_state = self.hass.states.get(self._ha_source_entity)
        if initial_state is not None and initial_state.state not in [STATE_UNAVAILABLE, STATE_UNKNOWN]:
            is_open = initial_state.state == STATE_ON
            self._is_open = is_open
            if is_open:
                # Nota: Não sabemos há quanto tempo está aberta, então usamos agora
                # ou poderíamos tentar ler a propriedade last_changed
                self._open_since = initial_state.last_changed.timestamp()
            
            _LOGGER.debug(
                "Estado inicial recuperado para porta %s: %s", 
                self._ha_source_entity, 
                "aberta" if is_open else "fechada"
            )

        @callback
        def _door_state_listener(event):
            new_state = event.data.get("new_state")

            if new_state is None or new_state.state in [STATE_UNAVAILABLE, STATE_UNKNOWN]:
                return

            # Verifica se o equipamento está ativo
            current_config = self._get_current_equip_config()
            if not current_config.get(CONF_ATIVO, DEFAULT_EQUIPAMENTO_ATIVO):
                return

            # Lógica de Estado
            is_open = new_state.state == STATE_ON

            # Atualiza variáveis internas para a Sirene usar
            if is_open and not self._is_open:
                self._open_since = time.time()
            elif not is_open:
                self._open_since = 0.0

            self._is_open = is_open
            self.async_write_ha_state() # Atualiza visual no HA

            # Monta payload de telemetria
            payload = {
                "equip_uuid": self._equip["uuid"],
                "sensor_uuid": self._config["uuid"],
                "tipo": "porta",
                "status": "aberta" if is_open else "fechada",
                "timestamp": datetime.now().isoformat()
            }

            # --- CORREÇÃO DO ERRO ---
            # Antes: self.coordinator.async_add_telemetry(payload) -> ERRO (sem await)
            # Agora: Agendamos a tarefa no loop do HA
            self.hass.async_create_task(self.coordinator.async_add_telemetry(payload))

        self.async_on_remove(
            async_track_state_change_event(self.hass, self._ha_source_entity, _door_state_listener)
        )


class EasySmartSirenSensor(BinarySensorEntity):
    """
    Sensor lógico que dispara (ON) se a porta ficar aberta por mais tempo que o permitido.
    """

    def __init__(self, coordinator, entry, equip, door_sensor: EasySmartDoorSensor):
        self.coordinator = coordinator
        self.entry = entry
        self._equip = equip
        self._door_sensor = door_sensor # Referência ao sensor de porta

        self._attr_unique_id = f"esm_sirene_{door_sensor._config['uuid']}"
        self._attr_name = f"{equip['nome']} Alerta Sirene ({door_sensor._config['ha_entity_id'].split('.')[-1]})"
        self._attr_device_class = BinarySensorDeviceClass.PROBLEM
        self._attr_has_entity_name = False
        self._attr_icon = "mdi:alarm-light-off"

        self._attr_device_info = DeviceInfo(identifiers={(DOMAIN, equip["uuid"])})

    @property
    def is_on(self):
        """
        Retorna True (Alerta) se:
        1. Equipamento Ativo
        2. Sirene Ativa
        3. Porta Aberta > Tempo Limite
        """
        # 1. Configurações Atuais
        # Precisamos ler diretamente da entry.data porque os Numbers/Switches atualizam lá
        current_config = self._door_sensor._get_current_equip_config()

        ativo = current_config.get(CONF_ATIVO, DEFAULT_EQUIPAMENTO_ATIVO)
        sirene_ativa = current_config.get(CONF_SIRENE_ATIVA, DEFAULT_SIRENE_ATIVA)
        tempo_limite = current_config.get(CONF_TEMPO_PORTA, DEFAULT_TEMPO_PORTA_ABERTA)

        if not ativo or not sirene_ativa:
            return False

        # 2. Verifica Duração
        tempo_aberto = self._door_sensor.open_duration

        # Dispara se passou do tempo
        if tempo_aberto > tempo_limite:
            return True

        return False

    @property
    def icon(self):
        return "mdi:alarm-light" if self.is_on else "mdi:alarm-light-off"

    async def async_added_to_hass(self) -> None:
        """
        O sensor de sirene precisa atualizar a cada segundo enquanto a porta está aberta
        para verificar se o tempo estourou.
        """
        await super().async_added_to_hass()

        # Cria um timer que roda a cada segundo para atualizar o status da sirene
        # Isso é leve, pois é só uma checagem de memória
        @callback
        def _update_siren_logic(now):
            if self._door_sensor.is_on:
                self.async_write_ha_state()

        from homeassistant.helpers.event import async_track_time_interval
        from datetime import timedelta

        self.async_on_remove(
            async_track_time_interval(self.hass, _update_siren_logic, timedelta(seconds=1))
        )