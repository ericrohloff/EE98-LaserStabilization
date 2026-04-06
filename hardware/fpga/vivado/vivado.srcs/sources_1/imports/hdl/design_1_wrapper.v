//Copyright 1986-2022 Xilinx, Inc. All Rights Reserved.
//--------------------------------------------------------------------------------
//Tool Version: Vivado v.2022.1 (lin64) Build 3526262 Mon Apr 18 15:47:01 MDT 2022
//Date        : Thu Mar 12 13:30:34 2026
//Host        : dell52 running 64-bit Red Hat Enterprise Linux release 8.10 (Ootpa)
//Command     : generate_target design_1_wrapper.bd
//Design      : design_1_wrapper
//Purpose     : IP block netlist
//--------------------------------------------------------------------------------
`timescale 1 ps / 1 ps

module design_1_wrapper
   (clk_100mhz_clk_n,
    clk_100mhz_clk_p,
    clk_output,
    led_8bits_tri_o);
  input clk_100mhz_clk_n;
  input clk_100mhz_clk_p;
  output clk_output;
  output [7:0]led_8bits_tri_o;

  wire clk_100mhz_clk_n;
  wire clk_100mhz_clk_p;
  wire clk_output;
  wire [7:0]led_8bits_tri_o;

  design_1 design_1_i
       (.clk_100mhz_clk_n(clk_100mhz_clk_n),
        .clk_100mhz_clk_p(clk_100mhz_clk_p),
        .clk_output(clk_output),
        .led_8bits_tri_o(led_8bits_tri_o));
endmodule
