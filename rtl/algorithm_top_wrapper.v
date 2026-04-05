module algorithm_top_wrapper (
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
	output wire dac_ldac_n
);

algorithm_top u_algorithm_top (
    ref_id,
    ref_exists,
    ref_locked,
    ref_pid_p,
    ref_pid_i,
    ref_pid_d,
    ref_set_wavelength,
    ref_detected_wavelength,

    l1_id,
    l1_exists,
    l1_locked,
    l1_pid_p,
    l1_pid_i,
    l1_pid_d,
    l1_set_wavelength,
    l1_detected_wavelength,

    l2_id,
    l2_exists,
    l2_locked,
    l2_pid_p,
    l2_pid_i,
    l2_pid_d,
    l2_set_wavelength,
    l2_detected_wavelength,

    l3_id,
    l3_exists,
    l3_locked,
    l3_pid_p,
    l3_pid_i,
    l3_pid_d,
    l3_set_wavelength,
    l3_detected_wavelength,

    l4_id,
    l4_exists,
    l4_locked,
    l4_pid_p,
    l4_pid_i,
    l4_pid_d,
    l4_set_wavelength,
    l4_detected_wavelength,

    system_on,
    system_locked,

	// Hardware I/O
    clk,
    reset,
    enable,

    adc_miso,
    adc_sck,
    adc_cnv,
    adc_sample_unsigned,

    dac_mosi,
    dac_sck,
    dac_cs,
	dac_ldac_n
);

endmodule