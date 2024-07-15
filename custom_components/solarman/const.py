from datetime import timedelta as td

DOMAIN = "solarman"
PLATFORMS: list[str] = ["sensor"]
SENSOR_PREFIX = "Solarman"

IP_BROADCAST = "<broadcast>"
IP_ANY = "0.0.0.0"

PORT_ANY = 0

DISCOVERY_PORT = 48899
DISCOVERY_TIMEOUT = 1.0
DISCOVERY_MESSAGE = "WIFIKIT-214028-READ"
DISCOVERY_RECV_MESSAGE_SIZE = 1024

COMPONENTS_DIRECTORY = "custom_components"

LOOKUP_DIRECTORY = "inverter_definitions"
LOOKUP_DIRECTORY_PATH = f"{COMPONENTS_DIRECTORY}/{DOMAIN}/{LOOKUP_DIRECTORY}/"

CONF_INVERTER_DISCOVERY = "inverter_discovery"
CONF_INVERTER_HOST = "inverter_host"
CONF_INVERTER_PORT = "inverter_port"
CONF_INVERTER_SERIAL = "inverter_serial"
CONF_INVERTER_MB_SLAVE_ID = "inverter_mb_slave_id"
CONF_LOOKUP_FILE = "lookup_file"
CONF_BATTERY_NOMINAL_VOLTAGE = "battery_nominal_voltage"
CONF_BATTERY_LIFE_CYCLE_RATING = "battery_life_cycle_rating"

DEFAULT_NAME = "Inverter"
DEFAULT_DISCOVERY = True
DEFAULT_PORT_INVERTER = 8899
DEFAULT_INVERTER_MB_SLAVE_ID = 1
DEFAULT_LOOKUP_FILE = "deye_hybrid.yaml"
DEFAULT_BATTERY_NOMINAL_VOLTAGE = 48
DEFAULT_BATTERY_LIFE_CYCLE_RATING = 6000

ACTION_RETRY_ATTEMPTS = 5

TIMINGS_INTERVAL = 5
TIMINGS_COORDINATOR = td(seconds = TIMINGS_INTERVAL)
TIMINGS_COORDINATOR_TIMEOUT = TIMINGS_INTERVAL * 6
TIMINGS_SOCKET_TIMEOUT = TIMINGS_INTERVAL * 3 - 1
TIMINGS_QUERY_INTERVAL_DEFAULT = 60
TIMINGS_QUERY_EXCEPT_SLEEP = 2

REGISTERS_MIN_SPAN_DEFAULT = 25
REGISTERS_DIGITS_DEFAULT = 6

REQUEST_CODE = "code"
REQUEST_CODE_ALT = "mb_functioncode"
REQUEST_START = "start"
REQUEST_END = "end"

SERVICES_PARAM_REGISTER = "register"
SERVICES_PARAM_VALUE = "value"
SERVICES_PARAM_VALUES = "values"

SERVICE_WRITE_REGISTER = "write_holding_register"
SERVICE_WRITE_MULTIPLE_REGISTERS = "write_multiple_holding_registers"
