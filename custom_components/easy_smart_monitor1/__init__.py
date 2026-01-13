import logging
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import DOMAIN, CONF_API_HOST, CONF_USERNAME, CONF_PASSWORD
from .client import EasySmartClient
from .coordinator import EasySmartCoordinator

_LOGGER = logging.getLogger(__name__)

# Definimos as plataformas que serão carregadas (sensor.py lida com todas as lógicas)
PLATFORMS: list[Platform] = [Platform.SENSOR, Platform.BINARY_SENSOR]

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Configura a integração Easy Smart Monitor a partir de uma entrada de configuração."""

    # 1. Preparar a sessão HTTP e o Cliente de API
    session = async_get_clientsession(hass)

    client = EasySmartClient(
        host=entry.data[CONF_API_HOST],
        username=entry.data[CONF_USERNAME],
        password=entry.data[CONF_PASSWORD],
        session=session,
        hass=hass
    )

    # 2. Carregar a fila persistente do disco (.storage)
    # Isso garante que dados de sessões anteriores não sejam perdidos no boot
    await client.load_queue_from_disk()

    # 3. Autenticação Inicial
    # Se falhar aqui, o HA marcará a integração como "Setup failed"
    if not await client.authenticate():
        _LOGGER.error("Falha ao autenticar na API Easy Smart durante o setup")
        # Não retornamos False aqui para permitir que o usuário corrija as credenciais
        # mas notificamos o erro.

    # 4. Configurar o Coordenador de Dados
    # O intervalo de atualização pode ser ajustado via Opções na interface
    update_interval = entry.options.get("update_interval", 30)

    coordinator = EasySmartCoordinator(
        hass,
        client,
        update_interval
    )

    # 5. Primeiro Refresh
    # Tenta carregar os dados iniciais antes de finalizar o setup
    await coordinator.async_config_entry_first_refresh()

    # 6. Armazenar o coordenador para uso pelas plataformas (sensor.py)
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = coordinator

    # 7. Registrar as plataformas
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    # Adicionar listener para atualizações nas opções (ex: mudar tempo de sincronização)
    entry.async_on_unload(entry.add_update_listener(update_listener))

    return True

async def update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Atualiza a integração quando as opções são alteradas na UI."""
    await hass.config_entries.async_reload(entry.entry_id)

async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Descarrega a integração e limpa os recursos."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok