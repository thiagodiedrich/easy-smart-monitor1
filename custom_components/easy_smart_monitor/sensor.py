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
    DIAG_CONEXAO_OK,
    DIAG_CONEXAO_ERR,
    ATTR_LAST_SYNC,
    ATTR_QUEUE_SIZE
)

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback) -> None:
    """
    Configura os sensores de telemetria e diagnóstico v1.0.13.
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


class EasySmartTelemetrySensor(CoordinatorEntity, SensorEntity):
    """
    Sensor que monitora uma entidade de origem do HA e envia dados para a fila.
    Respeita 'Equipamento Ativo' e 'Intervalo de Coleta'.
    """

    def __init__(self, coordinator, entry, equip, sensor_cfg):
        super().__init__(coordinator)
        self.entry = entry
        self._equip = equip
        self._config = sensor_cfg

        # Identificação
        self._attr_unique_id = f"esm_{sensor_cfg['uuid']}"
        self._attr_name = f"{equip['nome']} {sensor_cfg['tipo'].capitalize()} ({sensor_cfg['ha_entity_id'].split('.')[-1]})"
        self._attr_has_entity_name = False # Usa o nome completo definido acima

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
            model="Monitor Industrial v1.0.13",
            suggested_area=equip.get("local"),
        )

    def _setup_sensor_characteristics(self):
        """Define classe, unidade e ícone baseado no tipo de grandeza."""
        mapping = {
            "temperatura": (SensorDeviceClass.TEMPERATURE, "°C", "mdi:thermometer"),
            "energia": (SensorDeviceClass.POWER, "W", "mdi:flash"),
            "tensao": (SensorDeviceClass.VOLTAGE, "V", "mdi:sine-wave"),
            "corrente": (SensorDeviceClass.CURRENT, "A", "mdi:current-ac"),
            "humidade": (SensorDeviceClass.HUMIDITY, "%", "mdi:water-percent"),
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

    async def async_added_to_hass(self) -> None:
        """Registra o listener de mudança de estado."""
        await super().async_added_to_hass()

        @callback
        def _telemetry_listener(event):
            """Chamado sempre que a entidade original muda no HA."""
            new_state = event.data.get("new_state")

            # Validação Básica
            if new_state is None or new_state.state in [STATE_UNAVAILABLE, STATE_UNKNOWN]:
                return

            # 1. Verificação de Equipamento Ativo
            # Obtemos a config atualizada para respeitar o switch IMEDIATAMENTE
            current_config = self._get_current_equip_config()
            is_active = current_config.get(CONF_ATIVO, DEFAULT_EQUIPAMENTO_ATIVO)

            if not is_active:
                # Se o switch estiver OFF, ignoramos silenciosamente
                return

            # 2. Verificação de Intervalo (Debounce)
            intervalo = current_config.get(CONF_INTERVALO_COLETA, DEFAULT_INTERVALO_COLETA)
            now = time.time()

            if (now - self._last_collection_time) < intervalo:
                # Ignora atualizações muito rápidas para não floodar a fila
                return

            # 3. Processamento do Valor
            try:
                raw_value = new_state.state
                # Tenta converter para float se for numérico
                if self._attr_device_class in [SensorDeviceClass.TEMPERATURE, SensorDeviceClass.POWER, SensorDeviceClass.VOLTAGE]:
                    processed_value = float(raw_value)
                else:
                    processed_value = raw_value

                self._state = processed_value
                self._last_collection_time = now

                # Monta o payload
                payload = {
                    "equip_uuid": self._equip["uuid"],
                    "sensor_uuid": self._config["uuid"],
                    "tipo": self._tipo,
                    "status": str(processed_value),
                    "timestamp": datetime.now().isoformat()
                }

                # 4. Envio para o Coordenador
                # Usa async_create_task pois estamos dentro de um callback síncrono
                self.hass.async_create_task(self.coordinator.async_add_telemetry(payload))

                # Atualiza a interface do sensor
                self.async_write_ha_state()

            except ValueError:
                _LOGGER.warning("Valor inválido recebido de %s: %s", self._ha_source_entity, raw_value)

        # Monitora a entidade fonte
        self.async_on_remove(
            async_track_state_change_event(self.hass, self._ha_source_entity, _telemetry_listener)
        )


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
        self._attr_name = f"{equip['nome']} {name}"
        self._attr_icon = icon
        self._attr_entity_category = EntityCategory.DIAGNOSTIC
        self._attr_has_entity_name = False

        self._attr_device_info = DeviceInfo(identifiers={(DOMAIN, equip["uuid"])})

    @property
    def native_value(self):
        """Lê as propriedades restauradas do coordenador."""
        if self._diag_type == "conexao":
            # Usa a propriedade is_connected ou last_sync_success
            return DIAG_CONEXAO_OK if self.coordinator.last_sync_success else DIAG_CONEXAO_ERR

        elif self._diag_type == "sincro":
            # Usa a propriedade last_sync_time
            return self.coordinator.last_sync_time

        elif self._diag_type == "fila":
            # Usa a propriedade queue_size
            return self.coordinator.queue_size

        return None