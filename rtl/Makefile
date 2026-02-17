# Makefile for PID Controller Simulation

# Tools
IVERILOG = iverilog
VVP = vvp

# Files
SRC = pid_controller.sv
TB = pid_controller_tb.sv
OUT = pid_tb.vvp

# Targets
.PHONY: all clean sim

all: sim

sim: $(OUT)
	$(VVP) $(OUT)

$(OUT): $(SRC) $(TB)
	$(IVERILOG) -g2012 -o $(OUT) $(SRC) $(TB)

clean:
	rm -f $(OUT)
