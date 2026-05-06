# Future Work

Here are a list of changes that are necessary to get the design tested or
improve robustness. This will allow other groups to pick up where we left off
and continue development.

## Hardware TODOs

- [ ] Create a PCB for the 4-channel feedback DAC to eliminate wires
- [ ] (Related to testing task below) Design a secondary system that helps validate our system

## Software/FPGA TODOs

- [ ] Build upon the existing Python API to make a fully fledged GUI
- [ ] Refine the laser controller feedback module
      ([`hardware/rtl/laser_controller.sv`](hardware/rtl/laser_controller.sv)),
      and test it
- [ ] Make the peak detection module
      ([`hardware/rtl/peak_detection.sv`](hardware/rtl/peak_detection.sv)) more
      robust to noise

## Testing TODOs

Obviously the ideal is to get this tested on an actual system but we recognize
that this is difficult to do. Here are some ideas that could replace this:

- [ ] Create a system that is able to emulate a laser and cavity to allow in the
      loop testing of laser feedback
- [ ] Build a more sophisticated simulation system that makes it easy to test
      verilog algorithms in the loop
- [ ] Create a more robust testbench for the laser controller with dedicated
      unit tests for each component
- [ ] Test on actual laser system to ensure that the system is able to lock and
      stabilize a laser in practice
