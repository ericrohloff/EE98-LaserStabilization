module peak_detection_wrapper (
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

peak_detection u_peak_detection(
	.adc_sample(adc_sample),
	.ramp_start(ramp_start),
	.ref_target(ref_target),
	.l1_target(l1_target),
	.l2_target(l2_target),
	.l3_target(l3_target),
	.l4_target(l4_target),
	.l1_position(l1_position),
	.l2_position(l2_position),
	.l3_position(l3_position),
	.l4_position(l4_position)
);

endmodule
