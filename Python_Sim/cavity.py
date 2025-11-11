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

        for l in self.lasers:
            lorentzian = l.amplitude * (l.gamma / 2) / ( (self.curr_pos_nm - l.freq)**2 + (l.gamma / 2)**2 )
            self.v_out += lorentzian


if __name__ == "__main__":
    cavity = Cavity(535, 820)
    cavity.add_laser(SimLaser("L1", 600, 1.0))
    times = np.linspace(0, 1, 1000000)
    vouts = []
    cavity_values = []
    for t in times:
        cavity.ramp(10, 1e6) # 1000 Hz ramp, 1000 samples per ramp
        vouts.append(cavity.v_out)
        cavity_values.append(cavity.curr_pos_nm)
        # print(f"Time: {t:.6f} s, Cavity Position: {cavity.curr_pos_nm:.2f} nm, Output Voltage: {cavity.v_out}")

    import matplotlib.pyplot as plt
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
    plt.ylim(-0.1, 1.1)
    plt.grid(True)

    plt.tight_layout()
    plt.show()
    # plt.savefig("cavityPlot.png")