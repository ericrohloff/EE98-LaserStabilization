from laser import * 
import numpy as np
import random

class Cavity:
    def __init__(self, start_wv_nm, end_wv_nm):
        self.start_wv_nm = start_wv_nm
        self.end_wv_nm = end_wv_nm
        
        self.curr_pos_nm = start_wv_nm
        self.lasers = []
        self.v_out = 0
    
    def add_laser(self, laser):
        self.lasers.append(laser)
    
    # call this every time step 
    def ramp(self, ramp_freq, sample_rate):
        step = (self.end_wv_nm - self.start_wv_nm) * (ramp_freq / sample_rate)
        self.curr_pos_nm += step
        if self.curr_pos_nm > self.end_wv_nm:
            self.curr_pos_nm = self.start_wv_nm

        self.v_out = 0

        # noise floor
        std_dev = random.uniform(0.000_001, 0.000_002) # random noise on [1,2] mV
        self.v_out += np.random.normal(0, std_dev)

        # peaks
        for l in self.lasers:
            lorentzian = l.amplitude * (l.gamma / 2) / ( (self.curr_pos_nm - l.freq)**2 + (l.gamma / 2)**2 )
            self.v_out += lorentzian
            

class CavityController:
    def __init__(self, cavity):
        self.cavity = cavity
    
    def detect_peak(self, peak_bucket):
        
        # rudimentary, just check current
        if self.cavity.v_out > 0.02:
            return True
        return False
