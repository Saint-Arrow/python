import tkinter as tk
from tkinter import messagebox
from tkinter import ttk
import os
import threading
from relay_controller import control_instance

class relay_ui:
    def __init__(self, root):
        self.root = root
        self.root.title("继电器测试工具")
        self.root.geometry("450x350")
        
        # 创建主框架
        main_frame = ttk.Frame(root, padding="10")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        
        self.COM_label = ttk.Label(main_frame, text="COM")
        self.COM_label.grid(row=1, column=0, sticky=tk.W, pady=5)
        self.COM_range_var = tk.StringVar(value="COM24")
        self.COM_range_entry = ttk.Entry(main_frame, textvariable=self.COM_range_var, width=30)
        self.COM_range_entry.grid(row=1, column=2, sticky=(tk.W, tk.E), pady=5)

        self.IP_label = ttk.Label(main_frame, text="ip")
        self.IP_label.grid(row=2, column=0, sticky=tk.W, pady=5)
        self.IP_range_var = tk.StringVar(value="192.168.13.169")
        self.IP_range_entry = ttk.Entry(main_frame, textvariable=self.IP_range_var, width=30)
        self.IP_range_entry.grid(row=2, column=2, sticky=(tk.W, tk.E), pady=5)

        self.wait_time_label = ttk.Label(main_frame, text="wait_time")
        self.wait_time_label.grid(row=3, column=0, sticky=tk.W, pady=5)
        self.wait_time_range_var = tk.IntVar(value="50")
        self.wait_time_range_entry = ttk.Entry(main_frame, textvariable=self.wait_time_range_var, width=30)
        self.wait_time_range_entry.grid(row=3, column=2, sticky=(tk.W, tk.E), pady=5)

        # 确认按钮
        self.extract_button = ttk.Button(main_frame, text="start", command=self.test_start)
        self.extract_button.grid(row=8, column=0, pady=20)

        self.desc_label = ttk.Label(main_frame, text="链接")
        self.desc_label.grid(row=9, column=0, sticky=tk.W, pady=5)
        self.desc_range_var = tk.StringVar(value="https://item.jd.com/10193094063333.html")
        self.desc_range_entry = ttk.Entry(main_frame, textvariable=self.desc_range_var, width=30)
        self.desc_range_entry.grid(row=9,column=2,sticky=(tk.W, tk.E), padx=50)

        # 配置网格权重
        main_frame.columnconfigure(0, weight=1)
        root.columnconfigure(0, weight=1)
        root.rowconfigure(0, weight=1)

    def test_start(self):
        self.extract_button.config(state='disabled')
        
    def test_start(self):
        self.extract_button.config(state='disabled')
        
        def run_control():
            control_instance(port=self.COM_range_var.get(),
                     time_wait_to_ping=self.wait_time_range_var.get(),
                     ping_target=self.IP_range_var.get())
            #self.extract_button.config(state='normal')

        control_thread = threading.Thread(target=run_control)
        control_thread.daemon = True
        control_thread.start()
def main():
    root = tk.Tk()
    app = relay_ui(root)
    root.mainloop()

if __name__ == "__main__":
    main()