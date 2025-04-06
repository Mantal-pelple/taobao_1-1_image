import os
import threading
import tkinter as tk
from tkinter import filedialog, ttk
from PIL import Image, ImageOps
from PIL.Image import Resampling
from queue import Queue, Empty

Image.MAX_IMAGE_PIXELS = None

class ImageProcessorApp:
    def __init__(self, root):
        self.root = root
        self.root.title("淘宝图片1:1处理程序")
        self.root.geometry("506x300")  # 稍微增加高度以容纳进度条
        self.root.geometry("+400+130")

        # 线程控制
        self.processing = False
        self.thread = None
        self.message_queue = Queue()

        self.setup_ui()
        self.check_queue()

    def setup_ui(self):
        # 路径输入框
        self.editor = tk.Entry(self.root, width=50)
        self.editor.place(x=10, y=10)

        # 选择目录按钮
        self.select_btn = tk.Button(self.root, text="选择目录", command=self.select_directory)
        self.select_btn.place(x=370, y=5)

        # 运行按钮
        self.run_btn = tk.Button(self.root, text="直接运行", command=self.start_processing)
        self.run_btn.place(x=435, y=5)

        # 停止按钮
        self.stop_btn = tk.Button(self.root, text="停止处理", command=self.stop_processing, state=tk.DISABLED)
        self.stop_btn.place(x=435, y=35)

        # 信息显示区域
        self.label = tk.Label(self.root, padx=0, pady=0, relief="solid",
                              anchor='nw', justify=tk.LEFT, wraplength=480)
        self.label.config(width=69, height=10)
        self.label.place(x=10, y=70)

        # 进度条
        self.progress = ttk.Progressbar(self.root, orient=tk.HORIZONTAL,
                                        length=480, mode='determinate')
        self.progress.place(x=10, y=270)

        # 状态标签
        self.status_label = tk.Label(self.root, text="就绪", anchor='w')
        self.status_label.place(x=10, y=245, width=480)

    def select_directory(self):
        img_path = filedialog.askdirectory()
        if img_path:
            self.editor.delete(0, tk.END)
            self.editor.insert(0, img_path)
            self.start_processing()

    def start_processing(self):
        if self.processing:
            return

        img_path = self.editor.get()
        if not img_path or not os.path.isdir(img_path):
            self.update_status("错误: 目录不存在")
            return

        self.processing = True
        self.run_btn.config(state=tk.DISABLED)
        self.stop_btn.config(state=tk.NORMAL)
        self.label.config(text="")
        self.progress["value"] = 0
        self.update_status("正在处理...")

        # 启动处理线程
        self.thread = threading.Thread(
            target=self.process_images,
            args=(img_path,),
            daemon=True
        )
        self.thread.start()

    def stop_processing(self):
        if self.processing:
            self.processing = False
            self.update_status("处理已停止")
            self.run_btn.config(state=tk.NORMAL)
            self.stop_btn.config(state=tk.DISABLED)

    def process_images(self, img_path):
        try:
            img_list = [f for f in os.listdir(img_path)]
            total = len(img_list)

            for i, img_name in enumerate(img_list, 1):
                if not self.processing:
                    break

                full_path = os.path.join(img_path, img_name)
                result = self.deal_with_picture(full_path)

                # 更新进度和结果
                progress = (i / total) * 100
                self.message_queue.put((
                    f"{img_name}: {result}\n",
                    progress,
                    f"处理中: {i}/{total} ({progress:.1f}%)"
                ))

            if self.processing:
                self.message_queue.put((
                    "\n所有图片处理完成！",
                    100,
                    "处理完成"
                ))
        except Exception as e:
            self.message_queue.put((
                f"处理出错: {str(e)}",
                0,
                f"错误: {str(e)}"
            ))
        finally:
            self.message_queue.put((None, None, None))  # 结束信号

    def deal_with_picture(self, full_path):
        new_width = 0
        new_height = 0
        try:
            with Image.open(full_path) as img:
                img = ImageOps.exif_transpose(img)
                width, height = img.size
                target_size = max(width, height)

                if img.mode == 'RGB':
                    fill_color = (255, 255, 255)
                elif img.mode == 'L':
                    fill_color = 255
                elif img.mode == 'RGBA':
                    fill_color = (255, 255, 255, 0)
                else:
                    raise ValueError("不支持的图片模式")

                new_img = Image.new(img.mode, (target_size, target_size), fill_color)
                paste_position = ((target_size - width) // 2, (target_size - height) // 2)
                new_img.paste(img, paste_position)
                new_img.save(full_path)
                new_width, new_height = new_img.size

            # 压缩图片直到小于1MB
            while os.path.getsize(full_path) >= 1048576 and self.processing:
                with Image.open(full_path) as img:
                    new_width = img.width // 2
                    new_height = img.height // 2
                    img_resized = img.resize((new_width, new_height), Resampling.LANCZOS)
                    img_resized.save(full_path)

            return f"({new_width}, {new_height})"
        except Exception as e:
            return f"错误: {str(e)}"

    def check_queue(self):
        try:
            while True:
                message, progress, status = self.message_queue.get_nowait()

                if message is None:  # 处理结束
                    self.processing = False
                    self.run_btn.config(state=tk.NORMAL)
                    self.stop_btn.config(state=tk.DISABLED)
                    break

                # 更新界面
                current_text = self.label.cget("text")
                self.label.config(text=current_text + message)

                if progress is not None:
                    self.progress["value"] = progress

                if status is not None:
                    self.status_label.config(text=status)

        except Empty:
            pass

        # 每隔100ms检查一次队列
        self.root.after(100, self.check_queue)

    def update_status(self, message):
        self.status_label.config(text=message)


if __name__ == "__main__":
    root = tk.Tk()
    app = ImageProcessorApp(root)
    root.mainloop()