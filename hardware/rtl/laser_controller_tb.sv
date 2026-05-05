`timescale 1ns / 1ps

module laser_controller_tb;

    logic clk;
    logic reset;
    logic ramp_start;
    logic peak_valid;

    logic [3:0] laser_id;
    logic laser_exists;
    logic laser_locked;

    logic [31:0] pid_p;
    logic [31:0] pid_i;
    logic [31:0] pid_d;
    logic [15:0] set_wavelength;
    logic [15:0] current_wavelength;
    logic [15:0] ref_wavelength;

    logic [15:0] feedback;

    integer stim_fd;
    integer out_fd;
    integer rc;

    integer step_idx;
    integer stim_ramp_start;
    integer stim_peak_valid;
    integer stim_exists;
    integer stim_locked;
    integer stim_set;
    integer stim_current;
    integer stim_ref;
    integer stim_p;
    integer stim_i;
    integer stim_d;

    integer applied_steps;
    string header_line;

    laser_controller dut (
        .clk(clk),
        .reset(reset),
        .ramp_start(ramp_start),
        .peak_valid(peak_valid),
        .laser_id(laser_id),
        .laser_exists(laser_exists),
        .laser_locked(laser_locked),
        .pid_p(pid_p),
        .pid_i(pid_i),
        .pid_d(pid_d),
        .set_wavelength(set_wavelength),
        .current_wavelength(current_wavelength),
        .ref_wavelength(ref_wavelength),
        .feedback(feedback)
    );

    initial begin
        clk = 1'b0;
        forever #5 clk = ~clk;
    end

    initial begin
        reset = 1'b1;
        ramp_start = 1'b0;
        peak_valid = 1'b0;
        laser_id = 4'd1;
        laser_exists = 1'b1;
        laser_locked = 1'b1;
        pid_p = 32'd0;
        pid_i = 32'd0;
        pid_d = 32'd0;
        set_wavelength = 16'd0;
        current_wavelength = 16'd0;
        ref_wavelength = 16'd0;

        repeat (4) @(posedge clk);
        reset = 1'b0;

        stim_fd = $fopen("vectors/pid_stimulus.csv", "r");
        if (stim_fd == 0) begin
            $error("Failed to open vectors/pid_stimulus.csv");
            $finish;
        end

        out_fd = $fopen("vectors/pid_dut_outputs.csv", "w");
        if (out_fd == 0) begin
            $error("Failed to open vectors/pid_dut_outputs.csv");
            $finish;
        end

        $fwrite(out_fd, "step_idx,feedback_u16\n");

        rc = $fgets(header_line, stim_fd);
        applied_steps = 0;

        while (!$feof(stim_fd)) begin
            rc = $fscanf(
                stim_fd,
                "%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d\n",
                step_idx,
                stim_ramp_start,
                stim_peak_valid,
                stim_exists,
                stim_locked,
                stim_set,
                stim_current,
                stim_ref,
                stim_p,
                stim_i,
                stim_d
            );

            if (rc != 11)
                break;

            @(negedge clk);
            ramp_start = stim_ramp_start[0];
            peak_valid = stim_peak_valid[0];
            laser_exists = stim_exists[0];
            laser_locked = stim_locked[0];
            set_wavelength = stim_set[15:0];
            current_wavelength = stim_current[15:0];
            ref_wavelength = stim_ref[15:0];
            pid_p = stim_p;
            pid_i = stim_i;
            pid_d = stim_d;

            @(posedge clk);
            #1;

            $fwrite(out_fd, "%0d,%0d\n", step_idx, feedback);
            applied_steps = applied_steps + 1;
        end

        $fclose(stim_fd);
        $fclose(out_fd);

        $display("laser_controller_tb completed %0d steps", applied_steps);
        $finish;
    end

endmodule
