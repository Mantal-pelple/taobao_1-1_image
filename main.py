import os
import re
import subprocess
import sys
import threading
import tkinter as tk
import traceback
from queue import Queue, Empty
from tkinter import filedialog, ttk, messagebox

import ffmpeg
from PIL import Image, ImageOps
from PIL.Image import Resampling

Image.MAX_IMAGE_PIXELS = None
img_path = ""


class MediaProcessorApp:

    def __init__(self, root):
        self.root = root
        self.root.title("淘宝图片/视频1:1处理程序")
        self.root.geometry("506x350")  # 增加高度以适应更多控件
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

        # 文件类型选择
        self.file_type = tk.StringVar(value="both")  # "image", "video", "both"
        tk.Radiobutton(self.root, text="图片", variable=self.file_type, value="image").place(x=10, y=40)
        tk.Radiobutton(self.root, text="视频", variable=self.file_type, value="video").place(x=80, y=40)
        tk.Radiobutton(self.root, text="两者", variable=self.file_type, value="both").place(x=150, y=40)

        # 运行按钮
        self.run_btn = tk.Button(self.root, text="直接运行", command=self.start_processing)
        self.run_btn.place(x=435, y=5)

        # 停止按钮
        self.stop_btn = tk.Button(self.root, text="停止处理", command=self.stop_processing, state=tk.DISABLED)
        self.stop_btn.place(x=435, y=35)

        # 信息显示区域
        self.label = tk.Label(self.root, padx=0, pady=0, relief="solid",
                              anchor='nw', justify=tk.LEFT, wraplength=480)
        self.label.config(width=69, height=12)
        self.label.place(x=10, y=70)

        # 进度条
        self.progress = ttk.Progressbar(self.root, orient=tk.HORIZONTAL,
                                        length=480, mode='determinate')
        self.progress.place(x=10, y=320)

        # 状态标签
        self.status_label = tk.Label(self.root, text="就绪", anchor='w')
        self.status_label.place(x=10, y=295, width=480)

    def set_input_text(self, text):
        self.editor.delete(0, tk.END)
        self.editor.insert(0, text)

    def select_directory(self):
        global img_path
        img_path = filedialog.askdirectory()
        if img_path:
            self.start_processing()

    def start_processing(self):
        global img_path
        if self.processing:
            return

        if not img_path or not os.path.isdir(img_path):
            self.update_status("错误: 目录" + img_path + "不存在")
            return

        self.processing = True
        self.run_btn.config(state=tk.DISABLED)
        self.stop_btn.config(state=tk.NORMAL)
        self.label.config(text="")
        self.progress["value"] = 0
        self.update_status("正在处理...")

        # 启动处理线程
        self.thread = threading.Thread(
            target=self.process_files,
            args=(img_path, self.file_type.get()),
            daemon=True
        )
        self.jump_to_next_dir()
        self.thread.start()

    def jump_to_next_dir(self, ):
        global img_path
        # 调整下个目录
        pattern = r"\(\d+\)"
        resultList = re.findall(pattern, img_path)
        if len(resultList) > 0:
            newPattern = r"\d+"
            digitalList = re.findall(newPattern, resultList[0])
            digital = int(digitalList[0])
            digital = digital + 1
            temp = "(" + str(digital) + ")"
            img_path = re.sub(pattern, temp, img_path)
        else:
            img_path = img_path + " (2)"

        self.set_input_text(img_path)

    def stop_processing(self):
        if self.processing:
            self.processing = False
            self.update_status("处理已停止")
            self.run_btn.config(state=tk.NORMAL)
            self.stop_btn.config(state=tk.DISABLED)

    def process_files(self, img_path, file_type):
        try:
            # 根据选择的文件类型筛选文件
            img_list = []
            for f in os.listdir(img_path):
                full_path = os.path.join(img_path, f)
                if file_type == "image" and f.lower().endswith(('.png', '.jpg', '.jpeg', '.bmp', '.gif')):
                    img_list.append(f)
                elif file_type == "video" and f.lower().endswith(('.mp4', '.mov', '.avi', '.mkv')):
                    img_list.append(f)
                elif file_type == "both" and f.lower().endswith(
                        ('.png', '.jpg', '.jpeg', '.bmp', '.gif', '.mp4', '.mov', '.avi', '.mkv')):
                    img_list.append(f)

            total = len(img_list)

            for i, file_name in enumerate(img_list, 1):
                if not self.processing:
                    break

                full_path = os.path.join(img_path, file_name)

                if file_name.lower().endswith(('.png', '.jpg', '.jpeg', '.bmp', '.gif')):
                    result = self.process_image(full_path)
                else:
                    result = self.process_video(full_path)

                # 更新进度和结果
                progress = (i / total) * 100
                self.message_queue.put((
                    f"{file_name}: {result}\n",
                    progress,
                    f"处理中: {i}/{total} ({progress:.1f}%)"
                ))

            if self.processing:
                self.message_queue.put((
                    "\n所有文件处理完成！",
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

    def process_image(self, full_path):
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

            return f"图片处理完成 ({new_width}, {new_height})"
        except Exception as e:
            return f"图片处理错误: {str(e)}"

    def process_video(self, full_path):
        try:
            # 使用ffmpeg处理视频
            probe = ffmpeg.probe(full_path)
            video_stream = next((stream for stream in probe['streams'] if stream['codec_type'] == 'video'), None)

            if not video_stream:
                return "未找到视频流"

            width = int(video_stream['width'])
            height = int(video_stream['height'])
            target_size = max(width, height)

            # 创建临时文件
            temp_path = full_path + ".temp.mp4"

            # 构建ffmpeg命令
            (
                ffmpeg
                .input(full_path)
                .filter('pad', target_size, target_size, '(ow-iw)/2', '(oh-ih)/2')
                .output(temp_path, crf=23, preset='fast')
                .overwrite_output()
                .run(quiet=True, capture_stdout=True, capture_stderr=True)
            )

            # 替换原文件
            # os.remove(full_path)
            os.replace(temp_path, full_path)

            # 检查文件大小并压缩
            while os.path.getsize(full_path) >= 1048576 * 10 and self.processing:  # 视频限制为10MB
                # 压缩视频
                temp_path = full_path + ".compressed.mp4"
                (
                    ffmpeg
                    .input(full_path)
                    .output(temp_path, crf=28, preset='fast', video_bitrate='1000k')
                    .overwrite_output()
                    .run(quiet=True, capture_stdout=True, capture_stderr=True)
                )
                # os.remove(full_path)
                os.replace(temp_path, full_path)

            return "视频处理完成"
        except Exception as e:
            exc_type, exc_value, exc_traceback = sys.exc_info()
            traceback.print_exception(exc_type, exc_value, exc_traceback)
            return f"视频处理错误: {str(e)}"

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
    # 检查ffmpeg是否安装
    try:
        subprocess.run(["ffmpeg", "-version"], check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    except:
        tk.messagebox.showerror("错误", "请先安装ffmpeg并确保它在系统路径中")
        exit(1)

    root = tk.Tk()
    app = MediaProcessorApp(root)
    root.mainloop()
