`timescale 1ns / 1ps

module spi_controller_tb;

    logic       clk;
    logic       reset;
    logic       tx_start;
    logic [7:0] tx_byte;
    logic       spi_sclk;
    logic       spi_mosi;
    logic       busy;
    logic       done;

    logic [7:0] captured_byte;
    logic [2:0] captured_count;

    spi_controller #(
        .CLKS_PER_HALF_BIT(2)
    ) uut (
        .clk(clk),
        .reset(reset),
        .tx_start(tx_start),
        .tx_byte(tx_byte),
        .spi_sclk(spi_sclk),
        .spi_mosi(spi_mosi),
        .busy(busy),
        .done(done)
    );

    initial begin
        clk = 1'b0;
        forever #5 clk = ~clk;
    end

    always @(posedge spi_sclk or posedge reset) begin
        if (reset) begin
            captured_byte  <= 8'h00;
            captured_count <= 3'd0;
        end else if (busy) begin
            captured_byte  <= {captured_byte[6:0], spi_mosi};
            captured_count <= captured_count + 3'd1;
        end
    end

    task automatic send_and_check(input logic [7:0] value);
        begin
            @(posedge clk);
            while (busy) @(posedge clk);

            tx_byte  <= value;
            tx_start <= 1'b1;
            @(posedge clk);
            tx_start <= 1'b0;

            wait (done);
            @(posedge clk);

            $display("TX=0x%02h RX=0x%02h", value, captured_byte);
            if (captured_byte !== value) begin
                $error("Mismatch: expected 0x%02h got 0x%02h", value, captured_byte);
            end

            captured_byte  <= 8'h00;
            captured_count <= 3'd0;
        end
    endtask

    initial begin
        $dumpfile("spi.ghw");
        $dumpvars(0);
        reset    = 1'b1;
        tx_start = 1'b0;
        tx_byte  = 8'h00;

        #20;
        @(posedge clk);
        reset = 1'b0;

        send_and_check(8'hA5);
        send_and_check(8'h3C);
        send_and_check(8'hF0);
        send_and_check(8'h0F);

        $display("SPI testbench complete.");
        $finish;
    end

endmodule
