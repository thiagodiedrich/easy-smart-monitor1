"""Inicialização da integração Easy Smart Monitor."""
import logging
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
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

# Lista de plataformas suportadas. 
# O sensor.py gerencia as medições e o binary_sensor.py gerencia a sirene.
PLATFORMS: list[Platform] = [Platform.SENSOR, Platform.BINARY_SENSOR]

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Configura o Easy Smart Monitor a partir de uma entrada de configuração (ConfigEntry)."""
    
    _LOGGER.debug("Iniciando setup da integração %s para o usuário %s", DOMAIN, entry.data.get(CONF_USERNAME))

    # 1. Cria a sessão HTTP vinculada ao Home Assistant
    session = async_get_clientsession(hass)
    
    # 2. Instancia o Cliente de API (Coração da comunicação e fila)
    client = EasySmartClient(
        host=entry.data[CONF_API_HOST],
        username=entry.data[CONF_USERNAME],
        password=entry.data[CONF_PASSWORD],
        session=session,
        hass=hass
    )

    # 3. Carrega a fila persistente do disco (.storage/easy_smart_monitor1_storage)
    # Isso impede a perda de dados se o HA for reiniciado com a API offline.
    await client.load_queue_from_disk()

    # 4. Tenta a autenticação inicial no servidor
    # Em TEST_MODE (no const.py), o client sempre simulará sucesso.
    if not await client.authenticate():
        if not TEST_MODE:
            _LOGGER.warning("Falha inicial na autenticação com a API. A integração tentará novamente em segundo plano.")
        else:
            _LOGGER.info("[TEST MODE] Autenticação simulada ativada.")

    # 5. Configura o DataUpdateCoordinator
    # O intervalo de atualização vem das opções (configuráveis na UI) ou padrão de 60s
    update_interval = entry.options.get("update_interval", 60)

    coordinator = EasySmartCoordinator(
        hass,
        client,
        update_interval
    )

    # 6. Executa a primeira atualização de dados para popular as entidades
    # O timeout garante que o HA não trave se a rede estiver lenta
    await coordinator.async_config_entry_first_refresh()

    # 7. Armazena o coordenador no objeto global hass.data para acesso pelas plataformas
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = coordinator

    # 8. Encaminha o setup para as plataformas (sensor.py e binary_sensor.py)
    # Isso ativa as entidades físicas no sistema.
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    # 9. Registra o listener para atualizações nas opções (Ex: mudar o tempo de sync)
    entry.async_on_unload(entry.add_update_listener(update_listener))

    _LOGGER.info("Configuração da integração %s concluída com sucesso.", DOMAIN)
    return True

async def update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Atualiza a entrada de configuração quando as opções são alteradas pelo usuário."""
    _LOGGER.debug("Opções atualizadas detectadas, recarregando a integração.")
    await hass.config_entries.async_reload(entry.entry_id)

async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Descarrega a integração e remove os recursos da memória de forma limpa."""
    _LOGGER.debug("Descarregando a integração %s", DOMAIN)

    # Descarrega as plataformas (Sensores e Sirenes)
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

    # Limpa os dados do coordenador da memória se o descarregamento das plataformas foi OK
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)
        _LOGGER.info("Integração %s descarregada com sucesso.", DOMAIN)

    return unload_ok