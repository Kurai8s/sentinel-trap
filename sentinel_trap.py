import socket
import threading
import logging
import paramiko
import json
import sqlite3
import os
from datetime import datetime, timezone

logging.getLogger("paramiko").setLevel(logging.CRITICAL)

# 1. Database
def init_db():
    conn = sqlite3.connect('sentinel_data.db', check_same_thread=False)
    conn.execute('''
        CREATE TABLE IF NOT EXISTS attack_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT, source_ip TEXT, username TEXT,
            password TEXT, event_type TEXT
        )
    ''')
    conn.commit()
    return conn

db_conn = init_db()

# 2. SIEM-ready CEF logging
LOG_DIR = 'logs'
os.makedirs(LOG_DIR, exist_ok=True)
CEF_LOG = os.path.join(LOG_DIR, 'sentinel_cef.log')

def log_attack(client_addr, username, password):
    log_data = {
        "timestamp": datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'),
        "source_ip": client_addr[0],
        "username": username,
        "password": password,
        "event_type": "ssh_auth_attempt"
    }
    db_conn.execute('''
        INSERT INTO attack_logs (timestamp, source_ip, username, password, event_type)
        VALUES (?, ?, ?, ?, ?)
    ''', (log_data["timestamp"], log_data["source_ip"], log_data["username"],
          log_data["password"], log_data["event_type"]))
    db_conn.commit()

    cef = (f"CEF:0|SentinelTrap|SSH-Honeypot|1.0|1001|SSH Auth Attempt|7|"
           f"src={log_data['source_ip']} suser={username} dpt=2222 "
           f"rt={log_data['timestamp']} msg=Password captured: {password}")
    with open(CEF_LOG, 'a', encoding='utf-8') as f:
        f.write(cef + '\n')

    print(f"[!] Captured -> {json.dumps(log_data)}")
    print(f"[SIEM] CEF    -> {cef}")

# 3. Honeypot SSH dengan kunci persisten
def get_host_key():
    key_path = 'honeypot_rsa.key'
    if os.path.exists(key_path):
        return paramiko.RSAKey.from_private_key_file(key_path)
    new_key = paramiko.RSAKey.generate(2048)
    new_key.write_private_key_file(key_path)
    print("[*] Generated new host key -> honeypot_rsa.key")
    return new_key

host_key = get_host_key()

class HoneypotServer(paramiko.ServerInterface):
    def __init__(self, client_addr):
        self.client_addr = client_addr
    def check_auth_password(self, username, password):
        log_attack(self.client_addr, username, password)
        return paramiko.AUTH_FAILED

def handle_client(client_socket, client_addr):
    transport = None
    try:
        transport = paramiko.Transport(client_socket)
        transport.add_server_key(host_key)
        transport.start_server(server=HoneypotServer(client_addr))
        channel = transport.accept(20)
        if channel is not None:
            channel.close()
    except (paramiko.SSHException, ConnectionResetError, OSError):
        pass
    except Exception as e:
        print(f"[x] Error from {client_addr[0]}: {e}")
    finally:
        if transport is not None:
            try: transport.close()
            except Exception: pass
        try: client_socket.close()
        except Exception: pass

# 4. Main loop + graceful shutdown
def main():
    shutdown_event = threading.Event()
    threads = []
    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server_socket.bind(('0.0.0.0', 2222))
    server_socket.listen(100)
    server_socket.settimeout(1.0)

    print("[*] SentinelTrap SSH Honeypot listening on port 2222...")
    print("[*] Database: sentinel_data.db")
    print("[*] CEF Log: logs/sentinel_cef.log")
    print("[*] Press Ctrl+C to stop gracefully.")

    try:
        while not shutdown_event.is_set():
            try:
                client_socket, client_addr = server_socket.accept()
            except socket.timeout:
                continue
            except OSError:
                break
            t = threading.Thread(target=handle_client,
                                 args=(client_socket, client_addr), daemon=True)
            t.start()
            threads.append(t)
    except KeyboardInterrupt:
        print("\n[*] Ctrl+C detected -> shutting down gracefully...")
        shutdown_event.set()
    finally:
        try: server_socket.close()
        except Exception: pass
        for t in threads:
            t.join(timeout=2)
        try: db_conn.close()
        except Exception: pass
        print("[*] SentinelTrap stopped. Logs saved.")

if __name__ == '__main__':
    main()