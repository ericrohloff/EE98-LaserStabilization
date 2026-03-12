module clk20_gen (
    input logic_clk_in,
    input rst_n,
    output logic logic_clk_out
);

    logic [2:0] counter;

    always_ff @(posedge logic_clk_in or negedge rst_n) begin
        if (!rst_n) begin
            counter <= 0;
            logic_clk_out <= 0;
        end
        else begin
            if (counter == 2) begin
                counter <= 0;
                logic_clk_out <= ~logic_clk_out;
            end
            else begin
                counter <= counter + 1;
            end
        end
    end

endmodule
