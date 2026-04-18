`timescale 1ns / 1ps

module adc_read_bram_tb;

    // AXI BRAM Controller Interface (Port A)
    logic        bram_clk_a;
    logic        bram_rst_a;
    logic        bram_en_a;
    logic [3:0]  bram_we_a;
    logic [15:0] bram_addr_a;
    logic [31:0] bram_wrdata_a;
    logic [31:0] bram_rddata_a;

    // ADC interface (Port B)
    logic        adc_clk;
    logic        adc_rst_n;
    logic        requested;
    logic        ramp_start;
    logic [15:0] counter;
    logic [15:0] adc_sample_in;
    logic        adc_sample_valid;
    logic        record_done;

    // DUT
    adc_bram_fsm dut (
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
        .adc_sample_in(adc_sample_in),
        .adc_sample_valid(adc_sample_valid),
        .record_done(record_done)
    );

    // 100 MHz clocks in each domain
    initial begin
        adc_clk = 1'b0;
        forever #5 adc_clk = ~adc_clk;
    end

    initial begin
        bram_clk_a = 1'b0;
        forever #5 bram_clk_a = ~bram_clk_a;
    end

    task automatic read_word(
        input  logic [11:0] word_addr,
        output logic [31:0] data
    );
        begin
            @(negedge bram_clk_a);
            bram_addr_a <= {2'b00, word_addr, 2'b00};
            bram_en_a   <= 1'b1;
            bram_we_a   <= 4'b0000;
            @(posedge bram_clk_a);
            #1 data = bram_rddata_a;
            @(negedge bram_clk_a);
            bram_en_a <= 1'b0;
        end
    endtask

    logic [31:0] r0;
    logic [31:0] r1;
    logic [31:0] r2;
    logic [31:0] r3;
    logic [31:0] r_restart;

    task automatic pulse_sample_valid(
        input logic [15:0] sample
    );
        begin
            @(negedge adc_clk);
            adc_sample_in    <= sample;
            adc_sample_valid <= 1'b1;
            @(posedge adc_clk);
            @(negedge adc_clk);
            adc_sample_valid <= 1'b0;
        end
    endtask

    initial begin
        $dumpfile("adc_read_bram_tb.vcd");
        $dumpvars(0, adc_read_bram_tb);

        // Defaults
        bram_rst_a    = 1'b1;
        bram_en_a     = 1'b0;
        bram_we_a     = 4'b0000;
        bram_addr_a   = '0;
        bram_wrdata_a = '0;

        adc_rst_n     = 1'b0;
        requested     = 1'b0;
        ramp_start    = 1'b0;
        counter       = 16'd10;
        adc_sample_in = 16'h0000;
        adc_sample_valid = 1'b0;

        // Release resets
        repeat (4) @(posedge adc_clk);
        adc_rst_n  = 1'b1;
        bram_rst_a = 1'b0;

        // 1) Raise requested so FSM moves IDLE -> WAIT_RAMP
        @(negedge adc_clk);
        requested = 1'b1;
        repeat (5) @(posedge adc_clk);
        requested = 1'b0;

        // 2) Assert ramp_start high to start recording (level-sensitive start)
        repeat (2) @(posedge adc_clk);
        @(negedge adc_clk);
        ramp_start = 1'b1;
        @(posedge adc_clk);
        @(negedge adc_clk);
        ramp_start = 1'b0;

        // 3) Feed samples: one write per adc_sample_valid rising edge
        pulse_sample_valid(16'h0011);
        pulse_sample_valid(16'h0022);
        pulse_sample_valid(16'h0033);
        pulse_sample_valid(16'h0044);

        // 4) Next ramp_start event ends recording and raises record_done
        @(negedge adc_clk);
        ramp_start = 1'b1;
        @(posedge adc_clk);
        @(negedge adc_clk);
        ramp_start = 1'b0;
        repeat (2) @(posedge adc_clk);

        if (record_done !== 1'b1) $error("record_done should be high after recording completes");

        // 5) First BRAM read moves WAIT_READ -> READ_MODE and clears record_done
        read_word(12'd0, r0);
        repeat (8) @(posedge adc_clk);
        if (record_done !== 1'b0) $error("record_done should clear after first BRAM read");

        // Continue BRAM reads
        read_word(12'd1, r1);
        read_word(12'd2, r2);
        read_word(12'd3, r3);

        $display("Readback: [0]=0x%08h [1]=0x%08h [2]=0x%08h [3]=0x%08h", r0, r1, r2, r3);

        if (r0 !== 32'h0000_0011) $error("Word 0 mismatch");
        if (r1 !== 32'h0000_0022) $error("Word 1 mismatch");
        if (r2 !== 32'h0000_0033) $error("Word 2 mismatch");
        if (r3 !== 32'h0000_0044) $error("Word 3 mismatch");

        // 6) New request should restart flow and overwrite from address 0
        @(negedge adc_clk);
        requested = 1'b1;
        repeat (3) @(posedge adc_clk);
        requested = 1'b0;

        @(negedge adc_clk);
        ramp_start = 1'b1;
        @(posedge adc_clk);
        @(negedge adc_clk);
        ramp_start = 1'b0;

        pulse_sample_valid(16'h00AA);

        @(negedge adc_clk);
        ramp_start = 1'b1;
        @(posedge adc_clk);
        @(negedge adc_clk);
        ramp_start = 1'b0;

        if (record_done !== 1'b1) $error("record_done should be high for second capture completion");
        read_word(12'd0, r_restart);
        repeat (8) @(posedge adc_clk);
        if (record_done !== 1'b0) $error("record_done should clear after first read of second capture");
        if (r_restart !== 32'h0000_00AA) $error("Restart capture word 0 mismatch");

        repeat (5) @(posedge adc_clk);
        $finish;
    end

endmodule
