# Kurulum:
#   pip install customtkinter
#   python main.py

from __future__ import annotations

import base64
import json
import os
import platform
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from tkinter import BooleanVar
from uuid import uuid4

import customtkinter as ctk


APP_NAME = "Günlük To-Do List"
APP_FOLDER = "GunlukTodoList"
STARTUP_SHORTCUT_NAME = "Gunluk To-Do List.lnk"

WINDOW_WIDTH = 900
WINDOW_HEIGHT = 640
MIN_WINDOW_WIDTH = 780
MIN_WINDOW_HEIGHT = 560

SIDEBAR_WIDTH = 206
TASK_ROW_PADY = 7

MONTHS_TR = [
    "Ocak",
    "Şubat",
    "Mart",
    "Nisan",
    "Mayıs",
    "Haziran",
    "Temmuz",
    "Ağustos",
    "Eylül",
    "Ekim",
    "Kasım",
    "Aralık",
]

COLORS = {
    "app_bg": "#090B10",
    "sidebar": "#0D1117",
    "surface": "#111827",
    "surface_soft": "#151B23",
    "surface_lifted": "#1B2430",
    "surface_active": "#212B3A",
    "border": "#253044",
    "text": "#F8FAFC",
    "muted": "#8792A6",
    "muted_low": "#5F6B7D",
    "accent": "#B7A8FF",
    "accent_hover": "#C7BCFF",
    "accent_deep": "#352E5F",
    "danger": "#FCA5A5",
    "danger_hover": "#3A1720",
}


def get_app_data_dir() -> Path:
    appdata = os.getenv("APPDATA")
    root = Path(appdata) if appdata else Path.home() / ".local" / "share"
    data_dir = root / APP_FOLDER
    data_dir.mkdir(parents=True, exist_ok=True)
    return data_dir


APP_DATA_DIR = get_app_data_dir()
DATA_FILE = APP_DATA_DIR / "todo_data.json"
LEGACY_DATA_FILE = APP_DATA_DIR / "tasks.json"


def is_windows() -> bool:
    return platform.system().lower() == "windows"


def get_startup_folder() -> Path | None:
    appdata = os.getenv("APPDATA")
    if not appdata:
        return None

    return (
        Path(appdata)
        / "Microsoft"
        / "Windows"
        / "Start Menu"
        / "Programs"
        / "Startup"
    )


def get_launch_target() -> tuple[str, str, str, str]:
    if getattr(sys, "frozen", False):
        executable = Path(sys.executable).resolve()
        return str(executable), "", str(executable.parent), f"{executable},0"

    script_path = Path(__file__).resolve()
    pythonw = Path(sys.executable).with_name("pythonw.exe")
    launcher = pythonw if pythonw.exists() else Path(sys.executable)

    return (
        str(launcher.resolve()),
        f'"{script_path}"',
        str(script_path.parent),
        f"{launcher.resolve()},0",
    )


def ensure_startup_shortcut() -> bool:
    if not is_windows():
        return False

    startup_folder = get_startup_folder()
    if startup_folder is None:
        return False

    startup_folder.mkdir(parents=True, exist_ok=True)
    shortcut_path = startup_folder / STARTUP_SHORTCUT_NAME
    target_path, arguments, working_dir, icon_location = get_launch_target()

    payload = {
        "ShortcutPath": str(shortcut_path),
        "TargetPath": target_path,
        "Arguments": arguments,
        "WorkingDirectory": working_dir,
        "IconLocation": icon_location,
        "Description": APP_NAME,
    }
    encoded_payload = base64.b64encode(
        json.dumps(payload, ensure_ascii=False).encode("utf-8")
    ).decode("ascii")

    script = f"""
$ErrorActionPreference = 'Stop'
$json = [Text.Encoding]::UTF8.GetString([Convert]::FromBase64String('{encoded_payload}'))
$data = $json | ConvertFrom-Json
$shell = New-Object -ComObject WScript.Shell
$shortcut = $shell.CreateShortcut($data.ShortcutPath)
$shortcut.TargetPath = $data.TargetPath
$shortcut.Arguments = $data.Arguments
$shortcut.WorkingDirectory = $data.WorkingDirectory
$shortcut.IconLocation = $data.IconLocation
$shortcut.Description = $data.Description
$shortcut.Save()
"""

    try:
        subprocess.run(
            [
                "powershell",
                "-NoProfile",
                "-ExecutionPolicy",
                "Bypass",
                "-Command",
                script,
            ],
            check=True,
            capture_output=True,
            text=True,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        return True
    except Exception:
        return create_startup_cmd_fallback(startup_folder, target_path, arguments)


def create_startup_cmd_fallback(
    startup_folder: Path, target_path: str, arguments: str
) -> bool:
    fallback_path = startup_folder / "Gunluk To-Do List.cmd"
    command = f'start "" "{target_path}" {arguments}'.strip()

    try:
        fallback_path.write_text(f"@echo off\n{command}\n", encoding="utf-8")
        return True
    except Exception:
        return False


def timestamp() -> str:
    return datetime.now().isoformat(timespec="seconds")


def today_text() -> str:
    now = datetime.now()
    return f"{now.day} {MONTHS_TR[now.month - 1]} {now.year}"


def make_task(text: str, completed: bool = False) -> dict:
    return {
        "id": uuid4().hex,
        "text": text,
        "completed": completed,
        "created_at": timestamp(),
        "completed_at": timestamp() if completed else None,
    }


def make_list(name: str, tasks: list[dict] | None = None) -> dict:
    return {
        "id": uuid4().hex,
        "name": name,
        "created_at": timestamp(),
        "updated_at": timestamp(),
        "tasks": tasks or [],
    }


class TodoStore:
    def __init__(self, path: Path, legacy_path: Path) -> None:
        self.path = path
        self.legacy_path = legacy_path
        self.data: dict = {}
        self.load()

    def load(self) -> None:
        if self.path.exists():
            self.data = self.load_json_file(self.path)
        elif self.legacy_path.exists():
            self.data = self.migrate_legacy_tasks()
            self.save()
        else:
            default_list = make_list("Günlük")
            self.data = {
                "version": 2,
                "active_list_id": default_list["id"],
                "created_at": timestamp(),
                "updated_at": timestamp(),
                "lists": [default_list],
            }
            self.save()

        self.normalize()

    def load_json_file(self, path: Path) -> dict:
        try:
            with path.open("r", encoding="utf-8") as file:
                loaded = json.load(file)
            return loaded if isinstance(loaded, dict) else {}
        except Exception:
            backup_path = path.with_suffix(".broken.json")
            try:
                shutil.copy2(path, backup_path)
            except Exception:
                pass
            return {}

    def migrate_legacy_tasks(self) -> dict:
        legacy_data = self.load_json_file(self.legacy_path)
        legacy_tasks = legacy_data.get("tasks", [])
        tasks = legacy_tasks if isinstance(legacy_tasks, list) else []
        daily_list = make_list("Günlük", tasks)

        return {
            "version": 2,
            "active_list_id": daily_list["id"],
            "created_at": timestamp(),
            "updated_at": timestamp(),
            "lists": [daily_list],
        }

    def normalize(self) -> None:
        lists = self.data.get("lists")
        if not isinstance(lists, list) or not lists:
            lists = [make_list("Günlük")]

        normalized_lists = []
        for todo_list in lists:
            if not isinstance(todo_list, dict):
                continue

            tasks = todo_list.get("tasks", [])
            if not isinstance(tasks, list):
                tasks = []

            normalized_tasks = []
            for task in tasks:
                if not isinstance(task, dict) or not str(task.get("text", "")).strip():
                    continue

                completed = bool(task.get("completed", False))
                normalized_tasks.append(
                    {
                        "id": str(task.get("id") or uuid4().hex),
                        "text": str(task.get("text", "")).strip(),
                        "completed": completed,
                        "created_at": str(task.get("created_at") or timestamp()),
                        "completed_at": task.get("completed_at")
                        or (timestamp() if completed else None),
                    }
                )

            normalized_lists.append(
                {
                    "id": str(todo_list.get("id") or uuid4().hex),
                    "name": str(todo_list.get("name") or "Liste").strip(),
                    "created_at": str(todo_list.get("created_at") or timestamp()),
                    "updated_at": str(todo_list.get("updated_at") or timestamp()),
                    "tasks": normalized_tasks,
                }
            )

        if not normalized_lists:
            normalized_lists = [make_list("Günlük")]

        active_list_id = self.data.get("active_list_id")
        if not any(item["id"] == active_list_id for item in normalized_lists):
            active_list_id = normalized_lists[0]["id"]

        self.data = {
            "version": 2,
            "active_list_id": active_list_id,
            "created_at": str(self.data.get("created_at") or timestamp()),
            "updated_at": timestamp(),
            "lists": normalized_lists,
        }
        self.save()

    def save(self) -> None:
        self.data["updated_at"] = timestamp()
        temp_path = self.path.with_suffix(".tmp")
        with temp_path.open("w", encoding="utf-8") as file:
            json.dump(self.data, file, ensure_ascii=False, indent=2)
        temp_path.replace(self.path)

    @property
    def lists(self) -> list[dict]:
        return self.data["lists"]

    @property
    def active_list_id(self) -> str:
        return self.data["active_list_id"]

    def get_active_list(self) -> dict:
        return self.get_list(self.active_list_id) or self.lists[0]

    def get_list(self, list_id: str) -> dict | None:
        return next((todo_list for todo_list in self.lists if todo_list["id"] == list_id), None)

    def set_active_list(self, list_id: str) -> None:
        if self.get_list(list_id) is None:
            return
        self.data["active_list_id"] = list_id
        self.save()

    def add_list(self, name: str) -> dict:
        new_list = make_list(name)
        self.lists.append(new_list)
        self.data["active_list_id"] = new_list["id"]
        self.save()
        return new_list

    def add_task(self, text: str) -> None:
        active_list = self.get_active_list()
        active_list["tasks"].insert(0, make_task(text))
        active_list["updated_at"] = timestamp()
        self.save()

    def set_completed(self, task_id: str, completed: bool) -> None:
        active_list = self.get_active_list()
        for task in active_list["tasks"]:
            if task["id"] == task_id:
                task["completed"] = completed
                task["completed_at"] = timestamp() if completed else None
                active_list["updated_at"] = timestamp()
                break
        self.save()

    def delete_task(self, task_id: str) -> None:
        active_list = self.get_active_list()
        active_list["tasks"] = [
            task for task in active_list["tasks"] if task["id"] != task_id
        ]
        active_list["updated_at"] = timestamp()
        self.save()

    def clear_completed(self) -> None:
        active_list = self.get_active_list()
        active_list["tasks"] = [
            task for task in active_list["tasks"] if not task.get("completed", False)
        ]
        active_list["updated_at"] = timestamp()
        self.save()

    def reorder_task(self, task_id: str, target_index: int, persist: bool = False) -> bool:
        active_list = self.get_active_list()
        tasks = active_list["tasks"]
        current_index = next(
            (index for index, task in enumerate(tasks) if task["id"] == task_id), None
        )
        if current_index is None:
            return False

        task = tasks.pop(current_index)
        target_index = max(0, min(target_index, len(tasks)))
        tasks.insert(target_index, task)
        active_list["updated_at"] = timestamp()

        if persist:
            self.save()
        return True

    def counts_for_list(self, todo_list: dict) -> tuple[int, int]:
        total = len(todo_list.get("tasks", []))
        completed = sum(1 for task in todo_list.get("tasks", []) if task.get("completed"))
        return total, completed

    def active_counts(self) -> tuple[int, int]:
        return self.counts_for_list(self.get_active_list())


class TodoApp(ctk.CTk):
    def __init__(self) -> None:
        ctk.set_appearance_mode("Dark")
        ctk.set_default_color_theme("dark-blue")

        super().__init__()

        self.store = TodoStore(DATA_FILE, LEGACY_DATA_FILE)
        ensure_startup_shortcut()

        self.task_rows: dict[str, ctk.CTkFrame] = {}
        self.drag_task_id: str | None = None
        self.drag_started = False
        self.drag_start_y = 0

        self.title(APP_NAME)
        self.geometry(f"{WINDOW_WIDTH}x{WINDOW_HEIGHT}")
        self.minsize(MIN_WINDOW_WIDTH, MIN_WINDOW_HEIGHT)
        self.center_window()

        self.configure(fg_color=COLORS["app_bg"])
        self.grid_columnconfigure(0, minsize=SIDEBAR_WIDTH)
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        self.font_logo = ctk.CTkFont(size=22, weight="bold")
        self.font_title = ctk.CTkFont(size=26, weight="bold")
        self.font_section = ctk.CTkFont(size=12, weight="bold")
        self.font_body = ctk.CTkFont(size=14)
        self.font_body_medium = ctk.CTkFont(size=14, weight="bold")
        self.font_task_done = ctk.CTkFont(size=14, overstrike=True)
        self.font_small = ctk.CTkFont(size=11)
        self.font_button = ctk.CTkFont(size=13, weight="bold")

        self.build_sidebar()
        self.build_main_area()
        self.render_all()
        self.task_entry.focus()

    def center_window(self) -> None:
        self.update_idletasks()
        screen_width = self.winfo_screenwidth()
        screen_height = self.winfo_screenheight()
        x = int((screen_width - WINDOW_WIDTH) / 2)
        y = int((screen_height - WINDOW_HEIGHT) / 2)
        self.geometry(f"{WINDOW_WIDTH}x{WINDOW_HEIGHT}+{x}+{y}")

    def build_sidebar(self) -> None:
        self.sidebar = ctk.CTkFrame(
            self,
            width=SIDEBAR_WIDTH,
            corner_radius=0,
            fg_color=COLORS["sidebar"],
        )
        self.sidebar.grid(row=0, column=0, sticky="nsew")
        self.sidebar.grid_columnconfigure(0, weight=1)
        self.sidebar.grid_rowconfigure(2, weight=1)

        brand_frame = ctk.CTkFrame(self.sidebar, fg_color="transparent")
        brand_frame.grid(row=0, column=0, sticky="ew", padx=18, pady=(22, 20))
        brand_frame.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            brand_frame,
            text="Todo",
            font=self.font_logo,
            text_color=COLORS["text"],
            anchor="w",
        ).grid(row=0, column=0, sticky="w")

        ctk.CTkLabel(
            brand_frame,
            text="premium daily lists",
            font=self.font_small,
            text_color=COLORS["muted"],
            anchor="w",
        ).grid(row=1, column=0, sticky="w", pady=(3, 0))

        ctk.CTkLabel(
            self.sidebar,
            text="LİSTELER",
            font=self.font_section,
            text_color=COLORS["muted_low"],
            anchor="w",
        ).grid(row=1, column=0, sticky="ew", padx=18, pady=(0, 8))

        self.list_frame = ctk.CTkScrollableFrame(
            self.sidebar,
            fg_color="transparent",
            corner_radius=0,
            scrollbar_button_color=COLORS["surface_lifted"],
            scrollbar_button_hover_color=COLORS["surface_active"],
        )
        self.list_frame.grid(row=2, column=0, sticky="nsew", padx=12, pady=(0, 10))
        self.list_frame.grid_columnconfigure(0, weight=1)

        add_list_button = ctk.CTkButton(
            self.sidebar,
            text="+  Yeni liste",
            height=42,
            corner_radius=14,
            fg_color=COLORS["surface_soft"],
            hover_color=COLORS["surface_lifted"],
            text_color=COLORS["accent"],
            font=self.font_button,
            command=self.prompt_new_list,
        )
        add_list_button.grid(row=3, column=0, sticky="ew", padx=18, pady=(0, 18))

    def build_main_area(self) -> None:
        self.main = ctk.CTkFrame(self, fg_color=COLORS["app_bg"], corner_radius=0)
        self.main.grid(row=0, column=1, sticky="nsew", padx=24, pady=22)
        self.main.grid_columnconfigure(0, weight=1)
        self.main.grid_rowconfigure(2, weight=1)

        header = ctk.CTkFrame(self.main, fg_color="transparent")
        header.grid(row=0, column=0, sticky="ew", pady=(0, 18))
        header.grid_columnconfigure(0, weight=1)

        self.active_list_label = ctk.CTkLabel(
            header,
            text="",
            font=self.font_title,
            text_color=COLORS["text"],
            anchor="w",
        )
        self.active_list_label.grid(row=0, column=0, sticky="w")

        self.date_label = ctk.CTkLabel(
            header,
            text=today_text(),
            font=self.font_small,
            text_color=COLORS["muted"],
            anchor="w",
        )
        self.date_label.grid(row=1, column=0, sticky="w", pady=(4, 0))

        self.summary_pill = ctk.CTkLabel(
            header,
            text="",
            width=118,
            height=34,
            corner_radius=17,
            fg_color=COLORS["surface_soft"],
            text_color=COLORS["muted"],
            font=self.font_small,
        )
        self.summary_pill.grid(row=0, column=1, rowspan=2, sticky="e")

        input_frame = ctk.CTkFrame(
            self.main,
            fg_color=COLORS["surface"],
            corner_radius=16,
            border_width=1,
            border_color=COLORS["border"],
        )
        input_frame.grid(row=1, column=0, sticky="ew", pady=(0, 18))
        input_frame.grid_columnconfigure(0, weight=1)

        self.task_entry = ctk.CTkEntry(
            input_frame,
            placeholder_text="Yeni görev ekle...",
            placeholder_text_color=COLORS["muted_low"],
            border_width=0,
            height=46,
            fg_color="transparent",
            text_color=COLORS["text"],
            font=self.font_body,
        )
        self.task_entry.grid(row=0, column=0, sticky="ew", padx=(16, 10), pady=10)
        self.task_entry.bind("<Return>", lambda _event: self.add_task())

        add_task_button = ctk.CTkButton(
            input_frame,
            text="+",
            width=42,
            height=38,
            corner_radius=14,
            fg_color=COLORS["accent_deep"],
            hover_color=COLORS["surface_active"],
            text_color=COLORS["accent_hover"],
            font=ctk.CTkFont(size=20, weight="bold"),
            command=self.add_task,
        )
        add_task_button.grid(row=0, column=1, padx=(0, 10), pady=10)

        self.tasks_scroll = ctk.CTkScrollableFrame(
            self.main,
            fg_color="transparent",
            corner_radius=0,
            scrollbar_button_color=COLORS["surface_lifted"],
            scrollbar_button_hover_color=COLORS["surface_active"],
        )
        self.tasks_scroll.grid(row=2, column=0, sticky="nsew", pady=(0, 16))
        self.tasks_scroll.grid_columnconfigure(0, weight=1)

        footer = ctk.CTkFrame(self.main, fg_color="transparent")
        footer.grid(row=3, column=0, sticky="ew")
        footer.grid_columnconfigure(0, weight=1)

        self.footer_hint = ctk.CTkLabel(
            footer,
            text="Sıralamak için görev kartını sürükle",
            font=self.font_small,
            text_color=COLORS["muted_low"],
            anchor="w",
        )
        self.footer_hint.grid(row=0, column=0, sticky="w")

        clear_button = ctk.CTkButton(
            footer,
            text="Tamamlananları temizle",
            height=34,
            width=164,
            corner_radius=14,
            fg_color="transparent",
            hover_color=COLORS["surface_lifted"],
            text_color=COLORS["muted"],
            font=self.font_small,
            command=self.clear_completed,
        )
        clear_button.grid(row=0, column=1, sticky="e")

    def render_all(self) -> None:
        self.render_tasks()

    def render_sidebar(self) -> None:
        for child in self.list_frame.winfo_children():
            child.destroy()

        for row, todo_list in enumerate(self.store.lists):
            self.add_list_button(row, todo_list)

    def add_list_button(self, row: int, todo_list: dict) -> None:
        is_active = todo_list["id"] == self.store.active_list_id
        total, completed = self.store.counts_for_list(todo_list)
        active_count = total - completed

        fg_color = COLORS["surface_active"] if is_active else "transparent"
        hover_color = COLORS["surface_lifted"]
        text_color = COLORS["text"] if is_active else COLORS["muted"]

        button = ctk.CTkButton(
            self.list_frame,
            text=f"{todo_list['name']}  {active_count}",
            height=40,
            corner_radius=13,
            fg_color=fg_color,
            hover_color=hover_color,
            text_color=text_color,
            font=self.font_body_medium if is_active else self.font_body,
            anchor="w",
            command=lambda list_id=todo_list["id"]: self.switch_list(list_id),
        )
        button.grid(row=row, column=0, sticky="ew", pady=3)

    def render_tasks(self) -> None:
        self.drag_task_id = None
        self.drag_started = False
        self.task_rows.clear()

        for child in self.tasks_scroll.winfo_children():
            child.destroy()

        tasks = self.store.get_active_list()["tasks"]
        if not tasks:
            self.render_empty_state()
            self.update_header()
            return

        for row, task in enumerate(tasks):
            self.create_task_row(row, task)

        self.update_header()

    def render_empty_state(self) -> None:
        empty = ctk.CTkFrame(
            self.tasks_scroll,
            fg_color=COLORS["surface"],
            corner_radius=16,
            border_width=1,
            border_color=COLORS["border"],
        )
        empty.grid(row=0, column=0, sticky="ew", pady=(2, 0))
        empty.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            empty,
            text="Bu listede henüz görev yok",
            font=self.font_body_medium,
            text_color=COLORS["text"],
        ).grid(row=0, column=0, pady=(32, 4))

        ctk.CTkLabel(
            empty,
            text="Üstteki alandan ilk görevi ekleyebilirsin.",
            font=self.font_small,
            text_color=COLORS["muted"],
        ).grid(row=1, column=0, pady=(0, 32))

    def create_task_row(self, row: int, task: dict) -> None:
        completed = bool(task.get("completed", False))
        row_color = COLORS["surface_soft"] if not completed else COLORS["surface"]
        text_color = COLORS["text"] if not completed else COLORS["muted_low"]

        item = ctk.CTkFrame(
            self.tasks_scroll,
            corner_radius=16,
            fg_color=row_color,
            border_width=1,
            border_color=COLORS["border"],
        )
        item.grid(row=row, column=0, sticky="ew", pady=TASK_ROW_PADY)
        item.grid_columnconfigure(2, weight=1)
        self.task_rows[task["id"]] = item

        drag_handle = ctk.CTkLabel(
            item,
            text="⋮⋮",
            width=24,
            font=ctk.CTkFont(size=18),
            text_color=COLORS["muted_low"],
        )
        drag_handle.grid(row=0, column=0, sticky="n", padx=(12, 4), pady=14)

        completed_var = BooleanVar(value=completed)
        checkbox = ctk.CTkCheckBox(
            item,
            text="",
            width=22,
            checkbox_width=20,
            checkbox_height=20,
            border_width=2,
            fg_color=COLORS["accent_deep"],
            hover_color=COLORS["surface_active"],
            border_color=COLORS["muted_low"],
            variable=completed_var,
            command=lambda task_id=task["id"], var=completed_var: self.toggle_task(
                task_id, var
            ),
        )
        checkbox.grid(row=0, column=1, sticky="nw", padx=(0, 10), pady=16)

        task_label = ctk.CTkLabel(
            item,
            text=task.get("text", ""),
            font=self.font_task_done if completed else self.font_body,
            text_color=text_color,
            justify="left",
            anchor="w",
            wraplength=500,
        )
        task_label.grid(row=0, column=2, sticky="ew", padx=(0, 10), pady=15)

        delete_button = ctk.CTkButton(
            item,
            text="×",
            width=34,
            height=32,
            corner_radius=12,
            fg_color="transparent",
            hover_color=COLORS["danger_hover"],
            text_color=COLORS["danger"],
            font=ctk.CTkFont(size=18),
            command=lambda task_id=task["id"]: self.delete_task(task_id),
        )
        delete_button.grid(row=0, column=3, sticky="ne", padx=(0, 12), pady=10)

        for widget in (item, drag_handle, task_label):
            widget.bind(
                "<Button-1>",
                lambda event, task_id=task["id"]: self.start_drag(event, task_id),
            )
            widget.bind(
                "<B1-Motion>",
                lambda event, task_id=task["id"]: self.drag_motion(event, task_id),
            )
            widget.bind(
                "<ButtonRelease-1>",
                lambda event, task_id=task["id"]: self.end_drag(event, task_id),
            )

    def update_header(self) -> None:
        active_list = self.store.get_active_list()
        total, completed = self.store.active_counts()
        active = total - completed

        self.active_list_label.configure(text=active_list["name"])
        self.summary_pill.configure(text=f"{active} aktif  ·  {completed} bitti")
        self.render_sidebar()

    def switch_list(self, list_id: str) -> None:
        self.store.set_active_list(list_id)
        self.task_entry.delete(0, "end")
        self.render_all()
        self.task_entry.focus()

    def prompt_new_list(self) -> None:
        dialog = ctk.CTkInputDialog(
            title="Yeni liste",
            text="Liste adı:",
            button_fg_color=COLORS["accent_deep"],
            button_hover_color=COLORS["surface_active"],
            button_text_color=COLORS["accent_hover"],
        )
        name = dialog.get_input()
        if not name:
            return

        clean_name = name.strip()
        if not clean_name:
            return

        self.store.add_list(clean_name[:40])
        self.render_all()
        self.task_entry.focus()

    def add_task(self) -> None:
        text = self.task_entry.get().strip()
        if not text:
            self.task_entry.focus()
            return

        self.store.add_task(text)
        self.task_entry.delete(0, "end")
        self.render_all()
        self.task_entry.focus()

    def toggle_task(self, task_id: str, completed_var: BooleanVar) -> None:
        self.store.set_completed(task_id, completed_var.get())
        self.render_all()

    def delete_task(self, task_id: str) -> None:
        self.store.delete_task(task_id)
        self.render_all()

    def clear_completed(self) -> None:
        total, completed = self.store.active_counts()
        if total == 0 or completed == 0:
            return

        self.store.clear_completed()
        self.render_all()

    def start_drag(self, event, task_id: str) -> None:
        if task_id not in self.task_rows:
            return

        self.drag_task_id = task_id
        self.drag_started = False
        self.drag_start_y = event.y_root

        row = self.task_rows[task_id]
        row.configure(fg_color=COLORS["surface_active"], border_color=COLORS["accent"])

    def drag_motion(self, event, task_id: str) -> None:
        if self.drag_task_id != task_id:
            return

        if abs(event.y_root - self.drag_start_y) < 5:
            return

        self.drag_started = True
        target_index = self.calculate_drop_index(event.y_root, task_id)
        if self.store.reorder_task(task_id, target_index, persist=False):
            self.layout_task_rows()

    def calculate_drop_index(self, pointer_y: int, task_id: str) -> int:
        ordered_task_ids = [
            task["id"]
            for task in self.store.get_active_list()["tasks"]
            if task["id"] != task_id
        ]

        for index, other_task_id in enumerate(ordered_task_ids):
            row = self.task_rows.get(other_task_id)
            if row is None:
                continue

            midpoint = row.winfo_rooty() + (row.winfo_height() / 2)
            if pointer_y < midpoint:
                return index

        return len(ordered_task_ids)

    def layout_task_rows(self) -> None:
        for row, task in enumerate(self.store.get_active_list()["tasks"]):
            widget = self.task_rows.get(task["id"])
            if widget is None:
                continue
            widget.grid_configure(row=row, pady=TASK_ROW_PADY)

    def end_drag(self, _event, task_id: str) -> None:
        if self.drag_task_id != task_id:
            return

        self.store.save()
        self.drag_task_id = None

        row = self.task_rows.get(task_id)
        if row is not None:
            task = next(
                (
                    item
                    for item in self.store.get_active_list()["tasks"]
                    if item["id"] == task_id
                ),
                None,
            )
            row_color = (
                COLORS["surface"]
                if task and task.get("completed")
                else COLORS["surface_soft"]
            )
            row.configure(
                fg_color=row_color,
                border_color=COLORS["border"],
            )

        if self.drag_started:
            self.update_header()

        self.drag_started = False


if __name__ == "__main__":
    app = TodoApp()
    app.mainloop()
