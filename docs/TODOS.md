# TODOs
Here are a list of changes that are necessary to get the design tested or improve robustness.

## Hardware TODOs
- [ ] Create a PCB for the 4-channel feedback DAC to eliminate wires

## Software/FPGA TODOs
- [ ] Build upon the existing Python API to make a fully fledged GUI
- [ ] Refine the laser controller feedback module ([`hardware/rtl/laser_controller.sv`](hardware/rtl/laser_controller.sv)), and test it
- [ ] Make the peak detection module ([`hardware/rtl/peak_detection.sv`](hardware/rtl/peak_detection.sv)) more robust to noise

## Testing TODOs
Obviously the ideal is to get this tested on an actual system but we recognize that this is difficult to do.
Here are some ideas that could replace this:

- [ ] Create a system that is able to emulate a laser and cavity to allow in the loop testing of laser feedback
- [ ] Build a more sophisticated simulation system that makes it easy to test verilog algorithms in the loop