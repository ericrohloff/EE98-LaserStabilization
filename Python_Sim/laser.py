import random


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

        self.target_wavelength = wavelength  # Default target to initial wavelength

        # lorentzian profile: A * (Γ/2) / [ (x - x₀)² + (Γ/2)² ]
        self.amplitude = random.uniform(0.02, 0.1)  # random amplitude on [20,100] mV

        # experimentally: took 2ms to scan 285nm w/ a detected gamma on
        # the order of [5,10]us. Dividing away the time to get a general
        # relationship for wavelength gives [.7125, 1.425] nm
        self.gamma = random.uniform(0.7125, 1.425)  # random width on 0.7125 to 1.425 nm

    @property
    def freq(self):
        # Return the actual current wavelength (calling it freq to maintain compatibility with cavity.py for now)
        # wavelength = base + drift + control
        return (
            self.base_wavelength
            + self.drift_offset
            + (self.control_voltage * self.sensitivity)
        )

    def drift(self, magnitude):
        # Random walk drift
        change = random.uniform(-magnitude, magnitude)
        # Apply proportional drift to the offset
        self.drift_offset += change
