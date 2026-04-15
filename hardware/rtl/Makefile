# Makefile for PID Controller Simulation

# Tools
IVERILOG = iverilog
VVP = vvp

# Targets
.PHONY: all clean sim spi_sim dac_sim ramp_sim pid dac ramp feedback_dac_sim peak peak_sim pid_vector_sim

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

feedback_dac_sim: feedback_dac_driver_tb.vvp
	$(VVP) feedback_dac_driver_tb.vvp

vector_sim:
	cd ../../simulation && python3 run_sim_export_vectors.py

test_verilog_algorithms: vector_sim peak_sim pid_vector_sim
	cd ../../tests/rtlValidation && \
	python3 compare_peak_outputs.py && \
	python3 compare_pid_outputs.py

peak_sim: peak_detection_tb.vvp
	$(VVP) peak_detection_tb.vvp

pid_vector_sim: laser_controller_tb.vvp
	$(VVP) laser_controller_tb.vvp

pid_tb.vvp: pid_controller.sv pid_controller_tb.sv
	$(IVERILOG) -g2012 -o pid_tb.vvp pid_controller.sv pid_controller_tb.sv

spi_tb.vvp: spi_controller.sv spi_controller_tb.sv
	$(IVERILOG) -g2012 -o spi_tb.vvp spi_controller.sv spi_controller_tb.sv

dac_tb.vvp: dac_driver.sv spi_controller.sv dac_driver_tb.sv
	$(IVERILOG) -g2012 -o dac_tb.vvp dac_driver.sv spi_controller.sv dac_driver_tb.sv

ramp_bringup_tb.vvp: global_timing_sequencer.sv ramp_dac_spi.sv adc_frontend.sv output_dac_spi.sv ramp_dac_bringup_tb.sv
	$(IVERILOG) -g2012 -o ramp_bringup_tb.vvp global_timing_sequencer.sv ramp_dac_spi.sv adc_frontend.sv output_dac_spi.sv ramp_dac_bringup_tb.sv

feedback_dac_driver_tb.vvp: feedback_dac_driver.sv feedback_dac_driver_tb.sv
	$(IVERILOG) -g2012 -o feedback_dac_driver_tb.vvp feedback_dac_driver.sv feedback_dac_driver_tb.sv

peak_detection_tb.vvp: peak_detection.sv peak_detection_tb.sv
	$(IVERILOG) -g2012 -o peak_detection_tb.vvp peak_detection.sv peak_detection_tb.sv

laser_controller_tb.vvp: laser_controller.sv laser_controller_tb.sv
	$(IVERILOG) -g2012 -o laser_controller_tb.vvp laser_controller.sv laser_controller_tb.sv

clean:
	rm -f pid_tb.vvp spi_tb.vvp dac_tb.vvp ramp_bringup_tb.vvp feedback_dac_driver_tb.vvp peak_detection_tb.vvp laser_controller_tb.vvp
