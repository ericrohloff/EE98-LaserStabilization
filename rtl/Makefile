# Makefile for PID Controller Simulation

# Tools
IVERILOG = iverilog
VVP = vvp

# PID files
PID_SRC = pid_controller.sv
PID_TB = pid_controller_tb.sv
PID_OUT = pid_tb.vvp

# SPI files
SPI_SRC = spi_controller.sv
SPI_TB = spi_controller_tb.sv
SPI_OUT = spi_tb.vvp

# Targets
.PHONY: all clean sim spi_sim pid

all: sim

sim: $(PID_OUT)
	$(VVP) $(PID_OUT)

pid: sim

spi_sim: $(SPI_OUT)
	$(VVP) $(SPI_OUT)

$(PID_OUT): $(PID_SRC) $(PID_TB)
	$(IVERILOG) -g2012 -o $(PID_OUT) $(PID_SRC) $(PID_TB)

$(SPI_OUT): $(SPI_SRC) $(SPI_TB)
	$(IVERILOG) -g2012 -o $(SPI_OUT) $(SPI_SRC) $(SPI_TB)

clean:
	rm -f $(PID_OUT) $(SPI_OUT)
