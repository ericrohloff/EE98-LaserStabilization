"""
pynq_controller.py
------------------
Host-side controller for communicating with a PYNQ FPGA board over TCP sockets.
Uses a fixed-width binary protocol to minimise processing on the PYNQ side.

Usage:
    controller = PYNQController(server_ip="192.168.1.100", server_port=5000)
    controller.connect()
    controller.create_laser(pid=1)
    controller.lock_laser(pid=1, wavelength=1550.0)
    controller.start_cavity(duration=10.0)
    controller.disconnect()

    # Or as a context manager:
    with PYNQController(server_ip="192.168.1.100", server_port=5000) as ctrl:
        ctrl.create_laser(pid=1)
        ctrl.lock_laser(pid=1, wavelength=1550.0)

---------------------------------------------------------------------------
Binary packet format  (21 bytes, big-endian / network byte order)
---------------------------------------------------------------------------

 Offset  Size  Type     Field    Description
 ------  ----  -------  -------  ------------------------------------
   0      1    uint8    cmd_id   Command identifier (see _CMD_ID)
   1      4    int32    pid      Laser ID (0 if unused)
   5      8    float64  param1   wavelength (nm) or duration (s)
  13      8    float64  param2   Reserved (always 0.0)
 ------
  21 bytes total

PYNQ-side (Python):
    CMD_ID, PID, PARAM1, PARAM2 = struct.unpack('!Bidd', data)

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

PACKET_FORMAT = "!Bidd"          # network byte order: uint8, int32, float64, float64
PACKET_SIZE   = struct.calcsize(PACKET_FORMAT)   # 21 bytes

ACK_OK    = 0x00
ACK_ERROR = 0x01


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

    Each command is serialised into a 21-byte binary packet and sent over
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
        pid: int   = 0,
        param1: float = 0.0,
        param2: float = 0.0,
    ) -> bytes:
        """
        Pack a command into a fixed-width binary packet.

        Parameters map to fields as follows:
          LOCK_LASER   : pid=pid,  param1=wavelength_nm
          UNLOCK_LASER : pid=pid
          CREATE_LASER : pid=pid
          REMOVE_LASER : pid=pid
          START_CAVITY : param1=duration_s
          STOP_CAVITY  : (no params)
        """
        return struct.pack(PACKET_FORMAT, _CMD_ID[command], pid, param1, param2)

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
        pid: int   = 0,
        param1: float = 0.0,
        param2: float = 0.0,
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

        packet = self._build_packet(command, pid, param1, param2)
        self._logger.debug(
            "TX >> cmd=0x%02X pid=%d param1=%.6g param2=%.6g (%dB)",
            _CMD_ID[command], pid, param1, param2, PACKET_SIZE,
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

    def lock_laser(self, pid: int, wavelength: float) -> bool:
        """
        Lock a laser to a target wavelength.

        Parameters
        ----------
        pid        : Laser process/device ID.
        wavelength : Target wavelength in nanometres (nm).
        """
        self._logger.info("Locking laser | PID=%d | wavelength=%.4f nm", pid, wavelength)
        return self._send(CommandType.LOCK_LASER, pid=pid, param1=wavelength)

    def unlock_laser(self, pid: int) -> bool:
        """
        Unlock a previously locked laser.

        Parameters
        ----------
        pid : Laser process/device ID to unlock.
        """
        self._logger.info("Unlocking laser | PID=%d", pid)
        return self._send(CommandType.UNLOCK_LASER, pid=pid)

    def create_laser(self, pid: int) -> bool:
        """
        Register / initialise a new laser resource on the PYNQ board.

        Parameters
        ----------
        pid : Identifier for the new laser.
        """
        self._logger.info("Creating laser | PID=%d", pid)
        return self._send(CommandType.CREATE_LASER, pid=pid)

    def remove_laser(self, pid: int) -> bool:
        """
        Remove / de-register a laser resource from the PYNQ board.

        Parameters
        ----------
        pid : Identifier of the laser to remove.
        """
        self._logger.info("Removing laser | PID=%d", pid)
        return self._send(CommandType.REMOVE_LASER, pid=pid)

    # ------------------------------------------------------------------
    # Cavity commands
    # ------------------------------------------------------------------

    def start_cavity(self, duration: float) -> bool:
        """
        Start the optical cavity scan for a specified duration.

        Parameters
        ----------
        duration : Run duration in seconds.
        """
        self._logger.info("Starting cavity | duration=%.2f s", duration)
        return self._send(CommandType.START_CAVITY, param1=duration)

    def stop_cavity(self) -> bool:
        """Immediately stop the optical cavity scan."""
        self._logger.info("Stopping cavity.")
        return self._send(CommandType.STOP_CAVITY)

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
            ctrl.create_laser(pid=1)
            ctrl.lock_laser(pid=1, wavelength=1550.12)
            ctrl.start_cavity(duration=30.0)
            time.sleep(1)
            ctrl.stop_cavity()
            ctrl.unlock_laser(pid=1)
            ctrl.remove_laser(pid=1)
