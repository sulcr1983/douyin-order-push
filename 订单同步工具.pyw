import tkinter as tk
from tkinter import messagebox, ttk
import subprocess
import os
import sys

class OrderSyncApp:
    def __init__(self, root):
        self.root = root
        self.root.title("订单同步工具")
        self.root.geometry("500x300")
        self.root.resizable(False, False)
        
        # 设置界面样式
        self.setup_ui()
    
    def setup_ui(self):
        # 创建主框架
        main_frame = ttk.Frame(self.root, padding="20")
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # 标题
        title_label = ttk.Label(main_frame, text="订单同步系统", font=("微软雅黑", 16, "bold"))
        title_label.pack(pady=20)
        
        # 状态文本
        self.status_var = tk.StringVar(value="就绪：点击下方按钮开始同步")
        status_label = ttk.Label(main_frame, textvariable=self.status_var, font=("微软雅黑", 10))
        status_label.pack(pady=10)
        
        # 操作按钮
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(pady=20)
        
        sync_button = ttk.Button(button_frame, text="开始同步订单", command=self.start_sync, width=20)
        sync_button.pack(side=tk.LEFT, padx=10)
        
        open_folder_button = ttk.Button(button_frame, text="打开CSV文件夹", command=self.open_csv_folder, width=20)
        open_folder_button.pack(side=tk.LEFT, padx=10)
        
        # 日志文本框
        log_frame = ttk.LabelFrame(main_frame, text="执行日志")
        log_frame.pack(fill=tk.BOTH, expand=True, pady=10)
        
        self.log_text = tk.Text(log_frame, height=8, font=("Consolas", 9))
        self.log_text.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # 滚动条
        scrollbar = ttk.Scrollbar(self.log_text, command=self.log_text.yview)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.log_text.config(yscrollcommand=scrollbar.set)
    
    def start_sync(self):
        try:
            self.status_var.set("正在同步：请稍候...")
            self.log_text.delete(1.0, tk.END)
            self.log_text.insert(tk.END, "开始执行订单同步...\n")
            self.root.update()
            
            # 执行同步脚本
            result = subprocess.run(
                [sys.executable, "sync_orders_v6.py"],
                capture_output=True,
                text=True,
                cwd=os.path.dirname(os.path.abspath(__file__))
            )
            
            # 显示执行结果
            self.log_text.insert(tk.END, result.stdout)
            if result.stderr:
                self.log_text.insert(tk.END, "\n错误信息：\n" + result.stderr)
            
            self.status_var.set("同步完成：请查看执行结果")
            messagebox.showinfo("操作完成", "订单同步已完成！")
            
        except Exception as e:
            error_msg = f"执行出错：{str(e)}"
            self.log_text.insert(tk.END, error_msg)
            self.status_var.set("执行出错：请查看日志")
            messagebox.showerror("错误", error_msg)
    
    def open_csv_folder(self):
        try:
            csv_folder = os.path.join(os.path.dirname(os.path.abspath(__file__)), "csv")
            if not os.path.exists(csv_folder):
                os.makedirs(csv_folder)
            os.startfile(csv_folder)
        except Exception as e:
            messagebox.showerror("错误", f"无法打开文件夹：{str(e)}")

if __name__ == "__main__":
    root = tk.Tk()
    app = OrderSyncApp(root)
    root.mainloop()