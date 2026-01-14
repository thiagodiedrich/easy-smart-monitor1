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
    CONF_INTERVALO_COLETA,
    CONF_TEMPO_PORTA,
    DEFAULT_EQUIPAMENTO_ATIVO,
    DEFAULT_SIRENE_ATIVA,
    DEFAULT_INTERVALO_COLETA,
    DEFAULT_TEMPO_PORTA_ABERTA
)

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback) -> None:
    """Configura os sensores binários (Porta e Sirene Lógica)."""
    coordinator = hass.data[DOMAIN][entry.entry_id]
    equipments = entry.data.get(CONF_EQUIPMENTS, [])

    entities = []

    for equip in equipments:
        # 1. Sensores de Porta (Físicos) e Sirenes (Físicas ou Lógicas)
        for sensor_cfg in equip.get(CONF_SENSORS, []):
            tipo = sensor_cfg.get("tipo")
            if tipo == "porta":
                # Cria a entidade que monitora a porta física
                door_entity = EasySmartDoorSensor(coordinator, entry, equip, sensor_cfg)
                entities.append(door_entity)

            elif tipo == "sirene":
                # Caso o usuário adicione uma sirene física manualmente
                entities.append(EasySmartGenericBinarySensor(coordinator, entry, equip, sensor_cfg, BinarySensorDeviceClass.SOUND))

            elif tipo == "botao":
                # Caso o usuário adicione um botão de reset físico
                entities.append(EasySmartButtonSensor(coordinator, entry, equip, sensor_cfg))

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
        self._attr_translation_key = "porta"
        self._attr_has_entity_name = True
        self._attr_device_class = BinarySensorDeviceClass.DOOR

        self._ha_source_entity = sensor_cfg.get("ha_entity_id")
        self._is_open = False
        self._open_since = 0.0 # Timestamp de quando abriu

        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, equip["uuid"])},
            name=equip["nome"],
            manufacturer="Easy Smart",
            model="Monitor Industrial v1.0.16",
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

        # Listener para o evento de reset pelo botão
        @callback
        def _handle_reset_event(event):
            if event.data.get("equip_uuid") == self._equip["uuid"]:
                _LOGGER.debug("Botão pressionado: Resetando timer da porta %s", self.entity_id)
                if self.is_on:
                    self._open_since = time.time()
                self.hass.async_create_task(self._check_and_trigger_siren())

        self.async_on_remove(
            self.hass.bus.async_listen(f"{DOMAIN}_button_pressed", _handle_reset_event)
        )

        @callback
        def _periodic_collection(now=None):
            """Executa a coleta periódica baseada no intervalo configurado."""
            current_config = self._get_current_equip_config()
            is_active = current_config.get(CONF_ATIVO, DEFAULT_EQUIPAMENTO_ATIVO)

            if not is_active:
                return

            source_state = self.hass.states.get(self._ha_source_entity)
            if source_state is None or source_state.state in [STATE_UNAVAILABLE, STATE_UNKNOWN]:
                return

            is_open = source_state.state == STATE_ON
            
            # Monta payload de telemetria
            payload = {
                "equip_uuid": self._equip["uuid"],
                "sensor_uuid": self._config["uuid"],
                "tipo": "porta",
                "status": "aberta" if is_open else "fechada",
                "timestamp": datetime.now().isoformat()
            }

            self.hass.async_create_task(self.coordinator.async_add_telemetry(payload))

        # Configura o timer periódico
        from homeassistant.helpers.event import async_track_time_interval
        from datetime import timedelta

        current_config = self._get_current_equip_config()
        intervalo = current_config.get(CONF_INTERVALO_COLETA, DEFAULT_INTERVALO_COLETA)
        
        self.async_on_remove(
            async_track_time_interval(self.hass, _periodic_collection, timedelta(seconds=intervalo))
        )

        # Timer para verificar tempo de porta aberta e disparar sirene
        @callback
        def _check_siren_timer(now):
            if self.is_on:
                self.hass.async_create_task(self._check_and_trigger_siren())

        self.async_on_remove(
            async_track_time_interval(self.hass, _check_siren_timer, timedelta(seconds=5))
        )

        # 1. Tenta inicializar o estado com o valor atual da entidade fonte
        initial_state = self.hass.states.get(self._ha_source_entity)
        if initial_state is not None and initial_state.state not in [STATE_UNAVAILABLE, STATE_UNKNOWN]:
            is_open = initial_state.state == STATE_ON
            self._is_open = is_open
            if is_open:
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

            # Atualiza variáveis internas
            if is_open and not self._is_open:
                self._open_since = time.time()
            elif not is_open:
                self._open_since = 0.0

            self._is_open = is_open
            self.async_write_ha_state() # Atualiza visual no HA

            # Verifica disparo imediato de sirene ao fechar (para desligar)
            if not is_open:
                self.hass.async_create_task(self._check_and_trigger_siren())

            # Coleta imediata em mudança de estado
            _periodic_collection()

        self.async_on_remove(
            async_track_state_change_event(self.hass, self._ha_source_entity, _door_state_listener)
        )

    async def _check_and_trigger_siren(self):
        """Verifica se alguma porta do equipamento estourou o tempo e controla as sirenes físicas."""
        current_config = self._get_current_equip_config()
        if not current_config.get(CONF_ATIVO, DEFAULT_EQUIPAMENTO_ATIVO):
            return

        sirene_ativa = current_config.get(CONF_SIRENE_ATIVA, False) # Padrão desativado como pedido
        tempo_limite = current_config.get(CONF_TEMPO_PORTA, DEFAULT_TEMPO_PORTA_ABERTA)
        
        # Busca todas as sirenes físicas deste equipamento
        siren_entities = [s["ha_entity_id"] for s in current_config.get(CONF_SENSORS, []) if s.get("tipo") == "sirene"]
        
        if not siren_entities:
            return

        # Se a opção de sirene ativa estiver desligada, garantimos que as sirenes estejam OFF
        if not sirene_ativa:
            for entity_id in siren_entities:
                await self._set_siren_state(entity_id, False)
            return

        # Verifica se ESTA porta ou QUALQUER OUTRA porta deste equipamento está aberta além do tempo
        # Para simplificar, cada porta cuida de si mesma no disparo, mas o desligamento depende de todas estarem fechadas
        
        # 1. Verifica se deve LIGAR (baseado nesta porta para agilidade)
        if self.is_on and self.open_duration > tempo_limite:
            for entity_id in siren_entities:
                await self._set_siren_state(entity_id, True)
            return

        # 2. Verifica se deve DESLIGAR (somente se TODAS as portas do equipamento estiverem ok)
        all_doors_ok = True
        for sensor_cfg in current_config.get(CONF_SENSORS, []):
            if sensor_cfg.get("tipo") == "porta":
                # Precisamos checar o estado real no HA, pois não temos acesso fácil aos outros objetos EasySmartDoorSensor
                state = self.hass.states.get(sensor_cfg["ha_entity_id"])
                if state and state.state == STATE_ON:
                    # Calcula duração se estiver aberta
                    duration = time.time() - state.last_changed.timestamp()
                    if duration > tempo_limite:
                        all_doors_ok = False
                        break
        
        if all_doors_ok:
            for entity_id in siren_entities:
                await self._set_siren_state(entity_id, False)

    async def _set_siren_state(self, entity_id, turn_on):
        """Auxiliar para ligar/desligar uma entidade no HA."""
        domain = entity_id.split(".")[0]
        service = "turn_on" if turn_on else "turn_off"
        
        # Tenta usar o serviço genérico homeassistant.turn_on/off se o domínio for comum
        # ou o serviço específico do domínio
        try:
            await self.hass.services.async_call(domain, service, {"entity_id": entity_id})
        except Exception as e:
            _LOGGER.error("Erro ao controlar sirene %s: %s", entity_id, e)


class EasySmartGenericBinarySensor(BinarySensorEntity):
    """Sensor binário genérico para tipos como 'sirene' física ou 'status'."""

    def __init__(self, coordinator, entry, equip, sensor_cfg, device_class=None):
        self.coordinator = coordinator
        self.entry = entry
        self._equip = equip
        self._config = sensor_cfg
        self._tipo = sensor_cfg.get("tipo")
        self._ha_source_entity = sensor_cfg.get("ha_entity_id")

        self._attr_unique_id = f"esm_bin_{sensor_cfg['uuid']}"
        self._attr_translation_key = self._tipo
        self._attr_has_entity_name = True
        self._attr_device_class = device_class

        self._state = False

        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, equip["uuid"])},
            name=equip["nome"],
            manufacturer="Easy Smart",
            model="Monitor Industrial v1.0.16",
        )

    @property
    def is_on(self):
        return self._state

    def _get_current_equip_config(self) -> Dict[str, Any]:
        for e in self.entry.data.get(CONF_EQUIPMENTS, []):
            if e["uuid"] == self._equip["uuid"]:
                return e
        return self._equip

    async def async_added_to_hass(self) -> None:
        """Registra o timer de coleta periódica e o listener de eventos."""
        await super().async_added_to_hass()

        @callback
        def _periodic_collection(now=None):
            """Executa a coleta periódica baseada no intervalo configurado."""
            current_config = self._get_current_equip_config()
            is_active = current_config.get(CONF_ATIVO, DEFAULT_EQUIPAMENTO_ATIVO)

            if not is_active:
                return

            source_state = self.hass.states.get(self._ha_source_entity)
            if source_state is None or source_state.state in [STATE_UNAVAILABLE, STATE_UNKNOWN]:
                return

            is_on = source_state.state == STATE_ON
            self._state = is_on
            self.async_write_ha_state()

            payload = {
                "equip_uuid": self._equip["uuid"],
                "sensor_uuid": self._config["uuid"],
                "tipo": self._tipo,
                "status": "ligado" if is_on else "desligado",
                "timestamp": datetime.now().isoformat()
            }
            self.hass.async_create_task(self.coordinator.async_add_telemetry(payload))

        # Configura o timer periódico
        from homeassistant.helpers.event import async_track_time_interval
        from datetime import timedelta

        current_config = self._get_current_equip_config()
        intervalo = current_config.get(CONF_INTERVALO_COLETA, DEFAULT_INTERVALO_COLETA)
        
        self.async_on_remove(
            async_track_time_interval(self.hass, _periodic_collection, timedelta(seconds=intervalo))
        )

        initial_state = self.hass.states.get(self._ha_source_entity)
        if initial_state is not None and initial_state.state not in [STATE_UNAVAILABLE, STATE_UNKNOWN]:
            self._state = initial_state.state == STATE_ON

        @callback
        def _state_listener(event):
            new_state = event.data.get("new_state")
            if new_state is None or new_state.state in [STATE_UNAVAILABLE, STATE_UNKNOWN]:
                return

            # Coleta imediata em mudança de estado (opcional, mas bom para responsividade)
            _periodic_collection()

        self.async_on_remove(
            async_track_state_change_event(self.hass, self._ha_source_entity, _state_listener)
        )


class EasySmartButtonSensor(BinarySensorEntity):
    """Sensor que representa um botão físico de reset de alarme."""

    def __init__(self, coordinator, entry, equip, sensor_cfg):
        self.coordinator = coordinator
        self.entry = entry
        self._equip = equip
        self._config = sensor_cfg
        self._ha_source_entity = sensor_cfg.get("ha_entity_id")

        self._attr_unique_id = f"esm_btn_{sensor_cfg['uuid']}"
        self._attr_translation_key = "botao"
        self._attr_has_entity_name = True
        self._attr_icon = "mdi:bell-off"

        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, equip["uuid"])},
            name=equip["nome"],
            manufacturer="Easy Smart",
            model="Monitor Industrial v1.0.16",
        )

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()

        @callback
        def _button_listener(event):
            new_state = event.data.get("new_state")
            if new_state is None:
                return

            # Dispara o reset quando o botão for pressionado (geralmente ON em sensores momentâneos)
            # Mas vamos disparar em qualquer mudança para ON para garantir
            if new_state.state == STATE_ON:
                _LOGGER.info("Botão de Reset pressionado para equipamento %s", self._equip["nome"])
                self.hass.bus.async_fire(f"{DOMAIN}_button_pressed", {"equip_uuid": self._equip["uuid"]})

        self.async_on_remove(
            async_track_state_change_event(self.hass, self._ha_source_entity, _button_listener)
        )
