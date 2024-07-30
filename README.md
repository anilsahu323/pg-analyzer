Overview

fetch_configurations.py is a Python script designed to connect to a PostgreSQL High Availability (HA) cluster and collect the online status of its nodes. The script uses SSH for remote execution and supports output in both HTML and plain text formats.
Requirements

    Python 3.x
    Required Python libraries: paramiko, pyyaml, scp

Installation

    Install Dependencies:
    Install the required libraries using pip:

    bash

    pip install paramiko pyyaml scp

Usage

To use fetch_configurations.py, run the script from the command line with the following arguments:

bash

python3 fetch_configurations.py --node_ip <IP_ADDRESS> --username <USERNAME> --password <PASSWORD> --output_file <OUTPUT_FILE_PATH> --format <FORMAT>

Arguments

    --node_ip <IP_ADDRESS>: The IP address of the initial node to connect to.
    --username <USERNAME>: The username for SSH connection.
    --password <PASSWORD>: The password for SSH connection. If not provided, you will be prompted to enter it securely. Use --password prompt to explicitly indicate prompting.
    --output_file <OUTPUT_FILE_PATH>: The path to the file where the output will be written. Defaults to "output.html" if not specified.
    --format <FORMAT>: The format of the output file. Supported formats are html and text. Defaults to html.

Example

To fetch the status from a PostgreSQL node with the IP address 192.168.1.100, using username admin, and save the report in HTML format to your desktop, use:

bash

python3 fetch_configurations.py --node_ip 192.168.1.100 --username admin --password password123 --output_file /Users/yourusername/Desktop/status_report.html --format html

If you want to be prompted for the password, you can omit the --password argument:

bash

python3 fetch_configurations.py --node_ip 192.168.1.100 --username admin --output_file /Users/yourusername/Desktop/status_report.html --format html

To use plain text format instead:

bash

python3 fetch_configurations.py --node_ip 192.168.1.100 --username admin --password password123 --output_file /Users/yourusername/Desktop/status_report.txt --format text

Output

    HTML Format: The output will be formatted as an HTML file, providing a structured and styled report of the online status.
    Text Format: The output will be a plain text file, containing the raw status information.

Troubleshooting

    Authentication Errors: Ensure the username and password are correct and have necessary permissions.
    Connection Issues: Verify that the IP address is correct and the PostgreSQL node is accessible from your machine.
    Invalid Output Format: Check that the format specified is either html or text.

License

This script is released under the MIT License. See the LICENSE file for more details.
Contact

For any questions or issues, please contact Anil Sahu
