from flask import Flask, render_template_string, request, jsonify
import serial
import time
import threading
from datetime import datetime
import os

app = Flask(__name__)

# --- 設定・管理変数 ---
SERIAL_PORT = 'COM4' 
LOG_FILE = "mist_log.txt"
LIMIT_DURATION = 300  # 累計噴霧制限（秒）
ser = None

schedule = {"time": "未設定", "duration": 5, "pulse": False}
status = {
    "is_running": False,
    "is_spraying": False,  # ★追加：今まさに噴射中か
    "total_sprayed": 0,
    "is_locked": False,
    "last_executed": "なし"
}
last_executed_minute = ""

# --- シリアル初期化 ---
try:
    ser = serial.Serial(port=SERIAL_PORT, baudrate=115200, timeout=1)
    time.sleep(2)
    print(f"Connected to {SERIAL_PORT}")
except Exception as e:
    print(f"Connection Error: {e}")

# --- ヘルパー関数 ---
def write_log(message):
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(f"[{now}] {message}\n")

def send_command(cmd):
    if ser and ser.is_open:
        ser.write(f"{cmd}\n".encode())

# --- 制御メインロジック ---
def monitor_time():
    global last_executed_minute, status
    write_log("システム起動: 時刻監視を開始しました。")
    
    while True:
        now = datetime.now()
        current_time_str = now.strftime("%H:%M")
        
        if schedule["time"] == current_time_str and last_executed_minute != current_time_str and not status["is_locked"]:
            last_executed_minute = current_time_str
            status["is_running"] = True
            status["last_executed"] = now.strftime("%H:%M:%S")
            
            cycle_count = 0
            while status["is_running"]:
                cycle_count += 1
                if status["total_sprayed"] >= LIMIT_DURATION:
                    status["is_locked"] = True
                    status["is_running"] = False
                    write_log("⚠️ 警告: 累計制限超過。強制停止。")
                    break

                # ログ
                mode_label = 'PULSE' if schedule['pulse'] else 'NORMAL'
                if cycle_count == 1:
                    write_log(f"実行: {schedule['duration']}秒噴霧開始 ({mode_label})")
                else:
                    write_log(f"スヌーズ開始: {schedule['duration']}秒噴霧 ({mode_label})")
                
                # --- 噴射ルーチン ---
                status["is_spraying"] = True  # ★噴霧ON
                start_cycle_time = time.time()
                while time.time() - start_cycle_time < int(schedule["duration"]):
                    if not status["is_running"]: break
                    
                    if schedule["pulse"]:
                        send_command("ON"); time.sleep(0.5)
                        send_command("OFF"); time.sleep(0.5)
                    else:
                        send_command("ON"); time.sleep(0.5)
                    
                    status["total_sprayed"] += 0.5
                    if status["total_sprayed"] >= LIMIT_DURATION:
                        status["is_locked"] = True; break

                send_command("OFF")
                status["is_spraying"] = False  # ★噴霧OFF
                # ------------------

                if not status["is_running"] or status["is_locked"]: break
                write_log("待機中...")
                time.sleep(10)
            
        time.sleep(1)

threading.Thread(target=monitor_time, daemon=True).start()

# --- UI (CSSアニメーションとJSステータス取得を修正) ---
HTML = """
<!DOCTYPE html>
<html lang="ja">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Smart Mist Controller</title>
    <style>
        :root { --primary: #4facfe; --glow: #00f2fe; --stop: #ff4b2b; --bg: #e0e5ec; }
        body { background-color: var(--bg); font-family: 'Segoe UI', sans-serif; display: flex; justify-content: center; align-items: center; min-height: 100vh; margin: 0; color: #444; }
        .container { background: var(--bg); padding: 30px; border-radius: 30px; box-shadow: 20px 20px 60px #bec3c9, -20px -20px 60px #ffffff; width: 360px; text-align: center; }
        .input-group { margin-bottom: 20px; text-align: left; padding: 0 10px; }
        label { font-size: 0.8rem; font-weight: bold; color: #888; display: block; margin-bottom: 5px; }
        input { width: 100%; padding: 12px; border: none; border-radius: 10px; background: var(--bg); box-shadow: inset 6px 6px 12px #bec3c9, inset -6px -6px 12px #ffffff; box-sizing: border-box; outline: none; }
        
        .safety-zone { margin: 20px 0; text-align: left; padding: 0 10px; }
        .bar-bg { height: 10px; background: var(--bg); border-radius: 5px; box-shadow: inset 2px 2px 5px #bec3c9, inset -2px -2px 5px #ffffff; overflow: hidden; }
        .bar-fill { height: 100%; background: linear-gradient(90deg, #4facfe, #00f2fe); width: 0%; transition: 0.5s; }
        .locked { background: var(--stop) !important; }

        .toggle-group { display: flex; justify-content: space-between; align-items: center; padding: 10px; }
        .switch { position: relative; width: 50px; height: 26px; }
        .switch input { opacity: 0; width: 0; height: 0; }
        .slider { position: absolute; cursor: pointer; top: 0; left: 0; right: 0; bottom: 0; background-color: var(--bg); transition: .4s; border-radius: 34px; box-shadow: 4px 4px 8px #bec3c9, -4px -4px 8px #ffffff; }
        .slider:before { position: absolute; content: ""; height: 18px; width: 18px; left: 4px; bottom: 4px; background-color: #abb2b9; transition: .4s; border-radius: 50%; }
        input:checked + .slider:before { transform: translateX(24px); background: var(--primary); }

        .btn { width: 100%; padding: 15px; margin-top: 15px; border: none; border-radius: 15px; font-weight: bold; cursor: pointer; box-shadow: 5px 5px 15px #bec3c9, -5px -5px 15px #ffffff; transition: 0.2s; }
        .btn:active { transform: scale(0.98); box-shadow: 2px 2px 5px #bec3c9, -2px -2px 5px #ffffff; }
        .btn-save { background: linear-gradient(145deg, #55b9f3, #469ce6); color: white; }
        .btn-stop { background: linear-gradient(145deg, #ff5131, #e64427); color: white; }
        
        .status-display { margin-top: 25px; padding: 15px; border-radius: 20px; background: var(--bg); box-shadow: inset 4px 4px 8px #bec3c9, inset -4px -4px 8px #ffffff; font-size: 0.85rem; }
        
        /* --- 雲アイコンとアニメーション修正 --- */
        .mist-icon { 
            font-size: 3.5rem; 
            display: inline-block;
            margin-bottom: 10px;
            transition: 0.5s;
            color: #fff; /* 雲自体は白 */
            /* 初期状態の薄い光 */
            filter: drop-shadow(0 0 5px rgba(79, 172, 254, 0.4));
        }

        /* ★追加：噴霧中（呼吸のような点滅）のアニメーションCSS */
        .spraying-glow {
            animation: breatheGlow 2.5s infinite ease-in-out;
        }

        @keyframes breatheGlow {
            0%, 100% { 
                filter: drop-shadow(0 0 10px var(--glow)) drop-shadow(0 0 20px var(--primary));
                transform: scale(1.0);
            }
            50% { 
                filter: drop-shadow(0 0 5px rgba(79, 172, 254, 0.2));
                transform: scale(0.95); /* 少し縮むことで呼吸感を出す */
            }
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="mist-icon" id="mistIcon">☁️</div>
        <h1 style="color:#666; font-size:1.4rem; margin-top:0;">Mist Controller</h1>
        
        <div class="safety-zone">
            <label id="limitLabel">WATER LIMIT (0/300s)</label>
            <div class="bar-bg"><div id="safetyBar" class="bar-fill"></div></div>
        </div>

        <div class="input-group">
            <label>START TIME</label>
            <input type="time" id="mistTime" value="{{ config_time }}">
        </div>
        <div class="input-group">
            <label>DURATION (SEC)</label>
            <input type="number" id="mistDuration" value="{{ config_duration }}">
        </div>
        <div class="toggle-group">
            <label style="margin:0;">PULSE MODE</label>
            <label class="switch">
                <input type="checkbox" id="pulseMode" {% if config_pulse %}checked{% endif %}>
                <span class="slider"></span>
            </label>
        </div>
        <button class="btn btn-save" onclick="saveSettings()">SCHEDULE</button>
        <button class="btn btn-stop" onclick="stopMist()">EMERGENCY STOP</button>
        <div class="status-display" id="statusArea">
            Connecting...
        </div>
    </div>

    <script>
        const icon = document.getElementById('mistIcon');

        // ★JSステータス取得ロジックの修正
        function updateStatus() {
            fetch('/get_status').then(r => r.json()).then(data => {
                // セーフティバー
                const percent = (data.total_sprayed / 300) * 100;
                const bar = document.getElementById('safetyBar');
                bar.style.width = percent + '%';
                if(data.is_locked) bar.classList.add('locked');
                
                // ラベル
                document.getElementById('limitLabel').innerText = `WATER LIMIT (${Math.floor(data.total_sprayed)}/300s)`;
                document.getElementById('statusArea').innerHTML = `
                    Last: ${data.last_executed}<br>
                    Status: ${data.is_locked ? '<span style="color:red;font-weight:bold">LOCKED (Empty)</span>' : 'Ready'}
                `;

                // ★追加：is_sprayingの状態を見てCSSクラスを付け外しする
                if (data.is_spraying) {
                    icon.classList.add('spraying-glow'); // 呼吸アニメーションON
                } else {
                    icon.classList.remove('spraying-glow'); // OFF
                }
            }).catch(e => {
                document.getElementById('statusArea').innerText = "Connection Error";
            });
        }
        // デモ映えのために取得間隔を1秒にする（元は2秒）
        setInterval(updateStatus, 1000);

        // (saveSettings, stopMist関数は変更なし)
        function saveSettings() {
            const time = document.getElementById('mistTime').value;
            const duration = document.getElementById('mistDuration').value;
            const pulse = document.getElementById('pulseMode').checked;
            fetch('/set_schedule', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ time: time, duration: duration, pulse: pulse })
            }).then(() => alert('Schedule Updated!'));
        }
        function stopMist() {
            fetch('/stop').then(() => alert('Stopped.'));
        }
    </script>
</body>
</html>
"""

@app.route('/')
def index():
    t = schedule["time"] if schedule["time"] != "未設定" else "12:00"
    return render_template_string(HTML, config_time=t, config_duration=schedule["duration"], config_pulse=schedule["pulse"])

@app.route('/get_status')
def get_status():
    return jsonify(status)

@app.route('/set_schedule', methods=['POST'])
def set_schedule():
    global schedule
    data = request.json
    # 型変換安全策
    try: data['duration'] = int(data['duration'])
    except: data['duration'] = 5
    
    schedule.update(data)
    write_log(f"設定更新: {data['time']} / {data['duration']}s (Pulse: {data['pulse']})")
    return jsonify(schedule)

@app.route('/stop')
def stop_mist():
    global status
    status["is_running"] = False
    status["is_spraying"] = False # 強制停止時はここも切る
    send_command("OFF")
    write_log("緊急停止が押されました。")
    return "Stopped"

if __name__ == '__main__':
    if not os.path.exists(LOG_FILE):
        with open(LOG_FILE, "w") as f: f.write("=== Mist Control Log ===\n")
    app.run(host='0.0.0.0', port=5000, debug=True, use_reloader=False)