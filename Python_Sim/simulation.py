import numpy as np
import matplotlib.pyplot as plt
import random
from cavity import Cavity
from laser import Laser
from detectors import SimpleThresholdDetector
from controllers import PID


class Simulation:
    def __init__(self, duration=1.0, dt=0.01):
        self.duration = duration
        self.dt = dt  # Time step (represents one scan cycle)
        self.steps = int(duration / dt)

        # Setup Simulation Objects
        # Range covers the laser wavelength (650nm)
        self.cavity = Cavity(640, 660)
        self.laser = Laser("Laser1", 650.0)  # Start at 650nm
        self.cavity.add_laser(self.laser)

        self.detector = SimpleThresholdDetector(threshold=0.02)

        # Integral Controller
        # Kp=0, Ki=50.0, Kd=0 (Tune Ki for performance)
        # Limits +/- 1V
        # Setpoint is the target wavelength (e.g., 650.0 nm)
        self.pid = PID(
            Kp=0.0,
            Ki=50.0,
            Kd=0.0,
            setpoint=self.laser.target_wavelength,
            output_limits=(-1.0, 1.0),
        )

        # Data storage
        self.time_data = []
        self.laser_wavelength_data = []
        self.error_data = []
        self.control_voltage_data = []
        self.peaks_detected = []  # List of (time, wavelength)

    def perform_scan(self):
        """
        Simulates one full scan of the cavity and returns the output trace.
        """
        scan_points = 2000  # increased resolution for better detection
        scan_range = np.linspace(
            self.cavity.start_wv_nm, self.cavity.end_wv_nm, scan_points
        )
        scan_output = []

        for pos in scan_range:
            # Calculate cavity output at this position
            # Ideally this logic belongs in Cavity, but for now we simulate the physics here
            val = 0

            # Noise Floor
            noise = random.gauss(0, 0.000_001)
            val += noise

            # Laser Peak
            # Note: Using l.freq (actual physics wavelength)
            l = self.laser
            lorentzian = (
                l.amplitude * (l.gamma / 2) / ((pos - l.freq) ** 2 + (l.gamma / 2) ** 2)
            )
            val += lorentzian

            scan_output.append(val)

        return scan_output, scan_range

    def run(self):
        print(f"Starting simulation for {self.duration}s with dt={self.dt}s...")

        current_time = 0.0

        for i in range(self.steps):
            # 1. Physics: Laser Drifts
            # Drift is random walk.
            self.laser.drift(magnitude=0.005)

            # 2. Physics: Perform Scan
            scan_output, scan_range = self.perform_scan()

            # 3. Detection: Find Peaks
            peaks = self.detector.detect_peaks(scan_output, scan_range)

            measured_wavelength = 0
            if len(peaks) > 0:
                # Take the strongest peak (or just the first one found)
                measured_wavelength = peaks[0]
                self.peaks_detected.append((current_time, measured_wavelength))
            else:
                # If missed, hold last known valid measurement
                if len(self.peaks_detected) > 0:
                    measured_wavelength = self.peaks_detected[-1][1]
                else:
                    measured_wavelength = self.laser.target_wavelength  # Fallback

            # 4. Control: Update PID
            # The PID inputs the MEASURED value and compares to SETPOINT
            control_signal = self.pid.update(measured_wavelength, self.dt)

            # 5. Apply Feedback
            self.laser.control_voltage = control_signal

            # 6. Log Data
            self.time_data.append(current_time)
            self.laser_wavelength_data.append(
                self.laser.freq
            )  # Actual physics wavelength
            self.error_data.append(
                self.laser.target_wavelength - measured_wavelength
            )  # Measured error
            self.control_voltage_data.append(control_signal)

            current_time += self.dt

        print("Simulation complete.")

        final_error = self.error_data[-1]
        print(f"Final Error: {final_error:.6f} nm")
        print(f"Final Control Voltage: {self.control_voltage_data[-1]:.6f} V")

    def plot_results(self):
        plt.figure(figsize=(10, 8))

        # 1. Wavelength vs Time
        plt.subplot(3, 1, 1)
        plt.plot(
            self.time_data,
            self.laser_wavelength_data,
            label="Actual Wavelength",
            color="blue",
        )
        plt.axhline(
            self.laser.target_wavelength, color="r", linestyle="--", label="Target"
        )
        plt.ylabel("Wavelength (nm)")
        plt.title("Laser Wavelength Locking")
        plt.legend()
        plt.grid(True)

        # 2. Error Signal
        plt.subplot(3, 1, 2)
        plt.plot(self.time_data, self.error_data, color="orange")
        plt.ylabel("Detected Error (nm)")
        plt.title("Error Signal (Target - Measured)")
        plt.grid(True)

        # 3. Control Voltage
        plt.subplot(3, 1, 3)
        plt.plot(self.time_data, self.control_voltage_data, color="green")
        plt.ylabel("Control Voltage (V)")
        plt.xlabel("Time (s)")
        plt.title("PID Output / Control Voltage")
        plt.ylim(-1.1, 1.1)
        plt.grid(True)

        plt.tight_layout()
        plt.show()


if __name__ == "__main__":
    sim = Simulation(duration=2.0, dt=0.01)  # Run for 2 seconds
    sim.run()
    sim.plot_results()
