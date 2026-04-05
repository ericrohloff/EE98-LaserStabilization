module peak_detection (
	input  logic [15:0] adc_sample,
	input  logic        ramp_start,
	input  logic [15:0] ref_target,
	input  logic [15:0] l1_target,
	input  logic [15:0] l2_target,
	input  logic [15:0] l3_target,
	input  logic [15:0] l4_target,
	output logic [15:0] l1_position,
	output logic [15:0] l2_position,
	output logic [15:0] l3_position,
	output logic [15:0] l4_position
);

assign l1_position = l1_target;
assign l2_position = l2_target;
assign l3_position = l3_target;
assign l4_position = l4_target;

endmodule
