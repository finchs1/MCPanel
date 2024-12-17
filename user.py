import time
import subprocess
import threading
from pathlib import Path
from nicegui import run
import urllib.request

class console_io:
    def __init__(self):
        self.value = ""

    def reset(self):
        self.value = ""

class server_status:
    def __init__(self):
        self.text = "Offline"
        self.name = "close"

    def set_offline(self):
        self.text = "Offline"
        self.name = "close"

    def set_online(self):
        self.text = "Online"
        self.name = "check"

class server_user:
    def __init__(self, name):
        self.admin = False
        self.name = name
        self.server_process = None
        self.update_thread = None
        self.output = console_io()
        self.input = console_io()
        self.running = False
        self.status = server_status()
        self.uptime = None

    def get_server_output(self):
        val = self.server_process.stdout.readline()
        if val != None:
            return val.decode()
        else:
            return ""

    def send_command(self, cmd):
        if self.running:
            self.server_process.stdin.write(f"{cmd}\n".encode())
            self.server_process.stdin.flush()

    def send_server_input(self):
        self.send_command(self.input.value.strip("\n"))
        self.input.reset()

    def update_server_status(self):
        while self.running:
            output = self.get_server_output()
            self.output.value += output
            if self.server_process.poll() != None:
                break
            time.sleep(0.001)
        if self.running:
            self.running = False
            self.status.set_offline()

    def start_server(self):
        if not self.running:
            self.uptime = time.time()
            self.running = True
            self.output.reset()
            self.input.reset()
            server_path = Path(self.name)
            if not server_path.exists():
                server_path.mkdir()
                urllib.request.urlretrieve("https://piston-data.mojang.com/v1/objects/4707d00eb834b446575d89a61a11b5d548d8c001/server.jar", f"{self.name}/server.jar")
            self.server_process = subprocess.Popen(["java", "-Xmx1G", "-jar", "server.jar", "nogui"], stdout = subprocess.PIPE, stdin = subprocess.PIPE, cwd = self.name)
            self.update_thread = threading.Thread(target = self.update_server_status)
            self.update_thread.start()
            self.status.set_online()

    async def stop_server(self):
        if self.running:
            self.send_command("stop")
            await run.io_bound(time.sleep, 5)
            self.running = False
            self.update_thread.join()
