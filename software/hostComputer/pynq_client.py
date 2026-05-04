import logging
import socket
import struct
from pathlib import Path
from datetime import datetime, timedelta
from enum import Enum
from typing import Optional


# ---------------------------------------------------------------------------
# Packet constants
# ---------------------------------------------------------------------------

PACKET_FORMAT = "!BBIIII"        # uint8, uint8, uint32, uint32, uint32, uint32
PACKET_SIZE = struct.calcsize(PACKET_FORMAT)   # 18 bytes

ACK_OK = 0x00
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
        raise ValueError(
            f"{name} must be in range [0, 4294967295], got {value}.")
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
    LOCK_LASER = "LOCK_LASER"
    UNLOCK_LASER = "UNLOCK_LASER"
    START_CAVITY = "START_CAVITY"
    STOP_CAVITY = "STOP_CAVITY"
    CREATE_LASER = "CREATE_LASER"
    REMOVE_LASER = "REMOVE_LASER"
    REQUEST_ADC_DATA = "REQUEST_ADC_DATA"


# Byte value sent on the wire for each command
_CMD_ID = {
    CommandType.LOCK_LASER: 0x01,
    CommandType.UNLOCK_LASER: 0x02,
    CommandType.START_CAVITY: 0x03,
    CommandType.STOP_CAVITY: 0x04,
    CommandType.CREATE_LASER: 0x05,
    CommandType.REMOVE_LASER: 0x06,
    CommandType.REQUEST_ADC_DATA: 0x07,
}


class PYNQController:
    """
    Backend transport/controller for PYNQ command protocol.

    Each command is serialized into an 18-byte binary packet and sent over
    a persistent TCP connection. After every send the controller reads one
    framed response header with an optional payload.
    """

    def __init__(
        self,
        server_ip: str,
        server_port: int,
        log_file: Optional[str] = None,
        timeout: float = 300.0,
    ) -> None:
        self.server_ip = server_ip
        self.server_port = server_port
        self.timeout = timeout
        self._socket: Optional[socket.socket] = None
        self._connected = False
        self._laser_configured = {}
        self._laser_locked = {}
        self._system_on = False

        if log_file is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            log_file = f"pynq_session_{timestamp}.log"

        # Always route controller logs into logs/.
        log_dir = Path("logs")
        log_file = str(log_dir / Path(log_file).name)

        self._rotate_old_logs(log_dir)

        self.log_file = log_file
        self._logger = self._setup_logger(log_file)
        self._logger.info(
            "PYNQController initialised | target=%s:%d | packet_size=%dB | log=%s",
            server_ip,
            server_port,
            PACKET_SIZE,
            log_file,
        )

    @staticmethod
    def _rotate_old_logs(log_dir: Path, max_age_days: int = 1) -> None:
        """Move log files older than *max_age_days* into log_dir/archive/."""
        cutoff = datetime.now() - timedelta(days=max_age_days)
        archive_dir = log_dir / "archive"

        for log_path in log_dir.glob("pynq_session_*.log"):
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
                    self._logger.error(
                        "Connection closed by PYNQ board while receiving response.")
                    self._connected = False
                    return None
                data += chunk
            return data
        except socket.timeout:
            self._logger.warning(
                "Timed out while receiving response bytes (wanted=%d).", nbytes)
            return None
        except OSError as exc:
            self._logger.error("Response recv failed: %s", exc)
            return None

    def _recv_response(self, command: CommandType) -> tuple[bool, bytes]:
        """Read one universal response frame and return (success, payload)."""
        header = self._recv_exact(RESPONSE_SIZE)
        if header is None:
            return False, b""

        version, response_id, status, _reserved, payload_length = struct.unpack(
            RESPONSE_FORMAT, header)
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

        self._logger.error(
            "PYNQ board returned error status for %s.", command.value)
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
                "Cannot send %s - not connected to PYNQ board.", command.value
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
            self._logger.info(
                "RESP OK | command=%s | payload_len=%d", command.value, len(payload))
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
        """Build, transmit, and validate one command response."""
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

    def connect(self) -> bool:
        """Open a TCP connection to the PYNQ board."""
        if self._connected:
            self._logger.warning("Already connected to %s:%d.",
                                 self.server_ip, self.server_port)
            return True

        self._logger.info("Connecting to PYNQ board at %s:%d ...",
                          self.server_ip, self.server_port)
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(self.timeout)
            sock.connect((self.server_ip, self.server_port))
            self._socket = sock
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
                self._socket = None
                self._connected = False
                self._logger.info("Disconnected from PYNQ board.")

    @property
    def is_connected(self) -> bool:
        return self._connected

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

    # Translate to ramp math wavelenght->ramp
    def create_laser(
        self,
        laser_id: int,
        pid_param1: int = 0,
        pid_param2: int = 0,
        pid_param3: int = 0,
        wavelength: int = 0,
    ) -> bool:
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
            duration=wavelength,
        )
        if success:
            self._laser_configured[laser_id] = True
            self._laser_locked[laser_id] = False
        return success

    def remove_laser(self, laser_id: int) -> bool:
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

    # scan duration to ramp step position
    def start_cavity(self, duration: int) -> bool:
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

    def request_adc_data(self) -> list[int]:
        """Request ADC payload and decode network-order uint32 samples."""
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

    def __enter__(self) -> "PYNQController":
        self.connect()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.disconnect()

    def __repr__(self) -> str:
        status = "connected" if self._connected else "disconnected"
        return (
            f"PYNQController(server={self.server_ip}:{self.server_port}, "
            f"status={status}, log={self.log_file})"
        )

    @staticmethod
    def feedback_loop_test_plan() -> list[str]:
        return [
            "Connect controller to server and confirm TCP session opens.",
            "Create laser 1 and laser 2, then confirm ACKs from server and state snapshots on the board.",
            "Lock laser 2 with PID params, then confirm server-side state updates and read-back logs.",
            "Start the system for laser 2, confirm system_on becomes true, then read back global flags.",
            "Stop the system, unlock both lasers, remove both lasers, and confirm the final state is cleared.",
        ]


__all__ = [
    "PYNQController",
    "CommandType",
    "PACKET_FORMAT",
    "PACKET_SIZE",
    "RESPONSE_FORMAT",
    "RESPONSE_SIZE",
    "RESPONSE_VERSION",
    "ACK_OK",
    "ACK_ERROR",
]
