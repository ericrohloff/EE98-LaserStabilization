import argparse
import csv
import importlib.util
import os
import random
import sys


def s16_from_float(value):
    v = int(round(value))
    if v > 32767:
        return 32767
    if v < -32768:
        return -32768
    return v


def u16_from_s16(value):
    return (value + 32768) & 0xFFFF


def parse_args():
    parser = argparse.ArgumentParser(description="Generate PID stimulus and Python expected outputs")
    parser.add_argument("--steps", type=int, default=240, help="Number of timeline steps to generate")
    parser.add_argument("--seed", type=int, default=98, help="Random seed for reproducibility")
    parser.add_argument("--setpoint", type=int, default=24000, help="Set wavelength in ramp-position units")
    parser.add_argument("--reference", type=int, default=32000, help="Reference wavelength in ramp-position units")
    parser.add_argument("--kp", type=float, default=1.20, help="Kp (float model)")
    parser.add_argument("--ki", type=float, default=0.06, help="Ki (float model)")
    parser.add_argument("--kd", type=float, default=0.20, help="Kd (float model)")
    parser.add_argument("--dt", type=float, default=1.0, help="dt for Python PID update")
    return parser.parse_args()


def main():
    args = parse_args()

    repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
    vectors_dir = os.path.join(repo_root, "hardware", "rtl", "vectors")
    os.makedirs(vectors_dir, exist_ok=True)

    # Reuse the existing Python PID implementation as the golden behavior.
    controllers_path = os.path.join(repo_root, "tests", "pythonSim", "controllers.py")
    spec = importlib.util.spec_from_file_location("pythonsim_controllers", controllers_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Could not load controllers module from {controllers_path}")
    controllers_module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(controllers_module)
    PID = controllers_module.PID

    random.seed(args.seed)

    stim_path = os.path.join(vectors_dir, "pid_stimulus.csv")
    expected_path = os.path.join(vectors_dir, "pid_expected.csv")

    # Coefficients represented as Q16.16 for downstream RTL vector replay.
    pid_p_q16 = int(round(args.kp * (1 << 16)))
    pid_i_q16 = int(round(args.ki * (1 << 16)))
    pid_d_q16 = int(round(args.kd * (1 << 16)))

    set_minus_ref = args.setpoint - args.reference

    pid = PID(
        Kp=args.kp,
        Ki=args.ki,
        Kd=args.kd,
        setpoint=float(set_minus_ref),
        output_limits=(-32768.0, 32767.0),
    )

    feedback_u16 = 0x8000
    expected_rows = []

    with open(stim_path, "w", newline="") as f_stim:
        w = csv.writer(f_stim)
        w.writerow(
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

        current = args.setpoint - 200

        for step in range(args.steps):
            ramp_start = 1

            # Peak-valid dropout windows to test hold behavior.
            peak_valid = 0 if (40 <= step < 55 or 130 <= step < 140) else 1

            # Lock/liveness disturbance windows to test reset behavior.
            laser_exists = 0 if (170 <= step < 176) else 1
            laser_locked = 0 if (90 <= step < 96) else 1

            # Create measurement drift + disturbance + noise in ramp-position units.
            if step in (30, 85, 145):
                current += random.choice([-900, 900])

            current += int(round((args.setpoint - current) * 0.08))
            current += random.randint(-40, 40)

            if current < 0:
                current = 0
            if current > 65535:
                current = 65535

            w.writerow(
                [
                    step,
                    ramp_start,
                    peak_valid,
                    laser_exists,
                    laser_locked,
                    args.setpoint,
                    current,
                    args.reference,
                    pid_p_q16,
                    pid_i_q16,
                    pid_d_q16,
                ]
            )

            # Mirror intended laser_controller update policy.
            if not laser_exists or not laser_locked:
                pid.reset()
                feedback_u16 = 0x8000
            elif ramp_start and peak_valid:
                measurement_ref = float(current - args.reference)
                control = pid.update(measurement_ref, args.dt)
                feedback_u16 = u16_from_s16(s16_from_float(control))

            expected_rows.append([step, feedback_u16])

    with open(expected_path, "w", newline="") as f_exp:
        w = csv.writer(f_exp)
        w.writerow(["step_idx", "feedback_u16"])
        w.writerows(expected_rows)

    print(f"Wrote stimulus: {stim_path}")
    print(f"Wrote expected: {expected_path}")


if __name__ == "__main__":
    main()
