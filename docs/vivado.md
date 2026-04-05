# Using vivado on linux
Run `use xilinx.2022` to get the `xilinx` command. Run `xilinx PROJECT_NAME.xpr` to open the GUI.

# Creating a project

Adapted from this: https://rfsoc.mit.edu/6S965/F24/assignments/week01/pynq_01

Download constraints file: https://github.com/Xilinx/AUP-ZU3/blob/main/base/constraints/base.xdc

Download board files: https://github.com/RealDigitalOrg/aup-zu3-bsp/tree/master (We have the 4GB model)
- you need to add your board files "repo" to Xilinx so it can find it: https://docs.amd.com/r/en-US/ug895-vivado-system-level-design-entry/Using-the-Vivado-Design-Suite-Platform-Board-Flow

Follow the project creation files from the original tutorial (substituting the constraint files, and using our AUP ZU3 4GB board)

# Version control
Perhaps a helpful tutorial: https://www.fpgadeveloper.com/2014/08/version-control-for-vivado-projects.html/
