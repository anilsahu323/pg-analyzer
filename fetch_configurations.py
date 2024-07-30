import warnings
import paramiko
import yaml
import argparse
import getpass
from scp import SCPClient
import traceback
import re
import socket
from datetime import datetime

warnings.filterwarnings("ignore", category=DeprecationWarning)

def create_ssh_client(server, port, user, password):
    try:
        client = paramiko.SSHClient()
        client.load_system_host_keys()
        client.set_missing_host_key_policy(paramiko.WarningPolicy)
        print(f"Attempting to connect to {server}:{port} with user {user}")
        client.connect(server, port, username=user, password=password)
        return client
    except socket.gaierror as e:
        print(f"Address-related error connecting to server {server}:{port}: {e}")
        raise
    except paramiko.AuthenticationException:
        print(f"Authentication failed for server {server}")
        raise
    except paramiko.SSHException as e:
        print(f"SSH error: {e}")
        raise
    except Exception as e:
        print(f"Unexpected error: {e}")
        raise

def fetch_file(client, remote_path, local_path):
    scp = SCPClient(client.get_transport())
    scp.get(remote_path, local_path)
    scp.close()

def fetch_latest_log_file(client, remote_dir, file_pattern):
    try:
        command = f"sudo su postgres -c 'ls -t {remote_dir}/{file_pattern}'"
        print(f"Executing command: {command}")
        
        stdin, stdout, stderr = client.exec_command(command)
        file_list = stdout.read().decode().split()
        print(f"Files in directory {remote_dir}: {file_list}")

        if not file_list:
            raise FileNotFoundError("No log files found")
        
        latest_file = file_list[0]
        
        print(f"Latest log file: {latest_file}")
        
        tail_command = f"sudo su postgres -c 'tail -n 20 {latest_file}'"
        print(f"tail command is :{tail_command}")
        stdin, stdout, stderr = client.exec_command(tail_command)
        log_content = stdout.read().decode()
        # print(f"{log_content}")
      
        return log_content
        
    except Exception as e:
        print(f"Error fetching latest log file: {e}")
        print(traceback.format_exc())
        return str(e)

def execute_command(client, command):
    stdin, stdout, stderr = client.exec_command(command)
    return stdout.read().decode(), stderr.read().decode()

def parse_host_port(host_port):
    host, port = host_port.split(':')
    return host, int(port)

def fetch_last_error_from_log_file(client, remote_dir, file_pattern):
    try:
        command = f"sudo su postgres -c 'ls -t {remote_dir}/{file_pattern}'"
        print(f"Executing command: {command}")
        
        stdin, stdout, stderr = client.exec_command(command)
        file_list = stdout.read().decode().split()
        print(f"Files in directory {remote_dir}: {file_list}")

        if not file_list:
            raise FileNotFoundError("No log files found")
        
        latest_file = file_list[0]
        
        print(f"Latest log file: {latest_file}")
        
        tail_command = f"sudo su postgres -c 'tail -n 100000 {latest_file}'"
        stdin, stdout, stderr = client.exec_command(tail_command)
        log_content = stdout.read().decode()

        # Extract last error entry
        error_pattern = r'(FATAL.*|ERROR.*|Traceback[\s\S]*?)(?=^\w|\Z)' 
        errors = re.findall(error_pattern, log_content, re.MULTILINE)
        last_error = errors[-1] if errors else "No recent errors found."

        return last_error
        
    except Exception as e:
        print(f"Error fetching last error from log file: {e}")
        print(traceback.format_exc())
        return str(e)

def fetch_configuration_and_status(client):
    try:
        patroni_conf_content, _ = execute_command(client, 'sudo -u postgres cat /etc/patroni/patroni.yml')
        patroni_conf = yaml.safe_load(patroni_conf_content)
        all_hosts = patroni_conf['etcd']['hosts'].split(',')

        cluster_hosts = []
        for host_port in all_hosts:
            host, port = parse_host_port(host_port)
            cluster_hosts.append(host)

        haproxy_conf, haproxy_err = execute_command(client, 'sudo -u postgres cat /etc/haproxy/haproxy.cfg')
        etcd_conf, etcd_err = execute_command(client, 'sudo cat /etc/etcd/etcd.yml')
        pg_data_dir = patroni_conf['postgresql']['data_dir']
        pg_log_dir = f"{pg_data_dir}/log"
        postgres_conf, postgres_err = execute_command(client, f'sudo -u postgres cat {pg_data_dir}/postgresql.conf')

        patroni_last_error = fetch_last_error_from_log_file(client, '/var/log/patroni', 'patroni*.log')
        etcd_last_error = fetch_last_error_from_log_file(client, '/var/log/etcd', 'etcd*.log')
        postgres_last_error = fetch_last_error_from_log_file(client, pg_log_dir, 'postgresql*.log')

        haproxy_status, haproxy_status_err = execute_command(client, 'sudo systemctl status haproxy')
        patroni_status, patroni_status_err = execute_command(client, 'sudo systemctl status patroni')
        etcd_status, etcd_status_err = execute_command(client, 'sudo systemctl status etcd')
        postgres_status, postgres_status_err = execute_command(client, 'sudo systemctl status era_postgres')
        postgres_process_status, postgres_process_status_err = execute_command(client, 'ps -ef | grep postgres')
        last_reboot_status, last_reboot_status_err = execute_command(client, 'sudo last reboot')
        patronictl_path, _ = execute_command(client, 'which patronictl')
        patronictl_path = patronictl_path.strip()
        if not patronictl_path:
            patronictl_path = "patronictl"
        
        patronictl_status, patronictl_status_err = execute_command(client, f'sudo {patronictl_path} -c /etc/patroni/patroni.yml list')
        patroni_log_content = fetch_latest_log_file(client, '/var/log/patroni', 'patroni*.log')
        etcd_log_content = fetch_latest_log_file(client, '/var/log/etcd', 'etcd*.log')
        postgres_log_content = fetch_latest_log_file(client, pg_log_dir, 'postgresql*.log')
        disk_usage, disk_usage_err = execute_command(client, 'df -h')
        top_memory_processes, top_memory_processes_err = execute_command(client, 'ps aux --sort=-%mem | head -n 11')
        return {
            'cluster_hosts': cluster_hosts,
            'haproxy_conf': haproxy_conf,
            'etcd_conf': etcd_conf,
            'postgres_conf': postgres_conf,
            'haproxy_status': haproxy_status,
            'patroni_status': patroni_status,
            'etcd_status': etcd_status,
            'postgres_status': postgres_status,
            'postgres_process_status': postgres_process_status,
            'patronictl_status': patronictl_status,
            'patroni_last_error': patroni_last_error,
            'etcd_last_error': etcd_last_error,
            'postgres_last_error': postgres_last_error,
            'last_reboot_status': last_reboot_status,
            'patroni_log_content': patroni_log_content,
            'etcd_log_content':etcd_log_content,
            'postgres_log_content':postgres_log_content,
            'disk_usage':disk_usage,
            'top_memory_processes':top_memory_processes,
            'errors': {
                'haproxy_err': haproxy_err,
                'etcd_err': etcd_err,
                'postgres_err': postgres_err,
                'haproxy_status_err': haproxy_status_err,
                'patroni_status_err': patroni_status_err,
                'etcd_status_err': etcd_status_err,
                'postgres_status_err': postgres_status_err,
                'postgres_process_status_err': postgres_process_status_err,
                'patronictl_status_err': patronictl_status_err,
                'last_reboot_status_err':last_reboot_status_err,
                'disk_usage_err':disk_usage_err,
                'top_memory_processes_err':top_memory_processes_err
            }
        }
    except Exception as e:
        print(f"Error fetching configuration and status: {e}")
        print(traceback.format_exc())
        return {}

def generate_html_report(results, output_file):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    html_content = f"""
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>PG HA Cluster Analysis</title>
        <style>
            body {{ font-family: Arial, sans-serif; margin: 20px; }}
            h1 {{ color: #333; }}
            h2 {{ color: #555; }}
            .node-section {{ margin-bottom: 20px; }}
            .expandable {{ cursor: pointer; color: #0066cc; }}
            .expandable-content {{ display: none; margin-top: 10px; }}
            pre {{ background-color: #f4f4f4; padding: 10px; border: 1px solid #ddd; }}
        </style>
    </head>
    <body>
        <h1>Current status of PG HA Cluster</h1>
        <p>Time of Analysis: {timestamp}</p>
    """

    for result in results:
        html_content += f"""
        <div class="node-section">
            <h2>Node: {result['host']}</h2>
            <div>
                <span class="expandable">HAProxy Configuration</span>
                <div class="expandable-content"><pre>{result['haproxy_conf']}</pre></div>
            </div>
            <div>
                <span class="expandable">etcd Configuration</span>
                <div class="expandable-content"><pre>{result['etcd_conf']}</pre></div>
            </div>
            <div>
                <span class="expandable">PostgreSQL Configuration</span>
                <div class="expandable-content"><pre>{result['postgres_conf']}</pre></div>
            </div>
            <div>
                <span class="expandable">HAProxy Service Status</span>
                <div class="expandable-content"><pre>{result['haproxy_status']}</pre></div>
            </div>
            <div>
                <span class="expandable">Patroni Service Status</span>
                <div class="expandable-content"><pre>{result['patroni_status']}</pre></div>
            </div>
            <div>
                <span class="expandable">etcd Service Status</span>
                <div class="expandable-content"><pre>{result['etcd_status']}</pre></div>
            </div>
            <div>
                <span class="expandable">PostgreSQL Service Status</span>
                <div class="expandable-content"><pre>{result['postgres_status']}</pre></div>
            </div>
            <div>
                <span class="expandable">PostgreSQL Process Status</span>
                <div class="expandable-content"><pre>{result['postgres_process_status']}</pre></div>
            </div>
            <div>
                <span class="expandable">Patroni Cluster Status</span>
                <div class="expandable-content"><pre>{result['patronictl_status']}</pre></div>
            </div>
            <div>
                <span class="expandable">Patroni Log Content</span>
                <div class="expandable-content"><pre>{result['patroni_log_content']}</pre></div>
            </div>
            <div>
                <span class="expandable">etcd Log Content</span>
                <div class="expandable-content"><pre>{result['etcd_log_content']}</pre></div>
            </div>
            <div>
                <span class="expandable">PostgreSQL Log Content</span>
                <div class="expandable-content"><pre>{result['postgres_log_content']}</pre></div>
            </div>
            <div>
                <span class="expandable">Patroni Last Error</span>
                <div class="expandable-content"><pre>{result['patroni_last_error']}</pre></div>
            </div>
            <div>
                <span class="expandable">etcd Last Error</span>
                <div class="expandable-content"><pre>{result['etcd_last_error']}</pre></div>
            </div>
            <div>
                <span class="expandable">PostgreSQL Last Error</span>
                <div class="expandable-content"><pre>{result['postgres_last_error']}</pre></div>
            </div>
            <div>
                <span class="expandable">Node Last Reboot</span>
                <div class="expandable-content"><pre>{result['last_reboot_status']}</pre></div>
            </div>
            <div>
                <span class="expandable">Total Disk Usage</span>
                <div class="expandable-content"><pre>{result['disk_usage']}</pre></div>
            </div>
            <div>
                <span class="expandable">Top Consumer Process</span>
                <div class="expandable-content"><pre>{result['top_memory_processes']}</pre></div>
            </div>
        </div>
        """

    html_content += """
        <script>
            document.querySelectorAll('.expandable').forEach(function(element) {
                element.addEventListener('click', function() {
                    var content = this.nextElementSibling;
                    content.style.display = content.style.display === 'none' ? 'block' : 'none';
                });
            });
        </script>
    </body>
    </html>
    """

    with open(output_file, 'w') as f:
        f.write(html_content)

def generate_text_report(results, output_file):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    text_content = f"Analysis of PG HA Cluster\n"
    text_content += f"Time of Analysis: {timestamp}\n\n"

    for result in results:
        text_content += f"Node: {result['host']}\n"
        text_content += "HAProxy Configuration:\n"
        text_content += result['haproxy_conf'] + "\n"
        text_content += "etcd Configuration:\n"
        text_content += result['etcd_conf'] + "\n"
        text_content += "PostgreSQL Configuration:\n"
        text_content += result['postgres_conf'] + "\n"
        text_content += "HAProxy Service Status:\n"
        text_content += result['haproxy_status'] + "\n"
        text_content += "Patroni Service Status:\n"
        text_content += result['patroni_status'] + "\n"
        text_content += "etcd Service Status:\n"
        text_content += result['etcd_status'] + "\n"
        text_content += "PostgreSQL Service Status:\n"
        text_content += result['postgres_status'] + "\n"
        text_content += "PostgreSQL Process Status:\n"
        text_content += result['postgres_process_status'] + "\n"
        text_content += "Patroni Cluster Status:\n"
        text_content += result['patronictl_status'] + "\n"
        text_content += "Patroni Log Content:\n"
        text_content += result['patroni_log_content'] + "\n"
        text_content += "etcd Log Content:\n"
        text_content += result['etcd_log_content'] + "\n"
        text_content += "PostgreSQL Log Content:\n"
        text_content += result['postgres_log_content'] + "\n"
        text_content += "Patroni Last Error:\n"
        text_content += result['patroni_last_error'] + "\n"
        text_content += "etcd Last Error:\n"
        text_content += result['etcd_last_error'] +"\n"
        text_content += "PostgreSQL Last Error:\n"
        text_content += result['postgres_last_error'] +"\n"
        text_content += "Node Last Reboot:\n"
        text_content += result['last_reboot_status'] +"\n"
        text_content += "Total Disk Usage:\n"
        text_content += result['disk_usage'] +"\n"
        text_content += "Top Consumer Process:\n"
        text_content += result['top_memory_processes'] +"\n"
        "\n\n"

    with open(output_file, 'w') as f:
        f.write(text_content)

def main():
    parser = argparse.ArgumentParser(description="Fetch configurations and statuses from PostgreSQL cluster nodes.")
    parser.add_argument("--node_ip", help="IP address of the initial node to connect to")
    parser.add_argument("--username", help="Username for SSH connection")
    parser.add_argument("--password", help="Password for SSH connection (prompted if not provided)", nargs='?', const='prompt')
    parser.add_argument("--output_file", help="File to write the output (optional)", default="output.html")
    parser.add_argument("--format", help="Output format (html or text)", choices=['html', 'text'], default='html')
    args = parser.parse_args()

    if not args.node_ip:
        args.node_ip = input("Enter the IP address of the initial node to connect to: ")
    if not args.username:
        args.username = input("Enter the SSH username: ")
    if args.password == 'prompt' or not args.password:
        args.password = getpass.getpass("Enter the SSH password: ")

    primary_node = {'host': args.node_ip, 'port': 22, 'user': args.username, 'password': args.password}
    
    ssh_client = create_ssh_client(primary_node['host'], primary_node['port'], primary_node['user'], primary_node['password'])
    primary_config_data = fetch_configuration_and_status(ssh_client)
    
    cluster_hosts = primary_config_data.get('cluster_hosts', [])
    
    results = []

    for host in cluster_hosts:
        node_client = create_ssh_client(host, 22, primary_node['user'], primary_node['password'])
        config_data = fetch_configuration_and_status(node_client)
        node_client.close()
        
        result = {
            'host': host,
            'haproxy_conf': config_data.get('haproxy_conf', ''),
            'etcd_conf': config_data.get('etcd_conf', ''),
            'postgres_conf': config_data.get('postgres_conf', ''),
            'haproxy_status': config_data.get('haproxy_status', ''),
            'patroni_status': config_data.get('patroni_status', ''),
            'etcd_status': config_data.get('etcd_status', ''),
            'postgres_status': config_data.get('postgres_status', ''),
            'postgres_process_status': config_data.get('postgres_process_status', ''),
            'patronictl_status': config_data.get('patronictl_status', ''),
            'patroni_log_content': config_data.get('patroni_log_content', ''),
            'etcd_log_content': config_data.get('etcd_log_content', ''),
            'postgres_log_content': config_data.get('postgres_log_content', ''),
            # 'errors': config_data.get('errors', {}),
            'patroni_last_error': config_data.get('patroni_last_error', 'No Patroni error found'),
            'etcd_last_error': config_data.get('etcd_last_error', 'No etcd error found'),
            'postgres_last_error': config_data.get('postgres_last_error', 'No PostgreSQL error found'),
            'last_reboot_status': config_data.get('last_reboot_status', ''),
            'disk_usage': config_data.get('disk_usage',''),
            'top_memory_processes': config_data.get('top_memory_processes','')
        }
        results.append(result)

    if args.format == 'html':
        generate_html_report(results, args.output_file)
    else:
        generate_text_report(results, args.output_file)

    ssh_client.close()

if __name__ == "__main__":
    main()
