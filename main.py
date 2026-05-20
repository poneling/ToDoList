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
from uuid import uuid4

import customtkinter as ctk
from tkinter import BooleanVar


APP_NAME = "Günlük To-Do List"
APP_FOLDER = "GunlukTodoList"
STARTUP_SHORTCUT_NAME = "Gunluk To-Do List.lnk"

WINDOW_WIDTH = 400
WINDOW_HEIGHT = 600

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


def get_app_data_dir() -> Path:
    appdata = os.getenv("APPDATA")
    if appdata:
        root = Path(appdata)
    else:
        root = Path.home() / ".local" / "share"

    data_dir = root / APP_FOLDER
    data_dir.mkdir(parents=True, exist_ok=True)
    return data_dir


DATA_FILE = get_app_data_dir() / "tasks.json"


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
        return (
            str(executable),
            "",
            str(executable.parent),
            f"{executable},0",
        )

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
    """Create or update the app shortcut in the current user's Startup folder."""
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


def today_text() -> str:
    now = datetime.now()
    month = MONTHS_TR[now.month - 1]
    return f"{now.day} {month} {now.year}"


class TodoStore:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.tasks: list[dict] = []
        self.load()

    def load(self) -> None:
        if not self.path.exists():
            self.tasks = []
            return

        try:
            with self.path.open("r", encoding="utf-8") as file:
                data = json.load(file)
            tasks = data.get("tasks", [])
            self.tasks = tasks if isinstance(tasks, list) else []
        except Exception:
            backup_path = self.path.with_suffix(".broken.json")
            try:
                shutil.copy2(self.path, backup_path)
            except Exception:
                pass
            self.tasks = []

    def save(self) -> None:
        data = {"tasks": self.tasks}
        temp_path = self.path.with_suffix(".tmp")
        with temp_path.open("w", encoding="utf-8") as file:
            json.dump(data, file, ensure_ascii=False, indent=2)
        temp_path.replace(self.path)

    def add(self, text: str) -> None:
        self.tasks.insert(
            0,
            {
                "id": uuid4().hex,
                "text": text,
                "completed": False,
                "created_at": datetime.now().isoformat(timespec="seconds"),
                "completed_at": None,
            },
        )
        self.save()

    def set_completed(self, task_id: str, completed: bool) -> None:
        for task in self.tasks:
            if task["id"] == task_id:
                task["completed"] = completed
                task["completed_at"] = (
                    datetime.now().isoformat(timespec="seconds") if completed else None
                )
                break
        self.save()

    def delete(self, task_id: str) -> None:
        self.tasks = [task for task in self.tasks if task["id"] != task_id]
        self.save()

    def clear_completed(self) -> None:
        self.tasks = [task for task in self.tasks if not task.get("completed", False)]
        self.save()

    def counts(self) -> tuple[int, int]:
        total = len(self.tasks)
        completed = sum(1 for task in self.tasks if task.get("completed", False))
        return total, completed


class TodoApp(ctk.CTk):
    def __init__(self) -> None:
        ctk.set_appearance_mode("System")
        ctk.set_default_color_theme("blue")

        super().__init__()

        self.store = TodoStore(DATA_FILE)
        ensure_startup_shortcut()

        self.title(APP_NAME)
        self.geometry(f"{WINDOW_WIDTH}x{WINDOW_HEIGHT}")
        self.minsize(WINDOW_WIDTH, WINDOW_HEIGHT)
        self.resizable(False, True)
        self.center_window()

        self.normal_font = ctk.CTkFont(size=14)
        self.completed_font = ctk.CTkFont(size=14, overstrike=True)
        self.title_font = ctk.CTkFont(size=24, weight="bold")
        self.small_font = ctk.CTkFont(size=12)

        self.configure(padx=18, pady=18)
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(2, weight=1)

        self.build_header()
        self.build_input()
        self.build_task_list()
        self.build_footer()

        self.render_tasks()
        self.task_entry.focus()

    def center_window(self) -> None:
        self.update_idletasks()
        screen_width = self.winfo_screenwidth()
        screen_height = self.winfo_screenheight()
        x = int((screen_width - WINDOW_WIDTH) / 2)
        y = int((screen_height - WINDOW_HEIGHT) / 2)
        self.geometry(f"{WINDOW_WIDTH}x{WINDOW_HEIGHT}+{x}+{y}")

    def build_header(self) -> None:
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.grid(row=0, column=0, sticky="ew", pady=(0, 16))
        header.grid_columnconfigure(0, weight=1)

        title = ctk.CTkLabel(header, text="Bugünün Listesi", font=self.title_font)
        title.grid(row=0, column=0, sticky="w")

        date_label = ctk.CTkLabel(
            header,
            text=today_text(),
            font=self.small_font,
            text_color=("#6B7280", "#9CA3AF"),
        )
        date_label.grid(row=1, column=0, sticky="w", pady=(3, 0))

        self.theme_switch = ctk.CTkSegmentedButton(
            header,
            values=["Sistem", "Açık", "Koyu"],
            width=150,
            command=self.change_theme,
        )
        self.theme_switch.set("Sistem")
        self.theme_switch.grid(row=0, column=1, rowspan=2, sticky="e")

    def build_input(self) -> None:
        input_frame = ctk.CTkFrame(self, corner_radius=8)
        input_frame.grid(row=1, column=0, sticky="ew", pady=(0, 14))
        input_frame.grid_columnconfigure(0, weight=1)

        self.task_entry = ctk.CTkEntry(
            input_frame,
            placeholder_text="Yeni görev yaz...",
            border_width=0,
            height=42,
            font=self.normal_font,
        )
        self.task_entry.grid(row=0, column=0, sticky="ew", padx=(12, 8), pady=10)
        self.task_entry.bind("<Return>", lambda _event: self.add_task())

        add_button = ctk.CTkButton(
            input_frame,
            text="Ekle",
            width=74,
            height=36,
            corner_radius=7,
            command=self.add_task,
        )
        add_button.grid(row=0, column=1, sticky="e", padx=(0, 10), pady=10)

    def build_task_list(self) -> None:
        self.task_frame = ctk.CTkScrollableFrame(self, corner_radius=8)
        self.task_frame.grid(row=2, column=0, sticky="nsew", pady=(0, 14))
        self.task_frame.grid_columnconfigure(0, weight=1)

    def build_footer(self) -> None:
        footer = ctk.CTkFrame(self, fg_color="transparent")
        footer.grid(row=3, column=0, sticky="ew")
        footer.grid_columnconfigure(0, weight=1)

        self.summary_label = ctk.CTkLabel(
            footer,
            text="",
            font=self.small_font,
            text_color=("#6B7280", "#9CA3AF"),
        )
        self.summary_label.grid(row=0, column=0, sticky="w")

        clear_button = ctk.CTkButton(
            footer,
            text="Tamamlananları temizle",
            height=30,
            width=150,
            corner_radius=7,
            fg_color=("#E5E7EB", "#374151"),
            hover_color=("#D1D5DB", "#4B5563"),
            text_color=("#111827", "#F9FAFB"),
            command=self.clear_completed,
        )
        clear_button.grid(row=0, column=1, sticky="e")

    def change_theme(self, value: str) -> None:
        mode_map = {"Sistem": "System", "Açık": "Light", "Koyu": "Dark"}
        ctk.set_appearance_mode(mode_map.get(value, "System"))

    def add_task(self) -> None:
        text = self.task_entry.get().strip()
        if not text:
            self.task_entry.focus()
            return

        self.store.add(text)
        self.task_entry.delete(0, "end")
        self.render_tasks()

    def toggle_task(self, task_id: str, completed_var: BooleanVar) -> None:
        self.store.set_completed(task_id, completed_var.get())
        self.render_tasks()

    def delete_task(self, task_id: str) -> None:
        self.store.delete(task_id)
        self.render_tasks()

    def clear_completed(self) -> None:
        total, completed = self.store.counts()
        if total == 0 or completed == 0:
            return

        self.store.clear_completed()
        self.render_tasks()

    def render_tasks(self) -> None:
        for child in self.task_frame.winfo_children():
            child.destroy()

        if not self.store.tasks:
            empty_label = ctk.CTkLabel(
                self.task_frame,
                text="Bugün için görev yok.",
                font=self.normal_font,
                text_color=("#6B7280", "#9CA3AF"),
            )
            empty_label.grid(row=0, column=0, padx=16, pady=28)
            self.update_summary()
            return

        for row, task in enumerate(self.store.tasks):
            self.add_task_row(row, task)

        self.update_summary()

    def add_task_row(self, row: int, task: dict) -> None:
        completed = bool(task.get("completed", False))
        text_color = ("#9CA3AF", "#6B7280") if completed else ("#111827", "#F9FAFB")
        row_color = ("#F8FAFC", "#111827") if not completed else ("#F3F4F6", "#1F2937")

        item = ctk.CTkFrame(self.task_frame, corner_radius=7, fg_color=row_color)
        item.grid(row=row, column=0, sticky="ew", padx=2, pady=(0, 8))
        item.grid_columnconfigure(1, weight=1)

        completed_var = BooleanVar(value=completed)
        checkbox = ctk.CTkCheckBox(
            item,
            text="",
            variable=completed_var,
            command=lambda task_id=task["id"], var=completed_var: self.toggle_task(
                task_id, var
            ),
            checkbox_width=20,
            checkbox_height=20,
            border_width=2,
            width=20,
        )
        checkbox.grid(row=0, column=0, sticky="nw", padx=(12, 8), pady=13)

        task_label = ctk.CTkLabel(
            item,
            text=task.get("text", ""),
            font=self.completed_font if completed else self.normal_font,
            text_color=text_color,
            justify="left",
            anchor="w",
            wraplength=250,
        )
        task_label.grid(row=0, column=1, sticky="ew", padx=(0, 8), pady=12)
        task_label.bind(
            "<Button-1>",
            lambda _event, task_id=task["id"], var=completed_var: self.toggle_from_label(
                task_id, var
            ),
        )

        delete_button = ctk.CTkButton(
            item,
            text="X",
            width=32,
            height=28,
            corner_radius=7,
            fg_color="transparent",
            hover_color=("#FEE2E2", "#7F1D1D"),
            text_color=("#B91C1C", "#FCA5A5"),
            command=lambda task_id=task["id"]: self.delete_task(task_id),
        )
        delete_button.grid(row=0, column=2, sticky="ne", padx=(0, 10), pady=10)

    def toggle_from_label(self, task_id: str, completed_var: BooleanVar) -> None:
        completed_var.set(not completed_var.get())
        self.toggle_task(task_id, completed_var)

    def update_summary(self) -> None:
        total, completed = self.store.counts()
        active = total - completed

        if total == 0:
            summary = "Liste boş"
        else:
            summary = f"{active} aktif, {completed} tamamlandı"

        self.summary_label.configure(text=summary)

if __name__ == "__main__":
    app = TodoApp()
    app.mainloop()
