from __future__ import annotations

import os
import json
import hashlib
import subprocess
import sys
import threading
import webbrowser
from datetime import datetime, timezone
from pathlib import Path
import tkinter as tk
from tkinter import filedialog, messagebox, simpledialog, ttk

from server.config import settings
from server.database import db
from server.scanner import MediaScanner


class MediaVaultDesktopApp:
    def __init__(self) -> None:
        self.root = tk.Tk()
        self.root.title('MediaVault Pro Desktop Manager')
        self.root.geometry('1220x760')
        self.root.minsize(1040, 680)

        self.project_dir = Path(__file__).resolve().parent
        self.env_path = self.project_dir / '.env'
        self.scanner = MediaScanner(db)
        self.server_process: subprocess.Popen[str] | None = None
        self.server_status_var = tk.StringVar(value='Server stopped')
        self.host_var = tk.StringVar(value=settings.host)
        self.port_var = tk.StringVar(value=str(settings.port))
        self.app_name_var = tk.StringVar(value=settings.app_name)
        self.app_version_var = tk.StringVar(value=settings.app_version)
        self.data_dir_var = tk.StringVar(value=str(settings.data_dir))
        self.video_folder_var = tk.StringVar()
        self.music_folder_var = tk.StringVar()
        self.mixed_folder_var = tk.StringVar()
        self.overview_status_var = tk.StringVar(value='Ready')
        self.library_status_var = tk.StringVar(value='Pick a folder and start scanning.')
        self.pin_lock_enabled_var = tk.BooleanVar(value=self.module_pin_lock_enabled())
        self.pin_lock_status_var = tk.StringVar()

        self.settings_preview_vars = {
            'db_path': tk.StringVar(),
            'cloud_dir': tk.StringVar(),
            'artwork_dir': tk.StringVar(),
        }

        self.summary_vars = {
            'videos': tk.StringVar(value='0'),
            'music': tk.StringVar(value='0'),
            'files': tk.StringVar(value='0'),
            'libraries': tk.StringVar(value='0'),
            'users': tk.StringVar(value='0'),
            'storage': tk.StringVar(value='0 B'),
        }
        self.data_dir_summary_var = tk.StringVar(value=str(settings.data_dir))

        self._build_ui()
        self.refresh_settings_preview()
        self.refresh_all()
        self.refresh_security_settings()
        self.root.protocol('WM_DELETE_WINDOW', self.on_close)

    def _build_ui(self) -> None:
        self.root.configure(bg='#edf3f1')
        style = ttk.Style(self.root)
        try:
            style.theme_use('clam')
        except tk.TclError:
            pass
        style.configure('App.TFrame', background='#edf3f1')
        style.configure('HeaderBar.TFrame', background='#edf3f1')
        style.configure('Card.TFrame', background='#ffffff', relief='flat')
        style.configure('Inset.TFrame', background='#f6faf9')
        style.configure('TNotebook', background='#edf3f1', borderwidth=0, tabmargins=(0, 0, 0, 0))
        style.configure('TNotebook.Tab', padding=(16, 10), font=('Segoe UI', 10, 'bold'), background='#dfe9e6', foreground='#40515c')
        style.map('TNotebook.Tab', background=[('selected', '#ffffff')], foreground=[('selected', '#182127')])
        style.configure('Header.TLabel', background='#edf3f1', foreground='#182127', font=('Segoe UI', 24, 'bold'))
        style.configure('Sub.TLabel', background='#edf3f1', foreground='#55646e', font=('Segoe UI', 10))
        style.configure('CardTitle.TLabel', background='#ffffff', foreground='#182127', font=('Segoe UI', 12, 'bold'))
        style.configure('CardValue.TLabel', background='#ffffff', foreground='#0f766e', font=('Segoe UI', 25, 'bold'))
        style.configure('Info.TLabel', background='#ffffff', foreground='#55646e', font=('Segoe UI', 9))
        style.configure('Muted.TLabel', background='#f6faf9', foreground='#667680', font=('Segoe UI', 9))
        style.configure('Status.TLabel', background='#eef7f4', foreground='#0f766e', font=('Segoe UI', 9, 'bold'))
        style.configure('StatCaption.TLabel', background='#ffffff', foreground='#6b7b86', font=('Segoe UI', 9))
        style.configure('Accent.TButton', font=('Segoe UI', 10, 'bold'))
        style.configure('Secondary.TButton', font=('Segoe UI', 9, 'bold'))

        shell = ttk.Frame(self.root, padding=18, style='App.TFrame')
        shell.pack(fill='both', expand=True)

        header = ttk.Frame(shell, style='HeaderBar.TFrame')
        header.pack(fill='x', pady=(0, 14))
        ttk.Label(header, text='MediaVault Pro Desktop Manager', style='Header.TLabel').pack(anchor='w')
        ttk.Label(
            header,
            text='Manage libraries, scan folders, control the local server, and complete day-to-day admin work without opening the browser.',
            style='Sub.TLabel',
        ).pack(anchor='w', pady=(4, 0))
        badge_row = ttk.Frame(header, style='HeaderBar.TFrame')
        badge_row.pack(anchor='w', pady=(10, 0))
        ttk.Label(badge_row, textvariable=self.server_status_var, style='Status.TLabel', padding=(10, 5)).pack(side='left')
        ttk.Label(badge_row, text='  ').pack(side='left')
        ttk.Label(badge_row, textvariable=self.data_dir_summary_var, style='Sub.TLabel').pack(side='left')

        self.notebook = ttk.Notebook(shell)
        self.notebook.pack(fill='both', expand=True)

        self.overview_tab = ttk.Frame(self.notebook, padding=14, style='App.TFrame')
        self.libraries_tab = ttk.Frame(self.notebook, padding=14, style='App.TFrame')
        self.users_tab = ttk.Frame(self.notebook, padding=14, style='App.TFrame')
        self.activity_tab = ttk.Frame(self.notebook, padding=14, style='App.TFrame')
        self.server_tab = ttk.Frame(self.notebook, padding=14, style='App.TFrame')
        self.settings_tab = ttk.Frame(self.notebook, padding=14, style='App.TFrame')

        self.notebook.add(self.overview_tab, text='Overview')
        self.notebook.add(self.libraries_tab, text='Libraries')
        self.notebook.add(self.users_tab, text='Users')
        self.notebook.add(self.activity_tab, text='Activity')
        self.notebook.add(self.server_tab, text='Server')
        self.notebook.add(self.settings_tab, text='Settings')

        self._build_overview_tab()
        self._build_libraries_tab()
        self._build_users_tab()
        self._build_activity_tab()
        self._build_server_tab()
        self._build_settings_tab()

    def _build_overview_tab(self) -> None:
        top = ttk.Frame(self.overview_tab)
        top.pack(fill='x', pady=(0, 12))
        ttk.Label(top, textvariable=self.overview_status_var, style='Sub.TLabel').pack(side='left')
        top_actions = ttk.Frame(top)
        top_actions.pack(side='right')
        ttk.Button(top_actions, text='Refresh', style='Accent.TButton', command=self.refresh_all).pack(side='left', padx=(0, 8))
        ttk.Button(top_actions, text='Open Dashboard', style='Secondary.TButton', command=self.open_web_dashboard).pack(side='left')

        cards = ttk.Frame(self.overview_tab)
        cards.pack(fill='x')
        for index, (label, key) in enumerate([
            ('Videos', 'videos'),
            ('Music', 'music'),
            ('Files', 'files'),
            ('Libraries', 'libraries'),
            ('Users', 'users'),
            ('Storage', 'storage'),
        ]):
            card = ttk.Frame(cards, style='Card.TFrame', padding=16)
            card.grid(row=0, column=index, padx=(0 if index == 0 else 10, 0), sticky='nsew')
            cards.grid_columnconfigure(index, weight=1)
            ttk.Label(card, text=label, style='CardTitle.TLabel').pack(anchor='w')
            ttk.Label(card, textvariable=self.summary_vars[key], style='CardValue.TLabel').pack(anchor='w', pady=(8, 4))
            ttk.Label(card, text='Live project snapshot', style='StatCaption.TLabel').pack(anchor='w')

        bottom = ttk.Frame(self.overview_tab)
        bottom.pack(fill='both', expand=True, pady=(16, 0))
        bottom.columnconfigure(0, weight=1)
        bottom.columnconfigure(1, weight=1)

        left = ttk.Frame(bottom, style='Card.TFrame', padding=16)
        left.grid(row=0, column=0, sticky='nsew', padx=(0, 8))
        ttk.Label(left, text='Indexed Libraries', style='CardTitle.TLabel').pack(anchor='w')
        self.overview_libraries = ttk.Treeview(left, columns=('type', 'path', 'scanned'), show='headings', height=12)
        for name, width in [('type', 90), ('path', 360), ('scanned', 150)]:
            self.overview_libraries.heading(name, text=name.title())
            self.overview_libraries.column(name, width=width, anchor='w')
        self.overview_libraries.pack(fill='both', expand=True, pady=(10, 0))

        right = ttk.Frame(bottom, style='Card.TFrame', padding=16)
        right.grid(row=0, column=1, sticky='nsew', padx=(8, 0))
        ttk.Label(right, text='Quick Actions', style='CardTitle.TLabel').pack(anchor='w')
        action_bar = ttk.Frame(right)
        action_bar.pack(fill='x', pady=(12, 10))
        ttk.Button(action_bar, text='Refresh Everything', style='Accent.TButton', command=self.refresh_all).pack(fill='x', pady=4)
        ttk.Button(action_bar, text='Open Libraries Tab', style='Secondary.TButton', command=lambda: self._focus_tab(self.libraries_tab)).pack(fill='x', pady=4)
        ttk.Button(action_bar, text='Open Server Tab', style='Secondary.TButton', command=lambda: self._focus_tab(self.server_tab)).pack(fill='x', pady=4)
        ttk.Button(action_bar, text='Open Web Dashboard', style='Secondary.TButton', command=self.open_web_dashboard).pack(fill='x', pady=4)

        ttk.Label(right, text='Recent desktop log', style='CardTitle.TLabel').pack(anchor='w', pady=(10, 0))
        self.log_text = tk.Text(right, height=14, wrap='word', bg='#f6faf9', fg='#22313a', relief='flat', padx=12, pady=12, insertbackground='#22313a')
        self.log_text.pack(fill='both', expand=True, pady=(10, 0))
        self.log_text.configure(state='disabled')

    def _build_libraries_tab(self) -> None:
        shell = ttk.Frame(self.libraries_tab)
        shell.pack(fill='both', expand=True)
        shell.columnconfigure(0, weight=0)
        shell.columnconfigure(1, weight=1)
        shell.rowconfigure(0, weight=1)

        controls = ttk.Frame(shell, style='Card.TFrame', padding=16)
        controls.grid(row=0, column=0, sticky='nsw', padx=(0, 10))
        ttk.Label(controls, text='Scan Libraries', style='CardTitle.TLabel').pack(anchor='w')
        ttk.Label(controls, text='Pick folders for movies, music, or mixed media and scan them directly into MediaVault.', style='Info.TLabel', wraplength=280).pack(anchor='w', pady=(6, 12))

        self._folder_picker(controls, 'Video folder', self.video_folder_var, lambda: self.choose_folder(self.video_folder_var))
        ttk.Button(controls, text='Scan Video Folder', style='Accent.TButton', command=lambda: self.scan_selected_folder(self.video_folder_var, 'video')).pack(fill='x', pady=(0, 12))

        self._folder_picker(controls, 'Music folder', self.music_folder_var, lambda: self.choose_folder(self.music_folder_var))
        ttk.Button(controls, text='Scan Music Folder', style='Accent.TButton', command=lambda: self.scan_selected_folder(self.music_folder_var, 'music')).pack(fill='x', pady=(0, 12))

        self._folder_picker(controls, 'Mixed media folder', self.mixed_folder_var, lambda: self.choose_folder(self.mixed_folder_var))
        ttk.Button(controls, text='Scan Mixed Folder', style='Accent.TButton', command=lambda: self.scan_selected_folder(self.mixed_folder_var, 'all')).pack(fill='x', pady=(0, 12))

        ttk.Separator(controls).pack(fill='x', pady=12)
        ttk.Button(controls, text='Refresh Libraries', style='Secondary.TButton', command=self.refresh_libraries).pack(fill='x', pady=4)
        ttk.Button(controls, text='Rescan Selected', style='Secondary.TButton', command=self.rescan_selected_library).pack(fill='x', pady=4)
        ttk.Button(controls, text='Remove Selected', style='Secondary.TButton', command=self.remove_selected_library).pack(fill='x', pady=4)
        ttk.Label(controls, textvariable=self.library_status_var, style='Info.TLabel', wraplength=280).pack(anchor='w', pady=(14, 0))

        right = ttk.Frame(shell, style='Card.TFrame', padding=16)
        right.grid(row=0, column=1, sticky='nsew')
        right.rowconfigure(1, weight=1)
        ttk.Label(right, text='Managed Libraries', style='CardTitle.TLabel').grid(row=0, column=0, sticky='w')
        columns = ('type', 'path', 'scanned')
        self.library_tree = ttk.Treeview(right, columns=columns, show='headings', height=20)
        for name, width in [('type', 100), ('path', 520), ('scanned', 180)]:
            self.library_tree.heading(name, text=name.title())
            self.library_tree.column(name, width=width, anchor='w')
        self.library_tree.grid(row=1, column=0, sticky='nsew', pady=(12, 0))
        scroll = ttk.Scrollbar(right, orient='vertical', command=self.library_tree.yview)
        self.library_tree.configure(yscrollcommand=scroll.set)
        scroll.grid(row=1, column=1, sticky='ns', pady=(12, 0))

    def _build_server_tab(self) -> None:
        shell = ttk.Frame(self.server_tab)
        shell.pack(fill='both', expand=True)
        left = ttk.Frame(shell, style='Card.TFrame', padding=16)
        left.pack(side='left', fill='y', padx=(0, 10))
        right = ttk.Frame(shell, style='Card.TFrame', padding=16)
        right.pack(side='left', fill='both', expand=True)

        ttk.Label(left, text='Server Control', style='CardTitle.TLabel').pack(anchor='w')
        ttk.Label(left, text='Run the FastAPI app locally from this desktop manager.', style='Info.TLabel', wraplength=280).pack(anchor='w', pady=(6, 12))
        self._entry_row(left, 'Host', self.host_var)
        self._entry_row(left, 'Port', self.port_var)
        ttk.Button(left, text='Start Server', style='Accent.TButton', command=self.start_server).pack(fill='x', pady=4)
        ttk.Button(left, text='Stop Server', style='Secondary.TButton', command=self.stop_server).pack(fill='x', pady=4)
        ttk.Button(left, text='Open Web Dashboard', style='Secondary.TButton', command=self.open_web_dashboard).pack(fill='x', pady=4)
        ttk.Label(left, textvariable=self.server_status_var, style='Info.TLabel', wraplength=280).pack(anchor='w', pady=(12, 0))

        ttk.Label(right, text='Server Output', style='CardTitle.TLabel').pack(anchor='w')
        self.server_output = tk.Text(right, bg='#0f1720', fg='#d7e1e8', wrap='word', relief='flat', padx=12, pady=12, insertbackground='#d7e1e8')
        self.server_output.pack(fill='both', expand=True, pady=(12, 0))
        self.server_output.configure(state='disabled')

    def _build_users_tab(self) -> None:
        shell = ttk.Frame(self.users_tab)
        shell.pack(fill='both', expand=True)
        shell.columnconfigure(0, weight=0)
        shell.columnconfigure(1, weight=1)
        shell.rowconfigure(0, weight=1)

        controls = ttk.Frame(shell, style='Card.TFrame', padding=16)
        controls.grid(row=0, column=0, sticky='nsw', padx=(0, 10))
        ttk.Label(controls, text='User Management', style='CardTitle.TLabel').pack(anchor='w')
        ttk.Label(
            controls,
            text='Promote admins, tune module access, and clear module PIN locks directly from the desktop manager.',
            style='Info.TLabel',
            wraplength=280,
        ).pack(anchor='w', pady=(6, 12))
        ttk.Button(controls, text='Refresh Users', style='Accent.TButton', command=self.refresh_users).pack(fill='x', pady=4)
        ttk.Button(controls, text='Create User', style='Secondary.TButton', command=self.create_user).pack(fill='x', pady=4)
        ttk.Button(controls, text='Reset Password', style='Secondary.TButton', command=self.reset_selected_user_password).pack(fill='x', pady=4)
        ttk.Button(controls, text='Toggle Admin/User', style='Secondary.TButton', command=self.toggle_selected_user_role).pack(fill='x', pady=4)
        ttk.Button(controls, text='Grant All Modules', style='Secondary.TButton', command=self.grant_all_modules_to_selected_user).pack(fill='x', pady=4)
        ttk.Button(controls, text='Edit Modules', style='Secondary.TButton', command=self.edit_selected_user_modules).pack(fill='x', pady=4)
        ttk.Button(controls, text='Set Module PIN', style='Secondary.TButton', command=self.set_selected_user_pin).pack(fill='x', pady=4)
        ttk.Button(controls, text='Clear Module PINs', style='Secondary.TButton', command=self.clear_selected_user_pins).pack(fill='x', pady=4)
        ttk.Button(controls, text='Delete User', style='Secondary.TButton', command=self.delete_selected_user).pack(fill='x', pady=4)
        self.user_status_var = tk.StringVar(value='Select a user to manage their access.')
        ttk.Label(controls, textvariable=self.user_status_var, style='Info.TLabel', wraplength=280).pack(anchor='w', pady=(14, 0))

        right = ttk.Frame(shell, style='Card.TFrame', padding=16)
        right.grid(row=0, column=1, sticky='nsew')
        right.rowconfigure(1, weight=1)
        ttk.Label(right, text='Users', style='CardTitle.TLabel').grid(row=0, column=0, sticky='w')
        columns = ('username', 'role', 'modules', 'pin_locks', 'created')
        self.user_tree = ttk.Treeview(right, columns=columns, show='headings', height=20)
        for name, width in [('username', 180), ('role', 90), ('modules', 220), ('pin_locks', 140), ('created', 180)]:
            self.user_tree.heading(name, text=name.replace('_', ' ').title())
            self.user_tree.column(name, width=width, anchor='w')
        self.user_tree.grid(row=1, column=0, sticky='nsew', pady=(12, 0))
        scroll = ttk.Scrollbar(right, orient='vertical', command=self.user_tree.yview)
        self.user_tree.configure(yscrollcommand=scroll.set)
        scroll.grid(row=1, column=1, sticky='ns', pady=(12, 0))

    def _build_activity_tab(self) -> None:
        shell = ttk.Frame(self.activity_tab)
        shell.pack(fill='both', expand=True)
        shell.columnconfigure(0, weight=0)
        shell.columnconfigure(1, weight=1)
        shell.rowconfigure(0, weight=1)

        controls = ttk.Frame(shell, style='Card.TFrame', padding=16)
        controls.grid(row=0, column=0, sticky='nsw', padx=(0, 10))
        ttk.Label(controls, text='Streams & Activity', style='CardTitle.TLabel').pack(anchor='w')
        ttk.Label(
            controls,
            text='Watch active streams, recent playback activity, and recent sessions from the desktop manager.',
            style='Info.TLabel',
            wraplength=280,
        ).pack(anchor='w', pady=(6, 12))
        ttk.Button(controls, text='Refresh Activity', style='Accent.TButton', command=self.refresh_activity).pack(fill='x', pady=4)
        self.activity_status_var = tk.StringVar(value='Refresh to load stream activity.')
        ttk.Label(controls, textvariable=self.activity_status_var, style='Info.TLabel', wraplength=280).pack(anchor='w', pady=(14, 0))

        right = ttk.Frame(shell, style='Card.TFrame', padding=16)
        right.grid(row=0, column=1, sticky='nsew')
        right.columnconfigure(0, weight=1)
        right.rowconfigure(1, weight=1)
        right.rowconfigure(3, weight=1)
        right.rowconfigure(5, weight=1)

        ttk.Label(right, text='Active Streams', style='CardTitle.TLabel').grid(row=0, column=0, sticky='w')
        self.active_stream_tree = ttk.Treeview(
            right,
            columns=('user', 'media', 'kind', 'device', 'last_ping'),
            show='headings',
            height=7,
        )
        for name, width in [('user', 140), ('media', 300), ('kind', 90), ('device', 110), ('last_ping', 170)]:
            self.active_stream_tree.heading(name, text=name.replace('_', ' ').title())
            self.active_stream_tree.column(name, width=width, anchor='w')
        self.active_stream_tree.grid(row=1, column=0, sticky='nsew', pady=(10, 16))

        ttk.Label(right, text='Recent Streams', style='CardTitle.TLabel').grid(row=2, column=0, sticky='w')
        self.recent_stream_tree = ttk.Treeview(
            right,
            columns=('user', 'media', 'kind', 'device', 'started'),
            show='headings',
            height=8,
        )
        for name, width in [('user', 140), ('media', 300), ('kind', 90), ('device', 110), ('started', 170)]:
            self.recent_stream_tree.heading(name, text=name.replace('_', ' ').title())
            self.recent_stream_tree.column(name, width=width, anchor='w')
        self.recent_stream_tree.grid(row=3, column=0, sticky='nsew', pady=(10, 16))

        ttk.Label(right, text='Recent Sessions', style='CardTitle.TLabel').grid(row=4, column=0, sticky='w')
        self.session_tree = ttk.Treeview(
            right,
            columns=('username', 'role', 'ip', 'device', 'last_seen'),
            show='headings',
            height=7,
        )
        for name, width in [('username', 140), ('role', 90), ('ip', 130), ('device', 300), ('last_seen', 170)]:
            self.session_tree.heading(name, text=name.replace('_', ' ').title())
            self.session_tree.column(name, width=width, anchor='w')
        self.session_tree.grid(row=5, column=0, sticky='nsew', pady=(10, 0))

    def _build_settings_tab(self) -> None:
        shell = ttk.Frame(self.settings_tab)
        shell.pack(fill='both', expand=True)
        shell.columnconfigure(0, weight=3)
        shell.columnconfigure(1, weight=2)
        left = ttk.Frame(shell, style='Card.TFrame', padding=18)
        left.grid(row=0, column=0, sticky='nsew', padx=(0, 8))
        right = ttk.Frame(shell, style='Card.TFrame', padding=18)
        right.grid(row=0, column=1, sticky='nsew', padx=(8, 0))
        ttk.Label(left, text='Application Settings', style='CardTitle.TLabel').pack(anchor='w')
        ttk.Label(left, text='Use your custom directories and app settings here. Saved values go into .env and will apply after restart.', style='Info.TLabel').pack(anchor='w', pady=(6, 12))

        editable_rows = [
            ('App name', self.app_name_var, None),
            ('Version', self.app_version_var, None),
            ('Server host', self.host_var, None),
            ('Server port', self.port_var, None),
            ('Data directory', self.data_dir_var, self.choose_data_directory),
        ]
        for label, variable, browse_command in editable_rows:
            frame = ttk.Frame(left)
            frame.pack(fill='x', pady=6)
            ttk.Label(frame, text=label, width=18).pack(side='left')
            ttk.Entry(frame, textvariable=variable).pack(side='left', fill='x', expand=True, padx=(0, 8))
            if browse_command:
                ttk.Button(frame, text='Browse', style='Secondary.TButton', command=browse_command).pack(side='left')

        ttk.Separator(left).pack(fill='x', pady=14)

        security = ttk.Frame(left, style='Card.TFrame', padding=0)
        security.pack(fill='x', pady=(0, 14))
        ttk.Label(security, text='Security', style='CardTitle.TLabel').pack(anchor='w')
        ttk.Label(
            security,
            text='Control whether module PIN prompts are active across the web app and desktop-managed sessions.',
            style='Info.TLabel',
            wraplength=760,
        ).pack(anchor='w', pady=(6, 10))
        ttk.Checkbutton(
            security,
            text='Enable module PIN lock',
            variable=self.pin_lock_enabled_var,
            command=self.on_pin_toggle_changed,
        ).pack(anchor='w')
        ttk.Label(security, textvariable=self.pin_lock_status_var, style='Info.TLabel', wraplength=760).pack(anchor='w', pady=(6, 0))

        actions = ttk.Frame(left)
        actions.pack(fill='x', pady=(18, 0))
        ttk.Button(actions, text='Save Settings', style='Accent.TButton', command=self.save_app_settings).pack(side='left', padx=(0, 8))
        ttk.Button(actions, text='Open Project Folder', style='Secondary.TButton', command=lambda: self.open_path(self.project_dir)).pack(side='left')

        ttk.Label(right, text='Resolved Paths', style='CardTitle.TLabel').pack(anchor='w')
        ttk.Label(right, text='Preview the directories MediaVault will use after settings are saved.', style='Info.TLabel', wraplength=360).pack(anchor='w', pady=(6, 12))

        preview_rows = [
            ('Database path', self.settings_preview_vars['db_path']),
            ('Cloud storage', self.settings_preview_vars['cloud_dir']),
            ('Artwork directory', self.settings_preview_vars['artwork_dir']),
        ]
        for label, variable in preview_rows:
            frame = ttk.Frame(right)
            frame.pack(fill='x', pady=6)
            ttk.Label(frame, text=label, width=18).pack(side='left')
            entry = ttk.Entry(frame, textvariable=variable)
            entry.configure(state='readonly')
            entry.pack(side='left', fill='x', expand=True, padx=(0, 8))

        self.data_dir_var.trace_add('write', lambda *_: self.refresh_settings_preview())
        ttk.Separator(right).pack(fill='x', pady=14)
        quick_open = ttk.Frame(right)
        quick_open.pack(fill='x')
        ttk.Label(quick_open, text='Quick Open', style='CardTitle.TLabel').pack(anchor='w')
        ttk.Button(quick_open, text='Open Data Folder', style='Secondary.TButton', command=lambda: self.open_path(Path(self.data_dir_var.get().strip() or str(settings.data_dir)))).pack(fill='x', pady=(10, 6))
        ttk.Button(quick_open, text='Open Cloud Folder', style='Secondary.TButton', command=lambda: self.open_path(self.current_data_dir() / 'storage' / 'cloud')).pack(fill='x', pady=6)
        ttk.Button(quick_open, text='Open Artwork Folder', style='Secondary.TButton', command=lambda: self.open_path(self.current_data_dir() / 'storage' / 'artwork')).pack(fill='x', pady=6)

    def current_data_dir(self) -> Path:
        return Path(self.data_dir_var.get().strip() or str(settings.data_dir)).expanduser()

    def refresh_settings_preview(self) -> None:
        data_dir = self.current_data_dir()
        self.settings_preview_vars['db_path'].set(str(data_dir / 'mediavault.db'))
        self.settings_preview_vars['cloud_dir'].set(str(data_dir / 'storage' / 'cloud'))
        self.settings_preview_vars['artwork_dir'].set(str(data_dir / 'storage' / 'artwork'))
        self.data_dir_summary_var.set(f'Data directory: {data_dir}')

    def module_pin_lock_enabled(self) -> bool:
        return (db.get_setting('module_pin_lock_enabled', 'false') or 'false').strip().lower() == 'true'

    def refresh_security_settings(self) -> None:
        enabled = self.module_pin_lock_enabled()
        self.pin_lock_enabled_var.set(enabled)
        self.pin_lock_status_var.set(
            'Module PIN prompts are currently enabled.' if enabled else 'Module PIN prompts are currently disabled.'
        )

    def on_pin_toggle_changed(self) -> None:
        enabled = self.pin_lock_enabled_var.get()
        self.pin_lock_status_var.set(
            'Click Save Settings to apply this PIN lock change.' if enabled != self.module_pin_lock_enabled()
            else ('Module PIN prompts are currently enabled.' if enabled else 'Module PIN prompts are currently disabled.')
        )

    def choose_data_directory(self) -> None:
        folder = filedialog.askdirectory(initialdir=str(self.current_data_dir().parent if self.current_data_dir().parent.exists() else Path.home()))
        if folder:
            self.data_dir_var.set(folder)

    def save_app_settings(self) -> None:
        port = self.port_var.get().strip()
        if port and not port.isdigit():
            messagebox.showerror('MediaVault Pro', 'Server port must be a number.')
            return

        data_dir = self.current_data_dir()
        lines = [
            f'MEDIAVAULT_APP_NAME={self.app_name_var.get().strip() or settings.app_name}',
            f'MEDIAVAULT_APP_VERSION={self.app_version_var.get().strip() or settings.app_version}',
            f'MEDIAVAULT_HOST={self.host_var.get().strip() or settings.host}',
            f'MEDIAVAULT_PORT={port or settings.port}',
            f'MEDIAVAULT_DATA_DIR={data_dir}',
        ]
        self.env_path.write_text('\n'.join(lines) + '\n')
        db.set_setting('module_pin_lock_enabled', 'true' if self.pin_lock_enabled_var.get() else 'false')
        self.refresh_security_settings()
        self.root.title(f"{self.app_name_var.get().strip() or settings.app_name} Desktop Manager")
        self.log(f'Saved application settings to {self.env_path.name}')
        messagebox.showinfo(
            'MediaVault Pro',
            'Settings saved. Directory changes still need desktop app restart; PIN lock changes apply immediately.'
        )

    def _entry_row(self, parent: ttk.Frame, label: str, variable: tk.StringVar) -> None:
        frame = ttk.Frame(parent)
        frame.pack(fill='x', pady=(0, 10))
        ttk.Label(frame, text=label).pack(anchor='w')
        ttk.Entry(frame, textvariable=variable).pack(fill='x', pady=(4, 0))

    def _folder_picker(self, parent: ttk.Frame, label: str, variable: tk.StringVar, command) -> None:
        frame = ttk.Frame(parent)
        frame.pack(fill='x', pady=(0, 8))
        ttk.Label(frame, text=label).pack(anchor='w')
        row = ttk.Frame(frame)
        row.pack(fill='x', pady=(4, 0))
        ttk.Entry(row, textvariable=variable).pack(side='left', fill='x', expand=True)
        ttk.Button(row, text='Browse', command=command).pack(side='left', padx=(8, 0))

    def choose_folder(self, variable: tk.StringVar) -> None:
        folder = filedialog.askdirectory(initialdir=str(Path.home()))
        if folder:
            variable.set(folder)

    def _focus_tab(self, tab: ttk.Frame) -> None:
        self.notebook.select(tab)

    def log(self, message: str) -> None:
        timestamp = datetime.now().strftime('%H:%M:%S')
        line = f'[{timestamp}] {message}\n'
        self.log_text.configure(state='normal')
        self.log_text.insert('end', line)
        self.log_text.see('end')
        self.log_text.configure(state='disabled')

    def log_server_output(self, message: str) -> None:
        self.server_output.configure(state='normal')
        self.server_output.insert('end', message)
        self.server_output.see('end')
        self.server_output.configure(state='disabled')

    def run_task(self, func, done_message: str | None = None) -> None:
        def worker() -> None:
            try:
                func()
                if done_message:
                    self.root.after(0, lambda: self.log(done_message))
            except Exception as exc:
                self.root.after(0, lambda: messagebox.showerror('MediaVault Pro', str(exc)))
                self.root.after(0, lambda: self.log(f'Error: {exc}'))

        threading.Thread(target=worker, daemon=True).start()

    def fetch_summary(self) -> dict[str, str]:
        with db.connection() as conn:
            videos = conn.execute('SELECT COUNT(*) FROM videos').fetchone()[0]
            music = conn.execute('SELECT COUNT(*) FROM music').fetchone()[0]
            files = conn.execute('SELECT COUNT(*) FROM cloud_files').fetchone()[0]
            libraries = conn.execute('SELECT COUNT(*) FROM libraries').fetchone()[0]
            users = conn.execute('SELECT COUNT(*) FROM users').fetchone()[0]
            storage = conn.execute('SELECT COALESCE(SUM(size), 0) FROM cloud_files').fetchone()[0]
        return {
            'videos': str(videos),
            'music': str(music),
            'files': str(files),
            'libraries': str(libraries),
            'users': str(users),
            'storage': self.format_bytes(storage),
        }

    def refresh_all(self) -> None:
        self.refresh_summary()
        self.refresh_libraries()
        self.refresh_users()
        self.refresh_activity()
        self.overview_status_var.set('Desktop manager synced with current database state.')

    def refresh_summary(self) -> None:
        summary = self.fetch_summary()
        for key, value in summary.items():
            self.summary_vars[key].set(value)

    def fetch_libraries(self) -> list[dict]:
        with db.connection() as conn:
            rows = conn.execute('SELECT * FROM libraries ORDER BY scanned_at DESC').fetchall()
        return [dict(row) for row in rows]

    def refresh_libraries(self) -> None:
        libraries = self.fetch_libraries()
        for tree in (self.library_tree, self.overview_libraries):
            for item in tree.get_children():
                tree.delete(item)
        for library in libraries:
            scanned = self.format_dt(library['scanned_at'])
            values = (library['media_type'], library['path'], scanned)
            self.library_tree.insert('', 'end', iid=library['id'], values=values)
            self.overview_libraries.insert('', 'end', iid=f"overview-{library['id']}", values=values)
        self.library_status_var.set(f'{len(libraries)} libraries indexed and ready to manage.')
        self.refresh_summary()

    def fetch_users(self) -> list[dict]:
        with db.connection() as conn:
            rows = conn.execute('SELECT id, username, role, module_access, module_pins, created_at FROM users ORDER BY created_at ASC').fetchall()
        users: list[dict] = []
        for row in rows:
            item = dict(row)
            modules = sorted({value.strip() for value in (item.get('module_access') or 'all').split(',') if value.strip()}) or ['all']
            if 'all' in modules:
                modules = ['all']
            try:
                raw_pins = json.loads(item.get('module_pins') or '{}')
            except json.JSONDecodeError:
                raw_pins = {}
            pin_modules = sorted(raw_pins.keys()) if isinstance(raw_pins, dict) else []
            item['modules'] = modules
            item['pin_modules'] = pin_modules
            users.append(item)
        return users

    def refresh_users(self) -> None:
        if not hasattr(self, 'user_tree'):
            return
        users = self.fetch_users()
        for item in self.user_tree.get_children():
            self.user_tree.delete(item)
        for user in users:
            self.user_tree.insert(
                '',
                'end',
                iid=user['id'],
                values=(
                    user['username'],
                    user['role'],
                    ', '.join(user['modules']),
                    ', '.join(user['pin_modules']) if user['pin_modules'] else 'none',
                    self.format_dt(user['created_at']),
                ),
            )
        self.user_status_var.set(f'{len(users)} users loaded.')
        self.refresh_summary()

    def refresh_activity(self) -> None:
        if not hasattr(self, 'active_stream_tree'):
            return
        with db.connection() as conn:
            active_streams = conn.execute(
                'SELECT username, media_title, media_kind, device_label, last_ping_at FROM active_streams ORDER BY last_ping_at DESC'
            ).fetchall()
            recent_streams = conn.execute(
                'SELECT username, media_title, media_kind, device_label, started_at FROM stream_events ORDER BY started_at DESC LIMIT 20'
            ).fetchall()
            sessions = conn.execute(
                'SELECT username, role, ip_address, user_agent, last_seen_at FROM sessions ORDER BY last_seen_at DESC, created_at DESC LIMIT 20'
            ).fetchall()

        for tree in (self.active_stream_tree, self.recent_stream_tree, self.session_tree):
            for item in tree.get_children():
                tree.delete(item)

        for row in active_streams:
            self.active_stream_tree.insert(
                '',
                'end',
                values=(
                    row['username'],
                    row['media_title'] or 'Unknown media',
                    row['media_kind'],
                    row['device_label'] or 'Browser',
                    self.format_dt(row['last_ping_at']),
                ),
            )

        for row in recent_streams:
            self.recent_stream_tree.insert(
                '',
                'end',
                values=(
                    row['username'],
                    row['media_title'] or 'Unknown media',
                    row['media_kind'],
                    row['device_label'] or 'Browser',
                    self.format_dt(row['started_at']),
                ),
            )

        for row in sessions:
            self.session_tree.insert(
                '',
                'end',
                values=(
                    row['username'],
                    row['role'],
                    row['ip_address'] or 'Unknown IP',
                    row['user_agent'] or 'Unknown device',
                    self.format_dt(row['last_seen_at'] or ''),
                ),
            )

        self.activity_status_var.set(
            f"{len(active_streams)} active streams, {len(recent_streams)} recent streams, {len(sessions)} recent sessions."
        )

    def selected_user(self) -> dict | None:
        if not hasattr(self, 'user_tree'):
            return None
        selected = self.user_tree.selection()
        if not selected:
            messagebox.showinfo('MediaVault Pro', 'Please select a user first.')
            return None
        user_id = selected[0]
        with db.connection() as conn:
            row = conn.execute('SELECT id, username, role, module_access, module_pins, created_at FROM users WHERE id = ?', (user_id,)).fetchone()
        if not row:
            messagebox.showerror('MediaVault Pro', 'Selected user was not found.')
            return None
        item = dict(row)
        item['modules'] = sorted({value.strip() for value in (item.get('module_access') or 'all').split(',') if value.strip()}) or ['all']
        if 'all' in item['modules']:
            item['modules'] = ['all']
        try:
            raw_pins = json.loads(item.get('module_pins') or '{}')
        except json.JSONDecodeError:
            raw_pins = {}
        item['pin_modules'] = sorted(raw_pins.keys()) if isinstance(raw_pins, dict) else []
        return item

    @staticmethod
    def _hash_password(password: str) -> str:
        return hashlib.sha256(password.encode('utf-8')).hexdigest()

    @staticmethod
    def _hash_pin(pin: str) -> str:
        return hashlib.sha256(pin.encode('utf-8')).hexdigest()

    def create_user(self) -> None:
        username = simpledialog.askstring('MediaVault Pro', 'Enter new username:')
        if username is None:
            return
        username = username.strip()
        if len(username) < 3:
            messagebox.showerror('MediaVault Pro', 'Username must be at least 3 characters.')
            return

        password = simpledialog.askstring('MediaVault Pro', f'Enter password for {username}:', show='*')
        if password is None:
            return
        password = password.strip()
        if len(password) < 4:
            messagebox.showerror('MediaVault Pro', 'Password must be at least 4 characters.')
            return

        with db.connection() as conn:
            existing = conn.execute('SELECT id FROM users WHERE username = ?', (username,)).fetchone()
            if existing:
                messagebox.showerror('MediaVault Pro', 'That username already exists.')
                return
            conn.execute(
                'INSERT INTO users (id, username, password, role, module_access, module_pins, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)',
                (
                    self.make_id(),
                    username,
                    self._hash_password(password),
                    'user',
                    'all',
                    '{}',
                    datetime.now(timezone.utc).isoformat(),
                ),
            )
        self.user_status_var.set(f'Created user {username}.')
        self.log(f'Created user {username}')
        self.refresh_users()

    def reset_selected_user_password(self) -> None:
        user = self.selected_user()
        if not user:
            return
        password = simpledialog.askstring('MediaVault Pro', f"Enter new password for {user['username']}:", show='*')
        if password is None:
            return
        password = password.strip()
        if len(password) < 4:
            messagebox.showerror('MediaVault Pro', 'Password must be at least 4 characters.')
            return
        with db.connection() as conn:
            conn.execute('UPDATE users SET password = ? WHERE id = ?', (self._hash_password(password), user['id']))
            conn.execute('DELETE FROM sessions WHERE user_id = ?', (user['id'],))
        self.user_status_var.set(f"Password reset for {user['username']}.")
        self.log(f"Reset password for {user['username']}")
        self.refresh_users()

    def toggle_selected_user_role(self) -> None:
        user = self.selected_user()
        if not user:
            return
        with db.connection() as conn:
            admin_count = conn.execute("SELECT COUNT(*) FROM users WHERE role = 'admin'").fetchone()[0]
            if user['role'] == 'admin' and admin_count <= 1:
                messagebox.showerror('MediaVault Pro', 'At least one admin account must remain.')
                return
            next_role = 'user' if user['role'] == 'admin' else 'admin'
            conn.execute('UPDATE users SET role = ? WHERE id = ?', (next_role, user['id']))
            conn.execute('UPDATE sessions SET role = ? WHERE user_id = ?', (next_role, user['id']))
        self.user_status_var.set(f"{user['username']} is now {next_role}.")
        self.log(f"Updated role for {user['username']} -> {next_role}")
        self.refresh_users()

    def grant_all_modules_to_selected_user(self) -> None:
        user = self.selected_user()
        if not user:
            return
        with db.connection() as conn:
            conn.execute("UPDATE users SET module_access = 'all' WHERE id = ?", (user['id'],))
            conn.execute("UPDATE sessions SET module_access = 'all' WHERE user_id = ?", (user['id'],))
        self.user_status_var.set(f"Granted all modules to {user['username']}.")
        self.log(f"Granted all modules to {user['username']}")
        self.refresh_users()

    def edit_selected_user_modules(self) -> None:
        user = self.selected_user()
        if not user:
            return
        current_modules = ['music', 'video', 'files'] if 'all' in user['modules'] else list(user['modules'])
        answer = simpledialog.askstring(
            'MediaVault Pro',
            f"Enter modules for {user['username']} as comma-separated values.\nAllowed: music, video, files, all",
            initialvalue=','.join(current_modules if current_modules else ['music']),
        )
        if answer is None:
            return
        requested = sorted({value.strip().lower() for value in answer.split(',') if value.strip()})
        allowed = {'all', 'music', 'video', 'files'}
        if not requested or any(value not in allowed for value in requested) or ('all' in requested and len(requested) > 1):
            messagebox.showerror('MediaVault Pro', 'Use only: all or one/more of music, video, files.')
            return
        next_modules = 'all' if 'all' in requested else ','.join(requested)
        with db.connection() as conn:
            conn.execute('UPDATE users SET module_access = ? WHERE id = ?', (next_modules, user['id']))
            conn.execute('UPDATE sessions SET module_access = ? WHERE user_id = ?', (next_modules, user['id']))
        self.user_status_var.set(f"Updated modules for {user['username']}.")
        self.log(f"Updated module access for {user['username']} -> {next_modules}")
        self.refresh_users()

    def set_selected_user_pin(self) -> None:
        user = self.selected_user()
        if not user:
            return
        module_name = simpledialog.askstring(
            'MediaVault Pro',
            f"Enter module name for PIN on {user['username']}:\nAllowed: music, video, files",
            initialvalue='music',
        )
        if module_name is None:
            return
        module_name = module_name.strip().lower()
        if module_name not in {'music', 'video', 'files'}:
            messagebox.showerror('MediaVault Pro', 'Module must be one of: music, video, files.')
            return
        pin = simpledialog.askstring('MediaVault Pro', f'Enter 4-digit PIN for {module_name}:', show='*')
        if pin is None:
            return
        pin = pin.strip()
        if len(pin) != 4 or not pin.isdigit():
            messagebox.showerror('MediaVault Pro', 'PIN must be exactly 4 digits.')
            return

        try:
            current_pins = json.loads(user.get('module_pins') or '{}')
            if not isinstance(current_pins, dict):
                current_pins = {}
        except json.JSONDecodeError:
            current_pins = {}
        current_pins[module_name] = self._hash_pin(pin)

        with db.connection() as conn:
            conn.execute('UPDATE users SET module_pins = ? WHERE id = ?', (json.dumps(current_pins, separators=(',', ':')), user['id']))
            for row in conn.execute('SELECT token, unlocked_modules FROM sessions WHERE user_id = ?', (user['id'],)).fetchall():
                unlocked = [module for module in (row['unlocked_modules'] or '').split(',') if module and module != module_name]
                conn.execute('UPDATE sessions SET unlocked_modules = ? WHERE token = ?', (','.join(sorted(set(unlocked))), row['token']))
        self.user_status_var.set(f"Set {module_name} PIN for {user['username']}.")
        self.log(f"Set {module_name} PIN for {user['username']}")
        self.refresh_users()

    def clear_selected_user_pins(self) -> None:
        user = self.selected_user()
        if not user:
            return
        if not user['pin_modules']:
            messagebox.showinfo('MediaVault Pro', 'This user has no module PINs set.')
            return
        confirmed = messagebox.askyesno('MediaVault Pro', f"Clear all module PINs for {user['username']}?")
        if not confirmed:
            return
        with db.connection() as conn:
            conn.execute("UPDATE users SET module_pins = '{}' WHERE id = ?", (user['id'],))
            conn.execute("UPDATE sessions SET unlocked_modules = '' WHERE user_id = ?", (user['id'],))
        self.user_status_var.set(f"Cleared module PINs for {user['username']}.")
        self.log(f"Cleared module PINs for {user['username']}")
        self.refresh_users()

    def delete_selected_user(self) -> None:
        user = self.selected_user()
        if not user:
            return
        with db.connection() as conn:
            admin_count = conn.execute("SELECT COUNT(*) FROM users WHERE role = 'admin'").fetchone()[0]
            if user['role'] == 'admin' and admin_count <= 1:
                messagebox.showerror('MediaVault Pro', 'You cannot delete the last admin account.')
                return
        confirmed = messagebox.askyesno('MediaVault Pro', f"Delete user {user['username']}?")
        if not confirmed:
            return
        with db.connection() as conn:
            conn.execute('DELETE FROM sessions WHERE user_id = ?', (user['id'],))
            conn.execute('DELETE FROM users WHERE id = ?', (user['id'],))
        self.user_status_var.set(f"Deleted user {user['username']}.")
        self.log(f"Deleted user {user['username']}")
        self.refresh_users()

    @staticmethod
    def make_id() -> str:
        import uuid
        return str(uuid.uuid4())

    def selected_library(self) -> dict | None:
        selected = self.library_tree.selection()
        if not selected:
            messagebox.showinfo('MediaVault Pro', 'Please select a library first.')
            return None
        library_id = selected[0]
        with db.connection() as conn:
            row = conn.execute('SELECT * FROM libraries WHERE id = ?', (library_id,)).fetchone()
        if not row:
            messagebox.showerror('MediaVault Pro', 'Selected library was not found.')
            return None
        return dict(row)

    def scan_selected_folder(self, variable: tk.StringVar, media_type: str) -> None:
        folder = variable.get().strip()
        if not folder:
            messagebox.showinfo('MediaVault Pro', 'Please choose a folder first.')
            return
        self.library_status_var.set(f'Scanning {folder}...')

        def task() -> None:
            result = self.scanner.scan_folder(folder, media_type)
            self.root.after(0, lambda: self.library_status_var.set(
                f"Scan complete: {result['videos']} videos, {result['music']} music, {result['duplicates']} duplicates."
            ))
            self.root.after(0, self.refresh_all)

        self.run_task(task, f'Scan finished for {folder}.')

    def rescan_selected_library(self) -> None:
        library = self.selected_library()
        if not library:
            return
        self.library_status_var.set(f"Rescanning {library['path']}...")

        def task() -> None:
            result = self.scanner.scan_folder(library['path'], library['media_type'])
            self.root.after(0, lambda: self.library_status_var.set(
                f"Rescan complete: {result['videos']} videos, {result['music']} music, {result['duplicates']} duplicates."
            ))
            self.root.after(0, self.refresh_all)

        self.run_task(task, f"Rescan finished for {library['path']}.")

    def remove_selected_library(self) -> None:
        library = self.selected_library()
        if not library:
            return
        confirmed = messagebox.askyesno(
            'MediaVault Pro',
            'Remove this library and its indexed movie/music rows from the database?'
        )
        if not confirmed:
            return

        def task() -> None:
            root_path = str(Path(library['path']))
            child_prefix = f'{root_path}\\%'
            with db.connection() as conn:
                conn.execute('DELETE FROM videos WHERE path = ? OR path LIKE ?', (root_path, child_prefix))
                conn.execute('DELETE FROM music WHERE path = ? OR path LIKE ?', (root_path, child_prefix))
                conn.execute('DELETE FROM libraries WHERE id = ?', (library['id'],))
            self.root.after(0, lambda: self.library_status_var.set('Library removed successfully.'))
            self.root.after(0, self.refresh_all)

        self.run_task(task, f"Removed library {library['path']}.")

    def start_server(self) -> None:
        if self.server_process and self.server_process.poll() is None:
            messagebox.showinfo('MediaVault Pro', 'Server is already running.')
            return
        host = self.host_var.get().strip() or '127.0.0.1'
        port = self.port_var.get().strip() or str(settings.port)
        if not port.isdigit():
            messagebox.showerror('MediaVault Pro', 'Port must be a number.')
            return

        command = [sys.executable, '-m', 'uvicorn', 'main:app', '--host', host, '--port', port]
        self.server_process = subprocess.Popen(
            command,
            cwd=str(Path(__file__).resolve().parent),
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
        )
        self.server_status_var.set(f'Server running on http://{host}:{port}')
        self.log(f'Server started on http://{host}:{port}')
        threading.Thread(target=self._pump_server_output, daemon=True).start()

    def _pump_server_output(self) -> None:
        if not self.server_process or not self.server_process.stdout:
            return
        for line in self.server_process.stdout:
            self.root.after(0, lambda chunk=line: self.log_server_output(chunk))
        self.root.after(0, lambda: self.server_status_var.set('Server stopped'))

    def stop_server(self) -> None:
        if not self.server_process or self.server_process.poll() is not None:
            self.server_status_var.set('Server already stopped')
            return
        self.server_process.terminate()
        self.server_process = None
        self.server_status_var.set('Server stopped')
        self.log('Server stopped')

    def open_web_dashboard(self) -> None:
        host = self.host_var.get().strip() or '127.0.0.1'
        port = self.port_var.get().strip() or str(settings.port)
        webbrowser.open(f'http://{host}:{port}')

    def open_path(self, path: Path) -> None:
        target = str(path)
        if not Path(target).exists():
            messagebox.showerror('MediaVault Pro', f'Path not found: {target}')
            return
        if sys.platform.startswith('win'):
            os.startfile(target)  # type: ignore[attr-defined]
        elif sys.platform == 'darwin':
            subprocess.Popen(['open', target])
        else:
            subprocess.Popen(['xdg-open', target])

    def on_close(self) -> None:
        try:
            self.stop_server()
        finally:
            self.root.destroy()

    @staticmethod
    def format_bytes(size: int) -> str:
        if not size:
            return '0 B'
        units = ['B', 'KB', 'MB', 'GB', 'TB']
        value = float(size)
        index = 0
        while value >= 1024 and index < len(units) - 1:
            value /= 1024
            index += 1
        return f'{value:.0f} {units[index]}' if index == 0 or value >= 10 else f'{value:.1f} {units[index]}'

    @staticmethod
    def format_dt(value: str) -> str:
        try:
            return datetime.fromisoformat(value).strftime('%Y-%m-%d %H:%M')
        except ValueError:
            return value

    def run(self) -> None:
        self.root.mainloop()


if __name__ == '__main__':
    MediaVaultDesktopApp().run()
