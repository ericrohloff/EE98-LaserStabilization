import argparse
import csv
import importlib.util
import os
import sys
from types import MethodType

import numpy as np

from simulation import Simulation


REF_TARGET_DEFAULT = 32000
L1_TARGET_DEFAULT = 12000
L2_TARGET_DEFAULT = 24000
L3_TARGET_DEFAULT = 40000
L4_TARGET_DEFAULT = 52000

L1_WAVELENGTH_DEFAULT = 600.0 + (L1_TARGET_DEFAULT / 63000.0) * 100.0
L2_WAVELENGTH_DEFAULT = 600.0 + (L2_TARGET_DEFAULT / 63000.0) * 100.0


def wavelength_to_ramp_pos(sim, wavelength):
    span = sim.cavity.end_wv_nm - sim.cavity.start_wv_nm
    if span <= 0:
        return 0
    ramp_pos = (float(wavelength) - sim.cavity.start_wv_nm) / span
    return int(np.clip(round(ramp_pos * 63000.0), 0, 63000))


def voltage_to_adc(voltage):
    return int(np.clip(round(float(voltage) * 100000.0), 0, 65535))


def control_voltage_to_u16(voltage, full_scale=10.0):
    signed = int(round((float(voltage) / full_scale) * 32768.0))
    signed = max(min(signed, 32767), -32768)
    return (signed + 32768) & 0xFFFF


def s16_from_float(value):
    v = int(round(value))
    if v > 32767:
        return 32767
    if v < -32768:
        return -32768
    return v


def u16_from_s16(value):
    return (value + 32768) & 0xFFFF


def load_pid_class(repo_root):
    controllers_path = os.path.join(repo_root, "tests", "pythonSim", "controllers.py")
    spec = importlib.util.spec_from_file_location("pythonsim_controllers", controllers_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Could not load controllers module from {controllers_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.PID


def instrument_simulation(sim):
    capture = {
        "scan_records": [],
        "pending_scan": None,
        "step_idx": 0,
        "pid_records": [],
    }

    original_perform_scan = sim.perform_scan
    original_assign_peaks = sim.assign_peaks

    def wrapped_perform_scan(self):
        scan_output, scan_range = original_perform_scan()
        capture["pending_scan"] = {
            "scan_idx": len(capture["scan_records"]),
            "scan_output": np.asarray(scan_output).copy(),
            "scan_range": np.asarray(scan_range).copy(),
        }
        return scan_output, scan_range

    def wrapped_assign_peaks(self, detected_peaks):
        assignments = original_assign_peaks(detected_peaks)
        pending = capture.get("pending_scan")
        if pending is not None:
            pending["detected_peaks"] = list(detected_peaks)
            pending["assignments"] = dict(assignments)
            capture["scan_records"].append(pending)
            capture["pending_scan"] = None
        return assignments

    sim.perform_scan = MethodType(wrapped_perform_scan, sim)
    sim.assign_peaks = MethodType(wrapped_assign_peaks, sim)
    return capture


def write_peak_vectors(sim, capture, vectors_dir):
    os.makedirs(vectors_dir, exist_ok=True)
    stim_path = os.path.join(vectors_dir, "peak_stimulus.csv")
    expected_path = os.path.join(vectors_dir, "peak_expected.csv")

    target_lasers = sim.controlled_lasers[:4]
    target_positions = [
        L1_TARGET_DEFAULT,
        L2_TARGET_DEFAULT,
        L3_TARGET_DEFAULT,
        L4_TARGET_DEFAULT,
    ]
    ref_target = REF_TARGET_DEFAULT

    with open(stim_path, "w", newline="") as f_stim:
        writer = csv.writer(f_stim)
        writer.writerow(
            [
                "cycle",
                "adc_sample",
                "adc_sample_valid",
                "current_ramp_pos",
                "ramp_start",
                "ref_target",
                "l1_target",
                "l2_target",
                "l3_target",
                "l4_target",
            ]
        )

        cycle = 0
        for record in capture["scan_records"]:
            scan_output = record["scan_output"]
            scan_range = record["scan_range"]

            for sample_idx, (sample, wavelength) in enumerate(zip(scan_output, scan_range)):
                writer.writerow(
                    [
                        cycle,
                        voltage_to_adc(sample),
                        1,
                        wavelength_to_ramp_pos(sim, wavelength),
                        1 if sample_idx == 0 else 0,
                        ref_target,
                        *target_positions,
                    ]
                )
                cycle += 1

    with open(expected_path, "w", newline="") as f_expected:
        writer = csv.writer(f_expected)
        writer.writerow(["scan_idx", "l1_position", "l2_position", "l3_position", "l4_position"])

        # Match DUT timing: row N reports outputs updated from scan N-1.
        last_positions = list(target_positions)
        for scan_idx, record in enumerate(capture["scan_records"]):
            writer.writerow([scan_idx, *last_positions])

            assignments = record.get("assignments", {})
            for laser_idx, laser in enumerate(target_lasers):
                peak_wl = assignments.get(laser.id)
                if peak_wl is not None:
                    last_positions[laser_idx] = wavelength_to_ramp_pos(sim, peak_wl)

    return stim_path, expected_path


def write_pid_vectors(sim, capture, vectors_dir, pid_laser_id=None):
    os.makedirs(vectors_dir, exist_ok=True)
    stim_path = os.path.join(vectors_dir, "pid_stimulus.csv")
    expected_path = os.path.join(vectors_dir, "pid_expected.csv")

    if not sim.controlled_lasers:
        raise ValueError("No controlled lasers available for PID vector export.")

    pid_laser = None
    if pid_laser_id is not None:
        pid_laser = next((laser for laser in sim.controlled_lasers if laser.id == pid_laser_id), None)
        if pid_laser is None:
            raise ValueError(f"Unknown --pid-laser-id: {pid_laser_id}")
    else:
        pid_laser = sim.controlled_lasers[0]

    controller = sim.controllers[pid_laser.id]
    pid_p_q16 = int(round(controller.Kp * (1 << 16)))
    pid_i_q16 = int(round(controller.Ki * (1 << 16)))
    pid_d_q16 = int(round(controller.Kd * (1 << 16)))

    measured_series = sim.history[pid_laser.id]["measured"]
    ref_series = sim.history[sim.reference_laser.id]["measured"]

    repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    pid_class = load_pid_class(repo_root)
    set_ramp = wavelength_to_ramp_pos(sim, controller.setpoint)
    ref_target_ramp = REF_TARGET_DEFAULT
    pid_model = pid_class(
        Kp=controller.Kp,
        Ki=controller.Ki,
        Kd=controller.Kd,
        setpoint=float(set_ramp - ref_target_ramp),
        output_limits=(-32768.0, 32767.0),
    )
    feedback_u16 = 0x8000

    with open(stim_path, "w", newline="") as f_stim:
        writer = csv.writer(f_stim)
        writer.writerow(
            [
                "step_idx",
                "ramp_start",
                "peak_valid",
                "laser_exists",
                "laser_locked",
                "set_wavelength",
                "current_wavelength",
                "ref_wavelength",
                "pid_p_q16",
                "pid_i_q16",
                "pid_d_q16",
            ]
        )

        for step_idx, (measured, ref_measured) in enumerate(zip(measured_series, ref_series)):
            assignments = capture["scan_records"][step_idx].get("assignments", {})
            peak_valid = 1 if assignments.get(pid_laser.id) is not None else 0
            current_wavelength = measured if measured is not None else pid_laser.freq
            ref_wavelength = ref_measured if ref_measured is not None else sim.reference_laser.freq
            current_ramp = wavelength_to_ramp_pos(sim, current_wavelength)
            ref_ramp = wavelength_to_ramp_pos(sim, ref_wavelength)

            laser_exists = 1
            laser_locked = 1
            ramp_start = 1

            if not laser_exists or not laser_locked:
                pid_model.reset()
                feedback_u16 = 0x8000
            elif ramp_start and peak_valid:
                measurement_ref = float(current_ramp - ref_ramp)
                control = pid_model.update(measurement_ref, sim.dt)
                feedback_u16 = u16_from_s16(s16_from_float(control))

            writer.writerow(
                [
                    step_idx,
                    ramp_start,
                    peak_valid,
                    laser_exists,
                    laser_locked,
                    set_ramp,
                    current_ramp,
                    ref_ramp,
                    pid_p_q16,
                    pid_i_q16,
                    pid_d_q16,
                ]
            )
            capture["pid_records"].append(
                {
                    "step_idx": step_idx,
                    "feedback_u16": feedback_u16,
                }
            )

    with open(expected_path, "w", newline="") as f_expected:
        writer = csv.writer(f_expected)
        writer.writerow(["step_idx", "feedback_u16"])
        for row in capture["pid_records"]:
            writer.writerow([row["step_idx"], row["feedback_u16"]])

    return stim_path, expected_path


def parse_args():
    parser = argparse.ArgumentParser(
        description="Run simulation and export RTL validation vectors (peak + PID)."
    )
    parser.add_argument("--file", type=str, help="Path to oscilloscope CSV file for replay")
    parser.add_argument("--duration", type=float, default=5.0, help="Simulation duration in seconds")
    parser.add_argument("--ref", type=float, default=650.0, help="Reference laser wavelength in nm")
    parser.add_argument(
        "--starts",
        type=float,
        nargs="+",
        default=[L1_WAVELENGTH_DEFAULT, L2_WAVELENGTH_DEFAULT],
        help="Initial wavelengths for controllable lasers",
    )
    parser.add_argument(
        "--targets",
        type=float,
        nargs="+",
        default=[L1_WAVELENGTH_DEFAULT, L2_WAVELENGTH_DEFAULT],
        help="Target wavelengths for controllable lasers",
    )
    parser.add_argument(
        "--pid-laser-id",
        type=str,
        default=None,
        help="Laser ID for PID vector export (default: first controllable laser)",
    )
    parser.add_argument(
        "--vectors-dir",
        type=str,
        default=None,
        help="Output directory for vectors (default: hardware/rtl/vectors)",
    )
    return parser.parse_args()


def main():
    args = parse_args()

    if args.file and not os.path.exists(args.file):
        print(f"Error: File {args.file} not found.")
        return 1

    if len(args.starts) != len(args.targets):
        print(
            f"Error: --starts has {len(args.starts)} values but --targets has {len(args.targets)} values."
        )
        return 1

    if not (1 <= len(args.starts) <= 4):
        print("Error: please provide between 1 and 4 controllable lasers.")
        return 1

    dt = 0.01
    sim = Simulation(
        duration=args.duration,
        dt=dt,
        data_filepath=args.file,
        ref_wavelength=args.ref,
        starts=args.starts,
        targets=args.targets,
    )

    capture = instrument_simulation(sim)
    sim.run()

    repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    vectors_dir = args.vectors_dir or os.path.join(repo_root, "hardware", "rtl", "vectors")

    peak_stim, peak_expected = write_peak_vectors(sim, capture, vectors_dir)
    pid_stim, pid_expected = write_pid_vectors(sim, capture, vectors_dir, pid_laser_id=args.pid_laser_id)

    print(f"Exported peak stimulus: {peak_stim}")
    print(f"Exported peak expected: {peak_expected}")
    print(f"Exported PID stimulus: {pid_stim}")
    print(f"Exported PID expected: {pid_expected}")
    print("Next: run RTL testbenches, then compare scripts with --plot.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
