# Makefile for PID Controller Simulation

# Tools
IVERILOG = iverilog
VVP = vvp

# Targets
.PHONY: all clean sim spi_sim dac_sim ramp_sim pid dac ramp

all: sim

sim: pid_tb.vvp
	$(VVP) pid_tb.vvp

pid: sim

spi_sim: spi_tb.vvp
	$(VVP) spi_tb.vvp

spi_sim: $(SPI_OUT)
	$(VVP) $(SPI_OUT)

$(PID_OUT): $(PID_SRC) $(PID_TB)
	$(IVERILOG) -g2012 -o $(PID_OUT) $(PID_SRC) $(PID_TB)

$(SPI_OUT): $(SPI_SRC) $(SPI_TB)
	$(IVERILOG) -g2012 -o $(SPI_OUT) $(SPI_SRC) $(SPI_TB)

ramp: ramp_sim

ramp_sim: ramp_bringup_tb.vvp
	$(VVP) ramp_bringup_tb.vvp

pid_tb.vvp: pid_controller.sv pid_controller_tb.sv
	$(IVERILOG) -g2012 -o pid_tb.vvp pid_controller.sv pid_controller_tb.sv

spi_tb.vvp: spi_controller.sv spi_controller_tb.sv
	$(IVERILOG) -g2012 -o spi_tb.vvp spi_controller.sv spi_controller_tb.sv

dac_tb.vvp: dac_driver.sv spi_controller.sv dac_driver_tb.sv
	$(IVERILOG) -g2012 -o dac_tb.vvp dac_driver.sv spi_controller.sv dac_driver_tb.sv

ramp_bringup_tb.vvp: global_timing_sequencer.sv ramp_dac_spi.sv adc_frontend.sv output_dac_spi.sv ramp_dac_bringup_tb.sv
	$(IVERILOG) -g2012 -o ramp_bringup_tb.vvp global_timing_sequencer.sv ramp_dac_spi.sv adc_frontend.sv output_dac_spi.sv ramp_dac_bringup_tb.sv

clean:
	rm -f pid_tb.vvp spi_tb.vvp dac_tb.vvp ramp_bringup_tb.vvp
