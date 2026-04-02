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

    localparam CNV_START = 7'd10;
    localparam CNV_END   = 7'd49;
    localparam FRAME_LEN = 7'd100;
    localparam CAPTURE   = CNV_END + 7'd33;
    localparam VALID     = FRAME_LEN - 7'd1;

    logic [15:0] adc_shift_reg;
    logic        sck_prev;

    assign adc_cnv = enable && (frame_tick >= CNV_START) && (frame_tick <= CNV_END);
    assign adc_sck = enable ? frame_tick[0] : 1'b0;

    always_ff @(posedge clk or posedge reset) begin
        if (reset) begin
            adc_shift_reg       <= 16'h0000;
            adc_sample_unsigned <= 16'h0000;
            adc_sample_valid    <= 1'b0;
            sck_prev            <= 1'b0;
        end else begin
            sck_prev         <= adc_sck;
            adc_sample_valid <= 1'b0;

            if (enable) begin
                if (adc_sck && !sck_prev)
                    adc_shift_reg <= {adc_shift_reg[14:0], adc_miso};

                if (frame_tick == CAPTURE)
                    adc_sample_unsigned <= adc_shift_reg;

                if (frame_tick == VALID)
                    adc_sample_valid <= 1'b1;
            end
        end
    end

endmodule
