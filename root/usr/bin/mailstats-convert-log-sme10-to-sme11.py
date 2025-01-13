import os
import re
from datetime import datetime, timedelta
import glob  # Import the glob module

def tai64n_to_datetime(tai64n):
    """Convert TAI64N formatted timestamp to a datetime object."""
    if len(tai64n) < 16:
        raise ValueError(f"Invalid TAI64N timestamp length: {tai64n}")

    high_bits = int(tai64n[:15], 16)
    low_bits = int(tai64n[15:23], 16)

    seconds_since_epoch = high_bits
    nanoseconds = low_bits
    
    # Create datetime object
    epoch = datetime(1970, 1, 1)
    dt = epoch + timedelta(seconds=seconds_since_epoch)
    dt += timedelta(microseconds=nanoseconds // 1000)

    return dt

def convert_log(file_paths, output_path):
	host_name = "sme11"
	total_files = 0
	total_lines = 0

	# Input file validation
	for file_path in file_paths:
		if not os.path.isfile(file_path):
			print(f"Input file {file_path} does not exist.")
			return
	with open(output_path, 'w') as output_file:
		for file_path in file_paths:
			print(f"{file_path}")
			# Determine the process name based on the file being read
			if "sqpsmtpd" in file_path:
				process_name = "sqpsmtpd-forkserver"
			else:
				process_name = "qpsmtpd-forkserver"
			
			with open(file_path, 'r', encoding='latin1') as log_file:
				total_files += 1
				try:
					for line in log_file:
						total_lines += 1
						match = re.match(r'@(\w+) (\d+) \((.*?)\) (.*)', line.strip())
						if match:
							tai64n_timestamp, pid, context, message = match.groups()
							try:
								log_time = tai64n_to_datetime(tai64n_timestamp[1:])  # Ignore '@'
								formatted_time = log_time.strftime('%b %d %H:%M:%S')
								
								# Replace "bjsystems.co.uk" with "thereadclan.me.uk" in the message
								#message = message.replace("bjsystems.co.uk", "thereadclan.me.uk")
								
								# Correctly format the output line
								formatted_line = f"{formatted_time} {host_name} {process_name}[{pid}]: {pid} ({context}) {message}\n"
								output_file.write(formatted_line)
							except Exception as e:
								with open("error_log.txt", 'a') as error_file:
									error_file.write(f"Could not convert timestamp {tai64n_timestamp}: {e}\n")
								print(f"Error logged for timestamp {tai64n_timestamp}.")
						else:
							#does not mathc the logterse line, but still needed
							match = re.match(r'@(\w+) (\d+) (.*)', line.strip())
							if match:
								tai64n_timestamp, pid, message = match.groups()
								try:
									log_time = tai64n_to_datetime(tai64n_timestamp[1:])  # Ignore '@'
									formatted_time = log_time.strftime('%b %d %H:%M:%S')
									# Replace "bjsystems.co.uk" with "thereadclan.me.uk" in the message
									#message = message.replace("bjsystems.co.uk", "thereadclan.me.uk")
									# Correctly format the output line
									formatted_line = f"{formatted_time} {host_name} {process_name}[{pid}]: {pid} {message}\n"
									output_file.write(formatted_line)
								except Exception as e:
									with open("error_log.txt", 'a') as error_file:
										error_file.write(f"Could not convert timestamp {tai64n_timestamp}: {e}\n")
									print(f"Error logged for timestamp {tai64n_timestamp}.")
				except Exception as e:
					print(f"Error reading file {file_path}: {e}")
					continue
	print(f"Processed {total_files} files and {total_lines} lines.")
# Specify the input and output file paths
# Use glob to expand file patterns
input_log_files = (
    glob.glob("/var/log/qpsmtpd/@*.s") +
    ["/var/log/qpsmtpd/current", "/var/log/sqpsmtpd/current"] +
    glob.glob("/var/log/sqpsmtpd/@*.s")  # Adjust the asterisk * as needed
)
output_log_file = "output_log.txt"  # Specify your desired output file path

# Convert the log
convert_log(input_log_files, output_log_file)
print(f"Log conversion complete. Check the output at: {output_log_file}")