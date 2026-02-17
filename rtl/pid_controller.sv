/*
 * SystemVerilog implementation of a Fixed-Point PID Controller
 *
 * Overview:
 *  Uses fixed-point arithmetic to approximate floating-point precision.
 *  Coefficients (Kp, Ki, Kd) are fixed-point integers scaled by 2^FRAC_BITS.
 *  Example: If FRAC_BITS=16, a Kp of 1.5 is entered as integer 98304 (1.5 * 65536).
 *
 * Parameters:
 *  DATA_WIDTH: Width of the signed sample/setpoint/output (default 16)
 *  FRAC_BITS:  Number of bits used for the fractional part of coefficients (default 16)
 *
 * Inputs:
 *  kp, ki, kd: 32-bit coefficients in fixed-point format (Q16.16 if FRAC_BITS=16)
 */

module pid_controller #(
    parameter DATA_WIDTH = 16,
    parameter FRAC_BITS  = 16
)(
    input  logic                    clk,
    input  logic                    reset,
    input  logic                    valid,
    input  logic signed [DATA_WIDTH-1:0] sample,
    input  logic signed [DATA_WIDTH-1:0] setpoint,
    
    // Coefficients are typically wider to allow fine resolution
    // Range depends on FRAC_BITS. If FRAC_BITS=16, K=1.0 is 65536.
    input  logic signed [31:0]      kp,
    input  logic signed [31:0]      ki,
    input  logic signed [31:0]      kd,
    
    input  logic signed [DATA_WIDTH-1:0] output_min,
    input  logic signed [DATA_WIDTH-1:0] output_max,
    
    output logic signed [DATA_WIDTH-1:0] control_output
);

    // Internal resolution calculation
    // We need enough room for (DATA_WIDTH) * (COEFF_WIDTH)
    localparam ACC_WIDTH = 32 + DATA_WIDTH + 4; // 32-bit coeff + 16-bit data + headroom

    // Internal State
    logic signed [DATA_WIDTH-1:0] prev_error;
    logic signed [ACC_WIDTH-1:0]  integral_acc; // High-res accumulator
    
    // Internal Signals (Combinational)
    logic signed [DATA_WIDTH:0]   error;        // 1 bit wider for subtraction
    logic signed [DATA_WIDTH:0]   err_diff;
    logic signed [ACC_WIDTH-1:0]  p_term;
    logic signed [ACC_WIDTH-1:0]  i_term_inc;
    logic signed [ACC_WIDTH-1:0]  next_integral_acc;
    logic signed [ACC_WIDTH-1:0]  d_term;
    logic signed [ACC_WIDTH-1:0]  output_sum_scaled;
    logic signed [ACC_WIDTH-1:0]  output_sum_final;

    // Error Calculation
    assign error = setpoint - sample;

    always_comb begin
        // defaults
        p_term = '0;
        i_term_inc = '0;
        next_integral_acc = integral_acc;
        d_term = '0;
        output_sum_scaled = '0;
        output_sum_final = '0;
        err_diff = '0;

        if (valid) begin
            // -----------------------------------------------------------
            // 1. Proportional Term
            // Calculation: Kp * Error
            // Result is scaled by 2^FRAC_BITS
            // -----------------------------------------------------------
            p_term = signed'(kp) * signed'(error);

            // -----------------------------------------------------------
            // 2. Integral Term
            // This is the specific part that needs "floating point" like resolution.
            // We accumulate the scaled error.
            // i_acc[n] = i_acc[n-1] + (Ki * error)
            // -----------------------------------------------------------
            i_term_inc = signed'(ki) * signed'(error);
            
            // We do NOT shift down here. We keep the full precision in the accumulator.
            // This allows very small Ki values to eventually affect the output.
            next_integral_acc = integral_acc + i_term_inc;

            // Optional: Clamp internal integrator to prevent severe windup
            // For this simple implementation, we rely on output clamping, 
            // but in robust designs, you might clamp 'next_integral_acc' here.

            // -----------------------------------------------------------
            // 3. Derivative Term
            // -----------------------------------------------------------
            err_diff = error - prev_error;
            d_term = signed'(kd) * signed'(err_diff);

            // -----------------------------------------------------------
            // 4. Summation and Descaling
            // -----------------------------------------------------------
            // Sum all terms. All are currently scaled by 2^FRAC_BITS
            output_sum_scaled = p_term + next_integral_acc + d_term;

            // Rounding: Add 0.5 (which is 1 << (FRAC_BITS-1)) before shifting
            // This provides better accuracy than truncation
            output_sum_final = (output_sum_scaled + (1 << (FRAC_BITS - 1))) >>> FRAC_BITS;
        end
    end

    always_ff @(posedge clk or posedge reset) begin
        if (reset) begin
            prev_error      <= '0;
            integral_acc    <= '0;
            control_output  <= '0;
        end else if (valid) begin
            prev_error   <= error[DATA_WIDTH-1:0];
            integral_acc <= next_integral_acc;

            // -----------------------------------------------------------
            // 5. Output Clamping
            // -----------------------------------------------------------
            if (output_sum_final > output_max) begin
                control_output <= output_max;
            end else if (output_sum_final < output_min) begin
                control_output <= output_min;
            end else begin
                control_output <= output_sum_final[DATA_WIDTH-1:0];
            end
        end
    end

endmodule
