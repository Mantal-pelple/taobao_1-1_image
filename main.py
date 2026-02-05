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

# 支持的图片格式
SUPPORTED_IMAGE_FORMATS = ('.png', '.jpg', '.jpeg', '.bmp', '.gif', '.webp', '.tiff')
# 支持的视频格式
SUPPORTED_VIDEO_FORMATS = ('.mp4', '.mov', '.avi', '.mkv', '.webm', '.flv')


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
        # 增加窗口宽度以容纳更长的路径
        self.root.geometry("600x350")
        
        # 路径输入框 - 增加宽度
        tk.Label(self.root, text="目录路径:").place(x=10, y=12)
        self.editor = tk.Entry(self.root, width=65)  # 增加宽度
        self.editor.place(x=80, y=10)

        # 选择目录按钮
        self.select_btn = tk.Button(self.root, text="选择目录", command=self.select_directory, width=10)
        self.select_btn.place(x=520, y=5)  # 调整位置

        # 文件类型选择
        tk.Label(self.root, text="文件类型:").place(x=10, y=42)
        self.file_type = tk.StringVar(value="both")  # "image", "video", "both"
        tk.Radiobutton(self.root, text="图片", variable=self.file_type, value="image").place(x=80, y=40)
        tk.Radiobutton(self.root, text="视频", variable=self.file_type, value="video").place(x=140, y=40)
        tk.Radiobutton(self.root, text="两者", variable=self.file_type, value="both").place(x=200, y=40)

        # 自动跳转目录选项
        self.auto_jump = tk.BooleanVar(value=False)  # 默认不自动跳转
        tk.Checkbutton(self.root, text="自动跳转目录", variable=self.auto_jump).place(x=280, y=40)

        # 运行按钮
        self.run_btn = tk.Button(self.root, text="开始处理", command=self.start_processing, 
                                 bg="#4CAF50", fg="white", width=10)
        self.run_btn.place(x=450, y=35)  # 调整位置

        # 停止按钮
        self.stop_btn = tk.Button(self.root, text="停止", command=self.stop_processing, 
                                  state=tk.DISABLED, bg="#f44336", fg="white", width=8)
        self.stop_btn.place(x=520, y=35)  # 调整位置

        # 信息显示区域
        tk.Label(self.root, text="处理日志:").place(x=10, y=72)
        self.label = tk.Label(self.root, padx=5, pady=5, relief="solid", bg="white",
                              anchor='nw', justify=tk.LEFT, wraplength=570)  # 增加宽度
        self.label.config(width=82, height=12)  # 调整宽度
        self.label.place(x=10, y=90)

        # 滚动条
        self.scrollbar = tk.Scrollbar(self.root)
        self.scrollbar.place(x=585, y=90, height=200)  # 调整位置

        # 进度条
        self.progress = ttk.Progressbar(self.root, orient=tk.HORIZONTAL,
                                        length=570, mode='determinate')  # 增加长度
        self.progress.place(x=10, y=320)

        # 状态标签
        self.status_label = tk.Label(self.root, text="就绪", anchor='w', relief="sunken", bg="#f0f0f0")
        self.status_label.place(x=10, y=295, width=570, height=20)  # 调整宽度

    def set_input_text(self, text):
        self.editor.delete(0, tk.END)
        self.editor.insert(0, text)

    def select_directory(self):
        global img_path
        selected_path = filedialog.askdirectory()
        if selected_path:
            img_path = selected_path
            self.set_input_text(img_path)
            self.start_processing()

    def start_processing(self):
        global img_path
        real_path = self.editor.get()
        if real_path is not None and real_path != "" and real_path != img_path:
            img_path = real_path

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
                if not os.path.isfile(full_path):
                    continue
                    
                if file_type == "image" and f.lower().endswith(SUPPORTED_IMAGE_FORMATS):
                    img_list.append(f)
                elif file_type == "video" and f.lower().endswith(SUPPORTED_VIDEO_FORMATS):
                    img_list.append(f)
                elif file_type == "both" and (f.lower().endswith(SUPPORTED_IMAGE_FORMATS) or 
                                             f.lower().endswith(SUPPORTED_VIDEO_FORMATS)):
                    img_list.append(f)

            total = len(img_list)
            if total == 0:
                self.message_queue.put((
                    "没有找到符合条件的文件\n",
                    100,
                    "未找到文件"
                ))
                self.message_queue.put((None, None, None))
                return

            for i, file_name in enumerate(img_list, 1):
                if not self.processing:
                    break

                full_path = os.path.join(img_path, file_name)

                if file_name.lower().endswith(SUPPORTED_IMAGE_FORMATS):
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
                    f"\n所有文件处理完成！共处理 {total} 个文件",
                    100,
                    "处理完成"
                ))
        except Exception as e:
            self.message_queue.put((
                f"处理出错: {str(e)}\n{traceback.format_exc()}",
                0,
                f"错误: {str(e)}"
            ))
        finally:
            self.message_queue.put((None, None, None))  # 结束信号
            # 根据复选框决定是否跳转到下一个目录
            if self.auto_jump.get():
                self.jump_to_next_dir()

    def process_image(self, full_path):
        try:
            original_size = os.path.getsize(full_path)
            
            with Image.open(full_path) as img:
                img = ImageOps.exif_transpose(img)
                width, height = img.size
                target_size = max(width, height)

                # 处理不同图片模式的填充颜色
                if img.mode == 'RGB':
                    fill_color = (255, 255, 255)  # 白色背景
                elif img.mode == 'L':
                    fill_color = 255  # 白色背景（灰度）
                elif img.mode == 'RGBA':
                    # 对于PNG透明图片，使用透明背景
                    fill_color = (255, 255, 255, 0)  # 完全透明
                elif img.mode == 'P':
                    # 对于调色板模式，先转换为RGBA
                    img = img.convert('RGBA')
                    fill_color = (255, 255, 255, 0)  # 完全透明
                elif img.mode == 'CMYK':
                    # CMYK模式转换为RGB
                    img = img.convert('RGB')
                    fill_color = (255, 255, 255)  # 白色背景
                else:
                    # 其他模式尝试转换为RGB
                    try:
                        img = img.convert('RGB')
                        fill_color = (255, 255, 255)
                    except:
                        raise ValueError(f"不支持的图片模式: {img.mode}")

                new_img = Image.new(img.mode, (target_size, target_size), fill_color)
                paste_position = ((target_size - width) // 2, (target_size - height) // 2)
                
                # 对于RGBA模式，需要确保粘贴时保持透明度
                if img.mode == 'RGBA':
                    new_img.paste(img, paste_position, img)
                else:
                    new_img.paste(img, paste_position)
                
                # 保存图片，根据格式选择适当的参数
                if full_path.lower().endswith('.png'):
                    # PNG格式保存时保持透明度
                    new_img.save(full_path, format='PNG', optimize=True)
                elif full_path.lower().endswith('.jpg') or full_path.lower().endswith('.jpeg'):
                    # JPEG格式保存时设置质量
                    new_img.save(full_path, format='JPEG', quality=95, optimize=True)
                else:
                    new_img.save(full_path, optimize=True)
                    
                new_width, new_height = new_img.size

            # 压缩图片直到小于1MB，但避免无限循环
            compression_count = 0
            max_compression_cycles = 10  # 最多压缩10次
            
            while (os.path.getsize(full_path) >= 1048576 and 
                   self.processing and 
                   compression_count < max_compression_cycles):
                
                compression_count += 1
                with Image.open(full_path) as img:
                    # 计算新的尺寸，但不要小于100像素
                    new_width = max(img.width // 2, 100)
                    new_height = max(img.height // 2, 100)
                    
                    # 保持宽高比
                    if img.width > img.height:
                        aspect_ratio = img.height / img.width
                        new_height = int(new_width * aspect_ratio)
                    else:
                        aspect_ratio = img.width / img.height
                        new_width = int(new_height * aspect_ratio)
                    
                    img_resized = img.resize((new_width, new_height), Resampling.LANCZOS)
                    
                    # 根据格式保存
                    if full_path.lower().endswith('.png'):
                        img_resized.save(full_path, format='PNG', optimize=True)
                    elif full_path.lower().endswith('.jpg') or full_path.lower().endswith('.jpeg'):
                        # 逐步降低JPEG质量
                        quality = max(70, 95 - compression_count * 5)
                        img_resized.save(full_path, format='JPEG', quality=quality, optimize=True)
                    else:
                        img_resized.save(full_path, optimize=True)

            final_size = os.path.getsize(full_path)
            size_reduction = original_size - final_size
            
            if size_reduction > 0:
                size_info = f" (压缩了 {size_reduction/1024/1024:.2f}MB)"
            else:
                size_info = ""
                
            return f"图片处理完成 ({new_width}, {new_height}){size_info}"
        except Exception as e:
            return f"图片处理错误: {str(e)}"

    def process_video(self, full_path):
        try:
            original_size = os.path.getsize(full_path)
            
            # 使用ffmpeg处理视频
            probe = ffmpeg.probe(full_path)
            video_stream = next((stream for stream in probe['streams'] if stream['codec_type'] == 'video'), None)
            audio_stream = next((stream for stream in probe['streams'] if stream['codec_type'] == 'audio'), None)

            if not video_stream:
                return "未找到视频流"

            width = int(video_stream['width'])
            height = int(video_stream['height'])
            target_size = max(width, height)
            
            # 获取视频时长和帧率
            duration = float(video_stream.get('duration', 0))
            fps = eval(video_stream.get('r_frame_rate', '30/1'))
            if isinstance(fps, tuple):
                fps = fps[0] / fps[1] if fps[1] != 0 else 30
            fps = float(fps)

            # 创建临时文件
            temp_path = full_path + ".temp.mp4"
            
            # 构建ffmpeg命令 - 使用pad滤镜将视频填充为1:1比例
            # 保留音频流
            input_stream = ffmpeg.input(full_path)
            
            # 视频处理：填充为正方形，保持原始内容在中心
            video = input_stream.video.filter('pad', target_size, target_size, 
                                             f'(ow-iw)/2', f'(oh-ih)/2')
            
            # 如果有音频，保留音频
            if audio_stream:
                audio = input_stream.audio
                output = ffmpeg.output(video, audio, temp_path, 
                                      vcodec='libx264', 
                                      acodec='aac',
                                      crf=23, 
                                      preset='fast',
                                      pix_fmt='yuv420p')
            else:
                output = ffmpeg.output(video, temp_path, 
                                      vcodec='libx264', 
                                      crf=23, 
                                      preset='fast',
                                      pix_fmt='yuv420p')
            
            # 执行命令
            output.overwrite_output().run(quiet=True, capture_stdout=True, capture_stderr=True)

            # 替换原文件
            os.replace(temp_path, full_path)
            
            # 检查文件大小并压缩（视频限制为10MB）
            compression_count = 0
            max_compression_cycles = 5  # 视频最多压缩5次
            
            while (os.path.getsize(full_path) >= 10485760 and  # 10MB
                   self.processing and 
                   compression_count < max_compression_cycles):
                
                compression_count += 1
                temp_path = full_path + f".compressed{compression_count}.mp4"
                
                # 重新获取视频信息
                probe = ffmpeg.probe(full_path)
                video_stream = next((stream for stream in probe['streams'] if stream['codec_type'] == 'video'), None)
                audio_stream = next((stream for stream in probe['streams'] if stream['codec_type'] == 'audio'), None)
                
                if not video_stream:
                    break
                    
                # 获取当前尺寸
                current_width = int(video_stream['width'])
                current_height = int(video_stream['height'])
                
                # 计算新的尺寸（保持1:1比例）
                new_size = max(current_width // 2, 240)  # 最小240像素
                new_size = min(new_size, 1920)  # 最大1920像素
                
                input_stream = ffmpeg.input(full_path)
                video = input_stream.video.filter('scale', new_size, new_size)
                
                # 调整比特率
                target_bitrate = '1000k'
                if compression_count > 1:
                    target_bitrate = f'{max(500, 1000 - compression_count * 200)}k'
                
                if audio_stream:
                    audio = input_stream.audio
                    output = ffmpeg.output(video, audio, temp_path,
                                          vcodec='libx264',
                                          acodec='aac',
                                          crf=23 + compression_count * 2,  # 逐步增加压缩
                                          preset='fast',
                                          video_bitrate=target_bitrate,
                                          pix_fmt='yuv420p')
                else:
                    output = ffmpeg.output(video, temp_path,
                                          vcodec='libx264',
                                          crf=23 + compression_count * 2,
                                          preset='fast',
                                          video_bitrate=target_bitrate,
                                          pix_fmt='yuv420p')
                
                output.overwrite_output().run(quiet=True, capture_stdout=True, capture_stderr=True)
                os.replace(temp_path, full_path)

            final_size = os.path.getsize(full_path)
            size_reduction = original_size - final_size
            
            if size_reduction > 0:
                size_info = f" (压缩了 {size_reduction/1024/1024:.2f}MB)"
            else:
                size_info = ""
                
            return f"视频处理完成 ({target_size}x{target_size}){size_info}"
            
        except Exception as e:
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
                # 限制日志长度，避免内存问题
                if len(current_text) > 10000:
                    current_text = current_text[-5000:]
                self.label.config(text=current_text + message)

                if progress is not None:
                    self.progress["value"] = progress

                if status is not None:
                    self.status_label.config(text=status)

        except Empty:
            pass
        except Exception as e:
            # 记录错误但不中断队列检查
            print(f"队列检查错误: {e}")

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
