import importlib.util
from pathlib import Path
import tkinter as tk
from tkinter import filedialog, messagebox, simpledialog, ttk
from urllib.parse import urlparse
import webbrowser

import cv2
from PIL import Image, ImageTk


ROOT = Path(__file__).resolve().parent
CORE_PATH = ROOT / "1.py"
PREVIEW_LIMIT = 220


def load_core():
    spec = importlib.util.spec_from_file_location("barcode_core", CORE_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


core = load_core()


class BarcodeApp:
    def __init__(self, root):
        self.root = root
        self.root.title("条形码与二维码实时定位与解码系统")
        self.root.geometry("1220x760")
        self.root.minsize(1080, 680)

        self.cap = None
        self.running = False
        self.current_result = None
        self.current_frame = None
        self.current_decoded = []
        self.current_photo = None
        self.opened_urls = set()
        self.last_text_path = None

        self.configure_style()
        self.build_ui()
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)

    def configure_style(self):
        self.colors = {
            "bg": "#eef2f6",
            "panel": "#ffffff",
            "ink": "#111827",
            "muted": "#64748b",
            "line": "#d9e2ec",
            "primary": "#2563eb",
            "primary_dark": "#1d4ed8",
            "danger": "#dc2626",
            "success": "#15803d",
            "canvas": "#0f172a",
        }
        self.root.configure(bg=self.colors["bg"])
        self.style = ttk.Style()
        self.style.theme_use("clam")
        self.style.configure("TFrame", background=self.colors["bg"])
        self.style.configure("Panel.TFrame", background=self.colors["panel"])
        self.style.configure("TLabel", background=self.colors["bg"], foreground=self.colors["ink"], font=("Microsoft YaHei UI", 10))
        self.style.configure("Panel.TLabel", background=self.colors["panel"], foreground=self.colors["ink"], font=("Microsoft YaHei UI", 10))
        self.style.configure("Title.TLabel", background=self.colors["panel"], foreground=self.colors["ink"], font=("Microsoft YaHei UI", 18, "bold"))
        self.style.configure("Subtle.TLabel", background=self.colors["panel"], foreground=self.colors["muted"], font=("Microsoft YaHei UI", 9))
        self.style.configure("Stat.TLabel", background=self.colors["panel"], foreground=self.colors["ink"], font=("Microsoft YaHei UI", 16, "bold"))
        self.style.configure("TButton", font=("Microsoft YaHei UI", 10), padding=(12, 8))
        self.style.map("TButton", background=[("active", "#e2e8f0")])
        self.style.configure("Primary.TButton", background=self.colors["primary"], foreground="#ffffff")
        self.style.map("Primary.TButton", background=[("active", self.colors["primary_dark"])])
        self.style.configure("Danger.TButton", background=self.colors["danger"], foreground="#ffffff")

    def build_ui(self):
        header = ttk.Frame(self.root, style="Panel.TFrame", height=74)
        header.pack(side=tk.TOP, fill=tk.X)
        header.pack_propagate(False)

        title_wrap = ttk.Frame(header, style="Panel.TFrame")
        title_wrap.pack(side=tk.LEFT, padx=24, pady=12)
        ttk.Label(title_wrap, text="条形码与二维码实时定位与解码系统", style="Title.TLabel").pack(anchor="w")
        ttk.Label(title_wrap, text="图片识别 · 摄像头实时识别 · 批量测试 · 结果导出", style="Subtle.TLabel").pack(anchor="w", pady=(3, 0))

        self.status_label = ttk.Label(header, text="状态：等待操作", style="Subtle.TLabel")
        self.status_label.pack(side=tk.RIGHT, padx=24)

        body = ttk.Frame(self.root)
        body.pack(fill=tk.BOTH, expand=True, padx=18, pady=18)

        left = ttk.Frame(body, style="Panel.TFrame", width=218)
        left.pack(side=tk.LEFT, fill=tk.Y)
        left.pack_propagate(False)

        self.build_toolbar(left)

        center = ttk.Frame(body, style="Panel.TFrame")
        center.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=14)
        self.build_preview(center)

        right = ttk.Frame(body, style="Panel.TFrame", width=350)
        right.pack(side=tk.RIGHT, fill=tk.Y)
        right.pack_propagate(False)
        self.build_result_panel(right)

    def build_toolbar(self, parent):
        ttk.Label(parent, text="操作", style="Panel.TLabel", font=("Microsoft YaHei UI", 13, "bold")).pack(anchor="w", padx=16, pady=(18, 10))

        self.camera_btn = ttk.Button(parent, text="打开摄像头识别", command=self.start_camera, style="Primary.TButton")
        self.camera_btn.pack(fill=tk.X, padx=16, pady=5)

        self.stop_btn = ttk.Button(parent, text="停止摄像头", command=self.stop_camera, style="Danger.TButton", state=tk.DISABLED)
        self.stop_btn.pack(fill=tk.X, padx=16, pady=5)

        self.file_btn = ttk.Button(parent, text="选择图片识别", command=self.open_image)
        self.file_btn.pack(fill=tk.X, padx=16, pady=5)

        self.batch_btn = ttk.Button(parent, text="批量测试文件夹", command=self.batch_test)
        self.batch_btn.pack(fill=tk.X, padx=16, pady=5)

        self.make_qr_btn = ttk.Button(parent, text="生成网址二维码", command=self.create_url_qrcode)
        self.make_qr_btn.pack(fill=tk.X, padx=16, pady=5)

        ttk.Separator(parent).pack(fill=tk.X, padx=16, pady=14)

        self.save_btn = ttk.Button(parent, text="保存当前结果", command=self.save_current, state=tk.DISABLED)
        self.save_btn.pack(fill=tk.X, padx=16, pady=5)

        self.preprocess_btn = ttk.Button(parent, text="保存预处理图", command=self.save_preprocess, state=tk.DISABLED)
        self.preprocess_btn.pack(fill=tk.X, padx=16, pady=5)

        self.copy_btn = ttk.Button(parent, text="复制识别内容", command=self.copy_results, state=tk.DISABLED)
        self.copy_btn.pack(fill=tk.X, padx=16, pady=5)

        ttk.Separator(parent).pack(fill=tk.X, padx=16, pady=14)

        legend = ttk.Frame(parent, style="Panel.TFrame")
        legend.pack(fill=tk.X, padx=16, pady=(0, 10))
        ttk.Label(legend, text="颜色说明", style="Panel.TLabel", font=("Microsoft YaHei UI", 11, "bold")).pack(anchor="w")
        ttk.Label(legend, text="橙色：条形码候选区", style="Subtle.TLabel").pack(anchor="w", pady=(6, 0))
        ttk.Label(legend, text="蓝色：二维码定位角", style="Subtle.TLabel").pack(anchor="w")
        ttk.Label(legend, text="绿色：成功解码区域", style="Subtle.TLabel").pack(anchor="w")

    def build_preview(self, parent):
        top = ttk.Frame(parent, style="Panel.TFrame")
        top.pack(fill=tk.X, padx=18, pady=(16, 8))
        ttk.Label(top, text="图像预览", style="Panel.TLabel", font=("Microsoft YaHei UI", 13, "bold")).pack(side=tk.LEFT)
        self.mode_label = ttk.Label(top, text="当前模式：待机", style="Subtle.TLabel")
        self.mode_label.pack(side=tk.RIGHT)

        self.image_panel = tk.Label(
            parent,
            bg=self.colors["canvas"],
            fg="#cbd5e1",
            text="请选择图片、打开摄像头，或运行批量测试",
            font=("Microsoft YaHei UI", 15),
            relief=tk.FLAT,
        )
        self.image_panel.pack(fill=tk.BOTH, expand=True, padx=18, pady=(0, 18))

    def build_result_panel(self, parent):
        ttk.Label(parent, text="识别结果", style="Panel.TLabel", font=("Microsoft YaHei UI", 13, "bold")).pack(anchor="w", padx=16, pady=(18, 10))

        stats = ttk.Frame(parent, style="Panel.TFrame")
        stats.pack(fill=tk.X, padx=16, pady=(0, 12))
        self.count_label = ttk.Label(stats, text="0", style="Stat.TLabel")
        self.count_label.grid(row=0, column=0, sticky="w")
        ttk.Label(stats, text="检测数量", style="Subtle.TLabel").grid(row=1, column=0, sticky="w", pady=(0, 8))
        self.url_label = ttk.Label(stats, text="否", style="Stat.TLabel")
        self.url_label.grid(row=0, column=1, sticky="w", padx=(40, 0))
        ttk.Label(stats, text="包含网址", style="Subtle.TLabel").grid(row=1, column=1, sticky="w", padx=(40, 0), pady=(0, 8))

        self.result_text = tk.Text(
            parent,
            height=18,
            wrap=tk.WORD,
            font=("Microsoft YaHei UI", 10),
            relief=tk.FLAT,
            bg="#f8fafc",
            fg=self.colors["ink"],
            padx=10,
            pady=10,
        )
        self.result_text.pack(fill=tk.BOTH, expand=True, padx=16, pady=(0, 12))

        self.batch_summary = ttk.Label(parent, text="批量测试：未运行", style="Subtle.TLabel", wraplength=310)
        self.batch_summary.pack(fill=tk.X, padx=16, pady=(0, 16))

    def set_status(self, text):
        self.status_label.config(text=f"状态：{text}")

    def set_mode(self, text):
        self.mode_label.config(text=f"当前模式：{text}")

    def preview_text(self, text):
        return core.preview_text(text, PREVIEW_LIMIT)

    def result_full_text(self):
        if not self.current_decoded:
            return ""
        rows = []
        for index, item in enumerate(self.current_decoded, 1):
            rows.append(f"{index}. 类型：{item.format}\n   内容：{item.text}")
        return "\n\n".join(rows)

    def set_results(self, decoded):
        self.result_text.delete("1.0", tk.END)
        self.count_label.config(text=str(len(decoded)))
        has_url = any(self.normalize_url(item.text) for item in decoded)
        self.url_label.config(text="是" if has_url else "否")
        self.copy_btn.config(state=tk.NORMAL if decoded else tk.DISABLED)

        if not decoded:
            self.result_text.insert(tk.END, "未检测到可解码的条形码或二维码。")
            return

        for index, item in enumerate(decoded, 1):
            text = item.text or ""
            shortened = self.preview_text(text)
            suffix = "\n   说明：内容较长，完整文本会在保存结果时写入 txt 文件。\n" if len(text) > PREVIEW_LIMIT else "\n"
            self.result_text.insert(tk.END, f"{index}. 类型：{item.format}\n")
            self.result_text.insert(tk.END, f"   内容：{shortened}{suffix}\n")

    def show_frame(self, frame):
        panel_w = max(1, self.image_panel.winfo_width())
        panel_h = max(1, self.image_panel.winfo_height())

        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        image = Image.fromarray(rgb)
        image.thumbnail((panel_w, panel_h), Image.Resampling.LANCZOS)

        canvas = Image.new("RGB", (panel_w, panel_h), self.colors["canvas"])
        x = (panel_w - image.width) // 2
        y = (panel_h - image.height) // 2
        canvas.paste(image, (x, y))

        self.current_photo = ImageTk.PhotoImage(canvas)
        self.image_panel.config(image=self.current_photo, text="")

    def process_frame(self, frame, open_mode="camera"):
        analysis = core.analyze_frame(frame)
        decoded = analysis["decoded"]
        self.open_urls(decoded, mode=open_mode)
        self.current_frame = frame.copy()
        self.current_decoded = decoded
        self.current_result = analysis["result"]
        self.save_btn.config(state=tk.NORMAL)
        self.preprocess_btn.config(state=tk.NORMAL)
        self.set_results(decoded)
        return analysis["result"], decoded

    def normalize_url(self, text):
        value = (text or "").strip()
        if value.startswith(("http://", "https://")):
            parsed = urlparse(value)
            if parsed.netloc:
                return value
        if value.lower().startswith("www."):
            return "https://" + value
        return None

    def open_urls(self, decoded, mode="camera"):
        for item in decoded:
            url = self.normalize_url(item.text)
            if not url:
                continue
            if mode == "image":
                self.set_status(f"检测到网址，正在打开：{url}")
                webbrowser.open(url)
            elif url not in self.opened_urls:
                self.opened_urls.add(url)
                self.set_status(f"检测到网址，正在打开：{url}")
                webbrowser.open(url)

    def start_camera(self):
        if self.running:
            return
        self.cap = cv2.VideoCapture(0)
        if not self.cap.isOpened():
            self.cap = None
            messagebox.showerror("摄像头错误", "无法打开摄像头，请检查摄像头是否被其他程序占用。")
            return

        self.running = True
        self.camera_btn.config(state=tk.DISABLED)
        self.stop_btn.config(state=tk.NORMAL)
        self.file_btn.config(state=tk.DISABLED)
        self.batch_btn.config(state=tk.DISABLED)
        self.set_mode("摄像头实时识别")
        self.set_status("摄像头识别中")
        self.update_camera()

    def update_camera(self):
        if not self.running or self.cap is None:
            return
        ok, frame = self.cap.read()
        if not ok:
            self.stop_camera()
            messagebox.showwarning("摄像头提示", "读取摄像头画面失败。")
            return

        result, decoded = self.process_frame(frame, open_mode="camera")
        self.show_frame(result)
        self.set_status(f"摄像头识别中，当前检测到 {len(decoded)} 个")
        self.root.after(45, self.update_camera)

    def stop_camera(self):
        self.running = False
        if self.cap is not None:
            self.cap.release()
            self.cap = None
        self.camera_btn.config(state=tk.NORMAL)
        self.stop_btn.config(state=tk.DISABLED)
        self.file_btn.config(state=tk.NORMAL)
        self.batch_btn.config(state=tk.NORMAL)
        self.set_mode("待机")
        self.set_status("摄像头已停止")

    def open_image(self):
        self.stop_camera()
        path = filedialog.askopenfilename(
            title="选择待识别图片",
            filetypes=[("图片文件", "*.jpg *.jpeg *.png *.bmp *.webp"), ("所有文件", "*.*")],
        )
        if not path:
            return
        frame = cv2.imread(path)
        if frame is None:
            messagebox.showerror("读取失败", f"无法读取图片：{path}")
            return

        result, decoded = self.process_frame(frame, open_mode="image")
        self.show_frame(result)
        self.set_mode("图片识别")
        self.set_status(f"图片识别完成，检测到 {len(decoded)} 个")

    def batch_test(self):
        self.stop_camera()
        folder = filedialog.askdirectory(title="选择批量测试图片文件夹")
        if not folder:
            return
        self.set_mode("批量测试")
        self.set_status("批量测试运行中")
        self.root.update_idletasks()

        report = core.batch_test_folder(folder, save_visuals=True)
        self.batch_summary.config(
            text=(
                f"批量测试：{report['success']}/{report['total']}，"
                f"成功率 {report['rate']:.2f}%\nCSV：{report['csv_path']}"
            )
        )
        self.result_text.delete("1.0", tk.END)
        self.result_text.insert(tk.END, f"批量测试完成\n")
        self.result_text.insert(tk.END, f"总图片数：{report['total']}\n")
        self.result_text.insert(tk.END, f"成功识别：{report['success']}\n")
        self.result_text.insert(tk.END, f"成功率：{report['rate']:.2f}%\n\n")
        self.result_text.insert(tk.END, f"CSV 报告：\n{report['csv_path']}\n\n")
        if report["visual_dir"]:
            self.result_text.insert(tk.END, f"可视化结果：\n{report['visual_dir']}\n\n")
        failed = [row for row in report["rows"] if row["success"] == "否"]
        if failed:
            self.result_text.insert(tk.END, "失败样例：\n")
            for row in failed[:12]:
                self.result_text.insert(tk.END, f"- {Path(row['file']).name}\n")
        self.count_label.config(text=str(report["success"]))
        self.url_label.config(text="-")
        self.copy_btn.config(state=tk.NORMAL)
        self.set_status("批量测试完成")
        messagebox.showinfo("批量测试完成", f"成功率：{report['rate']:.2f}%\nCSV 报告已保存到：\n{report['csv_path']}")

    def create_url_qrcode(self):
        url = simpledialog.askstring("生成网址二维码", "请输入图片地址或网页地址：", parent=self.root)
        if not url:
            return
        url = url.strip()
        normalized = self.normalize_url(url)
        if normalized:
            url = normalized

        path = core.make_qr_code(url)
        image = cv2.imread(str(path))
        if image is not None:
            self.current_result = image
            self.current_frame = image.copy()
            self.current_decoded = []
            self.save_btn.config(state=tk.NORMAL)
            self.preprocess_btn.config(state=tk.NORMAL)
            self.show_frame(image)

        self.result_text.delete("1.0", tk.END)
        self.result_text.insert(tk.END, f"已生成二维码：\n{path}\n\n二维码内容：\n{url}\n")
        self.count_label.config(text="1")
        self.url_label.config(text="是" if self.normalize_url(url) else "否")
        self.set_mode("二维码生成")
        self.set_status("网址二维码已生成")
        messagebox.showinfo("生成成功", f"二维码已保存到：\n{path}")

    def save_current(self):
        if self.current_result is None:
            messagebox.showinfo("保存结果", "当前没有可保存的识别结果。")
            return
        result_path = core.save_result(self.current_result, "gui_result")
        self.last_text_path = core.save_decoded_text(self.current_decoded, "gui_result")
        if self.current_frame is not None and self.current_decoded:
            core.save_rectified_regions(self.current_frame, self.current_decoded, "gui_result")
        messagebox.showinfo("保存结果", f"结果图：\n{result_path}\n\n完整文本：\n{self.last_text_path}")

    def save_preprocess(self):
        if self.current_frame is None:
            messagebox.showinfo("保存预处理图", "当前没有可处理的图片。")
            return
        paths = core.save_preprocess_images(self.current_frame, "gui_preprocess")
        messagebox.showinfo("保存预处理图", "已保存：\n" + "\n".join(str(path) for path in paths))

    def copy_results(self):
        text = self.result_full_text() or self.result_text.get("1.0", tk.END).strip()
        if not text:
            messagebox.showinfo("复制识别内容", "当前没有可复制内容。")
            return
        self.root.clipboard_clear()
        self.root.clipboard_append(text)
        self.set_status("识别内容已复制到剪贴板")

    def on_close(self):
        self.stop_camera()
        self.root.destroy()


def main():
    root = tk.Tk()
    BarcodeApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
