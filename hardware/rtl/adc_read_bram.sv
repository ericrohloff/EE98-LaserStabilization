`timescale 1ns / 1ps

module adc_bram_fsm (
    // ==========================================
    // AXI BRAM Controller Interface (Port A - Read Domain)
    // ==========================================
    input  logic        bram_clk_a,
    input  logic        bram_rst_a,
    input  logic        bram_en_a,
    input  logic [3:0]  bram_we_a,        // Typically 0 for our use case, but included for completeness
    input  logic [14:0] bram_addr_a,      // 15-bit byte address (up to 32KB)
    input  logic [31:0] bram_wrdata_a,
    output logic [31:0] bram_rddata_a,

    // ==========================================
    // Custom ADC Interface (Port B - Write Domain)
    // ==========================================
    input  logic        adc_clk,
    input  logic        adc_rst_n,        // Active low reset for the ADC domain
    
    // Control signals
    input  logic        requested,        // Assumed to come from a different domain (needs sync)
    input  logic        ramp_start,       // Starts recording (rising edge)
    input  logic [15:0] counter,          // Stops recording when it reaches 0
    input  logic [15:0] adc_sample_in     // 16-bit data
);

    // ==========================================
    // Memory Array Definition (4096 words x 32 bits)
    // ==========================================
    // Synthesis tools will infer this as a Block RAM.
    logic [31:0] ram_memory [0:4095];

    // ==========================================
    // Synchronizers & Edge Detectors (ADC Clock Domain)
    // ==========================================
    
    // 1. Synchronize and edge-detect 'requested' (assuming it might be asynchronous)
    logic [2:0] req_sync_shift;
    logic       requested_rising_edge;
    
    always_ff @(posedge adc_clk or negedge adc_rst_n) begin
        if (!adc_rst_n) begin
            req_sync_shift <= 3'b000;
        end else begin
            req_sync_shift <= {req_sync_shift[1:0], requested};
        end
    end
    assign requested_rising_edge = (req_sync_shift[2:1] == 2'b01);

    // 2. Edge detector for 'ramp_start' (assuming it's already synchronous to adc_clk)
    logic ramp_start_d;
    logic ramp_start_rising_edge;
    
    always_ff @(posedge adc_clk or negedge adc_rst_n) begin
        if (!adc_rst_n) begin
            ramp_start_d <= 1'b0;
        end else begin
            ramp_start_d <= ramp_start;
        end
    end
    assign ramp_start_rising_edge = (ramp_start && !ramp_start_d);


    // ==========================================
    // State Machine (ADC Clock Domain)
    // ==========================================
    typedef enum logic [1:0] {
        ST_IDLE       = 2'b00,
        ST_WAIT_RAMP  = 2'b01,
        ST_RECORDING  = 2'b10,
        ST_READ_MODE  = 2'b11
    } state_t;

    state_t current_state, next_state;
    logic [11:0] write_addr; // 12 bits to cover 0 to 4095

    // State Register & Write Address Counter
    always_ff @(posedge adc_clk or negedge adc_rst_n) begin
        if (!adc_rst_n) begin
            current_state <= ST_IDLE;
            write_addr    <= 12'd0;
        end else begin
            current_state <= next_state;
            
            // Manage Write Address
            if (current_state == ST_WAIT_RAMP && ramp_start_rising_edge) begin
                write_addr <= 12'd0; // Reset address at start of new capture
            end else if (current_state == ST_RECORDING) begin
                // Stop incrementing if we hit max memory size to prevent overflow
                if (write_addr < 12'd4095) begin
                    write_addr <= write_addr + 1'b1;
                end
            end
        end
    end

    // Next State Logic
    always_comb begin
        next_state = current_state; // Default: stay in current state
        
        case (current_state)
            ST_IDLE: begin
                if (requested_rising_edge) begin
                    next_state = ST_WAIT_RAMP;
                end
            end
            
            ST_WAIT_RAMP: begin
                if (ramp_start_rising_edge) begin
                    next_state = ST_RECORDING;
                end
            end
            
            ST_RECORDING: begin
                if (counter == 16'd0 || write_addr == 12'd4095) begin
                    // Stop if counter hits zero OR if we max out memory capacity
                    next_state = ST_READ_MODE;
                end
            end
            
            ST_READ_MODE: begin
                // Wait here until a new request restarts the cycle
                if (requested_rising_edge) begin
                    next_state = ST_WAIT_RAMP;
                end
            end
            
            default: next_state = ST_IDLE;
        endcase
    end


    // ==========================================
    // RAM Port Operations
    // ==========================================
    
    // Port A: Read Domain (AXI BRAM Controller)
    // ------------------------------------------
    // AXI bram_addr_a is a byte address. We drop the lowest 2 bits ([1:0]) 
    // to convert it to a 32-bit word index. Bits [13:2] give us a 12-bit index (4096 words).
    logic [11:0] read_word_addr;
    assign read_word_addr = bram_addr_a[13:2];

    always_ff @(posedge bram_clk_a) begin
        if (bram_en_a) begin
            // Optional: Support writes from AXI (usually not needed for capture buffers)
            if (|bram_we_a) begin 
                ram_memory[read_word_addr] <= bram_wrdata_a;
            end
            
            // AXI Read operation
            bram_rddata_a <= ram_memory[read_word_addr];
        end
    end

    // Port B: Write Domain (ADC Controller)
    // ------------------------------------------
    always_ff @(posedge adc_clk) begin
        // Only write data when actively in the RECORDING state
        if (current_state == ST_RECORDING) begin
            // Zero padding the 16-bit ADC sample into the 32-bit slot
            ram_memory[write_addr] <= {16'd0, adc_sample_in};
        end
    end

endmodule