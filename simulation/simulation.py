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
    def __init__(self, duration=2.0, dt=0.01, data_filepath=None, ref_wavelength=650, starts=None, targets=None):
        self.duration = duration
        self.dt = dt  # Time step (represents one scan cycle)
        self.steps = int(duration / dt)
        self.data_filepath = data_filepath
        self.use_real_data = data_filepath is not None

        # Setup Simulation Objects
        # Range covers the laser wavelengths
        self.cavity = Cavity(600, 700)
        self.reference_laser = Laser("Ref", ref_wavelength, ref_wavelength)
        self.reference_laser.drift_enabled = False

        if starts is None:
            starts = [625.0, 675.0]
        if targets is None:
            targets = [625.0, 675.0]

        if len(starts) != len(targets):
            raise ValueError("controlled_starts and controlled_targets must have the same length")

        if not (1 <= len(starts) <= 4):
            raise ValueError("Number of controllable lasers must be between 1 and 4")

        # Integral Controller
        # Kp=0, Ki=5.0, Kd=0 (Tune Ki for performance)
        # Limits +/- 10V
        # Setpoint is the target wavelength (e.g., 650.0 nm)
        self.controllers = {}

        self.controlled_lasers = []

        for i, (start, target) in enumerate(zip(starts, targets), start=1):
            laser_id = f"L{i}"
            laser = Laser(laser_id, start, target)
            laser.drift_enabled = True

            self.controlled_lasers.append(laser)
            self.controllers[laser_id] = PID(Kp=0.0,Ki=5.0,Kd=0.0,
                setpoint=target, output_limits=(-10.0, 10.0))

        self.lasers = self.controlled_lasers + [self.reference_laser]

        for laser in self.lasers:
            self.cavity.add_laser(laser)

        self.detector = SimpleThresholdDetector(threshold=0.02)

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
        laser_ids = [laser.id for laser in self.lasers]
        expected = {laser.id: laser.freq for laser in self.lasers}
        assignments = {laser_id: None for laser_id in laser_ids}

        remaining_peaks = list(detected_peaks)

        # Assign in order of expected wavelength so nearby lasers don't fight as much
        ordered_ids = sorted(laser_ids, key=lambda lid: expected[lid])

        assignment_window = 2.0

        for laser_id in ordered_ids:
            if not remaining_peaks:
                break

            best_peak = min(remaining_peaks, key=lambda p: abs(p - expected[laser_id]))
            err = abs(best_peak - expected[laser_id])

            if err <= assignment_window:
                assignments[laser_id] = best_peak
                remaining_peaks.remove(best_peak)

        return assignments

    def slew_limit(self, new_u, old_u, max_step=0.25):
        return max(min(new_u, old_u + max_step), old_u - max_step)

    def run(self):
        print(f"Starting simulation for {self.duration}s with dt={self.dt}s...")

        current_time = 0.0

        # Per-laser history containers
        self.history = {
            self.reference_laser.id: {"actual": [], "measured": []}
        }

        for laser in self.controlled_lasers:
            self.history[laser.id] = {
                "actual": [],
                "measured": [],
                "error": [],
                "control": [],
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
                    laser.trigger_fast_jump(random.uniform(-10.0, 10.0), duration=0.2)

            # Laser being blocked/losing reading
            if random.random() < 0.005:
                block_duration = random.choice([0.05, 0.15, 0.3])
                for laser in self.lasers:
                    laser.trigger_block(block_duration)

            # 3) Optional local disturbances on individual adjustable lasers
            for laser in self.controlled_lasers:
                if random.random() < 0.0015:
                    laser.trigger_fast_jump(random.uniform(-0.8, 0.8), duration=0.01)

                if random.random() < 0.0005:
                    laser.trigger_block(random.choice([0.01, 0.05]))

            # 4) Perform one shared cavity scan
            scan_output, scan_range = self.perform_scan()

            # 5) Detect and assign peaks
            peaks = self.detector.detect_peaks(scan_output, scan_range)
            assignments = self.assign_peaks(peaks)

            ref_meas = assignments.get(self.reference_laser.id)

            measured_for_log = {}
            measured_for_control = {}

            for laser in self.controlled_lasers:
                meas = assignments.get(laser.id)
                measured_for_control[laser.id] = meas

                if meas is None and self.history[laser.id]["measured"]:
                    measured_for_log[laser.id] = self.history[laser.id]["measured"][-1]
                else:
                    measured_for_log[laser.id] = meas

            if ref_meas is None and self.history[self.reference_laser.id]["measured"]:
                ref_meas_for_log = self.history[self.reference_laser.id]["measured"][-1]
            else:
                ref_meas_for_log = ref_meas

            # 7) Update control only when a valid peak was assigned
            control_values = {}

            for laser in self.controlled_lasers:
                meas = measured_for_control[laser.id]
                controller = self.controllers[laser.id]

                if meas is not None:
                    raw_u = controller.update(meas, self.dt)
                    control_u = self.slew_limit(raw_u, laser.control_voltage, max_step=0.25)
                    laser.control_voltage = control_u
                else:
                    control_u = laser.control_voltage

                control_values[laser.id] = control_u

            # 8) Store diagnostics
            self.last_scan_data = {
                "scan_output": scan_output,
                "scan_range": scan_range,
                "detected_peaks": peaks,
                "assignments": assignments,
            }

            # 9) Log histories
            self.time_data.append(current_time)

            self.history[self.reference_laser.id]["actual"].append(self.reference_laser.freq)
            self.history[self.reference_laser.id]["measured"].append(ref_meas_for_log)

            for laser in self.controlled_lasers:
                controller = self.controllers[laser.id]

                self.history[laser.id]["actual"].append(laser.freq)
                self.history[laser.id]["measured"].append(measured_for_log[laser.id])
                self.history[laser.id]["control"].append(control_values[laser.id])

                if measured_for_log[laser.id] is not None:
                    self.history[laser.id]["error"].append(
                        controller.setpoint - measured_for_log[laser.id]
                    )
                else:
                    self.history[laser.id]["error"].append(np.nan)

            current_time += self.dt

        print("Simulation complete.")
        for laser in self.controlled_lasers:
            print(f"Final {laser.id} error: {self.history[laser.id]['error'][-1]:.6f} nm")
            print(f"Final {laser.id} control voltage: {self.history[laser.id]['control'][-1]:.6f} V")

    def plot_results(self):
        if not self.time_data or not hasattr(self, "history"):
            print("No simulation history available to plot.")
            return

        fig, axes = plt.subplots(3, 1, figsize=(12, 10), sharex=True)

        # Actual wavelengths
        for laser in self.lasers:
            axes[0].plot(
                self.time_data,
                self.history[laser.id]["actual"],
                label=laser.id,
                linewidth=2,
            )

        axes[0].set_ylabel("Wavelength (nm)")
        axes[0].set_title("Laser Wavelengths vs Time")
        axes[0].grid(True)
        axes[0].legend(loc="best", ncol=2)

        # Errors
        for laser in self.controlled_lasers:
            axes[1].plot(
                self.time_data,
                self.history[laser.id]["error"],
                label=f"{laser.id} Error",
                linewidth=2,
            )
        axes[1].axhline(0.0, linestyle="--", linewidth=1)
        axes[1].set_ylabel("Error (nm)")
        axes[1].set_title("Control Error (Target - Measured)")
        axes[1].grid(True)
        axes[1].legend(loc="best")

        # Controls
        for laser in self.controlled_lasers:
            axes[2].plot(
                self.time_data,
                self.history[laser.id]["control"],
                label=f"{laser.id} Applied Control Voltage",
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

        Marks assigned peaks for all lasers currently in the simulation.
        """
        if not self.last_scan_data:
            print("No scan data available to plot.")
            return

        scan_output = self.last_scan_data.get("scan_output", [])
        scan_range = self.last_scan_data.get("scan_range", [])
        assignments = self.last_scan_data.get("assignments", {})
        detected_peaks = self.last_scan_data.get("detected_peaks", [])

        if len(scan_output) == 0 or len(scan_range) == 0:
            print("Last scan data is empty.")
            return

        scan_time = np.linspace(0, self.dt, len(scan_range))

        fig, axes = plt.subplots(3, 1, figsize=(12, 10))

        # Marker styles for variable number of lasers
        markers = ["o", "s", "^", "D", "P", "X", "*", "v"]
        laser_ids = [laser.id for laser in self.lasers]
        assignment_styles = {
            laser_id: {
                "marker": markers[i % len(markers)],
                "label": f"Assigned {laser_id} Peak",
            }
            for i, laser_id in enumerate(laser_ids)
        }

        # --------------------------------------
        # 1) Cavity Output vs Wavelength
        # --------------------------------------
        axes[0].plot(scan_range, scan_output, label="Cavity Output", linewidth=2)

        # Optional: show all detected peaks too
        # detected_label_used = False
        # for peak_wl in detected_peaks:
        #     idx = np.abs(scan_range - peak_wl).argmin()
        #     axes[0].plot(
        #         peak_wl,
        #         scan_output[idx],
        #         "rx",
        #         markersize=7,
        #         label="Detected Peak" if not detected_label_used else None,
        #     )
        #     detected_label_used = True

        # Assigned peaks
        for laser_id, peak_wl in assignments.items():
            if peak_wl is None:
                continue

            idx = np.abs(scan_range - peak_wl).argmin()
            style = assignment_styles.get(
                laser_id, {"marker": "o", "label": f"Assigned {laser_id} Peak"}
            )

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

        # Optional: show all detected peaks in time too
        detected_label_used = False
        span = self.cavity.end_wv_nm - self.cavity.start_wv_nm
        if span != 0:
            # for peak_wl in detected_peaks:
            #     t_peak = ((peak_wl - self.cavity.start_wv_nm) / span) * self.dt
            #     idx = np.abs(scan_range - peak_wl).argmin()

            #     axes[2].plot(
            #         t_peak,
            #         scan_output[idx],
            #         "rx",
            #         markersize=7,
            #         label="Detected Peak" if not detected_label_used else None,
            #     )
            #     detected_label_used = True

            for laser_id, peak_wl in assignments.items():
                if peak_wl is None:
                    continue

                t_peak = ((peak_wl - self.cavity.start_wv_nm) / span) * self.dt
                idx = np.abs(scan_range - peak_wl).argmin()
                style = assignment_styles.get(
                    laser_id, {"marker": "o", "label": f"Assigned {laser_id} Peak"}
                )

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