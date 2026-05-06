import tkinter as tk
from tkinter import messagebox, ttk
import subprocess
import sys
import os
import threading
from pathlib import Path
from datetime import datetime

FONT_FAMILY = "微软雅黑"
BASE_DIR = Path(__file__).resolve().parent


def generate_report(shop_results):
    now = datetime.now().strftime('%Y%m%d_%H%M%S')
    log_dir = BASE_DIR / 'logs'
    log_dir.mkdir(exist_ok=True)

    lines = []
    lines.append("=" * 50)
    lines.append("  订单同步报告")
    lines.append(f"  生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    lines.append("=" * 50)
    lines.append("")

    for result in shop_results:
        shop = result['shop']
        lines.append(f"━━━ {shop} ━━━")
        lines.append(f"  总处理订单数: {result['total']}")
        lines.append(f"  实际变动数: {result['pending']}")
        lines.append(f"  成功数: {result['success']}")
        lines.append(f"  失败数: {result['fail']}")
        lines.append("")

    lines.append("=" * 50)
    lines.append("  同步完成")
    lines.append("=" * 50)

    report_content = '\n'.join(lines)
    report_file = log_dir / f'同步报告_{now}.txt'
    report_file.write_text(report_content, encoding='utf-8')

    return str(report_file)


class OrderSyncApp:
    def __init__(self, root):
        self.root = root
        self.root.title("订单同步工具")
        self.root.geometry("580x480")
        self.root.resizable(False, False)
        self._syncing = False
        self.shop_results = []
        self.setup_ui()

    def setup_ui(self):
        main_frame = ttk.Frame(self.root, padding=20)
        main_frame.pack(fill=tk.BOTH, expand=True)

        title_label = ttk.Label(
            main_frame, text="订单同步系统",
            font=(FONT_FAMILY, 16, "bold")
        )
        title_label.pack(pady=(0, 8))

        select_frame = ttk.Frame(main_frame)
        select_frame.pack(fill=tk.X, pady=(0, 8))

        ttk.Label(select_frame, text="选择店铺:", font=(FONT_FAMILY, 10)).pack(side=tk.LEFT, padx=(0, 8))

        self.shop_vars = {}
        shop_names = self._discover_shops()
        for name in shop_names:
            var = tk.BooleanVar(value=True)
            self.shop_vars[name] = var
            cb = ttk.Checkbutton(select_frame, text=name, variable=var)
            cb.pack(side=tk.LEFT, padx=4)

        self.status_var = tk.StringVar(value="就绪：选择店铺后点击开始同步")
        status_label = ttk.Label(
            main_frame, textvariable=self.status_var,
            font=(FONT_FAMILY, 10)
        )
        status_label.pack(pady=(0, 8))

        button_frame = ttk.Frame(main_frame)
        button_frame.pack(pady=(0, 8))

        self.sync_button = ttk.Button(
            button_frame, text="开始同步订单",
            command=self.start_sync, width=16
        )
        self.sync_button.pack(side=tk.LEFT, padx=4)

        open_folder_button = ttk.Button(
            button_frame, text="打开数据文件夹",
            command=self.open_data_folder, width=16
        )
        open_folder_button.pack(side=tk.LEFT, padx=4)

        open_log_button = ttk.Button(
            button_frame, text="打开日志文件夹",
            command=self.open_log_folder, width=16
        )
        open_log_button.pack(side=tk.LEFT, padx=4)

        log_frame = ttk.LabelFrame(main_frame, text="执行日志")
        log_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 4))

        self.log_text = tk.Text(log_frame, height=10, font=("Consolas", 9))
        self.log_text.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        scrollbar = ttk.Scrollbar(self.log_text, command=self.log_text.yview)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.log_text.config(yscrollcommand=scrollbar.set)

        stats_frame = ttk.Frame(main_frame)
        stats_frame.pack(fill=tk.X, pady=(4, 0))

        self.stats_var = tk.StringVar(value="等待同步...")
        stats_label = ttk.Label(
            stats_frame, textvariable=self.stats_var,
            font=(FONT_FAMILY, 9), foreground="#555"
        )
        stats_label.pack()

    def _discover_shops(self):
        shops = []
        for item in BASE_DIR.iterdir():
            if item.is_dir() and not item.name.startswith(('.', '_', 'system', 'venv', '__pycache__', 'logs', 'dist')):
                shops.append(item.name)
        return sorted(shops) if shops else ['Qmaster', 'tianyixinxuan']

    def start_sync(self):
        if self._syncing:
            return

        selected = [name for name, var in self.shop_vars.items() if var.get()]
        if not selected:
            messagebox.showwarning("提示", "请至少选择一个店铺")
            return

        self._syncing = True
        self.sync_button.config(state=tk.DISABLED)
        self.status_var.set("⏳ 正在同步：请稍候...")
        self.log_text.delete(1.0, tk.END)
        self.stats_var.set("")
        self.shop_results = []
        self.root.update()

        threading.Thread(target=self._run_sync, args=(selected,), daemon=True).start()

    def _run_sync(self, selected_shops):
        try:
            for shop in selected_shops:
                self.root.after(0, self._append_log, f"━━━ 开始同步店铺: {shop} ━━━\n")
                result = subprocess.run(
                    [sys.executable, str(BASE_DIR / "main.py"), f"--shops={shop}"],
                    capture_output=True,
                    text=True,
                    cwd=str(BASE_DIR),
                    timeout=600
                )
                output = result.stdout + result.stderr
                self.root.after(0, self._append_log, output)

                total = self._parse_number(output, '总处理:')
                pending = self._parse_number(output, '变动:')
                success = self._parse_number(output, '成功:')
                fail = self._parse_number(output, '失败:')

                self.shop_results.append({
                    'shop': shop,
                    'total': total,
                    'pending': pending,
                    'success': success,
                    'fail': fail
                })

            report_file = generate_report(self.shop_results)
            total_success = sum(r['success'] for r in self.shop_results)
            total_fail = sum(r['fail'] for r in self.shop_results)
            stats = (f"✅ 同步完成 | 成功: {total_success} | 失败: {total_fail} | "
                     f"报告已保存: logs/{Path(report_file).name}")
            self.root.after(0, self._on_sync_done, stats, report_file)
        except subprocess.TimeoutExpired:
            self.root.after(0, self._on_sync_error, "同步超时（超过5分钟），请检查网络或文件大小")
        except Exception as e:
            self.root.after(0, self._on_sync_error, str(e))

    def _parse_number(self, text, prefix):
        for line in text.split('\n'):
            if prefix in line:
                try:
                    return int(line.split(prefix)[-1].strip())
                except ValueError:
                    pass
        return 0

    def _on_sync_done(self, stats, report_file):
        self.stats_var.set(stats)
        self.status_var.set("✅ 同步完成")
        self._syncing = False
        self.sync_button.config(state=tk.NORMAL)
        messagebox.showinfo("操作完成", f"同步已完成！\n\n{stats}")

    def _on_sync_error(self, error_msg):
        self._append_log(f"执行出错：{error_msg}")
        self.status_var.set("❌ 执行出错")
        self.stats_var.set("同步异常终止")
        self._syncing = False
        self.sync_button.config(state=tk.NORMAL)
        messagebox.showerror("错误", f"执行出错：{error_msg}")

    def _append_log(self, text):
        self.log_text.insert(tk.END, text)
        self.log_text.see(tk.END)
        self.root.update()

    def open_data_folder(self):
        try:
            os.startfile(str(BASE_DIR))
        except Exception as e:
            messagebox.showerror("错误", f"无法打开文件夹：{e}")

    def open_log_folder(self):
        log_dir = BASE_DIR / 'logs'
        log_dir.mkdir(exist_ok=True)
        try:
            os.startfile(str(log_dir))
        except Exception as e:
            messagebox.showerror("错误", f"无法打开日志文件夹：{e}")


if __name__ == "__main__":
    root = tk.Tk()
    app = OrderSyncApp(root)
    root.mainloop()
