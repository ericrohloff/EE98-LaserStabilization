
`timescale 1 ns / 1 ps

	module axi_config_registers_v1_0 #
	(
		// Users to add parameters here

		// User parameters ends
		// Do not modify the parameters beyond this line


		// Parameters of Axi Slave Bus Interface S00_AXI
		parameter integer C_S00_AXI_DATA_WIDTH	= 32,
		parameter integer C_S00_AXI_ADDR_WIDTH	= 7
	)
	(
		// Users to add ports here
		output wire [3:0] ref_id,
		output wire ref_exists,
		output wire ref_locked,
        output wire [31:0] ref_pid_p,
        output wire [31:0] ref_pid_i,
        output wire [31:0] ref_pid_d,
        output wire [15:0] ref_set_wavelength,
        input  wire [15:0] ref_detected_wavelength,
		
		output wire [3:0] l1_id,
		output wire l1_exists,
		output wire l1_locked,
        output wire [31:0] l1_pid_p,
        output wire [31:0] l1_pid_i,
        output wire [31:0] l1_pid_d,
        output wire [15:0] l1_set_wavelength,
        input  wire [15:0] l1_detected_wavelength,
		
		
		output wire [3:0] l2_id,
		output wire l2_exists,
		output wire l2_locked,
        output wire [31:0] l2_pid_p,
        output wire [31:0] l2_pid_i,
        output wire [31:0] l2_pid_d,
        output wire [15:0] l2_set_wavelength,
        input  wire [15:0] l2_detected_wavelength,
		
		output wire [3:0] l3_id,
		output wire l3_exists,
		output wire l3_locked,
        output wire [31:0] l3_pid_p,
        output wire [31:0] l3_pid_i,
        output wire [31:0] l3_pid_d,
        output wire [15:0] l3_set_wavelength,
        input  wire [15:0] l3_detected_wavelength,
		
		output wire [3:0] l4_id,
		output wire l4_exists,
		output wire l4_locked,
        output wire [31:0] l4_pid_p,
        output wire [31:0] l4_pid_i,
        output wire [31:0] l4_pid_d,
        output wire [15:0] l4_set_wavelength,
        input  wire [15:0] l4_detected_wavelength,


        ///// Global flags
        output wire system_on,
        output wire system_locked,
		output wire adc_sample_requested,
        
		// User ports ends
		// Do not modify the ports beyond this line


		// Ports of Axi Slave Bus Interface S00_AXI
		input wire  s00_axi_aclk,
		input wire  s00_axi_aresetn,
		input wire [C_S00_AXI_ADDR_WIDTH-1 : 0] s00_axi_awaddr,
		input wire [2 : 0] s00_axi_awprot,
		input wire  s00_axi_awvalid,
		output wire  s00_axi_awready,
		input wire [C_S00_AXI_DATA_WIDTH-1 : 0] s00_axi_wdata,
		input wire [(C_S00_AXI_DATA_WIDTH/8)-1 : 0] s00_axi_wstrb,
		input wire  s00_axi_wvalid,
		output wire  s00_axi_wready,
		output wire [1 : 0] s00_axi_bresp,
		output wire  s00_axi_bvalid,
		input wire  s00_axi_bready,
		input wire [C_S00_AXI_ADDR_WIDTH-1 : 0] s00_axi_araddr,
		input wire [2 : 0] s00_axi_arprot,
		input wire  s00_axi_arvalid,
		output wire  s00_axi_arready,
		output wire [C_S00_AXI_DATA_WIDTH-1 : 0] s00_axi_rdata,
		output wire [1 : 0] s00_axi_rresp,
		output wire  s00_axi_rvalid,
		input wire  s00_axi_rready
	);
// Instantiation of Axi Bus Interface S00_AXI
	axi_config_registers_v1_0_S00_AXI # ( 
		.C_S_AXI_DATA_WIDTH(C_S00_AXI_DATA_WIDTH),
		.C_S_AXI_ADDR_WIDTH(C_S00_AXI_ADDR_WIDTH)
	) axi_config_registers_v1_0_S00_AXI_inst (
		.S_AXI_ACLK(s00_axi_aclk),
		.S_AXI_ARESETN(s00_axi_aresetn),
		.S_AXI_AWADDR(s00_axi_awaddr),
		.S_AXI_AWPROT(s00_axi_awprot),
		.S_AXI_AWVALID(s00_axi_awvalid),
		.S_AXI_AWREADY(s00_axi_awready),
		.S_AXI_WDATA(s00_axi_wdata),
		.S_AXI_WSTRB(s00_axi_wstrb),
		.S_AXI_WVALID(s00_axi_wvalid),
		.S_AXI_WREADY(s00_axi_wready),
		.S_AXI_BRESP(s00_axi_bresp),
		.S_AXI_BVALID(s00_axi_bvalid),
		.S_AXI_BREADY(s00_axi_bready),
		.S_AXI_ARADDR(s00_axi_araddr),
		.S_AXI_ARPROT(s00_axi_arprot),
		.S_AXI_ARVALID(s00_axi_arvalid),
		.S_AXI_ARREADY(s00_axi_arready),
		.S_AXI_RDATA(s00_axi_rdata),
		.S_AXI_RRESP(s00_axi_rresp),
		.S_AXI_RVALID(s00_axi_rvalid),
		.S_AXI_RREADY(s00_axi_rready),
		
		// ===== User ports =====

        // REF
        .ref_id(ref_id),
        .ref_exists(ref_exists),
        .ref_locked(ref_locked),
        .ref_pid_p(ref_pid_p),
        .ref_pid_i(ref_pid_i),
        .ref_pid_d(ref_pid_d),
        .ref_set_wavelength(ref_set_wavelength),
        .ref_detected_wavelength(ref_detected_wavelength),
    
        // L1
        .l1_id(l1_id),
        .l1_exists(l1_exists),
        .l1_locked(l1_locked),
        .l1_pid_p(l1_pid_p),
        .l1_pid_i(l1_pid_i),
        .l1_pid_d(l1_pid_d),
        .l1_set_wavelength(l1_set_wavelength),
        .l1_detected_wavelength(l1_detected_wavelength),
    
        // L2
        .l2_id(l2_id),
        .l2_exists(l2_exists),
        .l2_locked(l2_locked),
        .l2_pid_p(l2_pid_p),
        .l2_pid_i(l2_pid_i),
        .l2_pid_d(l2_pid_d),
        .l2_set_wavelength(l2_set_wavelength),
        .l2_detected_wavelength(l2_detected_wavelength),
    
        // L3
        .l3_id(l3_id),
        .l3_exists(l3_exists),
        .l3_locked(l3_locked),
        .l3_pid_p(l3_pid_p),
        .l3_pid_i(l3_pid_i),
        .l3_pid_d(l3_pid_d),
        .l3_set_wavelength(l3_set_wavelength),
        .l3_detected_wavelength(l3_detected_wavelength),
    
        // L4
        .l4_id(l4_id),
        .l4_exists(l4_exists),
        .l4_locked(l4_locked),
        .l4_pid_p(l4_pid_p),
        .l4_pid_i(l4_pid_i),
        .l4_pid_d(l4_pid_d),
        .l4_set_wavelength(l4_set_wavelength), // (kept your original name)
        .l4_detected_wavelength(l4_detected_wavelength),
    
        // Global
        .system_on(system_on),
        .system_locked(system_locked),
		.adc_sample_requested(adc_sample_requested)
	);

	// Add user logic here

	// User logic ends

	endmodule
