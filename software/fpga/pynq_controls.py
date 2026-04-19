"""
pynq_controls.py
----------------
Hardware abstraction layer for server-side PYNQ control logic.

This module centralizes board-specific interactions so server.py can stay focused
on packet parsing, protocol state, and socket handling.

Note:
- Register offsets, bitfields, and signal names are intentionally left as TODO.
- Replace TODO blocks when the hardware register map is finalized.
"""

from __future__ import annotations

import logging
from typing import Optional

from pynq import Overlay
import numpy as np
import time


LASER_SLOT_COUNT = 5
LASER_BLOCK_SIZE_BYTES = 0x14  # 5 x 32-bit registers per laser block
REG_STRIDE_BYTES = 0x04
GLOBAL_FLAGS_REG_ADDR = 25 * REG_STRIDE_BYTES  # slv_reg25


class PYNQControls:
    """Abstraction over PYNQ overlay interactions used by server.py."""

    def __init__(self, logger: Optional[logging.Logger] = None, overlay_path: Optional[str] = None) -> None:
        self._logger = logger or logging.getLogger("PYNQControls")
        self._overlay_path = overlay_path
        self._overlay = None

        # Optional local mirrors of hardware state.
        self._laser_configured = {}
        self._laser_locked = {}
        self._system_on = False

        self._overlay = Overlay("design_1_wrapper.bit")

    def _slot_base_addr(self, laser_id: int) -> int:
        if laser_id < 0 or laser_id >= LASER_SLOT_COUNT:
            raise ValueError(
                f"laser_id must be in range [0, {LASER_SLOT_COUNT - 1}], got {laser_id}")
        return int(self.compute_addr_offset(laser_id))

    @staticmethod
    def _u32(value: int) -> int:
        return int(value) & 0xFFFFFFFF

    @staticmethod
    def _u16(value: int) -> int:
        return int(value) & 0xFFFF

    def _write_reg(self, addr: int, value: int) -> None:
        self._overlay.axi_config_registers_0.write(
            int(addr) & 0xFF, self._u32(value))

    def _read_reg(self, addr: int) -> int:
        return int(self._overlay.axi_config_registers_0.read(int(addr) & 0xFF)) & 0xFFFFFFFF

    def _write_laser_set_wavelength(self, laser_id: int, set_wavelength: int) -> None:
        """Write set_wavelength (upper 16 bits) and preserve detected_wavelength (lower 16 bits)."""
        reg_addr = self._laser_reg_addr(laser_id, 0x10)
        current_word = self._read_reg(reg_addr)
        new_word = (self._u16(set_wavelength) << 16) | (current_word & 0xFFFF)
        self._write_reg(reg_addr, new_word)

    def _update_system_locked_flag(self) -> None:
        configured_ids = [lid for lid,
                          is_cfg in self._laser_configured.items() if is_cfg]
        system_locked = bool(configured_ids) and all(
            self._laser_locked.get(lid, False) for lid in configured_ids)

        flags = self._read_reg(GLOBAL_FLAGS_REG_ADDR)
        if system_locked:
            flags = flags | 0x2
        else:
            flags = flags & (~0x2)
        self._write_reg(GLOBAL_FLAGS_REG_ADDR, flags)

    @staticmethod
    def _pack_laser_ctrl_word(laser_id: int, exists: bool, locked: bool) -> int:
        return ((laser_id & 0x0F) | ((1 if exists else 0) << 4) | ((1 if locked else 0) << 5)) & 0x3F

    @staticmethod
    def _laser_block_index(laser_id: int) -> int:
        if laser_id < 0 or laser_id >= LASER_SLOT_COUNT:
            raise ValueError(
                f"laser_id must be in range [0, {LASER_SLOT_COUNT - 1}], got {laser_id}")
        return int(laser_id) * LASER_BLOCK_SIZE_BYTES

    def _laser_reg_addr(self, laser_id: int, reg_offset: int) -> int:
        return self._laser_block_index(laser_id) + int(reg_offset)

    def create_laser(
        self,
        laser_id: int,
        pid_param1: int,
        pid_param2: int,
        pid_param3: int,
        wavelength: int,
    ) -> bool:
        """Initialize a laser control path in hardware."""
        base_addr = self._slot_base_addr(laser_id)

        # slv_reg{0,5,10,15,20}: {id[3:0], exists[4], locked[5]}
        ctrl_word = self._pack_laser_ctrl_word(
            laser_id=laser_id, exists=True, locked=False)
        self._write_reg(base_addr + 0x00, ctrl_word)

        # slv_reg{1..3, 6..8, ...}: PID P/I/D
        self.configure_laser_pid(laser_id, pid_param1, pid_param2, pid_param3)

        self._write_laser_set_wavelength(laser_id, wavelength)

        self._laser_configured[laser_id] = True
        self._laser_locked[laser_id] = False
        self._update_system_locked_flag()
        self._logger.debug(
            "pynq_controls.create_laser | laser_id=%d p1=%d p2=%d p3=%d wavelength=%d",
            laser_id,
            pid_param1,
            pid_param2,
            pid_param3,
            wavelength,
        )
        return True

    def remove_laser(self, laser_id: int) -> bool:
        """Tear down a laser control path in hardware."""
        base_addr = self._slot_base_addr(laser_id)

        # Clear laser control and parameter registers for this slot.
        self._write_reg(base_addr + 0x00, 0)
        self._write_reg(base_addr + 0x04, 0)
        self._write_reg(base_addr + 0x08, 0)
        self._write_reg(base_addr + 0x0C, 0)
        self._write_reg(base_addr + 0x10, 0)

        self._laser_configured[laser_id] = False
        self._laser_locked[laser_id] = False
        self._update_system_locked_flag()
        self._logger.debug(
            "pynq_controls.remove_laser | laser_id=%d", laser_id)
        return True

    def configure_laser_pid(
        self,
        laser_id: int,
        pid_param1: int,
        pid_param2: int,
        pid_param3: int,
    ) -> bool:
        """Write PID parameters and mirror Python command value to set_wavelength."""
        base_addr = self._slot_base_addr(laser_id)

        # Keep address math in uint8 space, then convert to Python int for MMIO write.
        self._write_reg(base_addr + 0x04, pid_param1)
        self._write_reg(base_addr + 0x08, pid_param2)
        self._write_reg(base_addr + 0x0C, pid_param3)

        # Keep Python-commanded setpoint in set_wavelength register.
        self._write_laser_set_wavelength(laser_id, pid_param1)

        self._logger.debug(
            "pynq_controls.configure_laser_pid | laser_id=%d p1=%d p2=%d p3=%d",
            laser_id,
            pid_param1,
            pid_param2,
            pid_param3,
        )
        return True

    def set_laser_lock(self, laser_id: int, locked: bool, configured: bool) -> bool:
        """Enable or disable lock state for a laser in hardware."""
        base_addr = self._slot_base_addr(laser_id)

        # Update control word bits in slv_reg{0,5,10,15,20}.
        ctrl_word = self._pack_laser_ctrl_word(
            laser_id=laser_id,
            exists=bool(configured),
            locked=bool(locked),
        )
        self._write_reg(base_addr + 0x00, ctrl_word)

        self._laser_locked[laser_id] = bool(locked)
        self._laser_configured[laser_id] = bool(configured)
        if not configured:
            self._laser_configured[laser_id] = False
        self._update_system_locked_flag()
        self._logger.debug(
            "pynq_controls.set_laser_lock | laser_id=%d lock=%d cfg=%d",
            laser_id,
            1 if locked else 0,
            1 if configured else 0,
        )
        return True

    def start_cavity(self, duration: int) -> bool:
        """Start cavity scan logic in hardware."""
        # slv_reg25[0]=system_on, slv_reg25[1]=system_locked
        flags = self._read_reg(GLOBAL_FLAGS_REG_ADDR)
        flags = flags | 0x1
        self._write_reg(GLOBAL_FLAGS_REG_ADDR, flags)

        self._system_on = True
        self._logger.debug("pynq_controls.start_cavity | dur=%d", duration)
        return True

    def stop_cavity(self) -> bool:
        """Stop cavity scan logic in hardware."""
        # Clear system_on bit while preserving other global flag bits.
        flags = self._read_reg(GLOBAL_FLAGS_REG_ADDR)
        flags = flags & (~0x1)
        self._write_reg(GLOBAL_FLAGS_REG_ADDR, flags)

        self._system_on = False
        self._logger.debug("pynq_controls.stop_cavity")
        return True

    def request_adc_scan(self) -> list:
        """Requests a list of adc samples making up an entire scan."""
        # TODO: Calculate number of samples based on cavity scan config values
        NUM_SAMPLES = 500

        flags = self._read_reg(GLOBAL_FLAGS_REG_ADDR)
        flags = flags | 0b100
        self._write_reg(GLOBAL_FLAGS_REG_ADDR, flags)

        # TODO: better way to wait for scan to be complete
        time.sleep(0.05)
        values = []
        for i in range(0, NUM_SAMPLES):
            values.append(self._overlay.axi_bram_ctrl_0.read(i << 2))

        flags = self._read_reg(GLOBAL_FLAGS_REG_ADDR)
        flags = flags & (~0b100)
        self._write_reg(GLOBAL_FLAGS_REG_ADDR, flags)

        return values

    def read_laser_pid_param(self, laser_id: int, param_index: int) -> int:
        """Read PID parameter 1/2/3 for a given laser from MMIO."""
        if param_index not in (1, 2, 3):
            raise ValueError(
                f"param_index must be 1, 2, or 3, got {param_index}")

        reg_offset = 0x04 + (param_index - 1) * REG_STRIDE_BYTES
        value = self._read_reg(self._laser_reg_addr(laser_id, reg_offset))
        self._logger.debug(
            "pynq_controls.read_laser_pid_param | laser_id=%d param=%d value=%d",
            laser_id,
            param_index,
            value,
        )
        return value

    def read_laser_pid_p(self, laser_id: int) -> int:
        return self.read_laser_pid_param(laser_id, 1)

    def read_laser_pid_i(self, laser_id: int) -> int:
        return self.read_laser_pid_param(laser_id, 2)

    def read_laser_pid_d(self, laser_id: int) -> int:
        return self.read_laser_pid_param(laser_id, 3)

    def read_laser_set_wavelength(self, laser_id: int) -> int:
        """Read the programmed set wavelength field from the laser slot."""
        value = self._read_reg(self._laser_reg_addr(laser_id, 0x10))
        set_wavelength = (value >> 16) & 0xFFFF
        self._logger.debug(
            "pynq_controls.read_laser_set_wavelength | laser_id=%d value=%d",
            laser_id,
            set_wavelength,
        )
        return set_wavelength

    def read_laser_detected_wavelength(self, laser_id: int) -> int:
        """Read the detected wavelength field exposed by the RTL for a laser slot."""
        raw = self._read_reg(self._laser_reg_addr(laser_id, 0x10))
        detected_wavelength = raw & 0xFFFF
        self._logger.debug(
            "pynq_controls.read_laser_detected_wavelength | laser_id=%d value=%d",
            laser_id,
            detected_wavelength,
        )
        return detected_wavelength

    def read_laser_state(self, laser_id: int) -> dict:
        """Return the cached and hardware-backed state for one laser."""
        base_addr = self._slot_base_addr(laser_id)
        ctrl_word = self._read_reg(base_addr + 0x00)
        return {
            "laser_id": ctrl_word & 0x0F,
            "exists": bool((ctrl_word >> 4) & 0x01),
            "locked": bool((ctrl_word >> 5) & 0x01),
            "pid_p": self.read_laser_pid_p(laser_id),
            "pid_i": self.read_laser_pid_i(laser_id),
            "pid_d": self.read_laser_pid_d(laser_id),
            "set_wavelength": self.read_laser_set_wavelength(laser_id),
            "detected_wavelength": self.read_laser_detected_wavelength(laser_id),
        }

    def read_system_flags(self) -> dict:
        """Read global system flags from slv_reg25."""
        flags = self._read_reg(GLOBAL_FLAGS_REG_ADDR)
        result = {
            "system_on": bool(flags & 0x1),
            "system_locked": bool((flags >> 1) & 0x1),
        }
        self._logger.debug(
            "pynq_controls.read_system_flags | on=%d locked=%d",
            1 if result["system_on"] else 0,
            1 if result["system_locked"] else 0,
        )
        return result

    def compute_addr_offset(self, laser_id: int) -> np.uint8:
        """Compute MMIO address offset for a given laser and parameter.
           Each laser has 5 registers (1 config, 3 PID params, 1 duration) spaced 0x04 apart."""
        return np.uint8((laser_id * 5 * 0x04) & 0xFF)
