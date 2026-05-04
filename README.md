# EE98: Laser Stabilization for Trapped Ion Quantum Computing

**Team Name:** Blast Off Bronze  
**Institution:** Tufts University, School of Engineering  
**Sponsors:** Professor Mark Hempstead (Tufts) & University of Sydney Quantum
Science Group

## 1. Project Overview

This repository contains the design and implementation of a high-speed feedback
control system on an FPGA, specifically engineered to stabilize lasers used in
trapped ion quantum computers.

### The Challenge

In quantum computing, laser frequency and intensity stability are critical. Even
infinitesimal fluctuations can decohere qubits, leading to errors in quantum
gates. Existing solutions often lack the low-latency response required for
real-time feedback.

### Our Solution

**Blast Off Bronze** utilizes the custom hardware of FPGAs to provide an
ultra-low-latency method for laser frequency locking. This system is designed to
meet the rigorous specifications provided by the University of Sydney’s Quantum
Science Group.

## 2. Hardware Setup and Documentation

In order to start developing and testing the FPGA-based feedback control system,
you will need to set up the hardware as follows:

1. **FPGA Development Board**: The setup guide can be found in the
   [Xilinx AUP-ZU3 Documentation](https://xilinx.github.io/AUP-ZU3/getting_started.html).
2. **Laser Stabilization Components**:

## 3. Getting Started

### Prerequisites

- PYNQ Board (Xilinx AUP-ZU3)
- Python 3.8 or higher
- PYNQ framework installed on the board
- Network connectivity to the PYNQ board (192.168.3.1)
- `.bit` and `.hwh` files transferred to the PYNQ board

### Installation

Run the following commands on the PYNQ board to start the server:

```bash
ssh xilinx@192.168.3.1
# password: xilinx
sudo -i
source /usr/local/share/pynq-venv/bin/activate
cd /home/xilinx/jupyter_notebooks/
python server.py
```

## 4. Repository Structure

- `hardware/`: Contains the FPGA design files, including VHDL/Verilog code and
  constraints.
- `software/`: Contains any software components, such as drivers or control
  interfaces.
- `docs/`: Contains documentation, including setup guides and design
  specifications.
- `tests/`: Contains testbenches and simulation files for validating the FPGA
  design.
- `README.md`: This file, providing an overview of the project and instructions
  for use.

## 5. Usage

This project is intended for use in a laboratory setting, specifically for
researchers working on trapped ion quantum computing. The FPGA-based feedback
control system can be modified and integrated with existing laser setups to
enhance stability and performance.

## 6. Team

- Eric Rohloff
- Abe Nelson
- Matt Dacey
- Josh Wilkie

**Acknowledgments**

Special thanks to Professor Mark Hempstead and the University of Syndey Quantum
Science Group for their support and sponsorship.
