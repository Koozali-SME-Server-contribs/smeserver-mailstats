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
#
# Rocky8: (probably - not yet checked this)
#
# dnf install python3-chameleon --enablerepo=epel
# dnf install html2text --enablerepo=epel
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
import mysql.connector
import numpy as np
import plotly.graph_objects as go
import plotly.express as px
import colorsys

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

import mysql.connector
import json

def sanitize_and_filter_data_for_stacked_bar(data2d, xLabels, yLabels, exclude_columns_labels, exclude_rows_labels):
    """
    Sanitize data by removing unwanted columns and rows, and converting to numeric values.
    
    Parameters:
    - data2d (list of lists): A 2D list containing the data.
    - xLabels (list): Current labels for the x-axis.
    - yLabels (list): Current labels for the y-axis.
    - exclude_columns_labels (list): Labels of columns to exclude from the data and x-axis.
    - exclude_rows_labels (list): Labels of rows to exclude from the y-axis.
    
    Returns:
    - numpy.ndarray: Sanitized 2D numpy array with numeric data.
    - list: Filtered x-axis labels.
    - list: Filtered y-axis labels.
    """
    def to_numeric(value):
        try:
            if isinstance(value, str):
                # Remove any extra characters like '%' and convert to float
                return float(value.replace('%', '').strip())
            else:
                return float(value)
        except ValueError:
            return 0.0  # Default to 0 if conversion fails

    # Filter out columns based on their labels
    exclude_columns_indices = [xLabels.index(label) for label in exclude_columns_labels if label in xLabels]
    
    filtered_data2d = [
        [to_numeric(value) for idx, value in enumerate(row) if idx not in exclude_columns_indices]
        for row in data2d
    ]
    
    filtered_xLabels = [label for idx, label in enumerate(xLabels) if idx not in exclude_columns_indices]
    
    # Filter out rows based on their labels
    filtered_data2d = [row for label, row in zip(yLabels, filtered_data2d) if label not in exclude_rows_labels]
    filtered_yLabels = [label for label in yLabels if label not in exclude_rows_labels]
    
    # Convert filtered data to numpy array
    return np.array(filtered_data2d), filtered_xLabels, filtered_yLabels
      
def generate_distinct_colors(num_colors):
    """Generate distinct colors using HSV color space."""
    colors = []
    for i in range(num_colors):
        hue = i / num_colors
        saturation = 0.7
        value = 0.9
        r, g, b = colorsys.hsv_to_rgb(hue, saturation, value)
        colors.append(f'rgb({int(r * 255)},{int(g * 255)},{int(b * 255)})')
    return colors

def create_stacked_bar_graph(data2d, xLabels, yLabels, save_path='stacked_bar_graph.html'):
    """
    Creates and saves a stacked bar graph from given 2D numpy array data using Plotly.
    
    Parameters:
    - data2d (list of lists or numpy.ndarray): A 2D list or numpy array containing the data.
    - xLabels (list): A list of category labels for the x-axis.
    - yLabels (list): A list of labels for the y-axis (e.g., hours).
    - save_path (str): The path where the plot image will be saved.
    """
    # Identify columns to be removed based on their headers (label names) and indices (hours 24 and 25)
    exclude_columns_labels = ["Count", "PERCENT","TOTALS"]
    exclude_rows_labels = ["24:00", "25:00"]

    # Ensure input yLabels correspond to the data
    if len(yLabels) != len(data2d):
        raise ValueError(f"The length of yLabels {len(yLabels)} must match the number of rows in the data {len(data2d)}.")
    
    # Sanitize and filter the data
    sanitized_data, filtered_xLabels, filtered_yLabels = sanitize_and_filter_data_for_stacked_bar(data2d, xLabels, yLabels, exclude_columns_labels, exclude_rows_labels)
    
    # Ensure that the length of yLabels matches the number of rows (0 to n should be n+1 rows)
    if len(filtered_yLabels) != sanitized_data.shape[0]:
        raise ValueError(f"The length of filtered_yLabels {len(filtered_yLabels)} must match the number of rows in the data {sanitized_data.shape[0]}.")
    
    # Transpose the data so that hours are on the x-axis and categories are stacked in the y-axis
    transposed_data = sanitized_data.T
    
    fig = go.Figure()
    
    # Get unique colors for each category
    extended_colors = generate_distinct_colors(len(filtered_xLabels))
    
    for i, category in enumerate(filtered_xLabels):
        fig.add_trace(go.Bar(
            name=category,
            x=filtered_yLabels,
            y=transposed_data[i],
            marker_color=extended_colors[i % len(extended_colors)]  # Cycle through the colors if there are more categories than colors

        ))
    
    fig.update_layout(
        barmode='stack',
        title='Stacked Bar Graph by Hour',
        xaxis=dict(title='Hour'),
        yaxis=dict(title='Values'),
        legend_title_text='Categories',
        margin = {
            'l': 50,  #left margin
            'r': 120, #right margin
            't': 50,  #top margin
            'b': 50   #bottom margin
        }
 
    )
    
    # Save the graph to an HTML file
    fig.write_html(save_path)
    # Write it to a var and return the string
    graph_html = fig.to_html(full_html=False,include_plotlyjs='https://cdn.plot.ly/plotly-latest.min.js')
    return graph_html
 
def sanitize_and_filter_data(data2d, exclude_labels, xLabels):
    """
    Sanitize data by removing unwanted columns and converting to numeric values.
    
    Parameters:
    - data2d (list of lists): A 2D list containing the data.
    - exclude_labels (list): Labels to exclude from the data and x-axis.
    - xLabels (list): Current labels for the x-axis.
    
    Returns:
    - numpy.ndarray: Sanitized 2D numpy array with numeric data.
    - list: Filtered x-axis labels.
    """
    def to_numeric(value):
        try:
            if isinstance(value, str):
                # Remove any extra characters like '%' and convert to float
                return float(value.replace('%', '').strip())
            else:
                return float(value)
        except ValueError:
            return 0.0  # Default to 0 if conversion fails

    # Create a boolean array for columns to keep (not in exclude_labels)
    columns_to_keep = [label not in exclude_labels for label in xLabels]

    # Filter out the columns both from the data and xLabels
    filtered_data2d = []
    for row in data2d:
        filtered_row = [to_numeric(value) for keep, value in zip(columns_to_keep, row) if keep]
        filtered_data2d.append(filtered_row)

    filtered_xLabels = [label for label, keep in zip(xLabels, columns_to_keep) if keep]

    return np.array(filtered_data2d), filtered_xLabels

def create_heatmap(data2d, xLabels, yLabels, save_path='heatmap.html'):
    """
    Creates and saves a heatmap from given 2D numpy array data using Plotly.
    Parameters:
    - data2d (list of lists or numpy.ndarray): A 2D list or numpy array containing the data.
    - xLabels (list): A list of category labels for the x-axis.
    - yLabels (list): A list of labels for the y-axis (e.g., hours).
    - save_path (str): The path where the plot image will be saved.
    """
    excluded_columns = ["Count", "PERCENT", "TOTALS"]
    # Remove rows 24 and 25 by slicing the data and labels
    data2d = data2d[:24]
    yLabels = yLabels[:24]  # Ensure yLabels also excludes those rows

    # Sanitize and filter the data
    sanitized_data, filtered_xLabels = sanitize_and_filter_data(data2d, excluded_columns, xLabels)

    # Ensure that the length of yLabels matches the number of rows (0 to n should be n+1 rows)
    if len(yLabels) != sanitized_data.shape[0]:
        raise ValueError("The length of yLabels must match the number of rows in the data.")

    # Create the heatmap
    # Define a custom color scale where 0 is white
    color_scale = [
        [0, "lightgrey"],
        [0.3, "blue"],
        [0.6, 'green'],
        [0.75,'yellow'],
        [1,'red']
    ]
    fig = px.imshow(sanitized_data,
                    labels=dict(x="Category", y="Hour", color="Count"),
                    x=filtered_xLabels,
                    y=yLabels,                  
                    color_continuous_scale=color_scale)
    
    fig.update_layout(
        title='Heatmap of Counts by Category per Hour',
        xaxis_nticks=len(filtered_xLabels),
        yaxis_nticks=len(yLabels),
        margin=dict(l=0, r=0, t=30, b=0)

    )
    fig.update_xaxes(showticklabels=True, side='bottom', showline=True, linewidth=2, linecolor='black', mirror=True)
    fig.update_yaxes(showticklabels=True, showline=True, linewidth=2, linecolor='black', mirror=True)
   
    fig.write_html(save_path)  
    # Write it to a var and return the string
    graph_html = fig.to_html(full_html=False,include_plotlyjs='https://cdn.plot.ly/plotly-latest.min.js')
    return graph_html
  
   
def create_line_chart(data2d, xLabels, yLabels, save_path='line_chart.html'):
    fig = go.Figure()
    
    excluded_columns = ["Count", "PERCENT", "TOTALS"]
    # Remove rows 24 and 25 by slicing the data and labels
    data2d = data2d[:24]
    yLabels = yLabels[:24]  # Ensure yLabels also excludes those rows

    # Sanitize and filter the data
    sanitized_data, filtered_xLabels = sanitize_and_filter_data(data2d, excluded_columns, xLabels)

    # Ensure that the length of yLabels matches the number of rows (0 to n should be n+1 rows)
    if len(yLabels) != sanitized_data.shape[0]:
        raise ValueError("The length of yLabels must match the number of rows in the data.")

    # Remove rows with all zero elements and the corresponding categories
    nonzero_rows_indices = np.where(~np.all(sanitized_data == 0, axis=0))[0]  # find rows with non-zero elements
    sanitized_data = sanitized_data[:, nonzero_rows_indices]
    filtered_xLabels = [filtered_xLabels[i] for i in nonzero_rows_indices]  # update filtered_xLabels

    for i, category in enumerate(filtered_xLabels):
        fig.add_trace(go.Scatter(
            mode='lines+markers',
            name=category,
            x= [f'{j:02d}:00' for j in range(sanitized_data.shape[0])],  
            y=sanitized_data[:, i]
        ))

    fig.update_layout(
        title='Line Chart of Counts by Category per Hour',
        xaxis=dict(title='Hour'),
        yaxis=dict(title='Count'),
        legend_title_text='Category'
    )
    
    fig.write_html(save_path)
    # Write it to a var and return the string
    graph_html = fig.to_html(full_html=False,include_plotlyjs='https://cdn.plot.ly/plotly-latest.min.js')
    return graph_html



    
def save_summaries_to_db(date_str, hour, parsed_data):

    # Convert parsed_data to JSON string
    json_data = json.dumps(parsed_data)

    # Insert the record
    insert_query = """
    INSERT INTO SummaryLogs (Date, Hour, logData)
    VALUES (%s, %s, %s)
    """
    
    try:
        cursor.execute(insert_query, (date_str, hour, json_data))
        conn.commit()
    except mysql.connector.Error as err:
        print(f"DB Error {date_str} {hour} : {err}")
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
		print(f"{e} {timestamp}")
		raise ValueError
	# Remove the microseconds completely if they exist
	return truncated_timestamp.split('.')[0]

def read_in_relevant_log_file(file_path,analysis_date=yesterday):
	# Read the file and split each line into a list - timestamp and the rest
	log_entries = []
	skip_record_count = 0
	ignore_record_count = 0
	with codecs.open(file_path, 'rb','utf-8', errors='replace') as file:
		try:
			for Line in file:
				#extract time stamp
				try:
					entry = split_timestamp_and_data(Line)
					# compare with anal date
					timestamp_str = truncate_microseconds(entry[0])
				except ValueError as e:
					#print(f"ValueError {e} on timestamp create {timestamp_str}:{entry[0]} {entry[1]}")
					skip_record_count += 1
					continue
				# Parse the timestamp string into a datetime object
				# Ignoring extra microseconds 
				try:
					timestamp = datetime.strptime(timestamp_str, "%Y-%m-%d %H:%M:%S")
				except ValueError as e:
					print(f"ValueError {e} on timestamp extract {timestamp_str}:{entry[1]}")
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
		if '`' in line[1]:
			filtered_log_entries.append(line)
		else:
			skipped_entry_count += 1
	return [filtered_log_entries,skipped_entry_count]
	
def sort_log_entries(log_entries):
	# Sort the records, based on the timestamp
	sorted_entries = sorted(log_entries, key=lambda x: x[0])
	# and return a dictionary
	sorted_dict = {entry[0]: entry[1] for entry in sorted_entries}
	return sorted_dict
	
def parse_data(data):
	# Split data string into parts and map to named fields.
	# Adjust the field names and parsing logic according to your data format.
	# Split at the backtick - before it fields split at space, after, fields split at tab
	parts = data.split('`')
	fields1 = parts[0].strip().split() if len(parts) > 0 else []
	fields2 = parts[1].split('\t') if len(parts) > 1 else []
	# then merge them
	fields = fields1 + fields2
#	if fields[4] == 'localhost':
#		i = 0
#		print(f"len:{len(fields)}")
#		for part in fields:
#			print(f"{i}: {part}")
#			i  = i +1
#		quit()
	# and mapping:
	try:
		return_dict = {
			'id': fields[0].strip() if len(fields) > 0 else None,
			'action': fields[1].strip() if len(fields) > 1 else None,
			'logterse': fields[2].strip() if len(fields) > 2 else None,
			'ip': fields[3].strip() if len(fields) > 3 else None,
			'sendurl': fields[4].strip() if len(fields) > 4 else None,     #1
			'sendurl1': fields[5].strip() if len(fields) > 5 else None,    #2
			'from-email': fields[6].strip() if len(fields) > 6 else None,  #3
			'error-reason': fields[6].strip() if len(fields) > 6 else None, #3
			'to-email': fields[7].strip() if len(fields) > 7 else None,		#4
			'error-plugin': fields[8].strip() if len(fields) > 8 else None,  #5
			'action1': fields[8].strip() if len(fields) > 8 else None,       #5
			'error-number' : fields[9].strip() if len(fields) > 9 else None, #6
			'sender': fields[10].strip() if len(fields) > 10 else None,      #7
			'error-msg' :fields[10].strip() if len(fields) > 10 else None,   #7
			'spam-status': fields[11].strip() if len(fields) > 11 else None, #8 
			'error-result': fields[11].strip() if len(fields) > 11 else None,#8
			# Add more fields as necessary
		}
	except:
		#print(f"error:len:{len(fields)}")
		return_dict = {}  
	return return_dict

def count_entries_by_hour(log_entries):
	hourly_counts = defaultdict(int)
	for entry in log_entries:
		# Extract hour from the timestamp
		timestamp = entry['timestamp']
		hour = datetime.datetime.strptime(timestamp, '%Y-%m-%d %H:%M:%S').strftime('%Y-%m-%d %H')
		hourly_counts[hour] += 1
	return hourly_counts

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
		
		print(f"html2text is installed at: {html2text_path}")
		return True

	except subprocess.CalledProcessError:
		print("html2text is not installed. Please install it using your package manager.", file=sys.stderr)
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

		print(f"Converted {input_file} to {output_file}")
	except subprocess.CalledProcessError as e:
		print(f"Error occurred: {e.stderr.decode('utf-8')}", file=sys.stderr)
		sys.exit(e.returncode)

def get_html2text_version():
	try:
		result = subprocess.run(['html2text', '--version'], stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True)
		# Ensure the result is treated as a string in Python 3.6+
		return result.stdout.strip()
	except subprocess.CalledProcessError as e:
		print(f"Error occurred while checking html2text version: {e}", file=sys.stderr)
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
		print_end   - Optional : end character (e.g. "\r", "\r\n") (Str)
	"""
	if total == 0:
		raise ValueError("Progress total is zero")
	percent = ("{0:." + str(decimals) + "f}").format(100 * (iteration / float(total)))
	filled_length = int(length * iteration // total)
	bar = fill * filled_length + '-' * (length - filled_length)
	print(f'\r{prefix} |{bar}| {percent}% {suffix}', end=print_end)
	# Print New Line on Complete
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
		print(f"insert_string_after:({after}) string is not found in original")
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
	parts = log_entry.split(' ', 2)
	
	if len(parts) < 3:
		raise ValueError(f"The log entry format is incorrect {parts}")
	
	timestamp = ' '.join(parts[:2])
	rest_of_data = parts[2]
	return [timestamp, rest_of_data]
	
def render_sub_table(table_title,table_headers,found_values,get_character=None):
	# Get the total
	total_sum = sum(found_values.values())
	# and add in list with second element the percentage
	# Create a list of tuples with each tuple containing (key, value, percentage)
	if get_character:
		sub_result = [(key, value, 
						f"{round(value / total_sum * 100, 2)}",
						f"{get_character(key)}") for key, value in found_values.items()
						]
	else:
		sub_result = [(key, value, 
						f"{round(value / total_sum * 100, 2)}") for key, value in found_values.items()
						]
		
	sub_result.sort(key=lambda x: float(x[2]), reverse=True)  # Sort by percentage in descending order
	sub_template_path = template_dir+'mailstats-sub-table.html.pt'
	# Load the template
	with open(sub_template_path, 'r') as template_file:
		template_content = template_file.read()
	# Create a Chameleon template instance
	try:
		template = PageTemplate(template_content)
		# Render the template with the 2D array data and column headers
		try:
			rendered_html = template(array_2d=sub_result, column_headers=table_headers, title=table_title)
		except Exception as e:
			raise ValueError(f"{table_title}: A chameleon controller render error occurred: {e}")
	except Exception as e:
		raise ValueError(f"{table_title}: A chameleon controller template error occurred: {e}")
	return rendered_html
	
def get_character_in_reject_list(code):
	if code in BadCountries:
		return "*"
	else:
		return ""
	
        
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
	print("reading from html file")
	# Get Filepath
	css_path = os.path.dirname(filepath)+"/../css/mailstats.css"
	# Read in CSS 
	with open(css_path, 'r', encoding='utf-8') as file:
		css_contents = file.read()
	html_contents = insert_string_after(html_contents,"\n"+css_contents,"<!--css here-->")
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
		print(f"{filepath} not found")
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
		for connect_type in connection_type_counts.keys():
			smtp_stats = smtp_stats + f"\nCount of {connection_type} connections:{connection_type_counts[connect_type]}"

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

if __name__ == "__main__":
	try:
		chameleon_version = pkg_resources.get_distribution("Chameleon").version
	except pkg_resources.DistributionNotFound:
		chameleon_version = "Version information not available"
	python_version = sys.version
	python_version = python_version[:8]
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
		print("Specify a valid date (yyyy-mm-dd) for the analysis")
		quit()

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
	
	hello_string = "Mailstats:"+Mailstats_version+' for '+DomainName+" at "+formatted_datetime+" for "+analysis_date
	print(hello_string)
	version_string = "Chameleon:"+chameleon_version+" Python:"+python_version
	if isThonny:
		version_string = version_string + "...under Thonny"
	print(version_string)

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
	EmailTextOrHTML = get_value(ConfigDB,"mailstats","EmailTextOrHTML","Both") 		#Text or Both or None
	EmailHost = get_value(ConfigDB,"mailstats","EmailHost","localhost") 			#Default will be localhost
	EmailPort = int(get_value(ConfigDB,"mailstats","EmailPort","25"))
	EMailSMTPUser = get_value(ConfigDB,"mailstats","EmailUser")   					#None = default => no authenticatioon needed
	EMailSMTPPassword = get_value(ConfigDB,"mailstats","EmailPassword")
	
	BadCountries = get_value(ConfigDB,"qpsmtpd","BadCountries")
	
	# Db save control
	saveData = get_value(ConfigDB,"mailstats","SaveDataToMySQL","no") == 'yes' or forceDbSave
	if saveData:
		DBName = "mailstats";
		DBHost = get_value(ConfigDB,'mailstats','DBHost',"localhost")
		DBPort = get_value(ConfigDB,'mailstats','DBPort',"3306")
		DBName = 'mailstats'
		DBPassw = 'mailstats'
		DBUser = 'mailstats'
		UnixSocket = "/var/lib/mysql/mysql.sock" 
		# see if the DB exists
		# Try to Establish a database connection
		try:
			conn = mysql.connector.connect(
				host=DBHost,
				user=DBUser,
				password=DBPassw,
				database=DBName,
				port=DBPort,
				unix_socket=UnixSocket
			)
			cursor = conn.cursor()
			# Create table if it doesn't exist
			cursor.execute("""
			CREATE TABLE IF NOT EXISTS SummaryLogs (
				id INT AUTO_INCREMENT PRIMARY KEY,
				Date DATE,
				Hour INT,
				logData TEXT
			)
			""")
			# and prune the DB here if needed.
			# Delete existing records for the given date
			try:
				delete_query = """
				DELETE FROM SummaryLogs
				WHERE Date = %s
				"""
				cursor.execute(delete_query, (analysis_date,))   #Don't forget the syntactic sugar of the extra comma to make it a tuple!
				# Get the number of records deleted
				rows_deleted = cursor.rowcount
				if rows_deleted > 0:
					print(f"Deleted {rows_deleted} rows for {analysis_date} ")
			except mysql.connector.Error as e:
				print(f"SQL Delete failed ({delete_query}) ({e}) ")
		except mysql.connector.Error as e:
			print(f"Unable to connect to {DBName} on {DBHost} port {DBPort} error ({e}) ")
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

	log_file = logs_dir+'current.log'
	log_entries,skip_count,ignored_count = read_in_relevant_log_file(log_file,anaysis_date_obj)
	print(f"Found {len(log_entries)} entries in log for for {anaysis_date_obj.strftime('%Y-%m-%d')} Ignored: {ignored_count} skipped: {skip_count}")
	summary_log_entries,skip_count = filter_summary_records(log_entries)
	print(f"Found {len(summary_log_entries)} summary entries and skipped {skip_count} entries")
	sorted_log_dict = sort_log_entries(summary_log_entries)
	print(f"Sorted {len(sorted_log_dict)} entries")

	columnHeaders = ['Count','WebMail','Local','MailMan','Relay','DMARC','Virus','RBL/DNS','Geoip.','Non.Conf.','Karma','Rej.Load','Del.Spam','Qued.Spam?','  Ham','TOTALS','PERCENT']
	# dict for each colum identifying plugin that increments count
	columnPlugin = [''] * 17
	columnPlugin[Hour] = [] 
	columnPlugin[WebMail] = []
	columnPlugin[Local] = [] 
	columnPlugin[MailMan] = []
	columnPlugin[DMARC] = ['dmarc'] 
	columnPlugin[Virus] = ['pattern_filter', 'virus::pattern_filter','virus::clamav'] 
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
	
	found_qpcodes = defaultdict(int)
	qpcodes_pattern = re.compile(r"(\(.*\)).*'")
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
	if sorted_len > 0:
		if isThonny:
			# Initial call to print the progress bar
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
			# Save the data here if necessary
			if saveData:
				save_summaries_to_db(anaysis_date_obj.strftime('%Y-%m-%d'),hour,parsed_data)
			# Increment Count in which headings it falls
			#Hourly count and column total
			columnCounts_2d[hour][Hour] += 1
			columnCounts_2d[ColTotals][Hour] += 1
			#Row Totals
			columnCounts_2d[hour][TOTALS] += 1
			#Total totals
			columnCounts_2d[ColTotals][TOTALS] += 1
			
			# first spot the fetchmail and local deliveries.
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
							if not 'msg denied before queued' in parsed_data['error-msg']:
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
			if parsed_data['action'] == '(queue)':
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
			
			#Now increment the column which the plugin name indicates
			if parsed_data['action'] == '(deny)' and parsed_data['error-plugin']:
				if parsed_data['error-plugin']:
					row = search_2d_list(parsed_data['error-plugin'],columnPlugin)
					if not row == -1:
						columnCounts_2d[hour][row] += 1
						columnCounts_2d[ColTotals][row] += 1
						# a few ad hoc extra extractons of data
						if row == Virus:
							match = virus_pattern.match(parsed_data['action1'])
							if match:
								found_viruses[match.group(1)] += 1
							else:
								found_viruses[parsed_data['action1']] += 1
					else:
						found_qpcodes[parsed_data['action1']] += 1
			if isThonny:
				print() #seperate the [progress bar]
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
			try:
				match = helo_pattern.match(data[1])
				if match:
					ip  = match.group(1)
					fqdn = match.group(2)
					if is_private_ip(ip):
						totalinternalsmtpsessions += 1
					else:
						totalexternalsmtpsessions += 1
					continue
			except Exception as e:
				print(f" Helo pattern error {e} {data[1]} {analysis_date}")
				continue
					
			#Pull out Geoip countries for analysis table
			try:
				match = geoip_pattern.match(data[1])
				if match:
					j += 1
					country = match.group(1)
					found_countries[country] += 1
					total_countries += 1
					continue
			except Exception as e:
				print(f" Geoip pattern error {e} {data[1]} {analysis_date}")
				continue
			
			#Pull out DMARC approvals
			match = dmarc_pattern.match(data[1])
			if match:
				DMARCOkCount += 1
				continue

			#Pull out type of connection
			match = connect_type_pattern.match(data[1])
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
	yLabels = [f'{i:02d}:00' for i in range(len(columnCounts_2d))]
	stacked_Bar_html = create_stacked_bar_graph(columnCounts_2d,columnHeaders,yLabels,html_page_dir+'stacked_bar_'+analysis_date+'.html')
	heatmap_html = create_heatmap(columnCounts_2d,columnHeaders,yLabels,html_page_dir+'heatmap_'+analysis_date+'.html')
	line_graph_html = create_line_chart(columnCounts_2d,columnHeaders,yLabels,html_page_dir+'line_graph_'+analysis_date+'.html')

	#Now apply the results to the chameleon template - main table
	# Path to the template file
	template_path = template_dir+'mailstats.html.pt'
	# Load the template
	with open(template_path, 'r') as template_file:
		template_content = template_file.read()
	# Create a Chameleon template instance
	try:
		template = PageTemplate(template_content)
		# Render the template with the 2D array data and column headers
		try:
			rendered_html = template(array_2d=columnCounts_2d, column_headers=columnHeaders, 
										reporting_date=analysis_date, title=hello_string, 
										version=version_string,
										nolinks=nolinks,
										stacked_bar_graph=stacked_Bar_html,
										heatmap=heatmap_html,
										line_graph=line_graph_html,
										PreviousDate=previous_date_str,
										NextDate=next_date_str,
										DomainName=DomainName
										)
		except Exception as e:
			print(f"Chameleon template Exception {e}")
	except Exception as e:
		print(f"Chameleon render Exception {e}")
		
	total_html = rendered_html
	# Add in the header information
	rendered_html = get_heading()
	total_html =  insert_string_after(total_html,rendered_html, "<!---Add in header information here -->")

	#add in the subservient tables..

	#qpsmtd codes
	qpsmtpd_headers = ["Reason",'Count','Percent']
	qpsmtpd_title = 'Qpsmtpd codes league table:'
	rendered_html = render_sub_table(qpsmtpd_title,qpsmtpd_headers,found_qpcodes)
	# Add it to the total 
	total_html = insert_string_after(total_html,rendered_html, "<!---Add in sub tables here -->")
	
	#Geoip Country codes
	geoip_headers  = ['Country','Count','Percent','Rejected?']
	geoip_title = 'Geoip results:'
	rendered_html = render_sub_table(geoip_title,geoip_headers,found_countries,get_character_in_reject_list)
	# Add it to the total 
	total_html = insert_string_after(total_html,rendered_html, "<!---Add in sub tables here -->")
	
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
		# Get a temporary file name
		temp_file_name = tempfile.mktemp()
		html_to_text(output_path+'.html',temp_file_name)
		print(f"Rendered HTML saved to {temp_file_name}")
		# and save it if required
		if not notextfile:
			text_file_path = output_path+'.txt'
			# and rename it
			os.rename(temp_file_name, text_file_path)
		else:
			text_file_path = temp_file_name
	else:
		text_file_path = ""
	
	
	html_content = None
	text_content = None
	#Now see if Email required
	if EmailTextOrHTML:
		if EmailTextOrHTML == "HTML" or EmailTextOrHTML == "Both":
			# Send html email (default))
			filepath = html_page_dir+"mailstats_for_"+analysis_date+".html"
			html_content = read_html_from_file(filepath)
			# Replace the Navigation by a "See in browser" prompt
			replace_str = f"<div class='divseeinbrowser' style='text-align:center;'><a class='seeinbrowser' href='http://{DomainName}/mailstats/mailstats_for_{analysis_date}.html'>See in browser</a></div>"
			html_content = replace_between(html_content, "<div class='linksattop'>", ">Next</a></div>", replace_str)
			if not noemailfile:
				# Write out the email html to a web page
				email_file = html_page_dir + "Email_mailstats_for_"+analysis_date
				with open(email_file+'.html', 'w') as output_file:
					output_file.write(html_content)
		if EmailTextOrHTML == "Text" or EmailTextOrHTML == "Both":
			#filepath = html_page_dir+"mailstats_for_"+analysis_date+".txt"
			if not text_file_path == "":
				text_content = read_text_from_file(text_file_path)
			else:
				text_content = "No text avaiable as html2text (was not "
		if EMailSMTPUser:
			# Send authenticated
			print("Sending authenticated")
			send_email(
				html_content=email_content, 
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
			print(f"Sending non authenticated {EmailAddress} {EmailHost}")
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
				print(f"Email Exception {e}")
