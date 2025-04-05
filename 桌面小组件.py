# 运行前必须安装pygame,requests,psutil,matplotlib库！
# 右键窗口可以设置窗口位置是否锁定（能否拖动）、作者信息（嘻嘻）及退出
# 首次运行时会弹窗提示在location.txt写入要查询天气的城市的英文名或拼音
# 在之后弹出的记事本里（location.txt）第一行写入城市英文名或拼音，然后直接关闭保存就OK，然后再次启动该程序就可以获取城市的天气信息了
# 点击天气可以刷新，对于“未知”天气也可以通过这个方法获取详细信息（天气API网站是英文网站，得手动汉化，有些汉化得不大全面）
# 若出现“无服务”字样，则要么网络不佳，要么API链接因为访问人数过多不稳定而暂时无法使用
# 可以选择本地文件夹并播放其中的音乐
# <或>切歌，<<或>>后退/前进30秒，■或▲表示播放/暂停
# （顺带一提，pygame自带的音乐播放功能有些地方好像有点问题，比如说get_pos和set_pos这两个功能，所以音频计时相关功能很大一部分是我用笨办法自定义定时器实现的）
# 城市、窗口位置和音乐相关消息会有历史记录
# 目前只是一个原型程序，排版和性能和错误处理后续还可以优化的啊
# 稍微记录一下吧
# 华子（Yauhak），写于2025.4

import os 
import sys
import pygame
import random
import requests
import subprocess
import tkinter as tk
from datetime import date
from tkinter import messagebox
from tkinter import filedialog
import psutil as mo
from time import strftime,gmtime,sleep
import matplotlib
matplotlib.use('TkAgg')  # 用于嵌入tkinter库进行CPU占用率图表的绘制，必须放在导入pyplot之前
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg

class FloatingWindow:
    def __init__(self):
        if not os.path.exists("location.txt"):
            messagebox.showinfo("提示","无位置信息。\n请在location.txt进行配置。\n（将需要查询天气的城市的英文写到该文件第一行。）")
            file=open("location.txt","w")
            file.close()
            self.Notepad() # 弹出记事本（在此处第一行写上城市的拼音或英文）
        f=open("location.txt","r")
        self.localstation=f.readline()
        f.close()
        if self.localstation=="":
            messagebox.showinfo("提示","位置信息错误！")
            self.Notepad()
        self.root = tk.Tk()
        self.root.overrideredirect(True) # 不要边框，实现悬浮窗效果，这么做还有个好处是程序是在后台运行的，哪怕切换窗口也不影响，可以实现桌面常驻
        self.root.attributes('-alpha', 0.7) # 搞个半透明效果
        self.root.config(bg='#2e2e2e') # 黑色背景
        self.context_menu = tk.Menu(self.root, tearoff=0)

        self.fig, self.ax = plt.subplots(figsize=(5, 2)) # CPU图表创建 
        self.fig.patch.set_facecolor('#2e2e2e')  
        self.ax.set_facecolor('#2e2e2e')
        self.ax.tick_params(colors='white', labelsize=8)  
        self.canvas = FigureCanvasTkAgg(self.fig, master=self.root)
        self.canvas.get_tk_widget().place(x=225, y=20)  
        if not os.path.exists("pos.txt"):
            self.x = 20
            self.y = 20
            # 新增：位置锁定状态（即窗口不可拖动）
            self.is_fixed = False  # 默认未锁定
        else:
            f=open("pos.txt","r")
            pos=f.readline().split(' ')
            f.close()
            self.x = int(pos[0])
            self.y = int(pos[1])
            self.is_fixed = True

        pygame.init()
        pygame.mixer.init() # pygame音频播放功能初始化

        self.create_widgets()
        if os.path.exists("music.txt"): # 如果有音乐相关历史记录
            file=open("music.txt","r")
            f=file.read().split('\n')
            file.close()
            self.folder=f[0] # 音乐文件夹
            self.currentmusic=int(f[1]) # 播放到第几首了
            self.find_audio_files() # 播放到第几秒了
            pygame.mixer.music.load(self.audiofiles[self.currentmusic])
            self.initmusic()
            if len(f)>2:
                self.music_pos=int(f[2])
            else:
                self.music_pos=0
            current=self.music_pos
            self.progress_label.config(text=f"{strftime('%M:%S',gmtime(current))}/"
                                      f"{strftime('%M:%S',gmtime(self.total_length))}")
        else: # 没有播放记录ㄟ( ▔, ▔ )ㄏ
            self.folder=''
            self.currentmusic=0
            self.foundmusic=False
            self.music_pos=0

        self.root.geometry(f'700x330+{self.x}+{self.y}')
        self.music_disp=False
        self.isskip=False # 不是通过手动切歌而换歌的（自动连播）
        # 右键小菜单
        self.context_menu.add_command(
            label="解锁或锁定",
            command=self.toggle_fix
        )
        self.context_menu.add_command(
            label="关于作者",
            command=lambda:messagebox.showinfo("作者","华子（Yauhak）\nQQ 3953814837")
        )
        self.context_menu.add_command(
            label="关闭",
            command=self.exit_me
        )
        # 拖动相关变量
        self.dragging = False
        self.offset_x = 0
        self.offset_y = 0
        
        self.bind_events()
        self.update_time() # 时间更新
        self.update_date() # 日期更新
        self.update_cpu() # CPU占用率更新
        self.update_mem() # 内存使用率更新
        self.update_weather() # 天气更新
        self.update_netstream() # 网络流量总量更新
        self.update_signiture() # 随机挑一个个性签名
        self.lower_myself() # 降低窗口层级（使其吸附在桌面上）

    def Notepad(self):
        if sys.platform.startswith('win'):
            subprocess.run(["notepad","location.txt"],check=True)
            sys.exit()
        elif sys.platform.startswith('linux'): # 目前我的程序在Linux上好像兼容得不大好😂
            subprocess.run(["xdg-open","location.txt"],check=True)
            sys.exit()
            sys.exit()

    def create_widgets(self):
        # 时间标签
        self.time_label = tk.Label(
            self.root,
            text="00:00:00",
            font=('Liberation Sans', 22),
            fg='white',
            bg='#2e2e2e'
        )
        self.time_label.place(x=15,y=10)
        # 天气按钮
        self.weather_btn = tk.Button(
            self.root,
            text="??",
            font=('Liberation Sans', 22),
            command=lambda:self.update_weather(1),
            fg = 'white',
            bg='#2e2e2e',
            borderwidth=0
        )
        self.weather_btn.place(x=142,y=5)
        # 日期
        self.date_label = tk.Label(
            self.root,
            text="1970-1-1",
            font=('Liberation Sans', 22),
            fg='white',
            bg='#2e2e2e'
        )
        self.date_label.place(x=15,y=52)
        # CPU
        self.Cpu_label = tk.Label(
            self.root,
            text="CPU使用率：0%",
            font=('Liberation Sans', 13),
            fg='white',
            bg='#2e2e2e'
        )
        self.Cpu_label.place(x=20,y=97)
        # 内存
        self.Mem_label = tk.Label(
            self.root,
            text="内存占用率：0%",
            font=('Liberation Sans', 13),
            fg='white',
            bg='#2e2e2e'
        )
        self.Mem_label.place(x=20,y=127)
        # 网络流量
        self.Net_label1 = tk.Label(
            self.root,
            text="↑：114KB",
            font=('Liberation Sans', 13),
            fg='white',
            bg='#2e2e2e'
        )
        self.Net_label1.place(x=20,y=157)

        self.Net_label2 = tk.Label(
            self.root,
            text="↓：114KB",
            font=('Liberation Sans', 13),
            fg='white',
            bg='#2e2e2e'
        )
        self.Net_label2.place(x=20,y=187)
        # 音频快退、快进30秒
        self.back_30s_btn = tk.Button(
            self.root,
            text="<<",
            font=('Liberation Sans', 15),
            command=self.back30s,
            fg = 'white',
            bg='#2e2e2e',
            borderwidth=0
        )
        self.back_30s_btn.place(x=20,y=222)

        self.last_song_btn = tk.Button(
            self.root,
            text="<",
            font=('Liberation Sans', 15),
            command=self.lastsong,
            fg = 'white',
            bg='#2e2e2e',
            borderwidth=0
        )
        self.last_song_btn.place(x=50,y=222)
        # 音频暂停、继续
        self.pause_continue_btn = tk.Button(
            self.root,
            text="▲",
            font=('Liberation Sans', 15),
            command=self.pause_continue,
            fg = 'white',
            bg='#2e2e2e',
            borderwidth=0
        )
        self.pause_continue_btn.place(x=70,y=222)
        # 切歌
        self.next_song_btn = tk.Button(
            self.root,
            text=">",
            font=('Liberation Sans', 15),
            command=self.nextsong,
            fg = 'white',
            bg='#2e2e2e',
            borderwidth=0
        )
        self.next_song_btn.place(x=100,y=222)

        self.forward_30s_btn = tk.Button(
            self.root,
            text=">>",
            font=('Liberation Sans', 15),
            command=self.forward30s,
            fg = 'white',
            bg='#2e2e2e',
            borderwidth=0
        )
        self.forward_30s_btn.place(x=120,y=222)
        # 选择音乐文件夹
        self.choose = tk.Button(
            self.root,
            text="选音乐",
            font=('Liberation Sans', 15),
            command=self.choosefolder,
            fg = 'white',
            bg='#2e2e2e',
            borderwidth=0
        )
        self.choose.place(x=155,y=223)
        # 当前播放的歌曲
        self.disp_label = tk.Label(
            self.root,
            text="无播放",
            font=('Liberation Sans', 15),
            fg='white',
            bg='#2e2e2e'
        )
        self.disp_label.place(x=20,y=252)
        # 播放进度
        self.progress_label = tk.Label(
            self.root,
            text="00:00/00:00",
            font=('Liberation Sans', 15),
            fg='white',
            bg='#2e2e2e'
        )
        self.progress_label.place(x=20,y=282)
        # 个性签名
        self.signature_label = tk.Label(
            self.root,
            text="个性签名",
            font=('Liberation Sans', 24),
            fg='white',
            bg='#2e2e2e'
        )
        self.signature_label.place(x=285,y=252)

    def bind_events(self):
        self.root.bind('<Button-1>', self.start_drag)
        self.root.bind("<Button-3>", self.show_menu)
        self.root.bind('<B1-Motion>', self.on_drag)
        self.root.bind('<ButtonRelease-1>', self.stop_drag)
        
    def exit_me(self):
        if not self.folder=='' and self.foundmusic==True:
            file=open("music.txt","w")
            file.write(self.folder+'\n'+str(self.currentmusic)+'\n'+str(self.music_pos)) # 保存一下音乐进度
            file.close()
        sys.exit()

    def choosefolder(self):
        self.music_pos=0
        self.music_disp=False
        self.folder=''
        self.audiofiles=[]
        self.currentmusic=0
        self.foundmusic=False
        folder_path = filedialog.askdirectory(
            title="请选择音乐文件夹",
            initialdir="/",  # 初始目录（可选）
        )
        if folder_path:
            messagebox.showinfo("提示","已选择文件夹！")
            file=open("music.txt","w")
            file.write(folder_path+'\n'+'0')
            file.close()
            self.folder=folder_path
            self.find_audio_files()
            self.initmusic()
        else:
            messagebox.showinfo("提示","未选择文件夹。")

    def find_audio_files(self):
        audio_extensions = {'.mp3', '.wav', '.aac', '.flac', '.ogg', '.m4a'}  # 支持的音频扩展名
        audio_files = [] 
        for root, dirs, files in os.walk(self.folder):
            for file in files:
                # 获取文件扩展名并转换为小写
                ext = os.path.splitext(file)[1].lower()
                if ext in audio_extensions:
                    full_path = os.path.join(root, file)
                    audio_files.append(full_path)
        if len(audio_files)==0:
            messagebox.showinfo("提示","未找到音频文件！")
            return
        self.audiofiles=audio_files
        self.foundmusic=True

    # 初始化一下播放相关信息
    def initmusic(self):
        self.music_pos=0
        self.music_disp=False
        music=self.audiofiles[self.currentmusic]
        pygame.mixer.music.load(music)
        sound = pygame.mixer.Sound(music)
        self.total_length = sound.get_length()
        self.progress_label.config(text=f"00:00/{strftime('%M:%S', gmtime(self.total_length))}")
        file=os.path.basename(music)
        if len(file)>15:
            file=file[0:12]+'...'
        self.disp_label.config(text=file)
        self.pause_continue_btn.config(text="▲",font=('Liberation Sans', 15))

    def pause_continue(self):
        if self.foundmusic==False:
            messagebox.showinfo("提示","无音频文件！")
            return
        self.music_disp=not self.music_disp
        if self.music_disp==True:
            self.pause_continue_btn.config(text="■",font=('Liberation Sans', 15))
            self.dispnow()
            self.update_progress()
        else:
            self.pause_continue_btn.config(text="▲",font=('Liberation Sans', 15))
            self.stopnow()

    def dispnow(self):
        pygame.mixer.music.play(start=self.music_pos)

    def stopnow(self):
        pygame.mixer_music.pause()

    def back30s(self):
        if self.foundmusic==False:
            messagebox.showinfo("提示","无音频文件！")
            return
        if self.music_disp==False:
            return
        self.music_pos = max(0, self.music_pos - 30)
        pygame.mixer.music.stop()
        pygame.mixer.music.play(start=self.music_pos)

    def forward30s(self):
        if self.foundmusic==False:
            messagebox.showinfo("提示","无音频文件！")
            return
        if self.music_disp==False:
            return
        self.music_pos = min(self.total_length, self.music_pos + 30)
        pygame.mixer.music.stop()
        pygame.mixer.music.play(start=self.music_pos)

    def lastsong(self):
        if self.music_disp==False:
            self.pause_continue()
        if self.folder=='' or self.foundmusic==False:
            messagebox.showinfo("提示","无音频文件！")
            return
        pygame.mixer.music.stop()
        self.music_pos=self.total_length-2 # 我的思路是直接跳到歌曲末尾，然后“当前播放的音乐”换成下一首，剩下的切歌播放交给update_progress来做
        self.swlastsong() 

    def nextsong(self):
        if self.music_disp==False:
            self.pause_continue()
        if self.folder=='' or self.foundmusic==False:
            messagebox.showinfo("提示","无音频文件！")
            return
        pygame.mixer.music.stop()
        self.music_pos=self.total_length-2 # 思路同上
        self.swnextsong() 

    def swlastsong(self):
        if self.currentmusic-1<0:
            self.currentmusic=len(self.audiofiles)-1
        else:
            self.currentmusic=self.currentmusic-1
            self.isskip=True
        
    def swnextsong(self):
        self.currentmusic=(self.currentmusic+1)%len(self.audiofiles)
        self.isskip=True

    def update_progress(self):
        if self.music_disp==True:
            current=self.music_pos
            self.progress_label.config(text=f"{strftime('%M:%S',gmtime(current))}/"
                                      f"{strftime('%M:%S',gmtime(self.total_length))}")
            self.music_pos=self.music_pos+1
        else:
            return
        if abs(self.music_pos-self.total_length)<=1 or self.music_pos>=self.total_length:
            if self.isskip==False: # 如果不是手动切歌
                self.currentmusic=(self.currentmusic+1)%len(self.audiofiles) # 换成下一首
            if self.timerid: # 如果上一个音频计时器存在则销毁
                self.root.after_cancel(self.timerid)
            file=open("music.txt","w")
            file.write(self.folder+'\n'+str(self.currentmusic))
            file.close()
            self.stopnow()
            self.isskip=False
            self.initmusic()
            self.pause_continue()
            self.pause_continue_btn.config(text="■",font=('Liberation Sans', 15))
            return
        self.timerid=self.root.after(1000, self.update_progress)

    def show_menu(self,event):
        try:
            self.context_menu.tk_popup(event.x_root, event.y_root)
        finally:
            self.context_menu.grab_release()  # 确保释放菜单焦点

    def toggle_fix(self):
        # 切换锁定/移动状态
        self.is_fixed = not self.is_fixed
        if self.is_fixed==True:
            file=open("pos.txt","w")
            file.write(str(self.root.winfo_x())+' '+str(self.root.winfo_y()))
            file.close()

    def start_drag(self, event):
        if not self.is_fixed:  # 仅在未锁定时允许拖动
            self.dragging = True
            self.offset_x = event.x
            self.offset_y = event.y
            
    def on_drag(self, event):
        if self.dragging and not self.is_fixed:
            x = self.root.winfo_x() + (event.x - self.offset_x)
            y = self.root.winfo_y() + (event.y - self.offset_y)
            self.root.geometry(f'+{x}+{y}')
            
    def stop_drag(self, event):
        self.dragging = False
        
    def update_time(self):
        current_time = strftime('%H:%M:%S')
        self.time_label.config(text=current_time)
        self.root.after(1000, self.update_time)
        
    def update_date(self):
        current_date = date.today()
        self.date_label.config(text=current_date)

    def update_cpu(self):
        cpu_percent = mo.cpu_percent()
        self.Cpu_label.config(text=f"CPU使用率：{cpu_percent}%")
    
        # 记录最近60个数据点
        if not hasattr(self, 'cpu_data'):
            self.cpu_data = []
        self.cpu_data.append(cpu_percent)
        if len(self.cpu_data) > 60:
            self.cpu_data.pop(0)
    
        # 更新图表
        self.ax.clear()
        self.ax.plot(self.cpu_data, color='cyan', linewidth=1)
        self.ax.set_title("CPU(%)", color='white', fontsize=10)
        self.canvas.draw()
    
        # 继续定时更新
        self.root.after(1000, self.update_cpu)

    def update_mem(self):
        mem_percent=mo.virtual_memory().percent
        self.Mem_label.config(text=f"内存占用率：{mem_percent}%")
        self.root.after(900, self.update_mem)

    def update_weather(self,status=0):
        try:
            req=requests.get('https://wttr.in//'+self.localstation+'?format=j1',timeout=5)
            weather=req.json()["current_condition"][0]["weatherDesc"][0]["value"]
            weather_desc_mapping = {
                # 基础天气类型
                "Clear": "晴朗",
                "Sunny": "晴天",
                "Partly cloudy": "少云",
                "Cloudy": "多云",
                "Overcast": "阴天",
                "Mist": "薄雾",
                "Fog": "浓雾",
                "Haze": "雾霾",
    
                # 降水类
                "Light rain": "小雨",
                "Moderate rain": "中雨",
                "Heavy rain": "大雨",
                "Torrential rain": "暴雨",
                "Rain showers": "阵雨",
                "Thunderstorm": "雷阵雨",
                "Light snow": "小雪",
                "Moderate snow": "中雪",
                "Heavy snow": "大雪",
                "Snow showers": "阵雪",
                "Sleet": "雨夹雪",
                "Freezing rain": "冻雨",
    
                # 特殊天气
                "Dust": "浮尘",
                "Sandstorm": "沙尘暴",
                "Tornado": "龙卷风",
    
                # 天气现象
                "Drizzle": "毛毛雨",
                "Showers": "阵雨",
                "Blizzard": "暴风雪",
                "Ice pellets": "冰粒",

                "Light drizzle": "小雨",
                "Patchy rain": "零星雨",
                "Light snow showers": "小阵雪",
            }
            self.weather_btn.config(text=weather_desc_mapping.get(weather,"未知"), bg='#2e2e2e')
            if status==1:
                messagebox.showinfo("天气详细描述",weather)
        except requests.exceptions.RequestException as e:
            self.weather_btn.config(text="无服务", bg='#2e2e2e')

    def update_netstream(self):
        net_io = mo.net_io_counters()
        up = f"{net_io.bytes_sent / 1024:.2f} KB"
        down = f"{net_io.bytes_recv / 1024:.2f} KB"
        self.Net_label1.config(text=f"↑：{up}")
        self.Net_label2.config(text=f"↓：{down}")
        self.root.after(1000, self.update_netstream)

    def update_signiture(self):
        signatures = [
            "“听风吟，静待花开”",
            "“浮舟沧海，立马昆仑”",
            "“知命不惧，日日自新”",
            "“人生如逆旅，我亦是行人”",
            "“心中有丘壑，眉目作山河”",
            "“行到水穷处，坐看云起时”",
            "“追光的人，终会光芒万丈”",
            "“清醒自律，知进退”",
            "“和光同尘，与时舒卷”",
            "“生有热烈，藏与俗常”",
            "“我自明月，向星空”",
            "“山不让尘，川不辞盈”",
            "“以梦为马，不负韶华”",
            "“心有猛虎，细嗅蔷薇”",
            "“凡是过往，皆为序章”",
            "“霁月光风，不萦于怀”",
            "“但行好事，莫问前程”",
            "“玻璃晴朗，橘子辉煌”",
            "“身在井隅，心向璀璨”"
        ]
        self.signature_label.config(text=random.choice(signatures))

    def lower_myself(self):
        self.root.lower()
        self.root.after(500, self.lower_myself)

    def run(self):
        self.root.mainloop()

if __name__ == '__main__':
    app = FloatingWindow()
    app.run()
