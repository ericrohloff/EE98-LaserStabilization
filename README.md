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

### Future Work

We made a lot of progress towards our solution, but some testing and development
is still needed. In the case that other groups want to continue our work, we
have put together a list of todos: [`docs/FutureWork.md`](docs/FutureWork.md).

## 2. Hardware Setup and Documentation

In order to start developing and testing the FPGA-based feedback control system,
you will need to set up the hardware as decscribed in `docs/hardware_setup.md`.
This includes assembling the necessary components.

Some notes related to the Vivado project have been recorded in [`docs/vivado.md`](docs/vivado.md).

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
    - Follow the
      [AUP-ZU3 Getting Started guide](https://xilinx.github.io/AUP-ZU3/getting_started.html)
        - Download and Flash the image linked in the guide to a microSD card
          using Balena Etcher or similar tool
    - Insert the microSD card into the Xilinx AUP-ZU3 board

2. **Network Configuration**:
    - Connect the PYNQ board to your network via Ethernet
    - Verify connectivity by pinging the board: `ping 192.168.3.1`
    - Default credentials: `xilinx` / `xilinx`

### 3.2 Building and Transferring the Bitstream

**Copy Files from Repositiory**: - Copy the precompiled bitstream (`.bit`) and
hardware handoff (`.hwh`) files from the `hardware/` directory to the PYNQ board
directory.

**Transfer Files to PYNQ Board**:

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

### 3.4 Connecting from Host Computer

Once the server is running, you can interact with it from your development
machine:

1. **Install Host Dependencies**:

    ```bash
    cd software/hostComputer
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
enhance stability and performance. Reference commands and usage examples are
provided in `docs/usage_examples.md`

## 6. Team

- Eric Rohloff
- Abe Nelson
- Matt Dacey
- Josh Wilkie

**Acknowledgments**

Special thanks to Professor Mark Hempstead and the University of Syndey Quantum
Science Group for their support and sponsorship.

## Related Work

[1] E. Pultinevicius et al., “A scalable scanning transfer cavity laser
stabilization scheme based on the Red Pitaya STEMlab platform,” Review of
Scientific Instruments, vol. 94, no. 10, p. 103004, Oct. 2023, doi:
[10.1063/5.0169021](https://doi.org/10.1063/5.0169021).

[2] S. Subhankar, A. Restelli, Y. Wang, S. L. Rolston, and J. V. Porto,
“Microcontroller based scanning transfer cavity lock for long-term laser
frequency stabilization,” 2018, doi:
[10.48550/ARXIV.1810.07256](https://doi.org/10.48550/ARXIV.1810.07256).
