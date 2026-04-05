# api.py
# Canonical FPGA interface — delegates to software/pynq_controller.py
#
# Commands supported:
#   createLaser(pid)                   -> PYNQController.create_laser(pid)
#   lock(pid, wavelength)              -> PYNQController.lock_laser(pid, wavelength)
#   unlock(pid)                        -> PYNQController.unlock_laser(pid)
#   start_cavity_scan(duration)        -> PYNQController.start_cavity(duration)
#   stop_cavity_scan()                 -> PYNQController.stop_cavity()

import pathlib
import sys

# Add software/ to path so pynq_controller can be imported from anywhere
_software_dir = pathlib.Path(__file__).parents[2] / "software"
sys.path.insert(0, str(_software_dir))

from pynq_controller import PYNQController, CommandType  # noqa: F401


class InterfaceAPI:
    """
    Thin wrapper around PYNQController that maps the original sim API surface
    to the TCP-based FPGA controller.

    Parameters
    ----------
    server_ip   : IP address of the PYNQ board.
    server_port : TCP port the PYNQ board is listening on.
    """

    def __init__(self, server_ip: str, server_port: int) -> None:
        self._ctrl = PYNQController(server_ip=server_ip, server_port=server_port)
        self._ctrl.connect()

    def createLaser(self, pid: int) -> bool:
        return self._ctrl.create_laser(pid)

    def lock(self, pid: int, wavelength: float) -> bool:
        return self._ctrl.lock_laser(pid, wavelength)

    def unlock(self, pid: int) -> bool:
        return self._ctrl.unlock_laser(pid)

    def start_cavity_scan(self, duration: float) -> bool:
        return self._ctrl.start_cavity(duration)

    def stop_cavity_scan(self) -> bool:
        return self._ctrl.stop_cavity()

    def disconnect(self) -> None:
        self._ctrl.disconnect()

    def __enter__(self) -> "InterfaceAPI":
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.disconnect()
