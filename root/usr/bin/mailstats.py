#
# Mailstats.py
#
#
# This script provides daily SpamFilter statistics.
#
# Mailstats
#
#		usage: mailstats.py [-h] [-d DATE] [-ef EMAILFILE] [-tf TEXTFILE] [--version]
#							[-db DBSAVE]
#
#		Mailstats
#
#		optional arguments:
#		  -h, --help            show this help message and exit
#		  -d DATE, --date DATE  Specify a valid date (yyyy-mm-dd) for the analysis
#		  -ef EMAILFILE, --emailfile EMAILFILE
#								Save an html file of the email sent (y/N)
#		  -tf TEXTFILE, --textfile TEXTFILE
#								Save a txt file of the html page (y/N)
#		  --version             show program's version number and exit
#		  -db DBSAVE, --dbsave DBSAVE
#								Force save of summary logs in DB (y/N)
#
#
# (June 2024 - bjr) Re-written in Python from Mailstats.pl (Perl) to conform to SME11 / Postfix / qpsmtpd log formats
# and html output added
#
# Todo:
# 2  Other stats
# 3. Extra bits for sub tables - DONE
# 4. Percent char causes sort to fail - look at adding it in the template - DONE
# 5. Chase disparity in counts betweeen old mailstats and this - Some of it DONE
# 6. Count emails delivered over ports 25/587/465 (SMTPS?)
# 7. Arrange that the spec file overwrites the date even if it has been overwritten before
# 8. Allow mailstats pages to be public or private  (=> templating the fragment)) - DONE
# 9. Update format of the summarylogs page - DONE but still WIP
# 10. Add in links to summarylogs in web pages - DONE but still WIP
# 11. Move showSummaryLogs.php to individual directory "/opt/mailstats/php"
# 12. Make sure other directories not visible through apache 
# 
# Future:
# 1. Write summary line for each transaction to DB and link to it through cell in main table -DONE (write to DB))
# 2. Make DB password something more obscure.
# 3. Prune the DB according to parameter - delete corresponding page in opt/mailstats/html
# 4. Prune the html directory according to parameter
# 
# Even more Future (if ever))
# 2. Link each summary line through DB to actual transaction lines
#
# Centos7:
# yum install python3-chameleon --enablerepo=epel
# yum install html2text --enablerepo=epel
# yum install mysql-connector-python --enablerepo=epel (not sure if this is required as well the pip3))
# pip3 install mysql-connector
# pip3 install numpy
# pip3 install plotly
# pip3 install pandas
# NOTE: No matplotlib
#
# Rocky8: (probably - not yet checked this)
#
# dnf install python3-chameleon --enablerepo=epel
# dnf install html2text --enablerepo=epel
# dnf install python3-matplotlib
# pip3 install numpy
# pip3 pymysql
# pip3 install pandas
#
#
from datetime import datetime, timedelta
import sys
from chameleon import PageTemplateFile,PageTemplate
import pkg_resources
import re
import ipaddress
import subprocess
import os
from collections import defaultdict
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import codecs
import argparse
import tempfile
#import mysql.connector
import numpy as np
import plotly.graph_objects as go
import plotly.express as px
import colorsys
import pymysql
import json
from systemd import journal
import logging

# Configure logging
log_dir_path = "/var/log/mailstats"
# Check if the directory exists, and create it if it doesn't
if not os.path.exists(log_dir_path):
    os.makedirs(log_dir_path)
logging.basicConfig(level=logging.INFO,  # Default level of messages to log
                    format='%(asctime)s - %(levelname)s - %(message)s',
                    handlers=[
                        logging.StreamHandler(),  # Log to console
                        logging.FileHandler(log_dir_path+"/mailstats.log")  # Log to a file
                    ])
enable_graphs = True; #This could be a DB entry if required.
try:
	import matplotlib.pyplot as plt
except ImportError:
	logging.debug("Matplotlib is not installed  - no graphs")
	enable_graphs = False;

Mailstats_version = '1.2'
build_date_time = "2024-06-18 12:03:40OURCE" 
build_date_time = build_date_time[:19]  #Take out crap that sneaks in.

#if build_date_time == "2024-06-18 12:03:40OURCE":
#    build_date_time = "Unknown"

script_dir = os.path.dirname(os.path.abspath(__file__))
data_file_path = script_dir+'/../..'    #back to the top
now = datetime.now()
yesterday = now - timedelta(days=1)
formatted_yesterday = yesterday.strftime("%Y-%m-%d")
#html_page_path = data_file_path+"/home/e-smith/files/ibays/mesdb/html/mailstats/"
html_page_dir = data_file_path+"/opt/mailstats/html/"
template_dir = data_file_path+"/opt/mailstats/templates/"
logs_dir = data_file_path+"/opt/mailstats/logs/"

# Column numbering (easy to renumber or add one in)
Hour = 0
WebMail = Hour + 1
Local = WebMail + 1
MailMan = Local + 1
Relay = MailMan + 1
DMARC = Relay + 1
Virus = DMARC + 1
RBLDNS = Virus + 1
Geoip = RBLDNS + 1
NonConf = Geoip + 1
RejLoad = NonConf + 1
Karma = RejLoad + 1
DelSpam = Karma + 1
QuedSpam = DelSpam + 1
Ham = QuedSpam + 1
TOTALS = Ham + 1
PERCENT = TOTALS + 1

ColTotals = 24
ColPercent = 25

def replace_bracket_content(input_filename, output_filename):
    import re

    with open(input_filename, 'r', encoding='utf-8') as infile:
        content = infile.read()

    # Pattern to capture digits/spaces inside brackets
    pattern = r'\[([\d\s]*)\]\(\./showSummaryLogs\.php\?date=\d{4}-\d{2}-\d{2}&hour=\d{1,2}\)'
    
    # Pad captured group to 10 characters
    replaced_content = re.sub(pattern, lambda m: f"{m.group(1):8}", content)

    with open(output_filename, 'w', encoding='utf-8') as outfile:
        outfile.write(replaced_content)

    return f"Replacements completed. Output written to {output_filename}"


def get_logs_from_Journalctl(date='yesterday'):
	# JSON-pretty output example from journalctl
	# {
	# "__CURSOR" : "s=21b4f015be0c4f1fb71ac439a8365ee7;i=385c;b=dd778625547f4883b572daf53ae93cd4;m=ca99d6d;t=62d6316802b05;x=71b24e9f19f3b99a",
	# "__REALTIME_TIMESTAMP" : "1738753462774533",
	# "__MONOTONIC_TIMESTAMP" : "212442477",
	# "_BOOT_ID" : "dd778625547f4883b572daf53ae93cd4",
	# "_MACHINE_ID" : "f20b7edad71a44e59f9e9b68d4870b19",
	# "PRIORITY" : "6",
	# "SYSLOG_FACILITY" : "3",
	# "_UID" : "0",
	# "_GID" : "0",
	# "_SYSTEMD_SLICE" : "system.slice",
	# "_CAP_EFFECTIVE" : "1ffffffffff",
	# "_TRANSPORT" : "stdout",
	# "_COMM" : "openssl",
	# "_EXE" : "/usr/bin/openssl",
	# "_HOSTNAME" : "sme11.thereadclan.me.uk",
	# "_STREAM_ID" : "8bb0ef8920af4ae09b424a2e30abcdf7",
	# "SYSLOG_IDENTIFIER" : "qpsmtpd-init",
	# "MESSAGE" : "Generating DH parameters, 2048 bit long safe prime, generator 2",
	# "_PID" : "2850",
	# }
	# and the return from here:
	# {
		# '_TRANSPORT': 'stdout', 'PRIORITY': 6, 'SYSLOG_FACILITY': 3, '_CAP_EFFECTIVE': '0', '_SYSTEMD_SLICE': 'system.slice',
		# '_BOOT_ID': UUID('465c6202-36ac-4a8b-98e9-1581e8fec68f'), '_MACHINE_ID': UUID('f20b7eda-d71a-44e5-9f9e-9b68d4870b19'),
		# '_HOSTNAME': 'sme11.thereadclan.me.uk', '_STREAM_ID': '06c860deea374544a2b561f55394d728', 'SYSLOG_IDENTIFIER': 'qpsmtpd-forkserver',
		# '_UID': 453, '_GID': 453, '_COMM': 'qpsmtpd-forkser', '_EXE': '/usr/bin/perl',
		# '_CMDLINE': '/usr/bin/perl -Tw /usr/bin/qpsmtpd-forkserver -u qpsmtpd -l 0.0.0.0 -p 25 -c 40 -m 5',
		# '_SYSTEMD_CGROUP': '/system.slice/qpsmtpd.service', '_SYSTEMD_UNIT': 'qpsmtpd.service',
		# '_SYSTEMD_INVOCATION_ID': 'a2b7889a307748daaeb60173d31c5e0f', '_PID': 93647,
		# 'MESSAGE': '93647 Connection from localhost [127.0.0.1]',
		# '__REALTIME_TIMESTAMP': datetime.datetime(2025, 4, 2, 0, 1, 11, 668929),
		# '__MONOTONIC_TIMESTAMP': journal.Monotonic(timestamp=datetime.timedelta(11, 53118, 613602),
		# bootid=UUID('465c6202-36ac-4a8b-98e9-1581e8fec68f')),
		# '__CURSOR': 's=21b4f015be0c4f1fb71ac439a8365ee7;i=66d2c;b=465c620236ac4a8b98e91581e8fec68f;m=e9a65ed862;t=
	# }
	"""
	Retrieve and parse journalctl logs for a specific date and units,
	returning them as a sorted list of dictionaries.
	"""
	try:
		# Parse the input date to calculate the start and end of the day
		if date.lower() == "yesterday":
			target_date = datetime.now() - timedelta(days=1)
		else:
			target_date = datetime.strptime(date, "%Y-%m-%d")
		
		# Define the time range for the specified date
		since = target_date.strftime("%Y-%m-%d 00:00:00")
		until = target_date.strftime("%Y-%m-%d 23:59:59")
		
		# Convert times to microseconds for querying
		since_microseconds = int(datetime.strptime(since, "%Y-%m-%d %H:%M:%S").timestamp() * 1_000_000)
		until_microseconds = int(datetime.strptime(until, "%Y-%m-%d %H:%M:%S").timestamp() * 1_000_000)
		
		# Open the systemd journal
		j = journal.Reader()
		
		# Set filters for units
		j.add_match(_SYSTEMD_UNIT="qpsmtpd.service")
		j.add_match(_SYSTEMD_UNIT="uqpsmtpd.service")
		j.add_match(_SYSTEMD_UNIT="sqpsmtpd.service")
		
		# Filter by time range
		j.seek_realtime(since_microseconds // 1_000_000)  # Convert back to seconds for seeking
		
		# Retrieve logs within the time range
		logs = []
		for entry in j:
			entry_timestamp = entry.get('__REALTIME_TIMESTAMP', None)
			entry_microseconds = int(entry_timestamp.timestamp() * 1_000_000)
			if entry_timestamp and since_microseconds <= entry_microseconds <= until_microseconds:
				logs.append(entry)
		
		# Sort logs by __REALTIME_TIMESTAMP in ascending order
		sorted_logs = sorted(logs, key=lambda x: x.get("__REALTIME_TIMESTAMP", 0))
		
		return sorted_logs

	except Exception as e:
		logging.error(f"Unexpected error: {e}")
		return {}


def transform_to_dict(data, keys, iso_date):
    """
    Transforms a 26x17 list of lists into a list of dictionaries with specified keys.

    Args:
        data (list): A 26x17 list of lists.
        keys (list): A 1D array specifying the keys for the dictionaries.
        iso_date (str): A date in ISO format to prepend to each row number.

    Returns:get_JSOON
        list: A list of dictionaries with transformed data.
    """
    # Validate input dimensions
    if len(data) != 26:
        raise ValueError("Input data must have 26 rows.")
    if len(keys) != len(data[0]):  # Account for the new column
        raise ValueError(f"Keys must match the number of columns after transformation {len(keys)} {len(data[0])}")
    
    # Remove rows 25 and 26
    filtered_data = data[:24]
    
    # and same for keys
    modified_keys = keys[1:-2]

    # Add new column with ISO date and row number
    transformed_data = []
    for i, row in enumerate(filtered_data):
        new_column_value = f"{i}"  #f"{iso_date},{i}"
        transformed_row = [new_column_value] + row[1:-2]  # Remove first and last two columns
        transformed_data.append(transformed_row)

    # Convert each row into a dictionary using supplied keys
    result = [dict(zip(["Time"] + modified_keys, row)) for row in transformed_data]

    return result


def create_graph(data_dict, graph_type="line", output_file="graph.png",iso_date='1970-01-01'):
	"""
	Creates a graph from nested list data with hours as x-axis.

	Args:
		data_dict (list): List structure where:
			- Each element is a list representing hour data
			- First element is the hour (0-23)
			- Remaining elements are counts for different types/categories
		graph_type (str): Type of graph to create ("line", "bar", "scatter", "pie").
		output_file (str): Path to save the image file.
	"""
	# Check if data is empty
	if not data_dict:
		raise ValueError("Input data cannot be empty")

	# Extract hours (from the "NewColumn" key)
	hours = [row["Time"] for row in data_dict]  # First column is the ISO date + row number

	# Extract types (keys excluding "NewColumn")
	types = [key for key in data_dict[0].keys() if key != "Time"]  # Dynamically get keys except "NewColumn"

	# Extract counts for each type
	counts = {typ: [row[typ] for row in data_dict] for typ in types}

	plt.figure(figsize=(10, 6))  # Create a figure

	# Generate different types of graphs based on the input parameter
	if graph_type == "line":
		for typ in types:
			plt.plot(hours, counts[typ], label=typ, marker='o')
		plt.title(f"Line Graph for {iso_date}")
		plt.xlabel("Hours")
		plt.ylabel("Counts")

	elif graph_type == "bar":
		bottom = [0] * len(hours)
		for typ in types:
			plt.bar(hours, counts[typ], bottom=bottom, label=typ)
			bottom = [b + y for b, y in zip(bottom, counts[typ])]
		plt.title(f"Bar Graph for {iso_date}")
		plt.xlabel("Hours")
		plt.ylabel("Counts")

	elif graph_type == "scatter":
		for typ in types:
			plt.scatter(hours, counts[typ], label=typ)
		plt.title(f"Scatter Plot for {iso_date}")
		plt.xlabel("Hours")
		plt.ylabel("Counts")

	elif graph_type == "pie":
		total_counts = {typ: sum(counts[typ]) for typ in types}
		total_sum = sum(total_counts.values())
		threshold_percent = 0.01 * total_sum

		# Separate filtered counts and "Other" counts
		filtered_counts = {}
		other_total = 0

		for typ, value in total_counts.items():
			if value > 0 and value >= threshold_percent:
				filtered_counts[typ] = value
			else:
				other_total += value

		# Add "Other" category if there are values below the threshold
		if other_total > 0:
			filtered_counts["Other"] = other_total

		# Prepare data for the pie chart
		labels = filtered_counts.keys()
		sizes = filtered_counts.values()

		# Plot the pie chart
		plt.pie(sizes, labels=labels, autopct='%1.1f%%', startangle=90)
		plt.title(f"Pie Chart for {iso_date}")

	else:
		raise ValueError(f"Unsupported graph type: {graph_type}")

	if graph_type != "pie":
		plt.xticks(hours)
		plt.grid(alpha=0.3)
		plt.legend()

	# Save the graph to a file
	plt.tight_layout()
	plt.savefig(output_file)
	plt.close()

# def convert_to_numeric(data):
    # """
    # Converts all values in a nested list or dictionary to numeric types (int or float).
    # """
    # for i in range(len(data)):
        # for j in range(1, len(data[i])):  # Skip the first column (hour)
            # try:
                # data[i][j] = float(data[i][j])  # Convert to float
            # except ValueError:
                # raise ValueError(f"Non-numeric value found: {data[i][j]}")
    # return data

def save_summaries_to_db(cursor, conn, date_str, hour, parsed_data):
    # Convert parsed_data to JSON string
    global count_records_to_db
    json_data = json.dumps(parsed_data)

    # Insert the record
    insert_query = """
    INSERT INTO SummaryLogs (Date, Hour, logData)
    VALUES (%s, %s, %s)
    """
   
    try:
        cursor.execute(insert_query, (date_str, hour, json_data))
        conn.commit()
        count_records_to_db += 1
    except pymysql.Error as err:
        logging.error(f"DB Error {date_str} {hour} : {err}")
        conn.rollback()
                
def is_running_under_thonny():
    # Check for the 'THONNY_USER_DIR' environment variable
    return 'THONNY_USER_DIR' in os.environ

# Routines to access the E-Smith dbs
def parse_entity_line(line):
	"""
	Parses a single line of key-value pairs.

	:param line: Single line string to be parsed
	:return: Dictionary with keys and values
	"""
	parts = line.split('|')
	# First part contains the entity name and type in the format 'entity_name=type'
	entity_part = parts.pop(0)
	entity_name, entity_type = entity_part.split('=')
	
	entity_dict = {'type': entity_type}
	
	for i in range(0, len(parts)-1, 2):
		key = parts[i]
		value = parts[i+1]
		entity_dict[key] = value
	
	return entity_name, entity_dict

def parse_config(config_string):
    """
    Parses a multi-line configuration string where each line is an entity with key-value pairs.

    :param config_string: Multi-line string to be parsed
    :return: Dictionary of dictionaries with entity names as keys
    """
    config_dict = {}

    lines = config_string.strip().split('\n')
    for line in lines:
        line = line.strip()
        if line.startswith('#'):  # Skip lines that start with '#'
            continue
        entity_name, entity_dict = parse_entity_line(line)
        config_dict[entity_name] = entity_dict

    return config_dict
	
def read_config_file(file_path):
	"""
	Reads a configuration file and parses its contents.

	:param file_path: Path to the configuration file
	:return: Parsed configuration dictionary
	"""
	with open(file_path, 'r') as file:
		config_string = file.read()

	return parse_config(config_string)

def get_value(config_dict, entity, key, default=None):
    """
    Retrieves the value corresponding to the given key from a specific entity.

    :param config_dict: Dictionary of dictionaries with parsed config
    :param entity: Entity from which to retrieve the key's value
    :param key: Key whose value needs to be retrieved
    :param default: Default value to return if the entity or key does not exist
    :return: Value corresponding to the key, or the default value if the entity or key does not exist
    """
    return config_dict.get(entity, {}).get(key, default)


def is_private_ip(ip):
	try:
		# Convert string to an IPv4Address object
		ip_addr = ipaddress.ip_address(ip)
	except ValueError:
		return False
	# Define private IP ranges
	private_ranges = [
		ipaddress.ip_network('10.0.0.0/8'),
		ipaddress.ip_network('172.16.0.0/12'),
		ipaddress.ip_network('192.168.0.0/16'),
	]
	# Check if the IP address is within any of these ranges
	for private_range in private_ranges:
		if ip_addr in private_range:
			return True

	return False

def truncate_microseconds(timestamp):
	# Split timestamp into main part and microseconds
	try:
		main_part, microseconds = timestamp.split('.')
		# Truncate the last three digits of the microseconds
		truncated_microseconds = microseconds[:-3]
		# Combine the main part and truncated microseconds
		truncated_timestamp = f"{main_part}.{truncated_microseconds}"
	except Exception as e:
		logging.error(f"{e} {timestamp}")
		raise ValueError
	# Remove the microseconds completely if they exist
	return truncated_timestamp.split('.')[0]

def read_in_relevant_log_file(file_path,analysis_date=yesterday):
	# Read the file and split each line into a list - timestamp and the rest
	log_entries = []
	skip_record_count = 0
	ignore_record_count = 0
	# Get the year of yesterday
	yesterday = datetime.now() - timedelta(days=1)
	yesterday_year = yesterday.year
	line_count = 0;

	with codecs.open(file_path, 'rb','utf-8', errors='replace') as file:
		try:
			for Line in file:
				line_count += 1
				#extract time stamp
				try:
					entry = split_timestamp_and_data(Line)
					# compare with anal date
					timestamp_str = entry[0]; #truncate_microseconds(entry[0])
				except ValueError as e:
					logging.error(f"ValueError {e} on timestamp create {timestamp_str}:{entry[0]} {entry[1]}")
					skip_record_count += 1
					continue
				# Parse the timestamp string into a datetime object
				# Ignoring extra microseconds 
				try:
					timestamp = datetime.strptime(timestamp_str, "%b %d %H:%M:%S")
					# and add in gthe year of yesterday
					timestamp = timestamp.replace(year=yesterday_year)
				except (ValueError, TypeError) as e:
					logging.error(f"Error {e} line {line_count} on timestamp extract {timestamp_str}:{entry[1]}")
					ignore_record_count += 1
					continue
				if timestamp.date() == analysis_date.date():
					log_entries.append((timestamp, entry[1]))
				else:
					ignore_record_count += 1
		except UnicodeDecodeError as e:
			pass
	return [log_entries,skip_record_count,ignore_record_count]
	
def filter_summary_records(log_entries):
	# Return just the summary records
	filtered_log_entries = []
	skipped_entry_count = 0
	for line in log_entries:
		if '`' in line['MESSAGE']:
			filtered_log_entries.append(line)
		else:
			skipped_entry_count += 1
	return [filtered_log_entries,skipped_entry_count]
	
def sort_log_entries(log_entries):
	# Sort the records, based on the timestamp
	sorted_entries = sorted(log_entries, key=lambda x: x['__REALTIME_TIMESTAMP'])
	# and return a dictionary
	sorted_dict = {entry['__REALTIME_TIMESTAMP']: entry['MESSAGE'] for entry in sorted_entries}
	return sorted_dict
	
def parse_data(data):
	# Split data string into parts and map to named fields.
	# Adjust the field names and parsing logic according to your data format.
	# Split at the backtick - before it fields split at space, after, fields split at tab
	parts = data.split('`')
	fields0 = ["",""] #Add in dummy to make it the same as before, saves changing all the numbers below.
	fields1 = parts[0].strip().split() if len(parts) > 0 else []
	fields2 = parts[1].split('\t') if len(parts) > 1 else []
	# then merge them
	fields = fields0 + fields1 + fields2
	# and mapping:
	try:
		return_dict = {
			'sme': fields[0].strip() if len(fields) > 0 else None,
			'qpsmtpd': fields[1].strip() if len(fields) > 1 else None,
			'id': fields[2].strip() if len(fields) > 2 else None,
			'action': fields[3].strip() if len(fields) > 3 else None,       #5
			'logterse': fields[4].strip() if len(fields) > 4 else None,
			'ip': fields[5].strip() if len(fields) > 5 else None,
			'sendurl': fields[6].strip() if len(fields) > 6 else None,     #1
			'sendurl1': fields[7].strip() if len(fields) > 7 else None,    #2
			'from-email': fields[8].strip() if len(fields) > 8 else None,  #3
			'error-reason': fields[8].strip() if len(fields) > 9 else None, #3
			'to-email': fields[9].strip() if len(fields) > 9 else None,		#4
			'error-plugin': fields[10].strip() if len(fields) > 10 else None,  #5
			'action1': fields[10].strip() if len(fields) > 10 else None,       #5
			'error-number' : fields[11].strip() if len(fields) > 11 else None, #6
			'sender': fields[12].strip() if len(fields) > 12 else None,      #7
			'virus': fields[12].strip() if len(fields) > 12 else None,      #7
			'error-msg' :fields[13].strip() if len(fields) > 13 else None,   #7
			'spam-status': fields[13].strip() if len(fields) > 13 else None, #8 
			'error-result': fields[14].strip() if len(fields) > 14 else None,#8
			# Add more fields as necessary
		}
	except:
		logging.error(f"error:len:{len(fields)}")
		return_dict = {}  
	return return_dict

# def count_entries_by_hour(log_entries):
	# hourly_counts = defaultdict(int)
	# for entry in log_entries:
		# # Extract hour from the timestamp
		# timestamp = entry['timestamp']
		# hour = datetime.datetime.strptime(timestamp, '%Y-%m-%d %H:%M:%S').strftime('%Y-%m-%d %H')
		# hourly_counts[hour] += 1
	# return hourly_counts

def initialize_2d_array(num_hours, column_headers_len,reporting_date):
	num_hours += 1  # Adjust for the zeroth hour
	# Initialize the 2D list with zeroes
	return [[0] * column_headers_len for _ in range(num_hours)]

def search_2d_list(target, data):
	"""
	Search for a target string in a 2D list of variable-length lists of strings.

	:param target: str, the string to search for
	:param data: list of lists of str, the 2D list to search
	:return: int, the row number where the target string is found, or -1 if not found
	"""
	for row_idx, row in enumerate(data):
		if target in row:
			return row_idx
	return -1  # Return -1 if not found
	
def check_html2text_installed():
	try:
		# Check if html2text is installed by running 'which html2text'
		result = subprocess.run(
			['which', 'html2text'],
			check=True,
			stdout=subprocess.PIPE,
			stderr=subprocess.PIPE
		)

		# If the command finds html2text, it will output the path
		html2text_path = result.stdout.decode('utf-8').strip()
		
		if not html2text_path:
			raise FileNotFoundError
		
		logging.debug(f"html2text is installed at: {html2text_path}")
		return True

	except subprocess.CalledProcessError:
		logging.error("html2text is not installed. Please install it using your package manager.", file=sys.stderr)
		return False    

def html_to_text(input_file, output_file):
	if not check_html2text_installed():
		sys.exit(1)
	try:
		# Run the html2text command with -b0 --pad-tables parameters
		result = subprocess.run(
			['html2text', '-b0', '--pad-tables', input_file],
			check=True,  # Raise a CalledProcessError on non-zero exit
			stdout=subprocess.PIPE,  # Capture stdout
			stderr=subprocess.PIPE   # Capture stderr
		)

		# Write the stdout from the command to the output file
		with open(output_file, 'w', encoding='utf-8') as outfile:
			outfile.write(result.stdout.decode('utf-8'))

		logging.debug(f"Converted {input_file} to {output_file}")
	except subprocess.CalledProcessError as e:
		logging.error(f"Error occurred: {e.stderr.decode('utf-8')}", file=sys.stderr)
		sys.exit(e.returncode)

def get_html2text_version():
	try:
		result = subprocess.run(['html2text', '--version'], stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True)
		# Ensure the result is treated as a string in Python 3.6+
		return result.stdout.strip()
	except subprocess.CalledProcessError as e:
		logging.error(f"Error occurred while checking html2text version: {e}", file=sys.stderr)
		return None
 
def print_progress_bar(iteration, total, prefix='', suffix='', decimals=1, length=50, fill='█', print_end="\r"):
	"""
	Call in a loop to create a terminal progress bar
	@params:
		iteration   - Required : current iteration (Int)
		total       - Required : total iterations (Int)
		prefix      - Optional : prefix string (Str)
		suffix      - Optional : suffix string (Str)
		decimals    - Optional : positive number of decimals in percent complete (Int)
		length      - Optional : character length of bar (Int)
		fill        - Optional : bar fill character (Str)
		logging.error(_end   - Optional : end character (e.g. "\r", "\r\n") (Str)
	"""
	if total == 0:
		raise ValueError("Progress total is zero")
	percent = ("{0:." + str(decimals) + "f}").format(100 * (iteration / float(total)))
	filled_length = int(length * iteration // total)
	bar = fill * filled_length + '-' * (length - filled_length)
	print(f'\r{prefix} |{bar}| {percent}% {suffix}', end=print_end)
	# logging.error( New Line on Complete
	if iteration == total:
		print()
 
def insert_string_after(original:str, to_insert:str, after:str) -> str:
	"""
	Insert to_insert into original after the first occurrence of after.
	
	:param original: The original string.
	:param to_insert: The string to be inserted.
	:param after: The set of characters after which the string will be inserted.
	:return: The new string with to_insert inserted after after.
	"""
	position = original.find(after)
	if position == -1:
		logging.error(f"insert_string_after:({after}) string is not found in original")
		return original
	# Position of the insertion point
	insert_pos = position + len(after)
	
	return original[:insert_pos] + to_insert + original[insert_pos:]
	
def split_timestamp_and_data(log_entry: str) -> list:
	"""
	Split a log entry into timestamp and the rest of the data.
	
	:param log_entry: The log entry as a string.
	:return: A list with two entries: [timestamp, rest_of_data].
	"""
	# The timestamp is always the first part, up to the first space after the milliseconds
	# SME11 - the timestamp looks like this: "Dec 29 07:42:00 sme11 qpsmtpd-forkserver[942177]:<the rest>"
	#
	match = re.match(r'(\w{3} \d{1,2} \d{2}:\d{2}:\d{2}) (.+)', log_entry)
	if match:
		timestamp = match.group(1)
		rest_of_line = match.group(2).strip()  # Strip any leading spaces
	else:
		timestamp = None
		rest_of_line = log_entry  # If no match, return the whole line
	return [timestamp, rest_of_line]
	
def render_sub_table(table_title, table_headers, found_values, get_character=None, suppress_threshold=False):
	#Check if any data provided
	if len(found_values) != 0:
		# Get the total
		original_total = 0  # Initialize total variable
		if isinstance(found_values, dict):
			# If found_values is a dictionary, we operate as previously
			total_sum = sum(found_values.values())
			original_total = total_sum
			if not BadCountries:
				get_character = None
			if get_character:
				sub_result = [(key, value,
							   f"{round(value / total_sum * 100, 2)}%",
							   f"{get_character(key)}") for key, value in found_values.items()]
			else:
				sub_result = [(key, value,
							   f"{round(value / total_sum * 100, 2)}%" ) for key, value in found_values.items()]
		elif isinstance(found_values, list):
			# If found_values is a list of values
			if all(isinstance(v, (int, float)) for v in found_values):
				total_sum = sum(found_values)
				original_total = total_sum
				sub_result = [(i, value,
							   f"{round(value / total_sum * 100, 2)}%") for i, value in enumerate(found_values)]
			# If found_values is a list of dictionaries
			elif all(isinstance(v, dict) for v in found_values):
				# Example assumes first key is used for identification and others are numeric
				# Convert to 2D array
				sub_result = [list(entry.values()) for entry in found_values]

				# Calculate the total of the first numeric entry (index 1)
				total = sum(row[1] for row in sub_result)
				original_total = total

				# Append percentage of the total for each entry
				for row in sub_result:
					percentage = f"{round(row[1] / total * 100, 2) if total else 0}%"  # Handle division by zero
					row.append(percentage)
					
			else:
				raise ValueError("found_values must be either a list of numbers or a list of dictionaries.")
		else:
			raise TypeError("found_values must be a dictionary or a list.")
		sub_result.sort(key=lambda x: float(x[1]), reverse=True)  # Sort by percentage in descending order

		# Dynamic threshold calculation
		if not suppress_threshold:
			dynamic_threshold = max(1, 100 / (original_total**0.5)) if original_total > 0 else 0
			dynamic_threshold = round(dynamic_threshold,1)
			logging.debug(f"Threshold for {table_title} set to {dynamic_threshold}% ")
		else:
			dynamic_threshold=0
		absolute_floor = 50  # Minimum absolute value threshold

		# Filter results using early termination
		filtered_sub_result = []
		for row in sub_result:
			value = row[1]
			percentage = (value / original_total * 100) if original_total else 0
			
			# Exit condition: below both thresholds
			if percentage < dynamic_threshold and value < absolute_floor:
				break
				
			filtered_sub_result.append(row)
		
		sub_result = filtered_sub_result  # Keep only significant rows

		sub_template_path = template_dir+'mailstats-sub-table.html.pt'
		# Load the template
		with open(sub_template_path, 'r') as template_file:
			template_content = template_file.read()
		# Create a Chameleon template instance
		try:
			template = PageTemplate(template_content)
			# Render the template with the 2D array data and column headers
			try:
				rendered_html = template(array_2d=sub_result, column_headers=table_headers, 
										title=table_title, classname=get_first_word(table_title),
										threshold=dynamic_threshold)
			except Exception as e:
				raise ValueError(f"{table_title}: A chameleon controller render error occurred: {e}")
		except Exception as e:
			raise ValueError(f"{table_title}: A chameleon controller template error occurred: {e}")
	else:
		rendered_html = f"<div class='{get_first_word(table_title)}'><h2>{table_title}</h2>No data for {table_title}</div>"
	return rendered_html
	

def get_character_in_reject_list(code):
	if code in BadCountries:
		return "*"
	else:
		return ""
	
def get_first_word(text):
    return text.split(None, 1)[0]
        
def read_html_from_file(filepath):
	"""
	Reads HTML content from a given file.

	Args:
		filepath (str): Path to the HTML file.
	
	Returns:
		str: HTML content of the file.
	"""
	# Need to add in here the contents of the css file at the end of the head section.
	with open(filepath, 'r', encoding='utf-8') as file:
		html_contents = file.read()
	logging.debug("Reading from html file")
	# Get Filepath
	css_path = os.path.dirname(filepath)+"/../css/mailstats.css"
	# Read in CSS 
	with open(css_path, 'r', encoding='utf-8') as file:
		css_contents = file.read()
	html_contents = insert_string_after(html_contents,"\n<style>"+css_contents+"</style>","<!--css here-->")
	return html_contents
	
def read_text_from_file(filepath):
	"""
	Reads plain text content from a given file.

	Args:
		filepath (str): Path to the text file.
	
	Returns:
		str: Text content of the file.
	"""
	try:
		with open(filepath, 'r', encoding='utf-8') as file:
			return file.read()
	except:
		logging.error(f"{filepath} not found")
		return

def send_email(subject, from_email, to_email, smtp_server, smtp_port, HTML_content=None, Text_content=None, smtp_user=None, smtp_password=None):
	"""
	Sends an HTML email.

	Args:
		html_content (str): The HTML content to send in the email.
		subject (str): The subject of the email.
		from_email (str): The sender's email address.
		to_email (str): The recipient's email address.
		smtp_server (str): SMTP server address.
		smtp_port (int): SMTP server port.
		smtp_user (str, optional): SMTP server username. Default is None.
		smtp_password (str, optional): SMTP server password. Default is None.
	"""
	#Example (which works!)
			# send_email(
			# subject="Your subject",
			# from_email="mailstats@bjsystems.co.uk", 
			# to_email="brianr@bjsystems.co.uk", 
			# smtp_server="mail.bjsystems.co.uk", 
			# smtp_port=25
			# HTML_content=html_content, 
			# Text_content=Text_content, 
		# )

	# Set up the email
	msg = MIMEMultipart('alternative')
	msg['Subject'] = subject
	msg['From'] = from_email
	msg['To'] = to_email
	
	if HTML_content:
		part = MIMEText(HTML_content, 'html')
		msg.attach(part)
	if Text_content:
		part = MIMEText(Text_content, 'plain')
		msg.attach(part)

	# Sending the email
	with smtplib.SMTP(smtp_server, smtp_port) as server:
		server.starttls()  # Upgrade the connection to secure
		if smtp_user and smtp_password:
			server.login(smtp_user, smtp_password)  # Authenticate only if credentials are provided
		server.sendmail(from_email, to_email, msg.as_string())
 
def replace_between(text, start, end, replacement):
    # Escaping start and end in case they contain special regex characters
    pattern = re.escape(start) + '.*?' + re.escape(end)
    # Using re.DOTALL to match any character including newline
    replaced_text = re.sub(pattern, replacement, text, flags=re.DOTALL)
    return replaced_text
    
def get_heading():
	#
	# Needs from anaytsis
		# SATagLevel - done
		# SARejectLevel - done
		# warnnoreject - done
		# totalexamined - done
		# emailperhour - done
		# spamavg  - done
		# rejectspamavg - done
		# hamavg - done
		# DMARCSendCount - done
		# hamcount - done
		# DMARCOkCount - deone

	# Clam Version/DB Count/Last DB update
	clam_output = subprocess.getoutput("freshclam -V")
	clam_info = f"Clam Version/DB Count/Last DB update: {clam_output}"

	# SpamAssassin Version
	sa_output = subprocess.getoutput("spamassassin -V")
	sa_info = f"SpamAssassin Version: {sa_output}"

	# Tag level and Reject level
	tag_reject_info = f"Tag level: {SATagLevel}; Reject level: {SARejectLevel} {warnnoreject}"

	# SMTP connection stats
	smtp_stats = f"External SMTP connections accepted: {totalexternalsmtpsessions}\n"\
				 f"Internal SMTP connections accepted: {totalinternalsmtpsessions}"

	if len(connection_type_counts)>0:
		for connection_type in connection_type_counts.keys():
			smtp_stats += f"\nCount of {connection_type} connections: {connection_type_counts[connection_type]}"

	if len(total_ports)>0:
		for port_number in total_ports.keys():
			smtp_stats += f"\nCount of port {port_number} connections: {total_ports[port_number]}"

	smtp_stats = smtp_stats + f"\nEmails per hour: {emailperhour:.1f}/hr\n"\
				 f"Average spam score (accepted): {spamavg or 0:.2f}\n"\
				 f"Average spam score (rejected): {rejectspamavg or 0:.2f}\n"\
				 f"Average ham score: {hamavg or 0:.2f}\n"\
				 f"Number of DMARC reporting emails sent: {DMARCSendCount or 0} (not shown on table)"

	# DMARC approved emails
	dmarc_info = ""
	if hamcount != 0:
		dmarc_ok_percentage = DMARCOkCount * 100 / hamcount
		dmarc_info = f"Number of emails approved through DMARC: {DMARCOkCount or 0} ({dmarc_ok_percentage:.2f}% of Ham count)"

	# Accumulate all strings
	header_str = "\n".join([clam_info, sa_info, tag_reject_info, smtp_stats, dmarc_info])
	# switch newlines to <br />
	header_str = header_str.replace("\n","<br />")
	return header_str
	
def scan_mail_users():
	#
	# Count emails left in junkmail folders for each user
	#
    base_path = '/home/e-smith/files/users'
    users_info = defaultdict(int)
    
    # List of junk mail directories to check
    junk_mail_directories = [
        'Maildir/.Junk/cur',
        'Maildir/.Junk/new',
        'Maildir/.Junkmail/cur',
        'Maildir/.Junkmail/new'
        'Maildir/.junk/cur',
        'Maildir/.junk/new',
        'Maildir/.junkmail/cur',
        'Maildir/.junkmail/new'
    ]

    # Iterate through each user directory
    for user in os.listdir(base_path):
        user_path = os.path.join(base_path, user)     
        # Check if it is a directory
        if os.path.isdir(user_path):
            total_junk_count = 0
            
            # Check each junk mail path and accumulate counts
            for junk_dir in junk_mail_directories:
                junk_mail_path = os.path.join(user_path, junk_dir)

                # Check if the Junk directory actually exists
                if os.path.exists(junk_mail_path):
                    try:
                        # Count the number of junk mail files in that directory
                        junk_count = len(os.listdir(junk_mail_path))
                        total_junk_count += junk_count
                    except Exception as e:
                        logging.error(f"Error counting junk mails in {junk_mail_path} for user {user}: {e}")
            if total_junk_count != 0:
                users_info[user] = total_junk_count
    return users_info

def get_first_email_with_domain(email_string, domain):
    """
    Returns the first email address in the comma-separated string that matches the specified domain.
    If there is only one email, it returns that email regardless of the domain.

    Args:
    email_string (str): A string of comma-separated email addresses.
    domain (str): The domain to filter email addresses by.

    Returns:
    str: The first email address that matches the domain, or the single email if only one is provided, or None if no match is found.
    """
    # Remove leading and trailing whitespace and split the email string
    emails = [email.strip() for email in email_string.split(',')]
    
    # Check if there is only one email
    if len(emails) == 1:
        return emails[0]  # Return the single email directly
    
    # Iterate through the list of emails
    for email in emails:
        # Check if the email ends with the specified domain
        if email.endswith('@' + domain):
            return email  # Return the first matching email
    
    return None  # Return None if no matching email is found
    
def display_keys_and_values(data):
    """
    Display all keys and values for a list of dictionaries or an array (list of lists).

    Args:
        data (list): A list of dictionaries or a list of lists.
    """
    if not isinstance(data, list):
        raise ValueError("Input must be a list.")

    if all(isinstance(item, dict) for item in data):
        # Handle list of dictionaries
        for index, dictionary in enumerate(data):
            print(f"Item {index + 1}:")
            for key, value in dictionary.items():
                print(f"  {key}: {value}")
            print()  # Add a blank line between items
    elif all(isinstance(item, list) for item in data):
        # Handle array (list of lists)
        for index, item in enumerate(data):
            print(f"Item {index + 1}:")
            for i, value in enumerate(item):
                print(f"  Column {i + 1}: {value}")
            print()  # Add a blank line between items
    else:
        raise ValueError("Input must be a list of dictionaries or a list of lists.")
        
def extract_blacklist_domain(text):
    match = re.search(r'http://www\.surbl\.org', text)
    if match:
        return "www.surbl.org"
    return None
    
def set_log_level(level):
    """Dynamically adjust logging level (e.g., 'DEBUG', 'INFO', 'ERROR')."""
    numeric_level = getattr(logging, level.upper(), None)
    if not isinstance(numeric_level, int):
        raise ValueError(f"Invalid log level: {level}")
    logging.setLevel(numeric_level)

def format_duration(seconds: float) -> str:
    """Convert seconds to human-readable HH:MM:SS format."""
    return str(timedelta(seconds=seconds))


if __name__ == "__main__":
	start_time = datetime.now()
	try:
		chameleon_version = pkg_resources.get_distribution("Chameleon").version
	except pkg_resources.DistributionNotFound:
		chameleon_version = "Version information not available"
	python_version = sys.version
	#python_version = python_version[:8]
	python_version = re.match(r'^\d+\.\d+\.\d+',python_version).group(0); #Extract the version number
	current_datetime = datetime.now()
	formatted_datetime = current_datetime.strftime("%Y-%m-%d %H:%M")
	
	# Command line parameters
	parser = argparse.ArgumentParser(description="Mailstats")
	parser.add_argument('-d', '--date', help='Specify a valid date (yyyy-mm-dd) for the analysis', default=formatted_yesterday)
	parser.add_argument('-ef', '--emailfile', help='Save an html file of the email sent (y/N)', default='n')
	parser.add_argument('-tf', '--textfile', help='Save a txt file of the html page (y/N)', default='n')
	parser.add_argument('--version', action='version', version='%(prog)s '+Mailstats_version+" built on "+build_date_time)
	parser.add_argument('-db', '--dbsave', help='Force save of summary logs in DB (y/N)', default='n')
	
	args = parser.parse_args()

	analysis_date = args.date
	# and check its format is valid
	try:
		datetime.strptime(analysis_date, '%Y-%m-%d')
	except ValueError:
		logging.error("Specify a valid date (yyyy-mm-dd) for the analysis")
		quit(1)

	anaysis_date_obj = datetime.strptime(analysis_date, '%Y-%m-%d')
	noemailfile = args.emailfile.lower()  == 'n'
	notextfile = args.textfile.lower()  == 'n'
	isThonny = is_running_under_thonny()
	forceDbSave = args.dbsave.lower()  == 'y'
	
	#E-Smith Config DBs
	if isThonny:
		db_dir = "/home/brianr/SME11Build/GITFiles/smecontribs/smeserver-mailstats/"
	else:
		db_dir = "/home/e-smith/db/"
		
	#From SMEServer DB
	ConfigDB = read_config_file(db_dir+"configuration")

	DomainName = get_value(ConfigDB, "DomainName", "type") 							#'bjsystems.co.uk' #  $cdb->get('DomainName')->value;
	SystemName = get_value(ConfigDB, "SystemName", "type")
	
	hello_string = "Mailstats:"+Mailstats_version+' for '+SystemName+"."+DomainName+" for "+analysis_date+" printed at:"+formatted_datetime
	
	logging.info(hello_string)
	version_string = "Chameleon:"+chameleon_version+" Python:"+python_version
	if isThonny:
		version_string = version_string + "...under Thonny"
	logging.debug(f"{version_string} and built on {build_date_time}")
	

	RHSenabled = get_value(ConfigDB, "qpsmtpd", "RHSBL","disabled") == "enabled"    #True  #( $cdb->get('qpsmtpd')->prop('RHSBL') eq 'enabled' );
	DNSenabled = get_value(ConfigDB, "qpsmtpd", "DNSBL","disabled") == "enabled"  	#True  #( $cdb->get('qpsmtpd')->prop('DNSBL') eq 'enabled' );

	SARejectLevel = int(get_value(ConfigDB, "spamassassin", "RejectLevel","12")) 	#12  #$cdb->get('spamassassin')->prop('RejectLevel');
	SATagLevel = int(get_value(ConfigDB, "spamassassin", "TagLevel","4")) 			#4  #$cdb->get('spamassassin')->prop('TagLevel');
	if SARejectLevel == 0:
		warnnoreject = "(*Warning* 0 = no reject)"
	else:
		warnnoreject = ""

	EmailAddress = get_value(ConfigDB,"mailstats","Email","admin@"+DomainName)
	if '@' not in EmailAddress:
		EmailAddress = EmailAddress+"@"+DomainName
	EmailTextorHTML = get_value(ConfigDB,"mailstats","TextorHTML","Both") 		#Text or Both or None
	EmailHost = get_value(ConfigDB,"mailstats","EmailHost","localhost") 			#Default will be localhost
	EmailPort = int(get_value(ConfigDB,"mailstats","EmailPort","25"))
	EMailSMTPUser = get_value(ConfigDB,"mailstats","EmailUser")   					#None = default => no authenticatioon needed
	EMailSMTPPassword = get_value(ConfigDB,"mailstats","EmailPassword")
	
	BadCountries = get_value(ConfigDB,"qpsmtpd","BadCountries")
	
	wanted_mailstats_email = get_value(ConfigDB,"mailstats","CountMailstatsEmail", "no")
	
	count_records_to_db = 0;
	
	# Db save control
	saveData = get_value(ConfigDB,"mailstats","SaveDataToMySQL","no") == 'yes' or forceDbSave
	logging.debug(f"Save Mailstats to DB set:{saveData} ")

	if saveData:
		# Connect to MySQL DB for saving
		DBName = "mailstats"
		DBHost = get_value(ConfigDB, 'mailstats', 'DBHost', "localhost")
		DBPort = int(get_value(ConfigDB, 'mailstats', 'DBPort', "3306"))  # Ensure port is an integer
		DBPassw = 'mailstats'
		DBUser = 'mailstats'
		UnixSocket = "/var/lib/mysql/mysql.sock" 

		# Try to establish a database connection
		try:
			conn = pymysql.connect(
				host=DBHost,
				user=DBUser,
				password=DBPassw,
				database=DBName,
				port=DBPort,
				unix_socket=UnixSocket,
				cursorclass=pymysql.cursors.DictCursor  # Optional: use DictCursor for dict output
			)
			cursor = conn.cursor()
			# Check if the table exists before creating it
			check_table_query = "SHOW TABLES LIKE 'SummaryLogs'"
			cursor.execute(check_table_query)
			table_exists = cursor.fetchone()
			if not table_exists:
				# Create table if it doesn't exist
				cursor.execute("""
				CREATE TABLE IF NOT EXISTS SummaryLogs (
					id INT AUTO_INCREMENT PRIMARY KEY,
					Date DATE,
					Hour INT,
					logData TEXT
				)
				""")
			# Delete existing records for the given date
			try:
				delete_query = """
				DELETE FROM SummaryLogs
				WHERE Date = %s
				"""
				cursor.execute(delete_query, (analysis_date,))  # Don't forget the extra comma for tuple
				# Get the number of records deleted
				rows_deleted = cursor.rowcount
				if rows_deleted > 0:
					logging.debug(f"Deleted {rows_deleted} rows for {analysis_date} ")
			except pymysql.Error as e:
				logging.error(f"SQL Delete failed ({delete_query}) ({e}) ")

		except pymysql.Error as e:
			logging.error(f"Unable to connect to {DBName} on {DBHost} port {DBPort} error ({e}) ")
			saveData = False
	
	nolinks = not saveData 
	# Not sure we need these...
	# if (ConfigDB,"qpsmtpd","RHSBL").lower() == 'enabled':
		# RBLList = get_value(ConfigDB,"qpsmtpd","RBLList")
	# else:
		# RBLList = ""
	# if (ConfigDB,"qpsmtpd","RBLList").lower() == 'enabled':
		# SBLLIst = get_value(ConfigDB,"qpsmtpd","SBLLIst")
	# else:
		# RBLList = ""
	# if (ConfigDB,"qpsmtpd","RBLList").lower() == 'enabled':
		# UBLList = get_value(ConfigDB,"qpsmtpd","UBLLIst")
	# else:
		# RBLList = ""
	
	FetchmailIP = '127.0.0.200';       	#Apparent Ip address of fetchmail deliveries
	WebmailIP = '127.0.0.1';           	#Apparent Ip of Webmail sender
	localhost = 'localhost';           	#Apparent sender for webmail
	FETCHMAIL = 'FETCHMAIL';   			#Sender from fetchmail when Ip address not 127.0.0.200 - when qpsmtpd denies the email
	MAILMAN = "bounces";        		#sender when mailman sending when orig is localhost
	DMARCDomain="dmarc"; 				#Pattern to recognised DMARC sent emails (this not very reliable, as the email address could be anything)
	DMARCOkPattern="dmarc: pass";  		#Pattern to use to detect DMARC approval

	num_hours = 25  # Represents hours from 0 to 23 - adds extra one for column totals and another for percentages

	#log_file = logs_dir+'current.log'
	#log_entries,skip_count,ignored_count = read_in_relevant_log_file(log_file,anaysis_date_obj)
	log_entries = get_logs_from_Journalctl(analysis_date)
	logging.debug(f"Found {len(log_entries)} entries in log for for {anaysis_date_obj.strftime('%Y-%m-%d')}")  #Ignored: {ignored_count} skipped: {skip_count}")
	summary_log_entries,skip_count = filter_summary_records(log_entries)
	logging.debug(f"Found {len(summary_log_entries)} summary entries and skipped {skip_count} entries")
	sorted_log_dict = sort_log_entries(summary_log_entries)
	logging.debug(f"Sorted {len(sorted_log_dict)} entries")
	#print(f"{sorted_log_dict}")
	#quit(1)

	columnHeaders = ['Count','WebMail','Local','MailMan','Relay','DMARC','Virus','RBL/DNS','Geoip.','Non.Conf.','Karma','Rej.Load','Del.Spam','Qued.Spam?','  Ham','TOTALS','PERCENT']
	# dict for each colum identifying plugin that increments count
	columnPlugin = [''] * 17
	columnPlugin[Hour] = [] 
	columnPlugin[WebMail] = []
	columnPlugin[Local] = [] 
	columnPlugin[MailMan] = []
	columnPlugin[DMARC] = ['dmarc'] 
	columnPlugin[Virus] = ['pattern_filter', 'virus::pattern_filter','virus::clamav','virus::clamdscan'] 
	columnPlugin[RBLDNS] = ['rhsbl', 'dnsbl','uribl']
	columnPlugin[Geoip] = ['check_badcountries'] 
	columnPlugin[NonConf] = ['check_earlytalker','check_relay','check_norelay', 'require_resolvable_fromhost'
							 ,'check_basicheaders','check_badmailfrom','check_badrcptto_patterns'
							 ,'check_badrcptto','check_spamhelo','check_goodrcptto extn','rcpt_ok'
							 ,'check_goodrcptto','check_smtp_forward','count_unrecognized_commands','tls','auth::auth_cvm_unix_local'
							 ,'auth::auth_imap', 'earlytalker','resolvable_fromhost','relay','headers','mailfrom','badrcptto','helo'
							 ,'check_smtp_forward','sender_permitted_from']
	columnPlugin[RejLoad] = ['loadcheck']
	columnPlugin[DelSpam] = []
	columnPlugin[QuedSpam] = []
	columnPlugin[Ham] = [] 
	columnPlugin[TOTALS] = []
	columnPlugin[PERCENT] = []
	columnPlugin[Karma] = ['karma']
			
	columnHeaders_len = len(columnHeaders)
	columnCounts_2d = initialize_2d_array(num_hours, columnHeaders_len,analysis_date)
	
	virus_pattern = re.compile(r"Virus found: (.*)")
	found_viruses = defaultdict(int)
	
	recipients_found = []
	
	found_qpcodes = defaultdict(int)
	total_ports = defaultdict(int)
	blacklist_found = defaultdict(int)
	
	qpcodes_pattern = re.compile(r"(\(.*\)).*'")
	email_pattern = r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}' #extract email from rejected message
	i = 0;
	sorted_len= len(sorted_log_dict)
	#unless none to show
	spamavg = 0;
	spamqueuedcount = 0
	hamcount = 0
	hamavg = 0
	rejectspamcount = 0
	rejectspamavg = 0
	DMARCSendCount = 0
	totalexamined = 0
	total_qpsmtpd = 0
	total_sqpsmtpd = 0
	total_uqpsmtpd = 0
	count_ignored_mailstats = 0;
	
	if sorted_len > 0:
		if isThonny:
			# Initial call to logging.error( the progress bar
			print_progress_bar(0, sorted_len, prefix='Progress:', suffix='Complete', length=50)
		for timestamp, data in sorted_log_dict.items():
			i += 1
			totalexamined += 1
			if isThonny:
				print_progress_bar(i, sorted_len, prefix='Scanning for main table:', suffix='Complete', length=50)
			# Count of in which hour it falls      
			# Parse the timestamp string into a datetime object
			dt = timestamp
			hour = dt.hour
			# parse the data
			parsed_data = parse_data(data)
			#Take out the mailstats email if necessay
			if wanted_mailstats_email == 'no':
				if 'mailstats' in parsed_data['from-email'] and DomainName in parsed_data['from-email']:
					count_ignored_mailstats +=1
					continue
			# Save the data here if necessary
			if saveData:
				save_summaries_to_db(cursor,conn,anaysis_date_obj.strftime('%Y-%m-%d'),hour,parsed_data)

			#Count the number of emails through each of qpsmtpd, uqpsmtpd and sqpsmtpd
			# the forkserver column in the log indicates it.
			if parsed_data['qpsmtpd'].startswith ('qpsmtpd'):
				total_ports['25'] +=1
			elif parsed_data['qpsmtpd'].startswith ('sqpsmtpd'):
				total_ports['465'] +=1
			elif parsed_data['qpsmtpd'].startswith ('uqpsmtpd'):
				total_ports['587'] +=1
			# Increment Count in which headings it falls
			#Hourly count and column total
			columnCounts_2d[hour][Hour] += 1
			columnCounts_2d[ColTotals][Hour] += 1
			#Row Totals
			columnCounts_2d[hour][TOTALS] += 1
			#Total totals
			columnCounts_2d[ColTotals][TOTALS] += 1
			
			# first spot the fetchmail and 'local' deliveries.
			#Local send
			if DomainName in parsed_data['sendurl']:
				columnCounts_2d[hour][Local] += 1
				columnCounts_2d[ColTotals][Local] += 1
			#Relay or webmail
			elif not is_private_ip(parsed_data['ip']) and is_private_ip(parsed_data['sendurl1']) and parsed_data['action1'] == 'queued':
				#Relay
				columnCounts_2d[hour][Relay] += 1
				columnCounts_2d[ColTotals][Relay] += 1
			elif WebmailIP in parsed_data['sendurl1'] and not is_private_ip(parsed_data['ip']):
				#webmail
				columnCounts_2d[hour][WebMail] += 1
				columnCounts_2d[ColTotals][WebMail] += 1
				
			elif localhost in parsed_data['sendurl']:
				# but not if it comes from fetchmail
				if not FETCHMAIL in parsed_data['sendurl1']:
					# might still be from mailman here
					if MAILMAN in parsed_data['sendurl1']:
						#$mailmansendcount++;
						#$localsendtotal++;
						columnCounts_2d[hour][MailMan] += 1
						columnCounts_2d[ColTotals][MailMan] += 1
						#$counts{$abshour}{$CATMAILMAN}++;
						#$localflag = 1;
					else:
						#Or sent to the DMARC server
						#check for email address in $DMARC_Report_emails string
						#my $logemail = $log_items[4];
						if DMARCDomain in parsed_data['from-email']: #(index($DMARC_Report_emails,$logemail)>=0) or 
							#$localsendtotal++;
							DMARCSendCount += 1
							#localflag = 1;
						else:
							# ignore incoming localhost spoofs
							if parsed_data['error-msg'] and not 'msg denied before queued' in parsed_data['error-msg']:
								#Webmail
								#$localflag = 1;
								#$WebMailsendtotal++;
								columnCounts_2d[hour][WebMail] += 1
								columnCounts_2d[ColTotals][WebMail] += 1
								#$WebMailflag = 1;
				else:
					#$localflag = 1;
					#$WebMailsendtotal++;
					#$WebMailflag = 1;
					columnCounts_2d[hour][WebMail] += 1
					columnCounts_2d[ColTotals][WebMail] += 1

			#Queued email
			if parsed_data['action1'] == 'queued':
				columnCounts_2d[hour][Ham] += 1
				columnCounts_2d[ColTotals][Ham] += 1
				# spamassassin not rejected
				if parsed_data.get('spam-status') is not None and isinstance(parsed_data['spam-status'], str):
					if parsed_data['spam-status'].lower().startswith('no'):
						#Extract other parameters from this string
						# example: No, score=-3.9 
						spam_pattern = re.compile(r'score=(-?\d+\.\d+) required=(-?\d+\.\d+)')
						match = re.search(spam_pattern, parsed_data['spam-status'])
						if match:
							score = float(match.group(1))
							if score < float(SATagLevel):
								# Accumulate allowed score (inc negatives?)
								hamavg += score
								hamcount += 1

			#spamassasin rejects
			Isqueuedspam = False;
			if parsed_data.get('spam-status') is not None and isinstance(parsed_data['spam-status'], str):
				if parsed_data['spam-status'].lower().startswith('yes'):
					#Extract other parameters from this string
					# example: Yes, score=10.3 required=4.0 autolearn=disable
					spam_pattern = re.compile(r'score=(-?\d+\.\d+) required=(-?\d+\.\d+)')
					match = re.search(spam_pattern, parsed_data['spam-status'])
					if match:
						score = float(match.group(1))
						required = float(match.group(2))
						if score >= SARejectLevel:
							columnCounts_2d[hour][DelSpam] += 1
							columnCounts_2d[ColTotals][DelSpam] += 1
							rejectspamavg += score
							rejectspamcount += 1
						elif score >= required:
							columnCounts_2d[hour][QuedSpam] += 1
							columnCounts_2d[ColTotals][QuedSpam] += 1
							spamavg += score
							spamqueuedcount += 1
							Isqueuedspam = True #for recipient stats below
				

					
			# Count the qpsmtpd codes
			if parsed_data['error-plugin'].strip() == 'naughty':
				if parsed_data['error-msg'].startswith("(dnsbl)"):
					columnCounts_2d[hour][RBLDNS]+= 1
					columnCounts_2d[ColTotals][RBLDNS]+= 1
				elif parsed_data['error-msg'].startswith("(karma)"):
					columnCounts_2d[hour][KARMA] += 1
					columnCounts_2d[ColTotals][KARMA]+= 1
				elif parsed_data['error-msg'].startswith("(helo)"):
					columnCounts_2d[hour][RBLDNS] += 1
					columnCounts_2d[ColTotals][RBLDNS]+= 1
			else:
				match = qpcodes_pattern.match(parsed_data['action1'])
				if match:
					rejReason = match.group(1)
					found_qpcodes[parsed_data['error-plugin']+"-"+rejReason] += 1
				else:
					found_qpcodes[parsed_data['action1']] += 1

			#Check for blacklist rejection
			error_plugin = parsed_data['error-plugin'].strip()
			if  error_plugin == 'rhsbl' or error_plugin == 'dnsbl':
				blacklist_domain = extract_blacklist_domain(parsed_data['sender'])
				blacklist_found[blacklist_domain] += 1
			
			#Log the recipients and deny or accept and spam-tagged counts
		    # Try to find an existing record for the email
			action = parsed_data["action1"]      # Extract action
			if parsed_data['error-plugin'] == 'check_smtp_forward':
				#extract rejected email address from sender  
				match = re.search(email_pattern, parsed_data['sender'])  
				# If a match is found, return the email address
				if match:
					email = match.group(0)
				else:
					email = "unknown (no email found in smtp reject message)"
			elif parsed_data['error-plugin'] == 'check_badcountries':
				email = "Unknown (Bad Country)"
			elif not is_private_ip(parsed_data['ip']) and parsed_data["to-email"]:
				#Only look at internal recipients from outside
				#Take out the chevrons
				email = parsed_data["to-email"].replace('<', '').replace('>', '')
				email = get_first_email_with_domain(email,DomainName)  # Extract email
				if not email:
					logging.error(f"Incoming email with no internal email address: {email} {DomainName}")
					email = "Unknown (no internal email found)"
			else:
				if not is_private_ip(parsed_data['ip']):
					email = "Unknown (non conf?)"
				else:
					email = None
			if email:
				record = next((item for item in recipients_found if item['email'] == email), None)
				if not record:
					# If email is not in the array, we add it
					record = {"email": email,"accept": 0,"deny": 0,"spam-tagged": 0}
					recipients_found.append(record)
				# Update the deny or accept count based on action
				if action != "queued":
					record["deny"] += 1
				else:
					record["accept"] += 1
					#and see if it is spam tagged
					if Isqueuedspam:
						record["spam-tagged"] += 1
			
				
			
			#Now increment the column which the plugin name indicates
			if parsed_data['error-msg'] and "msg denied before queued" in parsed_data['error-msg'] and parsed_data['virus']:
				if parsed_data['error-plugin']:
					row = search_2d_list(parsed_data['error-plugin'],columnPlugin)
					if not row == -1:
						columnCounts_2d[hour][row] += 1
						columnCounts_2d[ColTotals][row] += 1
						# a few ad hoc extra extractons of data
						if row == Virus:
							match = virus_pattern.match(parsed_data['virus'])
							if match:
								found_viruses[match.group(1)] += 1
							else:
								found_viruses[parsed_data['virus']] += 1
					else:
						found_qpcodes[parsed_data['error-plugin']] += 1
			if isThonny:
				logging.error() #seperate the [progress bar]
				
	if count_ignored_mailstats > 0:
		logging.debug(f"Ignored {count_ignored_mailstats} mailstats emails")
	# Compute percentages
	total_Count  = columnCounts_2d[ColTotals][TOTALS]
	#Column of percentages
	for row in range(ColTotals):
		if total_Count == 0:
			percentage_of_total = 0
		else:
			percentage_of_total = f"{round(round(columnCounts_2d[row][TOTALS] / total_Count,4) * 100,1)}%"
		columnCounts_2d[row][PERCENT] = percentage_of_total
	#Row of percentages
	for col in range(TOTALS):
		if total_Count == 0:
			percentage_of_total = 0
		else:
			percentage_of_total = f"{round(round(columnCounts_2d[ColTotals][col] / total_Count,4) * 100,1)}%"
		columnCounts_2d[ColPercent][col] = percentage_of_total
	# and drop in the 100% to make it look correct!
	columnCounts_2d[ColPercent][PERCENT] = '100%'
	columnCounts_2d[ColTotals][PERCENT] = '100%'
	columnCounts_2d[ColPercent][TOTALS] = '100%'
	
	#other stats
	emailperhour = (totalexamined / 24)
	if not spamqueuedcount == 0:
		spamavg = spamavg / spamqueuedcount
	if not rejectspamcount == 0:
		rejectspamavg = rejectspamavg / rejectspamcount
	if not hamcount == 0:
		hamavg = hamavg / hamcount

	# Now scan for the other lines in the log of interest
	found_countries = defaultdict(int)
	geoip_pattern = re.compile(r".*check_badcountries: GeoIP Country: (.*)")
	dmarc_pattern = re.compile(r".*dmarc: pass")
	helo_pattern = re.compile(r".*Accepted connection.*?from (\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}) \/ ([\w.-]+)")
	connect_type_pattern = re.compile(r".*connect via (.*)")
	tls_type_pattern = re.compile(r".*Go ahead with (.*)")
	total_countries = 0
	DMARCOkCount = 0
	totalinternalsmtpsessions = 0
	totalexternalsmtpsessions = 0

	i = 0
	j = 0
	log_len = len(log_entries)
	connection_type_counts = defaultdict(int)
	if log_len > 0:
		if isThonny:
			print_progress_bar(0, log_len, prefix='Progress:', suffix='Complete', length=50)
		for data in log_entries:
			i += 1
			if isThonny:
				print_progress_bar(i, log_len, prefix='Scanning for sub tables:', suffix='Complete', length=50)
				
			# Match initial connection message
			IsInternal = True
			try:
				match = helo_pattern.match(data['MESSAGE'])
				if match:
					ip  = match.group(1)
					fqdn = match.group(2)
					if is_private_ip(ip):
						totalinternalsmtpsessions += 1
					else:
						totalexternalsmtpsessions += 1
						IsInternal = False
					continue
			except Exception as e:
				logging.error(f" Helo pattern error {e} {data['MESSAGE']} {analysis_date}")
				continue
					
			#Pull out Geoip countries for analysis table
			try:
				match = geoip_pattern.match(data['MESSAGE'])
				if match:
					j += 1
					country = match.group(1)
					found_countries[country] += 1
					total_countries += 1
					continue
			except Exception as e:
				logging.error(f"Geoip pattern error {e} {data['MESSAGE']} {analysis_date}")
				continue
			
			#Pull out DMARC approvals
			match = dmarc_pattern.match(data['MESSAGE'])
			if match:
				DMARCOkCount += 1
				continue

			#Pull out type of connection
			match = connect_type_pattern.match(data['MESSAGE'])
			if match:
				connection_type = match.group(1)
				connection_type_counts[connection_type] += 1
				continue
				
			match = tls_type_pattern.match(data['MESSAGE'])
			if match:
				connection_type = match.group(1)
				connection_type_counts[connection_type] += 1
				continue
	

	#Compute next and previous dates
	day_format = "%Y-%m-%d"
	# Convert the time string to a datetime object
	date_obj = datetime.strptime(analysis_date, day_format)
	# Compute the next date by adding one day
	next_date = date_obj + timedelta(days=1)
	# Compute the previous date by subtracting one day
	previous_date = date_obj - timedelta(days=1)
	# Convert the datetime objects back to strings in the desired format
	next_date_str = next_date.strftime(day_format)
	previous_date_str = previous_date.strftime(day_format)

	# Create graphs of data
	
	# yLabels = [f'{i:02d}:00' for i in range(len(columnCounts_2d))]
	# stacked_Bar_html = create_stacked_bar_graph(columnCounts_2d,columnHeaders,yLabels,html_page_dir+'stacked_bar_'+analysis_date+'.html')
	# heatmap_html = create_heatmap(columnCounts_2d,columnHeaders,yLabels,html_page_dir+'heatmap_'+analysis_date+'.html')
	# line_graph_html = create_line_chart(columnCounts_2d,columnHeaders,yLabels,html_page_dir+'line_graph_'+analysis_date+'.html')
	
	columnCounts_2d_dict = transform_to_dict(columnCounts_2d,columnHeaders,analysis_date)

	#Export as json for testing		
	# with open("/opt/mailstats/html/colCounts_2d.json", "w") as json_file:
		# json.dump(columnCounts_2d, json_file)
	# with open("/opt/mailstats/html/colCounts_2d-dict", "w") as json_file:
		# json.dump(columnCounts_2d_dict, json_file)
	# with open("/opt/mailstats/html/keys.json", "w") as json_file:
		# json.dump(columnHeaders, json_file)

	if enable_graphs:
		create_graph(columnCounts_2d_dict, "line", html_page_dir+"line_graph_"+analysis_date+".png",analysis_date)
		create_graph(columnCounts_2d_dict, "bar", html_page_dir+"bar_graph_"+analysis_date+".png",analysis_date)
		create_graph(columnCounts_2d_dict, "scatter", html_page_dir+"scatter_graph_"+analysis_date+".png",analysis_date)
		create_graph(columnCounts_2d_dict, "pie", html_page_dir+"pie_chart_"+analysis_date+".png",analysis_date)

	#Now apply the results to the chameleon template - main table
	# Path to the template file
	template_path = template_dir+'mailstats.html.pt'
	# Load the template
	with open(template_path, 'r') as template_file:
		template_content = template_file.read()
	#Use the hello string to create a suitable heading for the web page
	html_title = hello_string.replace("printed at:"," <span class='greyed-out'>printed at:")
	html_title += "</span>"
	
	# Create a Chameleon template instance
	try:
		template = PageTemplate(template_content)
		# Render the template with the 2D array data and column headers
		try:
			rendered_html = template(array_2d=columnCounts_2d, column_headers=columnHeaders, 
										reporting_date=analysis_date, 
										title=html_title, 
										version=version_string,
										nolinks=nolinks,
										PreviousDate=previous_date_str,
										NextDate=next_date_str,
										DomainName=DomainName,
										SystemName=SystemName,
										enable_graphs=enable_graphs
										)
		except Exception as e:
			logging.error(f"Chameleon template Exception {e}")
	except Exception as e:
		logging.error(f"Chameleon render Exception {e}")
		
	total_html = rendered_html
	# Add in the header information
	header_rendered_html = get_heading()
	total_html =  insert_string_after(total_html,header_rendered_html, "<!---Add in header information here -->")

	#add in the subservient tables..(remeber they appear in the reverse order of below!)

	#virus codes
	virus_headers = ["Virus",'Count','Percent']
	virus_title = 'Viruses found'
	virus_rendered_html = render_sub_table(virus_title,virus_headers,found_viruses,suppress_threshold=True)
	# Add it to the total 
	total_html = insert_string_after(total_html,virus_rendered_html, "<!---Add in sub tables here -->")

	#qpsmtd codes
	qpsmtpd_headers = ["Reason",'Count','Percent']
	qpsmtpd_title = 'Qpsmtpd codes league table'
	qpsmtpd_rendered_html = render_sub_table(qpsmtpd_title,qpsmtpd_headers,found_qpcodes)
	# Add it to the total 
	total_html = insert_string_after(total_html,qpsmtpd_rendered_html, "<!---Add in sub tables here -->")
	
	
	#Junk mails
	junk_mail_count_headers = ['Username','Count', 'Percent']
	junk_mail_counts = scan_mail_users()
	junk_mail_count_title = 'Junk mail counts'
	junk_rendered_html = render_sub_table(junk_mail_count_title,junk_mail_count_headers,junk_mail_counts,suppress_threshold=True)
	# Add it to the total 
	total_html = insert_string_after(total_html,junk_rendered_html, "<!---Add in sub tables here -->")

	
	#Recipient counts
	recipient_count_headers = ["Email",'Queued','Rejected','Spam tagged','Accepted Percent']
	recipient_count_title = 'Incoming email recipients'
	recipient_rendered_html = render_sub_table(recipient_count_title,recipient_count_headers,recipients_found,suppress_threshold=True)
	# Add it to the total 
	total_html = insert_string_after(total_html,recipient_rendered_html, "<!---Add in sub tables here -->")

	#Geoip Country codes
	geoip_headers  = ['Country','Count','Percent','Rejected?']
	geoip_title = 'Geoip results'
	geoip_rendered_html = render_sub_table(geoip_title,geoip_headers,found_countries,get_character_in_reject_list)
	# Add it to the total 
	total_html = insert_string_after(total_html,geoip_rendered_html, "<!---Add in sub tables here -->")
	
	#Blacklist counts
	blacklist_headers = ['URL','Count','Percent']
	blacklist_title = 'Blacklist used'
	blacklist_rendered_html = render_sub_table(blacklist_title,blacklist_headers,blacklist_found,suppress_threshold=True)
	# Add it to the total 
	total_html = insert_string_after(total_html,blacklist_rendered_html, "<!---Add in sub tables here -->")
	
	if saveData:
		# Close the connection
		cursor.close()
		conn.close()
	
	# Write the rendered HTML to a file
	output_path = html_page_dir+'mailstats_for_'+analysis_date
	output_path = output_path.replace(' ','_')
	with open(output_path+'.html', 'w') as output_file:
		output_file.write(total_html)
	#and create a text version if the local version of html2text is suffiicent
	if get_html2text_version() == '2019.9.26':
		# Get temporary file
		temp_file_name = tempfile.mktemp()
		temp_file_name1 = tempfile.mktemp()
		# see if html has links in the table entries, if not then use the current html file, else generate one
		if not nolinks:
			# i.e. links in html
			# Render the template with the 2D array data and column headers
			try:
				rendered_html = template(array_2d=columnCounts_2d, column_headers=columnHeaders, 
											reporting_date=analysis_date, 
											title="",
											version=version_string,
											nolinks=True,
											PreviousDate=previous_date_str,
											NextDate=next_date_str,
											DomainName=DomainName,
											SystemName=SystemName,
											enable_graphs=False
											)
			except Exception as e:
				logging.error(f"Chameleon template Exception {e}")
			# Need to add the sub tables
			full_rendered_html = ''.join([
				html_title+"<br />",
				header_rendered_html,
				rendered_html, 
				blacklist_rendered_html,
				geoip_rendered_html,
				recipient_rendered_html,
				junk_rendered_html,
				qpsmtpd_rendered_html,
				virus_rendered_html
			])
			# delete next and prev 
			start = full_rendered_html.find("Previous")
			end = full_rendered_html.find("Table")
			full_rendered_html = full_rendered_html[:start] + full_rendered_html[end:]
			with open(temp_file_name, 'w') as output_file:
				output_file.write(full_rendered_html)
		else:
			temp_file_name = output_path+'.html'
		html_to_text(temp_file_name,temp_file_name1)
		logging.debug(f"Rendered HTML saved to {temp_file_name1}")
		# and save it if required
		if not notextfile:
			text_file_path = output_path+'.txt'
			# and rename it
			os.rename(temp_file_name1, text_file_path)
		else:
			text_file_path = temp_file_name1
	else:
		text_file_path = ""
	
	logging.debug(f"Written {count_records_to_db} records to DB")
	
	html_content = None
	text_content = None
	#Now see if Email required
	if EmailTextorHTML:
		if EmailTextorHTML == "HTML" or EmailTextorHTML == "Both":
			# Send html email (default))
			filepath = html_page_dir+"mailstats_for_"+analysis_date+".html"
			html_content = read_html_from_file(filepath)
			# Replace the Navigation by a "See in browser" prompt
			replace_str = f"<div class='divseeinbrowser'><a class='seeinbrowser' href='http://{SystemName}.{DomainName}/mailstats/mailstats_for_{analysis_date}.html'>See in browser</a></div>"
			html_content = replace_between(html_content, "<div class='linksattop'>", ">Next</a></div>", replace_str)
			if not noemailfile:
				# Write out the email html to a web page
				email_file = html_page_dir + "Email_mailstats_for_"+analysis_date
				with open(email_file+'.html', 'w') as output_file:
					output_file.write(html_content)
		if EmailTextorHTML == "Text" or EmailTextorHTML == "Both":
			#filepath = html_page_dir+"mailstats_for_"+analysis_date+".txt"
			if not text_file_path == "":
				text_content = read_text_from_file(text_file_path)
			else:
				text_content = "No text avaiable (as html2text was not installed) "
		if EMailSMTPUser:
			# Send authenticated
			logging.debug("Sending authenticated")
			send_email(
				subject="Mailstats for "+analysis_date,
				from_email="mailstats@"+DomainName, 
				to_email=EmailAddress, 
				smtp_server=EmailHost, 
				smtp_port=EmailPort,
				HTML_content=html_content, 
				Text_content=text_content,
				smtp_user=EMailSMTPUser,
				smtp_password=EMailSMTPPassword
			)
		else:
			# No authentication
			logging.debug(f"Sending non authenticated {EmailAddress} {EmailHost}")
			try:
				send_email(
					subject="Mailstats for "+analysis_date,
					from_email="mailstats@"+DomainName, 
					to_email=EmailAddress, 
					smtp_server=EmailHost, 
					smtp_port=EmailPort,
					HTML_content=html_content, 
					Text_content=text_content 
				)
			except Exception as e:
				logging.error(f"Email Exception {e}")
	finish_time = datetime.now()
	duration = (finish_time - start_time).total_seconds()
	logging.info(
		f"Mailstats finished at {finish_time.strftime('%Y-%m-%d %H:%M:%S')}"+f" Time taken: {duration:.2f} seconds"
	)