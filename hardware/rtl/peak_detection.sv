module peak_detection #(
	parameter logic [15:0] THRESHOLD      = 16'd7500,
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

	logic [15:0] candidate_amp [0:MAX_CANDIDATES-1];
	logic [15:0] candidate_pos [0:MAX_CANDIDATES-1];
	logic        candidate_valid [0:MAX_CANDIDATES-1];
	logic [IDX_W:0] candidate_count;

	integer i;

	function automatic [15:0] abs_diff;
		input [15:0] a;
		input [15:0] b;
		begin
			if (a >= b)
				abs_diff = a - b;
			else
				abs_diff = b - a;
		end
	endfunction

	task automatic select_candidate;
		input  [15:0] expected_pos;
		input  [MAX_CANDIDATES-1:0] used_mask;
		output logic found;
		output logic [IDX_W-1:0] selected_idx;
		integer j;
		logic [15:0] this_diff;
		logic [15:0] best_diff;
		begin
			found = 1'b0;
			selected_idx = '0;
			best_diff = 16'hFFFF;

			for (j = 0; j < MAX_CANDIDATES; j = j + 1) begin
				if (candidate_valid[j] && !used_mask[j]) begin
					this_diff = abs_diff(candidate_pos[j], expected_pos);
					if ((this_diff <= ASSIGN_WINDOW) && (!found || (this_diff < best_diff))) begin
						found = 1'b1;
						selected_idx = j[IDX_W-1:0];
						best_diff = this_diff;
					end
				end
			end
		end
	endtask

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
				candidate_amp[i]   <= 16'd0;
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
				logic found;
				logic [IDX_W-1:0] idx;

				if (in_spike && (candidate_count < MAX_CANDIDATES)) begin
					candidate_amp[candidate_count[IDX_W-1:0]]   <= curr_peak_amp;
					candidate_pos[candidate_count[IDX_W-1:0]]   <= curr_peak_pos;
					candidate_valid[candidate_count[IDX_W-1:0]] <= 1'b1;
					candidate_count <= candidate_count + 1'b1;
				end

				in_spike      <= 1'b0;
				curr_peak_amp <= 16'd0;
				curr_peak_pos <= 16'd0;

				used_mask = '0;

				// Reserve the best candidate near the reference target first.
				select_candidate(ref_target, used_mask, found, idx);
				if (found)
					used_mask[idx] = 1'b1;

				select_candidate(l1_target, used_mask, found, idx);
				if (found) begin
					l1_position <= candidate_pos[idx];
					l1_valid <= 1'b1;
					used_mask[idx] = 1'b1;
				end

				select_candidate(l2_target, used_mask, found, idx);
				if (found) begin
					l2_position <= candidate_pos[idx];
					l2_valid <= 1'b1;
					used_mask[idx] = 1'b1;
				end

				select_candidate(l3_target, used_mask, found, idx);
				if (found) begin
					l3_position <= candidate_pos[idx];
					l3_valid <= 1'b1;
					used_mask[idx] = 1'b1;
				end

				select_candidate(l4_target, used_mask, found, idx);
				if (found) begin
					l4_position <= candidate_pos[idx];
					l4_valid <= 1'b1;
				end

				candidate_count <= '0;
				for (i = 0; i < MAX_CANDIDATES; i = i + 1) begin
					candidate_amp[i]   <= 16'd0;
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
						candidate_amp[candidate_count[IDX_W-1:0]]   <= curr_peak_amp;
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
