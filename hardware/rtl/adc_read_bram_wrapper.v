module adc_bram_wrapper (
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

    adc_bram_fsm u_bram(
        .bram_clk_a(bram_clk_a),
        .bram_rst_a(bram_rst_a),
        .bram_en_a(bram_en_a),
        .bram_we_a(bram_we_a),
        .bram_addr_a(bram_addr_a),
        .bram_wrdata_a(bram_wrdata_a),
        .bram_rddata_a(bram_rddata_a),

        .adc_clk(adc_clk),
        .adc_rst_n(adc_rst_n),
    
        .requested(requested),
        .ramp_start(ramp_start),
        .counter(counter),
        .adc_sample_in(adc_sample_in)
    );

endmodule