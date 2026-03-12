`timescale 1ns / 1ps
//////////////////////////////////////////////////////////////////////////////////
// Company: 
// Engineer: 
// 
// Create Date: 03/10/2026 01:21:31 PM
// Design Name: 
// Module Name: clockdiv_wrap
// Project Name: 
// Target Devices: 
// Tool Versions: 
// Description: 
// 
// Dependencies: 
// 
// Revision:
// Revision 0.01 - File Created
// Additional Comments:
// 
//////////////////////////////////////////////////////////////////////////////////


module clockdiv_wrap(
    input logic_clk_in,
    input rst_n,
    output logic_clk_out
    );
    
clk20_gen u(.logic_clk_in(logic_clk_in), .rst_n(rst_n), .logic_clk_out(logic_clk_out));
endmodule
