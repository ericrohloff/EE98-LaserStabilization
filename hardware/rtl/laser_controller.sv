module laser_controller (
    input logic clk,
    input logic reset,
    input logic ramp_start,
    input logic peak_valid,

    input logic [3:0] laser_id,
    input logic laser_exists,
    input logic laser_locked,

    input logic [15:0] pid_p,
    input logic [15:0] pid_i,
    input logic [15:0] pid_d,
    input logic [15:0] set_wavelength,
    input logic [15:0] current_wavelength,

    input logic [15:0] ref_wavelength,

    output logic [15:0] feedback
);

reg [15:0] prev_error = 16'h0000;
reg [15:0] integral = 16'h0000;
reg [15:0] derivative = 16'h0000;
reg [15:0] current_error = 16'h0000;

assign current_error = set_wavelength - current_wavelength;

always @(posedge clk or negedge rst_n) begin

    if (~rst_n) begin
        // Reset logic generally specific to application
    end 
    else if (ramp_start) begin
        if (laser_exists && laser_locked) begin
                    
        // PID Calculation
        integral <= integral + (pid_i * current_error);
        derivative <= pid_d * (current_error - prev_error);
        // Calculate control signal
        control_signal = (pid_p * current_error) + integral + derivative; 
        prev_error <= current_error;// Update previous error term to feed it for derrivative term.
        end
    end
end

assign feedback = control_signal;

endmodule