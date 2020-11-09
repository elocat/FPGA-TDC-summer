import re
import os

# port to change all the input ports to. Can easily be changed to a dictionary if different ports desired later
new_port = "F"

#Number of RO and number of logic elements per RO
nRO = 200
nstages = 9

#File names
rcf_file = 'ROarray_v3.rcf'
tcl_file = 'tcl_script.tcl'

#Dictionary to hold inital states. Key is RO number, item is a dictionary with inverter numbers as keys, and values are the input port used
port_dict = {}

#Specify lut_masks for each input port (the LUT mask used depends on the input port used). Will vary for different logical functions, so will have to change
# if a different logic element is used. Dictionary key is the input port, item is a list with the f0, f1, f2, and f3 LUT masks resp.

#the f0 and f2 LUT masks are used for the top section of the combination cell, f1 and f3 are used for bottom. For lcells with two inverters, the top inverter will
#only utilize the f0 and f2 masks; however, quartus still has a property for all 4 LUT masks for that inverter mode, but just makes the f1 LUT mask the same as the f0 mask, 
# and the f3 mask same as the f2 mask. Similar situation if the inverter is in the bottom of the lcell, but in this case the f1 and f3 are LUT masks acutally used.

lut_dict_reg = {
"A": ["AAAA", "AAAA", "AAAA", "AAAA"],
"C": ["F0F0", "F0F0", "F0F0", "F0F0"],
"D": ["FF00", "FF00", "FF00", "FF00"],
"E": ["0000", "0000", "FFFF", "FFFF"],
"F": ["0000", "0000", "FFFF", "FFFF"],
}

#LCELL acts differently if at end of oscillator, all 4 LUT masks are used for the single inverter, so the situation is different, and we have different LUT masks for 
#each input port than above. So far, it seems port E is used every time
lut_dict_end = {
"A": [],
"C": [],
"D": [],
"E": ["0000", "FFFF", "0000", "FFFF"],
"F": ["0000", "0000", "FFFF", "FFFF"],
}


#set up dictionary structure. X is placeholder until the value of the port is determined
for i in range(0, nRO):
	inv_dict = {}
	for j in range(1, nstages+1):
		inv_dict[j] = 'X'
	port_dict[i] = inv_dict

match_pattern = re.compile(r"dest = \( RO:generate_RO\[.*?\]\.ro_inst\|inv\[.*?\]")
pattern_RO = re.compile(r"dest = \( RO:generate_RO\[(.*?)\]")
pattern_inv = re.compile(r"\.ro_inst\|inv\[(.*?)\]")
pattern_port = re.compile(r"route_port = DATA([\w])")

#Create routing file
os.system("quartus_cdb ROarray_v3 --back_annotate=routing")


#Open .rcf file and get initial states
count = 0
with open(rcf_file, 'r') as rcf:
	for line in rcf:
		match = re.search(match_pattern, line)
		if match:
			RO_match = re.search(pattern_RO, line)
			inv_match = re.search(pattern_inv, line)
			port_match = re.search(pattern_port, line)
			
			RO_num = int(RO_match.group(1))
			inv_num = int(inv_match.group(1))
			port = port_match.group(1)
			
			port_dict[RO_num][inv_num] = port
			
			#print(str(RO_num) + ', ' + str(inv_num) + ', ' + port)
			count +=1



# for RO in port_dict:
	# end_port = port_dict[RO][9]
	# print("RO: {} , Port: {}".format(RO, end_port))



#---------------------Create tcl script with routing assignments---------------------

#Lists with some repeatedly used strings
lut_strings = ['"F0 LUT Mask"','"F1 LUT Mask"', '"F2 LUT Mask"', '"F3 LUT Mask"' ]
position_strings = ["top", "bottom"]

with open(tcl_file, 'w') as tcl_script:
	#Some setup stuff, also opens project that you want to modify the routing of
	tcl_script.write('package require ::quartus::chip_planner\npackage require ::quartus::project\nload_chip_planner_utility_commands\n' +
	                'project_open ROarray_v3 -revision ROarray_v3\nread_netlist\nset had_failure 0 \n\n\n')

	#Loop through all inverters and generate tcl commands to change the ports and LUT masks
	for RO in port_dict:
		for inv in port_dict[RO]:
			orig_port = port_dict[RO][inv]
			
			if orig_port!=new_port:
				src_inv = inv - 1
				if inv == 1:
					src_inv = nstages
				position = 1-inv%2      #element is in the top of the lcell if inverter number is odd, bottom if it is even (0 - top, 1 - bottom)
				
				#Create lists indicating which LUT masks could require changes based on if inverter is top/bottom combinational and if inverter is at end of oscillator
				if position:
					change_masks = [0, 1, 0, 1]
				if not position:
					change_masks = [1, 0, 1, 0]
				
				#Handle case where inverter is at end of oscillator. op_mode indicates the operation mode of the lcell, fractured means the top and bottom are used for
				# separate nodes, normal means the top and bottom are used for one node
				if inv==nstages:
					lut_dict = lut_dict_end
					change_masks = [1, 1, 1, 1]
					op_mode = 'normal'
				else:
					lut_dict = lut_dict_reg
					op_mode = 'fractured'
				
				#Create connection for new input port
				tcl_script.write('\n#### Create input port {} connection for RO[{}] inv[{}] #### \n\n'.format(new_port, RO, inv) +
					'set node_properties [ node_properties_record #auto \\\n' + 
					'\t-node_name |ROarray_v3|RO:generate_RO\[{}\].ro_inst|inv\[{}\] \\\n'.format(RO, inv) + 
					'\t-node_type LCCOMB_SII \\\n' +
					'\t-op_mode {} \\\n'.format(op_mode) +
					'\t-position {} \\\n'.format(position_strings[position]) +
					'\t-f0_lut_mask {} \\\n'.format(lut_dict[orig_port][0]) +
					'\t-f1_lut_mask {} \\\n'.format(lut_dict[orig_port][1]) +
					'\t-f2_lut_mask {} \\\n'.format(lut_dict[orig_port][2]) +
					'\t-f3_lut_mask {} \\\n'.format(lut_dict[orig_port][3]) +
					'\t-fanins [ list \\\n' +
					'\t\t[ fanin_record #auto -dst {-port_type DATA%s -lit_index 0} -src {-node_name |ROarray_v3|RO:generate_RO\[%d\].ro_inst|inv\[%d\] -port_type COMBOUT -lit_index 0} -delay_chain_setting -1 ] \\\n'%(orig_port, RO, src_inv) +
					'\t] \\\n' +
					'] \n\n' +
					'set result [ make_ape_connection_wrapper $node_properties |ROarray_v3|RO:generate_RO\[{}\].ro_inst|inv\[{}\] DATA{} 0 |ROarray_v3|RO:generate_RO\[{}\].ro_inst|inv\[{}\] COMBOUT 0 -1 ]\n'.format(RO, inv, new_port, RO, src_inv) +
					'if { $result == 0 } {\n' +
					'set had_failure 1\n' +
					'puts "Use the following information to evaluate how to apply this change."\n' +
					'dump_node $node_properties\n' +
					'}\n' +
					'remove_all_record_instances\n')

				#Remove connection to original input port
				tcl_script.write('\n#### Remove port {} connection from RO[{}] inv[{}] #### \n\n'.format(orig_port, RO, inv) +
					'set node_properties [ node_properties_record #auto \\\n' + 
					'\t-node_name |ROarray_v3|RO:generate_RO\[{}\].ro_inst|inv\[{}\] \\\n'.format(RO, inv) + 
					'\t-node_type LCCOMB_SII \\\n' +
					'\t-op_mode {} \\\n'.format(op_mode) +
					'\t-position {} \\\n'.format(position_strings[position]) +
					'\t-f0_lut_mask {} \\\n'.format(lut_dict[orig_port][0]) +
					'\t-f1_lut_mask {} \\\n'.format(lut_dict[orig_port][1]) +
					'\t-f2_lut_mask {} \\\n'.format(lut_dict[orig_port][2]) +
					'\t-f3_lut_mask {} \\\n'.format(lut_dict[orig_port][3]) +
					'\t-fanins [ list \\\n' +
					'\t\t[ fanin_record #auto -dst {-port_type DATA%s -lit_index 0} -src {-node_name |ROarray_v3|RO:generate_RO\[%d\].ro_inst|inv\[%d\] -port_type COMBOUT -lit_index 0} -delay_chain_setting -1 ] \\\n'%(orig_port, RO, src_inv) +
					'\t\t[ fanin_record #auto -dst {-port_type DATA%s -lit_index 0} -src {-node_name |ROarray_v3|RO:generate_RO\[%d\].ro_inst|inv\[%d\] -port_type COMBOUT -lit_index 0} -delay_chain_setting -1 ] \\\n'%(new_port, RO, src_inv) +
					'\t] \\\n' +
					'] \n\n' +
					'set result [ remove_ape_connection_wrapper $node_properties |ROarray_v3|RO:generate_RO\[{}\].ro_inst|inv\[{}\] DATA{} 0  ] \n'.format(RO, inv, orig_port) +
					'if { $result == 0 } { \n' +
					'set had_failure 1 \n' +
					'puts "Use the following information to evaluate how to apply this change." \n' +
					'dump_node $node_properties \n' +
					'} \n' +
					'remove_all_record_instances \n')
				
				##Make changes to LUT masks
				
				
				#Change mask F0 if necessary
				LUT = 0
				if lut_dict[orig_port][LUT]!=lut_dict[new_port][LUT] and change_masks[LUT]:
					tcl_script.write('\n#### Change the {} lut mask #### \n\n'.format(lut_strings[LUT]) +
						'set node_properties [ node_properties_record #auto \\\n' + 
						'\t-node_name |ROarray_v3|RO:generate_RO\[{}\].ro_inst|inv\[{}\] \\\n'.format(RO, inv) + 
						'\t-node_type LCCOMB_SII \\\n' +
						'\t-op_mode {} \\\n'.format(op_mode) +
						'\t-position {} \\\n'.format(position_strings[position]) +
						'\t-f0_lut_mask {} \\\n'.format(lut_dict[orig_port][0]) +
						'\t-f1_lut_mask {} \\\n'.format(lut_dict[orig_port][1]) +
						'\t-f2_lut_mask {} \\\n'.format(lut_dict[orig_port][2]) +
						'\t-f3_lut_mask {} \\\n'.format(lut_dict[orig_port][3]) +
						'\t-fanins [ list \\\n' +
						'\t\t[ fanin_record #auto -dst {-port_type DATA%s -lit_index 0} -src {-node_name |ROarray_v3|RO:generate_RO\[%d\].ro_inst|inv\[%d\] -port_type COMBOUT -lit_index 0} -delay_chain_setting -1 ] \\\n'%(new_port, RO, src_inv) +
						'\t] \\\n' +
						'] \n\n' +
						'set result [ set_lutmask_wrapper $node_properties |ROarray_v3|RO:generate_RO\[{}\].ro_inst|inv\[{}\] {} {} ] \n'.format(RO, inv, lut_strings[LUT], lut_dict[new_port][LUT] ) +
						'if { $result == 0 } { \n' +
						'set had_failure 1 \n' +
						'puts "Use the following information to evaluate how to apply this change." \n' +
						'dump_node $node_properties \n' +
						'} \n' +
						'remove_all_record_instances \n')


				#Change mask F1 if necessary
				LUT = 1
				if lut_dict[orig_port][LUT]!=lut_dict[new_port][LUT] and change_masks[LUT]:
					tcl_script.write('\n#### Change the {} lut mask #### \n\n'.format(lut_strings[LUT]) +
						'set node_properties [ node_properties_record #auto \\\n' + 
						'\t-node_name |ROarray_v3|RO:generate_RO\[{}\].ro_inst|inv\[{}\] \\\n'.format(RO, inv) + 
						'\t-node_type LCCOMB_SII \\\n' +
						'\t-op_mode {} \\\n'.format(op_mode) +
						'\t-position {} \\\n'.format(position_strings[position]) +
						'\t-f0_lut_mask {} \\\n'.format(lut_dict[new_port][0]) +
						'\t-f1_lut_mask {} \\\n'.format(lut_dict[orig_port][1]) +
						'\t-f2_lut_mask {} \\\n'.format(lut_dict[orig_port][2]) +
						'\t-f3_lut_mask {} \\\n'.format(lut_dict[orig_port][3]) +
						'\t-fanins [ list \\\n' +
						'\t\t[ fanin_record #auto -dst {-port_type DATA%s -lit_index 0} -src {-node_name |ROarray_v3|RO:generate_RO\[%d\].ro_inst|inv\[%d\] -port_type COMBOUT -lit_index 0} -delay_chain_setting -1 ] \\\n'%(new_port, RO, src_inv) +
						'\t] \\\n' +
						'] \n\n' +
						'set result [ set_lutmask_wrapper $node_properties |ROarray_v3|RO:generate_RO\[{}\].ro_inst|inv\[{}\] {} {} ] \n'.format(RO, inv, lut_strings[LUT], lut_dict[new_port][LUT] ) +
						'if { $result == 0 } { \n' +
						'set had_failure 1 \n' +
						'puts "Use the following information to evaluate how to apply this change." \n' +
						'dump_node $node_properties \n' +
						'} \n' +
						'remove_all_record_instances \n')

				#Change mask F2 if necessary
				LUT = 2
				if lut_dict[orig_port][LUT]!=lut_dict[new_port][LUT] and change_masks[LUT]:
					tcl_script.write('\n#### Change the {} lut mask #### \n\n'.format(lut_strings[LUT]) +
						'set node_properties [ node_properties_record #auto \\\n' + 
						'\t-node_name |ROarray_v3|RO:generate_RO\[{}\].ro_inst|inv\[{}\] \\\n'.format(RO, inv) + 
						'\t-node_type LCCOMB_SII \\\n' +
						'\t-op_mode {} \\\n'.format(op_mode) +
						'\t-position {} \\\n'.format(position_strings[position]) +
						'\t-f0_lut_mask {} \\\n'.format(lut_dict[new_port][0]) +
						'\t-f1_lut_mask {} \\\n'.format(lut_dict[new_port][1]) +
						'\t-f2_lut_mask {} \\\n'.format(lut_dict[orig_port][2]) +
						'\t-f3_lut_mask {} \\\n'.format(lut_dict[orig_port][3]) +
						'\t-fanins [ list \\\n' +
						'\t\t[ fanin_record #auto -dst {-port_type DATA%s -lit_index 0} -src {-node_name |ROarray_v3|RO:generate_RO\[%d\].ro_inst|inv\[%d\] -port_type COMBOUT -lit_index 0} -delay_chain_setting -1 ] \\\n'%(new_port, RO, src_inv) +
						'\t] \\\n' +
						'] \n\n' +
						'set result [ set_lutmask_wrapper $node_properties |ROarray_v3|RO:generate_RO\[{}\].ro_inst|inv\[{}\] {} {} ] \n'.format(RO, inv, lut_strings[LUT], lut_dict[new_port][LUT] ) +
						'if { $result == 0 } { \n' +
						'set had_failure 1 \n' +
						'puts "Use the following information to evaluate how to apply this change." \n' +
						'dump_node $node_properties \n' +
						'} \n' +
						'remove_all_record_instances \n')
						
				#Change mask F3 if necessary
				LUT = 3
				if lut_dict[orig_port][LUT]!=lut_dict[new_port][LUT] and change_masks[LUT]:
					tcl_script.write('\n#### Change the {} lut mask #### \n\n'.format(lut_strings[LUT]) +
						'set node_properties [ node_properties_record #auto \\\n' + 
						'\t-node_name |ROarray_v3|RO:generate_RO\[{}\].ro_inst|inv\[{}\] \\\n'.format(RO, inv) + 
						'\t-node_type LCCOMB_SII \\\n' +
						'\t-op_mode {} \\\n'.format(op_mode) +
						'\t-position {} \\\n'.format(position_strings[position]) +
						'\t-f0_lut_mask {} \\\n'.format(lut_dict[new_port][0]) +
						'\t-f1_lut_mask {} \\\n'.format(lut_dict[new_port][1]) +
						'\t-f2_lut_mask {} \\\n'.format(lut_dict[new_port][2]) +
						'\t-f3_lut_mask {} \\\n'.format(lut_dict[orig_port][3]) +
						'\t-fanins [ list \\\n' +
						'\t\t[ fanin_record #auto -dst {-port_type DATA%s -lit_index 0} -src {-node_name |ROarray_v3|RO:generate_RO\[%d\].ro_inst|inv\[%d\] -port_type COMBOUT -lit_index 0} -delay_chain_setting -1 ] \\\n'%(new_port, RO, src_inv) +
						'\t] \\\n' +
						'] \n\n' +
						'set result [ set_lutmask_wrapper $node_properties |ROarray_v3|RO:generate_RO\[{}\].ro_inst|inv\[{}\] {} {} ] \n'.format(RO, inv, lut_strings[LUT], lut_dict[new_port][LUT] ) +
						'if { $result == 0 } { \n' +
						'set had_failure 1 \n' +
						'puts "Use the following information to evaluate how to apply this change." \n' +
						'dump_node $node_properties \n' +
						'} \n' +
						'remove_all_record_instances \n')


				#Update port for the changed element in the port dictionary
				port_dict[RO][inv] = new_port
				
	#Execute changes and close project
	tcl_script.write("\n\nputs \"\"\n" + 
					"set drc_result [check_netlist_and_save]\n" + 
					"if { $drc_result == 1 } {\n" + 
					"puts \"check_netlist_and_save: SUCCESS\"\n" + 
					"} else {\n" + 
					"puts \"check_netlist_and_save: FAIL\"\n" + 
					"}\n" + 
					"if { $had_failure == 1 } {\n" + 
					"puts \"Not all set operations were successful\"\n" + 
					"}\n" + 
					"project_close\n")


#Execute tcl script
os.system("quartus_cdb -t {}".format(tcl_file))






















