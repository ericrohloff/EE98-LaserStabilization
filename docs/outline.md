# **FPGA Control Loop Architecture Guide**

## **1\. Global Timing & Architecture Strategy**

The system operates on a strict **1MHz control loop** (1000ns per cycle). To achieve sub-microsecond precision without complex clock domain crossings, the entire data path operates on a single **100MHz system clock**.

* **Timing Base:** 1 Tick \= 10ns. A full 1MHz loop consists of exactly 100 ticks (counting 0 to 99).  
* **Multi-Rate Control:** ADC and Ramp timing remain at 1MHz. However, the actuator loop (PID update \+ 4ch DAC write) runs at a programmable kHz rate by decimating ramp cycles. A feedback\_update\_strobe is asserted once every N ramp cycles (configured via feedback\_divider \= N).  
* **Embedded SPI Logic:** To avoid handshaking latency and guarantee strict CS (Chip Select) timing, we do not instantiate generic SPI master IPs. Instead, shift registers and pin toggling (SCK, MOSI, MISO) are embedded directly into the state machines of the driver modules. Unless otherwise specified, the SPI clock effectively runs at **50MHz** (toggling every 2 system ticks).

## **2\. Module Implementation Details**

### **A. ADC Module (Master Timekeeper)**

Acts as the system heartbeat. It runs a continuous 0–99 counter, triggers the analog conversion, reads the 16-bit result, and generates a global sync pulse.

* **Data Format Conversion:** The physical ADC outputs data in **offset binary**. Before latching the final data to the sample output register, the module must convert this to **straight unsigned binary** (typically accomplished by inverting the Most Significant Bit) so downstream modules can perform standard magnitude comparisons.  
* **Tick Schedule (0–99):**  
  * **Ticks 0–49 (0–500ns):** Assert CNV high (ADC converts).  
  * **Ticks 50–81 (500–820ns):** Drop CNV low. Toggle SCK to shift in 16 bits of data from MISO.  
  * **Ticks 82–98 (820–990ns):** SCK is idle. Convert the offset binary shift register data to unsigned binary, then latch into the sample register.  
  * **Tick 99 (990–1000ns):** Pulse sync high for exactly one tick.

### **B. Ramp Generation & DAC Module**

Generates the macroscopic 16-bit ramp waveform and transmits it to the external DAC. It uses the ADC's sync pulse to reset its own 0–99 tick counter, keeping transmission phase-locked.

* **Ramp Logic (1MHz updates):**  
  * **Shadow Registers:** To prevent mid-sweep glitches from asynchronous software updates, the module implements shadow registers for ramp\_step, ramp\_max, and ramp\_min. New values from MMIO are only latched into the active working registers precisely when a sweep resets (on ramp\_cycle\_start).  
  * Maintains a 16-bit current\_ramp\_pos accumulator, incrementing by the active ramp\_step every cycle.  
  * Accumulates up to ramp\_max, then instantly resets to ramp\_min (Sawtooth wave) or reverses direction (Triangle wave).  
  * Asserts a 1-tick ramp\_cycle\_start strobe upon reset/reversal to trigger a new peak search window and latch new shadow register values.  
* **Tick Schedule (0–99):**  
  * **Ticks 0–31 (0–320ns):** Drop CS low. Toggle SCK to shift out current\_ramp\_pos (which is already in unsigned binary for the DAC).  
  * **Ticks 32–49 (320–500ns):** Wait. Keep CS low.  
  * **Ticks 50–99 (500–1000ns):** Drive CS high to latch the external DAC. During this idle window, increment the current\_ramp\_pos accumulator for the next loop.

### **C. Peak Detection Module**

A purely digital processing block that monitors the 1MHz sample stream.

* **Behavior:** Uses the ramp\_cycle\_start strobe to clear its registers at the beginning of a sweep. Throughout the sweep, it performs a simple magnitude comparison, capturing the highest unsigned ADC sample and its corresponding current\_ramp\_pos. Future expansions may include digital filtering here, but current iterations will strictly track the raw maximum.  
* **Output:** Exposes the finalized ramp position of the maximum detected sample (peak\_pos\_on\_ramp) as the Process Variable for the PID.

### **D. PID Controller Module**

A synchronous, clocked module calculating the error between the desired peak position and the actual peak position using the standard algorithm: $u(t) = K_p e(t) + K_i \int e(t) dt + K_d \frac{de(t)}{dt}$

* **Fixed-Point Arithmetic:** Implements internal math using fixed-point fractional formats (e.g., Q16.16) to allow fine-grained tuning without floating-point overhead. Final outputs are truncated/rounded back to a 16-bit integer.  
* **Update Cadence:** Triggered exclusively by the feedback\_update\_strobe (kHz rate), sampling the most recently completed peak\_pos\_on\_ramp.  
* **Output:** Asserts a 1-tick control\_signal\_valid strobe when computation is complete, holding control\_signal steady between updates.

### **E. Output DAC Module (4-Channel Capable)**

Formats and transmits the computed PID control effort to the multi-channel DAC controlling the physical plant (e.g., laser piezos).

* **Channel Mapping:** Although the physical chip has 4 channels, the current implementation targets a single, hardcoded active channel. The PID calculates a single control\_signal which is routed strictly to this channel.  
* **Triggering (Piggybacking):** Idles until it detects the control\_signal\_valid strobe. Because the PID is triggered by decimated ramp cycles, this DAC naturally operates synchronously at the kHz feedback rate.  
* **Execution:** Upon valid trigger, latches the control\_signal and executes the required **24-bit SPI frame sequence** (8-bit command/address for the active channel \+ 16-bit unsigned data). Because this module updates at the kHz rate rather than the 1MHz loop rate, it is not constrained to complete its SPI transmission within a strict 320ns window, allowing for standard continuous transmission.

### **F. MMIO (Memory Mapped I/O)**

The asynchronous bridge (e.g., AXI Lite) between the FPGA fabric and software/CPU. Holds static configuration registers (PID tuning, ramp limits) independent of the 1MHz tick loop.

### **G. Feedback Scheduling (Sequence Summary)**

This deterministic chain avoids race conditions:

1. **Ramp DAC** asserts ramp\_cycle\_start every sweep.  
2. A divider logic block asserts feedback\_update\_strobe every $N$ sweeps.  
3. On this strobe, the **PID** samples the finalized peak\_pos\_on\_ramp and computes an update.  
4. The **PID** asserts control\_signal\_valid.  
5. The **Output DAC** triggers its SPI write frame for the active channel.
