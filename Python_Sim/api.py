# lock(laser_id) : Apply feedback to the laser “laser_id”
# unlock(laser_id) : Stop applying feedback to the laser “laser_id”
# start_cavity_scan(): Start scanning the cavity by applying the triangular ramp
# stop_cavity_scan(): Stop scanning the cavity by stopping output of triangular ramp

from laser import SimLaser
from cavity import Cavity


class InterfaceAPI:

    def __init__(self):
        self.cavity = Cavity(535, 820)  # example cavity range

    def createLaser(self, laser_id):

        new_laser = SimLaser(laser_id, freq, modifier=1.0)
        self.cavity.add_laser(new_laser)

        
        pass

    def lock(laser_id):
        # Apply feedback to the laser "laser_id"

        pass

    def unlock(laser_id):
        # Stop applying feedback

        pass

    def start_cavity_scan(duration):
        # Apply triangular ramp to cavity
        # duration in seconds
        # based on current DAC sample, have "ADC" input sample calculated from laser freqs
        pass

    def stop_cavity_scan(duration):
        pass