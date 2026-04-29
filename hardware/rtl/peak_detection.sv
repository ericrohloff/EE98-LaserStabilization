module peak_detection #(
	parameter logic [15:0] THRESHOLD      = 16'd7500,
	parameter logic [15:0] ASSIGN_WINDOW  = 16'd1500,
	parameter int unsigned MAX_CANDIDATES = 6
) (
	input  logic        clk,
	input  logic        reset,
	input  logic [15:0] adc_sample,
	input  logic        adc_sample_valid,
	input  logic [15:0] current_ramp_pos,
	input  logic        ramp_start,
	input  logic 		l1_exists,
	input  logic 		l2_exists,
	input  logic 		l3_exists,
	input  logic 		l4_exists,
	input  logic 		l1_locked,
	input  logic 		l2_locked,
	input  logic 		l3_locked,
	input  logic 		l4_locked,
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

	logic [15:0] r1_position;
	logic [15:0] r2_position;

	logic [3:0] locked_mask = {l4_locked && l4_exists, l3_locked && l3_exists, l2_locked && l2_exists, l1_locked && l1_exists};
	integer num_locked = locked_mask[0] + locked_mask[1] + locked_mask[2] + locked_mask[3];


	// candidates: r1, l1, l2, l3, l4, r2
	// always assign r1 to first, r2 to last 
	// then assign l1-l4 to middle based on which are locked
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

			l1_position <= 16'd0;
			l2_position <= 16'd0;
			l3_position <= 16'd0;
			l4_position <= 16'd0;

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

				if (in_spike && (candidate_count < MAX_CANDIDATES)) begin
					candidate_amp[candidate_count[IDX_W-1:0]]   <= curr_peak_amp;
					candidate_pos[candidate_count[IDX_W-1:0]]   <= curr_peak_pos;
					candidate_valid[candidate_count[IDX_W-1:0]] <= 1'b1;
					candidate_count <= candidate_count + 1'b1;
				end

				in_spike      <= 1'b0;
				curr_peak_amp <= 16'd0;
				curr_peak_pos <= 16'd0;


				// assign candidates in order based on how many found 
				// invalid- didn't see both reference peaks 
				// based on candidate_count, assign reference peaks in order r1, l1 ... l4, r2

				// didn't see correct number of peaks 
				if (candidate_count != num_locked + 2) begin 
					r1_position <= 16'd0;
					r2_position <= 16'd0;
					l1_position <= 16'd0;
					l2_position <= 16'd0;
					l3_position <= 16'd0;
					l4_position <= 16'd0;
					l1_valid <= 1'b0;
					l2_valid <= 1'b0;
					l3_valid <= 1'b0;
					l4_valid <= 1'b0;
				end else begin
					// assign r1 to lowest pos, r2 to highest pos 
					r1_position <= candidate_pos[0];
					r2_position <= candidate_pos[candidate_count-1];
					// assign l1-l4 to middle candidates based on which are locked 
					integer candidate_index = 1; 
					for (i = 0; i < 4; i = i + 1) begin 
						if (locked_mask[i]) begin 
							case (i) 
								0: begin l1_position <= candidate_pos[candidate_index]; l1_valid <= 1'b1; end
								1: begin l2_position <= candidate_pos[candidate_index]; l2_valid <= 1'b1; end
								2: begin l3_position <= candidate_pos[candidate_index]; l3_valid <= 1'b1; end
								3: begin l4_position <= candidate_pos[candidate_index]; l4_valid <= 1'b1; end
							endcase
							candidate_index = candidate_index + 1;
						end else begin 
							case (i) 
								0: begin l1_position <= 16'd0; l1_valid <= 1'b0; end
								1: begin l2_position <= 16'd0; l2_valid <= 1'b0; end
								2: begin l3_position <= 16'd0; l3_valid <= 1'b0; end
								3: begin l4_position <= 16'd0; l4_valid <= 1'b0; end
							endcase
						end
					end
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
