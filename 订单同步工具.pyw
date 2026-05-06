import tkinter as tk
from tkinter import messagebox, ttk
import subprocess
import sys
import os
import threading
from pathlib import Path

FONT_FAMILY = "微软雅黑"


class OrderSyncApp:
    def __init__(self, root):
        self.root = root
        self.root.title("订单同步工具")
        self.root.geometry("520x360")
        self.root.resizable(False, False)
        self._syncing = False
        self.setup_ui()

    def setup_ui(self):
        main_frame = ttk.Frame(self.root, padding=24)
        main_frame.pack(fill=tk.BOTH, expand=True)

        title_label = ttk.Label(
            main_frame, text="订单同步系统",
            font=(FONT_FAMILY, 16, "bold")
        )
        title_label.pack(pady=(0, 16))

        self.status_var = tk.StringVar(value="就绪：点击下方按钮开始同步")
        status_label = ttk.Label(
            main_frame, textvariable=self.status_var,
            font=(FONT_FAMILY, 10)
        )
        status_label.pack(pady=(0, 16))

        button_frame = ttk.Frame(main_frame)
        button_frame.pack(pady=(0, 16))

        self.sync_button = ttk.Button(
            button_frame, text="开始同步订单",
            command=self.start_sync, width=20
        )
        self.sync_button.pack(side=tk.LEFT, padx=8)

        open_folder_button = ttk.Button(
            button_frame, text="打开数据文件夹",
            command=self.open_data_folder, width=20
        )
        open_folder_button.pack(side=tk.LEFT, padx=8)

        log_frame = ttk.LabelFrame(main_frame, text="执行日志")
        log_frame.pack(fill=tk.BOTH, expand=True)

        self.log_text = tk.Text(log_frame, height=8, font=("Consolas", 9))
        self.log_text.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        scrollbar = ttk.Scrollbar(self.log_text, command=self.log_text.yview)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.log_text.config(yscrollcommand=scrollbar.set)

    def start_sync(self):
        if self._syncing:
            return
        self._syncing = True
        self.sync_button.config(state=tk.DISABLED)
        self.status_var.set("⏳ 正在同步：请稍候...")
        self.log_text.delete(1.0, tk.END)
        self.log_text.insert(tk.END, "开始执行订单同步...\n")
        self.root.update()

        threading.Thread(target=self._run_sync, daemon=True).start()

    def _run_sync(self):
        try:
            script_dir = Path(__file__).resolve().parent
            result = subprocess.run(
                [sys.executable, str(script_dir / "main.py")],
                capture_output=True,
                text=True,
                cwd=str(script_dir)
            )
            self.root.after(0, self._on_sync_done, result)
        except Exception as e:
            self.root.after(0, self._on_sync_error, str(e))

    def _on_sync_done(self, result):
        self.log_text.insert(tk.END, result.stdout)
        if result.stderr:
            self.log_text.insert(tk.END, "\n错误信息：\n" + result.stderr)
        self.status_var.set("✅ 同步完成：请查看执行结果")
        self._syncing = False
        self.sync_button.config(state=tk.NORMAL)
        messagebox.showinfo("操作完成", "订单同步已完成！")

    def _on_sync_error(self, error_msg):
        self.log_text.insert(tk.END, f"执行出错：{error_msg}")
        self.status_var.set("❌ 执行出错：请查看日志")
        self._syncing = False
        self.sync_button.config(state=tk.NORMAL)
        messagebox.showerror("错误", f"执行出错：{error_msg}")

    def open_data_folder(self):
        try:
            data_folder = Path(__file__).resolve().parent
            os.startfile(str(data_folder))
        except Exception as e:
            messagebox.showerror("错误", f"无法打开文件夹：{e}")


if __name__ == "__main__":
    root = tk.Tk()
    app = OrderSyncApp(root)
    root.mainloop()
