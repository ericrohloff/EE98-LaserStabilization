import random
import numpy as np

# TODO: make this work
class LaserController:
    def __init__(self, laser):
        self.laser = laser

    def compute_feedback(self, detected_freq):
        self.laser.modifier = self.laser.freq / detected_freq


class Laser:
    def __init__(self, id, wavelength, modifier=1.0):
        self.id = id
        self.base_wavelength = wavelength
        self.drift_offset = 0.0
        self.control_voltage = 0.0
        self.sensitivity = 3  # nm/V, adjust sensitivity as needed
        self.modifier = modifier
        self.drift_enabled = True

        self.target_wavelength = wavelength  # Default target to initial wavelength

        # lorentzian profile: A * (Γ/2) / [ (x - x₀)² + (Γ/2)² ]
        self.amplitude = random.uniform(0.02, 0.1)  # random amplitude on [20,100] mV

        # experimentally: took 2ms to scan 285nm w/ a detected gamma on
        # the order of [5,10]us. Dividing away the time to get a general
        # relationship for wavelength gives [.7125, 1.425] nm
        self.gamma = random.uniform(0.7125, 1.425)  # random width on 0.7125 to 1.425 nm

        # Adding stochastic state
        # slow drift state
        self.drift_velocity = 0.0     # nm/s
        self.drift_accel_sigma = 0.01 # nm/s^2 random acceleration

        # fast scan-to-scan center jitter
        self.scan_jitter_sigma = 0.01 # nm

        # Slow amplitude flicker
        self.amp_state = 0.0
        self.amp_tau = 0.5
        self.amp_sigma = 0.03

        # Slow linewidth flicker
        self.gamma_state = 0.0
        self.gamma_tau = 0.5
        self.gamma_sigma = 0.02

        # Transient offset to simulate ultra-fast jump
        self.transient_offset = 0.0
        self.transient_remaining = 0.0
        self.transient_decay = 0.2   # fraction left after each step

        # Temporary loss/block of peak
        self.blocked_remaining = 0.0


    @property
    def freq(self):
        # Return the actual current wavelength (calling it freq to maintain compatibility with cavity.py for now)
        # wavelength = base + drift + control
        return (
            self.base_wavelength
            + self.drift_offset
            + self.transient_offset
            + (self.control_voltage * self.sensitivity)
        )
    
    def trigger_fast_jump(self, jump_nm, duration=0.01):
        self.transient_offset += jump_nm
        self.transient_remaining = duration     # 10 ms time scale

    def trigger_block(self, duration_s):
        self.blocked_remaining = duration_s

    def is_blocked(self):
        return self.blocked_remaining > 0
    
    def step_environment(self, dt):
        # Update slow physical drift and slow parameter fluctuations once per control cycle.
        # Correlated drift: random acceleration integrated into velocity and position
        if self.drift_enabled:
            self.drift_velocity += np.random.normal(0.0, self.drift_accel_sigma) * np.sqrt(dt)
            self.drift_offset += self.drift_velocity * dt

        # Ornstein-Uhlenbeck style amplitude fluctuation
        self.amp_state += (-self.amp_state / self.amp_tau) * dt + np.random.normal(
            0.0, self.amp_sigma * np.sqrt(dt)
        )

        # Ornstein-Uhlenbeck style linewidth fluctuation
        self.gamma_state += (-self.gamma_state / self.gamma_tau) * dt + np.random.normal(
            0.0, self.gamma_sigma * np.sqrt(dt)
        )

        if self.transient_remaining > 0:
            self.transient_remaining -= dt
            self.transient_offset *= 0.1
            if (self.transient_remaining <= 0 or abs(self.transient_offset) < 0.0001):
                self.transient_offset = 0.0
                self.transient_remaining = 0.0

        if self.blocked_remaining > 0:
            self.blocked_remaining -= dt
            if self.blocked_remaining < 0:
                self.blocked_remaining = 0.0


    def get_scan_parameters(self):
        # Freeze the laser parameters for one scan.
        center = self.freq + np.random.normal(0.0, self.scan_jitter_sigma)

        amplitude = self.amplitude * max(0.2, 1.0 + self.amp_state)
        gamma = self.gamma * max(0.2, 1.0 + self.gamma_state)

        return center, amplitude, gamma

    def drift(self, magnitude):
        # Random walk drift
        change = random.uniform(-magnitude, magnitude)
        # Apply proportional drift to the offset
        self.drift_offset += change
