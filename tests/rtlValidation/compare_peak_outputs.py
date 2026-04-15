import csv
import argparse
import os
import sys


def read_rows(path):
    with open(path, "r", newline="") as f:
        return list(csv.DictReader(f))


def to_int_series(rows, key):
    return [int(r[key]) for r in rows]


def plot_comparison(expected, dut, output_path=None, show_plot=True):
    import matplotlib.pyplot as plt

    scans = to_int_series(expected, "scan_idx")
    channels = ["l1_position", "l2_position", "l3_position", "l4_position"]

    fig, axes = plt.subplots(2, 1, figsize=(12, 8), sharex=True)

    for ch in channels:
        exp_vals = to_int_series(expected, ch)
        dut_vals = to_int_series(dut, ch)

        axes[0].plot(scans, exp_vals, marker="o", linewidth=1.5, label=f"{ch} expected")
        axes[0].plot(
            scans,
            dut_vals,
            linestyle="--",
            marker="x",
            linewidth=1.2,
            label=f"{ch} dut",
        )

        err = [d - e for d, e in zip(dut_vals, exp_vals)]
        axes[1].plot(scans, err, marker=".", linewidth=1.2, label=f"{ch} error")

    axes[0].set_ylabel("Ramp Position")
    axes[0].set_title("Peak Positions: Python Expected vs Verilog DUT")
    axes[0].grid(True, alpha=0.3)
    axes[0].legend(ncol=2, fontsize=8)

    axes[1].axhline(0, color="black", linewidth=1)
    axes[1].set_xlabel("Scan Index")
    axes[1].set_ylabel("Position Error (dut - expected)")
    axes[1].set_title("Per-Scan Position Error")
    axes[1].grid(True, alpha=0.3)
    axes[1].legend(ncol=2, fontsize=8)

    plt.tight_layout()

    if output_path:
        plt.savefig(output_path, dpi=150)
        print(f"Saved plot: {output_path}")

    if show_plot:
        plt.show()
    else:
        plt.close(fig)


def parse_args():
    parser = argparse.ArgumentParser(description="Compare DUT peak outputs against Python golden outputs")
    parser.add_argument(
        "--plot",
        action="store_true",
        help="Generate a visual comparison plot of expected vs DUT positions",
    )
    parser.add_argument(
        "--save-plot",
        type=str,
        default=None,
        help="Optional output image path for the plot (e.g. hardware/rtl/vectors/peak_compare.png)",
    )
    parser.add_argument(
        "--no-show",
        action="store_true",
        help="Do not open an interactive plot window (useful for headless runs)",
    )
    return parser.parse_args()


def main():
    args = parse_args()

    repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
    vectors_dir = os.path.join(repo_root, "hardware", "rtl", "vectors")

    expected_path = os.path.join(vectors_dir, "peak_expected.csv")
    dut_path = os.path.join(vectors_dir, "peak_dut_outputs.csv")

    if not os.path.exists(expected_path):
        print(f"Missing expected file: {expected_path}")
        sys.exit(1)

    if not os.path.exists(dut_path):
        print(f"Missing DUT output file: {dut_path}")
        sys.exit(1)

    expected = read_rows(expected_path)
    dut = read_rows(dut_path)

    if len(expected) != len(dut):
        print(f"Row count mismatch: expected={len(expected)} dut={len(dut)}")
        sys.exit(1)

    mismatches = []
    for i, (e, d) in enumerate(zip(expected, dut)):
        for key in ["scan_idx", "l1_position", "l2_position", "l3_position", "l4_position"]:
            if int(e[key]) != int(d[key]):
                mismatches.append((i, key, int(e[key]), int(d[key])))

    if args.plot:
        plot_path = args.save_plot
        if plot_path is None:
            plot_path = os.path.join(vectors_dir, "peak_compare.png")
        plot_comparison(expected, dut, output_path=plot_path, show_plot=(not args.no_show))

    if mismatches:
        print(f"Found {len(mismatches)} mismatch(es):")
        for row_i, key, exp_val, dut_val in mismatches[:20]:
            print(f"  row={row_i} field={key} expected={exp_val} dut={dut_val}")
        return 1

    print("PASS: DUT outputs match Python golden results.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
