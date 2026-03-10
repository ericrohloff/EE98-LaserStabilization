`timescale 1ns / 1ps

module spi_controller #(
	parameter int CLKS_PER_HALF_BIT = 2
)(
	input  logic       clk,
	input  logic       reset,
	input  logic       tx_start,
	input  logic [7:0] tx_byte,
	output logic       spi_sclk,
	output logic       spi_mosi,
	output logic       busy,
	output logic       done
);

	localparam int DIV_COUNTER_WIDTH = (CLKS_PER_HALF_BIT <= 1) ? 1 : $clog2(CLKS_PER_HALF_BIT);

	logic [DIV_COUNTER_WIDTH-1:0] clk_div_count;
	logic [4:0] half_cycle_count;
	logic [2:0] bit_index;
	logic [7:0] tx_byte_latched;

	always_ff @(posedge clk or posedge reset) begin
		if (reset) begin
			spi_sclk        <= 1'b0;
			spi_mosi        <= 1'b0;
			busy            <= 1'b0;
			done            <= 1'b0;
			clk_div_count   <= '0;
			half_cycle_count<= '0;
			bit_index       <= 3'd7;
			tx_byte_latched <= 8'h00;
		end else begin
			done <= 1'b0;

			if (!busy) begin
				spi_sclk <= 1'b0;

				if (tx_start) begin
					busy             <= 1'b1;
					clk_div_count    <= '0;
					half_cycle_count <= 5'd0;
					bit_index        <= 3'd7;
					tx_byte_latched  <= tx_byte;
					spi_mosi         <= tx_byte[7];
				end
			end else begin
				if (clk_div_count == CLKS_PER_HALF_BIT - 1) begin
					clk_div_count <= '0;
					spi_sclk <= ~spi_sclk;

					if (spi_sclk) begin
						if (half_cycle_count < 5'd15) begin
							bit_index <= bit_index - 3'd1;
							spi_mosi <= tx_byte_latched[bit_index - 3'd1];
						end
					end

					if (half_cycle_count == 5'd15) begin
						busy <= 1'b0;
						done <= 1'b1;
						spi_sclk <= 1'b0;
					end else begin
						half_cycle_count <= half_cycle_count + 5'd1;
					end
				end else begin
					clk_div_count <= clk_div_count + 1'b1;
				end
			end
		end
	end

endmodule
