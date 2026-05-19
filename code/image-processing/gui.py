"""Desktop GUI for the barcode/QR code recognition system.

Uses tkinter for cross-platform compatibility.
Supports: image file loading, camera capture, recognition, result display.
"""

import sys
import os
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import cv2
import numpy as np
from PIL import Image, ImageTk
import threading

sys.path.insert(0, os.path.dirname(__file__))
from pipeline import run_pipeline, draw_results


class BarcodeScannerApp:
    """Main GUI application."""

    def __init__(self, root):
        self.root = root
        self.root.title('条码/二维码识别系统 - 数字图像处理课程大作业')
        self.root.geometry('1000x700')
        self.root.configure(bg='#f0f0f0')

        self.current_image = None
        self.current_path = None
        self.camera = None
        self.is_camera_active = False
        self.results = []

        self._setup_ui()

    def _setup_ui(self):
        """Build the UI layout."""
        # Main frames
        self.left_frame = tk.Frame(self.root, bg='#f0f0f0', width=300)
        self.left_frame.pack(side=tk.LEFT, fill=tk.Y, padx=10, pady=10)
        self.left_frame.pack_propagate(False)

        self.right_frame = tk.Frame(self.root, bg='#fff')
        self.right_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True, padx=10, pady=10)

        # --- Left panel: Controls ---
        tk.Label(self.left_frame, text='控制面板', font=('Microsoft YaHei', 14, 'bold'),
                 bg='#f0f0f0', fg='#333').pack(pady=(10, 20))

        # Load image button
        self.btn_load = tk.Button(self.left_frame, text='打开图片', font=('Microsoft YaHei', 11),
                                  bg='#1a73e8', fg='white', relief='flat',
                                  command=self.load_image, padx=20, pady=8, cursor='hand2')
        self.btn_load.pack(fill=tk.X, pady=5)

        # Camera button
        self.btn_camera = tk.Button(self.left_frame, text='打开摄像头', font=('Microsoft YaHei', 11),
                                    bg='#0f9d58', fg='white', relief='flat',
                                    command=self.toggle_camera, padx=20, pady=8, cursor='hand2')
        self.btn_camera.pack(fill=tk.X, pady=5)

        # Start recognition button
        self.btn_recognize = tk.Button(self.left_frame, text='开始识别', font=('Microsoft YaHei', 11, 'bold'),
                                       bg='#ea4335', fg='white', relief='flat',
                                       command=self.recognize, padx=20, pady=10, cursor='hand2')
        self.btn_recognize.pack(fill=tk.X, pady=(15, 5))

        # Save result button
        self.btn_save = tk.Button(self.left_frame, text='保存结果', font=('Microsoft YaHei', 11),
                                  bg='#555', fg='white', relief='flat',
                                  command=self.save_result, padx=20, pady=8, cursor='hand2')
        self.btn_save.pack(fill=tk.X, pady=5)

        # Separator
        ttk.Separator(self.left_frame, orient='horizontal').pack(fill=tk.X, pady=15)

        # Settings
        tk.Label(self.left_frame, text='识别设置', font=('Microsoft YaHei', 11, 'bold'),
                 bg='#f0f0f0', fg='#555').pack(anchor='w')

        self.adaptive_var = tk.BooleanVar(value=True)
        tk.Checkbutton(self.left_frame, text='使用自适应阈值', variable=self.adaptive_var,
                       bg='#f0f0f0', font=('Microsoft YaHei', 10)).pack(anchor='w', pady=2)

        # --- Right panel: Image display ---
        self.canvas_frame = tk.Frame(self.right_frame, bg='#ddd')
        self.canvas_frame.pack(fill=tk.BOTH, expand=True)

        self.canvas = tk.Canvas(self.canvas_frame, bg='#1a1a2e', highlightthickness=0)
        self.canvas.pack(fill=tk.BOTH, expand=True)

        self.canvas.bind('<Configure>', self._on_canvas_resize)

        # Placeholder text
        self.canvas.create_text(400, 300, text='请加载图片或打开摄像头',
                                fill='#666', font=('Microsoft YaHei', 16),
                                tags='placeholder')

        # --- Bottom: Results panel ---
        self.results_frame = tk.Frame(self.root, bg='#fafafa', height=150)
        self.results_frame.pack(side=tk.BOTTOM, fill=tk.X, padx=10, pady=(0, 10))
        self.results_frame.pack_propagate(False)

        # Results text
        self.results_text = tk.Text(self.results_frame, font=('Consolas', 11),
                                    bg='#fafafa', fg='#333', wrap=tk.WORD,
                                    height=5, borderwidth=1, relief='solid')
        self.results_text.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        # Status bar
        self.status_var = tk.StringVar(value='就绪')
        self.status_bar = tk.Label(self.root, textvariable=self.status_var,
                                   font=('Microsoft YaHei', 9), bg='#e0e0e0',
                                   fg='#666', anchor='w', padx=10)
        self.status_bar.pack(side=tk.BOTTOM, fill=tk.X)

    def _on_canvas_resize(self, event):
        """Redraw placeholder text centered on canvas resize."""
        self.canvas.delete('placeholder')
        self.canvas.create_text(event.width // 2, event.height // 2,
                                text='请加载图片或打开摄像头',
                                fill='#666', font=('Microsoft YaHei', 16),
                                tags='placeholder')

    def load_image(self):
        """Open file dialog and load an image."""
        filepath = filedialog.askopenfilename(
            title='选择图片',
            filetypes=[
                ('Image files', '*.png *.jpg *.jpeg *.bmp *.tiff'),
                ('All files', '*.*'),
            ]
        )
        if not filepath:
            return

        self._stop_camera()
        self.current_path = filepath
        img = cv2.imread(filepath)
        if img is None:
            messagebox.showerror('错误', f'无法读取图片: {filepath}')
            return

        self.current_image = img
        self._display_image(img)
        self.status_var.set(f'已加载: {os.path.basename(filepath)}')
        self.results_text.delete('1.0', tk.END)

    def toggle_camera(self):
        """Toggle camera on/off."""
        if self.is_camera_active:
            self._stop_camera()
            self.btn_camera.config(text='打开摄像头', bg='#0f9d58')
        else:
            self._start_camera()
            if self.is_camera_active:
                self.btn_camera.config(text='关闭摄像头', bg='#db4437')

    def _start_camera(self):
        """Start camera capture."""
        self.camera = cv2.VideoCapture(0)
        if not self.camera.isOpened():
            messagebox.showerror('错误', '无法打开摄像头')
            self.camera = None
            return

        self.is_camera_active = True
        self.status_var.set('摄像头已打开 - 点击"开始识别"进行扫描')
        self._update_camera()

    def _stop_camera(self):
        """Stop camera capture."""
        self.is_camera_active = False
        if self.camera:
            self.camera.release()
            self.camera = None

    def _update_camera(self):
        """Update camera frame in canvas."""
        if not self.is_camera_active or self.camera is None:
            return

        ret, frame = self.camera.read()
        if ret:
            self.current_image = frame.copy()
            self._display_image(frame)

        if self.is_camera_active:
            self.root.after(30, self._update_camera)

    def _display_image(self, img):
        """Display an OpenCV image on the canvas."""
        self.canvas.delete('all')

        # Resize to fit canvas
        canvas_w = self.canvas.winfo_width()
        canvas_h = self.canvas.winfo_height()

        if canvas_w < 50 or canvas_h < 50:
            canvas_w, canvas_h = 700, 500

        h, w = img.shape[:2]
        scale = min(canvas_w / w, canvas_h / h)

        new_w, new_h = int(w * scale), int(h * scale)
        resized = cv2.resize(img, (new_w, new_h))

        # Convert to RGB for PIL
        if len(resized.shape) == 2:
            resized = cv2.cvtColor(resized, cv2.COLOR_GRAY2RGB)
        else:
            resized = cv2.cvtColor(resized, cv2.COLOR_BGR2RGB)

        self._photo = ImageTk.PhotoImage(Image.fromarray(resized))

        # Center on canvas
        x = (canvas_w - new_w) // 2
        y = (canvas_h - new_h) // 2
        self.canvas.create_image(x, y, anchor='nw', image=self._photo)

    def recognize(self):
        """Run the recognition pipeline."""
        if self.current_image is None:
            messagebox.showwarning('提示', '请先加载图片或打开摄像头')
            return

        self.status_var.set('正在识别...')
        self.results_text.delete('1.0', tk.END)
        self.root.update()

        def run():
            try:
                results, vis_data = run_pipeline(
                    self.current_image,
                    adaptive=self.adaptive_var.get(),
                    visualize=True,
                )

                # Update UI on main thread
                self.root.after(0, lambda: self._on_recognition_done(results, vis_data))
            except Exception as e:
                self.root.after(0, lambda: self._on_recognition_error(str(e)))

        threading.Thread(target=run, daemon=True).start()

    def _on_recognition_done(self, results, vis_data):
        """Display recognition results."""
        # Update image with annotations
        annotated = draw_results(self.current_image, vis_data)
        self._display_image(annotated)

        # Display results text
        if not results:
            self.results_text.insert('1.0', '未检测到条码/二维码\n')
        else:
            for i, r in enumerate(results):
                self.results_text.insert(tk.END, f"[{r['type']}] {r['text']}\n")
                self.results_text.insert(tk.END, f"  置信度: {r['confidence']:.1%}\n\n")

        # Timing
        elapsed = vis_data.get('elapsed', {})
        self.results_text.insert(tk.END,
            f"--- 处理时间 ---\n"
            f"预处理: {elapsed.get('preprocess', 0)*1000:.0f}ms\n"
            f"定位:   {elapsed.get('localize', 0)*1000:.0f}ms\n"
            f"校正:   {elapsed.get('correct', 0)*1000:.0f}ms\n"
            f"解码:   {elapsed.get('decode', 0)*1000:.0f}ms\n"
            f"总计:   {elapsed.get('total', 0)*1000:.0f}ms\n"
        )

        self.results = results
        self.status_var.set(f'识别完成 - 检测到 {len(results)} 个条码/二维码')

    def _on_recognition_error(self, error_msg):
        """Handle recognition errors."""
        self.results_text.insert('1.0', f'识别出错:\n{error_msg}')
        self.status_var.set('识别失败')

    def save_result(self):
        """Save the annotated result image."""
        if self.current_image is None:
            return

        filepath = filedialog.asksaveasfilename(
            title='保存结果',
            defaultextension='.png',
            filetypes=[('PNG', '*.png'), ('JPEG', '*.jpg')],
        )
        if not filepath:
            return

        try:
            results, vis_data = run_pipeline(
                self.current_image,
                adaptive=self.adaptive_var.get(),
                visualize=True,
            )
            annotated = draw_results(self.current_image, vis_data)
            cv2.imwrite(filepath, annotated)
            self.status_var.set(f'结果已保存: {os.path.basename(filepath)}')
        except Exception as e:
            messagebox.showerror('错误', f'保存失败: {e}')

    def on_close(self):
        """Clean up on window close."""
        self._stop_camera()
        self.root.destroy()


def main():
    root = tk.Tk()
    app = BarcodeScannerApp(root)
    root.protocol('WM_DELETE_WINDOW', app.on_close)
    root.mainloop()


if __name__ == '__main__':
    main()
