import imghdr
import os
import threading
import tkinter as tk
from tkinter import filedialog

from PIL import Image
from PIL.Image import Resampling

global img_path

# 创建主窗口
root = tk.Tk()
root.title("图片1/1处理程序")
root.geometry("450x230")  # 设置窗口大小

# 添加一个编辑框
editor = tk.Entry(root)
editor.pack(side=tk.TOP, padx=5, pady=5, fill=tk.NONE)
editor.config(width=40)
editor.place(x=10, y=10)


def select():
    global img_path
    img_path = filedialog.askdirectory()
    if img_path:
        editor.delete(0, tk.END)
        editor.insert(0, img_path)
        thread = threading.Thread(target=run)
        thread.start()


# 添加一个按钮
button = tk.Button(root, text="选择目录", command=select)
button.pack(side=tk.TOP, padx=5, fill=tk.NONE)
button.place(x=310, y=5)


def is_image_file(filename):
    # 检查文件是否为图片
    return imghdr.what(filename) is not None


def deal_with_picture(full_path):
    new_width = 0
    new_height = 0
    try:
        with Image.open(full_path) as img:
            width, height = img.size
            target_size = max(width, height)
            if img.mode == 'RGB':
                fill_color = (255, 255, 255)
            elif img.mode == 'L':
                fill_color = 255
            else:
                raise ValueError("Unsupported image mode")

            new_img = Image.new(img.mode, (target_size, target_size), fill_color)
            paste_position = ((target_size - width) // 2, (target_size - height) // 2)
            new_img.paste(img, paste_position)
            new_img.save(full_path)
            new_width = new_img.width
            new_height = new_img.height
    except Exception:
        return "出错了"

    while os.path.getsize(full_path) >= 1048576:
        with Image.open(full_path) as img:
            new_width = img.width // 2
            new_height = img.width // 2
            img_resized = img.resize((new_width, new_height), Resampling.LANCZOS)
            img_resized.save(full_path)

    return "(" + str(new_width) + "," + str(new_height) + ")"


def run():
    imgList = os.listdir(img_path)
    text = ""
    for imgName in imgList:
        temp_path = os.path.join(img_path, imgName)
        if is_image_file(temp_path):
            text += deal_with_picture(temp_path) + "\n"

    label.config(text=text)


button = tk.Button(root, text="直接运行", command=run)
button.pack(side=tk.TOP, padx=5, fill=tk.NONE)
button.place(x=380, y=5)

label = tk.Label(root, padx=0, pady=0, relief="solid", anchor='nw', justify=tk.LEFT)
label.config(width=60, height=10)
label.place(x=10, y=40)

# 运行主事件循环
root.mainloop()
