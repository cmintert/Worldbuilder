import subprocess
import socket
import os


def is_neo4j_running(host="localhost", port=7687):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        try:
            s.connect((host, port))
            return True
        except (ConnectionRefusedError, socket.timeout):
            return False


neo4j_bin_path = os.getenv("NEO4J_BIN_PATH", "D:\neo4j-community-4.4.34\bin")
start_command = os.path.join(neo4j_bin_path, "neo4j") + " start"

if is_neo4j_running():
    print("Neo4j is already running.")
else:
    try:
        subprocess.run(start_command, check=True, shell=True)
        print("Neo4j started successfully.")
    except subprocess.CalledProcessError as e:
        print(f"Failed to start Neo4j: {e}")
