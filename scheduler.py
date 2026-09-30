import subprocess, os, glob, time, sys, threading

WATCH_DIR = "/home/container/bots"
processes = {}


def scan():
    # 只清理已停止的進程，不自動啟動
    for name in list(processes.keys()):
        p = processes.get(name)
        if p is not None and p.poll() is not None:
            print(f"[Scheduler] {name} 已停止 (exit {p.poll()})", flush=True)
            del processes[name]

def handle_command(cmd):
    cmd = cmd.strip()
    if not cmd:
        return
    print(f"[Scheduler] 收到指令: {cmd}", flush=True)

    if cmd == "list":
        if not processes:
            print("[Scheduler] 沒有運行中的 bot", flush=True)
        else:
            for name, p in processes.items():
                status = "running" if p.poll() is None else f"stopped"
                print(f"[Scheduler] {name}: PID {p.pid} ({status})", flush=True)
    elif cmd == "start-all":
        for f in sorted(glob.glob(f"{WATCH_DIR}/*.py")):
            name = os.path.basename(f)
            if name not in processes or processes[name].poll() is not None:
                try:
                    p = subprocess.Popen(["python3", "-u", f])
                    processes[name] = p
                    print(f"[Scheduler] 啟動 {name} (PID {p.pid})", flush=True)
                except Exception as e:
                    print(f"[Scheduler] 錯誤: {e}", flush=True)
    elif cmd == "stop-all":
        for name, p in list(processes.items()):
            if p.poll() is None:
                p.terminate()
                print(f"[Scheduler] 停止 {name}", flush=True)
    elif cmd.startswith("start "):
        name = cmd[6:].strip()
        f = f"{WATCH_DIR}/{name}"
        if os.path.exists(f):
            if name not in processes or processes[name].poll() is not None:
                p = subprocess.Popen(["python3", "-u", f])
                processes[name] = p
                print(f"[Scheduler] 啟動 {name} (PID {p.pid})", flush=True)
            else:
                print(f"[Scheduler] {name} 已在跑", flush=True)
        else:
            print(f"[Scheduler] 找不到 {name}", flush=True)
    elif cmd.startswith("stop "):
        name = cmd[5:].strip()
        if name in processes and processes[name].poll() is None:
            processes[name].terminate()
            print(f"[Scheduler] 停止 {name}", flush=True)
        else:
            print(f"[Scheduler] {name} 沒在跑", flush=True)
    elif cmd.startswith("restart "):
        name = cmd[8:].strip()
        if name in processes and processes[name].poll() is None:
            processes[name].terminate()
            time.sleep(1)
        f = f"{WATCH_DIR}/{name}"
        if os.path.exists(f):
            p = subprocess.Popen(["python3", "-u", f])
            processes[name] = p
            print(f"[Scheduler] 重啟 {name} (PID {p.pid})", flush=True)
    else:
        print(f"[Scheduler] 未知指令: {cmd}", flush=True)

def stdin_reader():
    for line in sys.stdin:
        handle_command(line)

threading.Thread(target=stdin_reader, daemon=True).start()

print("[Scheduler] 啟動，監控", WATCH_DIR, flush=True)
print("[Scheduler] 可用: list, start <file>, stop <file>, restart <file>, stop-all", flush=True)

while True:
    try:
        scan()
    except Exception as e:
        print(f"[Scheduler] 掃描錯誤: {e}", flush=True)
    time.sleep(5)
