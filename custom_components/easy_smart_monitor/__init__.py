"""
Inicialização da integração Easy Smart Monitor.
Gerencia a configuração, migração de dados e ciclo de vida das plataformas.
"""
import logging
import asyncio
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.const import CONF_HOST, CONF_USERNAME, CONF_PASSWORD
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import (
    DOMAIN,
    CONF_API_HOST,
    CONF_USERNAME as CONF_USER_KEY,
    CONF_PASSWORD as CONF_PASS_KEY,
    CONF_UPDATE_INTERVAL,
    CONF_EQUIPMENTS,
    DEFAULT_UPDATE_INTERVAL,
    PLATFORMS,
    TEST_MODE,
    MANUFACTURER,
    VERSION
)
from .client import EasySmartClient
from .coordinator import EasySmartCoordinator

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """
    Configura a integração a partir de uma entrada de configuração.
    Esta função é chamada na inicialização do HA ou quando o usuário recarrega a integração.
    """
    hass.data.setdefault(DOMAIN, {})

    _LOGGER.debug("Iniciando setup da entrada: %s (v%s)", entry.title, VERSION)

    # -------------------------------------------------------------------------
    # 1. Recuperação Robusta de Credenciais (Mantido)
    # -------------------------------------------------------------------------
    api_host = entry.data.get(CONF_API_HOST)
    username = entry.data.get(CONF_USER_KEY)
    password = entry.data.get(CONF_PASS_KEY)

    # Fallback: Se não encontrar, tenta chaves antigas ou genéricas
    if not api_host:
        api_host = (
                entry.data.get("host") or
                entry.data.get("api_url") or
                entry.data.get("server")
        )

    if not username:
        username = entry.data.get("user") or entry.data.get(CONF_USERNAME)

    if not password:
        password = entry.data.get("pass") or entry.data.get(CONF_PASSWORD)

    # -------------------------------------------------------------------------
    # 2. Validação Crítica
    # -------------------------------------------------------------------------
    if not api_host:
        _LOGGER.error(
            "CRÍTICO: Host da API não encontrado. Dados disponíveis: %s",
            entry.data.keys()
        )
        return False

    api_host = str(api_host).rstrip("/")

    # -------------------------------------------------------------------------
    # 3. Inicialização do Cliente API
    # -------------------------------------------------------------------------
    session = async_get_clientsession(hass)

    if TEST_MODE and (not username or not password):
        _LOGGER.warning("Modo Teste: Usando credenciais padrão.")
        username = username or "admin_teste"
        password = password or "senha_teste"

    client = EasySmartClient(api_host, username, password, session, hass)
    
    # Carrega a fila persistida no disco ANTES de iniciar o coordinator
    await client.load_queue_from_disk()

    # -------------------------------------------------------------------------
    # 4. Inicialização do Coordinator
    # -------------------------------------------------------------------------
    # Prioridade 1: Dados da entrada (Config salva no HA)
    # Prioridade 2: Padrão do sistema (const.py)
    # Trava de segurança: Mínimo de 60 segundos para não prejudicar o desempenho do Home Assistant e da API Cloud
    raw_interval = entry.data.get(CONF_UPDATE_INTERVAL, DEFAULT_UPDATE_INTERVAL)
    update_interval = max(int(raw_interval), 60)

    _LOGGER.info(
        "Iniciando Easy Smart Monitor [%s]. Intervalo de Envio Cloud: %s segundos.", 
        entry.title, 
        update_interval
    )

    coordinator = EasySmartCoordinator(hass, client, int(update_interval))

    # Primeira sincronização
    try:
        await coordinator.async_config_entry_first_refresh()
    except Exception as e:
        _LOGGER.warning("Falha na primeira sincronização (API Offline?): %s", e)

    hass.data[DOMAIN][entry.entry_id] = coordinator

    # -------------------------------------------------------------------------
    # 5. REGISTRO EXPLÍCITO DE DISPOSITIVOS (Força Criação Visual)
    # -------------------------------------------------------------------------
    dev_registry = dr.async_get(hass)

    # Agora podemos confiar em entry.data, pois o config_flow usa deepcopy+update_entry
    equipments = entry.data.get(CONF_EQUIPMENTS, [])

    if equipments:
        _LOGGER.debug("Processando %s equipamentos para registro.", len(equipments))
        for equip in equipments:
            try:
                dev_registry.async_get_or_create(
                    config_entry_id=entry.entry_id,
                    identifiers={(DOMAIN, str(equip["uuid"]))},
                    name=equip["nome"],
                    manufacturer=MANUFACTURER,
                    model=f"Monitor Industrial v{VERSION}",
                    suggested_area=equip.get("local"),
                    configuration_url=api_host
                )
            except Exception as e:
                _LOGGER.error("Erro ao registrar dispositivo %s: %s", equip.get("nome"), e)
    else:
        _LOGGER.debug("Nenhum equipamento encontrado na configuração.")

    # -------------------------------------------------------------------------
    # 6. Carregamento das Plataformas
    # -------------------------------------------------------------------------
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    # -------------------------------------------------------------------------
    # 7. Listener de Atualização
    # -------------------------------------------------------------------------
    entry.async_on_unload(entry.add_update_listener(async_update_options))

    _LOGGER.info("Easy Smart Monitor iniciado com sucesso.")
    return True

async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Descarrega a integração."""
    coordinator = hass.data[DOMAIN].get(entry.entry_id)
    if coordinator:
        # Para o timer robusto de sincronização
        if hasattr(coordinator, 'shutdown'):
            coordinator.shutdown()
            
        if hasattr(coordinator, 'client'):
            # Garante que qualquer dado na fila seja persistido antes de descarregar
            coordinator.client._save_queue_to_disk()

    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)
    return unload_ok

async def async_update_options(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Gerencia atualizações de opções em tempo de execução."""
    # Como agora salvamos tudo em entry.data e chamamos async_reload manualmente
    # no config_flow, este listener pode apenas forçar o reload se algo vier via options
    # ou ser mantido para compatibilidade.
    await hass.config_entries.async_reload(entry.entry_id)