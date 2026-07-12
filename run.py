"""Stock Agent launcher - 后台启动 + 单实例锁 + 优雅关闭.

用法:
  python run.py          # 前台启动 (开发调试, Ctrl+C 退出)
  pythonw run.py         # 后台启动 (无窗口, 像软件一样运行)
  python run.py --stop   # 停止运行中的实例
  python run.py --status  # 查看运行状态

退出方式:
  - 前台模式: Ctrl+C
  - 后台模式: python run.py --stop  或  任务管理器结束 pythonw.exe
"""
import os
import sys
import json
import time
import signal
import socket
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent
BACKEND = ROOT / "backend"
PID_FILE = ROOT / ".stock-agent.pid"
PORT = 8002


def _is_port_in_use() -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        return s.connect_ex(("127.0.0.1", PORT)) == 0


def _read_pid() -> int | None:
    if PID_FILE.exists():
        try:
            data = json.loads(PID_FILE.read_text())
            pid = data.get("pid")
            if pid:
                try:
                    if os.name == "nt":
                        # Windows: use tasklist to check if process exists
                        result = subprocess.run(
                            ["tasklist", "/FI", f"PID eq {pid}", "/NH"],
                            capture_output=True, text=True
                        )
                        if str(pid) in result.stdout:
                            return pid
                    else:
                        os.kill(pid, 0)  # Unix: signal 0 = check existence
                        return pid
                except (OSError, SystemError):
                    pass
        except (json.JSONDecodeError, KeyError):
            pass
    return None


def _write_pid():
    PID_FILE.write_text(json.dumps({
        "pid": os.getpid(),
        "port": PORT,
        "started": time.strftime("%Y-%m-%d %H:%M:%S"),
    }))


def _clear_pid():
    if PID_FILE.exists():
        PID_FILE.unlink(missing_ok=True)


def _stop_existing():
    pid = _read_pid()
    if pid is None:
        if _is_port_in_use():
            print(f"端口 {PORT} 被占用但找不到 PID 文件，尝试通过端口杀进程...")
            _kill_port(PORT)
            print("已停止。")
        else:
            print("Stock Agent 未在运行。")
        return
    try:
        if os.name == "nt":
            # Windows: taskkill /T kills child processes too
            subprocess.run(["taskkill", "/F", "/T", "/PID", str(pid)],
                            capture_output=True)
        else:
            os.kill(pid, signal.SIGTERM)
        print(f"已发送停止信号 (PID {pid})，等待退出...")
        for _ in range(10):
            time.sleep(0.5)
            pid_check = _read_pid()
            if pid_check is None:
                print("已停止。")
                _clear_pid()
                return
        print(f"进程仍在运行，尝试强制终止 (PID {pid})...")
        _kill_port(PORT)
        print("已停止。")
    except OSError:
        print(f"进程 {pid} 已不存在。")
    _clear_pid()


def _kill_port(port: int):
    import platform
    system = platform.system()
    try:
        if system == "Windows":
            result = subprocess.run(
                ["netstat", "-ano"], capture_output=True, text=True
            )
            for line in result.stdout.splitlines():
                if f":{port} " in line and "LISTENING" in line:
                    parts = line.split()
                    if parts:
                        pid = int(parts[-1])
                        subprocess.run(["taskkill", "/F", "/PID", str(pid)],
                                        capture_output=True)
        else:
            result = subprocess.run(
                ["fuser", f"{port}/tcp"], capture_output=True, text=True
            )
            for pid in result.stdout.split():
                os.kill(int(pid), signal.SIGKILL)
    except Exception:
        pass


def _show_status():
    pid = _read_pid()
    if pid is None:
        print("Stock Agent 未在运行。")
        return
    data = json.loads(PID_FILE.read_text())
    print(f"Stock Agent 运行中:")
    print(f"  PID:    {data.get('pid')}")
    print(f"  端口:   {data.get('port')}")
    print(f"  启动于: {data.get('started')}")
    print(f"  访问:   http://localhost:{data.get('port')}")


def _run_foreground():
    pid = _read_pid()
    if pid is not None:
        print(f"Stock Agent 已在运行 (PID {pid})。")
        print(f"  访问: http://localhost:{PORT}")
        print(f"  停止: python run.py --stop")
        return

    _write_pid()
    os.chdir(BACKEND)
    sys.path.insert(0, str(BACKEND))

    # 设置环境变量: 前台模式打开浏览器
    os.environ.setdefault("STOCK_AGENT_NO_BROWSER", "0")

    print(f"Stock Agent 启动中... http://localhost:{PORT}")
    print(f"  退出: Ctrl+C")
    print()

    try:
        import uvicorn
        uvicorn.run(
            "app.main:app",
            host="127.0.0.1",
            port=PORT,
            log_level="info",
            access_log=False,
        )
    except KeyboardInterrupt:
        print("\n正在停止...")
    finally:
        _clear_pid()
        print("已退出。")


def _run_background():
    pid = _read_pid()
    if pid is not None:
        print(f"Stock Agent 已在运行 (PID {pid})。")
        _show_status()
        return

    # 用 pythonw 后台启动 (无窗口)
    pythonw = sys.executable.replace("python.exe", "pythonw.exe")
    if not Path(pythonw).exists():
        pythonw = sys.executable  # fallback

    # 重新用 pythonw 执行自身的前台模式
    proc = subprocess.Popen(
        [pythonw, str(Path(__file__).resolve()), "--serve"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        stdin=subprocess.DEVNULL,
        creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
        cwd=str(BACKEND),
    )

    # 等待端口就绪
    for _ in range(15):
        time.sleep(1)
        if _is_port_in_use():
            break
    else:
        print("启动超时！请检查 backend/.venv 和依赖。")
        return

    print("Stock Agent 已在后台启动。")
    print(f"  访问: http://localhost:{PORT}")
    print(f"  停止: python run.py --stop")
    print(f"  状态: python run.py --status")


def main():
    if "--stop" in sys.argv:
        _stop_existing()
        return
    if "--status" in sys.argv:
        _show_status()
        return
    if "--serve" in sys.argv:
        # 内部调用: 实际运行 uvicorn (由 _run_background 启动)
        _write_pid()
        os.chdir(BACKEND)
        sys.path.insert(0, str(BACKEND))
        os.environ.setdefault("STOCK_AGENT_NO_BROWSER", "0")
        try:
            import uvicorn
            uvicorn.run(
                "app.main:app",
                host="127.0.0.1",
                port=PORT,
                log_level="warning",
                access_log=False,
            )
        except Exception:
            pass
        finally:
            _clear_pid()
        return
    if "--bg" in sys.argv or "--background" in sys.argv:
        _run_background()
        return
    # 默认: 前台运行
    _run_foreground()


if __name__ == "__main__":
    main()
