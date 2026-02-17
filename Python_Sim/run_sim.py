from simulation import Simulation
import matplotlib.pyplot as plt


def main():
    # Configure simulation
    # 5 seconds duration, 10ms time step (100Hz loop)
    sim = Simulation(duration=5.0, dt=0.01)

    # Run the simulation
    sim.run()

    # Visualize the results
    sim.plot_results()


if __name__ == "__main__":
    main()
