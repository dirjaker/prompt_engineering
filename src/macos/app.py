"""
macOS GUI wrapper for Prompt Engineering Platform
Provides a tkinter interface for managing prompts and running the web dashboard.
"""
import sys
import os
import threading
import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


class PromptEngineeringApp:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("Prompt Engineering Platform")
        self.root.geometry("850x650")
        self.root.configure(bg="#0d1117")

        self.server_thread = None
        self.server_running = False
        self.server_instance = None

        self._build_ui()

    def _build_ui(self):
        style = ttk.Style()
        style.theme_use("clam")
        style.configure("TFrame", background="#0d1117")
        style.configure("TLabel", background="#0d1117", foreground="#c9d1d9", font=("Helvetica", 12))
        style.configure("Header.TLabel", font=("Helvetica", 18, "bold"), foreground="#58a6ff")
        style.configure("Status.TLabel", font=("Helvetica", 11), foreground="#8b949e")

        # Header
        header = ttk.Frame(self.root)
        header.pack(fill=tk.X, padx=20, pady=(20, 10))
        ttk.Label(header, text="Prompt Engineering", style="Header.TLabel").pack(side=tk.LEFT)
        self.status_label = ttk.Label(header, text="Web Server: Stopped", style="Status.TLabel")
        self.status_label.pack(side=tk.RIGHT)

        # Server controls
        ctrl_frame = ttk.Frame(self.root)
        ctrl_frame.pack(fill=tk.X, padx=20, pady=10)

        self.start_btn = ttk.Button(ctrl_frame, text="Start Web Server", command=self.toggle_server)
        self.start_btn.pack(side=tk.LEFT, padx=(0, 10))

        ttk.Button(ctrl_frame, text="Open in Browser", command=self.open_browser).pack(side=tk.LEFT)

        port_frame = ttk.Frame(self.root)
        port_frame.pack(fill=tk.X, padx=20, pady=(0, 10))
        ttk.Label(port_frame, text="Port:").pack(side=tk.LEFT)
        self.port_var = tk.StringVar(value="8080")
        ttk.Entry(port_frame, textvariable=self.port_var, width=8).pack(side=tk.LEFT, padx=8)

        # Quick actions
        action_frame = ttk.LabelFrame(self.root, text="Quick Actions")
        action_frame.pack(fill=tk.X, padx=20, pady=10)

        btn_row = ttk.Frame(action_frame)
        btn_row.pack(fill=tk.X, padx=10, pady=8)
        ttk.Button(btn_row, text="Show Stats", command=self.show_stats).pack(side=tk.LEFT, padx=(0, 8))
        ttk.Button(btn_row, text="List Prompts", command=self.list_prompts).pack(side=tk.LEFT, padx=(0, 8))

        # Create prompt section
        create_frame = ttk.LabelFrame(self.root, text="Create Prompt")
        create_frame.pack(fill=tk.X, padx=20, pady=10)

        name_row = ttk.Frame(create_frame)
        name_row.pack(fill=tk.X, padx=10, pady=4)
        ttk.Label(name_row, text="Name:").pack(side=tk.LEFT)
        self.prompt_name_var = tk.StringVar()
        ttk.Entry(name_row, textvariable=self.prompt_name_var, width=30).pack(side=tk.LEFT, padx=8)
        ttk.Label(name_row, text="Category:").pack(side=tk.LEFT)
        self.prompt_cat_var = tk.StringVar(value="general")
        ttk.Entry(name_row, textvariable=self.prompt_cat_var, width=15).pack(side=tk.LEFT, padx=8)
        ttk.Button(name_row, text="Create", command=self.create_prompt).pack(side=tk.LEFT, padx=8)

        ttk.Label(create_frame, text="Template:").pack(anchor=tk.W, padx=10)
        self.template_input = scrolledtext.ScrolledText(
            create_frame, height=4, bg="#161b22", fg="#c9d1d9",
            insertbackground="#c9d1d9", font=("SF Mono", 11), borderwidth=1, relief=tk.FLAT
        )
        self.template_input.pack(fill=tk.X, padx=10, pady=(0, 8))

        # Log area
        ttk.Label(self.root, text="Output:").pack(anchor=tk.W, padx=20, pady=(10, 0))
        self.log_area = scrolledtext.ScrolledText(
            self.root, height=10, bg="#161b22", fg="#c9d1d9",
            insertbackground="#c9d1d9", font=("SF Mono", 11), borderwidth=1, relief=tk.FLAT
        )
        self.log_area.pack(fill=tk.BOTH, expand=True, padx=20, pady=(4, 20))

        self.log("Prompt Engineering GUI initialized.")

    def log(self, msg):
        self.log_area.insert(tk.END, f"{msg}\n")
        self.log_area.see(tk.END)

    def toggle_server(self):
        if self.server_running:
            self.stop_server()
        else:
            self.start_server()

    def start_server(self):
        port = int(self.port_var.get())
        self.log(f"Starting web server on port {port}...")

        def run():
            try:
                import uvicorn
                from src.web.app import app
                self.server_instance = uvicorn.Server(uvicorn.Config(app, host="0.0.0.0", port=port, log_level="warning"))
                self.server_instance.run()
            except Exception as e:
                self.root.after(0, lambda: self.log(f"Server error: {e}"))
                self.root.after(0, lambda: self._set_server_state(False))

        self.server_thread = threading.Thread(target=run, daemon=True)
        self.server_thread.start()
        self._set_server_state(True)
        self.log(f"Web server started at http://localhost:{port}")

    def stop_server(self):
        if self.server_instance:
            self.server_instance.should_exit = True
        self._set_server_state(False)
        self.log("Web server stopped.")

    def _set_server_state(self, running):
        self.server_running = running
        if running:
            self.start_btn.configure(text="Stop Web Server")
            self.status_label.configure(text="Web Server: Running", foreground="#3fb950")
        else:
            self.start_btn.configure(text="Start Web Server")
            self.status_label.configure(text="Web Server: Stopped", foreground="#8b949e")

    def open_browser(self):
        import webbrowser
        port = self.port_var.get()
        webbrowser.open(f"http://localhost:{port}")
        self.log(f"Opened browser at http://localhost:{port}")

    def show_stats(self):
        self.log("Fetching platform stats...")
        try:
            import urllib.request
            import json
            port = self.port_var.get()
            req = urllib.request.urlopen(f"http://localhost:{port}/api/stats")
            data = json.loads(req.read())
            self.log(f"  Prompts: {data['total_prompts']}")
            self.log(f"  Versions: {data['total_versions']}")
            self.log(f"  Evaluations: {data['total_evaluations']}")
            self.log(f"  A/B Tests: {data['total_ab_tests']}")
            if data.get('categories'):
                self.log(f"  Categories: {data['categories']}")
        except Exception as e:
            self.log(f"  Error: {e} (Is the web server running?)")

    def list_prompts(self):
        self.log("Fetching prompt list...")
        try:
            import urllib.request
            import json
            port = self.port_var.get()
            req = urllib.request.urlopen(f"http://localhost:{port}/api/prompts")
            data = json.loads(req.read())
            if data:
                for p in data:
                    self.log(f"  [{p['status']}] {p['name']} (v{p['current_version']}) - {p['category']}")
            else:
                self.log("  No prompts found.")
        except Exception as e:
            self.log(f"  Error: {e} (Is the web server running?)")

    def create_prompt(self):
        name = self.prompt_name_var.get().strip()
        if not name:
            messagebox.showwarning("Warning", "Please enter prompt name.")
            return
        template = self.template_input.get("1.0", tk.END).strip()
        self.log(f"Creating prompt: {name}...")
        try:
            import urllib.request
            import json
            port = self.port_var.get()
            body = json.dumps({
                "name": name,
                "category": self.prompt_cat_var.get(),
                "template": template,
            }).encode()
            req = urllib.request.Request(
                f"http://localhost:{port}/api/prompts",
                data=body,
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            resp = urllib.request.urlopen(req)
            data = json.loads(resp.read())
            self.log(f"  Created: {data['id']} (v{data['version']})")
        except Exception as e:
            self.log(f"  Error: {e} (Is the web server running?)")

    def run(self):
        self.root.mainloop()


def main():
    app = PromptEngineeringApp()
    app.run()


if __name__ == "__main__":
    main()
