`timescale 1ns / 1ps

module global_timing_sequencer_wrapper (
    input  wire       clk,
    input  wire       reset,
    input  wire       enable,
    output wire [6:0] frame_tick,
    output wire       frame_start,
    output wire       frame_boundary,
    output wire       phase_0_31,
    output wire       phase_32_49,
    output wire       phase_50_81,
    output wire       phase_82_98
);

    global_timing_sequencer u_global_timing_sequencer (
        .clk(clk),
        .reset(reset),
        .enable(enable),
        .frame_tick(frame_tick),
        .frame_start(frame_start),
        .frame_boundary(frame_boundary),
        .phase_0_31(phase_0_31),
        .phase_32_49(phase_32_49),
        .phase_50_81(phase_50_81),
        .phase_82_98(phase_82_98)
    );

endmodule
