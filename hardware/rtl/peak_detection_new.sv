module peak_detection #(
	parameter logic [15:0] THRESHOLD      = 16'd2000,
	parameter logic [15:0] ASSIGN_WINDOW  = 16'd1500,
	parameter int unsigned MAX_CANDIDATES = 8
) (
	input  logic        clk,
	input  logic        reset,
	input  logic [15:0] adc_sample,
	input  logic        adc_sample_valid,
	input  logic [15:0] current_ramp_pos,
	input  logic        ramp_start,
	input  logic [15:0] ref_target,
	input  logic [15:0] l1_target,
	input  logic [15:0] l2_target,
	input  logic [15:0] l3_target,
	input  logic [15:0] l4_target,
	output logic [15:0] l1_position,
	output logic [15:0] l2_position,
	output logic [15:0] l3_position,
	output logic [15:0] l4_position,
	output logic        l1_valid,
	output logic        l2_valid,
	output logic        l3_valid,
	output logic        l4_valid
);

	localparam int unsigned IDX_W = (MAX_CANDIDATES <= 2) ? 1 : $clog2(MAX_CANDIDATES);

	logic in_spike;
	logic [15:0] curr_peak_amp;
	logic [15:0] curr_peak_pos;

	logic [15:0] candidate_pos [0:MAX_CANDIDATES-1];
	logic        candidate_valid [0:MAX_CANDIDATES-1];
	logic [IDX_W:0] candidate_count;

	integer i;

	always_ff @(posedge clk or posedge reset) begin
		if (reset) begin
			in_spike       <= 1'b0;
			curr_peak_amp  <= 16'd0;
			curr_peak_pos  <= 16'd0;
			candidate_count <= '0;
			l1_valid <= 1'b0;
			l2_valid <= 1'b0;
			l3_valid <= 1'b0;
			l4_valid <= 1'b0;

			l1_position <= l1_target;
			l2_position <= l2_target;
			l3_position <= l3_target;
			l4_position <= l4_target;

			for (i = 0; i < MAX_CANDIDATES; i = i + 1) begin
				candidate_pos[i]   <= 16'd0;
				candidate_valid[i] <= 1'b0;
			end
		end else begin
			l1_valid <= 1'b0;
			l2_valid <= 1'b0;
			l3_valid <= 1'b0;
			l4_valid <= 1'b0;

			if (ramp_start) begin
				logic [MAX_CANDIDATES-1:0] used_mask;
				logic ref_reserved;
				integer j;

				if (in_spike && (candidate_count < MAX_CANDIDATES)) begin
					candidate_pos[candidate_count[IDX_W-1:0]]   <= curr_peak_pos;
					candidate_valid[candidate_count[IDX_W-1:0]] <= 1'b1;
					candidate_count <= candidate_count + 1'b1;
				end

				in_spike      <= 1'b0;
				curr_peak_amp <= 16'd0;
				curr_peak_pos <= 16'd0;

				used_mask = '0;
				ref_reserved = 1'b0;

				// Reserve the first candidate near the reference target.
				for (j = 0; j < MAX_CANDIDATES; j = j + 1) begin
					if (candidate_valid[j] && !ref_reserved) begin
						if (((candidate_pos[j] >= ref_target) ? (candidate_pos[j] - ref_target) : (ref_target - candidate_pos[j])) <= ASSIGN_WINDOW) begin
							used_mask[j] = 1'b1;
							ref_reserved = 1'b1;
						end
					end
				end

				// Single-pass first-match assignment for each laser target.
				for (j = 0; j < MAX_CANDIDATES; j = j + 1) begin
					if (candidate_valid[j] && !used_mask[j]) begin
						if (!l1_valid && (((candidate_pos[j] >= l1_target) ? (candidate_pos[j] - l1_target) : (l1_target - candidate_pos[j])) <= ASSIGN_WINDOW)) begin
							l1_position <= candidate_pos[j];
							l1_valid <= 1'b1;
							used_mask[j] = 1'b1;
						end else if (!l2_valid && (((candidate_pos[j] >= l2_target) ? (candidate_pos[j] - l2_target) : (l2_target - candidate_pos[j])) <= ASSIGN_WINDOW)) begin
							l2_position <= candidate_pos[j];
							l2_valid <= 1'b1;
							used_mask[j] = 1'b1;
						end else if (!l3_valid && (((candidate_pos[j] >= l3_target) ? (candidate_pos[j] - l3_target) : (l3_target - candidate_pos[j])) <= ASSIGN_WINDOW)) begin
							l3_position <= candidate_pos[j];
							l3_valid <= 1'b1;
							used_mask[j] = 1'b1;
						end else if (!l4_valid && (((candidate_pos[j] >= l4_target) ? (candidate_pos[j] - l4_target) : (l4_target - candidate_pos[j])) <= ASSIGN_WINDOW)) begin
							l4_position <= candidate_pos[j];
							l4_valid <= 1'b1;
							used_mask[j] = 1'b1;
						end
					end
				end

				candidate_count <= '0;
				for (i = 0; i < MAX_CANDIDATES; i = i + 1) begin
					candidate_pos[i]   <= 16'd0;
					candidate_valid[i] <= 1'b0;
				end
			end

			if (adc_sample_valid) begin
				if (adc_sample > THRESHOLD) begin
					if (!in_spike) begin
						in_spike      <= 1'b1;
						curr_peak_amp <= adc_sample;
						curr_peak_pos <= current_ramp_pos;
					end else if (adc_sample >= curr_peak_amp) begin
						curr_peak_amp <= adc_sample;
						curr_peak_pos <= current_ramp_pos;
					end
				end else if (in_spike) begin
					if (candidate_count < MAX_CANDIDATES) begin
						candidate_pos[candidate_count[IDX_W-1:0]]   <= curr_peak_pos;
						candidate_valid[candidate_count[IDX_W-1:0]] <= 1'b1;
						candidate_count <= candidate_count + 1'b1;
					end

					in_spike      <= 1'b0;
					curr_peak_amp <= 16'd0;
					curr_peak_pos <= 16'd0;
				end
			end
		end
	end

endmodule
