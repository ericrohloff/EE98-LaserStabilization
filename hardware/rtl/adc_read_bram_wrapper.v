

module adc_bram_wrapper (
    // ==========================================
    // AXI BRAM Controller Interface (Port A - Read Domain)
    // ==========================================
    input  wire        bram_clk_a,
    input  wire        bram_rst_a,
    input  wire        bram_en_a,
    input  wire [3:0]  bram_we_a,        // Typically 0 for our use case, but included for completeness
    input  wire [15:0] bram_addr_a,      // 15-bit byte address (up to 32KB)
    input  wire [31:0] bram_wrdata_a,
    output wire [31:0] bram_rddata_a,

    // ==========================================
    // Custom ADC Interface (Port B - Write Domain)
    // ==========================================
    input  wire        adc_clk,
    input  wire        adc_rst_n,        // Active low reset for the ADC domain

    // Control signals
    input  wire        requested,        // Assumed to come from a different domain (needs sync)
    input  wire        ramp_start,
    input  wire [15:0] adc_sample_in,    // 16-bit data
    input  wire        adc_sample_valid,
    output wire        record_done
);

    adc_bram_fsm u_bram (
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
        .adc_sample_in(adc_sample_in),
        .adc_sample_valid(adc_sample_valid),
        .record_done(record_done)
    );

endmodule