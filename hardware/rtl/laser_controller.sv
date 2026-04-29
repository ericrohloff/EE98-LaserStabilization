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

    logic [31:0] prev_error;
    logic [31:0] integral;
    logic [31:0] current_error;
    logic [31:0] ctrl_signal;

    // Use logic/wire for continuous assignments
    assign current_error = set_wavelength - current_wavelength;
    assign feedback = ctrl_signal[31:16] + 16'h8000;

    always_ff @(posedge clk or posedge reset) begin
        if (reset) begin
            integral    <= 32'h0;
            ctrl_signal <= 32'h0;
            prev_error  <= 32'h0;
        end 
        else if (ramp_start && laser_exists && laser_locked) begin
            if (peak_valid) begin
                integral    <= integral + (pid_i * current_error);
                ctrl_signal <= (pid_p * current_error) + integral + (pid_d * (current_error - prev_error)); 
                prev_error  <= current_error;
            end
        end
    end

endmodule