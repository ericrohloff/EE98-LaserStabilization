`timescale 1ns / 1ps

module output_dac_spi (
    input  logic        clk_100m,
    input  logic        reset_n,
    input  logic        control_signal_valid,
    input  logic [15:0] dac_ch0_data,
    input  logic [15:0] dac_ch1_data,
    input  logic [15:0] dac_ch2_data,
    input  logic [15:0] dac_ch3_data,
    output logic        out_dac_cs_n,
    output logic        out_dac_sck,
    output logic        out_dac_mosi,
    output logic        out_dac_busy
);

    // DAC command codes
    localparam logic [1:0] SINGLE_UPDATE = 2'b01;
    localparam logic [1:0] BROAD_UPDATE = 2'b11;
    
    // Clock divider for 2MHz SPI from 100MHz system clock
    // Need 25 clocks for half-period: 100MHz / 50 = 2MHz
    localparam int CLKS_PER_HALF_BIT = 25;
    localparam int DIV_COUNTER_WIDTH = $clog2(CLKS_PER_HALF_BIT);
    
    // FSM states
    typedef enum logic [3:0] {
        IDLE,
        LOAD_CH0,
        LOAD_CH1,
        LOAD_CH2,
        LOAD_CH3,
        BROADCAST_CMD,
        DONE
    } state_t;
    
    state_t state, next_state;
    
    // Clock divider signals
    logic [DIV_COUNTER_WIDTH-1:0] clk_div_count;
    logic [5:0] half_cycle_count;  // 16 half-cycles for 8 bits, 48 for 24 bits
    logic [4:0] bit_index;
    
    // SPI shift and command byte
    logic [23:0] shift_buffer;
    logic [7:0] addr_byte;
    
    // =========================================================================
    // Clock Divider and SPI Clock Generation
    // =========================================================================
    always_ff @(posedge clk_100m or negedge reset_n) begin
        if (!reset_n) begin
            clk_div_count   <= '0;
            half_cycle_count <= '0;
            out_dac_sck      <= 1'b0;
        end else begin
            if (out_dac_busy) begin
                if (clk_div_count == CLKS_PER_HALF_BIT - 1) begin
                    clk_div_count <= '0;
                    out_dac_sck <= ~out_dac_sck;
                    
                    // Increment half-cycle counter when clock toggles HIGH
                    if (~out_dac_sck) begin
                        if (half_cycle_count == 6'd47) begin  // 48 half-cycles = 24 bits
                            half_cycle_count <= '0;
                        end else begin
                            half_cycle_count <= half_cycle_count + 1'b1;
                        end
                    end
                end else begin
                    clk_div_count <= clk_div_count + 1'b1;
                end
            end else begin
                clk_div_count <= '0;
                half_cycle_count <= '0;
                out_dac_sck <= 1'b0;
            end
        end
    end
    
    // =========================================================================
    // MOSI Output (Shift MSB first)
    // =========================================================================
    assign out_dac_mosi = shift_buffer[23];
    
    // =========================================================================
    // Bit Shifting (on rising edge of SPI clock)
    // =========================================================================
    always_ff @(posedge clk_100m or negedge reset_n) begin
        if (!reset_n) begin
            shift_buffer <= 24'd0;
        end else begin
            // Shift on rising edge of SPI clock
            if (out_dac_busy && (clk_div_count == CLKS_PER_HALF_BIT - 1) && out_dac_sck == 1'b0) begin
                shift_buffer <= {shift_buffer[22:0], 1'b0};
            end
        end
    end
    
    // =========================================================================
    // FSM State Machine
    // =========================================================================
    always_ff @(posedge clk_100m or negedge reset_n) begin
        if (!reset_n) begin
            state <= IDLE;
        end else begin
            state <= next_state;
        end
    end
    
    always_comb begin
        next_state = state;
        
        case (state)
            IDLE: begin
                if (control_signal_valid) begin
                    next_state = LOAD_CH0;
                end
            end
            LOAD_CH0: begin
                if (half_cycle_count == 6'd47 && clk_div_count == CLKS_PER_HALF_BIT - 1) begin
                    next_state = LOAD_CH1;
                end
            end
            LOAD_CH1: begin
                if (half_cycle_count == 6'd47 && clk_div_count == CLKS_PER_HALF_BIT - 1) begin
                    next_state = LOAD_CH2;
                end
            end
            LOAD_CH2: begin
                if (half_cycle_count == 6'd47 && clk_div_count == CLKS_PER_HALF_BIT - 1) begin
                    next_state = LOAD_CH3;
                end
            end
            LOAD_CH3: begin
                if (half_cycle_count == 6'd47 && clk_div_count == CLKS_PER_HALF_BIT - 1) begin
                    next_state = BROADCAST_CMD;
                end
            end
            BROADCAST_CMD: begin
                if (half_cycle_count == 6'd47 && clk_div_count == CLKS_PER_HALF_BIT - 1) begin
                    next_state = DONE;
                end
            end
            DONE: begin
                next_state = IDLE;
            end
            default: next_state = IDLE;
        endcase
    end
    
    // =========================================================================
    // Load Buffer on State Transition
    // =========================================================================
    always_ff @(posedge clk_100m or negedge reset_n) begin
        if (!reset_n) begin
            shift_buffer <= 24'd0;
        end else if (state != next_state) begin
            case (next_state)
                LOAD_CH0: begin
                    shift_buffer <= {{SINGLE_UPDATE, 2'b00, 1'b0}, dac_ch0_data};
                end
                LOAD_CH1: begin
                    shift_buffer <= {{SINGLE_UPDATE, 2'b01, 1'b0}, dac_ch1_data};
                end
                LOAD_CH2: begin
                    shift_buffer <= {{SINGLE_UPDATE, 2'b10, 1'b0}, dac_ch2_data};
                end
                LOAD_CH3: begin
                    shift_buffer <= {{SINGLE_UPDATE, 2'b11, 1'b0}, dac_ch3_data};
                end
                BROADCAST_CMD: begin
                    // Broadcast update command: cmd=11, ch=xx, A0=0 (data doesn't matter)
                    shift_buffer <= {{BROAD_UPDATE, 6'b000000}, 16'd0};
                end
                default: begin
                    // No change
                end
            endcase
        end
    end
    
    // =========================================================================
    // Output Control
    // =========================================================================
    assign out_dac_busy = (state != IDLE);
    
    // CS goes LOW during transfer (when busy), HIGH otherwise
    assign out_dac_cs_n = ~out_dac_busy;

endmodule
