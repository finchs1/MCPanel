from nicegui import ui, app, Client
from nicegui.events import KeyEventArguments
import hashlib
import user
import time
from pathlib import Path
import shutil
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError
import psycopg2

users = dict()

def login(username: str, pw: str):
    cur = conn.cursor()
    cur.execute("select passhash from users where username = %s", (username, ))
    passhash = cur.fetchone()
    ph = PasswordHasher()
    try:
        if passhash != None and ph.verify(passhash[0], pw):
            ui.notify(f"Welcome back, {username}!", type = "positive", progress = True, timeout = 1000)
            ui.timer(2, lambda: ui.navigate.to("/server"), once = True)
            app.storage.user["user"] = username
            return
    except VerifyMismatchError:
        pass
    ui.notify("Login failed!", type = "negative", progress = True, timeout = 1000)

def logout():
    del app.storage.user["user"]
    ui.notify("Logging out...", type = "positive", progress = True, timeout = 1000)
    ui.timer(2, lambda: ui.navigate.to("/"), once = True)

def handle_key(e: KeyEventArguments):
    if e.key == "Enter" and e.action.keyup:
        username = app.storage.user["user"]
        users[username].send_server_input()

def update_uptime(label, user):
    if user.running:
        delta = time.time() - user.uptime
        days = int(delta // 86400)
        hours = int((delta % 86400) // 3600)
        mins = int((delta % 3600) // 60)
        secs = int(delta % 60)
        label.set_text(f"Uptime: {days} days {hours} hours {mins} mins {secs} secs")
    else:
        label.set_text("Uptime: down")

async def delete_file(filepath: Path):
    with ui.dialog() as dialog, ui.card():
        ui.label(f"Are you sure you want to delete {str(filepath).removeprefix(f'''/home/nicegui/panel/{app.storage.user['user']}/''')}?")
        ui.button("Yes", on_click = lambda: dialog.submit("Yes"))
        ui.button("No", on_click = lambda: dialog.submit("No"))

    result = await dialog

    if result == "Yes":
        if filepath.is_dir():
            shutil.rmtree(str(filepath.resolve()))
        else:
            filepath.unlink()
        ui.run_javascript("location.reload();")


@ui.page("/")
async def page_root(client: Client):
    await client.connected()
    try:
        if app.storage.user["user"]:
            ui.label("Already logged in! Redirecting...").classes("absolute-center")
            ui.timer(2, lambda: ui.navigate.to("/server"), once = True)
    except KeyError:
        with ui.card().classes("absolute-center"):
            ui.label("Panel Login").style("font-size: 200%; color: #639d49")
            username = ui.input("Username")
            pw = ui.input("Password", password = True)
            ui.button("Login", on_click = lambda: login(username.value, pw.value)).classes("ml-auto mr-auto").props("rounded icon=login")

@ui.page("/server")
async def page_server(client: Client):
    ui.page_title("Servers")
    await client.connected()
    try:
        if app.storage.user["user"]:

            username = app.storage.user["user"]

            if username not in users:
                users[username] = user.server_user(username)

            ui.keyboard(on_key = handle_key, repeating = False, ignore = ["input", "select", "button"])
            ui.label(f"Logged in as: {username}").classes("ml-auto")
            uptime_label = ui.label("Server uptime: ").classes("ml-auto")
            ui.timer(1, lambda: update_uptime(uptime_label, users[username]))
            ui.button("Logout", on_click = logout).classes("ml-auto").props("color=red rounded icon=logout")
            with ui.column().classes("w-full items-center"):
                with ui.row().classes("m-auto"):
                    ui.button("Start Server", on_click = lambda: users[username].start_server()).props("color=green rounded icon=start")
                    ui.button("Stop Server", on_click = lambda: users[username].stop_server()).props("color=red rounded icon=stop")
                    ui.button("Clear Console", on_click = lambda: users[username].output.reset()).props("color=grey rounded icon=clear_all")
                    ui.icon("warning", size = "2rem").bind_name(users[username].status)
                with ui.card().classes("w-1/3").style("height: 50vh"):
                    with ui.scroll_area().classes("h-full"):
                        ui.textarea("Server Console").classes("w-full").props("readonly outlined autogrow borderless").bind_value(users[username].output)
                with ui.card().classes("w-1/3"):
                    ui.textarea("Enter a command...").classes("w-full").props("outlined autogrow borderless").bind_value(users[username].input)
    except KeyError:
        ui.label("Not logged in! Redirecting to login...").classes("absolute-center")
        ui.timer(2, lambda: ui.navigate.to("/"), once = True)

@ui.page("/files")
async def page_settings(client: Client, filepath: str = ""):
    ui.page_title("Server File Manager")
    await client.connected()
    try:
        if app.storage.user["user"]:
            username = app.storage.user["user"]
            if not str(Path(f"{username}/{filepath}").resolve()).startswith(f"/home/nicegui/panel/{username}"):
                ui.label("Invalid Path")
                return

            if not Path(f"{username}/{filepath}").resolve().exists():
                ui.label("Invalid Path")
                return

            with ui.column().classes("w-full items-center mt-48"):
                with ui.row().classes("w-1/3"):
                    if str(Path(f"{username}/{filepath}/..").resolve()).startswith(f"/home/nicegui/panel/{username}"):
                        with ui.link(target = "files?filepath=" + str(Path(f"{username}/{filepath}/..").resolve()).removeprefix(f"/home/nicegui/panel/{username}")):
                            ui.button(icon = "arrow_back").classes("mr-auto").props("size=sm color=teal-8")
                with ui.card().classes("w-1/3"):
                    for path in Path(f"{username}/{filepath}").glob("*"):
                        with ui.row().classes("w-full"):
                            if path.is_dir() and not path.is_file():
                                ui.link(str(path).removeprefix(f"{username}/"), f"files?filepath={str(path).removeprefix(f'{username}/')}").style("font-size: 100%;")
                                ui.button(icon = "folder_zip").props("size=xs").classes("ml-auto").props("color=grey")
                            else:
                                ui.label(str(path).removeprefix(f"{username}/")).style("font-size: 100%;")
                                ui.button(icon = "download").props("size=xs").classes("ml-auto").props("color=green")
                            ui.button(icon = "delete_forever", on_click = lambda path_ = path: delete_file(path_.resolve())).props("size=xs").props("color=red")
    except KeyError:
        ui.label("Not logged in! Redirecting to login...").classes("absolute-center")
        ui.timer(2, lambda: ui.navigate.to("/"), once = True)

conn = psycopg2.connect("dbname=panel user=mcpanel")
ui.run(title = "Minecraft Control Panel", reload = False, dark = None, storage_secret = "1234567890-=][p][p][p][p8767867,.,/;]", port = 8080, favicon = "cube.png")#, ssl_keyfile = "privkey.pem", ssl_certfile = "fullchain.pem")
