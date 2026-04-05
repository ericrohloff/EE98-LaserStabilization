"""
pynq_controller.py
------------------
Host-side controller for communicating with a PYNQ FPGA board over TCP sockets.
Uses a fixed-width binary protocol to minimise processing on the PYNQ side.

Usage:
    controller = PYNQController(server_ip="192.168.1.100", server_port=5000)
    controller.connect()
    controller.create_laser(pid=1)
    controller.lock_laser(pid=1, pid_param1=1550)
    controller.start_cavity(duration=10)
    controller.disconnect()

    # Or as a context manager:
    with PYNQController(server_ip="192.168.1.100", server_port=5000) as ctrl:
        ctrl.create_laser(pid=1)
        ctrl.lock_laser(pid=1, pid_param1=1550)

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
ACK format  (1 byte)
---------------------------------------------------------------------------
  0x00  OK
  0x01  Error
"""

import logging
import socket
import struct
import time
from datetime import datetime
from enum import Enum
from typing import Optional


# ---------------------------------------------------------------------------
# Packet constants
# ---------------------------------------------------------------------------

PACKET_FORMAT = "!BBIIII"        # uint8, uint8, uint32, uint32, uint32, uint32
PACKET_SIZE   = struct.calcsize(PACKET_FORMAT)   # 18 bytes

ACK_OK    = 0x00
ACK_ERROR = 0x01

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

# Byte value sent on the wire for each command
_CMD_ID = {
    CommandType.LOCK_LASER:   0x01,
    CommandType.UNLOCK_LASER: 0x02,
    CommandType.START_CAVITY: 0x03,
    CommandType.STOP_CAVITY:  0x04,
    CommandType.CREATE_LASER: 0x05,
    CommandType.REMOVE_LASER: 0x06,
}


# ---------------------------------------------------------------------------
# Controller
# ---------------------------------------------------------------------------

class PYNQController:
    """
    Manages a TCP socket connection to a PYNQ FPGA board and exposes
    high-level methods for each supported command.

    Each command is serialised into an 18-byte binary packet and sent over
    a persistent TCP connection.  After every send the controller reads a
    1-byte ACK from the board (0x00 = ok, 0x01 = error).

    Parameters
    ----------
    server_ip   : IP address of the PYNQ board.
    server_port : TCP port the PYNQ board is listening on.
    log_file    : Path to the log file. Defaults to 'pynq_session_<timestamp>.log'.
    timeout     : Socket timeout in seconds (default: 5.0).
    """

    def __init__(
        self,
        server_ip: str,
        server_port: int,
        log_file: Optional[str] = None,
        timeout: float = 5.0,
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
    def _setup_logger(log_file: str) -> logging.Logger:
        """Configure a logger that writes to both file and stdout."""
        logger = logging.getLogger(f"PYNQController.{log_file}")
        logger.setLevel(logging.DEBUG)

        formatter = logging.Formatter(
            fmt="%(asctime)s | %(levelname)-8s | %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )

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

    def _recv_ack(self, command: CommandType) -> bool:
        """
        Read the 1-byte ACK from the board.
        Returns True on ACK_OK (0x00), False on ACK_ERROR or timeout.
        """
        try:
            raw = self._socket.recv(1)
            if not raw:
                self._logger.error("Connection closed by PYNQ board while waiting for ACK.")
                self._connected = False
                return False

            ack = raw[0]
            self._logger.debug("RX << ACK=0x%02X for %s", ack, command.value)

            if ack == ACK_OK:
                return True

            self._logger.error("PYNQ board returned error ACK for %s.", command.value)
            return False

        except socket.timeout:
            self._logger.warning("Timed out waiting for ACK | command=%s", command.value)
            return False
        except OSError as exc:
            self._logger.error("ACK recv failed: %s", exc)
            return False

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
        if not self._connected or self._socket is None:
            self._logger.error(
                "Cannot send %s – not connected to PYNQ board.", command.value
            )
            return False

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
            return False

        success = self._recv_ack(command)
        if success:
            self._logger.info("ACK OK | command=%s", command.value)
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
        pid: int,
        pid_param1: int,
        pid_param2: int = 0,
        pid_param3: int = 0,
        duration: int = 0,
    ) -> bool:
        """
        Lock a laser using packetized PID parameter fields.

        Parameters
        ----------
        pid         : Laser ID (nibble field in packet).
        pid_param1  : PID parameter 1 (uint32).
        pid_param2  : PID parameter 2 (uint32).
        pid_param3  : PID parameter 3 (uint32).
        duration    : Duration field (uint32).
        """
        self._logger.info(
            "Locking laser | laser_id=%d | p1=%d p2=%d p3=%d dur=%d",
            pid,
            pid_param1,
            pid_param2,
            pid_param3,
            duration,
        )
        success = self._send(
            CommandType.LOCK_LASER,
            laser_id=pid,
            laser_locked_flag=True,
            system_on_flag=self._system_on,
            laser_configured_flag=self._laser_is_configured(pid),
            pid_param1=pid_param1,
            pid_param2=pid_param2,
            pid_param3=pid_param3,
            duration=duration,
        )
        if success:
            self._laser_locked[pid] = True
        return success

    def unlock_laser(self, pid: int) -> bool:
        """
        Unlock a previously locked laser.

        Parameters
        ----------
        pid : Laser ID nibble to unlock.
        """
        self._logger.info("Unlocking laser | laser_id=%d", pid)
        success = self._send(
            CommandType.UNLOCK_LASER,
            laser_id=pid,
            laser_locked_flag=False,
            system_on_flag=self._system_on,
            laser_configured_flag=self._laser_is_configured(pid),
        )
        if success:
            self._laser_locked[pid] = False
        return success

    def create_laser(
        self,
        pid: int,
        pid_param1: int = 0,
        pid_param2: int = 0,
        pid_param3: int = 0,
        duration: int = 0,
    ) -> bool:
        """
        Register / initialise a new laser resource on the PYNQ board.

        Parameters
        ----------
        pid : Identifier for the new laser.
        """
        self._logger.info(
            "Creating laser | laser_id=%d | p1=%d p2=%d p3=%d dur=%d",
            pid,
            pid_param1,
            pid_param2,
            pid_param3,
            duration,
        )
        success = self._send(
            CommandType.CREATE_LASER,
            laser_id=pid,
            laser_locked_flag=False,
            system_on_flag=self._system_on,
            laser_configured_flag=True,
            pid_param1=pid_param1,
            pid_param2=pid_param2,
            pid_param3=pid_param3,
            duration=duration,
        )
        if success:
            self._laser_configured[pid] = True
            self._laser_locked[pid] = False
        return success

    def remove_laser(self, pid: int) -> bool:
        """
        Remove / de-register a laser resource from the PYNQ board.

        Parameters
        ----------
        pid : Identifier of the laser to remove.
        """
        self._logger.info("Removing laser | laser_id=%d", pid)
        success = self._send(
            CommandType.REMOVE_LASER,
            laser_id=pid,
            laser_locked_flag=False,
            system_on_flag=self._system_on,
            laser_configured_flag=False,
        )
        if success:
            self._laser_configured[pid] = False
            self._laser_locked[pid] = False
        return success

    # ------------------------------------------------------------------
    # Cavity commands
    # ------------------------------------------------------------------

    def start_cavity(self, duration: int, laser_id: int = 0) -> bool:
        """
        Start the optical cavity scan for a specified duration.

        Parameters
        ----------
        duration : Duration field (uint32).
        laser_id : Laser ID nibble (optional, defaults to 0).
        """
        self._logger.info("Starting cavity | laser_id=%d | duration=%d", laser_id, duration)
        success = self._send(
            CommandType.START_CAVITY,
            laser_id=laser_id,
            laser_locked_flag=self._laser_is_locked(laser_id),
            system_on_flag=True,
            laser_configured_flag=self._laser_is_configured(laser_id),
            duration=duration,
        )
        if success:
            self._system_on = True
        return success

    def stop_cavity(self, laser_id: int = 0) -> bool:
        """Immediately stop the optical cavity scan."""
        self._logger.info("Stopping cavity | laser_id=%d", laser_id)
        success = self._send(
            CommandType.STOP_CAVITY,
            laser_id=laser_id,
            laser_locked_flag=self._laser_is_locked(laser_id),
            system_on_flag=False,
            laser_configured_flag=self._laser_is_configured(laser_id),
        )
        if success:
            self._system_on = False
        return success

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


# ---------------------------------------------------------------------------
# Quick smoke-test / example usage (runs when executed directly)
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    PYNQ_IP   = "192.168.2.99"
    PYNQ_PORT = 5000

    with PYNQController(server_ip=PYNQ_IP, server_port=PYNQ_PORT) as ctrl:
        if not ctrl.is_connected:
            print("Could not reach PYNQ board – check IP/port and board status.")
        else:
            ctrl.create_laser(pid=1, pid_param1=100, pid_param2=10, pid_param3=1)
            ctrl.create_laser(pid=2, pid_param1=120, pid_param2=12, pid_param3=2)

            ctrl.lock_laser(pid=1, pid_param1=1500, pid_param2=20, pid_param3=3, duration=15)
            ctrl.start_cavity(duration=30, laser_id=1)
            time.sleep(1)

            ctrl.lock_laser(pid=2, pid_param1=1550, pid_param2=25, pid_param3=2, duration=10)
            ctrl.stop_cavity(laser_id=1)

            ctrl.unlock_laser(pid=1)
            ctrl.unlock_laser(pid=2)
            ctrl.remove_laser(pid=1)
            ctrl.remove_laser(pid=2)
