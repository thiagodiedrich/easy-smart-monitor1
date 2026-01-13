import logging
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import (
    DOMAIN,
    CONF_API_HOST,
    CONF_USERNAME,
    CONF_PASSWORD,
    TEST_MODE
)
from .client import EasySmartClient
from .coordinator import EasySmartCoordinator

_LOGGER = logging.getLogger(__name__)

# Plataformas que a integração gerencia
PLATFORMS: list[Platform] = [Platform.SENSOR, Platform.BINARY_SENSOR]

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """
    Configura a integração v1.0.10.
    Responsável por inicializar o cliente, carregar persistência e limpar o registro.
    """
    _LOGGER.info("Iniciando Easy Smart Monitor v1.0.10")

    # 1. INICIALIZAÇÃO DO CLIENTE
    # Usamos .get() para evitar o erro KeyError caso o config_flow tenha falhado
    api_host = entry.data.get(CONF_API_HOST, "http://localhost")
    username = entry.data.get(CONF_USERNAME, "admin")
    password = entry.data.get(CONF_PASSWORD, "")

    session = async_get_clientsession(hass)
    client = EasySmartClient(
        host=api_host,
        username=username,
        password=password,
        session=session,
        hass=hass
    )

    # 2. CARGA DE PERSISTÊNCIA (Crucial para não perder dados em reboots)
    # Carrega a fila do arquivo .storage/easy_smart_monitor1_queue.json
    await client.load_queue_from_disk()

    # 3. VALIDAÇÃO INICIAL (Opcional, não trava o boot)
    if not await client.authenticate():
        if not TEST_MODE:
            _LOGGER.warning("API inacessível no momento. A integração operará em modo offline/fila.")

    # 4. CONFIGURAÇÃO DO COORDENADOR DE SAÚDE (v1.0.10)
    update_interval = entry.options.get("update_interval", 60)
    coordinator = EasySmartCoordinator(hass, client, update_interval)

    # Realiza o primeiro refresh de dados
    # Isso garante que os sensores de diagnóstico iniciem com estados reais
    await coordinator.async_config_entry_first_refresh()

    # Armazena o coordenador para uso nas plataformas
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = coordinator

    # 5. LIMPEZA DE ENTIDADES ÓRFÃS
    # Remove sensores que foram deletados via menu 'Configurar'
    await async_cleanup_entities(hass, entry)

    # 6. REGISTRO DAS PLATAFORMAS
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    # Listener para mudanças nas opções (ex: mudar intervalo sem reiniciar)
    entry.async_on_unload(entry.add_update_listener(update_listener))

    return True

async def async_cleanup_entities(hass: HomeAssistant, entry: ConfigEntry):
    """Varre o registro e remove entidades que não constam mais no JSON de equipamentos."""
    entity_reg = er.async_get(hass)
    entities_in_registry = er.async_entries_for_config_entry(entity_reg, entry.entry_id)

    # Mapeia todos os unique_ids válidos (Telemetria + Diagnóstico v1.0.10)
    valid_unique_ids = []
    for equip in entry.data.get("equipments", []):
        # Unique IDs de Sensores e Binários
        for sensor in equip.get("sensors", []):
            valid_unique_ids.append(f"esm_{sensor['uuid']}")
            if sensor.get("tipo") == "sirene":
                valid_unique_ids.append(f"esm_siren_{sensor['uuid']}")

        # Unique IDs de Diagnóstico Automático
        valid_unique_ids.append(f"esm_diag_conexao_{equip['uuid']}")
        valid_unique_ids.append(f"esm_diag_sincro_{equip['uuid']}")

    # Remoção física do registro do HA
    for entity in entities_in_registry:
        if entity.unique_id not in valid_unique_ids:
            _LOGGER.info("Limpando entidade órfã: %s", entity.entity_id)
            entity_reg.async_remove(entity.entity_id)

async def update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Atualiza a integração quando o usuário altera as opções no botão Configurar."""
    _LOGGER.info("Opções atualizadas. Recarregando integração...")
    await hass.config_entries.async_reload(entry.entry_id)

async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Descarrega a integração com segurança."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)
        _LOGGER.debug("Integração descarregada com sucesso.")
    return unload_ok