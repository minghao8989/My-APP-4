import streamlit as st
import pandas as pd
import qrcode
import cv2
import numpy as np
from PIL import Image
import time
import random
from datetime import datetime

# --- 1. 全局状态管理 (模拟数据库) ---
# 使用 cache_resource 保证在云端运行时，所有用户共享这份数据
@st.cache_resource
class RaceManager:
    def __init__(self):
        self.contestants = {}  # 存储格式: {user_id: {'name': str, 'group': str, 'finish_time': float}}
        self.start_time = None # 比赛开始的时间戳
        self.is_running = False

    def register(self, name, group):
        # 生成一个简单的随机ID
        user_id = str(random.randint(100000, 999999))
        self.contestants[user_id] = {
            'name': name,
            'group': group,
            'finish_time': None
        }
        return user_id

    def start_race(self):
        self.is_running = True
        self.start_time = time.time()

    def reset_race(self):
        self.is_running = False
        self.start_time = None
        self.contestants = {} # 清空选手数据

    def record_finish(self, user_id):
        if user_id in self.contestants and self.start_time:
            if self.contestants[user_id]['finish_time'] is None:
                duration = time.time() - self.start_time
                self.contestants[user_id]['finish_time'] = duration
                return True, self.contestants[user_id]['name'], duration
            else:
                return False, "已录入成绩", self.contestants[user_id]['finish_time']
        return False, "无效ID", 0

    def get_dataframe(self):
        data = []
        for uid, info in self.contestants.items():
            ft = info['finish_time']
            ft_str = self.format_time(ft) if ft else "--:--"
            data.append({
                "姓名": info['name'],
                "组别": info['group'],
                "成绩": ft_str,
                "状态": "已完成" if ft else "进行中/未开始"
            })
        return pd.DataFrame(data)

    @staticmethod
    def format_time(seconds):
        if seconds is None: return "00:00.00"
        mins = int(seconds // 60)
        secs = int(seconds % 60)
        millis = int((seconds * 100) % 100)
        return f"{mins:02d}:{secs:02d}.{millis:02d}"

# 初始化全局管理器
manager = RaceManager()

# --- 2. 页面配置 ---
st.set_page_config(page_title="登山赛计时系统", page_icon="⏱️", layout="centered")

# CSS 美化，隐藏默认菜单，适配手机
st.markdown("""
    <style>
        .stApp { max-width: 100%; padding: 1rem; }
        .big-timer { font-size: 80px !important; font-weight: bold; text-align: center; color: #00CC00; font-family: monospace; }
        .stButton button { width: 100%; border-radius: 10px; height: 50px; font-weight: bold; }
        /* 隐藏Streamlit默认的菜单 */
        #MainMenu {visibility: hidden;}
        footer {visibility: hidden;}
    </style>
""", unsafe_allow_html=True)

# --- 3. 状态路由 (通过 session_state 控制页面跳转) ---
if 'page' not in st.session_state:
    st.session_state.page = 'register'
if 'user_id' not in st.session_state:
    st.session_state.user_id = None
if 'user_info' not in st.session_state:
    st.session_state.user_info = {}

# --- 辅助函数：解码二维码 ---
def decode_qr(image_buffer):
    try:
        # 将上传的图片转为 OpenCV 格式
        file_bytes = np.asarray(bytearray(image_buffer.read()), dtype=np.uint8)
        img = cv2.imdecode(file_bytes, 1)
        detector = cv2.QRCodeDetector()
        data, bbox, _ = detector.detectAndDecode(img)
        return data
    except Exception as e:
        return None

# ================= 页面 1: 选手报名 =================
if st.session_state.page == 'register':
    st.title("⛰️ 登山赛报名")
    
    with st.form("reg_form"):
        name = st.text_input("请输入姓名")
        
        # 组别选择 (组1 - 组30)
        groups = [f"组{i}" for i in range(1, 31)]
        
        # 随机组别逻辑
        col_g1, col_g2 = st.columns([3, 1])
        with col_g1:
            # 如果session里有随机结果，优先使用
            default_idx = 0
            if 'random_group_idx' in st.session_state:
                default_idx = st.session_state.random_group_idx
            
            selected_group = st.selectbox("选择组别", groups, index=default_idx)
            
        with col_g2:
            st.write("") # 占位
            st.write("") 
            if st.form_submit_button("🎲 随机"):
                st.session_state.random_group_idx = random.randint(0, 29)
                st.rerun()

        submit = st.form_submit_button("生成参赛证")
        
        if submit:
            if name:
                uid = manager.register(name, selected_group)
                st.session_state.user_id = uid
                st.session_state.user_info = {'name': name, 'group': selected_group}
                st.session_state.page = 'contestant'
                st.rerun()
            else:
                st.error("请填写姓名")

    st.markdown("---")
    if st.button("我是管理员/主办方"):
        st.session_state.page = 'admin_login'
        st.rerun()

# ================= 页面 2: 管理员登录 =================
elif st.session_state.page == 'admin_login':
    st.title("🔐 主办方登录")
    pwd = st.text_input("请输入密码", type="password")
    if st.button("登录"):
        if pwd == "963852":
            st.session_state.page = 'admin_dashboard'
            st.rerun()
        else:
            st.error("密码错误")
    
    if st.button("返回报名页"):
        st.session_state.page = 'register'
        st.rerun()

# ================= 页面 3: 选手端 (二维码 + 秒表) =================
elif st.session_state.page == 'contestant':
    info = st.session_state.user_info
    st.success(f"选手: {info['name']} | {info['group']}")
    
    # 1. 生成二维码
    qr = qrcode.QRCode(version=1, box_size=10, border=4)
    qr.add_data(st.session_state.user_id)
    qr.make(fit=True)
    img_qr = qr.make_image(fill_color="black", back_color="white")
    st.image(img_qr.get_image(), caption="终点请出示此二维码", width=250)
    
    st.markdown("---")
    
    # 2. 秒表显示逻辑
    timer_placeholder = st.empty()
    
    # 这是一个循环，只要页面开着，它就会一直刷新时间
    # 注意：Streamlit云端长时间运行可能会断开，但在活动期间通常没问题
    while True:
        if manager.is_running and manager.start_time:
            # 计算当前时间
            elapsed = time.time() - manager.start_time
            # 检查自己是否已经跑完了
            my_data = manager.contestants.get(st.session_state.user_id)
            if my_data and my_data['finish_time']:
                # 如果跑完了，显示最终成绩
                final_time = manager.format_time(my_data['finish_time'])
                timer_placeholder.markdown(f"<div class='big-timer' style='color:blue'>{final_time}</div>", unsafe_allow_html=True)
                st.info("您已完成比赛！")
                break # 停止循环
            else:
                # 还没跑完，显示动态时间
                current_time_str = manager.format_time(elapsed)
                timer_placeholder.markdown(f"<div class='big-timer'>{current_time_str}</div>", unsafe_allow_html=True)
        else:
            timer_placeholder.markdown("<div class='big-timer' style='color:gray'>00:00.00</div>", unsafe_allow_html=True)
            if not manager.is_running:
                st.caption("等待主办方开始比赛...")
        
        time.sleep(0.1) # 0.1秒刷新一次，节省资源

# ================= 页面 4: 管理员/主办方后台 =================
elif st.session_state.page == 'admin_dashboard':
    st.title("🏆 赛事管理后台")
    
    col1, col2 = st.columns(2)
    with col1:
        if st.button("🚀 开始比赛 (计时)", type="primary", disabled=manager.is_running):
            manager.start_race()
            st.rerun()
    with col2:
        if st.button("⚠️ 重置比赛"):
            manager.reset_race()
            st.rerun()

    if manager.is_running:
        st.write(f"比赛进行中... 开始时间: {time.strftime('%H:%M:%S', time.localtime(manager.start_time))}")
    
    st.markdown("### 📷 扫码录入成绩")
    st.info("手机端：点击下方 'Take Photo'，在弹出的相机界面中可切换前后摄像头。")
    
    # 扫码区域
    img_file = st.camera_input("点击拍照扫描选手二维码", key="camera")
    
    if img_file is not None:
        # 识别二维码
        code_data = decode_qr(img_file)
        if code_data:
            success, name, duration = manager.record_finish(code_data)
            if success:
                st.success(f"✅ 录入成功！选手：{name}，用时：{manager.format_time(duration)}")
                time.sleep(2) # 停留2秒让管理员看到成功提示
                st.rerun() # 刷新页面更新表格
            else:
                if name == "已录入成绩":
                    st.warning(f"⚠️ 该选手已录入，成绩：{manager.format_time(duration)}")
                else:
                    st.error("❌ 无效的二维码或数据")
        else:
            st.error("❌ 未识别到二维码，请靠近一点重试")

    st.markdown("### 📊 实时榜单")
    df = manager.get_dataframe()
    # 按照成绩排序
    if not df.empty:
        df = df.sort_values(by="成绩")
    st.dataframe(df, use_container_width=True)