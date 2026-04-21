module algorithm_top (
	input  wire [3:0] ref_id,
	input  wire ref_exists,
	input  wire ref_locked,
	input  wire [31:0] ref_pid_p,
	input  wire [31:0] ref_pid_i,
	input  wire [31:0] ref_pid_d,
	input  wire [15:0] ref_set_wavelength,
	output wire [15:0] ref_detected_wavelength,

	input  wire [3:0] l1_id,
	input  wire l1_exists,
	input  wire l1_locked,
	input  wire [31:0] l1_pid_p,
	input  wire [31:0] l1_pid_i,
	input  wire [31:0] l1_pid_d,
	input  wire [15:0] l1_set_wavelength,
	output wire [15:0] l1_detected_wavelength,

	input  wire [3:0] l2_id,
	input  wire l2_exists,
	input  wire l2_locked,
	input  wire [31:0] l2_pid_p,
	input  wire [31:0] l2_pid_i,
	input  wire [31:0] l2_pid_d,
	input  wire [15:0] l2_set_wavelength,
	output wire [15:0] l2_detected_wavelength,

	input  wire [3:0] l3_id,
	input  wire l3_exists,
	input  wire l3_locked,
	input  wire [31:0] l3_pid_p,
	input  wire [31:0] l3_pid_i,
	input  wire [31:0] l3_pid_d,
	input  wire [15:0] l3_set_wavelength,
	output wire [15:0] l3_detected_wavelength,

	input  wire [3:0] l4_id,
	input  wire l4_exists,
	input  wire l4_locked,
	input  wire [31:0] l4_pid_p,
	input  wire [31:0] l4_pid_i,
	input  wire [31:0] l4_pid_d,
	input  wire [15:0] l4_set_wavelength,
	output wire [15:0] l4_detected_wavelength,

	input  wire system_on,
	input  wire system_locked,

	// Hardware I/O
	input wire clk,
    input wire reset,
    input wire enable,

	input wire adc_miso,
	output wire adc_sck,
	output wire adc_cnv,
    output wire [15:0] adc_sample_unsigned,

	output wire dac_mosi,
	output wire dac_sck,
	output wire dac_cs,
	output wire dac_ldac_n,

    // Ramp DAC
	output wire feedback_dac_mosi,
	output wire feedback_dac_sck,
	output wire feedback_dac_cs,

    output wire requested, 
    output wire ramp_start, 
    output wire [15:0] counter, 

    // Debug
    output wire debug_pin_0,
    output wire debug_pin_1,
    output wire debug_pin_2,
    output wire debug_pin_3,
    output wire debug_pin_4,
    output wire debug_pin_5,
    output wire debug_pin_6,
    output wire debug_pin_7

);

    logic [6:0] seq_frame_tick;

    global_timing_sequencer u_sequencer (
        .clk(clk),
        .reset(reset),
        .enable(enable),
        .frame_tick(seq_frame_tick)
    );

    logic ramp_done;
    logic ramp_cycle_start;
    logic [15:0] current_ramp_pos;
    logic adc_sample_valid;
    assign debug_pin_1 = adc_sample_valid; // TODO give this a real port
    assign debug_pin_0 = ramp_done;
    assign counter = current_ramp_pos;
    assign ramp_start = ramp_cycle_start;

	ramp_dac_spi u_ramp_dac_spi (
        .clk(clk),
        .reset(reset),
        .enable(enable && system_on),
        .frame_tick(seq_frame_tick),
        .ramp_step(64),
        .ramp_min(16'd0),
        .ramp_max(16'd63000),
        .triangle_mode(0),                                 // TODO: remove this?
        .ramp_dac_cs_n(dac_cs),
        .ramp_dac_sck(dac_sck),
        .ramp_dac_mosi(dac_mosi),
        .ramp_dac_ldac_n(dac_ldac_n),
        .current_ramp_pos(current_ramp_pos),
        .ramp_cycle_start(ramp_cycle_start),
        .ramp_done(ramp_done)
    );

	adc_frontend u_adc_frontend (
        .clk(clk),
        .reset(reset),
        .enable(enable && system_on),
        .frame_tick(seq_frame_tick),
        .adc_miso(adc_miso),
        .adc_cnv(adc_cnv),
        .adc_sck(adc_sck),
        .adc_sample_unsigned(adc_sample_unsigned),
        .adc_sample_valid(adc_sample_valid)
    );

    logic [15:0] l1_peak_position;
    logic [15:0] l2_peak_position;
    logic [15:0] l3_peak_position;
    logic [15:0] l4_peak_position;

    logic l1_peak_valid;
    logic l2_peak_valid;
    logic l3_peak_valid;
    logic l4_peak_valid;

    logic [15:0] l1_feedback;
    logic [15:0] l2_feedback;
    logic [15:0] l3_feedback;
    logic [15:0] l4_feedback;

	peak_detection u_peak_detection (
        .clk(clk),
        .reset(reset),
        .adc_sample(adc_sample_unsigned),
        .adc_sample_valid(adc_sample_valid),
        .current_ramp_pos(current_ramp_pos),
        .ramp_start(ramp_cycle_start),
        .ref_target(ref_set_wavelength),
        .l1_target(l1_set_wavelength),
        .l2_target(l2_set_wavelength),
        .l3_target(l3_set_wavelength),
        .l4_target(l4_set_wavelength),

        .l1_position(l1_detected_wavelength),
        .l2_position(l2_detected_wavelength),
        .l3_position(l3_detected_wavelength),
        .l4_position(l4_detected_wavelength),
        .l1_valid(l1_peak_valid),
        .l2_valid(l2_peak_valid),
        .l3_valid(l3_peak_valid),
        .l4_valid(l4_peak_valid)
    );


	laser_controller u_l1_controller (
        .clk(clk),
        .reset(reset),
        .ramp_start(ramp_cycle_start),
        .peak_valid(l1_peak_valid),
        .laser_id(l1_id),
        .laser_exists(l1_exists),
        .laser_locked(l1_locked),
        .pid_p(l1_pid_p),
        .pid_i(l1_pid_i),
        .pid_d(l1_pid_d),
        .set_wavelength(l1_set_wavelength),
        .current_wavelength(l1_detected_wavelength),
        .ref_wavelength(ref_set_wavelength),
        .feedback(l1_feedback)
    );
	laser_controller u_l2_controller (
    .clk(clk),
    .reset(reset),
    .ramp_start(ramp_cycle_start),
    .peak_valid(l2_peak_valid),
        .laser_id(l2_id),
        .laser_exists(l2_exists),
        .laser_locked(l2_locked),
        .pid_p(l2_pid_p),
        .pid_i(l2_pid_i),
        .pid_d(l2_pid_d),
        .set_wavelength(l2_set_wavelength),
        .current_wavelength(l2_detected_wavelength),
        .ref_wavelength(ref_set_wavelength),
        .feedback(l2_feedback)
    );
	laser_controller u_l3_controller (
    .clk(clk),
    .reset(reset),
    .ramp_start(ramp_cycle_start),
    .peak_valid(l3_peak_valid),
        .laser_id(l3_id),
        .laser_exists(l3_exists),
        .laser_locked(l3_locked),
        .pid_p(l3_pid_p),
        .pid_i(l3_pid_i),
        .pid_d(l3_pid_d),
        .set_wavelength(l3_set_wavelength),
        .current_wavelength(l3_detected_wavelength),
        .ref_wavelength(ref_set_wavelength),
        .feedback(l3_feedback)
    );
	laser_controller u_l4_controller (
    .clk(clk),
    .reset(reset),
    .ramp_start(ramp_cycle_start),
    .peak_valid(l4_peak_valid),
        .laser_id(l4_id),
        .laser_exists(l4_exists),
        .laser_locked(l4_locked),
        .pid_p(l4_pid_p),
        .pid_i(l4_pid_i),
        .pid_d(l4_pid_d),
        .set_wavelength(l4_set_wavelength),
        .current_wavelength(l4_detected_wavelength),
        .ref_wavelength(ref_set_wavelength),
        .feedback(l4_feedback)
    );

    feedback_dac_driver u_feedback_dac (
        .clk(clk),
        .enable(enable),
        .reset(reset),
        .update_trigger(ramp_done),
        .l1_feedback_value(l1_feedback),
        .l1_feedback_enable(l1_exists && l1_locked),
        .l2_feedback_value(l2_feedback),
        .l2_feedback_enable(l2_exists && l2_locked),
        .l3_feedback_value(l3_feedback),
        .l3_feedback_enable(l3_exists && l3_locked),
        .l4_feedback_value(l4_feedback),
        .l4_feedback_enable(l4_exists && l4_locked),

        .dac_cs(feedback_dac_cs),
        .dac_mosi(feedback_dac_mosi),
        .dac_sck(feedback_dac_sck)
    );

endmodule
