import argparse
import csv
import os
import sys


def read_rows(path):
    with open(path, "r", newline="") as f:
        return list(csv.DictReader(f))


def to_int_series(rows, key):
    return [int(r[key]) for r in rows]


def parse_args():
    parser = argparse.ArgumentParser(description="Compare DUT PID outputs against Python golden outputs")
    parser.add_argument(
        "--plot",
        action="store_true",
        help="Generate visual comparison plot of expected vs DUT PID feedback",
    )
    parser.add_argument(
        "--save-plot",
        type=str,
        default=None,
        help="Optional output image path (default: hardware/rtl/vectors/pid_compare.png)",
    )
    parser.add_argument(
        "--no-show",
        action="store_true",
        help="Do not open an interactive plot window",
    )
    parser.add_argument(
        "--tolerance",
        type=int,
        default=48,
        help="Allowed absolute difference in u16 LSB (default: 48 for float-vs-fixed-point matching)",
    )
    return parser.parse_args()


def plot_comparison(expected, dut, output_path=None, show_plot=True):
    import matplotlib.pyplot as plt

    steps = to_int_series(expected, "step_idx")
    exp_vals = to_int_series(expected, "feedback_u16")
    dut_vals = to_int_series(dut, "feedback_u16")
    err = [d - e for d, e in zip(dut_vals, exp_vals)]

    fig, axes = plt.subplots(2, 1, figsize=(12, 8), sharex=True)

    axes[0].plot(steps, exp_vals, label="Expected (Python PID)", linewidth=1.8, marker="o")
    axes[0].plot(steps, dut_vals, label="DUT (RTL)", linewidth=1.4, linestyle="--", marker="x")
    axes[0].set_ylabel("Feedback (u16)")
    axes[0].set_title("PID Feedback Over Time")
    axes[0].grid(True, alpha=0.3)
    axes[0].legend()

    axes[1].axhline(0, color="black", linewidth=1)
    axes[1].plot(steps, err, label="Error (dut - expected)", linewidth=1.4, marker=".")
    axes[1].set_xlabel("Step Index")
    axes[1].set_ylabel("u16 LSB")
    axes[1].set_title("PID Output Error")
    axes[1].grid(True, alpha=0.3)
    axes[1].legend()

    plt.tight_layout()

    if output_path:
        plt.savefig(output_path, dpi=150)
        print(f"Saved plot: {output_path}")

    if show_plot:
        plt.show()
    else:
        plt.close(fig)


def main():
    args = parse_args()

    repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
    vectors_dir = os.path.join(repo_root, "hardware", "rtl", "vectors")

    expected_path = os.path.join(vectors_dir, "pid_expected.csv")
    dut_path = os.path.join(vectors_dir, "pid_dut_outputs.csv")

    if not os.path.exists(expected_path):
        print(f"Missing expected file: {expected_path}")
        print("Run tests/rtlValidation/generate_pid_vectors.py first.")
        return 1

    if not os.path.exists(dut_path):
        print(f"Missing DUT output file: {dut_path}")
        print("Generate RTL PID output log at this path, then rerun this comparator.")
        return 1

    expected = read_rows(expected_path)
    dut = read_rows(dut_path)

    if len(expected) != len(dut):
        print(f"Row count mismatch: expected={len(expected)} dut={len(dut)}")
        return 1

    mismatches = []
    abs_errors = []
    for i, (e, d) in enumerate(zip(expected, dut)):
        if int(e["step_idx"]) != int(d["step_idx"]):
            mismatches.append((i, "step_idx", int(e["step_idx"]), int(d["step_idx"])))
            continue

        exp_val = int(e["feedback_u16"])
        dut_val = int(d["feedback_u16"])
        err = abs(dut_val - exp_val)
        abs_errors.append(err)

        if err > args.tolerance:
            mismatches.append((i, "feedback_u16", exp_val, dut_val))

    if args.plot:
        plot_path = args.save_plot
        if plot_path is None:
            plot_path = os.path.join(vectors_dir, "pid_compare.png")
        plot_comparison(expected, dut, output_path=plot_path, show_plot=(not args.no_show))

    if abs_errors:
        max_err = max(abs_errors)
        mean_err = sum(abs_errors) / len(abs_errors)
        print(f"PID comparison stats: max_abs_err={max_err} mean_abs_err={mean_err:.3f} tolerance={args.tolerance}")

    if mismatches:
        print(f"Found {len(mismatches)} mismatch(es):")
        for row_i, key, exp_val, dut_val in mismatches[:20]:
            print(f"  row={row_i} field={key} expected={exp_val} dut={dut_val}")
        return 1

    print("PASS: DUT PID outputs are within tolerance against Python golden results.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
