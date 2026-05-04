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
2. **Laser Stabilization Components**: Optical cavity, laser diodes,
   photodetectors, and analog signal conditioning circuits as documented in the
   hardware schematics.

## 3. Getting Started

### Prerequisites

- **PYNQ Board**: Xilinx AUP-ZU3 with PYNQ OS installed
- **Python 3.8+**: On both the PYNQ board and host computer
- **PYNQ Framework**: Pre-installed on the board
- **Network**: Ethernet connection between host and PYNQ board (IP: 192.168.3.1)
- **FPGA Bitstream**: Compiled `.bit` file from the Vivado project
- **Hardware Handoff**: Associated `.hwh` file for PYNQ overlay loading

### 3.1 Initial Board Setup

1. **Flash the PYNQ Image**:
    - Download the PYNQ image from the
      [official PYNQ releases](https://github.com/Xilinx/PYNQ/releases)
    - Follow the
      [PYNQ Getting Started guide](https://pynq.readthedocs.io/en/latest/getting_started.html)
    - Flash the image to a microSD card using Etcher or similar tool
    - Insert the microSD card into the Xilinx AUP-ZU3 board

2. **Network Configuration**:
    - Connect the PYNQ board to your network via Ethernet
    - Verify connectivity by pinging the board: `ping 192.168.3.1`
    - Default credentials: `xilinx` / `xilinx`

### 3.2 Building and Transferring the Bitstream

1. **Generate the FPGA Bitstream**:

    ```bash
    cd hardware/rtl
    make  # Compiles RTL to generate design_1_wrapper.bit and design_1_wrapper.hwh
    ```

2. **Transfer Files to PYNQ Board**:

    ```bash
    # From your development machine:
    scp hardware/fpga/vivado/vivado.runs/impl_1/design_1_wrapper.bit xilinx@192.168.3.1:/home/xilinx/
    scp hardware/fpga/vivado/vivado.runs/impl_1/design_1_wrapper.hwh xilinx@192.168.3.1:/home/xilinx/
    ```

3. **Verify File Transfer**:
    ```bash
    ssh xilinx@192.168.3.1 ls -la /home/xilinx/*.bit /home/xilinx/*.hwh
    ```

### 3.3 Running the Server

1. **SSH into the PYNQ Board**:

    ```bash
    ssh xilinx@192.168.3.1
    # password: xilinx
    ```

2. **Activate the PYNQ Environment**:

    ```bash
    sudo -i
    source /usr/local/share/pynq-venv/bin/activate
    ```

3. **Navigate to the Server Directory**:

    ```bash
    cd /home/xilinx/jupyter_notebooks/
    # Or copy server.py here if not already present
    ```

4. **Start the Server**:

    ```bash
    python server.py
    ```

    You should see output indicating the server is listening on a TCP port
    (typically 5000).

### 3.4 Connecting from Host Computer

Once the server is running, you can interact with it from your development
machine:

1. **Install Host Dependencies**:

    ```bash
    cd software/hostComputer
    pip install -r requirements.txt  # If requirements file exists
    ```

2. **Run the CLI Client** (from repository root):

    ```bash
    python software/hostComputer/host_cli.py
    ```

3. **Example Commands**:

    ```bash
    # Create and configure a laser
    create_laser(0, kp=100, ki=50, kd=10)

    # Start cavity scan for 10 seconds
    start_cavity_scan(10)

    # Lock a laser at target wavelength
    lock(0, 650.0)
    ```

### 3.5 Troubleshooting

- **Cannot connect to board**: Check network connectivity and IP address
- **Bitstream load fails**: Verify `.bit` and `.hwh` files are in the correct
  location
- **Server crashes**: Check logs in `/home/xilinx/` for error messages
- **Commands not working**: Ensure the FPGA overlay is properly loaded in the
  server

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
