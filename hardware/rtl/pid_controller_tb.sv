/*
 * Testbench for PID Controller (Fixed-Point)
 */

`timescale 1ns / 1ps

module pid_controller_tb;

    // Parameters
    localparam DATA_WIDTH = 16;
    localparam FRAC_BITS = 10; // Use 10 bits for testing to keep numbers manageable
    
    // Inputs
    logic                    clk;
    logic                    reset;
    logic                    valid;
    logic signed [DATA_WIDTH-1:0] sample;
    logic signed [DATA_WIDTH-1:0] setpoint;
    
    // 32-bit coefficients (Q22.10 format)
    logic signed [31:0]      kp;
    logic signed [31:0]      ki;
    logic signed [31:0]      kd;
    
    logic signed [DATA_WIDTH-1:0] output_min;
    logic signed [DATA_WIDTH-1:0] output_max;

    // Outputs
    logic signed [DATA_WIDTH-1:0] control_output;

    // Instantiate the Unit Under Test (UUT)
    pid_controller #(
        .DATA_WIDTH(DATA_WIDTH),
        .FRAC_BITS(FRAC_BITS)
    ) uut (
        .clk(clk),
        .reset(reset),
        .valid(valid),
        .sample(sample),
        .setpoint(setpoint),
        .kp(kp),
        .ki(ki),
        .kd(kd),
        .output_min(output_min),
        .output_max(output_max),
        .control_output(control_output)
    );

    // Clock generation
    initial begin
        clk = 0;
        forever #5 clk = ~clk;
    end

    // Test sequence
    initial begin
        // Initialize Inputs
        reset = 1;
        valid = 0;
        sample = 0;
        setpoint = 0;
        kp = 0;
        ki = 0;
        kd = 0;
        output_min = -1000;
        output_max = 1000;

        // Wait for global reset
        #20;
        reset = 0;
        #10;

        // Test Case 1: Step Response with Fractional Coefficients
        // Kp = 1.5 (1.5 * 2^10 = 1536)
        // Ki = 0.5 (0.5 * 2^10 = 512)
        // Kd = 0.0
        // Setpoint = 100, Sample = 0
        // Error = 100
        
        $display("Test Case 1: Fractional Coefficients");
        kp = 1536; // 1.5
        ki = 512;  // 0.5
        kd = 0;    // 0.0
        setpoint = 100;
        sample = 0;
        valid = 1;
        
        // Expected:
        // P = 1.5 * 100 = 150
        // I = 0.5 * 100 = 50
        // D = 0
        // Output = 200
        #10; // Wait for clock edge
        valid = 0;
        #10; // Wait for logic to settle/display
        
        $display("Time=%0t Output=%d Expected=200", $time, control_output);
        if (control_output !== 200) $error("Test Case 1 Failed!");


        // Test Case 2: Accumulation
        // Same inputs, one more cycle.
        // Error = 100 (Constant)
        // P = 1.5 * 100 = 150
        // I = I_prev + (0.5 * 100) = 50 + 50 = 100
        // Output = 150 + 100 = 250
        
        $display("Test Case 2: Integration Accumulation");
        valid = 1;
        #10;
        valid = 0;
        #10;
        
        $display("Time=%0t Output=%d Expected=250", $time, control_output);
        if (control_output !== 250) $error("Test Case 2 Failed!");


        // Test Case 3: Saturation with large error
        // Set output max to 300.
        // Error = 1000.
        // Kp = 1.0 (1024)
        // P = 1000.
        // Output should be 300.
        
        $display("Test Case 3: Saturation");
        output_max = 300;
        kp = 1024; // 1.0
        ki = 0;
        kd = 0;
        setpoint = 1000;
        sample = 0;
        
        // Reset the integrator for clean test
        reset = 1; 
        #10; 
        reset = 0;
        
        valid = 1;
        #10;
        valid = 0;
        #10;
        
        $display("Time=%0t Output=%d Expected=300", $time, control_output);
        if (control_output !== 300) $error("Test Case 3 Failed!");

        $display("Testbench complete.");
        $finish;
    end

endmodule
