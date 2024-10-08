import time
import errno
import struct
import socket
import logging
import asyncio
import threading
import concurrent.futures

from datetime import datetime

from pysolarmanv5 import PySolarmanV5Async, V5FrameError
from umodbus.client.tcp import read_coils, read_discrete_inputs, read_holding_registers, read_input_registers, write_single_coil, write_multiple_coils, write_single_register, write_multiple_registers, parse_response_adu

from homeassistant.helpers.device_registry import CONNECTION_NETWORK_MAC, DeviceInfo, format_mac
from homeassistant.helpers.update_coordinator import UpdateFailed

from .const import *
from .common import *
from .parser import ParameterParser

_LOGGER = logging.getLogger(__name__)

class PySolarmanV5AsyncWrapper(PySolarmanV5Async):
    sm_start = bytes.fromhex("AA")
    sm_passthrough = False

    def __init__(self, address, serial, port, mb_slave_id):
        super().__init__(address, serial, port = port, mb_slave_id = mb_slave_id, logger = _LOGGER, auto_reconnect = AUTO_RECONNECT, socket_timeout = TIMINGS_SOCKET_TIMEOUT)

    async def _tcp_parse_response_adu(self, mb_request_frame):
        return parse_response_adu(await self._send_receive_v5_frame(mb_request_frame), mb_request_frame)

    def _received_frame_is_valid(self, frame):
        if self.sm_passthrough:
            return True
        if not frame.startswith(self.v5_start):
            self.log.debug("[%s] V5_MISMATCH: %s", self.serial, frame.hex(" "))
            return False
        if frame[5] != self.sequence_number and is_ethernet_frame(frame):
            self.log.debug("[%s] V5_ETHERNET_DETECTED: %s", self.serial, frame.hex(" "))
            self.sm_passthrough = True
            return False
        if frame[5] != self.sequence_number:
            self.log.debug("[%s] V5_SEQ_NO_MISMATCH: %s", self.serial, frame.hex(" "))
            return False
        if frame.startswith(self.v5_start + b"\x01\x00\x10\x47"):
            self.log.debug("[%s] COUNTER: %s", self.serial, frame.hex(" "))
            return False
        return True

    async def connect(self) -> None:
        if not self.reader_task:
            _LOGGER.info(f"[{self.serial}] Connecting to {self.address}:{self.port}")
            await super().connect()
        # ! Gonna have to rewrite the state handling in the future as it's now after all the development and tunning mess AF !
        #elif not self.state > 0:
        #    await super().reconnect()

    async def disconnect(self) -> None:
        _LOGGER.info(f"[{self.serial}] Disconnecting from {self.address}:{self.port}")

        try:
            await super().disconnect()
        finally:
            self.reader_task = None
            self.reader = None
            self.writer = None

    async def read_coils(self, register_addr, quantity):
        if not self.sm_passthrough:
            return await super().read_coils(register_addr, quantity)
        return await self._tcp_parse_response_adu(read_coils(self.mb_slave_id, register_addr, quantity))

    async def read_discrete_inputs(self, register_addr, quantity):
        if not self.sm_passthrough:
            return await super().read_discrete_inputs(register_addr, quantity)
        return await self._tcp_parse_response_adu(read_discrete_inputs(self.mb_slave_id, register_addr, quantity))

    async def read_input_registers(self, register_addr, quantity):
        if not self.sm_passthrough:
            return await super().read_input_registers(register_addr, quantity)
        return await self._tcp_parse_response_adu(read_input_registers(self.mb_slave_id, register_addr, quantity))

    async def read_holding_registers(self, register_addr, quantity):
        if not self.sm_passthrough:
            return await super().read_holding_registers(register_addr, quantity)
        return await self._tcp_parse_response_adu(read_holding_registers(self.mb_slave_id, register_addr, quantity))

    async def write_single_coil(self, register_addr, value):
        if not self.sm_passthrough:
            return await super().write_single_coil(register_addr, value)
        return await self._tcp_parse_response_adu(write_single_coil(self.mb_slave_id, register_addr, value))

    async def write_multiple_coils(self, register_addr, values):
        if not self.sm_passthrough:
            return await super().write_multiple_coils(register_addr, values)
        return await self._tcp_parse_response_adu(write_multiple_coils(self.mb_slave_id, register_addr, values))

    async def write_holding_register(self, register_addr, value):
        if not self.sm_passthrough:
            return await super().write_holding_register(register_addr, value)
        return await self._tcp_parse_response_adu(write_single_register(self.mb_slave_id, register_addr, value))

    async def write_multiple_holding_registers(self, register_addr, values):
        if not self.sm_passthrough:
            return await super().write_multiple_holding_registers(register_addr, values)
        return await self._tcp_parse_response_adu(write_multiple_registers(self.mb_slave_id, register_addr, values))

class Inverter(PySolarmanV5AsyncWrapper):
    def __init__(self, address, serial, port, mb_slave_id):
        super().__init__(address, serial, port, mb_slave_id)
        self._is_busy = 0
        self.state_updated = datetime.now()
        self.state_interval = 0
        self.state = -1
        self.auto_reconnect = AUTO_RECONNECT
        self.manufacturer = "Solarman"
        self.model = None
        self.parameter_definition = None
        self.device_info = {}

    async def load(self, name, mac, path, file):
        self.name = name
        self.mac = mac
        self.lookup_path = path
        self.lookup_file = process_profile(file if file else "deye_hybrid.yaml")
        self.model = self.lookup_file.replace(".yaml", "")
        self.parameter_definition = await yaml_open(self.lookup_path + self.lookup_file)
        self.profile = ParameterParser(self.parameter_definition)

        if "info" in self.parameter_definition and "model" in self.parameter_definition["info"]:
            info = self.parameter_definition["info"]
            if "manufacturer" in info:
                self.manufacturer = info["manufacturer"]
            if "model" in info:
                self.model = info["model"]
        elif '_' in self.model:
            dev_man = self.model.split('_')
            self.manufacturer = dev_man[0].capitalize()
            self.model = dev_man[1].upper()
        else:
            self.manufacturer = "Solarman"
            self.model = "Stick Logger"

        self.device_info = ({ "connections": {(CONNECTION_NETWORK_MAC, format_mac(self.mac))} } if self.mac else {}) | {
            "identifiers": {(DOMAIN, self.serial)},
            "name": self.name,
            "manufacturer": self.manufacturer,
            "model": self.model,
            "serial_number": self.serial
        }

        _LOGGER.debug(self.device_info)

    def get_sensors(self):
        return self.profile.get_sensors() if self.parameter_definition else []

    def available(self):
        return self.state > -1

    def get_connection_state(self):
        if self.state > 0:
            return "Connected"
        return "Disconnected"

    async def shutdown(self) -> None:
        self.state = -1
        await self.disconnect()

    async def read_write(self, code, start, arg):
        await self.connect()

        match code:
            case CODE.READ_COILS:
                return await self.read_coils(start, arg)
            case CODE.READ_DISCRETE_INPUTS:
                return await self.read_discrete_inputs(start, arg)
            case CODE.READ_HOLDING_REGISTERS:
                return await self.read_holding_registers(start, arg)
            case CODE.READ_INPUT:
                return await self.read_input_registers(start, arg)
            case CODE.WRITE_SINGLE_COIL:
                return await self.write_single_coil(start, arg)
            case CODE.WRITE_HOLDING_REGISTER:
                return await self.write_holding_register(start, arg)
            case CODE.WRITE_MULTIPLE_COILS:
                return await self.write_multiple_coils(start, arg)
            case CODE.WRITE_MULTIPLE_HOLDING_REGISTERS:
                return await self.write_multiple_holding_registers(start, arg)
            case _:
                raise Exception(f"[{self.serial}] Used incorrect modbus function code {code}")

    async def wait_for_done(self, attempts_left = ACTION_ATTEMPTS):
        while self._is_busy == 1 and attempts_left > 0:
            attempts_left -= 1
            await asyncio.sleep(TIMINGS_WAIT_FOR_SLEEP)
        return self._is_busy == 1

    def get_result(self, middleware = None):
        result = middleware.get_result() if middleware else {}
        result_count = len(result) if result else 0

        if result_count > 0:
            _LOGGER.debug(f"[{self.serial}] Returning {result_count} new values to the Coordinator. [Previous State: {self.get_connection_state()} ({self.state})]")
            now = datetime.now()
            self.state_interval = now - self.state_updated
            self.state_updated = now
            self.state = 1

        return result

    async def get_failed(self, message = None):
        _LOGGER.debug(f"[{self.serial}] Request failed. [Previous State: {self.get_connection_state()} ({self.state})]")
        self.state = 0 if self.state == 1 else -1

        await self.disconnect()

        if message and self.state == -1:
            raise UpdateFailed(message)

    async def get(self, runtime = 0):
        requests = self.profile.get_requests(runtime)
        requests_count = len(requests) if requests else 0
        results = [0] * requests_count

        _LOGGER.debug(f"[{self.serial}] Scheduling {requests_count} query request{'' if requests_count == 1 else 's'}. #{runtime}")

        if await self.wait_for_done(ACTION_ATTEMPTS):
            _LOGGER.debug(f"[{self.serial}] get: Timeout.")
            raise TimeoutError(f"[{self.serial}] Currently writing data to the device!")

        self._is_busy = 1

        try:
            async with asyncio.timeout(TIMINGS_UPDATE_TIMEOUT):
                for i, request in enumerate(requests):
                    code = get_request_code(request)
                    start = get_request_start(request)
                    end = get_request_end(request)
                    quantity = end - start + 1

                    start_end = f"{start:04} - {end:04} | 0x{start:04X} - 0x{end:04X} # {quantity:03}"
                    _LOGGER.debug(f"[{self.serial}] Querying {start_end} ...")

                    attempts_left = ACTION_ATTEMPTS
                    while attempts_left > 0 and results[i] == 0:
                        attempts_left -= 1

                        try:
                            self.profile.parse(await self.read_write(code, start, quantity), start, quantity)
                            results[i] = 1
                        except (V5FrameError, TimeoutError, Exception) as e:
                            results[i] = 0

                            #if ((not isinstance(e, TimeoutError) or not attempts_left >= 1) and not (not isinstance(e, TimeoutError) or (e.__cause__ and isinstance(e.__cause__, OSError) and e.__cause__.errno == errno.EHOSTUNREACH))) or _LOGGER.isEnabledFor(logging.DEBUG):
                            #    _LOGGER.warning(f"[{self.serial}] Querying {start_end} failed. #{runtime} [{format_exception(e)}]")
                            _LOGGER.debug(f"[{self.serial}] Querying {start_end} failed. [{format_exception(e)}]")

                            if not self.auto_reconnect:
                                await self.disconnect()

                            if not attempts_left > 0:
                                raise

                            await asyncio.sleep((ACTION_ATTEMPTS - attempts_left) * TIMINGS_WAIT_SLEEP)

                        _LOGGER.debug(f"[{self.serial}] Querying {start_end} {'succeeded.' if results[i] == 1 else f'attempts left: {attempts_left}{'' if attempts_left > 0 else ', aborting.'}'}")

                    if results[i] == 0:
                        break

                if not 0 in results:
                    return self.get_result(self.profile)
                else:
                    await self.get_failed(f"[{self.serial}] Querying {self.address}:{self.port} failed: {results}")

        except TimeoutError:
            last_state = self.state
            await self.get_failed()
            if last_state < 1:
                raise
            else:
                _LOGGER.debug(f"[{self.serial}] Timeout fetching {self.name} data")
        except UpdateFailed:
            raise
        except Exception as e:
            #await self.get_failed(f"[{self.serial}] Querying {self.address}:{self.port} failed: {results} with exception: {format_exception(e)}.")
            await self.get_failed(f"[{self.serial}] {format_exception(e)}: {results}")
        finally:
            self._is_busy = 0

        return self.get_result()

    async def call(self, code, start, arg, wait_for_attempts = ACTION_ATTEMPTS) -> bool:
        _LOGGER.debug(f"[{self.serial}] call code {code}: {start} | 0x{start:04X}, arg: {arg}, wait_for_attempts: {wait_for_attempts}")

        if await self.wait_for_done(wait_for_attempts):
            _LOGGER.debug(f"[{self.serial}] call code {code}: Timeout.")
            raise TimeoutError(f"[{self.serial}] Coordinator is currently reading data from the device!")

        self._is_busy = 1

        try:
            attempts_left = ACTION_ATTEMPTS
            while attempts_left > 0:
                attempts_left -= 1

                try:
                    response = await self.read_write(code, start, arg)
                    _LOGGER.debug(f"[{self.serial}] call code {code}: {start} | 0x{start:04X}, response: {response}")
                    return response
                except Exception as e:
                    _LOGGER.debug(f"[{self.serial}] call code {code}: {start} | 0x{start:04X}, arg: {arg} failed, attempts left: {attempts_left}. [{format_exception(e)}]")

                    if not self.auto_reconnect:
                        await self.disconnect()

                    if not attempts_left > 0:
                        raise

                    await asyncio.sleep(TIMINGS_WAIT_SLEEP)
        except:
            raise
        finally:
            self._is_busy = 0
