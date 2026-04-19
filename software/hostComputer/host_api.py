"""
pynq_controller.py
------------------
Host-side controller for communicating with a PYNQ FPGA board over TCP sockets.
Uses a fixed-width binary protocol to minimise processing on the PYNQ side.

Usage:
    controller = PYNQController(server_ip="192.168.1.100", server_port=5000)
    controller.connect()
    controller.create_laser(laser_id=1)
    controller.lock_laser(laser_id=1, pid_param1=1550)
    controller.start_cavity(duration=10)
    controller.disconnect()

    # Or as a context manager:
    with PYNQController(server_ip="192.168.1.100", server_port=5000) as ctrl:
        ctrl.create_laser(laser_id=1)
        ctrl.lock_laser(laser_id=1, pid_param1=1550)

Test plan for feedback-loop validation:
    1. Controller sends create/lock/start commands.
    2. Server receives packets and dispatches to PYNQControls.
    3. PYNQControls updates MMIO and local state.
    4. Server reads back laser state / flags from PYNQControls.
    5. Controller verifies ACKs and the server-side readback snapshot.

---------------------------------------------------------------------------
Binary packet format  (18 bytes, big-endian / network byte order)
---------------------------------------------------------------------------

 Offset  Size  Type     Field           Description
 ------  ----  -------  -------------   ------------------------------------
     0      1    uint8    cmd_id          Command identifier (see _CMD_ID)
    1      1    uint8    laser_and_flags [7:4]=laser_id, [2]=laser_locked, [1]=system_on, [0]=laser_configured
     2      4    uint32   pid_param1      PID parameter 1
     6      4    uint32   pid_param2      PID parameter 2
    10      4    uint32   pid_param3      PID parameter 3
    14      4    uint32   duration        Duration field
 ------
    18 bytes total

PYNQ-side (Python):
        CMD_ID, LASER_FLAGS, P1, P2, P3, DURATION = struct.unpack('!BBIIII', data)

Status nibble layout (low nibble):
    bit3: 0 (reserved)
    bit2: laser_locked_flag
    bit1: system_on_flag
    bit0: laser_configured_flag

---------------------------------------------------------------------------
Response format  (8-byte header + optional payload)
---------------------------------------------------------------------------
 Offset  Size  Type     Field
 ------  ----  -------  ----------------
         0      1    uint8    response_version
         1      1    uint8    response_id (echo of cmd_id)
         2      1    uint8    status (0x00=ok, 0x01=error)
         3      1    uint8    reserved
         4      4    uint32   payload_length
        8..N  var    bytes    payload
"""

import logging
import socket
import struct
import time
import argparse
import shlex
from pathlib import Path
from datetime import datetime, timedelta
from enum import Enum
from typing import Optional


# ---------------------------------------------------------------------------
# Packet constants
# ---------------------------------------------------------------------------

PACKET_FORMAT = "!BBIIII"        # uint8, uint8, uint32, uint32, uint32, uint32
PACKET_SIZE   = struct.calcsize(PACKET_FORMAT)   # 18 bytes

ACK_OK    = 0x00
ACK_ERROR = 0x01

RESPONSE_FORMAT = "!BBBBI"
RESPONSE_SIZE = struct.calcsize(RESPONSE_FORMAT)
RESPONSE_VERSION = 0x01
MAX_RESPONSE_PAYLOAD = 8 * 1024 * 1024  # 8 MiB guardrail

_NIBBLE_MAX = 0x0F
_UINT32_MAX = 0xFFFFFFFF


def _validate_nibble(name: str, value: int) -> int:
    v = int(value)
    if v < 0 or v > _NIBBLE_MAX:
        raise ValueError(f"{name} must be in range [0, 15], got {value}.")
    return v


def _validate_uint32(name: str, value: int) -> int:
    v = int(value)
    if v < 0 or v > _UINT32_MAX:
        raise ValueError(f"{name} must be in range [0, 4294967295], got {value}.")
    return v


def _pack_laser_and_flags(
    laser_id: int,
    laser_locked_flag: bool,
    system_on_flag: bool,
    laser_configured_flag: bool,
) -> int:
    lid = _validate_nibble("laser_id", laser_id)
    status_nibble = (
        ((1 if laser_locked_flag else 0) << 2)
        | ((1 if system_on_flag else 0) << 1)
        | (1 if laser_configured_flag else 0)
    )
    return (lid << 4) | status_nibble


# ---------------------------------------------------------------------------
# Command definitions
# ---------------------------------------------------------------------------

class CommandType(str, Enum):
    LOCK_LASER   = "LOCK_LASER"
    UNLOCK_LASER = "UNLOCK_LASER"
    START_CAVITY = "START_CAVITY"
    STOP_CAVITY  = "STOP_CAVITY"
    CREATE_LASER = "CREATE_LASER"
    REMOVE_LASER = "REMOVE_LASER"
    REQUEST_ADC_DATA     = "REQUEST_ADC_DATA"

# Byte value sent on the wire for each command
_CMD_ID = {
    CommandType.LOCK_LASER:   0x01,
    CommandType.UNLOCK_LASER: 0x02,
    CommandType.START_CAVITY: 0x03,
    CommandType.STOP_CAVITY:  0x04,
    CommandType.CREATE_LASER: 0x05,
    CommandType.REMOVE_LASER: 0x06,
    CommandType.REQUEST_ADC_DATA:     0x07,
}


# ---------------------------------------------------------------------------
# Controller
# ---------------------------------------------------------------------------

class PYNQController:
    """
    Manages a TCP socket connection to a PYNQ FPGA board and exposes
    high-level methods for each supported command.

    Each command is serialised into an 18-byte binary packet and sent over
    a persistent TCP connection. After every send the controller reads one
    framed response header with an optional payload.

    Parameters
    ----------
    server_ip   : IP address of the PYNQ board.
    server_port : TCP port the PYNQ board is listening on.
    log_file    : Path to the log file. Defaults to 'pynq_session_<timestamp>.log'.
    timeout     : Socket timeout in seconds (default: 300.0).
    """

    def __init__(
        self,
        server_ip: str,
        server_port: int,
        log_file: Optional[str] = None,
        timeout: float = 300.0,
    ) -> None:
        self.server_ip   = server_ip
        self.server_port = server_port
        self.timeout     = timeout
        self._socket: Optional[socket.socket] = None
        self._connected  = False
        self._laser_configured = {}
        self._laser_locked = {}
        self._system_on = False

        if log_file is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            log_file  = f"pynq_session_{timestamp}.log"

        # Always route controller logs into logs/.
        log_dir  = Path("logs")
        log_file = str(log_dir / Path(log_file).name)

        self._rotate_old_logs(log_dir)

        self.log_file = log_file
        self._logger  = self._setup_logger(log_file)
        self._logger.info(
            "PYNQController initialised | target=%s:%d | packet_size=%dB | log=%s",
            server_ip, server_port, PACKET_SIZE, log_file,
        )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _rotate_old_logs(log_dir: Path, max_age_days: int = 1) -> None:
        """Move log files older than *max_age_days* into log_dir/archive/."""
        cutoff = datetime.now() - timedelta(days=max_age_days)
        archive_dir = log_dir / "archive"

        for log_path in log_dir.glob("pynq_session_*.log"):
            # Use file modification time to determine age.
            mtime = datetime.fromtimestamp(log_path.stat().st_mtime)
            if mtime < cutoff:
                archive_dir.mkdir(parents=True, exist_ok=True)
                dest = archive_dir / log_path.name
                log_path.rename(dest)

    @staticmethod
    def _setup_logger(log_file: str) -> logging.Logger:
        """Configure a logger that writes to both file and stdout."""
        logger = logging.getLogger(f"PYNQController.{log_file}")
        logger.setLevel(logging.DEBUG)

        formatter = logging.Formatter(
            fmt="%(asctime)s | %(levelname)-8s | %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )

        Path(log_file).parent.mkdir(parents=True, exist_ok=True)
        fh = logging.FileHandler(log_file, mode="a")
        fh.setLevel(logging.DEBUG)
        fh.setFormatter(formatter)

        ch = logging.StreamHandler()
        ch.setLevel(logging.INFO)
        ch.setFormatter(formatter)

        logger.addHandler(fh)
        logger.addHandler(ch)
        return logger

    def _build_packet(
        self,
        command: CommandType,
        laser_id: int = 0,
        laser_locked_flag: bool = False,
        system_on_flag: bool = False,
        laser_configured_flag: bool = False,
        pid_param1: int = 0,
        pid_param2: int = 0,
        pid_param3: int = 0,
        duration: int = 0,
    ) -> bytes:
        """
        Pack a command into a fixed-width binary packet.

        Packet fields:
          byte0: cmd_id
                    byte1: [7:4]=laser_id, [3:0]={0, laser_locked_flag, system_on_flag, laser_configured_flag}
          byte2..17: pid_param1, pid_param2, pid_param3, duration
        """
        laser_flags = _pack_laser_and_flags(
            laser_id=laser_id,
            laser_locked_flag=laser_locked_flag,
                        system_on_flag=system_on_flag,
            laser_configured_flag=laser_configured_flag,
        )
        return struct.pack(
            PACKET_FORMAT,
            _CMD_ID[command],
            laser_flags,
            _validate_uint32("pid_param1", pid_param1),
            _validate_uint32("pid_param2", pid_param2),
            _validate_uint32("pid_param3", pid_param3),
            _validate_uint32("duration", duration),
        )

    def _recv_exact(self, nbytes: int) -> Optional[bytes]:
        """Read exactly nbytes from the socket or return None on failure."""
        if self._socket is None:
            return None

        data = b""
        try:
            while len(data) < nbytes:
                chunk = self._socket.recv(nbytes - len(data))
                if not chunk:
                    self._logger.error("Connection closed by PYNQ board while receiving response.")
                    self._connected = False
                    return None
                data += chunk
            return data
        except socket.timeout:
            self._logger.warning("Timed out while receiving response bytes (wanted=%d).", nbytes)
            return None
        except OSError as exc:
            self._logger.error("Response recv failed: %s", exc)
            return None

    def _recv_response(self, command: CommandType) -> tuple[bool, bytes]:
        """Read one universal response frame and return (success, payload)."""
        header = self._recv_exact(RESPONSE_SIZE)
        if header is None:
            return False, b""

        version, response_id, status, _reserved, payload_length = struct.unpack(RESPONSE_FORMAT, header)
        expected_id = _CMD_ID[command]

        self._logger.debug(
            "RX << response_version=%d response_id=0x%02X status=0x%02X payload_len=%d for %s",
            version,
            response_id,
            status,
            payload_length,
            command.value,
        )

        if version != RESPONSE_VERSION:
            self._logger.error(
                "Unexpected response version for %s: got %d expected %d",
                command.value,
                version,
                RESPONSE_VERSION,
            )
            return False, b""

        if response_id != expected_id:
            self._logger.error(
                "Response ID mismatch for %s: got 0x%02X expected 0x%02X",
                command.value,
                response_id,
                expected_id,
            )
            return False, b""

        if payload_length > MAX_RESPONSE_PAYLOAD:
            self._logger.error(
                "Response payload too large for %s: %d > %d",
                command.value,
                payload_length,
                MAX_RESPONSE_PAYLOAD,
            )
            return False, b""

        payload = b""
        if payload_length > 0:
            payload = self._recv_exact(payload_length)
            if payload is None:
                return False, b""

        if status == ACK_OK:
            return True, payload

        self._logger.error("PYNQ board returned error status for %s.", command.value)
        return False, payload

    def _send_with_response(
        self,
        command: CommandType,
        laser_id: int = 0,
        laser_locked_flag: bool = False,
        system_on_flag: bool = False,
        laser_configured_flag: bool = False,
        pid_param1: int = 0,
        pid_param2: int = 0,
        pid_param3: int = 0,
        duration: int = 0,
    ) -> tuple[bool, bytes]:
        """Build, transmit, and return (status, payload) from one framed response."""
        if not self._connected or self._socket is None:
            self._logger.error(
                "Cannot send %s – not connected to PYNQ board.", command.value
            )
            return False, b""

        packet = self._build_packet(
            command=command,
            laser_id=laser_id,
            laser_locked_flag=laser_locked_flag,
            system_on_flag=system_on_flag,
            laser_configured_flag=laser_configured_flag,
            pid_param1=pid_param1,
            pid_param2=pid_param2,
            pid_param3=pid_param3,
            duration=duration,
        )
        self._logger.debug(
            "TX >> cmd=0x%02X laser_id=%d lock=%d sys=%d cfg=%d p1=%d p2=%d p3=%d dur=%d (%dB)",
            _CMD_ID[command],
            laser_id,
            1 if laser_locked_flag else 0,
            1 if system_on_flag else 0,
            1 if laser_configured_flag else 0,
            pid_param1,
            pid_param2,
            pid_param3,
            duration,
            PACKET_SIZE,
        )

        try:
            self._socket.sendall(packet)
        except (socket.timeout, OSError) as exc:
            self._logger.error("Failed to send %s: %s", command.value, exc)
            self._connected = False
            return False, b""

        success, payload = self._recv_response(command)
        if success:
            self._logger.info("RESP OK | command=%s | payload_len=%d", command.value, len(payload))
        return success, payload

    def _send(
        self,
        command: CommandType,
        laser_id: int = 0,
        laser_locked_flag: bool = False,
        system_on_flag: bool = False,
        laser_configured_flag: bool = False,
        pid_param1: int = 0,
        pid_param2: int = 0,
        pid_param3: int = 0,
        duration: int = 0,
    ) -> bool:
        """
        Build, transmit, and ACK-verify a command.
        Returns True on success, False on any failure.
        """
        success, _payload = self._send_with_response(
            command=command,
            laser_id=laser_id,
            laser_locked_flag=laser_locked_flag,
            system_on_flag=system_on_flag,
            laser_configured_flag=laser_configured_flag,
            pid_param1=pid_param1,
            pid_param2=pid_param2,
            pid_param3=pid_param3,
            duration=duration,
        )
        return success

    # ------------------------------------------------------------------
    # Connection management
    # ------------------------------------------------------------------

    def connect(self) -> bool:
        """
        Open a TCP connection to the PYNQ board.
        Returns True if successful, False otherwise.
        """
        if self._connected:
            self._logger.warning("Already connected to %s:%d.", self.server_ip, self.server_port)
            return True

        self._logger.info("Connecting to PYNQ board at %s:%d …", self.server_ip, self.server_port)
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(self.timeout)
            sock.connect((self.server_ip, self.server_port))
            self._socket    = sock
            self._connected = True
            self._logger.info("Connected successfully.")
            return True
        except (socket.timeout, ConnectionRefusedError, OSError) as exc:
            self._logger.error("Connection failed: %s", exc)
            return False

    def disconnect(self) -> None:
        """Gracefully close the socket connection."""
        if self._socket:
            try:
                self._socket.shutdown(socket.SHUT_RDWR)
                self._socket.close()
            except OSError:
                pass
            finally:
                self._socket    = None
                self._connected = False
                self._logger.info("Disconnected from PYNQ board.")

    @property
    def is_connected(self) -> bool:
        return self._connected

    # ------------------------------------------------------------------
    # Laser commands
    # ------------------------------------------------------------------

    def _laser_is_configured(self, laser_id: int) -> bool:
        return bool(self._laser_configured.get(laser_id, False))

    def _laser_is_locked(self, laser_id: int) -> bool:
        return bool(self._laser_locked.get(laser_id, False))

    def send_command(
        self,
        command: CommandType,
        laser_id: int = 0,
        laser_locked_flag: bool = False,
        system_on_flag: bool = False,
        laser_configured_flag: bool = False,
        pid_param1: int = 0,
        pid_param2: int = 0,
        pid_param3: int = 0,
        duration: int = 0,
    ) -> bool:
        """Send a raw command packet using the full protocol field set."""
        return self._send(
            command=command,
            laser_id=laser_id,
            laser_locked_flag=laser_locked_flag,
            system_on_flag=system_on_flag,
            laser_configured_flag=laser_configured_flag,
            pid_param1=pid_param1,
            pid_param2=pid_param2,
            pid_param3=pid_param3,
            duration=duration,
        )

    def lock_laser(
        self,
        laser_id: int,
        pid_param1: int,
        pid_param2: int = 0,
        pid_param3: int = 0,
        duration: int = 0,
    ) -> bool:
        """
        Lock a laser using packetized PID parameter fields.

        Parameters
        ----------
        laser_id    : Laser ID (nibble field in packet).
        pid_param1  : PID parameter 1 (uint32).
        pid_param2  : PID parameter 2 (uint32).
        pid_param3  : PID parameter 3 (uint32).
        duration    : Duration field (uint32).
        """
        self._logger.info(
            "Locking laser | laser_id=%d | p1=%d p2=%d p3=%d dur=%d",
            laser_id,
            pid_param1,
            pid_param2,
            pid_param3,
            duration,
        )
        success = self._send(
            CommandType.LOCK_LASER,
            laser_id=laser_id,
            laser_locked_flag=True,
            system_on_flag=self._system_on,
            laser_configured_flag=self._laser_is_configured(laser_id),
            pid_param1=pid_param1,
            pid_param2=pid_param2,
            pid_param3=pid_param3,
            duration=duration,
        )
        if success:
            self._laser_locked[laser_id] = True
        return success

    def unlock_laser(self, laser_id: int) -> bool:
        """
        Unlock a previously locked laser.

        Parameters
        ----------
        laser_id : Laser ID nibble to unlock.
        """
        self._logger.info("Unlocking laser | laser_id=%d", laser_id)
        success = self._send(
            CommandType.UNLOCK_LASER,
            laser_id=laser_id,
            laser_locked_flag=False,
            system_on_flag=self._system_on,
            laser_configured_flag=self._laser_is_configured(laser_id),
        )
        if success:
            self._laser_locked[laser_id] = False
        return success

    def create_laser(
        self,
        laser_id: int,
        pid_param1: int = 0,
        pid_param2: int = 0,
        pid_param3: int = 0,
        wavelength: int = 0,
    ) -> bool:
        """
        Register / initialise a new laser resource on the PYNQ board.

        Parameters
        ----------
        laser_id  : Identifier for the new laser.
        wavelength: Target set-wavelength (uint32). Packed into the duration
                    field of the shared packet format, which is unused by
                    CREATE_LASER on the server side.
        """
        self._logger.info(
            "Creating laser | laser_id=%d | p1=%d p2=%d p3=%d wavelength=%d",
            laser_id,
            pid_param1,
            pid_param2,
            pid_param3,
            wavelength,
        )
        success = self._send(
            CommandType.CREATE_LASER,
            laser_id=laser_id,
            laser_locked_flag=False,
            system_on_flag=self._system_on,
            laser_configured_flag=True,
            pid_param1=pid_param1,
            pid_param2=pid_param2,
            pid_param3=pid_param3,
            duration=wavelength,  # duration field repurposed as wavelength for CREATE_LASER
        )
        if success:
            self._laser_configured[laser_id] = True
            self._laser_locked[laser_id] = False
        return success

    def remove_laser(self, laser_id: int) -> bool:
        """
        Remove / de-register a laser resource from the PYNQ board.

        Parameters
        ----------
        laser_id : Identifier of the laser to remove.
        """
        self._logger.info("Removing laser | laser_id=%d", laser_id)
        success = self._send(
            CommandType.REMOVE_LASER,
            laser_id=laser_id,
            laser_locked_flag=False,
            system_on_flag=self._system_on,
            laser_configured_flag=False,
        )
        if success:
            self._laser_configured[laser_id] = False
            self._laser_locked[laser_id] = False
        return success

    # ------------------------------------------------------------------
    # Cavity commands
    # ------------------------------------------------------------------

    def start_cavity(self, duration: int) -> bool:
        """
        Start the optical cavity scan for a specified duration.

        Parameters
        ----------
        duration : Duration field (uint32).
        """
        self._logger.info("Starting cavity | duration=%d", duration)
        success = self._send(
            CommandType.START_CAVITY,
            laser_id=0,
            laser_locked_flag=False,
            system_on_flag=True,
            laser_configured_flag=False,
            duration=duration,
        )
        if success:
            self._system_on = True
        return success

    def stop_cavity(self) -> bool:
        """Immediately stop the optical cavity scan."""
        self._logger.info("Stopping cavity")
        success = self._send(
            CommandType.STOP_CAVITY,
            laser_id=0,
            laser_locked_flag=False,
            system_on_flag=False,
            laser_configured_flag=False,
        )
        if success:
            self._system_on = False
        return success

    def request_adc_data(self) -> list:
        """
        Request a data payload from the PYNQ board.

        Sends a REQUEST_ADC_DATA command and reads a universal response frame.
        The payload is interpreted as packed network-order uint32 ADC samples.

        Returns
        -------
        list
            ADC sample values decoded from payload bytes.
        """
        self._logger.info("Requesting data from board")
        success, payload = self._send_with_response(
            CommandType.REQUEST_ADC_DATA,
            laser_id=0,
            laser_locked_flag=False,
            system_on_flag=self._system_on,
            laser_configured_flag=False,
        )
        if not success:
            self._logger.error("REQUEST_ADC_DATA command rejected by board")
            return []

        if len(payload) % 4 != 0:
            self._logger.error(
                "Malformed ADC payload length=%d (not divisible by 4)",
                len(payload),
            )
            return []

        sample_count = len(payload) // 4
        if sample_count == 0:
            self._logger.warning("REQUEST_ADC_DATA returned empty payload")
            return []

        samples = list(struct.unpack(f"!{sample_count}I", payload))
        self._logger.info("Received ADC payload | samples=%d", sample_count)
        return samples

    # ------------------------------------------------------------------
    # Context-manager support
    # ------------------------------------------------------------------

    def __enter__(self) -> "PYNQController":
        self.connect()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.disconnect()

    # ------------------------------------------------------------------
    # String representation
    # ------------------------------------------------------------------

    def __repr__(self) -> str:
        status = "connected" if self._connected else "disconnected"
        return (
            f"PYNQController(server={self.server_ip}:{self.server_port}, "
            f"status={status}, log={self.log_file})"
        )

    @staticmethod
    def feedback_loop_test_plan() -> list[str]:
        """Return the intended end-to-end controller/server/controls validation steps."""
        return [
            "Connect controller to server and confirm TCP session opens.",
            "Create laser 1 and laser 2, then confirm ACKs from server and state snapshots on the board.",
            "Lock laser 2 with PID params, then confirm server-side state updates and read-back logs.",
            "Start the system for laser 2, confirm system_on becomes true, then read back global flags.",
            "Stop the system, unlock both lasers, remove both lasers, and confirm the final state is cleared.",
        ]


def _parse_cli_value(raw: str):
    lower = raw.lower()
    if lower == "true":
        return True
    if lower == "false":
        return False
    try:
        return int(raw, 0)
    except ValueError:
        return raw


def _parse_cli_command(spec: str):
    """Parse one CLI command spec into method name, args, and kwargs.

    Examples:
        create_laser laser_id=2 pid_param1=120 pid_param2=12 pid_param3=2
        stop_cavity
        unlock_laser 2
    """
    parts = shlex.split(spec)
    if not parts:
        raise ValueError("Command spec cannot be empty.")

    method_name = parts[0]
    args = []
    kwargs = {}

    for token in parts[1:]:
        if "=" in token:
            key, value = token.split("=", 1)
            kwargs[key] = _parse_cli_value(value)
        else:
            args.append(_parse_cli_value(token))

    return method_name, args, kwargs


def _run_interactive_commands(ctrl: "PYNQController") -> bool:
    """Run user-entered API commands until the user exits interactive mode."""
    print("Interactive command mode enabled.")
    print("Enter one API call per line (example: create_laser laser_id=2 pid_param1=120 pid_param2=12 pid_param3=2)")
    print("Type 'help' for available calls. Type 'exit' or 'quit' to stop.")

    available = [
        "create_laser",
        "remove_laser",
        "lock_laser",
        "unlock_laser",
        "start_cavity",
        "stop_cavity",
        "send_command",
    ]

    all_ok = True
    while True:
        raw = input("pynq> ").strip()
        if not raw:
            continue
        if raw.lower() in {"exit", "quit"}:
            break
        if raw.lower() == "help":
            print("Available methods:")
            for name in available:
                print(f"- {name}")
            continue

        try:
            method_name, args, kwargs = _parse_cli_command(raw)
            method = getattr(ctrl, method_name, None)
            if method is None or not callable(method):
                raise ValueError(f"Unknown API method: {method_name}")

            result = method(*args, **kwargs)
            ok = bool(result) if isinstance(result, bool) else True
            all_ok = all_ok and ok
            print(f"{method_name} -> {result}")
            if not ctrl.is_connected:
                print("Connection to server lost. Exiting interactive mode.")
                return False
            if isinstance(result, bool) and not result:
                print("Command failed. Exiting interactive mode.")
                return False
        except Exception as exc:
            all_ok = False
            print(f"Command failed: {exc}")
            if not ctrl.is_connected:
                print("Connection to server lost. Exiting interactive mode.")
                return False

    return all_ok


def _run_cli_commands(ctrl: "PYNQController", commands: list[str]) -> bool:
    """Run a list of user-provided API command specs."""
    all_ok = True
    for idx, spec in enumerate(commands, start=1):
        method_name, args, kwargs = _parse_cli_command(spec)
        method = getattr(ctrl, method_name, None)
        if method is None or not callable(method):
            raise ValueError(f"Unknown API method in --command #{idx}: {method_name}")

        print(f"> {spec}")
        result = method(*args, **kwargs)
        ok = bool(result) if isinstance(result, bool) else True
        all_ok = all_ok and ok
        print(f"  {result}")
        if not ctrl.is_connected:
            print("Connection to server lost. Exiting.")
            return False
        if isinstance(result, bool) and not result:
            print("Command failed. Exiting.")
            return False
    return all_ok


def _load_commands_from_file(path: str) -> list[str]:
    """Load command specs from a text file.

    File format:
      - One command spec per line.
      - Blank lines are ignored.
      - Lines starting with '#' are treated as comments.
    """
    commands: list[str] = []
    with open(path, "r", encoding="utf-8") as handle:
        for line in handle:
            spec = line.strip()
            if not spec or spec.startswith("#"):
                continue
            commands.append(spec)
    return commands


def _run_default_feedback_demo(ctrl: "PYNQController") -> None:
    """Run the original step-by-step feedback-loop demo."""
    print("Feedback-loop test plan:")
    for step in PYNQController.feedback_loop_test_plan():
        print(f"- {step}")
    print()

    def run_step(label: str, action) -> bool:
        print(f"> {label}")
        ok = action()
        print(f"  {'OK' if ok else 'FAILED'}")
        return ok

    if run_step("create_laser(laser_id=1, p1=100, p2=10, p3=1)", lambda: ctrl.create_laser(laser_id=1, pid_param1=100, pid_param2=10, pid_param3=1)):
        if not run_step("create_laser(laser_id=2, p1=120, p2=12, p3=2)", lambda: ctrl.create_laser(laser_id=2, pid_param1=120, pid_param2=12, pid_param3=2)):
            raise SystemExit(1)
    else:
        raise SystemExit(1)

    if not run_step("lock_laser(laser_id=1, p1=1500, p2=20, p3=3, duration=15)", lambda: ctrl.lock_laser(laser_id=1, pid_param1=1500, pid_param2=20, pid_param3=3, duration=15)):
        raise SystemExit(1)
    if not run_step("start_cavity(duration=30)", lambda: ctrl.start_cavity(duration=30)):
        raise SystemExit(1)

    time.sleep(1)

    if not run_step("lock_laser(laser_id=2, p1=1550, p2=25, p3=2, duration=10)", lambda: ctrl.lock_laser(laser_id=2, pid_param1=1550, pid_param2=25, pid_param3=2, duration=10)):
        raise SystemExit(1)
    if not run_step("stop_cavity()", lambda: ctrl.stop_cavity()):
        raise SystemExit(1)

    if not run_step("unlock_laser(laser_id=1)", lambda: ctrl.unlock_laser(laser_id=1)):
        raise SystemExit(1)
    if not run_step("unlock_laser(laser_id=2)", lambda: ctrl.unlock_laser(laser_id=2)):
        raise SystemExit(1)
    if not run_step("remove_laser(laser_id=1)", lambda: ctrl.remove_laser(laser_id=1)):
        raise SystemExit(1)
    if not run_step("remove_laser(laser_id=2)", lambda: ctrl.remove_laser(laser_id=2)):
        raise SystemExit(1)


def _build_cli_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="PYNQ laser controller CLI",
    )
    parser.add_argument("--ip", default="192.168.3.1", help="PYNQ server IP address")
    parser.add_argument("--port", type=int, default=5000, help="PYNQ server TCP port")
    parser.add_argument(
        "--timeout",
        type=float,
        default=300.0,
        help="Socket timeout in seconds (default: 300)",
    )
    parser.add_argument(
        "-c",
        "--command",
        action="append",
        default=[],
        help=(
            "Controller API command to run. Can be provided multiple times. "
            "Example: --command \"create_laser laser_id=2 pid_param1=120 pid_param2=12 pid_param3=2\""
        ),
    )
    parser.add_argument(
        "--interactive",
        action="store_true",
        help="Run an interactive prompt to enter API commands",
    )
    parser.add_argument(
        "--commands-file",
        action="append",
        default=[],
        help=(
            "Path to a text file containing API commands, one per line. "
            "Can be provided multiple times."
        ),
    )
    return parser


# ---------------------------------------------------------------------------
# Quick smoke-test / example usage (runs when executed directly)
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    args = _build_cli_parser().parse_args()

    with PYNQController(server_ip=args.ip, server_port=args.port, timeout=args.timeout) as ctrl:
        if not ctrl.is_connected:
            print("Could not reach PYNQ board – check IP/port and board status.")
            raise SystemExit(1)

        combined_commands: list[str] = []
        for file_path in args.commands_file:
            combined_commands.extend(_load_commands_from_file(file_path))
        combined_commands.extend(args.command)

        if combined_commands:
            ok = _run_cli_commands(ctrl, combined_commands)
            raise SystemExit(0 if ok else 1)

        if args.interactive:
            ok = _run_interactive_commands(ctrl)
            raise SystemExit(0 if ok else 1)

        # Backward-compatible default path remains the test demo.
        _run_default_feedback_demo(ctrl)
