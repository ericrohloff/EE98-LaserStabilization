"""
pynq_server.py
--------------
Server-side script that runs on the PYNQ FPGA board.
Listens for a TCP connection from PYNQController, receives 21-byte binary
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
 ------  ----  -------  ------
   0      1    uint8    cmd_id
   1      4    int32    pid      (0 if unused by command)
   5      8    float64  param1   wavelength_nm  |  duration_s  |  0.0
  13      8    float64  param2   reserved (ignored)
  21 bytes total

ACK: 1 byte — 0x00 = ok, 0x01 = error
"""

import logging
import signal
import socket
import struct
from datetime import datetime

# ---------------------------------------------------------------------------
# Packet / protocol constants  (keep in sync with pynq_controller.py)
# ---------------------------------------------------------------------------

PACKET_FORMAT = "!Bidd"
PACKET_SIZE   = struct.calcsize(PACKET_FORMAT)   # 21 bytes

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

# ---------------------------------------------------------------------------
# Server config
# ---------------------------------------------------------------------------

HOST    = "0.0.0.0"
PORT    = 5000
TIMEOUT = 30.0   # seconds — client must send a packet within this window

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

def _setup_logger() -> logging.Logger:
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_file  = f"pynq_server_{timestamp}.log"

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

# ---------------------------------------------------------------------------
# FPGA overlay  (replace stubs with real pynq / overlay calls)
# ---------------------------------------------------------------------------

# Uncomment when running on the PYNQ board:
# from pynq import Overlay
# overlay = Overlay("your_design.bit")

def handle_create_laser(pid: int) -> bool:
    """Initialise a laser PID controller instance on the FPGA."""
    # TODO: overlay.laser_ctrl.create(pid)
    logger.debug("handle_create_laser | pid=%d", pid)
    return True

def handle_remove_laser(pid: int) -> bool:
    """De-register a laser PID controller instance."""
    # TODO: overlay.laser_ctrl.remove(pid)
    logger.debug("handle_remove_laser | pid=%d", pid)
    return True

def handle_lock_laser(pid: int, wavelength: float) -> bool:
    """Set target wavelength and enable closed-loop feedback for a laser."""
    # TODO: overlay.laser_ctrl.set_target(pid, wavelength)
    # TODO: overlay.laser_ctrl.enable_feedback(pid)
    logger.debug("handle_lock_laser | pid=%d | wavelength=%.4f nm", pid, wavelength)
    return True

def handle_unlock_laser(pid: int) -> bool:
    """Disable closed-loop feedback for a laser."""
    # TODO: overlay.laser_ctrl.disable_feedback(pid)
    logger.debug("handle_unlock_laser | pid=%d", pid)
    return True

def handle_start_cavity(duration: float) -> bool:
    """Start the triangular cavity ramp for a given duration (seconds)."""
    # TODO: overlay.cavity_ctrl.start(duration)
    logger.debug("handle_start_cavity | duration=%.2f s", duration)
    return True

def handle_stop_cavity() -> bool:
    """Stop the cavity ramp immediately."""
    # TODO: overlay.cavity_ctrl.stop()
    logger.debug("handle_stop_cavity")
    return True

# ---------------------------------------------------------------------------
# Dispatch table  (cmd_id -> callable)
# ---------------------------------------------------------------------------

def _dispatch(cmd_id: int, pid: int, param1: float) -> bool:
    """Route an unpacked command to the appropriate handler."""
    if cmd_id == CMD_CREATE_LASER:
        return handle_create_laser(pid)
    elif cmd_id == CMD_REMOVE_LASER:
        return handle_remove_laser(pid)
    elif cmd_id == CMD_LOCK_LASER:
        return handle_lock_laser(pid, param1)
    elif cmd_id == CMD_UNLOCK_LASER:
        return handle_unlock_laser(pid)
    elif cmd_id == CMD_START_CAVITY:
        return handle_start_cavity(param1)
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

            cmd_id, pid, param1, _param2 = struct.unpack(PACKET_FORMAT, data)
            cmd_name = CMD_NAMES.get(cmd_id, f"0x{cmd_id:02X}")
            logger.debug(
                "RX << cmd=%s pid=%d param1=%.6g",
                cmd_name, pid, param1,
            )

            success = _dispatch(cmd_id, pid, param1)
            conn.sendall(ACK_OK if success else ACK_ERROR)
            logger.info(
                "CMD %-14s | pid=%d | param1=%.6g | ack=%s",
                cmd_name, pid, param1, "OK" if success else "ERROR",
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
