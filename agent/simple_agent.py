import base64
import copy
import io
import json
import logging
import os
import pickle
import shutil
import time
from datetime import datetime

from config import MAX_TOKENS, MODEL_NAME, TEMPERATURE, USE_NAVIGATOR

from agent.emulator import Emulator
from anthropic import Anthropic

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger(__name__)


def get_screenshot_base64(screenshot, upscale=1):
    """Convert PIL image to base64 string."""
    # Resize if needed
    if upscale > 1:
        new_size = (screenshot.width * upscale, screenshot.height * upscale)
        screenshot = screenshot.resize(new_size)

    # Convert to base64
    buffered = io.BytesIO()
    screenshot.save(buffered, format="PNG")
    return base64.standard_b64encode(buffered.getvalue()).decode()


SYSTEM_PROMPT = """你正在玩宝可梦红版。你可以看到游戏画面并通过执行模拟器命令来控制游戏。
 
你的目标是通关宝可梦红版并最终击败四天王。根据你在屏幕上看到的内容做出决策。
 
在每个动作之前，简要解释你的推理，然后使用模拟器工具执行你选择的命令。
 
对话历史可能会偶尔被总结以节省上下文空间。如果你看到标记为"对话历史总结"的消息，这包含了关于你迄今为止进展的关键信息。使用这些信息来保持你游戏玩法的连续性。"""
 
SUMMARY_PROMPT = """我需要你创建一个详细的总结，包含我们到目前为止的对话历史。这个总结将替换完整的对话历史以管理上下文窗口。
 
请包括：
1. 你达到的关键游戏事件和里程碑
2. 你做出的重要决定
3. 你当前正在处理的目标或任务
4. 你当前的位置和宝可梦队伍状态
5. 你提到的任何策略或计划
 
总结应该足够全面，以便你可以在不丢失重要上下文的情况下继续游戏。"""


AVAILABLE_TOOLS = [
    {
        "name": "press_buttons",
        "description": "Press a sequence of buttons on the Game Boy.",
        "input_schema": {
            "type": "object",
            "properties": {
                "buttons": {
                    "type": "array",
                    "items": {
                        "type": "string",
                        "enum": ["a", "b", "start", "select", "up", "down", "left", "right"]
                    },
                    "description": "List of buttons to press in sequence. Valid buttons: 'a', 'b', 'start', 'select', 'up', 'down', 'left', 'right'"
                },
                "wait": {
                    "type": "boolean",
                    "description": "Whether to wait for a brief period after pressing each button. Defaults to true."
                }
            },
            "required": ["buttons"],
        },
    }
]

if USE_NAVIGATOR:
    AVAILABLE_TOOLS.append({
        "name": "navigate_to",
        "description": "Automatically navigate to a position on the map grid. The screen is divided into a 9x10 grid, with the top-left corner as (0, 0). This tool is only available in the overworld.",
        "input_schema": {
            "type": "object",
            "properties": {
                "row": {
                    "type": "integer",
                    "description": "The row coordinate to navigate to (0-8)."
                },
                "col": {
                    "type": "integer",
                    "description": "The column coordinate to navigate to (0-9)."
                }
            },
            "required": ["row", "col"],
        },
    })


class SimpleAgent:
    def __init__(self, rom_path, headless=True, sound=False, max_history=60, 
                 load_state=None, save_interval=10, save_dir="./saves", auto_save_enabled=True):
        """Initialize the simple agent.

        Args:
            rom_path: Path to the ROM file
            headless: Whether to run without display
            sound: Whether to enable sound
            max_history: Maximum number of messages in history before summarization
            load_state: Path to saved state file to load
            save_interval: Number of steps between auto-saves
            save_dir: Directory to save game states
            auto_save_enabled: Whether to enable automatic saving
        """
        self.emulator = Emulator(rom_path, headless, sound)
        self.emulator.initialize()  # Initialize the emulator
        self.client = Anthropic(api_key="sk-ksbCidPFhLiGTRo_I4fflYASF92UHYC8S1DNHp2kkbTaJkRShC8oOKPIJdI",  # 替换为您的实际API key
    base_url="https://chatapi.leyidc.net/claude")
        self.running = True
        self.message_history = [{"role": "user", "content": "你现在可以开始游戏了。"}]
        self.max_history = max_history
        
        # 保存相关属性
        self.save_interval = save_interval
        self.save_dir = save_dir
        self.auto_save_enabled = auto_save_enabled
        self.total_steps = 0  # 累计总步数计数器
        
        # 确保保存目录存在
        os.makedirs(self.save_dir, exist_ok=True)
        
        if load_state:
            logger.info(f"从 {load_state} 加载保存的状态")
            if load_state.endswith('.pkl'):
                # 新格式：完整状态文件
                self.load_complete_state(load_state)
            else:
                # 旧格式：只有游戏状态
                self.emulator.load_state(load_state)

    def get_save_filename(self, total_steps):
        """获取存档文件名，包含总步数信息"""
        return os.path.join(self.save_dir, f"pokemon_save_step{total_steps:04d}.pkl")

    def get_backup_filename(self, total_steps):
        """获取备份文件名"""
        return os.path.join(self.save_dir, f"pokemon_save_step{total_steps:04d}_backup.pkl")

    def find_latest_save(self):
        """查找最新的存档文件"""
        if not os.path.exists(self.save_dir):
            return None, 0
        
        save_files = []
        for filename in os.listdir(self.save_dir):
            if filename.startswith("pokemon_save_step") and filename.endswith(".pkl") and "backup" not in filename:
                try:
                    step_str = filename.replace("pokemon_save_step", "").replace(".pkl", "")
                    steps = int(step_str)
                    save_files.append((steps, filename))
                except ValueError:
                    continue
        
        if save_files:
            latest_steps, latest_filename = max(save_files, key=lambda x: x[0])
            return os.path.join(self.save_dir, latest_filename), latest_steps
        
        return None, 0

    def extract_current_summary(self):
        """提取当前的summary_text"""
        if (len(self.message_history) == 1 and 
            self.message_history[0]["role"] == "user"):
            
            content = self.message_history[0]["content"]
            if isinstance(content, list) and len(content) > 0:
                first_text = content[0].get("text", "")
                if "对话历史摘要" in first_text:
                    if ": " in first_text:
                        return first_text.split(": ", 1)[1]
        
        return None

    def restore_summary_to_history(self, summary_text):
        """基于保存的summary_text重建message_history"""
        screenshot = self.emulator.get_screenshot()
        screenshot_b64 = get_screenshot_base64(screenshot, upscale=2)
        
        self.message_history = [
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": f"对话历史摘要 (代表之前的 {self.max_history} 条消息): {summary_text}"
                    },
                    {
                        "type": "text",
                        "text": "\n\n当前游戏截图供参考:"
                    },
                    {
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": "image/png",
                            "data": screenshot_b64,
                        },
                    },
                    {
                        "type": "text",
                        "text": "你刚刚被要求总结到目前为止的游戏过程，这就是你在上面看到的摘要。你现在可以通过选择下一个动作来继续游戏。"
                    },
                ]
            }
        ]

    def save_with_backup(self, save_data, total_steps):
        """安全保存策略：备份旧存档，保存新存档"""
        try:
            # 查找并备份旧存档
            old_save_path, old_steps = self.find_latest_save()
            if old_save_path and os.path.exists(old_save_path):
                backup_path = self.get_backup_filename(old_steps)
                shutil.move(old_save_path, backup_path)
                logger.info(f"💾 旧存档已备份: {os.path.basename(backup_path)}")
            
            # 保存新存档
            new_save_path = self.get_save_filename(total_steps)
            with open(new_save_path, 'wb') as f:
                pickle.dump(save_data, f)
            
            file_size = os.path.getsize(new_save_path) / 1024  # KB
            logger.info(f"✅ 存档保存成功: {os.path.basename(new_save_path)} ({file_size:.1f}KB)")
            
        except Exception as e:
            logger.error(f"❌ 保存失败: {e}")
            raise

    def auto_save(self, total_steps):
        """自动保存方法"""
        logger.info(f"🔄 [自动保存] 正在保存游戏进度 (第{total_steps}步)...")
        
        # 创建临时字节流来保存PyBoy状态
        pyboy_state_buffer = io.BytesIO()
        self.emulator.pyboy.save_state(pyboy_state_buffer)
        pyboy_state_buffer.seek(0)
        
        save_data = {
            "pyboy_state": pyboy_state_buffer.getvalue(),
            "message_history": self.message_history,
            "summary_text": self.extract_current_summary(),
            "total_steps": total_steps,
            "save_time": datetime.now().isoformat(),
            "game_info": self.emulator.get_state_from_memory(),
            "version": "1.0"
        }
        
        try:
            self.save_with_backup(save_data, total_steps)
            logger.info(f"🎮 [自动保存] 游戏进度已保存 (累计{total_steps}步)")
        except Exception as e:
            logger.error(f"❌ [自动保存] 保存失败，游戏将继续运行: {e}")

    def emergency_save(self):
        """紧急保存方法"""
        logger.info("🚨 检测到程序异常退出，正在执行紧急保存...")
        
        # 创建临时字节流来保存PyBoy状态
        pyboy_state_buffer = io.BytesIO()
        self.emulator.pyboy.save_state(pyboy_state_buffer)
        pyboy_state_buffer.seek(0)
        
        save_data = {
            "pyboy_state": pyboy_state_buffer.getvalue(),
            "message_history": self.message_history,
            "summary_text": self.extract_current_summary(),
            "total_steps": self.total_steps,
            "save_time": datetime.now().isoformat(),
            "game_info": self.emulator.get_state_from_memory(),
            "version": "1.0"
        }
        
        try:
            self.save_with_backup(save_data, self.total_steps)
            logger.info(f"🛡️ 紧急保存完成！游戏进度已安全保存 (第{self.total_steps}步)")
        except Exception as e:
            logger.error(f"❌ 紧急保存失败，游戏进度可能丢失: {e}")

    def load_complete_state(self, filename):
        """加载完整的游戏和AI状态"""
        logger.info(f"📂 正在加载存档: {os.path.basename(filename)}")
        
        try:
            # 1. 读取保存文件
            with open(filename, 'rb') as f:
                save_data = pickle.load(f)
            
            file_size = os.path.getsize(filename) / 1024  # KB
            save_time = save_data.get("save_time", "未知时间")
            
            # 2. 恢复游戏状态
            logger.info("🎮 正在恢复游戏状态...")
            pyboy_state_buffer = io.BytesIO(save_data["pyboy_state"])
            self.emulator.pyboy.load_state(pyboy_state_buffer)
            
            # 3. 恢复AI记忆状态
            logger.info("🧠 正在恢复AI记忆...")
            if "summary_text" in save_data and save_data["summary_text"]:
                self.restore_summary_to_history(save_data["summary_text"])
                logger.info("📝 已恢复摘要格式的AI记忆")
            else:
                self.message_history = save_data["message_history"]
                logger.info("📚 已恢复完整的AI对话历史")
            
            # 4. 恢复步数计数
            self.total_steps = save_data.get("total_steps", 0)
            
            # 5. 成功日志记录
            logger.info(f"✅ 存档加载成功！")
            logger.info(f"   📁 文件: {os.path.basename(filename)} ({file_size:.1f}KB)")
            logger.info(f"   🕐 保存时间: {save_time}")
            logger.info(f"   🎯 累计步数: {self.total_steps}")
            logger.info(f"   🚀 游戏可以继续进行")
            
        except FileNotFoundError:
            logger.error(f"❌ 存档文件不存在: {filename}")
            logger.error("   请检查文件路径是否正确")
            raise
        except Exception as e:
            logger.error(f"❌ 加载存档失败: {e}")
            logger.error("   存档文件可能已损坏，请尝试使用备份存档")
            raise

    def process_tool_call(self, tool_call):
        """Process a single tool call."""
        tool_call_start = time.time()  # 新增：工具调用开始时间
        tool_name = tool_call.name
        tool_input = tool_call.input
        logger.info(f"处理工具调用: {tool_name}")

        if tool_name == "press_buttons":
            buttons = tool_input["buttons"]
            wait = tool_input.get("wait", True)
            logger.info(f"[按钮] 按下: {buttons} (等待={wait})")
            
            # 按钮操作计时
            button_start = time.time()  # 新增
            result = self.emulator.press_buttons(buttons, wait)
            button_time = time.time() - button_start  # 新增
            
            # 截图处理计时
            screenshot_start = time.time()  # 新增
            screenshot = self.emulator.get_screenshot()
            screenshot_b64 = get_screenshot_base64(screenshot, upscale=2)
            screenshot_time = time.time() - screenshot_start  # 新增
            
            # 内存读取计时
            memory_start = time.time()  # 新增
            memory_info = self.emulator.get_state_from_memory()
            memory_time = time.time() - memory_start  # 新增
            
            # Log the memory state after the tool call
            logger.info(f"[动作后的内存状态]")
            logger.info(memory_info)
            
            # 碰撞地图计时
            collision_start = time.time()  # 新增
            collision_map = self.emulator.get_collision_map()
            collision_time = time.time() - collision_start  # 新增
            if collision_map:
                logger.info(f"[动作后的碰撞地图]\n{collision_map}")
            
            # 新增：工具性能打印
            tool_total = time.time() - tool_call_start
            print(f"🔧 工具执行细分:")
            print(f"   🎮 按钮操作: {button_time:.3f}秒")
            print(f"   📸 截图处理: {screenshot_time:.3f}秒") 
            print(f"   🧠 内存读取: {memory_time:.3f}秒")
            print(f"   🗺️ 碰撞地图: {collision_time:.3f}秒")
            print(f"   ⚡ 工具总计: {tool_total:.3f}秒")
            
            # Return tool result as a dictionary
            return {
                "type": "tool_result",
                "tool_use_id": tool_call.id,
                "content": [
                    {"type": "text", "text": f"按下的按钮: {', '.join(buttons)}"},
                    {"type": "text", "text": "\n这是你按下按钮后的屏幕截图："},
                    {
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": "image/png",
                            "data": screenshot_b64,
                        },
                    },
                    {"type": "text", "text": f"\n你动作后内存中的游戏状态信息:\n{memory_info}"},
                ],
            }
        elif tool_name == "navigate_to":
            row = tool_input["row"]
            col = tool_input["col"]
            logger.info(f"[导航] 正在导航到: ({row}, {col})")
            
            # 导航计算计时
            nav_start = time.time()  # 新增
            status, path = self.emulator.find_path(row, col)
            nav_calc_time = time.time() - nav_start  # 新增
            
            # 路径执行计时
            path_start = time.time()  # 新增
            if path:
                for direction in path:
                    self.emulator.press_buttons([direction], True)
                result = f"导航成功: 跟随路径走了{len(path)}步"
            else:
                result = f"导航失败: {status}"
            path_time = time.time() - path_start  # 新增
            
            # 截图和状态读取计时
            screenshot_start = time.time()  # 新增
            screenshot = self.emulator.get_screenshot()
            screenshot_b64 = get_screenshot_base64(screenshot, upscale=2)
            screenshot_time = time.time() - screenshot_start  # 新增
            
            memory_start = time.time()  # 新增
            memory_info = self.emulator.get_state_from_memory()
            memory_time = time.time() - memory_start  # 新增
            
            # Log the memory state after the tool call
            logger.info(f"[Memory State after action]")
            logger.info(memory_info)
            
            collision_start = time.time()  # 新增
            collision_map = self.emulator.get_collision_map()
            collision_time = time.time() - collision_start  # 新增
            if collision_map:
                logger.info(f"[Collision Map after action]\n{collision_map}")
            
            # 导航工具性能打印
            tool_total = time.time() - tool_call_start
            print(f"🧭 导航工具性能:")
            print(f"   🔍 路径计算: {nav_calc_time:.3f}秒")
            print(f"   🚶 路径执行: {path_time:.3f}秒")
            print(f"   📸 截图处理: {screenshot_time:.3f}秒")
            print(f"   🧠 内存读取: {memory_time:.3f}秒")
            print(f"   🗺️ 碰撞地图: {collision_time:.3f}秒")
            print(f"   ⚡ 导航总耗时: {tool_total:.3f}秒")
            
            # Return tool result as a dictionary
            return {
                "type": "tool_result",
                "tool_use_id": tool_call.id,
                "content": [
                    {"type": "text", "text": f"导航结果: {result}"},
                    {"type": "text", "text": "\n这是导航后的屏幕截图："},
                    {
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": "image/png",
                            "data": screenshot_b64,
                        },
                    },
                    {"type": "text", "text": f"\n你动作后内存中的游戏状态信息:\n{memory_info}"},
                ],
            }
        else:
            logger.error(f"调用了未知工具: {tool_name}")
            return {
                "type": "tool_result",
                "tool_use_id": tool_call.id,
                "content": [
                    {"type": "text", "text": f"错误: 未知工具 '{tool_name}'"}
                ],
            }

    def run(self, num_steps=1):
        """主代理循环 - 集成自动保存功能

        Args:
            num_steps: Number of steps to run for
        """
        logger.info(f"开始代理循环，运行{num_steps}步")

        steps_completed = 0
        current_session_steps = 0
        
        try:
            while self.running and steps_completed < num_steps:
                step_start = time.time()  # 新增：步骤开始时间
                
                # 1. 准备消息阶段
                prep_start = time.time()  # 新增
                messages = copy.deepcopy(self.message_history)

                if len(messages) >= 3:
                    if messages[-1]["role"] == "user" and isinstance(messages[-1]["content"], list) and messages[-1]["content"]:
                        messages[-1]["content"][-1]["cache_control"] = {"type": "ephemeral"}
                    
                    if len(messages) >= 5 and messages[-3]["role"] == "user" and isinstance(messages[-3]["content"], list) and messages[-3]["content"]:
                        messages[-3]["content"][-1]["cache_control"] = {"type": "ephemeral"}
                prep_time = time.time() - prep_start  # 新增

                # 2. API调用阶段
                api_start = time.time()  # 新增
                
                # 保存真实的API请求参数到文件 (仅保存一次)
                real_request_file = "real_api_request.json"
                if not os.path.exists(real_request_file):
                    real_request_data = {
                        "model": MODEL_NAME,
                        "max_tokens": MAX_TOKENS,
                        "system": SYSTEM_PROMPT,
                        "messages": messages,
                        "tools": AVAILABLE_TOOLS,
                        "temperature": TEMPERATURE,
                        "timestamp": datetime.now().isoformat(),
                        "step_number": self.total_steps + 1,
                        "description": "真实游戏运行时的API请求参数"
                    }
                    
                    try:
                        with open(real_request_file, 'w', encoding='utf-8') as f:
                            json.dump(real_request_data, f, ensure_ascii=False, indent=2)
                        logger.info(f"💾 已保存真实API请求参数到: {real_request_file}")
                    except Exception as e:
                        logger.warning(f"⚠️ 保存API请求参数失败: {e}")
                
                response = self.client.messages.create(
                    model=MODEL_NAME,
                    max_tokens=MAX_TOKENS,
                    system=SYSTEM_PROMPT,
                    messages=messages,
                    tools=AVAILABLE_TOOLS,
                    temperature=TEMPERATURE,
                )
                api_time = time.time() - api_start  # 新增

                logger.info(f"响应使用情况: {response.usage}")

                # 3. 响应处理阶段
                process_start = time.time()  # 新增
                # Extract tool calls
                tool_calls = [
                    block for block in response.content if block.type == "tool_use"
                ]

                # Display the model's reasoning
                for block in response.content:
                    if block.type == "text":
                        logger.info(f"[文本] {block.text}")
                    elif block.type == "tool_use":
                        logger.info(f"[工具] 使用工具: {block.name}")
                process_time = time.time() - process_start  # 新增

                # 4. 工具调用阶段
                tool_start = time.time()  # 新增
                if tool_calls:
                    # Add assistant message to history
                    assistant_content = []
                    for block in response.content:
                        if block.type == "text":
                            assistant_content.append({"type": "text", "text": block.text})
                        elif block.type == "tool_use":
                            assistant_content.append({"type": "tool_use", **dict(block)})
                    
                    self.message_history.append(
                        {"role": "assistant", "content": assistant_content}
                    )
                    
                    # Process tool calls and create tool results
                    tool_results = []
                    for tool_call in tool_calls:
                        tool_result = self.process_tool_call(tool_call)
                        tool_results.append(tool_result)
                    
                    # Add tool results to message history
                    self.message_history.append(
                        {"role": "user", "content": tool_results}
                    )

                    # Check if we need to summarize the history
                    if len(self.message_history) >= self.max_history:
                        summary_start = time.time()
                        self.summarize_history()
                        summary_time = time.time() - summary_start
                        print(f"⏱️ 摘要生成耗时: {summary_time:.2f}秒")
                tool_time = time.time() - tool_start  # 新增

                # 5. 保存检查阶段
                save_start = time.time()  # 新增
                # 更新步数计数
                self.total_steps += 1
                current_session_steps += 1
                steps_completed += 1
                
                logger.info(f"🎯 完成第{current_session_steps}/{num_steps}步 (累计第{self.total_steps}步)")

                # 自动保存检查
                if self.auto_save_enabled and current_session_steps % self.save_interval == 0:
                    self.auto_save(self.total_steps)
                save_time = time.time() - save_start  # 新增
                
                # 新增：性能统计打印
                total_time = time.time() - step_start
                print(f"⏱️ 第{current_session_steps}步性能统计:")
                print(f"   📝 消息准备: {prep_time:.3f}秒 ({prep_time/total_time*100:.1f}%)")
                print(f"   🌐 API调用: {api_time:.3f}秒 ({api_time/total_time*100:.1f}%)")
                print(f"   🔄 响应处理: {process_time:.3f}秒 ({process_time/total_time*100:.1f}%)")
                print(f"   🛠️ 工具执行: {tool_time:.3f}秒 ({tool_time/total_time*100:.1f}%)")
                print(f"   💾 保存检查: {save_time:.3f}秒 ({save_time/total_time*100:.1f}%)")
                print(f"   🎯 总耗时: {total_time:.3f}秒")

        except (KeyboardInterrupt, Exception) as e:
            if self.auto_save_enabled:
                self.emergency_save()
            if isinstance(e, KeyboardInterrupt):
                logger.info("⏹️ 收到键盘中断信号，游戏已安全停止")
                self.running = False
            else:
                logger.error(f"❌ 代理循环中出现错误: {e}")
            raise e

        if not self.running:
            self.emulator.stop()

        return steps_completed

    def summarize_history(self):
        """Generate a summary of the conversation history and replace the history with just the summary."""
        logger.info(f"[代理] 正在生成对话摘要...")
        
        # Get a new screenshot for the summary
        screenshot = self.emulator.get_screenshot()
        screenshot_b64 = get_screenshot_base64(screenshot, upscale=2)
        
        # Create messages for the summarization request - pass the entire conversation history
        messages = copy.deepcopy(self.message_history) 
        if len(messages) >= 3:
            if messages[-1]["role"] == "user" and isinstance(messages[-1]["content"], list) and messages[-1]["content"]:
                messages[-1]["content"][-1]["cache_control"] = {"type": "ephemeral"}
            
            if len(messages) >= 5 and messages[-3]["role"] == "user" and isinstance(messages[-3]["content"], list) and messages[-3]["content"]:
                messages[-3]["content"][-1]["cache_control"] = {"type": "ephemeral"}

        messages += [
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": SUMMARY_PROMPT,
                    }
                ],
            }
        ]
        
        # Get summary from Claude
        response = self.client.messages.create(
            model=MODEL_NAME,
            max_tokens=MAX_TOKENS,
            system=SYSTEM_PROMPT,
            messages=messages,
            temperature=TEMPERATURE
        )
        
        # Extract the summary text
        summary_text = " ".join([block.text for block in response.content if block.type == "text"])
        
        logger.info(f"[代理] 游戏进度摘要:")
        logger.info(f"{summary_text}")
        
        # Replace message history with just the summary
        self.message_history = [
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": f"对话历史摘要 (代表之前的 {self.max_history} 条消息): {summary_text}"
                    },
                    {
                        "type": "text",
                        "text": "\n\n当前游戏截图供参考:"
                    },
                    {
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": "image/png",
                            "data": screenshot_b64,
                        },
                    },
                    {
                        "type": "text",
                        "text": "你刚刚被要求总结到目前为止的游戏过程，这就是你在上面看到的摘要。你现在可以通过选择下一个动作来继续游戏。"
                    },
                ]
            }
        ]
        
        logger.info(f"[代理] 消息历史已压缩为摘要。")
        
    def stop(self):
        """Stop the agent."""
        self.running = False
        self.emulator.stop()


if __name__ == "__main__":
    # Get the ROM path relative to this file
    current_dir = os.path.dirname(os.path.abspath(__file__))
    rom_path = os.path.join(os.path.dirname(current_dir), "pokemon.gb")

    # Create and run agent
    agent = SimpleAgent(rom_path)

    try:
        steps_completed = agent.run(num_steps=10)
        logger.info(f"Agent completed {steps_completed} steps")
    except KeyboardInterrupt:
        logger.info("Received keyboard interrupt, stopping")
    finally:
        agent.stop()
