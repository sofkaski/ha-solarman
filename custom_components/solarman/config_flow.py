from __future__ import annotations

import logging
import voluptuous as vol

from voluptuous.schema_builder import Schema
from socket import getaddrinfo, herror, gaierror, timeout
from typing import Any

from homeassistant.const import CONF_NAME
from homeassistant.core import HomeAssistant, callback
from homeassistant.config_entries import ConfigFlow, ConfigFlowResult, OptionsFlow
from homeassistant.helpers.device_registry import format_mac
from homeassistant.helpers import config_validation as cv
from homeassistant.components.dhcp import DhcpServiceInfo
from homeassistant.exceptions import HomeAssistantError

from .const import *
from .discovery import InverterDiscovery

_LOGGER = logging.getLogger(__name__)

async def async_update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    _LOGGER.debug(f"async_update_listener: entry: {entry.as_dict()}")
    hass.data[DOMAIN][entry.entry_id].config(entry)
    entry.title = entry.options[CONF_NAME]

async def step_user_data_process(discovery):
    _LOGGER.debug(f"step_user_data_process: discovery: {discovery}")
    return { CONF_NAME: DEFAULT_NAME, CONF_INVERTER_DISCOVERY: DEFAULT_DISCOVERY, CONF_INVERTER_HOST: await discovery.get_ip(), CONF_INVERTER_SERIAL: await discovery.get_serial(), CONF_INVERTER_PORT: DEFAULT_PORT_INVERTER, CONF_INVERTER_MB_SLAVE_ID: DEFAULT_INVERTER_MB_SLAVE_ID, CONF_LOOKUP_FILE: DEFAULT_LOOKUP_FILE, CONF_BATTERY_NOMINAL_VOLTAGE: DEFAULT_BATTERY_NOMINAL_VOLTAGE, CONF_BATTERY_LIFE_CYCLE_RATING: DEFAULT_BATTERY_LIFE_CYCLE_RATING, CONF_DISABLE_TEMPLATING: DEFAULT_DISABLE_TEMPLATING }

def step_user_data_schema(data: dict[str, Any] = { CONF_NAME: DEFAULT_NAME, CONF_INVERTER_DISCOVERY: DEFAULT_DISCOVERY, CONF_INVERTER_PORT: DEFAULT_PORT_INVERTER, CONF_INVERTER_MB_SLAVE_ID: DEFAULT_INVERTER_MB_SLAVE_ID, CONF_LOOKUP_FILE: DEFAULT_LOOKUP_FILE, CONF_BATTERY_NOMINAL_VOLTAGE: DEFAULT_BATTERY_NOMINAL_VOLTAGE, CONF_BATTERY_LIFE_CYCLE_RATING: DEFAULT_BATTERY_LIFE_CYCLE_RATING, CONF_DISABLE_TEMPLATING: DEFAULT_DISABLE_TEMPLATING }) -> Schema:
    _LOGGER.debug(f"step_user_data_schema: data: {data}")
    STEP_USER_DATA_SCHEMA = vol.Schema(
        {
            vol.Required(CONF_NAME, default = data.get(CONF_NAME)): str,
            vol.Required(CONF_INVERTER_DISCOVERY, default = data.get(CONF_INVERTER_DISCOVERY)): bool,
            vol.Required(CONF_INVERTER_HOST, default = data.get(CONF_INVERTER_HOST)): str,
            vol.Required(CONF_INVERTER_SERIAL, default = data.get(CONF_INVERTER_SERIAL)): int,
            vol.Optional(CONF_INVERTER_PORT, default = data.get(CONF_INVERTER_PORT)): int,
            vol.Optional(CONF_INVERTER_MB_SLAVE_ID, default = data.get(CONF_INVERTER_MB_SLAVE_ID)): int,
            vol.Optional(CONF_LOOKUP_FILE, default = data.get(CONF_LOOKUP_FILE)): vol.In(LOOKUP_FILES),
            vol.Optional(CONF_BATTERY_NOMINAL_VOLTAGE, default = data.get(CONF_BATTERY_NOMINAL_VOLTAGE)): int,
            vol.Optional(CONF_BATTERY_LIFE_CYCLE_RATING, default = data.get(CONF_BATTERY_LIFE_CYCLE_RATING)): int,
            vol.Optional(CONF_DISABLE_TEMPLATING, default = data.get(CONF_DISABLE_TEMPLATING)): bool,
        },
        extra = vol.PREVENT_EXTRA
    )
    _LOGGER.debug(f"step_user_data_schema: STEP_USER_DATA_SCHEMA: {STEP_USER_DATA_SCHEMA}")

    return STEP_USER_DATA_SCHEMA

async def validate_input(hass: HomeAssistant, data: dict[str, Any]) -> dict[str, Any]:
    """
    Validate the user input allows us to connect.

    Data has the keys from STEP_USER_DATA_SCHEMA with values provided by the user.
    """
    _LOGGER.debug(f"validate_input: {data}")

    try:
        getaddrinfo(data[CONF_INVERTER_HOST], data[CONF_INVERTER_PORT], family = 0, type = 0, proto = 0, flags = 0)
    except herror:
        raise InvalidHost
    except gaierror:
        raise CannotConnect
    except timeout:
        raise CannotConnect

    return {"title": data[CONF_NAME]}

class ConfigFlowHandler(ConfigFlow, domain = DOMAIN):
    """Handle a solarman stick logger config flow."""
    VERSION = 1

    async def async_step_dhcp(self, discovery_info: DhcpServiceInfo) -> ConfigFlowResult:
        """Handle a flow initiated by the DHCP client."""
        _LOGGER.debug(f"ConfigFlowHandler.async_step_dhcp: {discovery_info}")
        #await self.async_set_unique_id(format_mac(discovery_info.macaddress))
        discovery_input = { CONF_NAME: DEFAULT_NAME,
            CONF_INVERTER_HOST: discovery_info.ip,
            CONF_INVERTER_PORT: DEFAULT_PORT_INVERTER }
        self._async_abort_entries_match(discovery_input)
        return await self.async_step_user(user_input = discovery_input)

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Handle the initial step."""
        _LOGGER.debug(f"ConfigFlowHandler.async_step_user: {user_input}")
        if user_input is None:
            discovery_options = await step_user_data_process(InverterDiscovery(self.hass))
            return self.async_show_form(step_id = "user", data_schema = step_user_data_schema(discovery_options))

        errors = {}

        try:
            info = await validate_input(self.hass, user_input)
        except InvalidHost:
            errors["base"] = "invalid_host"
        except CannotConnect:
            errors["base"] = "cannot_connect"
        except Exception:
            _LOGGER.exception("Unexpected exception")
            errors["base"] = "unknown"
        else:
            _LOGGER.debug(f"ConfigFlowHandler.async_step_user: validation passed: {user_input}")
            # not sure this is permitted as the user can change the device_id
            # await self.async_set_unique_id(user_input.device_id) 
            # self._abort_if_unique_id_configured()
            return self.async_create_entry(title = info["title"], data = user_input, options = user_input)

        _LOGGER.debug(f"ConfigFlowHandler.async_step_user: validation failed: {user_input}")

        return self.async_show_form(step_id = "user", data_schema = step_user_data_schema(user_input), errors = errors)

    @staticmethod
    @callback
    def async_get_options_flow(entry: ConfigEntry) -> OptionsFlowHandler:
        """Get the options flow for this handler."""
        _LOGGER.debug(f"ConfigFlowHandler.async_get_options_flow: {entry}")
        return OptionsFlowHandler(entry)

class OptionsFlowHandler(OptionsFlow):
    """Handle a solarman stick logger options flow."""

    def __init__(self, entry: ConfigEntry) -> None:
        """Initialize options flow."""
        _LOGGER.debug(f"OptionsFlowHandler.__init__: {entry}")
        self.entry = entry

    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Handle options flow."""
        _LOGGER.debug(f"OptionsFlowHandler.async_step_init: {user_input}")
        if user_input is None:
            return self.async_show_form(step_id = "init", data_schema = step_user_data_schema(self.entry.options))

        errors = {}

        try:
            info = await validate_input(self.hass, user_input)
        except InvalidHost:
            errors["base"] = "invalid_host"
        except CannotConnect:
            errors["base"] = "cannot_connect"
        except Exception: # pylint: disable=broad-except
            _LOGGER.exception("Unexpected exception")
            errors["base"] = "unknown"
        else:
            return self.async_create_entry(title = info["title"], data = user_input)

        return self.async_show_form(step_id = "init", data_schema = step_user_data_schema(user_input), errors = errors)

class InvalidHost(HomeAssistantError):
    """Error to indicate there is invalid hostname or IP address."""

class CannotConnect(HomeAssistantError):
    """Error to indicate we cannot connect."""