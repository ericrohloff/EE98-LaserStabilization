"""
pynq_server.py
--------------
Server-side script that runs on the PYNQ FPGA board.
Listens for a TCP connection from PYNQController, receives 18-byte binary
command packets, dispatches them to the FPGA overlay, and sends a 1-byte ACK.

Deploy:
    Copy this file to the PYNQ board and run:
        python3 pynq_server.py

    The server accepts one client at a time.  If the host disconnects it
    waits for a new connection automatically.

---------------------------------------------------------------------------
Packet format  (must match pynq_controller.py)
---------------------------------------------------------------------------
 Offset  Size  Type     Field
 ------  ----  -------  ----------------
     0      1    uint8    cmd_id
     1      1    uint8    laser_and_flags
     2      4    uint32   pid_param1
     6      4    uint32   pid_param2
    10      4    uint32   pid_param3
    14      4    uint32   duration
    18 bytes total

laser_and_flags byte:
    high nibble: laser_id
    low nibble : {0, laser_locked_flag, system_on_flag, laser_configured_flag}

ACK: 1 byte — 0x00 = ok, 0x01 = error
"""

import logging
import signal
import socket
import struct
from pathlib import Path
from datetime import datetime

from pynq_controls import PYNQControls

# ---------------------------------------------------------------------------
# Packet / protocol constants  (keep in sync with pynq_controller.py)
# ---------------------------------------------------------------------------

PACKET_FORMAT = "!BBIIII"
PACKET_SIZE   = struct.calcsize(PACKET_FORMAT)   # 18 bytes

ACK_OK    = bytes([0x00])
ACK_ERROR = bytes([0x01])

CMD_LOCK_LASER   = 0x01
CMD_UNLOCK_LASER = 0x02
CMD_START_CAVITY = 0x03
CMD_STOP_CAVITY  = 0x04
CMD_CREATE_LASER = 0x05
CMD_REMOVE_LASER = 0x06

CMD_NAMES = {
    CMD_LOCK_LASER:   "LOCK_LASER",
    CMD_UNLOCK_LASER: "UNLOCK_LASER",
    CMD_START_CAVITY: "START_CAVITY",
    CMD_STOP_CAVITY:  "STOP_CAVITY",
    CMD_CREATE_LASER: "CREATE_LASER",
    CMD_REMOVE_LASER: "REMOVE_LASER",
}


def _decode_laser_and_flags(laser_and_flags: int):
    laser_id = (laser_and_flags >> 4) & 0x0F
    status_nibble = laser_and_flags & 0x0F
    laser_locked_flag = bool((status_nibble >> 2) & 0x01)
    system_on_flag = bool((status_nibble >> 1) & 0x01)
    laser_configured_flag = bool(status_nibble & 0x01)
    return laser_id, laser_locked_flag, system_on_flag, laser_configured_flag


# Global flag memory
SYSTEM_ON_FLAG = False
LASER_CONFIGURED_FLAGS = {}
LASER_LOCKED_FLAGS = {}


def _laser_is_configured(laser_id: int) -> bool:
    return bool(LASER_CONFIGURED_FLAGS.get(laser_id, False))


def _laser_is_locked(laser_id: int) -> bool:
    return bool(LASER_LOCKED_FLAGS.get(laser_id, False))


def _expected_flags(laser_id: int):
    return _laser_is_locked(laser_id), SYSTEM_ON_FLAG, _laser_is_configured(laser_id)


def _update_flag_memory(cmd_id: int, laser_id: int) -> None:
    global SYSTEM_ON_FLAG

    if cmd_id == CMD_CREATE_LASER:
        LASER_CONFIGURED_FLAGS[laser_id] = True
        LASER_LOCKED_FLAGS[laser_id] = False
    elif cmd_id == CMD_REMOVE_LASER:
        LASER_CONFIGURED_FLAGS[laser_id] = False
        LASER_LOCKED_FLAGS[laser_id] = False
    elif cmd_id == CMD_LOCK_LASER:
        LASER_LOCKED_FLAGS[laser_id] = True
    elif cmd_id == CMD_UNLOCK_LASER:
        LASER_LOCKED_FLAGS[laser_id] = False
    elif cmd_id == CMD_START_CAVITY:
        SYSTEM_ON_FLAG = True
    elif cmd_id == CMD_STOP_CAVITY:
        SYSTEM_ON_FLAG = False

# ---------------------------------------------------------------------------
# Server config
# ---------------------------------------------------------------------------

HOST    = "0.0.0.0"
PORT    = 5000
TIMEOUT = 300.0  # seconds — client must send a packet within this window

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

def _setup_logger() -> logging.Logger:
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_dir = Path("logs")
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = str(log_dir / f"pynq_server_{timestamp}.log")

    logger = logging.getLogger("PYNQServer")
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
    logger.info("Logging to %s", log_file)
    return logger

logger = _setup_logger()
controls = PYNQControls(logger=logger)

# ---------------------------------------------------------------------------
# FPGA overlay  (replace stubs with real pynq / overlay calls)
# ---------------------------------------------------------------------------

# Uncomment when running on the PYNQ board:
# from pynq import Overlay
# overlay = Overlay("your_design.bit")

def handle_create_laser(laser_id: int, pid_param1: int, pid_param2: int, pid_param3: int, duration: int) -> bool:
    """Initialise a laser PID controller instance on the FPGA."""
    success = controls.create_laser(laser_id, pid_param1, pid_param2, pid_param3, duration)
    logger.debug(
        "handle_create_laser | laser_id=%d | p1=%d p2=%d p3=%d dur=%d",
        laser_id,
        pid_param1,
        pid_param2,
        pid_param3,
        duration,
    )
    return success

def handle_remove_laser(laser_id: int) -> bool:
    """De-register a laser PID controller instance."""
    success = controls.remove_laser(laser_id)
    logger.debug("handle_remove_laser | laser_id=%d", laser_id)
    return success

def handle_lock_laser(
    laser_id: int,
    pid_param1: int,
    pid_param2: int,
    pid_param3: int,
    duration: int,
    laser_locked_flag: bool,
    system_on_flag: bool,
    laser_configured_flag: bool,
) -> bool:
    """Set PID parameters and lock-state for a laser controller."""
    pid_ok = controls.configure_laser_pid(laser_id, pid_param1, pid_param2, pid_param3)
    lock_ok = controls.set_laser_lock(laser_id, laser_locked_flag, laser_configured_flag)
    logger.debug(
        "handle_lock_laser | laser_id=%d | lock=%d sys=%d cfg=%d | p1=%d p2=%d p3=%d dur=%d",
        laser_id,
        1 if laser_locked_flag else 0,
        1 if system_on_flag else 0,
        1 if laser_configured_flag else 0,
        pid_param1,
        pid_param2,
        pid_param3,
        duration,
    )
    return pid_ok and lock_ok

def handle_unlock_laser(laser_id: int, laser_configured_flag: bool) -> bool:
    """Disable closed-loop feedback for a laser."""
    success = controls.set_laser_lock(laser_id, False, laser_configured_flag)
    logger.debug(
        "handle_unlock_laser | laser_id=%d | cfg=%d",
        laser_id,
        1 if laser_configured_flag else 0,
    )
    return success

def handle_start_cavity(duration: int) -> bool:
    """Start the triangular cavity ramp for the requested duration field."""
    success = controls.start_cavity(duration)
    logger.debug("handle_start_cavity | duration=%d", duration)
    return success

def handle_stop_cavity() -> bool:
    """Stop the cavity ramp immediately."""
    success = controls.stop_cavity()
    logger.debug("handle_stop_cavity")
    return success


def _log_state_snapshot(laser_id: int) -> None:
    """Log the current FPGA-backed state after a successful command."""
    try:
        laser_state = read_laser_state(laser_id)
        system_flags = read_system_flags()
    except Exception as exc:  # pragma: no cover - logging only
        logger.warning("State snapshot failed | laser_id=%d | %s", laser_id, exc)
        return

    logger.info(
        "STATE SNAPSHOT | laser_id=%d | laser=%s | system=%s",
        laser_id,
        laser_state,
        system_flags,
    )


def read_laser_pid_param(laser_id: int, param_index: int) -> int:
    """Read one PID parameter for a laser from FPGA MMIO."""
    value = controls.read_laser_pid_param(laser_id, param_index)
    logger.debug(
        "read_laser_pid_param | laser_id=%d param_index=%d value=%d",
        laser_id,
        param_index,
        value,
    )
    return value


def read_laser_pid_p(laser_id: int) -> int:
    return read_laser_pid_param(laser_id, 1)


def read_laser_pid_i(laser_id: int) -> int:
    return read_laser_pid_param(laser_id, 2)


def read_laser_pid_d(laser_id: int) -> int:
    return read_laser_pid_param(laser_id, 3)


def read_laser_state(laser_id: int) -> dict:
    """Read the full laser state as exposed by the FPGA register block."""
    state = controls.read_laser_state(laser_id)
    logger.debug("read_laser_state | laser_id=%d state=%s", laser_id, state)
    return state


def read_system_flags() -> dict:
    """Read the global system flags from the FPGA."""
    flags = controls.read_system_flags()
    logger.debug("read_system_flags | %s", flags)
    return flags

# ---------------------------------------------------------------------------
# Dispatch table  (cmd_id -> callable)
# ---------------------------------------------------------------------------

def _dispatch(
    cmd_id: int,
    laser_id: int,
    laser_locked_flag: bool,
    system_on_flag: bool,
    laser_configured_flag: bool,
    pid_param1: int,
    pid_param2: int,
    pid_param3: int,
    duration: int,
) -> bool:
    """Route an unpacked command to the appropriate handler."""
    if cmd_id == CMD_CREATE_LASER:
        return handle_create_laser(laser_id, pid_param1, pid_param2, pid_param3, duration)
    elif cmd_id == CMD_REMOVE_LASER:
        return handle_remove_laser(laser_id)
    elif cmd_id == CMD_LOCK_LASER:
        return handle_lock_laser(
            laser_id,
            pid_param1,
            pid_param2,
            pid_param3,
            duration,
            laser_locked_flag,
            system_on_flag,
            laser_configured_flag,
        )
    elif cmd_id == CMD_UNLOCK_LASER:
        return handle_unlock_laser(laser_id, laser_configured_flag)
    elif cmd_id == CMD_START_CAVITY:
        return handle_start_cavity(duration)
    elif cmd_id == CMD_STOP_CAVITY:
        return handle_stop_cavity()
    else:
        logger.warning("Unknown cmd_id=0x%02X — ignoring.", cmd_id)
        return False

# ---------------------------------------------------------------------------
# Connection handler
# ---------------------------------------------------------------------------

def handle_connection(conn: socket.socket, addr) -> None:
    """
    Read packets from a connected host until the connection closes.
    Sends ACK_OK / ACK_ERROR after each packet.
    """
    logger.info("Client connected: %s:%d", *addr)
    conn.settimeout(TIMEOUT)

    try:
        while True:
            # Read exactly PACKET_SIZE bytes
            data = b""
            while len(data) < PACKET_SIZE:
                chunk = conn.recv(PACKET_SIZE - len(data))
                if not chunk:
                    logger.info("Client disconnected: %s:%d", *addr)
                    return
                data += chunk

            cmd_id, laser_and_flags, pid_param1, pid_param2, pid_param3, duration = struct.unpack(PACKET_FORMAT, data)
            laser_id, laser_locked_flag, system_on_flag, laser_configured_flag = _decode_laser_and_flags(laser_and_flags)
            cmd_name = CMD_NAMES.get(cmd_id, f"0x{cmd_id:02X}")
            expected_locked, expected_system_on, expected_configured = _expected_flags(laser_id)
            if (
                laser_locked_flag != expected_locked
                or system_on_flag != expected_system_on
                or laser_configured_flag != expected_configured
            ):
                logger.warning(
                    "FLAG mismatch from client | laser_id=%d | rx(lock=%d sys=%d cfg=%d) expected(lock=%d sys=%d cfg=%d)",
                    laser_id,
                    1 if laser_locked_flag else 0,
                    1 if system_on_flag else 0,
                    1 if laser_configured_flag else 0,
                    1 if expected_locked else 0,
                    1 if expected_system_on else 0,
                    1 if expected_configured else 0,
                )
            logger.debug(
                "RX << cmd=%s laser_id=%d lock=%d sys=%d cfg=%d p1=%d p2=%d p3=%d dur=%d",
                cmd_name,
                laser_id,
                1 if laser_locked_flag else 0,
                1 if system_on_flag else 0,
                1 if laser_configured_flag else 0,
                pid_param1,
                pid_param2,
                pid_param3,
                duration,
            )

            success = _dispatch(
                cmd_id,
                laser_id,
                laser_locked_flag,
                system_on_flag,
                laser_configured_flag,
                pid_param1,
                pid_param2,
                pid_param3,
                duration,
            )
            if success:
                _update_flag_memory(cmd_id, laser_id)
                _log_state_snapshot(laser_id)

            mem_locked, mem_system_on, mem_configured = _expected_flags(laser_id)
            conn.sendall(ACK_OK if success else ACK_ERROR)
            logger.info(
                "CMD %-14s | laser_id=%d | rx(lock=%d sys=%d cfg=%d) | mem(lock=%d sys=%d cfg=%d) | p1=%d p2=%d p3=%d dur=%d | ack=%s",
                cmd_name,
                laser_id,
                1 if laser_locked_flag else 0,
                1 if system_on_flag else 0,
                1 if laser_configured_flag else 0,
                1 if mem_locked else 0,
                1 if mem_system_on else 0,
                1 if mem_configured else 0,
                pid_param1,
                pid_param2,
                pid_param3,
                duration,
                "OK" if success else "ERROR",
            )

    except socket.timeout:
        logger.warning("Connection from %s:%d timed out.", *addr)
    except OSError as exc:
        logger.error("Socket error with %s:%d: %s", *addr, exc)
    finally:
        conn.close()

# ---------------------------------------------------------------------------
# Main server loop
# ---------------------------------------------------------------------------

_running = True

def _handle_sigint(sig, frame):
    global _running
    logger.info("Shutdown signal received.")
    _running = False

def main():
    signal.signal(signal.SIGINT,  _handle_sigint)
    signal.signal(signal.SIGTERM, _handle_sigint)

    logger.info(
        "PYNQ server starting | %s:%d | packet=%dB",
        HOST, PORT, PACKET_SIZE,
    )

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as srv:
        srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        srv.bind((HOST, PORT))
        srv.listen(1)
        srv.settimeout(1.0)   # allows the _running flag to be checked each second
        logger.info("Listening on %s:%d …", HOST, PORT)

        while _running:
            try:
                conn, addr = srv.accept()
            except socket.timeout:
                continue   # check _running and loop
            except OSError:
                break

            handle_connection(conn, addr)

    logger.info("Server stopped.")


if __name__ == "__main__":
    main()
