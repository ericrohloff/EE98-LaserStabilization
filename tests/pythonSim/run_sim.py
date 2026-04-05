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
    args = parser.parse_args()

    # Configure simulation
    # 10ms time step (100Hz loop)
    dt = 0.01

    data_file = args.file

    if data_file and not os.path.exists(data_file):
        print(f"Error: File {data_file} not found.")
        sys.exit(1)

    sim = Simulation(duration=args.duration, dt=dt, data_filepath=data_file)

    # Run the simulation
    sim.run()

    # Visualize the results
    sim.plot_results()

    # Plot detailed scan diagnostics (Ramp and Peak Detection)
    sim.plot_last_scan()


if __name__ == "__main__":
    main()
