// PID algorithm for individual laser, based on setpoint and current wavelength value
// which comes from the peak detector

module laser_pid (
    input logic ramp_start,

    input logic [31:0] pid_p,
    input logic [31:0] pid_i,
    input logic [31:0] pid_d,
    input logic [15:0] set_wavelength,
    input logic [15:0] current_wavelength,

    output logic [16:0] feedback,
);

assign feedback = 0;

endmodule