`timescale 1ns / 1ps

module feedback_dac_driver_tb;

    logic clk;
    logic reset;
    logic enable;
    logic update_trigger;

    logic [15:0] l1_feedback_value;
    logic        l1_feedback_enable;
    logic [15:0] l2_feedback_value;
    logic        l2_feedback_enable;
    logic [15:0] l3_feedback_value;
    logic        l3_feedback_enable;
    logic [15:0] l4_feedback_value;
    logic        l4_feedback_enable;

    logic dac_cs;
    logic dac_mosi;
    logic dac_sck;

    integer frame_start_count;
    integer frame_index;
    time    last_sck_rise_time;
    integer scheduled_trigger_delay;
    logic   scheduled_trigger_pending;
    logic   scheduled_trigger_drive;

    feedback_dac_driver uut (
        .clk(clk),
        .enable(enable),
        .reset(reset),
        .update_trigger(update_trigger),
        .l1_feedback_value(l1_feedback_value),
        .l1_feedback_enable(l1_feedback_enable),
        .l2_feedback_value(l2_feedback_value),
        .l2_feedback_enable(l2_feedback_enable),
        .l3_feedback_value(l3_feedback_value),
        .l3_feedback_enable(l3_feedback_enable),
        .l4_feedback_value(l4_feedback_value),
        .l4_feedback_enable(l4_feedback_enable),
        .dac_cs(dac_cs),
        .dac_mosi(dac_mosi),
        .dac_sck(dac_sck)
    );

    initial begin
        clk = 1'b0;
        forever #5 clk = ~clk;
    end

    function automatic [7:0] make_addr_byte(input logic [1:0] channel);
        make_addr_byte = {2'b00, 2'b01, 1'b0, channel, 1'b0};
    endfunction

    function automatic [23:0] make_frame(input logic [1:0] channel, input logic [15:0] data_word);
        make_frame = {make_addr_byte(channel), data_word};
    endfunction

    task automatic pulse_trigger();
        begin
            @(negedge clk);
            update_trigger = 1'b1;
            @(negedge clk);
            update_trigger = 1'b0;
        end
    endtask

    task automatic schedule_overlap_trigger(input int cycles);
        begin
            scheduled_trigger_delay  = cycles;
            scheduled_trigger_pending = 1'b1;
            scheduled_trigger_drive   = 1'b0;
        end
    endtask

    always @(posedge clk) begin
        if (scheduled_trigger_pending) begin
            if (scheduled_trigger_delay == 0) begin
                update_trigger <= 1'b1;
                scheduled_trigger_pending <= 1'b0;
                scheduled_trigger_drive <= 1'b1;
            end else begin
                scheduled_trigger_delay <= scheduled_trigger_delay - 1;
            end
        end else if (scheduled_trigger_drive) begin
            update_trigger <= 1'b0;
            scheduled_trigger_drive <= 1'b0;
        end
    end

    task automatic capture_and_check_frame(
        input [23:0] expected_frame,
        input int frame_number
    );
        logic [23:0] captured_frame;
        time previous_fall_time;
        time delta_time;
        begin
            captured_frame   = 24'd0;
            previous_fall_time = 0;

            repeat (24) begin
                @(negedge dac_sck);

                if (dac_cs !== 1'b0) begin
                    $error("Frame %0d: dac_cs should be low while shifting", frame_number);
                end

                if (previous_fall_time != 0) begin
                    delta_time = $time - previous_fall_time;
                    if (delta_time != 100) begin
                        $error("Frame %0d: SCK period should be 100 ns, got %0t ns", frame_number, delta_time);
                    end
                end

                previous_fall_time = $time;
                captured_frame = {captured_frame[22:0], dac_mosi};
            end

            if (captured_frame !== expected_frame) begin
                $error("Frame %0d mismatch: expected 0x%06h got 0x%06h", frame_number, expected_frame, captured_frame);
            end else begin
                $display("Frame %0d OK: 0x%06h", frame_number, captured_frame);
            end
        end
    endtask

    task automatic run_scenario(
        input logic [15:0] v1,
        input logic        e1,
        input logic [15:0] v2,
        input logic        e2,
        input logic [15:0] v3,
        input logic        e3,
        input logic [15:0] v4,
        input logic        e4,
        input int expected_frames,
        input bit trigger_again_while_busy
    );
        int local_frame_count;
        begin
            l1_feedback_value  = v1;
            l1_feedback_enable = e1;
            l2_feedback_value  = v2;
            l2_feedback_enable = e2;
            l3_feedback_value  = v3;
            l3_feedback_enable = e3;
            l4_feedback_value  = v4;
            l4_feedback_enable = e4;

            frame_start_count = 0;
            local_frame_count = 0;

            pulse_trigger();

            if (trigger_again_while_busy) begin
                schedule_overlap_trigger(20);
            end

            while (local_frame_count < expected_frames) begin
                @(negedge dac_cs);
                frame_start_count = frame_start_count + 1;

                if (local_frame_count == 0 && e1) begin
                    capture_and_check_frame(make_frame(2'b00, v1), local_frame_count + 1);
                end else if ((local_frame_count == (e1 ? 1 : 0)) && e2) begin
                    capture_and_check_frame(make_frame(2'b01, v2), local_frame_count + 1);
                end else if ((local_frame_count == ((e1 ? 1 : 0) + (e2 ? 1 : 0))) && e3) begin
                    capture_and_check_frame(make_frame(2'b10, v3), local_frame_count + 1);
                end else if ((local_frame_count == ((e1 ? 1 : 0) + (e2 ? 1 : 0) + (e3 ? 1 : 0))) && e4) begin
                    capture_and_check_frame(make_frame(2'b11, v4), local_frame_count + 1);
                end else begin
                    $error("Unexpected frame ordering or enabled-channel mismatch at frame %0d", local_frame_count + 1);
                end

                local_frame_count = local_frame_count + 1;
            end

            repeat (200) @(posedge clk);
            if (frame_start_count !== expected_frames) begin
                $error("Expected %0d frames, observed %0d frames", expected_frames, frame_start_count);
            end
            if (dac_cs !== 1'b1) begin
                $error("dac_cs should be high when the driver is idle");
            end
            if (dac_sck !== 1'b0) begin
                $error("dac_sck should be low when the driver is idle");
            end
        end
    endtask

    initial begin
        $dumpfile("feedback_dac_driver_tb.vcd");
        $dumpvars(0, feedback_dac_driver_tb);

        reset             = 1'b1;
        enable            = 1'b0;
        update_trigger    = 1'b0;
        l1_feedback_value = 16'h0000;
        l2_feedback_value = 16'h0000;
        l3_feedback_value = 16'h0000;
        l4_feedback_value = 16'h0000;
        l1_feedback_enable = 1'b0;
        l2_feedback_enable = 1'b0;
        l3_feedback_enable = 1'b0;
        l4_feedback_enable = 1'b0;

        #20;
        @(posedge clk);
        reset = 1'b0;
        enable = 1'b1;

        run_scenario(
            16'hFFFF, 1'b1,
            16'hFFFF, 1'b1,
            16'hFFFF, 1'b1,
            16'hFFFF, 1'b1,
            4,
            1'b0
        );

        run_scenario(
            16'h00A5, 1'b0,
            16'h1357, 1'b1,
            16'h2468, 1'b0,
            16'hBEEF, 1'b1,
            2,
            1'b1
        );

        $display("feedback_dac_driver_tb complete.");
        $finish;
    end

endmodule