module feedback_dac_driver (
    input wire clk,
    input wire enable,
    input wire reset,
    input wire update_trigger,

    input wire [15:0] l1_feedback_value,
    input wire l1_feedback_enable,
    input wire [15:0] l2_feedback_value,
    input wire l2_feedback_enable,
    input wire [15:0] l3_feedback_value,
    input wire l3_feedback_enable,
    input wire [15:0] l4_feedback_value,
    input wire l4_feedback_enable,

    output wire dac_cs,
    output wire dac_mosi,
    output wire dac_sck
);

localparam [1:0] DAC_SINGLE_UPDATE = 2'b01;
localparam integer CLKS_PER_HALF_BIT = 5;  // 100MHz -> 10MHz SCK
localparam integer LOAD_WAIT_CLKS = (4 * CLKS_PER_HALF_BIT);  // 2 full dac_sck cycles

localparam [1:0] CH_L1 = 2'b00;
localparam [1:0] CH_L2 = 2'b01;
localparam [1:0] CH_L3 = 2'b10;
localparam [1:0] CH_L4 = 2'b11;

localparam [1:0] ST_IDLE = 2'd0;
localparam [1:0] ST_LOAD = 2'd1;
localparam [1:0] ST_SHIFT = 2'd2;

reg [1:0] state;

wire trigger_rise;

reg [15:0] value_l1_lat;
reg [15:0] value_l2_lat;
reg [15:0] value_l3_lat;
reg [15:0] value_l4_lat;

reg [3:0] pending_mask;
reg [1:0] active_channel;

reg [7:0] addr_byte;
reg [23:0] shift_reg;

reg [2:0] clk_div_count;
reg [4:0] bits_sent;
reg last_bit_sampled;
reg [5:0] load_wait_count;
reg load_prepared;

reg dac_cs_r;
reg dac_sck_r;
reg dac_mosi_r;

assign dac_cs = dac_cs_r;
assign dac_sck = dac_sck_r;
assign dac_mosi = dac_mosi_r;


always @(posedge clk or posedge reset) begin
    if (reset) begin
        state <= ST_IDLE;
        value_l1_lat <= 16'd0;
        value_l2_lat <= 16'd0;
        value_l3_lat <= 16'd0;
        value_l4_lat <= 16'd0;
        pending_mask <= 4'b0000;
        active_channel <= 2'b00;
        addr_byte <= 8'd0;
        shift_reg <= 24'd0;
        clk_div_count <= 3'd0;
        bits_sent <= 5'd0;
        last_bit_sampled <= 1'b0;
        load_wait_count <= 6'd0;
        load_prepared <= 1'b0;
        dac_cs_r <= 1'b1;
        dac_sck_r <= 1'b0;
        dac_mosi_r <= 1'b0;
    end else begin

        case (state)
            ST_IDLE: begin
                dac_cs_r <= 1'b1;
                dac_sck_r <= 1'b0;
                clk_div_count <= 3'd0;
                bits_sent <= 5'd0;
                last_bit_sampled <= 1'b0;
                load_wait_count <= 6'd0;
                load_prepared <= 1'b0;

                if (enable && update_trigger) begin
                    // Latch values and channel enables once per trigger edge.
                    value_l1_lat <= l1_feedback_value;
                    value_l2_lat <= l2_feedback_value;
                    value_l3_lat <= l3_feedback_value;
                    value_l4_lat <= l4_feedback_value;
                    pending_mask <= {
                        l4_feedback_enable,
                        l3_feedback_enable,
                        l2_feedback_enable,
                        l1_feedback_enable
                    };

                    if (l1_feedback_enable || l2_feedback_enable || l3_feedback_enable || l4_feedback_enable) begin
                        state <= ST_LOAD;
                    end
                end
            end

            ST_LOAD: begin
                dac_cs_r <= 1'b1;
                dac_sck_r <= 1'b0;
                clk_div_count <= 3'd0;
                bits_sent <= 5'd0;
                last_bit_sampled <= 1'b0;

                if (!load_prepared) begin
                    load_wait_count <= 6'd0;

                    if (pending_mask[0]) begin
                        active_channel <= CH_L1;
                        addr_byte <= {2'b00, DAC_SINGLE_UPDATE, 1'b0, CH_L1, 1'b0};
                        shift_reg <= {{2'b00, DAC_SINGLE_UPDATE, 1'b0, CH_L1, 1'b0}, value_l1_lat};
                        dac_mosi_r <= 1'b0;
                        pending_mask[0] <= 1'b0;
                        load_prepared <= 1'b1;
                    end else if (pending_mask[1]) begin
                        active_channel <= CH_L2;
                        addr_byte <= {2'b00, DAC_SINGLE_UPDATE, 1'b0, CH_L2, 1'b0};
                        shift_reg <= {{2'b00, DAC_SINGLE_UPDATE, 1'b0, CH_L2, 1'b0}, value_l2_lat};
                        dac_mosi_r <= 1'b0;
                        pending_mask[1] <= 1'b0;
                        load_prepared <= 1'b1;
                    end else if (pending_mask[2]) begin
                        active_channel <= CH_L3;
                        addr_byte <= {2'b00, DAC_SINGLE_UPDATE, 1'b0, CH_L3, 1'b0};
                        shift_reg <= {{2'b00, DAC_SINGLE_UPDATE, 1'b0, CH_L3, 1'b0}, value_l3_lat};
                        dac_mosi_r <= 1'b0;
                        pending_mask[2] <= 1'b0;
                        load_prepared <= 1'b1;
                    end else if (pending_mask[3]) begin
                        active_channel <= CH_L4;
                        addr_byte <= {2'b00, DAC_SINGLE_UPDATE, 1'b0, CH_L4, 1'b0};
                        shift_reg <= {{2'b00, DAC_SINGLE_UPDATE, 1'b0, CH_L4, 1'b0}, value_l4_lat};
                        dac_mosi_r <= 1'b0;
                        pending_mask[3] <= 1'b0;
                        load_prepared <= 1'b1;
                    end else begin
                        state <= ST_IDLE;
                    end
                end else if (load_wait_count == (LOAD_WAIT_CLKS - 1)) begin
                    load_wait_count <= 6'd0;
                    load_prepared <= 1'b0;
                    state <= ST_SHIFT;
                    dac_cs_r <= 1'b0;
                end else begin
                    load_wait_count <= load_wait_count + 6'd1;
                end
            end

            ST_SHIFT: begin
                if (clk_div_count == (CLKS_PER_HALF_BIT - 1)) begin
                    clk_div_count <= 3'd0;

                    if (!dac_sck_r) begin
                        // Rising edge: DAC samples MOSI in SPI mode 0.
                        dac_sck_r <= 1'b1;
                        if (bits_sent == 5'd23) begin
                            last_bit_sampled <= 1'b1;
                        end
                        bits_sent <= bits_sent + 5'd1;
                    end else begin
                        // Falling edge: update next MOSI bit.
                        dac_sck_r <= 1'b0;

                        if (last_bit_sampled) begin
                            dac_cs_r <= 1'b1;
                            last_bit_sampled <= 1'b0;
                            bits_sent <= 5'd0;

                            if (pending_mask != 4'b0000) begin
                                state <= ST_LOAD;
                            end else begin
                                state <= ST_IDLE;
                            end
                        end else begin
                            shift_reg <= {shift_reg[22:0], 1'b0};
                            dac_mosi_r <= shift_reg[22];
                        end
                    end
                end else begin
                    clk_div_count <= clk_div_count + 3'd1;
                end
            end

            default: begin
                state <= ST_IDLE;
            end
        endcase
    end
end

endmodule