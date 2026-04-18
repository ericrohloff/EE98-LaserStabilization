`timescale 1ns / 1ps

module adc_bram_fsm_test (
    // ==========================================
    // AXI BRAM Controller Interface (Port A - Read Domain)
    // ==========================================
    input  logic        bram_clk_a,
    input  logic        bram_rst_a,
    input  logic        bram_en_a,
    input  logic [3:0]  bram_we_a,
    input  logic [14:0] bram_addr_a,
    input  logic [31:0] bram_wrdata_a,
    output logic [31:0] bram_rddata_a,

    // ==========================================
    // Custom ADC Interface (Port B - Write Domain)
    // ==========================================
    input  logic        adc_clk,
    input  logic        adc_rst_n,
    input  logic        requested,
    input  logic        ramp_start,
    input  logic [15:0] counter,
    input  logic [15:0] adc_sample_in
);

    // Minimal stub implementation:
    // only respond to reads at address 0x0 with 0xDEADBEEF.
    always_ff @(posedge bram_clk_a or posedge bram_rst_a) begin
        if (bram_rst_a) begin
            bram_rddata_a <= 32'h0000_0000;
        end else if (bram_en_a) begin
            if (bram_addr_a == 15'h0000) begin
                bram_rddata_a <= 32'hDEAD_BEEF;
            end else begin
                bram_rddata_a <= 32'h0000_0000;
            end
        end
    end

endmodule
