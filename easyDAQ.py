from PyQt5 import QtGui, QtCore
from PyQt5.QtCore import Qt
import pyqtgraph as pg
import serial
import struct
import sys
import time
import os
import ctypes
import serial.tools.list_ports
from hotfire_packet import ECParse

###############################################################################
###   CONFIGURATION   #########################################################
###############################################################################
						
flight_num_plots = 3                           
plot_area_height = 3                            
BUFFER_SIZE = 600 
# pnum = 8 # number of pressure channels
# snum = 8 # number of valve channels
# lnum = 4 # number of LED channels
# lcnum = 0 # number of loadcells                                             			                          

###############################################################################
###   END CONFIGURATION   #####################################################
###############################################################################

parser = ECParse()
packet_number = 0
flight_packet_number = 0
heart_beat = 0
beats = "▖▘▝▗"

# COMMAND IDs
COMMAND_TARE             =    30
COMMAND_AMBIENTIZE         =    31
COMMAND_DIGITAL_WRITE     =    50
COMMAND_LED_WRITE         =    51
COMMAND_MOTOR_WRITE     =    52
COMMAND_MOTOR_DISABLE     =    53
COMMAND_MOTOR_ENABLE     =    54
COMMAND_QD_SET             =    55
COMMAND_SET_KP             =    60
COMMAND_SET_KI             =    61
COMMAND_SET_KD             =    62
COMMAND_TELEMRATE_SET    =    63
COMMAND_SAMPLERATE_SET    =    64
COMAND_LOGRATE_SET        =    65
COMMAND_ARM                =    100
COMMAND_DISARM            =    101
COMMAND_MAIN_AUTO_START    =    102
TARGET_ADDRESS_GROUND     =    100
TARGET_ADDRESS_FLIGHT     =    101
COMMAND_PRINT_FILE      =   40
COMMAND_NUMFILES        =   41
COMMAND_LOG_START       =   42
COMMAND_LOG_END         =   43
COMMAND_INIT_FS         =   44
COMMAND_TELEM_PAUSE     =   45
COMMAND_TELEM_RESUME   =   46

def s2_command(target_id, command_id, argc, argv):
	global packet_number, flight_packet_number
	if ser.isOpen():
		packet_number += 1
		command_id = command_id
		packet = [0]*(8+4*argc+2)
		packet[0] = packet_number >> 8
		packet[1] = packet_number & 0xff
		packet[2] = target_id >> 8
		packet[3] = target_id & 0xff
		packet[4] = command_id >> 8
		packet[5] = command_id & 0xff
		packet[6] = argc >> 8
		packet[7] = argc & 0xff
		for n in range(argc):
			packet[8+4*n] = (argv[n] >> 24) & 0xff
			packet[9+4*n] = (argv[n] >> 16) & 0xff
			packet[10+4*n] = (argv[n] >> 8) & 0xff
			packet[11+4*n] = argv[n] & 0xff
		for n in range(4+2*argc):
			packet[8+4*argc] ^= packet[2*n]
			packet[9+4*argc] ^= packet[2*n+1]
		
		packet = stuff_array(packet, 0)
		tosend = bytes(packet)
		ser.write(tosend)

		if(target_id == TARGET_ADDRESS_GROUND):
			#flight_packet_number += 1
			#flight_command_log.write(str(packet)+'\n')
			pass
		if(target_id == TARGET_ADDRESS_FLIGHT):
			flight_packet_number += 1
			flight_command_log.write(str(packet)+'\n')
	else:
		print("ERROR: Cannot send command. Port is not open")
		#print(str(argv))

def stuff_array(arr, seperator):
	arr.append(0)
	arr.insert(0, 0)
	first_sep = 1
	for x in arr[1:]:
		if x == seperator:
			break
		first_sep += 1
	index = 1
	while(index < len(arr)-1):
		if(arr[index] == seperator):
			offset = 1
			while(arr[index+offset] != seperator):
				offset += 1
			arr[index] = offset
			index += offset
		else:
			index += 1
	arr[0] = first_sep
	return arr


def get_file(target_id):
	s2_command(target_id, COMMAND_TELEM_PAUSE, 0, [])
	print("Telemetry paused.")
	time.sleep(0.1)

	response = 1               #
	print("There are "+str(response)+" files to read.")
	filelist = []
	for filenum in range(response):
		print("Downloading file "+str(filenum)+"...")
		mydir = os.path.join(os.getcwd(), "data", str(time.strftime("%Y_%m_%d_-_%H%M_%S")))
		os.makedirs(mydir)
		filename = mydir+"/"+str(filenum)+".bin"
		filelist.append(filename)
		binfile = open(filename, "wb")              # Open the binary
		readfile = True
		s2_command(target_id, COMMAND_PRINT_FILE, 1, [0])
		while(readfile):
			try:
				page = ser.read(2048)                  # Read a page
				if(len(page) != 2048):
					readfile = False
				binfile.write(page)                    # Log to bin
			except SerialTimeoutException:       # Read pages until the fc stops sending them
				readfile = False                       # Then move on to the next file
			except:
				print("Serial error")                  # Oops
				exit(1)
		binfile.close()                             # Close bin file


	s2_command(target_id, COMMAND_TELEM_RESUME, 0, [])
	print("All files downloaded.")
	print("Telemetry Resumed.")
	
	file = open(filename, 'rb')
	datalog = open(filename+'_datalog.csv', 'w')
	datalog.write(parser.csv_header)

	packets = []
	this_line = []
	n = 0
	while True:
		b = file.read(1)
		# print(b)
		if not b:
			break
		if b == b'\x0a':
			n += 1
			packets.append(this_line)
			this_line = []
		else:
			this_line += b

	print(n)

	for packet in packets:
		# print(len(packet))
		packet = list(packet)
		unstuffed = b''
		index = int(packet[0])
		for n in range(1, len(packet)):
			temp = bytes(packet[n:n+1])
			if(n == index):
				index = int(packet[n])+n
				temp = b'\n'
			unstuffed = unstuffed + temp
		packet = unstuffed
		# print(list(unstuffed))
		try:
			parser.parse_packet(packet)
		except:
			pass
		if not(parser.valve_states == 65535):
			datalog.write(parser.log_string+'\n')
		#os.system("python csvplot.py "+filename)
		#print("")

###############################################################################
### APPLICATION INITILIZATION #################################################
###############################################################################

# apparently I need to mess with process ids just to get the logo in the task bar
appid = 'MASA.EasyDAQ' # arbitrary string
if os.name == 'nt': # Bypass command because it is not supported on Linux 
	ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(appid)
else:
	pass
	# NOTE: On Ubuntu 18.04 this does not need to done to display logo in task bar

# initialize application
app = QtGui.QApplication([])
app.setWindowIcon(QtGui.QIcon('logos/logo_ed.png'))
runbox = QtGui.QWidget()
run_name, ok = QtGui.QInputDialog().getText(runbox, 'Run Name', ' Enter Run Name: ')
if not ok or len(run_name) == 0:
	run_name = "test"

# open log files
if not os.path.exists("data/" + run_name + "/"):
	os.makedirs("data/" + run_name + "/")
flight_serial_log = open('data/'+run_name+"/"+run_name+"_flight_serial_log.csv", "w+")
flight_info_log = open('data/'+run_name+"/"+run_name+"_flight_python_log.csv", "w+")
flight_command_log = open('data/'+run_name+"/"+run_name+"_flight_command_log.csv", "w+")
flight_data_log = open('data/'+run_name+"/"+run_name+"_flight_datalog.csv", "w+")
flight_command_log.write("Time, Command/info\n")
flight_data_log.write(parser.csv_header)

# window with central layout
main_window = QtGui.QWidget()
top_layout = QtGui.QGridLayout()
main_window.setLayout(top_layout)
top = QtGui.QMainWindow()
top.setCentralWidget(main_window)
top.setWindowTitle("MASA EasyDAQ - " + str(run_name))

# tabs
tabs = QtGui.QTabWidget()
top_layout.addWidget(tabs, 0, 1)

# main tab
control_widget = QtGui.QWidget()
tabs.addTab(control_widget, "Main")
flight_layout = QtGui.QGridLayout()
control_widget.setLayout(flight_layout)

# config tab
# cal_widget = QtGui.QWidget()
# tabs.addTab(cal_widget, "Configuration")
# cal_layout = QtGui.QGridLayout()
# cal_widget.setLayout(cal_layout)
# wip_label = QtGui.QLabel()
# wip_label.setText("COMING SOON TO A GUI NEAR YOU")
# cal_layout.addWidget(wip_label)

# menu bar
main_menu = top.menuBar()
main_menu.setNativeMenuBar(True)
options_menu = main_menu.addMenu('&Options')

# sidebar
sidebar = QtGui.QWidget()
top_layout.addWidget(sidebar, 0, 0)
sidebar_layout = QtGui.QVBoxLayout()
sidebar.setLayout(sidebar_layout)
sidebar.setFixedWidth(450)

# logo
logo = QtGui.QLabel()
#logo.setGeometry(0, 0, 300, 158)
logo.setPixmap(QtGui.QPixmap(os.getcwd() + "/logos/logo_ed_norocket.png"))
logo.setAlignment(QtCore.Qt.AlignCenter)
sidebar_layout.addWidget(logo)

if run_name == "XP":
	app.setStyle('Windows')

#main tab offsets
zr = 0
zc = 0


################### PLOT DEV ########################

flight_active_plots = [0]*parser.num_items
plot_y = [[]]*parser.num_items
plot_x = [[]]*parser.num_items
flight_curves = [None]*parser.num_items
time_start = time.time()

def flight_plots_update(item_clicked):
	global plot_x, plot_y, BUFFER_SIZE, flight_curves
	if(not item_clicked.column() == 2):
		return
	if(flight_active_plots[item_clicked.row()] == flight_num_plots):
		flight_active_plots[item_clicked.row()] = 0
		temp_item = QtGui.QTableWidgetItem('off')
		temp_item.setBackground(QtGui.QColor(250,150,150))
		table.setItem(item_clicked.row(), item_clicked.column(), temp_item)
		flight_plots[flight_active_plots[item_clicked.row()]-1].removeItem(flight_curves[item_clicked.row()])
	else:
		flight_active_plots[item_clicked.row()] += 1
		temp_item = QtGui.QTableWidgetItem(str(flight_active_plots[item_clicked.row()]))
		temp_item.setBackground(QtGui.QColor(150, 250, 150))
		table.setItem(item_clicked.row(), item_clicked.column(), temp_item)
		flight_curves[item_clicked.row()] = (flight_plots[flight_active_plots[item_clicked.row()]-1].plot(plot_x[n], plot_y[n], pen='r'))

def flight_reset_plot():
	global plot_x, plot_y, BUFFER_SIZE, flight_curves
	plot_y = [[]]*parser.num_items
	plot_x = [[]]*parser.num_items

flight_clear_plot = QtGui.QPushButton("Clear plots")
flight_clear_plot.clicked.connect(lambda: flight_reset_plot())

clear = QtGui.QAction("&Clear Plots", options_menu)
clear.setShortcut("Ctrl+D")
clear.triggered.connect(flight_reset_plot)
options_menu.addAction(clear)

pg.setConfigOption('background', 'w')
flight_plots = []
for n in range(flight_num_plots):
	flight_plots.append(pg.PlotWidget(title='Plot '+str(n+1)))
	flight_layout.addWidget(flight_plots[n], zr+(plot_area_height/flight_num_plots)*n, zc+2, int(plot_area_height/flight_num_plots), 1)


##################### END PLOT DEV ########################

# Full telemetry table
table = QtGui.QTableWidget()
table.setRowCount(parser.num_items)
table.setColumnCount(3)
table.setHorizontalHeaderLabels(['Channel', 'Value', 'Plot'])
header = table.horizontalHeader()
header.setResizeMode(2, QtGui.QHeaderView.Stretch)
for n in range(parser.num_items):
	table.setItem(n,0, QtGui.QTableWidgetItem(parser.items[n]))
	temp_item = QtGui.QTableWidgetItem("off")
	temp_item.setBackground(QtGui.QColor(250,150,150))
	table.setItem(n, 2, temp_item)
flight_layout.addWidget(table, zr+0, zc+1, plot_area_height, 1)
table.clicked.connect(flight_plots_update)

# Populate the alias and cal dictionaries
alias = {}
cal_slope = {}
cal_offset = {}
with open("config.txt") as cfg_file:
	cfg_file.readline()
	for line in cfg_file:
		s = line.split('\t')
		#print(str(s))
		if len(s) < 3:
			alias[s[0]] = s[1].rstrip('\n')
		else:
			alias[s[0]] = s[1]
			cal_slope[s[1]] = float(s[2])
			cal_offset[s[1]] = float(s[3].rstrip('\n'))
flight_info_log.write("alias"+str(alias)+"\n")
flight_info_log.write("cal_slope"+str(cal_slope)+"\n")
flight_info_log.write("cal_offset"+str(cal_offset)+"\n")

pnum = int(alias['pnum']) # number of pressure channels
snum = int(alias['snum']) # number of valve channels
lnum = int(alias['lnum']) # number of LED channels
lcnum = int(alias['lcnum']) # number of loadcells 
		
# populate auto state names
try:
	if("STATE_N" in alias.keys()):
		state_dict = {}
		for n in range(0, int(alias["STATE_N"])):
			state_dict[n] = alias["STATE"+str(n)]
	else:
		raise Exception("STATE_N definition not found in devices.alias file")
except Exception:
	print("INVALID STATE ALIAS DEFINITIONS")

# load cells
lc_tare = [0]*5
lc_load = [0]*5

# Tare
def tare():
	global lc_tare
	lc_tare = lc_load.copy()


##################### START PORT MANAGEMENT ########################

# Try to open the serial port
ser = serial.Serial(port=None, baudrate=int(alias["BAUDRATE"]), timeout=0.2)
ser.port = alias["COM_PORT"]
try:
	ser.open()
	if(ser.is_open):
		ser.readline()
		print("Port active on "+ser.port)
	else:
		print("Serial port is not open")
except:
	print("Could not open Serial Port")

#scan ports
ports = [p.device for p in serial.tools.list_ports.comports()]

#connect to port
def connect():
	global ser, ports_box
	if ser.isOpen():
		ser.close()
	try:
		ser.port = str(ports_box.currentText())
		ser.open()
		ser.readline()
		print("Connection established on %s" % str(ports_box.currentText()))
	except:
		print("Unable to connect to selected port or no ports available")

#scan for com ports
def scan():
	global ports_box
	ports = [p.device for p in serial.tools.list_ports.comports()]
	ports_box.clear()
	ports_box.addItems(ports)

#connection box (add to connection_layout)
connection = QtGui.QGroupBox("Connection")
sidebar_layout.addWidget(connection)
connection_layout = QtGui.QGridLayout()
connection.setLayout(connection_layout)
scanButton = QtGui.QPushButton("Scan")
scanButton.clicked.connect(scan)
connection_layout.addWidget(scanButton, 1, 0, 1, 2)
connectButton = QtGui.QPushButton("Connect")
connectButton.clicked.connect(connect)
connection_layout.addWidget(connectButton, 2, 0, 1, 2)
ports_box = QtGui.QComboBox()
connection_layout.addWidget(ports_box, 0, 0)
heart_beat_indicator = QtGui.QLabel("▖")
connection_layout.addWidget(heart_beat_indicator, 0, 1)
connection_layout.setColumnStretch(0, 75)
connection_layout.setColumnStretch(0, 50)

##################### END PORT MANAGEMENT ########################

###############################################################################
#  END APPLICATION INITILIZATION ##############################################
###############################################################################

###############################################################################
### PARSER ####################################################################
###############################################################################

# Parse a line and upate GUI fields
write_csv_header = True
def parse_serial():
	global plot_y, plot_x, flight_curves, heart_beat
	try:
		if ser.is_open:
			# Read a packet
			packet = ser.readline()
			
			# Unstuff the packet
			unstuffed = b''
			index = int(packet[0])
			for n in range(1, len(packet)):
				temp = packet[n:n+1]
				if(n == index):
					index = int(packet[n])+n
					temp = b'\n'
				unstuffed = unstuffed + temp
			packet = unstuffed

			parser.parse_packet(packet)

			###################################################################
			### DATA UPDATE ###################################################
			###################################################################
			if(parser.BOARD_ID == TARGET_ADDRESS_FLIGHT):
				flight_data_log.write(parser.log_string+'\n')
				flight_serial_log.write(time.strftime("%H:%M:%S"))
				flight_serial_log.write(str(packet)+'length = '+str(len(packet))+'\n')

				if(parser.ebatt < 10):
					print(len(packet))
				else:
					# print(str(len(packet))+" - good")
					pass

				for n in range(parser.num_items-1):
					plot_y[n].append(float(parser.dict[parser.items[n]]))
					plot_x[n].append(int(time.time()-time_start))
					plot_y[n] = plot_y[n][-BUFFER_SIZE:]
					plot_x[n] = plot_x[n][-BUFFER_SIZE:]
					if flight_active_plots[n]:
						flight_curves[n].setData(plot_x[n][:], plot_y[n][:])
						app.processEvents()

				mask = 1
				# Update valve state feedback
				for n in range(0, snum):
					state = 0
					if(mask & parser.valve_states):
						state = 1

					vlv_id = 'f'+'vlv'+str(n)
					if vlv_id in alias.keys():
						vlv_id = alias[vlv_id]

					flight_valve_buttons[n][0].setText(vlv_id+" is "+str(state))
					flight_valve_buttons[n][1].setText(str(parser.ivlv[n])+"A / "+str(parser.evlv[n])+"V")
					mask = mask << 1
				for n in range(0, pnum):
					this_press = parser.pressure[n]
					if(alias['fpressure'+str(n)] in cal_offset.keys()):
						this_press -= cal_offset[alias['fpressure'+str(n)]]
						this_press *= cal_slope[alias['fpressure'+str(n)]]
					this_press = int(this_press)
					flight_pressure_labels[n][1].setText(str(this_press)+" psi")

				total_thrust = 0
				for n in range(0, lcnum): # update loadcells
					this_load = parser.load[n]
					if('LOADCELL-'+str(n) in cal_offset.keys()):
						this_load -= cal_offset['LOADCELL-'+str(n)]
						this_load *= cal_slope['LOADCELL-'+str(n)]
					lc_load[n] = this_load
					this_load -= float(lc_tare[n])
					total_thrust += this_load
					this_load = int(this_load)
					flight_load_cell_labels[n][1].setText(str(this_load)+" kg")
				flight_total_load_label[1].setText(str(int(total_thrust))+" kg")

				# Board health
				flight_ebatt_value.setText(str(parser.ebatt))
				flight_ibus_value.setText(str(parser.ibus))
				flight_e5v_value.setText(str(parser.e5v))
				flight_e3v_value.setText(str(parser.e3v))

				last_packet_flight.setText(str(parser.last_packet_number))
				last_command_flight.setText(str(parser.last_command_id))
				if(parser.last_packet_number == flight_packet_number):
					flight_BOARD_HEALTH_LABEL.setText("PACKET GOOD")
					pass
				else:
					flight_BOARD_HEALTH_LABEL.setText("PACKET BAD")
					pass

				flight_samplerate_send.setText("Samplerate: "+str(parser.samplerate)+"hz")
				flight_telemrate_send.setText("Telemrate: "+str(parser.telemetry_rate)+"hz")

				state_label.setText("STATE = "+state_dict[parser.STATE])

				for n in range(parser.num_items - 1):
					table.setItem(n, 1, QtGui.QTableWidgetItem(str(parser.dict[parser.items[n]])))

				#heart beat
				heart_beat_indicator.setText(beats[heart_beat % len(beats)])
				heart_beat += 1
				###################################################################
				### END DATA UPDATE ###############################################
				###################################################################

	except Exception as e:
		##print(e)
		pass

###############################################################################
### END PARSER ################################################################
###############################################################################

###############################################################################
### GUI LAYOUT ################################################################
###############################################################################

# Populate pressure labels and valve buttons
flight_valve_buttons = []
flight_pressure_labels = []
flight_load_cell_labels = []
for valve_buttons, pressure_labels, load_labels, abbrev in [(flight_valve_buttons, flight_pressure_labels, flight_load_cell_labels, 'f')]:
	for n in range(0, snum):
		# Valve widgets init
		temp = []
		vlv_id = abbrev+'vlv'+str(n)
		if vlv_id in alias.keys():
			vlv_id = alias[vlv_id]
		temp.append(QtGui.QPushButton(str(vlv_id)+' is 0'))
		temp.append(QtGui.QLabel())
		valve_buttons.append(temp)
	for n in range(0, pnum):
		# Pressure reading widgets init
		ptemp = []
		ptemp.append(QtGui.QLabel())
		ptemp.append(QtGui.QLabel())
		pressure_labels.append(ptemp)
		press_id = abbrev+"pressure"+str(n)
		if press_id in alias.keys():
			press_id = alias[press_id]
		pressure_labels[n][0].setText(press_id+":")
		pressure_labels[n][1].setText(str(0)+" psi")
	
	for n in range(0, lnum):
		# led widget init
		temp = []
		led_id = 'LED '+str(n)
		temp.append(QtGui.QPushButton(str(led_id)+' is 0'))
		valve_buttons.append(temp)

	# Load cell reading widgets init
	for n in range(0, lcnum):
		ltemp = []
		ltemp.append(QtGui.QLabel())
		ltemp.append(QtGui.QLabel())
		load_labels.append(ltemp)
		load_id = "Load Cell "+str(n)
		load_labels[n][0].setText(load_id+":")
		load_labels[n][1].setText(str(0)+" kg")

# command region (pressure and valves)
command = QtGui.QWidget()
command_layout = QtGui.QGridLayout()
command.setLayout(command_layout)
flight_layout.addWidget(command, zr+0, zc+0, plot_area_height, 1)

# Valves column
valves_holder = QtGui.QWidget()
valves_holder_layout = QtGui.QVBoxLayout()
valves_holder.setLayout(valves_holder_layout)
valves = QtGui.QGroupBox("Valves")
valves_layout = QtGui.QGridLayout()
valves_layout.setVerticalSpacing(15)
valves.setLayout(valves_layout)
valves_holder_layout.addWidget(valves)

# Pressures column
pressures_holder = QtGui.QWidget()
pressures_holder_layout = QtGui.QVBoxLayout()
pressures_holder.setLayout(pressures_holder_layout)
pressures = QtGui.QGroupBox("Pressures")
pressures_layout = QtGui.QGridLayout()
pressures_layout.setVerticalSpacing(40)
pressures.setLayout(pressures_layout)
pressures_holder_layout.addWidget(pressures)

# build command buttons
def layout_common_widgets(vlayout, playout, vlv_buttons, p_labels):
	for n in range(0, snum):
		vlayout.addWidget(vlv_buttons[n][0], n, 0)
		vlayout.addWidget(vlv_buttons[n][1], n, 1)
		vlv_buttons[n][1].setText(str(0.0)+"A / "+str(0.0)+"V")
	for n in range(0, pnum):
		playout.addWidget(p_labels[n][0], n, 0)
		playout.addWidget(p_labels[n][1], n, 1)
	for n in range(0, lnum):
		vlayout.addWidget(vlv_buttons[n+snum][0], n+1+snum, 0)

# add buttons
layout_common_widgets(valves_layout, pressures_layout, flight_valve_buttons, flight_pressure_labels)

#add command columns
command_layout.addWidget(valves_holder, 0, 0)
command_layout.addWidget(pressures_holder, 0, 1)
cwidth = command.geometry().width()
valves_holder.setFixedWidth(cwidth*0.75)
pressures_holder.setFixedWidth(cwidth*0.65)


# Autosequence control and state feedback
autos = QtGui.QGroupBox("Autos")
autos_layout = QtGui.QGridLayout()
autos.setLayout(autos_layout)
state_label = QtGui.QLabel("STATE = N/A")
arm_button = QtGui.QPushButton("ARM")
disarm_button = QtGui.QPushButton("DISARM")
hotfire_button = QtGui.QPushButton("RUN AUTO")
autos_layout.addWidget(state_label, 0, 0)
autos_layout.addWidget(arm_button, 1, 0)
autos_layout.addWidget(disarm_button, 2, 0)
autos_layout.addWidget(hotfire_button, 3, 0)
sidebar_layout.addWidget(autos)

# telem and logging commands
filesystembox = QtGui.QGroupBox("Logging and Filesystem")
file_layout = QtGui.QVBoxLayout()
filesystembox.setLayout(file_layout)
sidebar_layout.addWidget(filesystembox)
init_fs = QtGui.QPushButton("Init Filesystem")
log_start = QtGui.QPushButton("Log Start")
log_end = QtGui.QPushButton("Log Stop")
telem_pause = QtGui.QPushButton("Pause Telemetry")
telem_resume = QtGui.QPushButton("Resume Telemetry")
file_download = QtGui.QPushButton("Download file")

file_layout.addWidget(init_fs)
file_layout.addWidget(log_start)
file_layout.addWidget(log_end)
file_layout.addWidget(file_download)
file_layout.addWidget(telem_pause)
file_layout.addWidget(telem_resume)

# Samplerate Set
flight_samplerate_setpoint = QtGui.QLineEdit('50')
flight_samplerate_send = QtGui.QPushButton("Update samplerate (Hz)")
file_layout.addWidget(flight_samplerate_send)
file_layout.addWidget(flight_samplerate_setpoint)

# Telemrate set
flight_telemrate_setpoint = QtGui.QLineEdit('10')
flight_telemrate_send = QtGui.QPushButton("Update telemrate (Hz)")
file_layout.addWidget(flight_telemrate_send)
file_layout.addWidget(flight_telemrate_setpoint)

# Board Health labels
health = QtGui.QGroupBox("Board Health")
health_layout = QtGui.QGridLayout()
health.setLayout(health_layout)
sidebar_layout.addWidget(health)
flight_BOARD_HEALTH_LABEL = QtGui.QLabel("PACKETSTATUS")
flight_ebatt_label =  QtGui.QLabel("Bus Voltage:")
flight_ibus_label =  QtGui.QLabel("Bus Current:")
flight_e5v_label = QtGui.QLabel("5V:")
flight_e3v_label = QtGui.QLabel("3V3:")
flight_ebatt_value =  QtGui.QLabel("ebatt")
flight_ibus_value = QtGui.QLabel("ibus")
flight_e5v_value =  QtGui.QLabel("e5v")
flight_e3v_value =  QtGui.QLabel("e3v")
health_layout.addWidget(flight_BOARD_HEALTH_LABEL, 0, 0, 1, 2)
health_layout.addWidget(flight_ebatt_label, 1, 0)
health_layout.addWidget(flight_ibus_label, 2, 0)
health_layout.addWidget(flight_e5v_label, 3, 0)
health_layout.addWidget(flight_e3v_label, 4, 0)
health_layout.addWidget(flight_ebatt_value, 1, 1)
health_layout.addWidget(flight_ibus_value, 2, 1)
health_layout.addWidget(flight_e5v_value, 3, 1)
health_layout.addWidget(flight_e3v_value, 4, 1)

# Last packet info
last_packet_flight_label = QtGui.QLabel("Packet #:")
last_command_flight_label = QtGui.QLabel("Last Command:")
health_layout.addWidget(last_packet_flight_label, 5, 0)
health_layout.addWidget(last_command_flight_label, 6, 0)
last_packet_flight = QtGui.QLabel("lastpacket")
last_command_flight = QtGui.QLabel("lastcommand")
health_layout.addWidget(last_packet_flight, 5, 1)
health_layout.addWidget(last_command_flight, 6, 1)

# tare button
lcbox = QtGui.QGroupBox("Load Cells")
lcbox_layout = QtGui.QGridLayout()
lcbox.setLayout(lcbox_layout)
if lcnum > 0:
	pressures_holder_layout.addWidget(lcbox)

for n in range(0, lcnum):
	lcbox_layout.addWidget(flight_load_cell_labels[n][0], n+1, 0)
	lcbox_layout.addWidget(flight_load_cell_labels[n][1], n+1, 1)

flight_total_load_label = []
flight_total_load_label.append(QtGui.QLabel())
flight_total_load_label.append(QtGui.QLabel())
flight_total_load_label[0].setText("Total Thrust:")
flight_total_load_label[1].setText(str(0)+" kg")

lcbox_layout.addWidget(flight_total_load_label[0], 0, 0)
lcbox_layout.addWidget(flight_total_load_label[1], 0, 1)
tare_button = QtGui.QPushButton("Tare")
lcbox_layout.addWidget(tare_button, lcnum+2, 0, 1, 2)
tare_button.clicked.connect(tare)


# padding and spacing
sidebar_layout.addStretch(1)
valves_holder_layout.addStretch(1)
pressures_holder_layout.addStretch(1)
flight_layout.setColumnStretch(zc+0, 230)
flight_layout.setColumnStretch(zc+1, 170)
flight_layout.setColumnStretch(zc+2, 390)

###############################################################################
### END GUI LAYOUT ############################################################
###############################################################################


###############################################################################
### FUNCTIONAL CONNECTIONS ####################################################
###############################################################################

init_fs.clicked.connect(lambda: s2_command(TARGET_ADDRESS_FLIGHT, COMMAND_INIT_FS, 0, []))
log_start.clicked.connect(lambda: s2_command(TARGET_ADDRESS_FLIGHT, COMMAND_LOG_START, 0, []))
log_end.clicked.connect(lambda: s2_command(TARGET_ADDRESS_FLIGHT, COMMAND_LOG_END, 0, []))
telem_pause.clicked.connect(lambda: s2_command(TARGET_ADDRESS_FLIGHT, COMMAND_TELEM_PAUSE, 0, []))
telem_resume.clicked.connect(lambda: s2_command(TARGET_ADDRESS_FLIGHT, COMMAND_TELEM_RESUME, 0, []))
file_download.clicked.connect(lambda: get_file(TARGET_ADDRESS_FLIGHT))

flight_samplerate_send.clicked.connect(lambda: s2_command(TARGET_ADDRESS_FLIGHT, COMMAND_SAMPLERATE_SET, 1, [int(flight_samplerate_setpoint.text())]))
flight_telemrate_send.clicked.connect(lambda: s2_command(TARGET_ADDRESS_FLIGHT, COMMAND_TELEMRATE_SET, 1, [int(flight_telemrate_setpoint.text())]))

arm_button.clicked.connect(lambda: s2_command(TARGET_ADDRESS_FLIGHT, COMMAND_ARM, 0, []))
disarm_button.clicked.connect(lambda: s2_command(TARGET_ADDRESS_FLIGHT, COMMAND_DISARM, 0, []))
hotfire_button.clicked.connect(lambda: s2_command(TARGET_ADDRESS_FLIGHT, COMMAND_MAIN_AUTO_START, 0, []))

def toggle_valve(board, vlv_id):
	if board is 'flight':
		state = int(flight_valve_buttons[vlv_id][0].text()[-1])
		state = int(not state)
		s2_command(TARGET_ADDRESS_FLIGHT, COMMAND_DIGITAL_WRITE, 2, [vlv_id, state])

def toggle_led(board, vlv_id):
	if ser.is_open:
		if board is 'flight':
			state1 = flight_valve_buttons[vlv_id+snum][0].text()
			state2 = str(int(not int(state1[-1])))
			state1 = list(state1)
			state1[-1] = state2
			flight_valve_buttons[vlv_id+snum][0].setText(''.join(state1))
			s2_command(TARGET_ADDRESS_FLIGHT, COMMAND_LED_WRITE, 2, [vlv_id, state2])

## VALVE FUNCTIONS
for n in range(0, snum):
	flight_valve_buttons[n][0].clicked.connect(lambda _, bound_n=n: toggle_valve('flight', bound_n))

## LED FUNCTIONS
for n in range(0, lnum):
	flight_valve_buttons[snum+n][0].clicked.connect(lambda _, bound_n=n: toggle_led('flight', bound_n))

resize = QtGui.QAction("&Resize Window", options_menu)
resize.setShortcut("Ctrl+R")
options_menu.addAction(resize)

def death():
	flight_command_log.close()
	flight_info_log.close()
	flight_serial_log.close()
	flight_data_log.close()
	app.quit()

quit = QtGui.QAction("&Quit", options_menu)
quit.setShortcut("Ctrl+Q")
quit.triggered.connect(death)
options_menu.addAction(quit)


##############################################################################
### END FUNCTIONAL CONNECTIONS ###############################################
##############################################################################

# scan for ports
scan()
connect()

# Start
top.showMaximized()
ww = top.geometry().width()
wh = top.geometry().height()
top.setFixedSize(ww, wh)

def resizer():
	global top
	top.setFixedSize(app.desktop().screenGeometry().width(), wh)

resize.triggered.connect(resizer)

# main timer
timer2 = pg.QtCore.QTimer()
timer2.timeout.connect(parse_serial)
timer2.start(10) # 100hz for 10 as arg

# Watchdog
parity = True
def reset_watchdog():
	if ser.is_open:
		try:
			global parity
			if parity:
				s2_command(TARGET_ADDRESS_FLIGHT, COMMAND_LED_WRITE, 2, [2,0])
				parity = False
			else:
				s2_command(TARGET_ADDRESS_GROUND, COMMAND_LED_WRITE, 2, [2,0])
				parity = True
		except:
			pass

watchdog_reset_timer = pg.QtCore.QTimer()
watchdog_reset_timer.timeout.connect(reset_watchdog)
watchdog_reset_timer.start(250)

# handoff to application
app.exec_()

# close files and cleanup
death()