# **FPGA Control Loop Architecture Guide**

## **1\. Global Timing & Architecture Strategy**

The system operates on a strict **1MHz frame** (1000ns per frame) using a single **100MHz system clock**. All modules are synchronous to this clock; no additional clock domains are required for the control path.

* **Timing Base:** 1 tick \= 10ns. One frame \= 100 ticks (0 to 99).  
* **Single Timing Owner:** A dedicated **Global Timing Sequencer (GTS)** owns the 0–99 tick counter and emits phase strobes used by all time-sensitive modules. ADC and Ramp are peers that consume this schedule; neither is the global time master.  
* **Multi-Rate Feedback:** ADC sampling and ramp updates run every frame (1MHz). PID and Output DAC updates run at programmable kHz via decimation (`feedback_divider = N`), producing `feedback_update_strobe` every $N$ ramp cycles.  
* **Embedded SPI Engines:** ADC/Ramp/Output-DAC SPI pin control remains embedded in each module FSM for deterministic CS/SCK behavior.

### **Global Frame Schedule (Owned by GTS)**

| Tick Window | Time Window | Primary Activity | Owners |
|---|---|---|---|
| 0–31 | 0–320ns | Ramp DAC shift window (16b out) | Ramp DAC |
| 32–49 | 320–500ns | Ramp DAC hold-low / settle | Ramp DAC |
| 0–49 | 0–500ns | ADC conversion (`CNV=1`) | ADC |
| 50–81 | 500–820ns | ADC shift window (16b in) | ADC |
| 82–98 | 820–990ns | ADC post-process/latch | ADC |
| 99 | 990–1000ns | Frame boundary pulse(s) | GTS (+ consumers) |

`frame_start` and/or `frame_end` are 1-tick strobes from the GTS. If both are implemented, they must be non-overlapping and deterministic.

## **2\. Module Implementation Details & FSM Definitions**

### **A. Global Timing Sequencer (GTS)**

Provides the canonical frame tick and all phase strobes.

* **Inputs:** `clk_100m`, `rst_n`, optional `enable`.  
* **Outputs:** `frame_tick[6:0]` (0..99), phase strobes (`phase_0_31`, `phase_32_49`, `phase_50_81`, `phase_82_98`), `frame_boundary` pulse at tick 99.

**FSM States**

* `GTS_RESET`: initialize tick counter and outputs.  
* `GTS_RUN`: increment tick each clock; wrap 99→0.

**State Transitions**

* `GTS_RESET -> GTS_RUN` on reset release.  
* `GTS_RUN -> GTS_RESET` on synchronous fault/reset request (optional).  
* `GTS_RUN` self-loop every cycle; tick wraps automatically.

### **B. ADC Front-End Module**

Samples external ADC once per frame using GTS timing; converts offset-binary to unsigned.

* **Inputs:** phase strobes or `frame_tick`, `adc_miso`.  
* **Outputs:** `adc_cnv`, `adc_sck`, `adc_sample_unsigned[15:0]`, `adc_sample_valid`.

**FSM States**

* `ADC_CONVERT`: ticks 0–49, assert `CNV=1`, `SCK` idle.  
* `ADC_SHIFT_IN`: ticks 50–81, `CNV=0`, shift 16 bits from `MISO`.  
* `ADC_POST`: ticks 82–98, invert MSB (offset-binary -> unsigned), register sample.  
* `ADC_BOUNDARY`: tick 99, pulse `adc_sample_valid` (or hold valid through boundary per interface choice).

**State Transitions**

* `ADC_CONVERT -> ADC_SHIFT_IN` at tick 50.  
* `ADC_SHIFT_IN -> ADC_POST` at tick 82 after 16 shifts complete.  
* `ADC_POST -> ADC_BOUNDARY` at tick 99.  
* `ADC_BOUNDARY -> ADC_CONVERT` at tick wrap to 0.

### **C. Ramp Generation + Ramp DAC Module**

Generates `current_ramp_pos` and transmits it to the external ramp DAC every frame.

* **Inputs:** phase strobes/`frame_tick`, active config registers, shadow config registers.  
* **Outputs:** `ramp_dac_cs_n`, `ramp_dac_sck`, `ramp_dac_mosi`, `current_ramp_pos`, `ramp_cycle_start`.

**SPI/Frame FSM States**

* `RAMP_SHIFT_OUT`: ticks 0–31, `CS=0`, shift 16-bit `current_ramp_pos`.  
* `RAMP_HOLD_LOW`: ticks 32–49, keep `CS=0`.  
* `RAMP_LATCH_HIGH`: ticks 50–99, set `CS=1` to latch DAC output.

**Ramp Profile Substates**

* `RAMP_UP`: increment toward `ramp_max`.  
* `RAMP_DOWN`: decrement toward `ramp_min` (triangle mode only).

**State Transitions**

* SPI FSM transitions strictly by tick windows: `RAMP_SHIFT_OUT -> RAMP_HOLD_LOW -> RAMP_LATCH_HIGH -> RAMP_SHIFT_OUT`.  
* Sawtooth mode: on boundary update, if next value exceeds `ramp_max`, set to `ramp_min` and pulse `ramp_cycle_start`.  
* Triangle mode: `RAMP_UP -> RAMP_DOWN` at/above `ramp_max`, `RAMP_DOWN -> RAMP_UP` at/below `ramp_min`, pulse `ramp_cycle_start` on each reversal.  
* Shadow-to-active config commit occurs only on `ramp_cycle_start`.

### **D. Peak Detection Module**

Tracks maximum ADC sample and associated ramp position over each sweep.

* **Inputs:** `adc_sample_unsigned`, `adc_sample_valid`, `current_ramp_pos`, `ramp_cycle_start`.  
* **Outputs:** `peak_pos_on_ramp`, optional `peak_value`, optional `peak_ready`.

**FSM States**

* `PEAK_CLEAR`: clear max/value registers at sweep start.  
* `PEAK_TRACK`: compare each valid sample against running max.  
* `PEAK_HOLD`: hold finalized result between sweep boundaries.

**State Transitions**

* `PEAK_HOLD -> PEAK_CLEAR` on `ramp_cycle_start`.  
* `PEAK_CLEAR -> PEAK_TRACK` immediately next cycle.  
* `PEAK_TRACK -> PEAK_HOLD` on next `ramp_cycle_start` after final sample window.

### **E. Feedback Divider / Scheduler Module**

Decimates ramp cycles to create the PID update cadence.

* **Inputs:** `ramp_cycle_start`, `feedback_divider`.  
* **Outputs:** `feedback_update_strobe` (1 tick).

**FSM States**

* `FDBK_COUNT`: count sweep boundaries.  
* `FDBK_FIRE`: issue strobe, then clear/reload count.

**State Transitions**

* `FDBK_COUNT -> FDBK_FIRE` when count reaches `feedback_divider - 1` on `ramp_cycle_start`.  
* `FDBK_FIRE -> FDBK_COUNT` in one cycle.

### **F. PID Controller Module**

Computes control effort at kHz cadence:

$$u(t) = K_p e(t) + K_i \int e(t)dt + K_d\frac{de(t)}{dt}$$

* **Inputs:** `feedback_update_strobe`, `peak_pos_on_ramp`, `setpoint`, `Kp`, `Ki`, `Kd`.  
* **Outputs:** `control_signal[15:0]`, `control_signal_valid`.

**FSM States**

* `PID_IDLE`: hold output between updates.  
* `PID_SAMPLE`: latch process variable and setpoint, compute error terms.  
* `PID_COMPUTE`: fixed-point multiply-accumulate (Q-format internal).  
* `PID_CLAMP`: saturate/round/truncate to DAC width.  
* `PID_VALID`: assert 1-tick `control_signal_valid`.

**State Transitions**

* `PID_IDLE -> PID_SAMPLE` on `feedback_update_strobe`.  
* `PID_SAMPLE -> PID_COMPUTE -> PID_CLAMP -> PID_VALID` in deterministic pipeline order (single- or multi-cycle implementation).  
* `PID_VALID -> PID_IDLE` next cycle.

### **G. Output DAC Module (4-Channel Device, 1 Active Channel)**

Writes PID control effort to a selected DAC channel using a 24-bit SPI frame.

* **Inputs:** `control_signal`, `control_signal_valid`, `active_channel`.  
* **Outputs:** `out_dac_cs_n`, `out_dac_sck`, `out_dac_mosi`, optional `out_dac_busy`.

**FSM States**

* `ODAC_IDLE`: wait for `control_signal_valid`.  
* `ODAC_LOAD`: latch control signal and command/address bits.  
* `ODAC_SHIFT24`: transmit 24-bit frame (8-bit command/address + 16-bit data).  
* `ODAC_LATCH`: deassert CS / finalize transfer.  
* `ODAC_DONE`: optional one-cycle done pulse.

**State Transitions**

* `ODAC_IDLE -> ODAC_LOAD` on `control_signal_valid`.  
* `ODAC_LOAD -> ODAC_SHIFT24 -> ODAC_LATCH -> ODAC_DONE -> ODAC_IDLE` sequentially.  
* If `control_signal_valid` reasserts while busy, either queue one sample or define overwrite/drop policy explicitly (must be deterministic).

### **H. MMIO / Configuration Module**

Bridges software writes into deterministic hardware update points.

* **Registers:** PID gains, setpoint, ramp limits/step, mode flags, divider, enable bits.  
* **Shadowing Rule:** Asynchronous software writes always update shadow registers first.

**FSM States**

* `MMIO_IDLE`: no transaction.  
* `MMIO_WRITE_SHADOW`: commit bus write to shadow register map.  
* `MMIO_ARMED`: shadow differs from active; waiting for safe commit.  
* `MMIO_COMMIT`: copy shadow->active at designated boundary event.

**State Transitions**

* `MMIO_IDLE -> MMIO_WRITE_SHADOW` on valid bus write.  
* `MMIO_WRITE_SHADOW -> MMIO_ARMED` when write completes.  
* `MMIO_ARMED -> MMIO_COMMIT` on module-defined safe point (typically `ramp_cycle_start`; optionally `frame_boundary` for non-ramp fields).  
* `MMIO_COMMIT -> MMIO_IDLE` next cycle.

## **3\. End-to-End Feedback Scheduling (Deterministic Chain)**

1. **GTS** runs the canonical 0–99 frame and emits phase strobes.  
2. **ADC** produces one `adc_sample_valid` + sample per frame.  
3. **Ramp DAC** updates once per frame and emits `ramp_cycle_start` on sweep reset/reversal.  
4. **Peak Detection** finalizes `peak_pos_on_ramp` for each completed sweep.  
5. **Feedback Divider** emits `feedback_update_strobe` every $N$ sweeps.  
6. **PID** computes and pulses `control_signal_valid`.  
7. **Output DAC** transmits one 24-bit frame to the active channel.

## **4\. Verification & Robustness Requirements**

* All event strobes (`frame_boundary`, `adc_sample_valid`, `ramp_cycle_start`, `feedback_update_strobe`, `control_signal_valid`) are exactly one system tick wide.  
* No ADC/Ramp SPI phase overlap violations relative to the published frame windows.  
* Tick-driven transitions are monotonic and reset-safe (no skipped/duplicate phase windows after reset).  
* Optional watchdog flags if expected boundary pulses are absent for more than programmable threshold frames.
