`timescale 1ns / 1ps

module adc_frontend (
    input  logic        clk,
    input  logic        reset,
    input  logic        enable,
    input  logic [6:0]  frame_tick,
    input  logic        adc_miso,
    output logic        adc_cnv,
    output logic        adc_sck,
    output logic [15:0] adc_sample_unsigned,
    output logic        adc_sample_valid
);

    logic [15:0] adc_shift_reg;

    always @(posedge adc_sck or posedge reset) begin
        if (reset) begin
            adc_shift_reg <= 16'h0000;
        end else if (enable && !adc_cnv) begin
            adc_shift_reg <= {adc_shift_reg[14:0], adc_miso};
        end
    end

    always_ff @(posedge clk or posedge reset) begin
        if (reset) begin
            adc_sample_unsigned <= 16'h0000;
            adc_sample_valid    <= 1'b0;
        end else begin
            adc_sample_valid <= 1'b0;

            if (enable) begin
                if (frame_tick == 7'd82) begin
                    adc_sample_unsigned <= adc_shift_reg;
                end

                if (frame_tick == 7'd99) begin
                    adc_sample_valid <= 1'b1;
                end
            end
        end
    end

    assign adc_cnv = (enable && (frame_tick <= 7'd49));
    assign adc_sck = enable ? frame_tick[0] : 1'b0;

endmodule
