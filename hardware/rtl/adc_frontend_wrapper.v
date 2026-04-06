`timescale 1ns / 1ps

module adc_frontend_wrapper (
    input  wire        clk,
    input  wire        reset,
    input  wire        enable,
    input  wire [6:0]  frame_tick,
    input  wire        adc_miso,
    output wire        adc_cnv,
    output wire        adc_sck,
    output wire [15:0] adc_sample_unsigned,
    output wire        adc_sample_valid
);

    adc_frontend u_adc_frontend (
        .clk(clk),
        .reset(reset),
        .enable(enable),
        .frame_tick(frame_tick),
        .adc_miso(adc_miso),
        .adc_cnv(adc_cnv),
        .adc_sck(adc_sck),
        .adc_sample_unsigned(adc_sample_unsigned),
        .adc_sample_valid(adc_sample_valid)
    );

endmodule
