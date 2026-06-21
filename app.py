import socket
import threading
import re
import time
from flask import Flask, jsonify, render_template, request

app = Flask(__name__, template_folder='.')

PRINTER_IP = "192.168.0.109"
PRINTER_PORT = 8080

state = {
    "tool0": 0.0,
    "bed": 0.0,
    "status": "Connecting...",
    "filename": "No Active Job",
    "progress": 0.0,
    "time_elapsed": "00:00:00",
    "time_remaining": "Not Printing",
    "raw_logs": [],
    "sd_files": []
}

sock_connection = None
is_printing = False
total_print_seconds = 0
socket_lock = threading.Lock()

def format_time(seconds):
    if seconds <= 0: return "00:00:00"
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    return f"{h:02d}:{m:02d}:{s:02d}"

def parse_filename_time(filename):
    global total_print_seconds
    match_hm = re.search(r"(\d+)h(\d+)m", filename, re.IGNORECASE)
    if match_hm:
        hours = int(match_hm.group(1))
        minutes = int(match_hm.group(2))
        total_print_seconds = (hours * 3600) + (minutes * 60)
        return

    match_m = re.search(r"(\d+)m\.gcode", filename, re.IGNORECASE)
    if match_m:
        minutes = int(match_m.group(1))
        total_print_seconds = minutes * 60
        return

    total_print_seconds = 0

def printer_listener():
    global sock_connection, is_printing, total_print_seconds
    is_reading_file_list = False
    sd_files_accumulator = []

    while True:
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(5)
            s.connect((PRINTER_IP, PRINTER_PORT))
            sock_connection = s
            state["status"] = "Connected"
            buffer = ""

            while True:
                data = s.recv(1024).decode(errors='ignore')
                if not data: break
                buffer += data
                while "\n" in buffer:
                    line, buffer = buffer.split("\n", 1)
                    line = line.strip()
                    if not line: continue

                    state["raw_logs"].append(line)
                    if len(state["raw_logs"]) > 50: state["raw_logs"].pop(0)

                    if "Begin file list" in line:
                        is_reading_file_list = True
                        sd_files_accumulator = []
                        continue
                    elif "End file list" in line:
                        is_reading_file_list = False
                        state["sd_files"] = list(sd_files_accumulator)
                        continue

                    if is_reading_file_list:
                        parts = line.split()
                        if parts:
                            cleaned_filename = parts[0]
                            if cleaned_filename.lower().endswith(('.gcode', '.gco', '.g')):
                                sd_files_accumulator.append(cleaned_filename)
                        continue

                    t = re.search(r"T:([\d.]+)", line)
                    b = re.search(r"B:([\d.]+)", line)
                    if t: state["tool0"] = float(t.group(1))
                    if b: state["bed"] = float(b.group(1))

                    if "M997" in line:
                        m997_match = re.search(r"M997\s+(\w+)", line)
                        if m997_match:
                            mks_status = m997_match.group(1).upper()
                            if mks_status == "IDLE":
                                is_printing = False
                                state["status"] = "Idle"
                                state["filename"] = "No Active Job"
                                state["time_elapsed"] = "00:00:00"
                                state["time_remaining"] = "Not Printing"
                                state["progress"] = 0.0
                                total_print_seconds = 0
                            elif "PAUSE" in mks_status:
                                is_printing = True
                                state["status"] = "Paused"
                            elif "PRINT" in mks_status or mks_status == "BUSY":
                                is_printing = True
                                state["status"] = "Printing"

                    # 3. Filename Metadata (M994)
                    if "M994" in line and is_printing:
                        m994_match = re.search(r"M994\s+\d+:/([^; \n]+)", line)
                        if m994_match:
                            new_file = m994_match.group(1)
                            if state["filename"] != new_file:
                                state["filename"] = new_file
                                parse_filename_time(new_file)

                    if "M992" in line and is_printing:
                        m992_match = re.search(r"M992\s+(\d{2}:\d{2}:\d{2})", line)
                        if m992_match:
                            state["time_elapsed"] = m992_match.group(1)

        except Exception:
            state["status"] = "Disconnected"
            sock_connection = None
            is_printing = False
            time.sleep(4)

def printer_poller():
    global sock_connection
    while True:
        if sock_connection:
            try:
                with socket_lock:
                    sock_connection.sendall(b"M997\nM994\nM992\nM105\n")
            except Exception:
                pass
        time.sleep(1.2)

def smart_calculation_engine():
    global is_printing, total_print_seconds
    while True:
        if is_printing and total_print_seconds > 0:
            parts = state["time_elapsed"].split(":")
            if len(parts) == 3:
                elapsed_seconds = (int(parts[0]) * 3600) + (int(parts[1]) * 60) + int(parts[2])
                remaining_seconds = total_print_seconds - elapsed_seconds
                if remaining_seconds < 0: remaining_seconds = 0

                pct = (elapsed_seconds / total_print_seconds) * 100
                state["progress"] = round(min(100.0, pct), 1)
                state["time_remaining"] = format_time(remaining_seconds)
        elif is_printing and total_print_seconds == 0:
            state["time_remaining"] = "No time token found"
            state["progress"] = 0.0

        time.sleep(0.8)

threading.Thread(target=printer_listener, daemon=True).start()
threading.Thread(target=printer_poller, daemon=True).start()
threading.Thread(target=smart_calculation_engine, daemon=True).start()

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/data')
def data():
    return jsonify(state)

@app.route('/sd/list', methods=['GET'])
def list_sd_files():
    global sock_connection
    if not sock_connection:
        return jsonify([]), 400
    try:
        state["sd_files"] = []
        with socket_lock:
            sock_connection.sendall(b"M20\n")

        timeout = 1.2
        start_time = time.time()
        while time.time() - start_time < timeout:
            if state["sd_files"]:
                break
            time.sleep(0.05)

        return jsonify(state["sd_files"])
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/control/print_file', methods=['POST'])
def print_file():
    global sock_connection
    if not sock_connection:
        return jsonify({"status": "error", "message": "Printer offline"}), 400

    payload = request.get_json() or {}
    filename = payload.get("file")
    if not filename:
        return jsonify({"status": "error", "message": "No file parameter specified"}), 400

    try:
        with socket_lock:
            command_chain = f"M23 {filename}\nM24\n"
            sock_connection.sendall(command_chain.encode())
            sock_connection.sendall(b"M997\n")
        return jsonify({"status": "success", "message": f"Executing print for {filename}"})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/control/gcode', methods=['POST'])
def send_gcode():
    global sock_connection
    if not sock_connection:
        return jsonify({"status": "error", "message": "Link down"}), 400

    payload = request.get_json() or {}
    gcode_cmd = payload.get("cmd", "").strip()
    if not gcode_cmd:
        return jsonify({"status": "error", "message": "Empty command string"}), 400

    try:
        with socket_lock:
            formatted_cmd = f"{gcode_cmd}\n"
            sock_connection.sendall(formatted_cmd.encode())
        return jsonify({"status": "success"})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/control/<action>', methods=['POST'])
def control(action):
    global sock_connection
    if not sock_connection:
        return jsonify({"status": "error", "message": "Printer not reached"}), 400

    try:
        with socket_lock:
            if action == "start":
                sock_connection.sendall(b"M24\n")
            elif action == "pause":
                sock_connection.sendall(b"M25\n")
            elif action == "stop":
                sock_connection.sendall(b"M25\nM26\nM524\n")

            sock_connection.sendall(b"M997\nM105\n")

        return jsonify({"status": "success", "action": action})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
