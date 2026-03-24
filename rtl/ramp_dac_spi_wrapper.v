`timescale 1ns / 1ps

module ramp_dac_spi_wrapper (
    input  wire        clk,
    input  wire        reset,
    input  wire        enable,
    input  wire [6:0]  frame_tick,
    input  wire [15:0] ramp_step,
    input  wire [15:0] ramp_min,
    input  wire [15:0] ramp_max,
    input  wire        triangle_mode,
    output wire        ramp_dac_cs_n,
    output wire        ramp_dac_sck,
    output wire        ramp_dac_mosi,
    output wire        ramp_dac_ldac_n,
    output wire [15:0] current_ramp_pos,
    output wire        ramp_cycle_start
);

    ramp_dac_spi u_ramp_dac_spi (
        .clk(clk),
        .reset(reset),
        .enable(enable),
        .frame_tick(frame_tick),
        .ramp_step(ramp_step),
        .ramp_min(ramp_min),
        .ramp_max(ramp_max),
        .triangle_mode(triangle_mode),
        .ramp_dac_cs_n(ramp_dac_cs_n),
        .ramp_dac_sck(ramp_dac_sck),
        .ramp_dac_mosi(ramp_dac_mosi),
        .ramp_dac_ldac_n(ramp_dac_ldac_n),
        .current_ramp_pos(current_ramp_pos),
        .ramp_cycle_start(ramp_cycle_start)
    );

endmodule
