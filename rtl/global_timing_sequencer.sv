`timescale 1ns / 1ps

module global_timing_sequencer (
    input  logic       clk,
    input  logic       reset,
    input  logic       enable,
    output logic [6:0] frame_tick,
    output logic       frame_start,
    output logic       frame_boundary,
    output logic       phase_0_31,
    output logic       phase_32_49,
    output logic       phase_50_81,
    output logic       phase_82_98
);

    always_ff @(posedge clk or posedge reset) begin
        if (reset) begin
            frame_tick <= 7'd0;
        end else if (enable) begin
            if (frame_tick == 7'd99) begin
                frame_tick <= 7'd0;
            end else begin
                frame_tick <= frame_tick + 7'd1;
            end
        end
    end

    always_comb begin
        frame_start    = (enable && (frame_tick == 7'd0));
        frame_boundary = (enable && (frame_tick == 7'd99));

        phase_0_31  = (frame_tick <= 7'd31);
        phase_32_49 = (frame_tick >= 7'd32) && (frame_tick <= 7'd49);
        phase_50_81 = (frame_tick >= 7'd50) && (frame_tick <= 7'd81);
        phase_82_98 = (frame_tick >= 7'd82) && (frame_tick <= 7'd98);
    end

endmodule
