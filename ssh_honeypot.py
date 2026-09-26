import json
import os
import socket
from datetime import datetime
from pathlib import Path
import paramiko

HOST = "0.0.0.0"
PORT = 2222
HOST_KEY_FILE = "mirage_ed25519_host_key"
LOG_DIR = Path("logs")
EVENT_LOG = LOG_DIR / "events.jsonl"

def log_event(event, source_ip, source_port, username=None, **details):
    LOG_DIR.mkdir(exist_ok=True)
    record = {
        "timestamp": datetime.now().astimezone().isoformat(timespec="seconds"),
        "source_ip": source_ip,
        "source_port": source_port,
        "username": username,
        "event": event,
        **details
    }
    with EVENT_LOG.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record) + "\n")
    print(f"[LOG] {record}")

class MirageSSHServer(paramiko.ServerInterface):
    def __init__(self, address):
        self.username = None
        self.authenticated = False
        self.address = address

    def check_auth_password(self, username, password):
        self.username = username
        log_event("authentication_attempt", self.address[0], self.address[1], username=username)
        if username == "admin" and password == os.getenv("MIRAGE_HONEYPOT_PASSWORD","change-me"):
            self.authenticated = True
            print("[AUTH] Accepted")
            log_event("authentication_success", self.address[0], self.address[1], username=username)
            return paramiko.AUTH_SUCCESSFUL
        print("[AUTH] Rejected")
        log_event("authentication_failed", self.address[0], self.address[1], username=username)
        return paramiko.AUTH_FAILED

    def get_allowed_auths(self, username):
        return "password"

    def check_channel_request(self, kind, chanid):
        if kind == "session":
            return paramiko.OPEN_SUCCEEDED
        return paramiko.OPEN_FAILED_ADMINISTRATIVELY_PROHIBITED

    def check_channel_pty_request(self, channel, term, width, height, pixelwidth, pixelheight, modes):
        return True

    def check_channel_shell_request(self, channel):
        return True

def send(channel, text):
    channel.send(text.encode())

def handle_shell(channel, username, address):
    log_event("session_started", address[0], address[1], username=username)
    print(f"[SESSION] Shell started for {username} from {address[0]}:{address[1]}")
    send(channel, "\r\nWelcome to Mirage SSH Honeypot\r\n")
    send(channel, "This is a monitored environment.\r\n")
    send(channel, "Type 'help' for available commands.\r\n\r\n")
    send(channel, "mirage@server:~$ ")
    command_buffer = ""

    while True:
        data = channel.recv(1024)
        if not data:
            break

        for byte in data:
            if byte in (10, 13):
                send(channel, "\r\n")
                command = command_buffer.strip()
                command_buffer = ""

                if not command:
                    send(channel, "mirage@server:~$ ")
                    continue

                log_event("command", address[0], address[1], username=username, command=command)

                if command == "exit":
                    send(channel, "Goodbye.\r\n")
                    log_event("session_closed", address[0], address[1], username=username, reason="exit")
                    channel.close()
                    return
                elif command == "help":
                    response = "Available commands:\r\n  help\r\n  whoami\r\n  pwd\r\n  ls\r\n  id\r\n  uname -a\r\n  exit\r\n"
                elif command == "whoami":
                    response = "admin\r\n"
                elif command == "pwd":
                    response = "/home/admin\r\n"
                elif command == "ls":
                    response = "documents  downloads  scripts  .ssh\r\n"
                elif command == "id":
                    response = "uid=1000(admin) gid=1000(admin) groups=1000(admin)\r\n"
                elif command == "uname -a":
                    response = "Linux mirage-server 6.8.0-generic x86_64 GNU/Linux\r\n"
                else:
                    response = f"bash: {command}: command not found\r\n"

                send(channel, response)
                send(channel, "mirage@server:~$ ")

            elif byte in (8, 127):
                if command_buffer:
                    command_buffer = command_buffer[:-1]
                    send(channel, "\b \b")
            elif byte >= 32:
                char = chr(byte)
                command_buffer += char
                send(channel, char)

    log_event("session_closed", address[0], address[1], username=username, reason="connection_closed")
    print(f"[SESSION] Closed {address[0]}:{address[1]}")
    channel.close()

def main():
    LOG_DIR.mkdir(exist_ok=True)
    host_key = paramiko.Ed25519Key.from_private_key_file(HOST_KEY_FILE)
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server.bind((HOST, PORT))
    server.listen(5)

    print(f"[*] Mirage SSH Honeypot listening on {HOST}:{PORT}")
    print(f"[*] Event log: {EVENT_LOG}")

    while True:
        client, address = server.accept()
        print(f"[+] Connection from {address[0]}:{address[1]}")
        log_event("connection", address[0], address[1])

        transport = paramiko.Transport(client)
        transport.add_server_key(host_key)
        ssh_server = MirageSSHServer(address)

        try:
            transport.start_server(server=ssh_server)
            channel = transport.accept(20)

            if channel is None:
                print("[-] No SSH channel opened")
                log_event("channel_failed", address[0], address[1])
                transport.close()
                continue

            print("[+] SSH channel established")
            if ssh_server.authenticated:
                handle_shell(channel, ssh_server.username, address)
            else:
                print("[-] Channel opened without authentication")
                channel.close()

        except Exception as exc:
            print(f"[!] SSH error: {exc}")
            log_event("error", address[0], address[1], error=str(exc))
        finally:
            transport.close()

if __name__ == "__main__":
    main()
