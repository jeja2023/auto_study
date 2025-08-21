import asyncio
import time
import random
import logging # 导入logging模块
from DrissionPage import ChromiumPage
from DrissionPage._configs.chromium_options import ChromiumOptions # 导入 ChromiumOptions
from DrissionPage.errors import ElementNotFoundError, PageDisconnectedError, CDPError
import json # 导入json用于处理cookies
from collections import deque # 用于存储日志，限制长度
from typing import Optional # 导入Optional用于类型提示
from backend.database import get_db # 导入 get_db
from backend import crud # 导入 crud
from sqlalchemy.orm import Session # 导入 Session

# 获取当前模块的日志记录器
logger = logging.getLogger(__name__)

# 全局字典，用于存储每个用户的活跃浏览器页面实例
_active_browser_pages = {}
# 全局字典，用于存储每个用户的停止事件
_stop_events = {}

# 定义一个简单的日志函数，用于替代GUI中的log
def console_log(message, user_id=None, username=None, ip_address=None, level=logging.INFO):
    """
    替代GUI中的log，将消息发送到主日志系统。
    """
    extra_data = {}
    if user_id is not None:
        extra_data['user_id'] = user_id
    if username is not None:
        extra_data['username'] = username
    if ip_address is not None: # 添加ip_address到extra_data
        extra_data['ip_address'] = ip_address

    # 打印 extra_data 以便调试
    # print(f"[DEBUG] console_log extra_data: {extra_data}")

    if extra_data:
        logger.log(level, message, extra=extra_data)
    else:
        logger.log(level, message)

async def send_log_to_queue(message: str, user_id: Optional[int] = None, username: Optional[str] = None, ip_address: Optional[str] = None, level=logging.INFO):
    """ 将日志消息发送到主日志系统，以便被DbLogHandler捕获并推送到WebSocket队列。 """
    extra_data = {}
    if user_id is not None:
        extra_data['user_id'] = user_id
    if username is not None:
        extra_data['username'] = username
    if ip_address is not None:
        extra_data['ip_address'] = ip_address

    if extra_data:
        logger.log(level, message, extra=extra_data)
    else:
        logger.log(level, message)

def format_seconds_to_hms(seconds: int, threshold_seconds: int = 60) -> str:
    """
    将秒数格式化为时分秒字符串，如果小于阈值则只显示秒数。
    """
    if seconds < threshold_seconds:
        return f"{seconds} 秒"
    else:
        minutes, remaining_seconds = divmod(seconds, 60)
        hours, minutes = divmod(minutes, 60)
        
        if hours > 0:
            return f"{int(hours):02}:{int(minutes):02}:{int(remaining_seconds):02}"
        else:
            return f"{int(minutes):02}:{int(remaining_seconds):02}"

async def process_single_task_videos(user_id: int, page, learning_task, stop_event: asyncio.Event, db: Session, ip_address: Optional[str] = None, username: Optional[str] = None) -> bool:
    """ 负责在当前任务的视频列表页面上播放所有未完成的视频。 """
    # --- [修改点] ---
    # 使用 contains(@class, 'childSection') 来匹配所有包含 'childSection' 类的视频条目，
    # 无论是 'childSection' 还是 'childSection active' 都能被正确找到。
    video_locator = "xpath://div[@class='videoList']/div[@class='listBox']/div[contains(@class, 'childSection')]"

    while True:
        if stop_event.is_set(): # 检查停止信号
            console_log(f"收到停止信号，退出当前视频列表自动化循环。", user_id, username, ip_address, level=logging.INFO)
            return False # 表示未完成所有视频，因为被停止了

        try:
            console_log("\n页面已就绪，准备扫描视频...", user_id, username, ip_address, level=logging.INFO)
            # 等待 videoListBox 元素可见，确保视频列表容器已加载
            page.ele('xpath://div[@class="videoListBox"]', timeout=15).wait.displayed()
            console_log(f"视频列表容器 videoListBox 已加载。", user_id, username, ip_address, level=logging.INFO)
        except (ElementNotFoundError, PageDisconnectedError, CDPError):
            console_log("错误：浏览器连接已断开或视频列表容器未加载，退出任务。", user_id, username, ip_address, level=logging.ERROR)
            return False

        await asyncio.sleep(3)

        video_to_play_element = None # 存储要播放的视频元素（需要点击的）
        video_to_play_db_obj = None # 存储数据库中对应的 LearningVideo 对象（需要点击的）
        video_already_playing_element = None # 存储已经正在播放的视频元素（无需点击）
        video_already_playing_db_obj = None # 存储数据库中对应的 LearningVideo 对象（无需点击）

        try:
            video_elements = page.eles(video_locator)
            video_count = len(video_elements)

            if video_count == 0:
                console_log("错误：未找到任何视频条目。请检查页面是否已加载，或页面结构已发生改变。", user_id, username, ip_address, level=logging.ERROR)
                return False # 当前列表无视频，或者发生错误，退出

            console_log("-" * 20 + f" 任务‘{learning_task.task_name}’视频状态诊断 " + "-" * 20, user_id, username, ip_address, level=logging.INFO)
            # with next(get_db()) as db: # 移除此行，使用外部传入的db会话
            for i, video_ele in enumerate(video_elements):
                try:
                    await asyncio.sleep(0.5) # 增加短暂等待，确保元素内容加载
                    
                    title_ele = video_ele.ele('.title', timeout=5) # 视频标题的新 XPath
                    progress_text_ele = video_ele.ele('.isFinsh', timeout=5) # 进度文本的新 XPath
                    
                    # 检查视频是否处于活动状态（正在播放）
                    is_active_video = 'active' in video_ele.attr('class')

                    title_text = title_ele.text.strip() if title_ele else "[标题未找到]"
                    progress_text = progress_text_ele.text.strip() if progress_text_ele else "未完成" # 获取进度文本

                    # 获取或创建数据库中的 LearningVideo 记录
                    db_video = crud.get_or_create_learning_video(db, learning_task.id, title_text)
                    db.add(db_video) # 重新附加到会话
                    db.refresh(db_video) # 显式刷新对象
                    
                    # 更新数据库中的视频完成状态，如果页面显示已完成且不是当前正在播放的视频
                    if "已完成" in progress_text and not db_video.is_completed and not is_active_video:
                        crud.update_learning_video_progress(db, db_video.id, is_completed=True)
                        db.add(db_video) # 重新附加到会话
                        db.refresh(db_video) # 显式刷新对象
                        console_log(f"视频‘{db_video.video_title}’已在页面显示为完成，更新数据库。", user_id, username, ip_address, level=logging.INFO)

                    # 根据是否active显示当前播放状态，学习状态依然是 progress_text
                    status_display = progress_text # 学习状态只能是 '待学习' 或 '已完成'
                    console_log(f"序号 {i+1}: {db_video.video_title} -> 学习状态: '{status_display}' (DB ID: {db_video.id})", user_id, username, ip_address, level=logging.INFO)
                    
                    if is_active_video:
                        console_log(f"视频‘{db_video.video_title}’当前正在播放中。", user_id, username, ip_address, level=logging.INFO)

                    # 如果视频是“待学习”且“正在播放”，则优先处理此视频
                    if not db_video.is_completed and "待学习" in progress_text and is_active_video:
                        video_already_playing_element = video_ele
                        video_already_playing_db_obj = db_video
                        console_log(f"^^^ 识别到正在播放的待学习视频 (DB ID: {db_video.id}) ^^^", user_id, username, ip_address, level=logging.INFO)
                        # 移除这里的 break 语句，以便继续扫描所有视频

                    # 判断视频是否未完成（数据库中的 is_completed 为 False）
                    # 并且页面状态是'待学习'且不是当前正在播放的视频
                    if not db_video.is_completed and "待学习" in progress_text and \
                       not is_active_video and video_already_playing_db_obj is None:
                        if video_to_play_db_obj is None: # 只选择第一个符合条件的视频
                            video_to_play_element = video_ele
                            video_to_play_db_obj = db_video
                            # 只有在没有视频正在播放时，才打印此日志
                            if video_already_playing_db_obj is None:
                                console_log(f"^^^ 标记此视频为下一个播放目标 (DB ID: {db_video.id}) ^^^", user_id, username, ip_address, level=logging.INFO)

                except Exception as e:
                     console_log(f"读取序号 {i+1} 视频信息时出错: {e}", user_id, username, ip_address, level=logging.ERROR)
            console_log("-" * 55, user_id, username, ip_address, level=logging.INFO)

        except (PageDisconnectedError, CDPError):
            console_log("在查找视频时浏览器连接断开，退出任务。", user_id, username, ip_address, level=logging.ERROR)
            return False

        # 优先处理已经正在播放的待学习视频
        if video_already_playing_db_obj is not None:
            video_to_play_element = video_already_playing_element
            video_to_play_db_obj = video_already_playing_db_obj
            console_log(f"--- 根据诊断结果，发现视频: {video_to_play_db_obj.video_title} (DB ID: {video_to_play_db_obj.id}) 正在播放中，直接进入监控 ---", user_id, username, ip_address, level=logging.INFO)
            # 如果是正在播放的视频，则无需点击，直接进入播放监控循环

        # 如果没有正在播放的待学习视频，则尝试点击下一个待学习视频
        elif video_to_play_db_obj is not None:
            console_log(f"--- 根据诊断结果，找到目标视频: {video_to_play_db_obj.video_title} (DB ID: {video_to_play_db_obj.id}) ---", user_id, username, ip_address, level=logging.INFO)
            try:
                # 直接点击视频条目本身来触发播放
                video_to_play_element.click()
                console_log(f"已点击视频‘{video_to_play_db_obj.video_title}’条目，等待播放页面加载...", user_id, username, ip_address, level=logging.INFO)
                await asyncio.sleep(7) # 增加等待时间，确保视频加载到播放器

                # 同时更新主任务的URL，因为它代表了任务实际开始学习的页面
                # with next(get_db()) as db: # 移除此行，使用外部传入的db会话
                crud.update_learning_task_progress(db, learning_task.id, task_url=page.url)
                console_log(f"已将任务‘{learning_task.task_name}’的URL更新为: {page.url}。", user_id, username, ip_address, level=logging.INFO)

            except Exception as e:
                console_log(f"点击视频 '{video_to_play_db_obj.video_title}' 条目时出错: {e}，尝试扫描下一个...", user_id, username, ip_address, level=logging.ERROR)
                # with next(get_db()) as db: # 移除此行，使用外部传入的db会话
                crud.update_learning_video_progress(db, video_to_play_db_obj.id, is_completed=True) # 标记为完成，避免重复点击
                db.add(video_to_play_db_obj) # 重新附加到会话
                db.refresh(video_to_play_db_obj) # 显式刷新对象
                continue # 重新扫描视频列表

        # 如果既没有正在播放的待学习视频，也没有可点击的待学习视频，则认为所有视频已完成
        else:
            console_log(f"诊断完成：任务‘{learning_task.task_name}’未找到任何可学习的视频，所有视频均已完成！", user_id, username, ip_address, level=logging.INFO)
            with next(get_db()) as db_session_inner: # 此处需要一个新的会话，因为外层会话可能已关闭或不适用于此上下文
                crud.update_learning_task_progress(db_session_inner, learning_task.id, is_completed=True, current_progress="100.00%")
                console_log(f"任务‘{learning_task.task_name}’已标记为完成。", user_id, username, ip_address, level=logging.INFO)
            return True # 当前列表所有视频都已完成

        is_video_finished = False
        last_reported_time = -1

        while not is_video_finished:
            if stop_event.is_set(): # 检查停止信号
                console_log(f"收到停止信号，退出视频播放监控。", user_id, username, ip_address, level=logging.INFO)
                # with next(get_db()) as db: # 移除此行，使用外部传入的db会话
                crud.update_learning_video_progress(db, video_to_play_db_obj.id, current_progress_seconds=int(current_time), total_duration_seconds=int(duration))
                db.add(video_to_play_db_obj) # 重新附加到会话
                db.refresh(video_to_play_db_obj) # 显式刷新对象
                console_log(f"已保存视频‘{video_to_play_db_obj.video_title}’的当前播放进度到数据库。", user_id, username, ip_address, level=logging.INFO)
                break
            try:
                video_player = page.ele('tag:video', timeout=5)
                js_get_time = "return {currentTime: document.querySelector('video').currentTime, duration: document.querySelector('video').duration};"
                progress = page.run_js(js_get_time)
                if not isinstance(progress, dict):
                    sleep_task = asyncio.create_task(asyncio.sleep(2))
                    stop_task = asyncio.create_task(stop_event.wait())
                    done, pending = await asyncio.wait([sleep_task, stop_task], return_when=asyncio.FIRST_COMPLETED)
                    if stop_task in done: 
                        for task in pending: task.cancel()
                        return False 
                    for task in pending: task.cancel()
                    continue
                current_time = progress.get('currentTime', 0)
                duration = progress.get('duration', 0)
                if duration is None or duration == 0 or current_time is None:
                    console_log("等待视频加载元数据...", user_id, username, ip_address, level=logging.INFO)
                    await asyncio.sleep(5); continue
                if current_time >= duration - 3: 
                    is_video_finished = True
                    console_log(f"视频 '{video_to_play_db_obj.video_title}' 播放完毕。", user_id, username, ip_address, level=logging.INFO)
                    # with next(get_db()) as db: # 移除此行，使用外部传入的db会话
                    crud.update_learning_video_progress(db, video_to_play_db_obj.id, current_progress_seconds=int(duration), total_duration_seconds=int(duration), is_completed=True)
                    db.add(video_to_play_db_obj) # 重新附加到会话
                    db.refresh(video_to_play_db_obj) # 显式刷新对象
                    console_log(f"已将视频‘{video_to_play_db_obj.video_title}’标记为完成。", user_id, username, ip_address, level=logging.INFO)
                else:
                    if int(current_time) > last_reported_time + 9:
                        formatted_current_time = format_seconds_to_hms(int(current_time))
                        formatted_duration = format_seconds_to_hms(int(duration))
                        console_log(f"播放进度: {formatted_current_time} / {formatted_duration}", user_id, username, ip_address, level=logging.INFO)
                        last_reported_time = int(current_time)
                        # with next(get_db()) as db: # 移除此行，使用外部传入的db会话
                        crud.update_learning_video_progress(db, video_to_play_db_obj.id, current_progress_seconds=int(current_time), total_duration_seconds=int(duration))
                        db.add(video_to_play_db_obj) # 重新附加到会话
                        db.refresh(video_to_play_db_obj) # 显式刷新对象
                    sleep_task = asyncio.create_task(asyncio.sleep(2))
                    stop_task = asyncio.create_task(stop_event.wait())
                    done, pending = await asyncio.wait([sleep_task, stop_task], return_when=asyncio.FIRST_COMPLETED)
                    if stop_task in done:
                        for task in pending: task.cancel()
                        return False 
                    for task in pending: task.cancel()
            except (PageDisconnectedError, CDPError) as e:
                console_log(f"浏览器或操作失败，监控中断: {e}", user_id, username, ip_address, level=logging.ERROR)
                is_video_finished = True; break
            except ElementNotFoundError:
                console_log("在当前页面未找到 <video> 播放器，可能页面还未加载完成，重试中...", user_id, username, ip_address, level=logging.WARNING)
                sleep_task = asyncio.create_task(asyncio.sleep(5))
                stop_task = asyncio.create_task(stop_event.wait())
                done, pending = await asyncio.wait([sleep_task, stop_task], return_when=asyncio.FIRST_COMPLETED)
                if stop_task in done: 
                    for task in pending: task.cancel()
                    return False
                for task in pending: task.cancel()
            except Exception as e:
                console_log(f"监控进度时发生未知错误: {e}，判定此视频播放结束。", user_id, username, ip_address, level=logging.ERROR)
                is_video_finished = True
        console_log(f"准备返回任务‘{learning_task.task_name}’视频列表上一个页面...", user_id, username, ip_address, level=logging.INFO)
        try:
            # 移除此处的返回操作，导航将由调用方处理
            console_log(f"视频列表处理完毕，将返回上一级由主程序导航。", user_id, username, ip_address, level=logging.INFO)
        except Exception as e:
            console_log(f"执行返回操作失败: {e}，程序终止。", user_id, username, ip_address, level=logging.ERROR)
            return False
    return True

async def launch_browser_for_user_login(user_id: int, url: str, username: Optional[str] = None, password: Optional[str] = None, headless: bool = False, ip_address: Optional[str] = None):
    console_log(f"正在启动浏览器进行登录... {'(无头模式)' if headless else '(有头模式)'}", user_id, username, ip_address, level=logging.INFO)
    # 如果该用户已有活跃的浏览器实例，先关闭它
    if user_id in _active_browser_pages and _active_browser_pages[user_id]:
        try:
            _active_browser_pages[user_id].quit()
            console_log(f"已关闭旧的浏览器实例。", user_id, username, ip_address, level=logging.INFO)
        except Exception as e:
            console_log(f"关闭旧浏览器实例时出错: {e}", user_id, username, ip_address, level=logging.ERROR)
            
    # 创建 ChromiumOptions 实例
    options = ChromiumOptions()
    # 根据 headless 参数设置无头模式
    options.headless(headless)
    # 设置临时用户数据路径，确保每次运行环境干净
    options.set_paths(user_data_path='./tmp_user_data') # 将 tmp_path 改为 user_data_path

    try:
        # 将配置好的 options 传递给 ChromiumPage 构造函数
        page = ChromiumPage(options) # 创建新的浏览器实例，并传入配置好的 options
        page.set.auto_handle_alert()
        console_log(f"自动弹窗处理已开启。", user_id, username, ip_address, level=logging.INFO)
        page.set.window.max()
        
        # 确保URL包含协议头
        if not url.startswith("http://") and not url.startswith("https://"):
            url = "https://" + url
            console_log(f"URL缺少协议，已自动添加 https://", user_id, username, ip_address, level=logging.INFO)
            
        page.get(url)
        console_log(f"浏览器启动成功！已打开登录页面: {url}", user_id, username, ip_address, level=logging.INFO)
        
        # 尝试自动登录和后续导航
        if username and password:
            console_log(f"尝试自动登录学习网站...", user_id, username, ip_address, level=logging.INFO)
            await asyncio.sleep(2) # 等待页面完全加载
            
            try:
                # 填写用户名
                username_input = page.ele(f'xpath://input[@placeholder="请输入账号（身份证号）"]')
                if username_input:
                    username_input.input(username)
                    console_log(f"已填写用户名。", user_id, username, ip_address, level=logging.INFO)
                else:
                    console_log(f"未找到用户名输入框。", user_id, username, ip_address, level=logging.WARNING)
                    raise ElementNotFoundError("用户名输入框未找到")

                # 填写密码
                password_input = page.ele(f'xpath://input[@placeholder="请输入密码" and @type="password"]')
                if password_input:
                    password_input.input(password)
                    console_log(f"已填写密码。", user_id, username, ip_address, level=logging.INFO)
                else:
                    console_log(f"未找到密码输入框。", user_id, username, ip_address, level=logging.WARNING)
                    raise ElementNotFoundError("密码输入框未找到")
                
                await asyncio.sleep(1) # 等待输入完成

                # 点击“阅读并同意”复选框
                agree_checkbox = page.ele(f'xpath://*[@id="app"]/div[1]/div[2]/div[1]/div[2]/label/span[1]/input')
                if agree_checkbox:
                    # 使用 run_js 获取 checked 属性
                    is_checked = agree_checkbox.run_js('return this.checked;')
                    if not is_checked:
                        agree_checkbox.click()
                        console_log(f"已点击‘阅读并同意’复选框。", user_id, username, ip_address, level=logging.INFO)
                    else:
                        console_log(f"‘阅读并同意’复选框已选中。", user_id, username, ip_address, level=logging.INFO)
                else:
                    console_log(f"未找到‘阅读并同意’复选框。", user_id, username, ip_address, level=logging.WARNING)
                    # 不强制要求找到，因为有些页面可能没有或已默认选中

                await asyncio.sleep(1) # 等待点击完成

                # 点击登录按钮
                login_button = page.ele(f'xpath://*[@id="app"]/div[1]/div[2]/div[1]/div[2]/div[1]/div[5]')
                if login_button:
                    login_button.click()
                    console_log(f"已点击登录按钮。", user_id, username, ip_address, level=logging.INFO)
                    # 等待页面加载，或者等待某个成功登录后的标志性元素出现
                    try:
                        # 等待'Personage' div出现，作为成功登录的标志
                        page.ele(f'xpath://div[@data-v-a2cdffec and @class="Personage"]', timeout=15)
                        # console_log(f"成功登录并进入个人空间页面。", user_id) # 将此行移动到弹窗处理之后
                    except ElementNotFoundError:
                        console_log(f"登录后未找到个人空间页面标志元素，可能登录失败或页面加载异常。", user_id, username, ip_address, level=logging.WARNING)
                        raise ElementNotFoundError("登录后个人空间页面标志元素未找到") # 抛出异常以终止当前流程

                    await asyncio.sleep(3) # 额外等待，确保页面完全加载或重定向到个人空间页

                else:
                    console_log(f"未找到登录按钮。", user_id, username, ip_address, level=logging.WARNING)
                    raise ElementNotFoundError("登录按钮未找到")

                # 尝试关闭登录后可能出现的弹窗
                console_log(f"尝试关闭登录后弹窗...", user_id, username, ip_address, level=logging.INFO)
                try:
                    popup_close_button = page.ele(f'xpath:/html/body/div[3]/div/div[2]/div/div[2]/div[3]/div/button', timeout=3) # 设置一个较短的超时时间
                    if popup_close_button:
                        popup_close_button.click()
                        console_log(f"成功关闭登录后弹窗。", user_id, username, ip_address, level=logging.INFO)
                    else:
                        console_log(f"未找到登录后弹窗的关闭按钮，可能没有弹窗。", user_id, username, ip_address, level=logging.INFO)
                except Exception as e:
                    # 如果弹窗关闭失败，不影响后续操作，只记录日志
                    console_log(f"关闭登录后弹窗时发生错误或未找到弹窗: {e}", user_id, username, ip_address, level=logging.WARNING)

                # 确认登录并进入个人空间页面
                console_log(f"成功登录并进入个人空间页面。", user_id, username, ip_address, level=logging.INFO) # 移动到此处

                await asyncio.sleep(3) # 额外等待，确保页面完全加载或重定向到个人空间页

                # 点击“专业技术人员继续教育”按钮
                console_log(f"尝试点击‘专业技术人员继续教育’按钮...", user_id, username, ip_address, level=logging.INFO)
                # 等待按钮出现，最多等待10秒
                professional_button = page.ele(f'xpath://*[@id="app"]/div[1]/div[2]/div[2]/div/div[2]/div[1]/label[1]', timeout=10) # 增加 timeout 到 10秒
                if professional_button:
                    professional_button.click()
                    console_log(f"成功点击‘专业技术人员继续教育’按钮。", user_id, username, ip_address, level=logging.INFO)
                    await asyncio.sleep(3) # 等待页面跳转到课程列表页
                    
                    # 移除此处保存视频列表URL的逻辑，因为这里还是课程类型页，且URL保存已由crud.get_or_create_learning_task处理
                    # current_video_list_url = page.url
                    # with next(get_db()) as db:
                    #     crud.update_learning_website_credential_video_list_url(db, user_id, current_video_list_url)
                    #     console_log(f"已保存课程列表URL: {current_video_list_url} 到数据库。", user_id)
                else:
                    console_log(f"未找到‘专业技术人员继续教育’按钮。", user_id, username, ip_address, level=logging.WARNING)
                    raise ElementNotFoundError("‘专业技术人员继续教育’按钮未找到")

            except ElementNotFoundError as e:
                console_log(f"自动登录或初始导航失败，关键元素未找到: {e}", user_id, username, ip_address, level=logging.WARNING)
                # 即使自动登录失败，也继续存储页面实例，等待用户手动操作
            except Exception as e:
                console_log(f"自动登录或初始导航时发生未知错误: {e}", user_id, username, ip_address, level=logging.ERROR)
                # 即使自动登录失败，也继续存储页面实例，等待用户手动操作
            
            # 自动登录和初始导航成功，存储活跃的页面实例并返回
            _active_browser_pages[user_id] = page # 存储活跃的页面实例
            return page # 返回活跃的页面实例
        
    except Exception as e:
        console_log(f"浏览器启动失败: {e}", user_id, username, ip_address, level=logging.ERROR)
        if user_id in _active_browser_pages: # 清理失败的实例
            del _active_browser_pages[user_id]
        raise

async def get_cookies_for_user(user_id: int, username: Optional[str] = None, ip_address: Optional[str] = None):
    console_log(f"正在获取会话 Cookies...", user_id, username, ip_address, level=logging.INFO)
    page = _active_browser_pages.get(user_id)
    if not page:
        console_log(f"没有找到活跃的浏览器实例。", user_id, username, ip_address, level=logging.WARNING)
        return None

    try:
        cookies = page.cookies()
        console_log(f"成功获取 Cookies。", user_id, username, ip_address, level=logging.INFO)
        return json.dumps(cookies) # 返回 JSON 字符串
    except Exception as e:
        console_log(f"获取 Cookies 失败: {e}", user_id, username, ip_address, level=logging.ERROR)
        raise

async def close_browser_for_user(user_id: int, username: Optional[str] = None, ip_address: Optional[str] = None):
    console_log(f"正在关闭浏览器实例...", user_id, username, ip_address, level=logging.INFO)
    page = _active_browser_pages.get(user_id)
    if page:
        try:
            console_log(f"浏览器返回上一页...", user_id, username, ip_address, level=logging.INFO)
            page.back() # 返回上一页
            await asyncio.sleep(2) # 等待2秒
            page.quit()
            console_log(f"浏览器已关闭。", user_id, username, ip_address, level=logging.INFO)
        except (PageDisconnectedError, CDPError, Exception) as e: # 捕获 DrissionPage 错误和其他通用异常
            console_log(f"关闭浏览器时发生错误: {e}", user_id, username, ip_address, level=logging.ERROR)
        finally:
            del _active_browser_pages[user_id]
            # 关闭浏览器时清空该用户的日志
            # if user_id in _user_logs: # 移除此行，因为 _user_logs 已删除
            #     del _user_logs[user_id]
    else:
        console_log(f"没有找到要关闭的浏览器实例。", user_id, username, ip_address, level=logging.INFO)

async def stop_auto_watcher_for_user(user_id: int, username: Optional[str] = None, ip_address: Optional[str] = None):
    console_log(f"正在设置停止自动化任务信号...", user_id, username, ip_address, level=logging.INFO)
    if user_id in _stop_events:
        _stop_events[user_id].set() # 设置停止事件
        console_log(f"停止信号已设置。", user_id, username, ip_address, level=logging.INFO)
    else:
        console_log(f"没有找到对应的自动化任务停止事件。", user_id, username, ip_address, level=logging.WARNING)

async def run_auto_watcher(user_id: int, page: ChromiumPage, credential_id: int, ip_address: Optional[str] = None, username: Optional[str] = None): # 移除 initial_url, session_cookies 参数，添加 page 参数
    console_log("正在初始化浏览器 (使用 DrissionPage) 进行自动化学习...", user_id, username, ip_address, level=logging.INFO)
    _stop_events[user_id] = asyncio.Event() # 为当前用户创建停止事件
    
    with next(get_db()) as db:
        credential = crud.get_learning_website_credential(db, credential_id=credential_id, system_user_id=user_id)
        if not credential:
            console_log(f"未找到凭据 ID {credential_id} 或无权限访问。", user_id, username, ip_address, level=logging.WARNING)
            if user_id in _stop_events:
                del _stop_events[user_id]
            if page:
                try: page.quit()
                except Exception as e: console_log(f"关闭浏览器时发生错误: {e}", user_id, username, ip_address, level=logging.ERROR)
            return

    try:
        console_log(f"自动化学习任务已启动，使用现有浏览器会话。", user_id, username, ip_address, level=logging.INFO)
        console_log("等待页面加载完成...", user_id, username, ip_address, level=logging.INFO)
        await asyncio.sleep(5) # 等待页面加载
        
        # 定义课程类型切换按钮的 XPath 列表
        course_type_buttons_info = [
            {
                "name": "专业技术人员继续教育",
                "xpath": "//*[@id='app']/div[1]/div[2]/div[2]/div/div[2]/div[1]/label[1]"
            }
        ]

        all_courses_completed_overall = True

        for course_type_info in course_type_buttons_info:
            if _stop_events[user_id].is_set():
                console_log(f"收到停止信号，中止后续课程类型学习。", user_id, username, ip_address, level=logging.INFO)
                all_courses_completed_overall = False
                break

            course_name = course_type_info['name']
            button_xpath = course_type_info['xpath']

            console_log(f"\n--- 正在切换到课程类型: {course_name} ---", user_id, username, ip_address, level=logging.INFO)
            try:
                type_button = page.ele(f'xpath:{button_xpath}', timeout=10)
                if type_button:
                    current_class = type_button.run_js('return this.className;')
                    if 'ant-radio-button-wrapper-checked' in current_class:
                        console_log(f"‘{course_name}’按钮已选中，无需点击。", user_id, username, ip_address, level=logging.INFO)
                    else:
                        type_button.click()
                        console_log(f"已点击‘{course_name}’按钮。", user_id, username, ip_address, level=logging.INFO)
                        await asyncio.sleep(5) # 等待页面加载新的课程列表
                    
                    # 移除此处保存视频列表URL的逻辑，因为这里还是课程类型页，且URL保存已由crud.get_or_create_learning_task处理
                    # current_video_list_url = page.url
                    # with next(get_db()) as db:
                    #     crud.update_learning_website_credential_video_list_url(db, user_id, current_video_list_url)
                    #     console_log(f"已保存课程列表URL: {current_video_list_url} 到数据库。", user_id)

                # 等待任务列表容器完全加载和可见
                console_log(f"等待任务列表容器加载...", user_id, username, ip_address, level=logging.INFO)
                try:
                    page.ele('xpath://div[@class="objectList"]/ul[@class="scroll-bar"]', timeout=15) # 增加等待时间
                    console_log(f"任务列表容器已加载。", user_id, username, ip_address, level=logging.INFO)
                except ElementNotFoundError:
                    console_log(f"任务列表容器未在预期时间内加载，可能页面结构已改变。", user_id, username, ip_address, level=logging.WARNING)
                    all_courses_completed_overall = False
                    break # 退出当前课程类型循环

                console_log(f"正在扫描‘{course_name}’下的任务列表...", user_id, username, ip_address, level=logging.INFO)
                # 修正任务列表的 XPath
                task_list_locator = "xpath://div[@class=\'objectList\']/ul[@class=\'scroll-bar\']/li"

                while True:
                    if _stop_events[user_id].is_set():
                        console_log(f"收到停止信号，中止任务列表遍历。", user_id, username, ip_address, level=logging.INFO)
                        all_courses_completed_overall = False
                        break

                    tasks_on_page = []
                    try:
                        task_elements = page.eles(task_list_locator)
                        if not task_elements:
                            console_log(f"未找到‘{course_name}’下的任何任务条目，可能已全部完成或页面结构改变。", user_id, username, ip_address, level=logging.INFO)
                            break # 退出任务列表循环

                        console_log("-" * 20 + " 任务状态诊断 " + "-" * 20, user_id, username, ip_address, level=logging.INFO)
                        for i, task_ele in enumerate(task_elements):
                            try:
                                await asyncio.sleep(0.5)

                                # 1. 定位元素
                                task_title_ele = task_ele.ele('xpath:.//p[contains(@class, "center-title")]', timeout=10)
                                task_progress_ele = task_ele.ele('xpath:.//div[@class="center-center"]/p', timeout=10)
                                task_hours_ele = task_ele.ele('xpath:.//div[@class="ul-center"]/p', timeout=10)
                                start_study_button_ele = task_ele.ele('xpath:.//button[contains(text(), "开始学习")]', timeout=10)

                                # 2. 正确地等待元素可见 (这是一个异步操作，需要 await)
                                task_title_ele.wait.displayed()

                                # 3. [修复 TypeError] 正确地获取文本 (这是一个同步操作，严禁使用 await)
                                task_title = task_title_ele.text.strip() if task_title_ele else "[任务标题未找到]"
                                # 修正：移除标题末尾的“未学习”标记
                                if task_title.endswith(" 未学习"):
                                    task_title = task_title[:-len(" 未学习")]
                                task_progress = task_progress_ele.text.strip() if task_progress_ele else "0.00%"
                                task_hours = task_hours_ele.text.strip() if task_hours_ele else "未知"

                                # (数据库操作部分)
                                with next(get_db()) as db_session:
                                    db_task = crud.get_or_create_learning_task(db_session, credential.id, task_title, page.url, task_hours)
                                    if db_task.current_progress != task_progress:
                                        crud.update_learning_task_progress(db_session, db_task.id, current_progress=task_progress)
                                console_log(f"序号 {i+1}: 任务名称: {db_task.task_name} -> 学习进度: {task_progress} -> 学时: {task_hours} (DB ID: {db_task.id})", user_id, username, ip_address, level=logging.INFO)
                                # 4. [修复逻辑漏洞] 将扫描到的可学习任务添加到待处理列表
                                if start_study_button_ele and not db_task.is_completed:
                                    tasks_on_page.append({
                                        "element": task_ele,
                                        "db_obj": db_task,
                                        "button": start_study_button_ele
                                    })
                            except Exception as e:
                                console_log(f"读取序号 {i+1} 任务信息时出错: {e}", user_id, username, ip_address, level=logging.ERROR)
                        console_log("-" * 55, user_id, username, ip_address, level=logging.INFO)

                    except (ElementNotFoundError, PageDisconnectedError, CDPError) as e:
                        console_log(f"扫描任务列表时出错: {e}，退出任务处理。", user_id, username, ip_address, level=logging.ERROR)
                        all_courses_completed_overall = False
                        break # 出现错误，退出整个自动化

                    # 筛选出未完成的任务进行处理
                    tasks_to_process_this_round = [t for t in tasks_on_page if not t['db_obj'].is_completed]
                    
                    if not tasks_to_process_this_round:
                        console_log(f"‘{course_name}’下所有任务均已完成或没有可学习的任务。", user_id, username, ip_address, level=logging.INFO)
                        break # 退出任务列表循环

                    # 循环处理每个未完成的任务
                    for task in tasks_to_process_this_round:
                        if _stop_events[user_id].is_set():
                            console_log(f"收到停止信号，中止当前任务的学习。", user_id, username, ip_address, level=logging.INFO)
                            all_courses_completed_overall = False
                            break # 退出任务学习循环
                        
                        console_log(f"--- 正在学习任务: {task['db_obj'].task_name} (DB ID: {task['db_obj'].id}) ---", user_id, username, ip_address, level=logging.INFO)
                        try:
                            task['button'].click() # 点击任务的“开始学习”按钮
                            console_log(f"已点击任务‘{task['db_obj'].task_name}’的‘开始学习’按钮，等待视频列表页加载...", user_id, username, ip_address, level=logging.INFO)
                            # 等待视频列表页面的关键元素加载，例如 class="videoList" 的 div
                            page.ele('xpath://div[@class="videoList"]', timeout=20).wait.displayed() # 增加等待时间，确保页面完全加载
                            console_log(f"视频列表页面已加载。", user_id, username, ip_address, level=logging.INFO)
                            # await asyncio.sleep(5) # 移除固定等待时间，依靠 ele().wait.displayed()

                            # 调用 process_single_task_videos 处理当前任务的视频列表
                            task_success = await process_single_task_videos(user_id, page, task['db_obj'], _stop_events[user_id], db, ip_address, username)

                            if _stop_events[user_id].is_set(): # 如果在处理视频过程中收到停止信号
                                console_log(f"收到停止信号，任务‘{task['db_obj'].task_name}’未完成。", user_id, username, ip_address, level=logging.INFO)
                                break # 退出当前任务循环，让 finally 块处理浏览器关闭

                            # 如果任务的所有视频都已完成，更新任务状态
                            if task_success:
                                # with next(get_db()) as db_session: # 移除此行，使用外部传入的db会话
                                crud.update_learning_task_progress(db, task['db_obj'].id, is_completed=True, current_progress="100.00%")
                                console_log(f"任务‘{task['db_obj'].task_name}’已标记为完成。", user_id, username, ip_address, level=logging.INFO)

                            console_log(f"任务‘{task['db_obj'].task_name}’视频学习完成或已中止。准备返回任务列表。", user_id, username, ip_address, level=logging.INFO)
                            # 直接导航回任务列表页面，而不是使用 page.back()
                            page.get(task['db_obj'].task_url) # 直接导航到任务URL
                            await asyncio.sleep(2) # 等待任务列表页重新加载

                        except (ElementNotFoundError, PageDisconnectedError, CDPError) as e:
                            console_log(f"处理任务‘{task['db_obj'].task_name}’时出现错误: {e}，退出任务学习。", user_id, username, ip_address, level=logging.ERROR)
                            all_courses_completed_overall = False # 标记为未完全完成
                        except Exception as e:
                            console_log(f"处理任务‘{task['db_obj'].task_name}’时发生未知错误: {e}，退出任务学习。", user_id, username, ip_address, level=logging.ERROR)
                            all_courses_completed_overall = False # 标记为未完全完成
                        # finally:
                        #     console_log("\n" + "="*30, user_id)
                        #     console_log("自动化任务已结束（可能未完全完成或被手动中止）。", user_id)
                        #     console_log("="*30, user_id)
                        #     # 在任务结束后，统一处理浏览器关闭
                        #     await close_browser_for_user(user_id) # 统一调用关闭浏览器函数
                        #     # 任务结束后清除停止事件
                        #     if user_id in _stop_events:
                        #         del _stop_events[user_id]

                    if not all_courses_completed_overall: # 如果内部循环被停止或有错误，退出外层任务列表循环
                        break

                    await asyncio.sleep(3) # 等待短暂时间，防止无限循环和 CPU 占用过高

            except Exception as e:
                console_log(f"处理课程类型‘{course_name}’时发生错误: {e}", user_id, username, ip_address, level=logging.ERROR)
                all_courses_completed_overall = False
                break # 出现错误，退出课程类型循环

        if all_courses_completed_overall and not _stop_events[user_id].is_set():
            console_log("\n" + "="*30, user_id, username, ip_address, level=logging.INFO)
            console_log("恭喜！所有课程列表中的所有视频都已学习完成！", user_id, username, ip_address, level=logging.INFO)
            console_log("="*30, user_id, username, ip_address, level=logging.INFO)
        else:
            console_log("\n" + "="*30, user_id, username, ip_address, level=logging.INFO)
            console_log("自动化任务已结束（可能未完全完成或被手动中止）。", user_id, username, ip_address, level=logging.INFO)
            console_log("="*30, user_id, username, ip_address, level=logging.INFO)

    except Exception as e:
        console_log(f"自动化执行过程中发生严重错误: {e}", user_id, username, ip_address, level=logging.ERROR)
    finally:
        # 任务结束后清除停止事件
        if user_id in _stop_events:
            del _stop_events[user_id]
        if page:
            try:
                page.quit()
                console_log("浏览器已关闭。", user_id, username, ip_address, level=logging.INFO)
            except Exception as e:
                console_log(f"关闭浏览器时发生错误: {e}", user_id, username, ip_address, level=logging.ERROR)
    console_log("自动化流程已结束。", user_id, username, ip_address, level=logging.INFO)