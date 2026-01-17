import logging
import time
from datetime import datetime
from typing import Any, Dict, Optional

from homeassistant.components.sensor import (
    SensorEntity,
    SensorStateClass,
    SensorDeviceClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.event import async_track_state_change_event
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.helpers.entity import DeviceInfo, EntityCategory
from homeassistant.const import STATE_UNAVAILABLE, STATE_UNKNOWN

from .const import (
    DOMAIN,
    CONF_EQUIPMENTS,
    CONF_SENSORS,
    CONF_ATIVO,
    CONF_INTERVALO_COLETA,
    DEFAULT_INTERVALO_COLETA,
    DEFAULT_EQUIPAMENTO_ATIVO,
    CONF_SENSOR_ATIVO,
    DIAG_CONEXAO_OK,
    DIAG_INTERNET_ERR,
    DIAG_SERVER_ERR,
    DIAG_TIMEOUT_RETRY,
    ATTR_LAST_SYNC,
    ATTR_QUEUE_SIZE
)

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback) -> None:
    """
    Configura os sensores de telemetria e diagnóstico v1.3.0.
    """
    coordinator = hass.data[DOMAIN][entry.entry_id]
    equipments = entry.data.get(CONF_EQUIPMENTS, [])

    entities = []

    for equip in equipments:
        equip_uuid = equip["uuid"]

        # 1. Criação dos Sensores de Telemetria (Temperatura, Energia, etc.)
        for sensor_cfg in equip.get(CONF_SENSORS, []):
            # Ignora sensores binários (Porta/Sirene) pois são tratados no binary_sensor.py
            if sensor_cfg.get("tipo") in ["porta", "sirene"]:
                continue

            entities.append(EasySmartTelemetrySensor(coordinator, entry, equip, sensor_cfg))

        # 2. Criação dos Sensores de Diagnóstico (Vinculados ao Equipamento)
        # Status da Conexão API
        entities.append(EasySmartDiagnosticSensor(
            coordinator, equip, "conexao", "Status Conexão API", "mdi:server-network"
        ))
        # Última Sincronização
        entities.append(EasySmartDiagnosticSensor(
            coordinator, equip, "sincro", "Última Sincronização", "mdi:clock-check"
        ))
        # Tamanho da Fila (Para monitorar dados pendentes deste equipamento)
        entities.append(EasySmartDiagnosticSensor(
            coordinator, equip, "fila", "Fila de Envio", "mdi:tray-full"
        ))

    if entities:
        async_add_entities(entities)


class EasySmartTelemetrySensor(SensorEntity):
    """
    Sensor que monitora uma entidade de origem do HA e envia dados para a fila.
    Respeita 'Equipamento Ativo' e 'Intervalo de Coleta'.
    """

    def __init__(self, coordinator, entry, equip, sensor_cfg):
        self.coordinator = coordinator
        self.entry = entry
        self._equip = equip
        self._config = sensor_cfg

        # Identificação
        self._attr_unique_id = f"esm_{sensor_cfg['uuid']}"
        self._attr_translation_key = sensor_cfg.get("tipo")
        self._attr_has_entity_name = True

        # Estado interno
        self._state = None
        self._tipo = sensor_cfg.get("tipo")
        self._ha_source_entity = sensor_cfg.get("ha_entity_id")
        self._last_collection_time = 0.0 # Timestamp da última coleta

        # Configuração de Ícone e Unidade
        self._setup_sensor_characteristics()

        # Device Info (Agrupamento)
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, equip["uuid"])},
            name=equip["nome"],
            manufacturer="Easy Smart",
            model="Monitor Industrial v1.3.0",
            suggested_area=equip.get("local"),
        )

    def _setup_sensor_characteristics(self):
        """Define classe, unidade e ícone baseado no tipo de grandeza."""
        mapping = {
            "temperatura": (SensorDeviceClass.TEMPERATURE, "°C", "mdi:thermometer"),
            "energia": (SensorDeviceClass.POWER, "W", "mdi:flash"),
            "tensao": (SensorDeviceClass.VOLTAGE, "V", "mdi:sine-wave"),
            "corrente": (SensorDeviceClass.CURRENT, "A", "mdi:current-ac"),
            "umidade": (SensorDeviceClass.HUMIDITY, "%", "mdi:water-percent"),
        }

        if self._tipo in mapping:
            dev_class, unit, icon = mapping[self._tipo]
            self._attr_device_class = dev_class
            self._attr_native_unit_of_measurement = unit
            self._attr_icon = icon
            self._attr_state_class = SensorStateClass.MEASUREMENT
        else:
            self._attr_icon = "mdi:chart-line"

    @property
    def native_value(self):
        return self._state

    def _get_current_equip_config(self) -> Dict[str, Any]:
        """Busca a configuração mais recente do equipamento (pode ter mudado via Switch/Number)."""
        # A entry.data é atualizada pelos controls (switch.py/number.py)
        for e in self.entry.data.get(CONF_EQUIPMENTS, []):
            if e["uuid"] == self._equip["uuid"]:
                return e
        return self._equip # Fallback

    def _get_current_sensor_config(self) -> Dict[str, Any]:
        """Busca a configuração atual deste sensor específico."""
        equip_cfg = self._get_current_equip_config()
        for s in equip_cfg.get(CONF_SENSORS, []):
            if s["uuid"] == self._config["uuid"]:
                return s
        return self._config

    async def async_added_to_hass(self) -> None:
        """Registra o timer de coleta periódica e inicializa o valor atual."""
        await super().async_added_to_hass()

        # 1. Tenta inicializar o estado com o valor atual da entidade fonte
        initial_state = self.hass.states.get(self._ha_source_entity)
        if initial_state is not None and initial_state.state not in [STATE_UNAVAILABLE, STATE_UNKNOWN]:
            try:
                raw_value = initial_state.state
                if self._attr_device_class in [SensorDeviceClass.TEMPERATURE, SensorDeviceClass.POWER, SensorDeviceClass.VOLTAGE]:
                    self._state = float(raw_value)
                else:
                    self._state = raw_value
                
                _LOGGER.debug(
                    "Estado inicial recuperado para %s: %s", 
                    self._ha_source_entity, 
                    self._state
                )
            except ValueError:
                _LOGGER.warning(
                    "Valor inicial inválido para %s: %s", 
                    self._ha_source_entity, 
                    initial_state.state
                )

        @callback
        def _periodic_collection(now=None):
            """Executa a coleta periódica baseada no intervalo configurado."""
            # 1. Verifica se o Equipamento está ativo
            current_config = self._get_current_equip_config()
            if not current_config.get(CONF_ATIVO, DEFAULT_EQUIPAMENTO_ATIVO):
                return

            # 2. Verifica se este Sensor específico está ativo
            sensor_config = self._get_current_sensor_config()
            if not sensor_config.get(CONF_SENSOR_ATIVO, True):
                return

            source_state = self.hass.states.get(self._ha_source_entity)
            if source_state is None or source_state.state in [STATE_UNAVAILABLE, STATE_UNKNOWN]:
                return

            try:
                raw_value = source_state.state
                if self._attr_device_class in [SensorDeviceClass.TEMPERATURE, SensorDeviceClass.POWER, SensorDeviceClass.VOLTAGE]:
                    processed_value = float(raw_value)
                else:
                    processed_value = raw_value

                self._state = processed_value
                
                # Monta o payload
                payload = {
                    "equip_uuid": self._equip["uuid"],
                    "sensor_uuid": self._config["uuid"],
                    "tipo": self._tipo,
                    "status": str(processed_value),
                    "timestamp": datetime.now().isoformat()
                }

                # Envio para o Coordenador
                self.hass.async_create_task(self.coordinator.async_add_telemetry(payload))
                self.async_write_ha_state()

            except ValueError:
                _LOGGER.warning("Valor inválido em coleta periódica de %s: %s", self._ha_source_entity, raw_value)

        # Configura o timer periódico
        from homeassistant.helpers.event import async_track_time_interval
        from datetime import timedelta

        # Busca o intervalo inicial. Se for menor que 30 segundos, assume 30 
        # para não prejudicar o desempenho do Home Assistant.
        current_config = self._get_current_equip_config()
        intervalo = max(int(current_config.get(CONF_INTERVALO_COLETA, 30)), 30)
        
        self._unsub_timer = async_track_time_interval(
            self.hass, 
            _periodic_collection, 
            timedelta(seconds=intervalo)
        )
        self.async_on_remove(self._unsub_timer)

        # Monitora também mudanças na configuração para atualizar o timer se o intervalo mudar
        @callback
        def _config_change_listener(event):
            # Se a configuração do intervalo mudou, reiniciamos o timer
            # Nota: No ESM, as mudanças de entry.data não disparam eventos de estado facilmente,
            # mas o reload da integração após mudar o Number cuidará disso se não implementarmos um listener específico.
            # Como a integração recarrega ao mudar o Number (via async_update_options em __init__.py),
            # o timer será recriado com o novo valor automaticamente.
            pass


class EasySmartDiagnosticSensor(CoordinatorEntity, SensorEntity):
    """
    Sensor de diagnóstico que expõe as propriedades do Coordinator.
    Usa 'last_sync_success', 'last_sync_time' e 'queue_size'.
    """

    def __init__(self, coordinator, equip, diag_type, name, icon):
        super().__init__(coordinator)
        self._equip = equip
        self._diag_type = diag_type

        self._attr_unique_id = f"esm_diag_{diag_type}_{equip['uuid']}"
        self._attr_translation_key = diag_type
        self._attr_icon = icon
        self._attr_entity_category = EntityCategory.DIAGNOSTIC
        self._attr_has_entity_name = True

        self._attr_device_info = DeviceInfo(identifiers={(DOMAIN, equip["uuid"])})

    @property
    def native_value(self):
        """Lê as propriedades restauradas do coordenador."""
        if self._diag_type == "conexao":
            # Retorna o status real (Conectado, Falha de Internet, Falha de Servidor ou Timeout/Retry)
            return self.coordinator.data.get("status_conexao", DIAG_INTERNET_ERR) if self.coordinator.data else DIAG_INTERNET_ERR

        elif self._diag_type == "sincro":
            # Usa a propriedade last_sync_time
            return self.coordinator.last_sync_time

        elif self._diag_type == "fila":
            # Usa a propriedade queue_size
            return self.coordinator.queue_size

        return None