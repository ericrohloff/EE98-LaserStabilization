`timescale 1ns / 1ps

module ramp_dac_spi (
    input  logic        clk,
    input  logic        reset,
    input  logic        enable,
    input  logic [6:0]  frame_tick,
    input  logic [15:0] ramp_step,
    input  logic [15:0] ramp_min,
    input  logic [15:0] ramp_max,
    input  logic        triangle_mode,
    output logic        ramp_dac_cs_n,
    output logic        ramp_dac_sck,
    output logic        ramp_dac_mosi,
    output logic        ramp_dac_ldac_n,
    output logic [15:0] current_ramp_pos,
    output logic        ramp_cycle_start
);

    localparam logic [6:0] DAC_SHIFT_END_TICK = 7'd31;
    localparam logic [6:0] LDAC_LOW_START_TICK = 7'd33;
    localparam logic [6:0] LDAC_LOW_END_TICK = 7'd36;

    logic [15:0] tx_word;
    logic        ramp_dir_up;

    logic [16:0] up_candidate;
    logic [16:0] min_plus_step;

    assign up_candidate  = {1'b0, current_ramp_pos} + {1'b0, ramp_step};
    assign min_plus_step = {1'b0, ramp_min} + {1'b0, ramp_step};

    always_ff @(posedge clk or posedge reset) begin
        if (reset) begin
            current_ramp_pos <= ramp_min;
            tx_word          <= ramp_min;
            ramp_cycle_start <= 1'b0;
            ramp_dir_up      <= 1'b1;
        end else begin
            ramp_cycle_start <= 1'b0;

            if (enable) begin
                if (frame_tick == 7'd0) begin
                    tx_word <= current_ramp_pos;
                end else if ((frame_tick >= 7'd2) && (frame_tick <= 7'd30) && (frame_tick[0] == 1'b0)) begin
                    tx_word <= {tx_word[14:0], 1'b0};
                end

                if (frame_tick == 7'd50) begin
                    if (!triangle_mode) begin
                        if (up_candidate > {1'b0, ramp_max}) begin
                            current_ramp_pos <= ramp_min;
                            ramp_cycle_start <= 1'b1;
                        end else begin
                            current_ramp_pos <= up_candidate[15:0];
                        end
                    end else begin
                        if (ramp_dir_up) begin
                            if (up_candidate >= {1'b0, ramp_max}) begin
                                current_ramp_pos <= ramp_max;
                                ramp_dir_up      <= 1'b0;
                                ramp_cycle_start <= 1'b1;
                            end else begin
                                current_ramp_pos <= up_candidate[15:0];
                            end
                        end else begin
                            if ({1'b0, current_ramp_pos} <= min_plus_step) begin
                                current_ramp_pos <= ramp_min;
                                ramp_dir_up      <= 1'b1;
                                ramp_cycle_start <= 1'b1;
                            end else begin
                                current_ramp_pos <= current_ramp_pos - ramp_step;
                            end
                        end
                    end
                end
            end
        end
    end

    assign ramp_dac_cs_n = !(enable && (frame_tick <= DAC_SHIFT_END_TICK));
    assign ramp_dac_sck  = enable ? frame_tick[0] : 1'b0;
    assign ramp_dac_mosi = tx_word[15];
    assign ramp_dac_ldac_n = !(enable && (frame_tick >= LDAC_LOW_START_TICK) && (frame_tick <= LDAC_LOW_END_TICK));

endmodule
