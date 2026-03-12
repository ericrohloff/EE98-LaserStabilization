`timescale 1ns / 1ps

module ramp_dac_bringup (
    input  logic        clk,
    input  logic        reset,
    input  logic        enable,
    input  logic [15:0] ramp_step,
    input  logic [15:0] ramp_min,
    input  logic [15:0] ramp_max,
    input  logic        triangle_mode,
    output logic        ramp_dac_cs_n,
    output logic        ramp_dac_sck,
    output logic        ramp_dac_mosi,
    input  logic        adc_miso,
    output logic        adc_cnv,
    output logic        adc_sck,
    output logic [15:0] adc_sample_unsigned,
    output logic        adc_sample_valid,
    output logic [6:0]  frame_tick,
    output logic        frame_start,
    output logic        frame_boundary,
    output logic        ramp_cycle_start,
    output logic [15:0] current_ramp_pos
);

    logic phase_0_31;
    logic phase_32_49;
    logic phase_50_81;
    logic phase_82_98;

    global_timing_sequencer gts (
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

    ramp_dac_spi ramp_spi (
        .clk(clk),
        .reset(reset),
        .enable(enable),
        .frame_tick(frame_tick),
        .ramp_step(ramp_step),
        .ramp_min(ramp_min),
        .ramp_max(ramp_max),
        .triangle_mode(triangle_mode),
        .ramp_dac_cs_n(ramp_dac_cs_n),
        .ramp_dac_sck(ramp_dac_sck),
        .ramp_dac_mosi(ramp_dac_mosi),
        .current_ramp_pos(current_ramp_pos),
        .ramp_cycle_start(ramp_cycle_start)
    );

    adc_frontend adc (
        .clk(clk),
        .reset(reset),
        .enable(enable),
        .frame_tick(frame_tick),
        .adc_miso(adc_miso),
        .adc_cnv(adc_cnv),
        .adc_sck(adc_sck),
        .adc_sample_unsigned(adc_sample_unsigned),
        .adc_sample_valid(adc_sample_valid)
    );

endmodule


module ramp_dac_bringup_tb;

    logic clk;
    logic reset;
    logic enable;
    logic [15:0] ramp_step;
    logic [15:0] ramp_min;
    logic [15:0] ramp_max;
    logic triangle_mode;

    logic       ramp_dac_cs_n;
    logic       ramp_dac_sck;
    logic       ramp_dac_mosi;
    logic       adc_miso;
    logic       adc_cnv;
    logic       adc_sck;
    logic [15:0] adc_sample_unsigned;
    logic       adc_sample_valid;
    logic [6:0] frame_tick;
    logic       frame_start;
    logic       frame_boundary;
    logic       ramp_cycle_start;
    logic [15:0] current_ramp_pos;

    logic [15:0] shifted_word;
    logic [15:0] captured_word;
    integer      bit_count;
    integer      frame_count;
    logic [15:0] expected_tx_word;
    logic        checks_active;

    logic [15:0] adc_shift_word;
    logic [15:0] adc_expected_offset_word;
    logic [15:0] adc_expected_unsigned_word;
    logic [15:0] adc_next_offset_word;
    integer      adc_sample_count;

    localparam int FRAMES_TO_CHECK = 12;

    assign adc_next_offset_word = adc_expected_offset_word + 16'h0111;

    ramp_dac_bringup uut (
        .clk(clk),
        .reset(reset),
        .enable(enable),
        .ramp_step(ramp_step),
        .ramp_min(ramp_min),
        .ramp_max(ramp_max),
        .triangle_mode(triangle_mode),
        .ramp_dac_cs_n(ramp_dac_cs_n),
        .ramp_dac_sck(ramp_dac_sck),
        .ramp_dac_mosi(ramp_dac_mosi),
        .adc_miso(adc_miso),
        .adc_cnv(adc_cnv),
        .adc_sck(adc_sck),
        .adc_sample_unsigned(adc_sample_unsigned),
        .adc_sample_valid(adc_sample_valid),
        .frame_tick(frame_tick),
        .frame_start(frame_start),
        .frame_boundary(frame_boundary),
        .ramp_cycle_start(ramp_cycle_start),
        .current_ramp_pos(current_ramp_pos)
    );

    initial begin
        clk = 1'b0;
        forever #5 clk = ~clk;
    end

    assign captured_word = {shifted_word[14:0], ramp_dac_mosi};

    always @(posedge clk) begin
        if (!reset && enable && frame_start) begin
            checks_active <= 1'b1;
            expected_tx_word <= current_ramp_pos;
        end

        if (!reset && checks_active && (frame_tick == 7'd50)) begin
            adc_shift_word <= adc_expected_offset_word;
            adc_miso <= adc_expected_offset_word[15];
        end

        if (!reset && checks_active) begin
            if (frame_tick <= 7'd49) begin
                if (ramp_dac_cs_n !== 1'b0) begin
                    $error("CS should be low in ticks 0..49, tick=%0d", frame_tick);
                end
            end else begin
                if (ramp_dac_cs_n !== 1'b1) begin
                    $error("CS should be high in ticks 50..99, tick=%0d", frame_tick);
                end
            end

            if (frame_tick <= 7'd31) begin
                if (ramp_dac_sck !== frame_tick[0]) begin
                    $error("SCK mismatch in shift window at tick=%0d", frame_tick);
                end
            end else begin
                if (ramp_dac_sck !== 1'b0) begin
                    $error("SCK should be idle low outside shift window, tick=%0d", frame_tick);
                end
            end

            if (frame_tick <= 7'd49) begin
                if (adc_cnv !== 1'b1) begin
                    $error("ADC CNV should be high in ticks 0..49, tick=%0d", frame_tick);
                end
            end else begin
                if (adc_cnv !== 1'b0) begin
                    $error("ADC CNV should be low in ticks 50..99, tick=%0d", frame_tick);
                end
            end

            if ((frame_tick >= 7'd50) && (frame_tick <= 7'd81)) begin
                if (adc_sck !== frame_tick[0]) begin
                    $error("ADC SCK mismatch in shift window at tick=%0d", frame_tick);
                end
            end else begin
                if (adc_sck !== 1'b0) begin
                    $error("ADC SCK should be idle low outside shift window, tick=%0d", frame_tick);
                end
            end

            if (adc_sample_valid) begin
                if (frame_tick != 7'd0) begin
                    $error("adc_sample_valid asserted at non-0 tick (%0d)", frame_tick);
                end
                if (adc_sample_unsigned !== adc_expected_unsigned_word) begin
                    $error("ADC sample mismatch at sample %0d: expected 0x%04h got 0x%04h",
                           adc_sample_count, adc_expected_unsigned_word, adc_sample_unsigned);
                end
                adc_sample_count <= adc_sample_count + 1;
                adc_expected_offset_word <= adc_next_offset_word;
                adc_expected_unsigned_word <= adc_next_offset_word;
            end
        end
    end

    always @(negedge adc_sck or posedge reset) begin
        if (reset) begin
            adc_shift_word <= 16'h0000;
            adc_miso <= 1'b0;
        end else if (checks_active && (frame_tick >= 7'd52) && (frame_tick <= 7'd80)) begin
            adc_shift_word <= {adc_shift_word[14:0], 1'b0};
            adc_miso <= adc_shift_word[14];
        end
    end

    always @(posedge ramp_dac_sck or posedge reset) begin
        if (reset) begin
            shifted_word <= 16'h0000;
            bit_count    <= 0;
        end else if (checks_active && !ramp_dac_cs_n) begin
            shifted_word <= {shifted_word[14:0], ramp_dac_mosi};
            bit_count    <= bit_count + 1;

            if (bit_count == 15) begin
                if (captured_word !== expected_tx_word) begin
                    $error("SPI frame mismatch at frame %0d: expected 0x%04h got 0x%04h",
                           frame_count, expected_tx_word, captured_word);
                end

                frame_count <= frame_count + 1;

                bit_count <= 0;
            end
        end else begin
            bit_count <= 0;
        end
    end

    always @(posedge clk) begin
        if (!reset && checks_active) begin
            if (frame_boundary && (frame_tick != 7'd99)) begin
                $error("frame_boundary asserted at non-99 tick (%0d)", frame_tick);
            end

            if (frame_start && (frame_tick != 7'd0)) begin
                $error("frame_start asserted at non-0 tick (%0d)", frame_tick);
            end
        end
    end

    initial begin
        $dumpfile("ramp_dac_bringup.ghw");
        $dumpvars(0);

        reset         = 1'b1;
        enable        = 1'b0;
        triangle_mode = 1'b0;
        ramp_step     = 16'd3;
        ramp_min      = 16'd10;
        ramp_max      = 16'd22;
        adc_miso      = 1'b0;
        shifted_word  = 16'h0000;
        adc_shift_word = 16'h0000;
        bit_count     = 0;
        frame_count   = 0;
        expected_tx_word = 16'd0;
        checks_active = 1'b0;
        adc_expected_offset_word = 16'h8001;
        adc_expected_unsigned_word = 16'h8001;
        adc_sample_count = 0;

        #20;
        @(posedge clk);
        reset  = 1'b0;
        enable = 1'b1;

        wait ((frame_count >= FRAMES_TO_CHECK) && (adc_sample_count >= FRAMES_TO_CHECK));
        repeat (5) @(posedge clk);

        $display("Ramp DAC + ADC bring-up test complete: verified %0d ramp frames, %0d ADC samples", frame_count, adc_sample_count);
        $finish;
    end

    initial begin
        #200000;
        $error("Timeout waiting for ramp bring-up verification");
        $finish;
    end

endmodule
