# 宝可梦红版AI代理 - 保存/加载功能开发任务列表

## 任务概述

根据《保存加载功能需求文档.md》，将保存/加载功能的开发分解为多个可独立完成的任务，按优先级和依赖关系排序。

## 任务分类

### Phase 1: 核心基础功能 (必须完成)
### Phase 2: 集成和测试 (必须完成)  
### Phase 3: 命令行和用户体验 (可选优化)

---

## Phase 1: 核心基础功能

### Task 1.1: 配置文件更新
**状态**: ✅ 已完成  
**文件**: `config.py`  
**依赖**: 无

**任务内容**:
```python
# 在config.py中添加以下配置项
AUTO_SAVE_ENABLED = True
SAVE_INTERVAL_STEPS = 10
SAVE_DIRECTORY = "./saves"
```

**验收标准**:
- [ ] 配置项正确添加到config.py
- [ ] 配置项有合理的默认值
- [ ] 不影响现有配置

---

### Task 1.2: SimpleAgent初始化扩展
**状态**: ✅ 已完成
**文件**: `agent/simple_agent.py`
**优先级**: 高
**预计时间**: 20分钟
**依赖**: Task 1.1

**任务内容**:
1. 修改`__init__`方法，添加保存相关参数
2. 初始化保存相关属性

**具体修改**:
```python
def __init__(self, rom_path, headless=True, sound=False, max_history=60, 
             load_state=None, save_interval=10, save_dir="./saves", auto_save_enabled=True):
    # 现有代码保持不变
    # 在末尾添加:
    self.save_interval = save_interval
    self.save_dir = save_dir
    self.auto_save_enabled = auto_save_enabled
    self.total_steps = 0  # 累计总步数计数器
    
    # 确保保存目录存在
    os.makedirs(self.save_dir, exist_ok=True)
```

**验收标准**:
- [ ] 新参数正确添加到__init__方法
- [ ] 保存相关属性正确初始化
- [ ] total_steps计数器初始化为0
- [ ] 保存目录自动创建
- [ ] 不影响现有功能

---

### Task 1.3: 文件名管理方法
**状态**: ✅ 已完成
**文件**: `agent/simple_agent.py`
**优先级**: 高
**预计时间**: 30分钟
**依赖**: Task 1.2

**任务内容**:
实现文件名生成和查找相关方法

**需要实现的方法**:
```python
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
```

**验收标准**:
- [ ] 文件名格式正确: `pokemon_save_step{步数:04d}.pkl`
- [ ] 备份文件名格式正确: `pokemon_save_step{步数:04d}_backup.pkl`
- [ ] find_latest_save能正确找到最新存档
- [ ] 处理目录不存在的情况
- [ ] 处理文件名解析错误的情况

---

### Task 1.4: 记忆备份方法
**状态**: ✅ 已完成  
**文件**: `agent/simple_agent.py`  
**依赖**: Task 1.3

**任务内容**:
实现记忆提取和恢复方法

**需要实现的方法**:
```python
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
```

**验收标准**:
- [ ] extract_current_summary能正确提取摘要文本
- [ ] 处理没有摘要的情况（返回None）
- [ ] restore_summary_to_history重建的格式与summarize_history一致
- [ ] 包含当前游戏截图
- [ ] 消息结构正确

---

### Task 1.5: 核心保存方法
**状态**: ✅ 已完成  
**文件**: `agent/simple_agent.py`  
**依赖**: Task 1.4

**任务内容**:
实现核心的保存功能

**需要实现的方法**:
```python
def save_with_backup(self, save_data, total_steps):
    """安全保存策略：备份旧存档，保存新存档"""
    # 查找并备份旧存档
    old_save_path, old_steps = self.find_latest_save()
    if old_save_path and os.path.exists(old_save_path):
        backup_path = self.get_backup_filename(old_steps)
        shutil.move(old_save_path, backup_path)
        logger.info(f"旧存档已备份到: {backup_path}")
    
    # 保存新存档
    new_save_path = self.get_save_filename(total_steps)
    with open(new_save_path, 'wb') as f:
        pickle.dump(save_data, f)
    
    logger.info(f"新存档已保存到: {new_save_path}")

def auto_save(self, total_steps):
    """自动保存方法"""
    logger.info(f"[自动保存] 正在保存第{total_steps}步的进度...")
    
    save_data = {
        "pyboy_state": self.emulator.pyboy.save_state(),
        "message_history": self.message_history,
        "summary_text": self.extract_current_summary(),
        "total_steps": total_steps,
        "save_time": datetime.now().isoformat(),
        "game_info": self.emulator.get_state_from_memory(),
        "version": "1.0"
    }
    
    try:
        self.save_with_backup(save_data, total_steps)
        logger.info(f"[自动保存] 成功保存到第{total_steps}步")
    except Exception as e:
        logger.error(f"[自动保存] 保存失败: {e}")

def emergency_save(self):
    """紧急保存方法"""
    logger.info("执行紧急保存...")
    
    save_data = {
        "pyboy_state": self.emulator.pyboy.save_state(),
        "message_history": self.message_history,
        "summary_text": self.extract_current_summary(),
        "total_steps": self.total_steps,
        "save_time": datetime.now().isoformat(),
        "game_info": self.emulator.get_state_from_memory(),
        "version": "1.0"
    }
    
    try:
        self.save_with_backup(save_data, self.total_steps)
        logger.info("紧急保存完成")
    except Exception as e:
        logger.error(f"紧急保存失败: {e}")
```

**验收标准**:
- [ ] save_data包含所有必要字段
- [ ] 旧存档正确备份
- [ ] 新存档正确保存
- [ ] 错误处理完善
- [ ] 日志记录详细
- [ ] 紧急保存与正常保存格式一致

---

### Task 1.6: 核心加载方法
**状态**: ✅ 已完成  
**文件**: `agent/simple_agent.py`  
**依赖**: Task 1.5

**任务内容**:
实现核心的加载功能

**需要实现的方法**:
```python
def load_complete_state(self, filename):
    """加载完整的游戏和AI状态"""
    logger.info(f"正在加载存档: {filename}")
    
    # 1. 读取保存文件
    with open(filename, 'rb') as f:
        save_data = pickle.load(f)
    
    # 2. 恢复游戏状态
    self.emulator.pyboy.load_state(save_data["pyboy_state"])
    
    # 3. 恢复AI记忆状态
    if "summary_text" in save_data and save_data["summary_text"]:
        self.restore_summary_to_history(save_data["summary_text"])
    else:
        self.message_history = save_data["message_history"]
    
    # 4. 恢复步数计数
    self.total_steps = save_data.get("total_steps", 0)
    
    # 5. 日志记录
    logger.info(f"已加载保存点: {filename} (第{self.total_steps}步)")
```

**验收标准**:
- [ ] 正确读取存档文件
- [ ] 游戏状态正确恢复
- [ ] AI记忆状态正确恢复
- [ ] 优先使用summary_text
- [ ] 步数计数正确恢复
- [ ] 错误处理（文件不存在、格式错误等）

---

### Task 1.7: 修改run方法集成保存功能
**状态**: ✅ 已完成  
**文件**: `agent/simple_agent.py`  
**依赖**: Task 1.6

**任务内容**:
修改现有的run方法，集成自动保存和异常处理

**修改内容**:
```python
def run(self, num_steps=1):
    """主代理循环 - 集成自动保存功能"""
    logger.info(f"开始代理循环，运行{num_steps}步")

    steps_completed = 0
    current_session_steps = 0
    
    try:
        while self.running and steps_completed < num_steps:
            # 现有的游戏循环逻辑保持不变
            # ... 现有代码 ...
            
            # 更新步数计数
            self.total_steps += 1
            current_session_steps += 1
            steps_completed += 1
            
            logger.info(f"完成第{current_session_steps}/{num_steps}步 (累计第{self.total_steps}步)")

            # 自动保存检查
            if self.auto_save_enabled and current_session_steps % self.save_interval == 0:
                self.auto_save(self.total_steps)

    except (KeyboardInterrupt, Exception) as e:
        logger.info("检测到异常退出，正在保存紧急存档...")
        if self.auto_save_enabled:
            self.emergency_save()
        raise e

    if not self.running:
        self.emulator.stop()

    return steps_completed
```

**验收标准**:
- [ ] 现有游戏逻辑不受影响
- [ ] 步数计数正确（区分累计步数和当前会话步数）
- [ ] 自动保存在正确时机触发
- [ ] 异常退出时执行紧急保存
- [ ] 日志信息清晰

---

## Phase 2: 集成和测试

### Task 2.1: 扩展现有load_state逻辑
**状态**: ✅ 已完成  
**文件**: `agent/simple_agent.py`  
**依赖**: Task 1.7

**任务内容**:
修改现有的load_state参数处理，支持新的存档格式

**修改内容**:
```python
def __init__(self, rom_path, headless=True, sound=False, max_history=60, load_state=None, ...):
    # 现有初始化代码
    # ...
    
    # 处理load_state参数
    if load_state:
        logger.info(f"从 {load_state} 加载保存的状态")
        if load_state.endswith('.pkl'):
            # 新格式：完整状态文件
            self.load_complete_state(load_state)
        else:
            # 旧格式：只有游戏状态
            self.emulator.load_state(load_state)
```

**验收标准**:
- [ ] 支持新的.pkl格式存档
- [ ] 保持对旧格式的兼容性
- [ ] 正确区分文件格式
- [ ] 错误处理完善

---

### Task 2.2: 基础功能测试
**状态**: ✅ 已完成  
**文件**: 创建测试脚本或手动测试  
**依赖**: Task 2.1

**任务内容**:
测试核心保存/加载功能

**测试用例**:
1. **自动保存测试**:
   - 运行10步，检查是否生成存档文件
   - 检查存档文件名格式是否正确
   - 检查存档内容是否完整

2. **加载测试**:
   - 从存档加载，检查游戏状态是否正确恢复
   - 检查AI记忆是否正确恢复
   - 检查步数计数是否正确

3. **异常退出测试**:
   - 模拟Ctrl+C中断，检查是否生成紧急存档
   - 检查紧急存档是否可以正常加载

4. **备份机制测试**:
   - 多次保存，检查旧存档是否正确备份
   - 检查只保留一个主存档和一个备份

**验收标准**:
- [ ] 所有测试用例通过
- [ ] 存档文件格式正确
- [ ] 加载后游戏可以正常继续
- [ ] AI记忆连续性保持
- [ ] 异常处理正常工作

---

## Phase 3: 命令行和用户体验

### Task 3.1: 命令行参数扩展
**状态**: ✅ 已完成  
**文件**: `main.py`  
**依赖**: Task 2.2

**任务内容**:
添加新的命令行参数支持

**需要添加的参数**:
```python
parser.add_argument('--save-every', type=int, default=10, help='每N步保存（默认10）')
parser.add_argument('--save-dir', type=str, default='./saves', help='保存目录（默认./saves）')
parser.add_argument('--no-auto-save', action='store_true', help='禁用自动保存')
parser.add_argument('--new-game', action='store_true', help='强制从头开始新游戏')
parser.add_argument('--load-backup', action='store_true', help='从备份存档恢复')
parser.add_argument('--save-info', action='store_true', help='显示当前存档信息')
```

**验收标准**:
- [ ] 所有参数正确添加
- [ ] 参数帮助信息清晰
- [ ] 参数默认值合理
- [ ] 与现有参数不冲突

---

### Task 3.2: 默认加载逻辑实现
**状态**: ✅ 已完成  
**文件**: `main.py`  
**依赖**: Task 3.1

**任务内容**:
实现智能的默认加载逻辑

**需要实现的函数**:
```python
def determine_load_state(args, agent):
    """确定要加载的存档文件"""
    if args.new_game:
        return None, 0
    elif args.load_backup:
        # 查找最新备份
        # ... 实现逻辑
    else:
        # 默认查找最新存档
        latest_save_path, latest_steps = agent.find_latest_save()
        if latest_save_path:
            return latest_save_path, latest_steps
        return None, 0

def show_save_info(agent):
    """显示存档信息"""
    # ... 实现逻辑
```

**验收标准**:
- [ ] 默认行为：自动从最新存档继续
- [ ] --new-game强制新游戏
- [ ] --load-backup从备份恢复
- [ ] --save-info显示详细信息
- [ ] 错误处理完善

---

### Task 3.3: main.py集成
**状态**: ✅ 已完成  
**文件**: `main.py`  
**依赖**: Task 3.2

**任务内容**:
将新功能集成到main.py的主流程中

**修改内容**:
```python
def main():
    args = parser.parse_args()
    
    # 处理save-info命令
    if args.save_info:
        agent = SimpleAgent(rom_path, save_dir=args.save_dir)
        show_save_info(agent)
        return
    
    # 确定加载状态
    agent = SimpleAgent(
        rom_path, 
        headless=args.headless,
        save_interval=args.save_every,
        save_dir=args.save_dir,
        auto_save_enabled=not args.no_auto_save
    )
    
    load_path, load_steps = determine_load_state(args, agent)
    if load_path:
        agent.load_complete_state(load_path)
    
    # 运行游戏
    agent.run(num_steps=args.steps)
```

**验收标准**:
- [ ] 命令行参数正确传递给SimpleAgent
- [ ] 加载逻辑正确执行
- [ ] save-info命令正常工作
- [ ] 保持现有功能不受影响

---

### Task 3.4: 用户体验优化
**状态**: ✅ 已完成  
**文件**: `agent/simple_agent.py`, `main.py`  
**依赖**: Task 3.3

**任务内容**:
优化用户体验和日志输出

**优化内容**:
1. 改进日志信息的可读性
2. 添加保存/加载进度提示
3. 优化错误信息显示
4. 添加存档信息的详细显示

**验收标准**:
- [ ] 日志信息清晰易懂
- [ ] 保存/加载过程有明确提示
- [ ] 错误信息有助于问题诊断
- [ ] 存档信息显示完整

---

## 最终验收

### 完整功能测试
**状态**: ✅ 已完成  
**依赖**: 所有前置任务

**测试场景**:
1. **默认使用场景**:
   ```bash
   python main.py --steps 50
   # 应该自动从最新存档继续，每10步保存
   ```

2. **新游戏场景**:
   ```bash
   python main.py --steps 30 --new-game
   # 应该强制从头开始，忽略现有存档
   ```

3. **自定义保存场景**:
   ```bash
   python main.py --steps 100 --save-every 5 --save-dir "./my_saves"
   # 应该每5步保存到指定目录
   ```

4. **备份恢复场景**:
   ```bash
   python main.py --load-backup --steps 20
   # 应该从备份存档恢复
   ```

5. **存档信息查看**:
   ```bash
   python main.py --save-info
   # 应该显示当前存档的详细信息
   ```

**最终验收标准**:
- [ ] 所有使用场景正常工作
- [ ] AI记忆连续性保持
- [ ] 异常退出保护正常
- [ ] 文件管理策略正确
- [ ] 用户体验良好

---

## 任务执行建议

### 执行顺序
1. **严格按Phase顺序执行**：Phase 1 → Phase 2 → Phase 3
2. **Phase内按Task编号顺序执行**：Task 1.1 → Task 1.2 → ...
3. **每个Task完成后进行简单验证**，确保功能正常再进行下一个

### 执行阶段
- **Phase 1**: 核心基础功能（必须完成）
- **Phase 2**: 集成和测试（必须完成）
- **Phase 3**: 命令行和用户体验（可选优化）

### 风险控制
- **每个Task都有明确的验收标准**
- **优先完成Phase 1和Phase 2**，确保核心功能可用
- **Phase 3可以根据时间情况选择性实现**
- **遇到问题时可以回退到上一个稳定状态**

---

**文档版本**: v1.0  
**创建时间**: 2024年1月15日  
**任务总数**: 14个主要任务

## 状态说明
- ✅ 已完成
- 🔄 进行中  
- ⏳ 待完成
