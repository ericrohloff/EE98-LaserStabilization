// PID algorithm for individual laser, based on setpoint and current wavelength value
// which comes from the peak detector

module laser_controller_wrapper (
    input logic ramp_start,

    input logic [3:0 ] laser_id,
    input logic laser_exists,
    input logic laser_locked,

    input logic [31:0] pid_p,
    input logic [31:0] pid_i,
    input logic [31:0] pid_d,
    input logic [15:0] set_wavelength,
    input logic [15:0] current_wavelength,

    input logic [15:0] ref_wavelength,

    output logic [16:0] feedback
);

laser_controller u_laser_controller(
    .ramp_start(ramp_start),

    .laser_id(laser_id),
    .laser_exists(laser_exists),
    .laser_locked(laser_locked),

    .pid_p(pid_p),
    .pid_i(pid_i),
    .pid_d(pid_d),
    .set_wavelength(set_wavelength),
    .current_wavelength(current_wavelength),

    .ref_wavelength(ref_wavelength),

    .feedback(feedback)
);

endmodule