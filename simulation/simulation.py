import numpy as np
import matplotlib.pyplot as plt
import random
import pandas as pd
import itertools
from cavity import Cavity
from laser import Laser
from detectors import SimpleThresholdDetector
from controllers import PID


class Simulation:
    def __init__(self, duration=2.0, dt=0.01, data_filepath=None, ref_wavelength=650, laser_a_start=625, laser_a_target=625, laser_b_start=675, laser_b_target=675):
        self.duration = duration
        self.dt = dt  # Time step (represents one scan cycle)
        self.steps = int(duration / dt)
        self.data_filepath = data_filepath
        self.use_real_data = data_filepath is not None

        # Setup Simulation Objects
        # Range covers the laser wavelengths
        self.cavity = Cavity(600, 700)
        self.reference_laser = Laser("Ref", ref_wavelength)
        self.reference_laser.drift_enabled = False
        self.laser_a = Laser("A", laser_a_start)
        self.laser_b = Laser("B", laser_b_start)
        self.laser_a.target_wavelength = laser_a_target
        self.laser_b.target_wavelength = laser_b_target
        self.laser_a.drift_enabled = True
        self.laser_b.drift_enabled = True
        self.lasers = [self.reference_laser, self.laser_a, self.laser_b]
        self.controlled_lasers = [self.laser_a, self.laser_b]

        for laser in self.lasers:
            self.cavity.add_laser(laser)

        self.detector = SimpleThresholdDetector(threshold=0.02)

        # Integral Controller

        # Kp=0, Ki=5.0, Kd=0 (Tune Ki for performance)
        # Limits +/- 10V
        # Setpoint is the target wavelength (e.g., 650.0 nm)
        self.pid_a = PID(Kp=0, Ki=5.0, Kd=0.0,
                         setpoint=laser_a_target, output_limits=(-10.0, 10.0))
        self.pid_b = PID(Kp=0, Ki=5.0, Kd=0.0,
                         setpoint=laser_b_target, output_limits=(-10.0, 10.0))

        # Data storage
        self.time_data = []

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
            candidates = []

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
                        # We will collect all candidates first, then filter
                        candidates.append(
                            {
                                "time": time_col[segment_start_idx:segment_end_idx],
                                "signal": signal_col[segment_start_idx:segment_end_idx],
                            }
                        )
                        segment_start_idx = -1

            # Handle case where file ends during a segment
            if segment_start_idx != -1:
                candidates.append(
                    {
                        "time": time_col[segment_start_idx:],
                        "signal": signal_col[segment_start_idx:],
                    }
                )

            # Filter segments: Keep only those that are close to the maximum length found
            # This avoids partial scans at start/end of file
            if candidates:
                max_len = max(len(c["signal"]) for c in candidates)
                self.real_scan_segments = [
                    c for c in candidates if len(c["signal"]) > 0.8 * max_len
                ]

            print(
                f"Loaded {len(self.real_scan_segments)} valid scan segments from data (filtered from {len(candidates)})."
            )

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

            # ----- Baseline / background -----
            # DC offset at mV scale
            baseline_offset = np.random.normal(0.0, 0.001)

            # Small linear slope across the scan
            slope = np.random.normal(0.0, 0.0005) / (
                self.cavity.end_wv_nm - self.cavity.start_wv_nm
            )
            baseline = baseline_offset + slope * (scan_range - scan_range[0])

            # Etalon-like ripple / interference background
            ripple_amp = abs(np.random.normal(0.0008, 0.0003))    # ~0.8 mV typical
            ripple_period = np.random.uniform(0.5, 3.0)           # nm
            ripple_phase = np.random.uniform(0, 2 * np.pi)
            ripple = ripple_amp * np.sin(
                2 * np.pi * (scan_range - scan_range[0]) / ripple_period + ripple_phase
            )

            # ----- Noise -----
            # White detector/electronics noise: 1–2 mV range
            white_sigma = np.random.uniform(0.001, 0.002)
            white_noise = np.random.normal(0.0, white_sigma, size=scan_points)

            # Slightly correlated low-frequency noise
            colored_noise = np.cumsum(np.random.normal(0.0, 0.00003, size=scan_points))
            colored_noise -= np.mean(colored_noise)

            # Rare spikes/glitches
            spikes = np.zeros(scan_points)
            spike_mask = np.random.rand(scan_points) < 0.001
            spikes[spike_mask] = np.random.normal(0.0, 0.006, size=np.sum(spike_mask))

            scan_output = baseline + ripple + white_noise + colored_noise + spikes

            # Freeze laser parameters for this scan
            for laser in self.lasers:
                center, amplitude, gamma = laser.get_scan_parameters()
                amplitude = 0.0 if laser.is_blocked() else amplitude
                lorentzian = amplitude * (gamma / 2) / (
                    (scan_range - center) ** 2 + (gamma / 2) ** 2
                )
                scan_output += lorentzian

            return scan_output, scan_range
        
    def assign_peaks(self, detected_peaks):
        assignments = {"Ref": None, "A": None, "B": None}

        expected = {
            "Ref": self.reference_laser.freq,
            "A": self.laser_a.freq,
            "B": self.laser_b.freq,
        }

        names = ["Ref", "A", "B"]
        best_cost = float("inf")
        best_assignment = assignments.copy()

        # try assignments using up to 3 detected peaks
        for chosen_peaks in itertools.permutations(detected_peaks, min(len(detected_peaks), 3)):
            trial = {"Ref": None, "A": None, "B": None}
            cost = 0.0
            valid = True

            for name, peak in zip(names, chosen_peaks):
                err = abs(peak - expected[name])
                if err > 2.0:
                    valid = False
                    break
                trial[name] = peak
                cost += err

            if valid and cost < best_cost:
                best_cost = cost
                best_assignment = trial

        return best_assignment

    def slew_limit(self, new_u, old_u, max_step=0.25):
        return max(min(new_u, old_u + max_step), old_u - max_step)

    def run(self):
        print(f"Starting simulation for {self.duration}s with dt={self.dt}s...")

        current_time = 0.0

        # Per-laser history containers
        self.history = {
            "Ref": {"actual": [], "measured": []},
            "A": {"actual": [], "measured": [], "error": [], "control": []},
            "B": {"actual": [], "measured": [], "error": [], "control": []},
        }

        for _ in range(self.steps):
            # 1) Advance all lasers' internal state.
            # Ref has drift_enabled = False, so it will still process transient/block timers
            # without accumulating slow drift.
            for laser in self.lasers:
                laser.step_environment(self.dt)

            # 2) Global disturbances affecting the whole setup
            # Laser jump from table bump or other disturbance
            if random.random() < 0.005:
                for laser in self.lasers:
                    laser.trigger_fast_jump(random.uniform(-10.0, 10.0), duration=0.8)

            # Laser being blocked/losing reading
            if random.random() < 0.005:
                block_duration = random.choice([0.05, 0.15, 0.3])
                for laser in self.lasers:
                    laser.trigger_block(block_duration)

            # 3) Optional local disturbances on individual adjustable lasers
            if random.random() < 0.0015:
                self.laser_a.trigger_fast_jump(random.uniform(-0.8, 0.8), duration=0.01)

            if random.random() < 0.0015:
                self.laser_b.trigger_fast_jump(random.uniform(-0.8, 0.8), duration=0.01)

            if random.random() < 0.0005:
                self.laser_a.trigger_block(random.choice([0.01, 0.05]))

            if random.random() < 0.0005:
                self.laser_b.trigger_block(random.choice([0.01, 0.05]))

            # 4) Perform one shared cavity scan
            scan_output, scan_range = self.perform_scan()

            # 5) Detect and assign peaks
            peaks = self.detector.detect_peaks(scan_output, scan_range)
            assignments = self.assign_peaks(peaks)

            ref_meas = assignments["Ref"]
            a_meas = assignments["A"]
            b_meas = assignments["B"]

            # 6) Hold last valid measurement if a peak is missed
            if ref_meas is None and self.history["Ref"]["measured"]:
                ref_meas_for_log = self.history["Ref"]["measured"][-1]
            else:
                ref_meas_for_log = ref_meas

            if a_meas is None and self.history["A"]["measured"]:
                a_meas_for_log = self.history["A"]["measured"][-1]
            else:
                a_meas_for_log = a_meas

            if b_meas is None and self.history["B"]["measured"]:
                b_meas_for_log = self.history["B"]["measured"][-1]
            else:
                b_meas_for_log = b_meas

            # 7) Update control only when a valid peak was assigned
            if a_meas is not None:
                raw_a = self.pid_a.update(a_meas, self.dt)
                control_a = self.slew_limit(raw_a, self.laser_a.control_voltage, max_step=0.25)
                self.laser_a.control_voltage = control_a
            else:
                control_a = self.laser_a.control_voltage  # hold last output

            if b_meas is not None:
                raw_b = self.pid_b.update(b_meas, self.dt)
                control_b = self.slew_limit(raw_b, self.laser_b.control_voltage, max_step=0.25)
                self.laser_b.control_voltage = control_b
            else:
                control_b = self.laser_b.control_voltage  # hold last output

            # 8) Store diagnostics
            self.last_scan_data = {
                "scan_output": scan_output,
                "scan_range": scan_range,
                "detected_peaks": peaks,
                "assignments": assignments,
            }

            # 9) Log histories
            self.time_data.append(current_time)

            self.history["Ref"]["actual"].append(self.reference_laser.freq)

            self.history["A"]["actual"].append(self.laser_a.freq)
            self.history["A"]["control"].append(control_a)

            self.history["B"]["actual"].append(self.laser_b.freq)
            self.history["B"]["control"].append(control_b)

            self.history["Ref"]["measured"].append(ref_meas_for_log)

            self.history["A"]["measured"].append(a_meas_for_log)
            if a_meas_for_log is not None:
                self.history["A"]["error"].append(self.pid_a.setpoint - a_meas_for_log)
            else:
                self.history["A"]["error"].append(np.nan)

            self.history["B"]["measured"].append(b_meas_for_log)
            if b_meas_for_log is not None:
                self.history["B"]["error"].append(self.pid_b.setpoint - b_meas_for_log)
            else:
                self.history["B"]["error"].append(np.nan)

            current_time += self.dt

        print("Simulation complete.")
        print(f"Final A error: {self.history['A']['error'][-1]:.6f} nm")
        print(f"Final B error: {self.history['B']['error'][-1]:.6f} nm")
        print(f"Final A control voltage: {self.history['A']['control'][-1]:.6f} V")
        print(f"Final B control voltage: {self.history['B']['control'][-1]:.6f} V")

    def plot_results(self):
        if not self.time_data or not hasattr(self, "history"):
            print("No simulation history available to plot.")
            return

        fig, axes = plt.subplots(3, 1, figsize=(12, 10), sharex=True)

        # -----------------------------
        # 1) Actual wavelengths vs time
        # -----------------------------
        axes[0].plot(
            self.time_data,
            self.history["Ref"]["actual"],
            label="Reference",
            color="green",
            linewidth=2,
        )
        axes[0].plot(
            self.time_data,
            self.history["A"]["actual"],
            label="Laser A",
            color="blue",
            linewidth=2,
        )
        axes[0].plot(
            self.time_data,
            self.history["B"]["actual"],
            label="Laser B",
            color="orange",
            linewidth=2,
        )

        # Optional measured traces
        # axes[0].plot(
        #     self.time_data,
        #     self.history["Ref"]["measured"],
        #     "--",
        #     label="Reference Measured",
        #     alpha=0.8,
        # )
        # axes[0].plot(
        #     self.time_data,
        #     self.history["A"]["measured"],
        #     "--",
        #     label="Laser A Measured",
        #     alpha=0.8,
        # )
        # axes[0].plot(
        #     self.time_data,
        #     self.history["B"]["measured"],
        #     "--",
        #     label="Laser B Measured",
        #     alpha=0.8,
        # )

        # # Target lines for controlled lasers
        # axes[0].axhline(
        #     self.laser_a.target_wavelength,
        #     linestyle=":",
        #     linewidth=2,
        #     label=f"Laser A Target ({self.laser_a.target_wavelength:.3f} nm)",
        # )
        # axes[0].axhline(
        #     self.laser_b.target_wavelength,
        #     linestyle=":",
        #     linewidth=2,
        #     label=f"Laser B Target ({self.laser_b.target_wavelength:.3f} nm)",
        # )

        axes[0].set_ylabel("Wavelength (nm)")
        axes[0].set_title("Laser Wavelengths vs Time")
        axes[0].grid(True)
        axes[0].legend(loc="best", ncol=2)

        # -----------------------------
        # 2) Error traces
        # -----------------------------
        axes[1].plot(
            self.time_data,
            self.history["A"]["error"],
            label="Laser A Error",
            linewidth=2,
        )
        axes[1].plot(
            self.time_data,
            self.history["B"]["error"],
            label="Laser B Error",
            linewidth=2,
        )
        axes[1].axhline(0.0, linestyle="--", linewidth=1)

        axes[1].set_ylabel("Error (nm)")
        axes[1].set_title("Control Error (Target - Measured)")
        axes[1].grid(True)
        axes[1].legend(loc="best")

        # -----------------------------
        # 3) Control voltages
        # -----------------------------
        axes[2].plot(
            self.time_data,
            self.history["A"]["control"],
            label="Laser A Control Voltage",
            linewidth=2,
        )
        axes[2].plot(
            self.time_data,
            self.history["B"]["control"],
            label="Laser B Control Voltage",
            linewidth=2,
        )
        axes[2].axhline(0.0, linestyle="--", linewidth=1)

        axes[2].set_ylabel("Control Voltage (V)")
        axes[2].set_xlabel("Time (s)")
        axes[2].set_title("PID Outputs")
        axes[2].grid(True)
        axes[2].legend(loc="best")

        plt.tight_layout()
        plt.show()

    def plot_last_scan(self):
        """
        Plot the last scan in three views:
        1) output vs wavelength
        2) wavelength ramp vs time within the scan
        3) output vs time within the scan

        Marks all detected peaks plus the assigned peaks for Ref, A, and B.
        """
        if not self.last_scan_data:
            print("No scan data available to plot.")
            return

        scan_output = self.last_scan_data.get("scan_output", [])
        scan_range = self.last_scan_data.get("scan_range", [])
        detected_peaks = self.last_scan_data.get("detected_peaks", [])
        assignments = self.last_scan_data.get("assignments", {})

        if len(scan_output) == 0 or len(scan_range) == 0:
            print("Last scan data is empty.")
            return

        scan_time = np.linspace(0, self.dt, len(scan_range))

        fig, axes = plt.subplots(3, 1, figsize=(12, 10))

        # --------------------------------------
        # 1) Cavity Output vs Wavelength
        # --------------------------------------
        axes[0].plot(scan_range, scan_output, label="Cavity Output", linewidth=2)

        # Mark all detected peaks
        # detected_label_used = False
        # for peak_wl in detected_peaks:
        #     idx = np.abs(scan_range - peak_wl).argmin()
        #     axes[0].plot(
        #         peak_wl,
        #         scan_output[idx],
        #         "rx",
        #         markersize=8,
        #         label="Detected Peak" if not detected_label_used else None,
        #     )
        #     detected_label_used = True

        # Mark assignments
        assignment_styles = {
            "Ref": {"marker": "o", "label": "Assigned Ref Peak"},
            "A": {"marker": "s", "label": "Assigned A Peak"},
            "B": {"marker": "^", "label": "Assigned B Peak"},
        }

        for name, peak_wl in assignments.items():
            if peak_wl is None:
                continue
            idx = np.abs(scan_range - peak_wl).argmin()
            style = assignment_styles.get(name, {"marker": "o", "label": f"{name} Peak"})
            axes[0].plot(
                peak_wl,
                scan_output[idx],
                linestyle="None",
                marker=style["marker"],
                markersize=10,
                label=style["label"],
            )

        axes[0].set_xlabel("Cavity Position / Wavelength (nm)")
        axes[0].set_ylabel("Output (V)")
        axes[0].set_title("Last Scan: Output vs Wavelength")
        axes[0].grid(True)
        axes[0].legend(loc="best")

        # --------------------------------------
        # 2) Ramp Signal: Wavelength vs Time
        # --------------------------------------
        axes[1].plot(scan_time, scan_range, label="Cavity Ramp", linewidth=2)
        axes[1].set_xlabel("Time within Scan (s)")
        axes[1].set_ylabel("Wavelength (nm)")
        axes[1].set_title("Last Scan: Ramp Signal")
        axes[1].grid(True)
        axes[1].legend(loc="best")

        # --------------------------------------
        # 3) Cavity Output vs Time within Scan
        # --------------------------------------
        axes[2].plot(scan_time, scan_output, label="PD Voltage", linewidth=2)

        # detected_label_used = False
        # for peak_wl in detected_peaks:
        #     if (self.cavity.end_wv_nm - self.cavity.start_wv_nm) == 0:
        #         continue

        #     t_peak = (
        #         (peak_wl - self.cavity.start_wv_nm)
        #         / (self.cavity.end_wv_nm - self.cavity.start_wv_nm)
        #         * self.dt
        #     )
        #     idx = np.abs(scan_range - peak_wl).argmin()

        #     axes[2].plot(
        #         t_peak,
        #         scan_output[idx],
        #         "rx",
        #         markersize=8,
        #         label="Detected Peak" if not detected_label_used else None,
        #     )
        #     detected_label_used = True

        for name, peak_wl in assignments.items():
            if peak_wl is None:
                continue
            if (self.cavity.end_wv_nm - self.cavity.start_wv_nm) == 0:
                continue

            t_peak = (
                (peak_wl - self.cavity.start_wv_nm)
                / (self.cavity.end_wv_nm - self.cavity.start_wv_nm)
                * self.dt
            )
            idx = np.abs(scan_range - peak_wl).argmin()
            style = assignment_styles.get(name, {"marker": "o", "label": f"{name} Peak"})

            axes[2].plot(
                t_peak,
                scan_output[idx],
                linestyle="None",
                marker=style["marker"],
                markersize=10,
                label=style["label"],
            )

        axes[2].set_xlabel("Time within Scan (s)")
        axes[2].set_ylabel("Voltage (V)")
        axes[2].set_title("Last Scan: Output vs Time")
        axes[2].grid(True)
        axes[2].legend(loc="best")

        plt.tight_layout()
        plt.show()