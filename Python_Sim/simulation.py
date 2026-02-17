import numpy as np
import matplotlib.pyplot as plt
import random
import pandas as pd
from cavity import Cavity
from laser import Laser
from detectors import SimpleThresholdDetector
from controllers import PID


class Simulation:
    def __init__(self, duration=1.0, dt=0.01, data_filepath=None):
        self.duration = duration
        self.dt = dt  # Time step (represents one scan cycle)
        self.steps = int(duration / dt)
        self.data_filepath = data_filepath
        self.use_real_data = data_filepath is not None

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

        # Diagnostics
        self.last_scan_data = None

        # Real Data State
        self.real_scan_segments = []
        self.current_scan_index = 0

        if self.use_real_data:
            self.load_real_data()

    def load_real_data(self):
        """
        Loads the oscilloscope data and segments it into individual scans.
        """
        print(f"Loading real data from {self.data_filepath}...")
        try:
            df = pd.read_csv(self.data_filepath, skiprows=15)

            # Extract columns (using exact names from file check)
            # File has: TIME,CH1,CH2,CH3,CH4
            # We need TIME, CH2 (Trigger), CH3 (Signal)
            time_col = df["TIME"].to_numpy()
            trigger_col = df["CH2"].to_numpy()
            signal_col = df["CH3"].to_numpy()

            # Segment the data based on Trigger (CH2)
            # User says: Ramp UP while CH2 is 0V (Low).
            # Threshold: let's use 25V as in dataTesting.py

            is_low = trigger_col < 25.0

            # Find continuous segments of "Low"
            # Using simple state machine or diff

            # Identify transitions
            # A segment starts when we go High -> Low
            # A segment ends when we go Low -> High

            self.real_scan_segments = []

            segment_start_idx = -1

            for i in range(len(is_low)):
                if is_low[i]:
                    if segment_start_idx == -1:
                        segment_start_idx = i
                else:
                    if segment_start_idx != -1:
                        # Segment ended
                        segment_end_idx = i
                        # Store segment
                        # Only keep segments that are long enough to be valid scans
                        if (segment_end_idx - segment_start_idx) > 10:
                            self.real_scan_segments.append(
                                {
                                    "time": time_col[segment_start_idx:segment_end_idx],
                                    "signal": signal_col[
                                        segment_start_idx:segment_end_idx
                                    ],
                                }
                            )
                        segment_start_idx = -1

            # Handle case where file ends during a segment
            if segment_start_idx != -1:
                self.real_scan_segments.append(
                    {
                        "time": time_col[segment_start_idx:],
                        "signal": signal_col[segment_start_idx:],
                    }
                )

            print(f"Loaded {len(self.real_scan_segments)} scan segments from data.")

        except Exception as e:
            print(f"Error loading data: {e}")
            self.use_real_data = False

    def perform_scan(self):
        """
        Simulates one full scan of the cavity and returns the output trace.
        """
        if self.use_real_data and self.real_scan_segments:
            # Replay real data
            segment = self.real_scan_segments[self.current_scan_index]
            scan_output = segment["signal"]

            # Map time/indices to wavelength range
            # We arbitrarily map the duration of the recorded scan to the cavity range
            scan_points = len(scan_output)
            scan_range = np.linspace(
                self.cavity.start_wv_nm, self.cavity.end_wv_nm, scan_points
            )

            # Advance to next segment for next step, loop if needed
            self.current_scan_index = (self.current_scan_index + 1) % len(
                self.real_scan_segments
            )

            return scan_output, scan_range

        else:
            # Synthetic Simulation
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
                    l.amplitude
                    * (l.gamma / 2)
                    / ((pos - l.freq) ** 2 + (l.gamma / 2) ** 2)
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

            # Store data for diagnostics
            self.last_scan_data = {
                "scan_output": scan_output,
                "scan_range": scan_range,
                "detected_peaks": peaks,
            }

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

    def plot_last_scan(self):
        """
        Plots the details of the last scan cycle to validate detection.
        """
        if self.last_scan_data:
            detected_peaks = self.last_scan_data.get("detected_peaks", [])
            scan_output = self.last_scan_data.get("scan_output", [])
            scan_range = self.last_scan_data.get("scan_range", [])

            plt.figure(figsize=(10, 10))

            # 1. Cavity Output vs Position (Wavelength)
            plt.subplot(3, 1, 1)
            plt.plot(scan_range, scan_output, label="Cavity Output")
            # Mark detected peaks
            for peak_wl in detected_peaks:
                # Find closest index
                idx = (np.abs(scan_range - peak_wl)).argmin()
                # Use the ACTUAL output value at that index, not peak_wl
                plt.plot(
                    peak_wl,
                    scan_output[idx],
                    "rx",
                    markersize=10,
                    label="Detected Peak",
                )

            plt.xlabel("Cavity Position (Wavelength nm)")
            plt.ylabel("Output (V)")
            plt.title("Last Scan: Output vs Wavelength")
            plt.legend()
            plt.grid(True)

            # 2. Cavity Position vs Time (The Ramp)
            # Create a time axis for the scan (assuming linear ramp over dt)
            scan_time = np.linspace(0, self.dt, len(scan_range))

            plt.subplot(3, 1, 2)
            plt.plot(scan_time, scan_range, color="orange", label="Cavity Position")
            plt.xlabel("Time (s) within scan")
            plt.ylabel("Wavelength (nm)")
            plt.title("Last Scan: Ramp Signal")
            plt.grid(True)

            # 3. Cavity Output vs Time (Simulated Scope Trace)
            plt.subplot(3, 1, 3)
            plt.plot(scan_time, scan_output, color="green", label="PD Voltage")
            # Mark detected peaks in time
            for peak_wl in detected_peaks:
                # Map wavelength back to time
                # time = (wl - start) / (end - start) * dt
                if (self.cavity.end_wv_nm - self.cavity.start_wv_nm) != 0:
                    t_peak = (
                        (peak_wl - self.cavity.start_wv_nm)
                        / (self.cavity.end_wv_nm - self.cavity.start_wv_nm)
                        * self.dt
                    )

                    # Find voltage
                    idx = (np.abs(scan_range - peak_wl)).argmin()
                    plt.plot(
                        t_peak, scan_output[idx], "bx", markersize=10, label="Peak"
                    )

            plt.xlabel("Time (s) within scan")
            plt.ylabel("Voltage (V)")
            plt.title("Last Scan: Output vs Time")
            plt.legend()
            plt.grid(True)

            plt.tight_layout()
            plt.show()


if __name__ == "__main__":
    sim = Simulation(duration=2.0, dt=0.01)  # Run for 2 seconds
    sim.run()
    sim.plot_results()
