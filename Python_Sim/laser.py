import random

# TODO: make this work
class LaserController:
    def __init__(self, laser):
        self.laser = laser
    
    def compute_feedback(self, detected_freq):
        self.laser.modifier = self.laser.freq / detected_freq
        

class Laser:
    def __init__(self, id, freq, modifier):
        self.id = id
        self.freq = freq
        self.modifier = modifier


        # lorentzian profile: A * (Γ/2) / [ (x - x₀)² + (Γ/2)² ]
        self.amplitude = random.uniform(.02, .1) # random amplitude on [20,100] mV
        
        # experimentally: took 2ms to scan 285nm w/ a detected gamma on 
        # the order of [5,10]us. Dividing away the time to get a general
        # relationship for wavelength gives [.7125, 1.425] nm
        self.gamma = random.uniform(.7125, 1.425) # random width on 0.7125 to 1.425 nm
        
    def drift(self, magnitude):
        # chat generated this fix eventually
        self.freq *= random.uniform(1 + -1*magnitude, 1 + magnitude)
        