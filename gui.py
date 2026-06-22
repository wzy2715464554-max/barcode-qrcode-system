import importlib.util
from pathlib import Path
import tkinter as tk
from tkinter import filedialog, messagebox
from urllib.parse import urlparse
import webbrowser

import cv2
from PIL import Image, ImageTk


ROOT = Path(__file__).resolve().parent
CORE_PATH = ROOT / "1.py"


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
        self.root.geometry("1040x720")
        self.root.minsize(900, 620)

        self.cap = None
        self.running = False
        self.current_result = None
        self.current_frame = None
        self.current_decoded = []
        self.current_photo = None
        self.opened_urls = set()

        self.build_ui()
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)

    def build_ui(self):
        self.root.configure(bg="#f4f6f8")

        top = tk.Frame(self.root, bg="#ffffff", height=64)
        top.pack(side=tk.TOP, fill=tk.X)
        top.pack_propagate(False)

        title = tk.Label(
            top,
            text="条形码与二维码实时定位与解码系统",
            bg="#ffffff",
            fg="#1f2937",
            font=("Microsoft YaHei UI", 18, "bold"),
        )
        title.pack(side=tk.LEFT, padx=24)

        toolbar = tk.Frame(self.root, bg="#f4f6f8")
        toolbar.pack(side=tk.TOP, fill=tk.X, padx=18, pady=12)

        self.camera_btn = tk.Button(toolbar, text="打开摄像头识别", command=self.start_camera, width=16)
        self.camera_btn.pack(side=tk.LEFT, padx=6)

        self.stop_btn = tk.Button(toolbar, text="停止摄像头", command=self.stop_camera, width=14, state=tk.DISABLED)
        self.stop_btn.pack(side=tk.LEFT, padx=6)

        self.file_btn = tk.Button(toolbar, text="选择图片识别", command=self.open_image, width=14)
        self.file_btn.pack(side=tk.LEFT, padx=6)

        self.save_btn = tk.Button(toolbar, text="保存当前结果", command=self.save_current, width=14, state=tk.DISABLED)
        self.save_btn.pack(side=tk.LEFT, padx=6)

        main = tk.Frame(self.root, bg="#f4f6f8")
        main.pack(side=tk.TOP, fill=tk.BOTH, expand=True, padx=18, pady=(0, 18))

        self.image_panel = tk.Label(main, bg="#111827", fg="#d1d5db", text="请选择图片或打开摄像头", font=("Microsoft YaHei UI", 15))
        self.image_panel.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        side = tk.Frame(main, bg="#ffffff", width=310)
        side.pack(side=tk.RIGHT, fill=tk.Y, padx=(14, 0))
        side.pack_propagate(False)

        result_title = tk.Label(side, text="识别结果", bg="#ffffff", fg="#111827", font=("Microsoft YaHei UI", 14, "bold"))
        result_title.pack(anchor="w", padx=16, pady=(16, 8))

        self.result_text = tk.Text(side, height=18, wrap=tk.WORD, font=("Microsoft YaHei UI", 11), relief=tk.FLAT)
        self.result_text.pack(fill=tk.BOTH, expand=True, padx=16, pady=(0, 12))

        self.status = tk.Label(side, text="状态：等待操作", bg="#ffffff", fg="#4b5563", anchor="w", font=("Microsoft YaHei UI", 10))
        self.status.pack(fill=tk.X, padx=16, pady=(0, 16))

    def set_status(self, text):
        self.status.config(text=f"状态：{text}")

    def set_results(self, decoded):
        self.result_text.delete("1.0", tk.END)
        if not decoded:
            self.result_text.insert(tk.END, "未检测到可解码的条形码或二维码。")
            return

        for index, item in enumerate(decoded, 1):
            self.result_text.insert(tk.END, f"{index}. 类型：{item.format}\n")
            self.result_text.insert(tk.END, f"   内容：{item.text}\n\n")

    def show_frame(self, frame):
        panel_w = max(1, self.image_panel.winfo_width())
        panel_h = max(1, self.image_panel.winfo_height())

        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        image = Image.fromarray(rgb)
        image.thumbnail((panel_w, panel_h), Image.Resampling.LANCZOS)

        canvas = Image.new("RGB", (panel_w, panel_h), "#111827")
        x = (panel_w - image.width) // 2
        y = (panel_h - image.height) // 2
        canvas.paste(image, (x, y))

        self.current_photo = ImageTk.PhotoImage(canvas)
        self.image_panel.config(image=self.current_photo, text="")

    def process_frame(self, frame, open_mode="camera"):
        decoded = core.decode_barcodes(frame)
        self.open_urls(decoded, mode=open_mode)
        candidates = core.locate_barcode_candidates(frame)
        qr_patterns = core.locate_qr_finder_patterns(frame)
        result = core.draw_results(frame, decoded, candidates, qr_patterns)
        self.current_frame = frame.copy()
        self.current_decoded = decoded
        self.current_result = result
        self.save_btn.config(state=tk.NORMAL)
        self.set_results(decoded)
        return result, decoded

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
        self.root.after(30, self.update_camera)

    def stop_camera(self):
        self.running = False
        if self.cap is not None:
            self.cap.release()
            self.cap = None

        self.camera_btn.config(state=tk.NORMAL)
        self.stop_btn.config(state=tk.DISABLED)
        self.file_btn.config(state=tk.NORMAL)
        self.set_status("摄像头已停止")

    def open_image(self):
        self.stop_camera()
        path = filedialog.askopenfilename(
            title="选择待识别图片",
            filetypes=[
                ("图片文件", "*.jpg *.jpeg *.png *.bmp *.webp"),
                ("所有文件", "*.*"),
            ],
        )
        if not path:
            return

        frame = cv2.imread(path)
        if frame is None:
            messagebox.showerror("读取失败", f"无法读取图片：{path}")
            return

        result, decoded = self.process_frame(frame, open_mode="image")
        self.show_frame(result)
        self.set_status(f"图片识别完成，检测到 {len(decoded)} 个")

    def save_current(self):
        if self.current_result is None:
            messagebox.showinfo("保存结果", "当前没有可保存的识别结果。")
            return

        core.save_result(self.current_result, "gui_result")
        if self.current_frame is not None and self.current_decoded:
            core.save_rectified_regions(self.current_frame, self.current_decoded, "gui_result")
        messagebox.showinfo("保存结果", f"结果已保存到：\n{core.OUTPUT_DIR}")

    def on_close(self):
        self.stop_camera()
        self.root.destroy()


def main():
    root = tk.Tk()
    app = BarcodeApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
