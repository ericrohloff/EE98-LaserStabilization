`timescale 1ns / 1ps

module peak_detection_tb;

    logic clk;
    logic reset;
    logic [15:0] adc_sample;
    logic adc_sample_valid;
    logic [15:0] current_ramp_pos;
    logic ramp_start;
    logic [15:0] ref_target;
    logic [15:0] l1_target;
    logic [15:0] l2_target;
    logic [15:0] l3_target;
    logic [15:0] l4_target;

    logic [15:0] l1_position;
    logic [15:0] l2_position;
    logic [15:0] l3_position;
    logic [15:0] l4_position;

    integer stim_fd;
    integer log_fd;
    integer rc;
    integer cycle_idx;
    integer stim_cycle;
    integer stim_adc;
    integer stim_valid;
    integer stim_pos;
    integer stim_ramp_start;
    integer stim_ref;
    integer stim_l1;
    integer stim_l2;
    integer stim_l3;
    integer stim_l4;
    integer scan_idx;
    string header_line;

    peak_detection #(
        .THRESHOLD(16'd2000),
        .ASSIGN_WINDOW(16'd1500),
        .MAX_CANDIDATES(8)
    ) dut (
        .clk(clk),
        .reset(reset),
        .adc_sample(adc_sample),
        .adc_sample_valid(adc_sample_valid),
        .current_ramp_pos(current_ramp_pos),
        .ramp_start(ramp_start),
        .ref_target(ref_target),
        .l1_target(l1_target),
        .l2_target(l2_target),
        .l3_target(l3_target),
        .l4_target(l4_target),
        .l1_position(l1_position),
        .l2_position(l2_position),
        .l3_position(l3_position),
        .l4_position(l4_position)
    );

    initial begin
        clk = 1'b0;
        forever #5 clk = ~clk;
    end

    initial begin
        reset = 1'b1;
        adc_sample = 16'd0;
        adc_sample_valid = 1'b0;
        current_ramp_pos = 16'd0;
        ramp_start = 1'b0;
        ref_target = 16'd32000;
        l1_target = 16'd12000;
        l2_target = 16'd24000;
        l3_target = 16'd40000;
        l4_target = 16'd52000;
        scan_idx = -1;

        repeat (4) @(posedge clk);
        reset = 1'b0;

        stim_fd = $fopen("vectors/peak_stimulus.csv", "r");
        if (stim_fd == 0) begin
            $error("Failed to open vectors/peak_stimulus.csv");
            $finish;
        end

        log_fd = $fopen("vectors/peak_dut_outputs.csv", "w");
        if (log_fd == 0) begin
            $error("Failed to open vectors/peak_dut_outputs.csv");
            $finish;
        end

        // Header for output comparison.
        $fwrite(log_fd, "scan_idx,l1_position,l2_position,l3_position,l4_position\n");

        // Skip the stimulus header line.
        rc = $fgets(header_line, stim_fd);

        cycle_idx = 0;
        while (!$feof(stim_fd)) begin
            rc = $fscanf(
                stim_fd,
                "%d,%d,%d,%d,%d,%d,%d,%d,%d,%d\n",
                stim_cycle,
                stim_adc,
                stim_valid,
                stim_pos,
                stim_ramp_start,
                stim_ref,
                stim_l1,
                stim_l2,
                stim_l3,
                stim_l4
            );

            if (rc != 10)
                break;

            @(negedge clk);
            adc_sample       = stim_adc[15:0];
            adc_sample_valid = stim_valid[0];
            current_ramp_pos = stim_pos[15:0];
            ramp_start       = stim_ramp_start[0];
            ref_target       = stim_ref[15:0];
            l1_target        = stim_l1[15:0];
            l2_target        = stim_l2[15:0];
            l3_target        = stim_l3[15:0];
            l4_target        = stim_l4[15:0];

            @(posedge clk);
            cycle_idx = cycle_idx + 1;

            if (ramp_start) begin
                #1;
                scan_idx = scan_idx + 1;
                $fwrite(
                    log_fd,
                    "%0d,%0d,%0d,%0d,%0d\n",
                    scan_idx,
                    l1_position,
                    l2_position,
                    l3_position,
                    l4_position
                );
            end
        end

        $fclose(stim_fd);
        $fclose(log_fd);

        $display("Peak detection TB completed after %0d cycles", cycle_idx);
        $finish;
    end

endmodule
