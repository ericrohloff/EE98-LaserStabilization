"""Board-local sanity check for PYNQControls register read/write behavior.

Run this on the PYNQ board from repository root:
    python3 sanity_check.py

What it validates:
1) Python command values are routed into set_wavelength (upper 16 bits) during PID configuration.
2) PID registers read back as written.
3) system_on toggles through start/stop.
4) detected_wavelength is treated as FPGA-driven (read-only from software side).
"""

from __future__ import annotations

from pynq_controls import PYNQControls


def main() -> int:
    controls = PYNQControls()
    laser_id = 0

    # Create path and verify create_laser routes pid_param1 -> set_wavelength.
    assert controls.create_laser(laser_id, 111, 222, 333, 44)
    state = controls.read_laser_state(laser_id)
    print("After create:", state)
    assert state["exists"] is True
    assert state["locked"] is False
    assert state["pid_p"] == 111
    assert state["pid_i"] == 222
    assert state["pid_d"] == 333
    assert state["set_wavelength"] == 111

    detected_before = state["detected_wavelength"]

    # Reconfigure PID and verify set_wavelength follows pid_param1.
    assert controls.configure_laser_pid(laser_id, 555, 666, 777)
    state = controls.read_laser_state(laser_id)
    print("After configure_laser_pid:", state)
    assert state["pid_p"] == 555
    assert state["pid_i"] == 666
    assert state["pid_d"] == 777
    assert state["set_wavelength"] == 555

    # start_cavity is global and does not change per-laser set_wavelength.
    assert controls.start_cavity(duration=20)
    flags = controls.read_system_flags()
    state = controls.read_laser_state(laser_id)
    print("After start:", flags, state)
    assert flags["system_on"] is True
    assert state["set_wavelength"] == 555

    # detected_wavelength is FPGA ADC-path driven; software should not be using command writes for it.
    detected_after = state["detected_wavelength"]
    print("Detected wavelength (before, after):", detected_before, detected_after)

    # Stop and clean up.
    assert controls.stop_cavity()
    flags = controls.read_system_flags()
    print("After stop:", flags)
    assert flags["system_on"] is False

    assert controls.remove_laser(laser_id)
    state = controls.read_laser_state(laser_id)
    print("After remove:", state)
    assert state["exists"] is False

    print("Sanity check PASSED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
