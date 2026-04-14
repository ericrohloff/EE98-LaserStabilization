from simulation import Simulation
import argparse
import sys
import os


def main():
    parser = argparse.ArgumentParser(description="Run Laser Stabilization Simulation")
    parser.add_argument(
        "--file", type=str, help="Path to oscilloscope CSV file for testing"
    )
    parser.add_argument(
        "--duration", type=float, default=5.0, help="Simulation duration in seconds"
    )
    parser.add_argument("--ref", type=float, default=650.0,
                    help="Reference laser wavelength in nm")
    parser.add_argument(
        "--starts", type=float, nargs="+", default=[625.0, 675.0],
        help="Initial wavelengths for controllable lasers, e.g. --starts 625 675",
    )
    parser.add_argument(
        "--targets", type=float, nargs="+", default=[625.0, 675.0],
        help="Target wavelengths for controllable lasers, e.g. --targets 640 655",
    )
    args = parser.parse_args()

    # Configure simulation
    # 10ms time step (100Hz loop)
    dt = 0.01

    data_file = args.file

    if data_file and not os.path.exists(data_file):
        print(f"Error: File {data_file} not found.")
        sys.exit(1)

    if len(args.starts) != len(args.targets):
        print(
            f"Error: --starts has {len(args.starts)} values but --targets has {len(args.targets)} values."
        )
        sys.exit(1)

    if not (1 <= len(args.starts) <= 4):
        print("Error: please provide between 1 and 4 controllable lasers.")
        sys.exit(1)

    sim = Simulation(duration=args.duration, dt=dt, data_filepath=data_file,
                     ref_wavelength=args.ref, starts=args.starts,
                     targets=args.targets)

    # Run the simulation
    sim.run()

    # Visualize the results
    sim.plot_results()

    # Plot detailed scan diagnostics (Ramp and Peak Detection)
    sim.plot_last_scan()


if __name__ == "__main__":
    main()
