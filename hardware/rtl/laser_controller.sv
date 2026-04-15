module laser_controller (
    input logic clk,
    input logic reset,
    input logic ramp_start,
    input logic peak_valid,

    input logic [3:0] laser_id,
    input logic laser_exists,
    input logic laser_locked,

    input logic [31:0] pid_p,
    input logic [31:0] pid_i,
    input logic [31:0] pid_d,
    input logic [15:0] set_wavelength,
    input logic [15:0] current_wavelength,

    input logic [15:0] ref_wavelength,

    output logic [15:0] feedback
);

localparam int FRAC_BITS = 16;
localparam logic [15:0] MID_SCALE = 16'h8000;

logic signed [31:0] integral_accum;
logic signed [31:0] prev_error;

function automatic signed [31:0] sat32_from64;
    input signed [63:0] value;
    begin
        if (value > 64'sh000000007FFFFFFF)
            sat32_from64 = 32'sh7FFFFFFF;
        else if (value < -64'sh0000000080000000)
            sat32_from64 = -32'sh80000000;
        else
            sat32_from64 = value[31:0];
    end
endfunction

function automatic signed [31:0] sat_add32;
    input signed [31:0] a;
    input signed [31:0] b;
    reg signed [32:0] sum;
    begin
        sum = a + b;
        if (sum > 33'sh07FFFFFFF)
            sat_add32 = 32'sh7FFFFFFF;
        else if (sum < -33'sh080000000)
            sat_add32 = -32'sh80000000;
        else
            sat_add32 = sum[31:0];
    end
endfunction

function automatic signed [15:0] clamp_to_s16;
    input signed [31:0] value;
    begin
        if (value > 32'sd32767)
            clamp_to_s16 = 16'sd32767;
        else if (value < -32'sd32768)
            clamp_to_s16 = -16'sd32768;
        else
            clamp_to_s16 = value[15:0];
    end
endfunction

function automatic [15:0] s16_to_u16;
    input signed [15:0] value;
    reg signed [16:0] shifted;
    begin
        shifted = value + 17'sd32768;
        s16_to_u16 = shifted[15:0];
    end
endfunction

always_ff @(posedge clk or posedge reset) begin
    if (reset) begin
        integral_accum <= 32'sd0;
        prev_error <= 32'sd0;
        feedback <= MID_SCALE;
    end else if (ramp_start) begin
        if (!laser_exists || !laser_locked) begin
            integral_accum <= 32'sd0;
            prev_error <= 32'sd0;
            feedback <= MID_SCALE;
        end else if (peak_valid) begin
            logic signed [16:0] set_minus_ref;
            logic signed [16:0] current_minus_ref;
            logic signed [31:0] error_s32;
            logic signed [31:0] d_error_s32;

            logic signed [63:0] p_product;
            logic signed [63:0] i_product;
            logic signed [63:0] d_product;

            logic signed [31:0] p_term;
            logic signed [31:0] i_term;
            logic signed [31:0] d_term;
            logic signed [31:0] next_integral;
            logic signed [31:0] control_sum;
            logic signed [15:0] control_s16;

            // Reference-aware form; currently equivalent to (set_wavelength - current_wavelength).
            set_minus_ref = $signed({1'b0, set_wavelength}) - $signed({1'b0, ref_wavelength});
            current_minus_ref = $signed({1'b0, current_wavelength}) - $signed({1'b0, ref_wavelength});
            error_s32 = $signed({{15{set_minus_ref[16]}}, set_minus_ref})
                      - $signed({{15{current_minus_ref[16]}}, current_minus_ref});

            d_error_s32 = error_s32 - prev_error;

            p_product = $signed(pid_p) * error_s32;
            i_product = $signed(pid_i) * error_s32;
            d_product = $signed(pid_d) * d_error_s32;

            p_term = sat32_from64(p_product >>> FRAC_BITS);
            i_term = sat32_from64(i_product >>> FRAC_BITS);
            d_term = sat32_from64(d_product >>> FRAC_BITS);

            next_integral = sat_add32(integral_accum, i_term);
            control_sum = sat_add32(sat_add32(p_term, next_integral), d_term);

            control_s16 = clamp_to_s16(control_sum);
            feedback <= s16_to_u16(control_s16);

            integral_accum <= next_integral;
            prev_error <= error_s32;
        end
    end
end

endmodule