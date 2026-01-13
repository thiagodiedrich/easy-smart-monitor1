import logging
import asyncio
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import (
    DOMAIN,
    PLATFORMS,
    CONF_API_HOST,
    CONF_USERNAME,
    CONF_PASSWORD,
    CONF_EQUIPMENTS,
    TEST_MODE
)
from .client import EasySmartClient
from .coordinator import EasySmartCoordinator

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """
    Configura a integração Easy Smart Monitor v1.0.11.
    Gerencia a inicialização do cliente, persistência de fila e orquestração de plataformas.
    """
    _LOGGER.info("Inicializando Easy Smart Monitor v1.0.11 em %s", entry.data.get(CONF_API_HOST))

    # 1. Preparação da Sessão e Cliente
    session = async_get_clientsession(hass)

    try:
        client = EasySmartClient(
            host=entry.data.get(CONF_API_HOST),
            username=entry.data.get(CONF_USERNAME),
            password=entry.data.get(CONF_PASSWORD),
            session=session,
            hass=hass
        )

        # 2. Restauração de Dados Locais
        # Carrega a fila do disco antes de qualquer outra operação para garantir integridade
        await client.load_queue_from_disk()
        _LOGGER.debug("Persistência local carregada com sucesso para %s", entry.entry_id)

    except Exception as err:
        _LOGGER.error("Falha ao configurar o cliente de API: %s", err)
        raise ConfigEntryNotReady from err

    # 3. Configuração do Coordenador de Dados
    # O intervalo pode ser ajustado nas opções da integração
    update_interval = entry.options.get("update_interval", 60)
    coordinator = EasySmartCoordinator(hass, client, update_interval)

    # Tenta o primeiro refresh. Se falhar, não impede o boot (resiliência)
    try:
        await coordinator.async_config_entry_first_refresh()
    except Exception as err:
        _LOGGER.warning("Primeira atualização do coordenador falhou (API offline?), continuando boot: %s", err)

    # 4. Armazenamento Global
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = coordinator

    # 5. Manutenção do Registro de Entidades (Cleanup)
    # Remove entidades de equipamentos ou sensores que foram excluídos do JSON
    await async_cleanup_orphan_entities(hass, entry)

    # 6. Inicialização das Plataformas (Switch, Number, Sensor, Binary Sensor)
    # Segue a ordem definida em PLATFORMS no const.py
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    # 7. Listeners de Atualização
    # Permite mudar configurações (como intervalo) sem precisar reiniciar o HA
    entry.async_on_unload(entry.add_update_listener(async_reload_entry))

    _LOGGER.info("Easy Smart Monitor v1.0.11 configurado e operante.")
    return True

async def async_cleanup_orphan_entities(hass: HomeAssistant, entry: ConfigEntry):
    """
    Varre o Entity Registry do HA e remove entidades que não constam mais na configuração atual.
    Essencial para manter o sistema limpo após edições no Config Flow.
    """
    entity_reg = er.async_get(hass)
    entries_for_this_config = er.async_entries_for_config_entry(entity_reg, entry.entry_id)

    # Gera lista de IDs únicos que DEVEM existir
    valid_unique_ids = []
    equipments = entry.data.get(CONF_EQUIPMENTS, [])

    for equip in equipments:
        uuid = equip["uuid"]

        # IDs de Controle (v1.0.11)
        valid_unique_ids.append(f"esm_sw_ativo_{uuid}")
        valid_unique_ids.append(f"esm_sw_sirene_ativa_{uuid}")
        valid_unique_ids.append(f"esm_num_intervalo_coleta_{uuid}")
        valid_unique_ids.append(f"esm_num_tempo_porta_{uuid}")

        # IDs de Diagnóstico
        valid_unique_ids.append(f"esm_diag_conexao_{uuid}")
        valid_unique_ids.append(f"esm_diag_sincro_{uuid}")

        # IDs de Sensores e Telemetria
        for sensor in equip.get("sensors", []):
            s_uuid = sensor["uuid"]
            valid_unique_ids.append(f"esm_{s_uuid}")

            # Sensores binários derivados
            if sensor.get("tipo") == "porta":
                valid_unique_ids.append(f"esm_porta_{s_uuid}")
                valid_unique_ids.append(f"esm_sirene_{uuid}")

    # Processa a remoção
    for entity in entries_for_this_config:
        if entity.unique_id not in valid_unique_ids:
            _LOGGER.info("Removendo entidade órfã obsoleta: %s", entity.entity_id)
            entity_reg.async_remove(entity.entity_id)

async def async_reload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Recarrega a integração após mudanças nas opções (Options Flow)."""
    await hass.config_entries.async_reload(entry.entry_id)

async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """
    Descarrega a integração de forma limpa.
    Interrompe conexões ativas e remove o coordenador da memória.
    """
    _LOGGER.debug("Descarregando Easy Smart Monitor para o entry: %s", entry.entry_id)

    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)
        _LOGGER.info("Integração Easy Smart Monitor descarregada com sucesso.")

    return unload_ok