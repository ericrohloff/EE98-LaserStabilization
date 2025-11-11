import threading
import time
from cavity import Cavity
from laser import SimLaser
import numpy as np
from matplotlib import pyplot as plt

end_sim = threading.Event()
scanning = False

cavity = Cavity(535, 820)  # example cavity range
vouts = []
cavity_values = []

def run_simulation():
    global scanning
    while not end_sim.is_set():
        if scanning:
            # Simulation logic would go here
            cavity.ramp(10, 1e6)  # Example ramp call
            vouts.append(cavity.v_out)
            cavity_values.append(cavity.curr_pos_nm)

def handle_command(command: str):
    global scanning
    parts = command.strip().split()
    if not parts:
        return
    
    cmd = parts[0].lower()

    if cmd == 'exit':
        print("Exiting simulation...")
        end_sim.set()

    elif cmd == 'lock':
        if len(parts) != 2:
            print("Usage: lock <laser_id>")
            return
        laser_id = parts[1]
        print(f"Locking laser {laser_id}...")
        # TODO: Call API to lock the laser
        pass

    elif cmd == 'unlock':
        if len(parts) != 2:
            print("Usage: unlock <laser_id>")
            return
        laser_id = parts[1]
        print(f"Unlocking laser {laser_id}...")
        # TODO: Call API to lock the laser
        pass

    elif cmd == 'start_cavity_scan':
        if len(parts) != 2:
            print("Usage: start_cavity_scan <duration>")
            return
        duration = float(parts[1])
        scanning = True
        print(f"Starting cavity scan for {duration} seconds...")
        # TODO: Call API to lock the laser
        pass


    elif cmd == 'stop_cavity_scan':
        if len(parts) != 2:
            print("Usage: stop_cavity_scan <duration>")
            return
        duration = float(parts[1])
        scanning = False
        print(f"Stopping cavity scan for {duration} seconds...")
        # TODO: Call API to lock the laser
        pass

    elif cmd == 'create_laser':
        if len(parts) != 3:
            print("Usage: create_laser <laser_id> <frequency>")
            return
        laser_id = parts[1]
        frequency = float(parts[2])
        cavity.add_laser(SimLaser(laser_id, frequency, 1.0))
        
        print(f"Creating laser {laser_id} with frequency {frequency}...")
        # TODO: Call API to lock the laser
        pass

    else:
        print(f"Unknown command: {cmd}")


def main():
    print("Starting Laser Simulation...")
    
    # start background simulation thread
    worker_thread = threading.Thread(target=run_simulation)
    worker_thread.start()

    while not end_sim.is_set():
        try:
            command = input("Enter command: ")
            handle_command(command)
        except KeyboardInterrupt:
            print("Stopping simulation...")
            end_sim.set()

    worker_thread.join()

    times = np.linspace(0, len(vouts) * 1e-6, len(vouts))
    
    print("Simulation Stopped")
    
    plt.figure(figsize=(10,6))

    # Plot v_out vs cavity position
    plt.subplot(3, 1, 1)
    plt.plot(cavity_values, vouts, lw=0.5)
    plt.xlabel("Cavity Position (nm)")
    plt.ylabel("V_out")
    plt.title("Cavity Output vs Cavity Position")
    plt.ylim(-0.1, 1.1)
    plt.grid(True)

    # Plot cavity position vs time
    plt.subplot(3, 1, 2)
    plt.plot(times, cavity_values, lw=0.5, color='orange')
    plt.xlabel("Time (s)")
    plt.ylabel("Cavity Position (nm)")
    plt.title("Cavity Position vs Time")
    plt.grid(True)

    # Plot v_out vs time
    plt.subplot(3, 1, 3)
    plt.plot(times, vouts, lw=0.5, color='green')
    plt.xlabel("Time (s)")
    plt.ylabel("V_out")
    plt.title("Cavity Output vs Time")
    plt.ylim(-0.01, 0.1)
    plt.grid(True)

    plt.tight_layout()
    # plt.savefig("cavityPlot.png")
    plt.show()

    print("Simulation ended.")

if __name__ == "__main__":
    main()