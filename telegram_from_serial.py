#!/usr/bin/env python3
# Python script to retrieve and parse a DSMR telegram from a P1 port

import re
import sys
import serial
import crcmod.predefined
import datetime
import argparse
import argcomplete
# PYTHON_ARGCOMPLETE_OK


def main():
    # Default settings:
    dailyLine = False  # Print a log line every 10s
    # dailyLine = True   # Print a single daily line to be copied into the daily file manually
    
    # Debugging settings
    production = True   # Use serial or file as input
    debugging = 0       # Show extra output (0-3)
    # DSMR interesting codes
    gas_meter = '1' 
    list_of_interesting_codes = {
        '1-0:1.8.1': 'Meter Reading electricity delivered to client (Tariff 1) in kWh',
        '1-0:1.8.2': 'Meter Reading electricity delivered to client (Tariff 2) in kWh',
        '1-0:2.8.1': 'Meter Reading electricity delivered by client (Tariff 1) in kWh',
        '1-0:2.8.2': 'Meter Reading electricity delivered by client (Tariff 2) in kWh',
        '0-0:96.14.0': 'Tariff indicator electricity',
        '1-0:1.7.0': 'Actual electricity power delivered (+P) in kW',
        '1-0:2.7.0': 'Actual electricity power received (-P) in kW',
        '0-0:17.0.0': 'The actual threshold electricity in kW',
        '0-0:96.3.10': 'Switch position electricity',
        '0-0:96.7.21': 'Number of power failures in any phase',
        '0-0:96.7.9': 'Number of long power failures in any phase',
        '1-0:32.32.0': 'Number of voltage sags in phase L1',
        '1-0:52.32.0': 'Number of voltage sags in phase L2',
        '1-0:72:32.0': 'Number of voltage sags in phase L3',
        '1-0:32.36.0': 'Number of voltage swells in phase L1',
        '1-0:52.36.0': 'Number of voltage swells in phase L2',
        '1-0:72.36.0': 'Number of voltage swells in phase L3',
        '1-0:31.7.0': 'Instantaneous current L1 in A',
        '1-0:51.7.0': 'Instantaneous current L2 in A',
        '1-0:71.7.0': 'Instantaneous current L3 in A',
        '1-0:21.7.0': 'Instantaneous active power L1 (+P) in kW',
        '1-0:41.7.0': 'Instantaneous active power L2 (+P) in kW',
        '1-0:61.7.0': 'Instantaneous active power L3 (+P) in kW',
        '1-0:22.7.0': 'Instantaneous active power L1 (-P) in kW',
        '1-0:42.7.0': 'Instantaneous active power L2 (-P) in kW',
        '1-0:62.7.0': 'Instantaneous active power L3 (-P) in kW',
        '0-'+gas_meter+':24.2.1': 'Last hourly value (temperature converted), gas delivered to client in m3'
    }
    
    max_len = max(map(len,list_of_interesting_codes.values()))
        
    # Program variables
    # Set the way the values are printed:
    # print_format = 'string'
    # print_format = 'code'
    # print_format = 'table'  # Table with header, date and time and all energies and powers
    print_format = 'power'    # Time of day and net power (out - in)
    maxIter = float('inf')   # Maximum number of iterations
    # maxIter = 2               # Maximum number of iterations
    
    # The true telegram ends with an exclamation mark after a CR/LF
    pattern = re.compile('\r\n(?=!)')
    # According to the DSMR spec, we need to check a CRC16
    crc16 = crcmod.predefined.mkPredefinedCrcFun('crc16')
    # Create an empty telegram
    telegram = ''
    checksum_found = False
    good_checksum = False
    
    
    # Command-line options:
    
    # Parse command-line arguments:
    parser = argparse.ArgumentParser(description="Read data from an electricity meter via the P1 port.", 
                                     formatter_class=argparse.ArgumentDefaultsHelpFormatter)  # Use capital, period, add default values
    
    # Optional arguments:
    # parser.add_argument("-c", "--cron",      action="store_true", help="run in cron mode: save energies to a (yearly) file and 5 minutes of powers to a daily file")  # Default = False
    
    # Mutually exclusive:
    Format  = parser.add_mutually_exclusive_group()
    Format.add_argument("-c", "--cron",      action="store_true", help="run in cron mode: save energies to a (yearly) file and 5 minutes of powers to a daily file")  # Default = False
    Format.add_argument("-p", "--power",     action="store_true", help="print time and power only every 10s")  # Default = False
    Format.add_argument("-t", "--table",     action="store_true", help="print table with header, date, time, energies and powers every 10s")  # Default = False
    
    parser.add_argument("-i", "--iter",    type=int, default=6, help="number of (10s) iterations to monitor")
    # parser.add_argument("-v", "--verbosity", action="count", default=0, help="increase output verbosity")  # Counts number of occurrences
    # parser.add_argument("-t", "--twater",    type=float, default=50, help="water temperature in °C")
    
    argcomplete.autocomplete(parser)
    args = parser.parse_args()
    
    # Use arguments:
    if(args.power): print_format = 'power'  # Time of day and net power (out - in)
    if(args.table): print_format = 'table'  # Table with header, date and time and all energies and powers
    if(args.cron):  print_format = 'cron'   # Cron mode: save energies to a (yearly) file and 5 minutes of powers to a daily file
    maxIter = args.iter
    
    
    
    
    if production:
        # Serial port configuration:
        ser = serial.Serial()
        ser.baudrate = 9600              # DSMR 2.2: 9600;  DSMR 4.2/ESMR 5.0: 115200
        ser.bytesize = serial.SEVENBITS  # DSMR 2.2/4.2: SEVENBITS;  ESMR 5.0: EIGHTBITS
        ser.parity = serial.PARITY_EVEN  # ESMR 2.2/4.2: PARITY_EVEN;  ESMR 5.0: PARITY_NONE
        ser.stopbits = serial.STOPBITS_ONE
        ser.xonxoff = 1
        ser.rtscts = 0
        ser.timeout = 12
        ser.port = "/dev/ttyUSB0"
    else:
        # Testing:
        print("Running in test mode")
        ser = open("raw.out", 'rb')
    
    
    # Print table header:
    if(print_format == 'table'):
        print()
        if(dailyLine):
            print( "%10s,%6s, %8s, %9s,%10s,%10s,%10s" % ('Date','Time','Heat','Ein1','Ein2','Eout1','Eout2'))
        else:
            print( "%10s,%9s, %10s,%10s,%10s,%10s,%6s" % ('Date','Time','Ein1','Ein2','Eout1','Eout2','Pi-Po'))
    
    # (Infinite) loop:
    iIter = 0
    while(iIter<maxIter):
        try:
            # Read in all the lines until we find the checksum (line starting with an exclamation mark)
            if production:
                # Open serial port:
                try:
                    ser.open()
                    telegram = ''
                    checksum_found = False
                except Exception as ex:
                    template = "An exception of type {0} occured. Arguments:\n{1!r}"
                    message = template.format(type(ex).__name__, ex.args)
                    print(message)
                    sys.exit("Error when opening %s. Aborting." % ser.name)
            else:
                telegram = ''
                checksum_found = False
            
            while not checksum_found:
                # Read in a line:
                if debugging > 2: print("Reading a line...")
                telegram_line = ser.readline()
                if debugging > 1: print("Line read: ", telegram_line.decode('ascii').strip())
                
                # Check if it matches the checksum line (! at start)
                if re.match(b'(?=!)', telegram_line):
                    telegram = telegram + str(telegram_line)
                    if debugging > 0:  print('Found checksum!')
                    checksum_found = True
                else:
                    telegram = telegram + str(telegram_line)
        
        except Exception as ex:
            template = "An exception of type {0} occured. Arguments:\n{1!r}"
            message = template.format(type(ex).__name__, ex.args)
            print("There was a problem:  '%s', continuing..." % ex)
            
        # Close serial port:
        if production:
            try:
                ser.close()
            except Exception as ex:
                sys.exit("An error occurred when closing the serial port %s: '%s'.  Aborting." % (ser.name, str(ex)))
        
        
        # We have a complete telegram, now we can process it.
        # Look for the checksum in the telegram
        for m in pattern.finditer(telegram):
            # Remove the exclamation mark from the checksum,
            # and make an integer out of it.
            given_checksum = int('0x' + telegram[m.end() + 1:].decode('ascii'), 16)
            # The exclamation mark is also part of the text to be CRC16'd
            calculated_checksum = crc16(telegram[:m.end() + 1])
            if given_checksum == calculated_checksum:
                good_checksum = True
                
        good_checksum = True
        if(not good_checksum):
        # if(False):
            print("Checksum failed!")
            print("Given checksum:      ", given_checksum)
            print("Calculated checksum: ", calculated_checksum)
            
        else:
            if debugging >= 1: print("Good checksum !")
            
            # Store the values in a dictionary:
            telegram_values = dict()
            
            # Split the telegram into lines and iterate over them:
            for telegram_line in telegram.split("\\r\\n'b'"):
                # Split the OBIS code from the value
                # The lines with a OBIS code start with a number
                if re.match('\\d', telegram_line):
                    if debugging >= 3: print(telegram_line)
                    # The values are enclosed with parenthesis
                    # Find the location of the first opening parenthesis, and store all split lines
                    if debugging >= 2: print(telegram_line)
                    if debugging >= 3: print(re.split('(\\()', telegram_line))
                    # You can't put a list in a dict TODO better solution
                    code = ''.join(re.split('(\\()', telegram_line)[:1])
                    value = ''.join(re.split('(\\()', telegram_line)[1:])
                    telegram_values[code] = value
            
            
            # Print the lines to screen:
            # print(telegram_values)
            if(print_format == 'string' or print_format == 'code'):
                print()
                print(datetime.datetime.now())
            
            for code, value in sorted(telegram_values.items()):
                if code in list_of_interesting_codes:
                    value = clean_value(value)  # Cleanup value
                    
                    # Print nicely formatted string:
                    if print_format == 'string':
                        print_string = '{0:<'+str(max_len)+'}{1:>12}'
                        if debugging > 0: print(datetime.datetime.utcnow())
                        print(print_string.format(list_of_interesting_codes[code], value))
                    elif(print_format == 'code'):
                        print_string = '{0:<10}{1:>12}'
                        if debugging > 0: print(datetime.datetime.utcnow())
                        print(print_string.format(code, value))
                    
                else:
                    if(debugging > 2): print("Unknown code: %s." % code)
            
            
            if( (print_format == 'table') | ( (print_format == 'cron') & (iIter==0) ) ):
                # print()
                # print( "%10s,%9s, %10s,%10s,%10s,%10s, %5s,%5s" % ('Date','Time','Ein1','Ein2','Eout1','Eout2','Pin','Pout'))
                
                if(dailyLine):  # Print a sinle line with daily values
                    print( "%10s,%6s, %8s, %9.3f,%10.3f,%10.3f,%10.3f" % (
                        datetime.date.today().strftime('%Y,%m,%d'),
                        datetime.datetime.now().strftime('%H,%M'),
                        '253.851',
                        clean_value(telegram_values['1-0:1.8.1']),
                        clean_value(telegram_values['1-0:1.8.2']),
                        clean_value(telegram_values['1-0:2.8.1']),
                        clean_value(telegram_values['1-0:2.8.2'])
                    ) )
                    print()
                    exit()
                else:  # Print log line every 10s:
                    print( "%10s,%9s, %10.3f,%10.3f,%10.3f,%10.3f,%6i" % (
                        datetime.date.today(),
                        datetime.datetime.now().strftime('%H:%M:%S'),
                        clean_value(telegram_values['1-0:1.8.1']),
                        clean_value(telegram_values['1-0:1.8.2']),
                        clean_value(telegram_values['1-0:2.8.1']),
                        clean_value(telegram_values['1-0:2.8.2']),
                        (clean_value(telegram_values['1-0:1.7.0']) - clean_value(telegram_values['1-0:2.7.0']))*1000
                    ) )
                
            if( (print_format == 'power') | (print_format == 'cron') ):
                    print( "%8s,%6i" % (
                        datetime.datetime.now().strftime('%H:%M:%S'),
                        (clean_value(telegram_values['1-0:1.7.0']) - clean_value(telegram_values['1-0:2.7.0']))*1000
                    ), flush=True)
                
            # exit()
        iIter += 1
    # End of (infinite) loop
    
    
def clean_value(value):
    """Remove non-numbers from values.
    
    Note: Gas (in m3) needs another way to cleanup.
    """
    
    if 'm3' in value:
        (time,value) = re.findall('\\((.*?)\\)',value)
        value = float(value.lstrip('\\(').rstrip('\\)*m3'))
    else:
        value = float(value.lstrip('\\(').rstrip('\\)*kWhA'))
        
    return value


if(__name__ == "__main__"): main()
