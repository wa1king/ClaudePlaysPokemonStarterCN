import argparse
import logging
import os

from agent.simple_agent import SimpleAgent

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler()],
)

logger = logging.getLogger(__name__)

def determine_load_state(args, agent):
    """确定要加载的存档文件"""
    if args.new_game:
        return None, 0
    elif args.load_backup:
        # 查找最新备份
        if not os.path.exists(args.save_dir):
            logger.error("保存目录不存在")
            return None, 0
        
        backup_files = []
        for filename in os.listdir(args.save_dir):
            if filename.startswith("pokemon_save_step") and filename.endswith("_backup.pkl"):
                try:
                    step_str = filename.replace("pokemon_save_step", "").replace("_backup.pkl", "")
                    steps = int(step_str)
                    backup_files.append((steps, filename))
                except ValueError:
                    continue
        
        if backup_files:
            latest_steps, latest_backup = max(backup_files, key=lambda x: x[0])
            backup_path = os.path.join(args.save_dir, latest_backup)
            return backup_path, latest_steps
        else:
            logger.error("没有找到备份存档")
            return None, 0
    else:
        # 默认行为：查找最新的主存档
        latest_save_path, latest_steps = agent.find_latest_save()
        if latest_save_path:
            return latest_save_path, latest_steps
        return None, 0

def show_save_info(agent):
    """显示存档信息"""
    latest_save_path, latest_steps = agent.find_latest_save()
    
    if not latest_save_path:
        print("没有找到存档文件")
        return
    
    print(f"\n=== 存档信息 ===")
    print(f"存档文件: {latest_save_path}")
    print(f"累计步数: {latest_steps}")
    
    try:
        import pickle
        with open(latest_save_path, 'rb') as f:
            save_data = pickle.load(f)
        
        print(f"保存时间: {save_data.get('save_time', '未知')}")
        print(f"版本: {save_data.get('version', '未知')}")
        
        game_info = save_data.get('game_info', '')
        if game_info:
            print(f"游戏状态:\n{game_info}")
        
        # 检查备份文件
        backup_files = []
        if os.path.exists(agent.save_dir):
            for filename in os.listdir(agent.save_dir):
                if filename.startswith("pokemon_save_step") and filename.endswith("_backup.pkl"):
                    backup_files.append(filename)
        
        if backup_files:
            print(f"备份文件数量: {len(backup_files)}")
            print(f"最新备份: {max(backup_files)}")
        else:
            print("没有备份文件")
            
    except Exception as e:
        print(f"读取存档详细信息失败: {e}")

def main():
    parser = argparse.ArgumentParser(description="Claude Plays Pokemon - Starter Version")
    parser.add_argument(
        "--rom", 
        type=str, 
        default="pokemon.gb",
        help="Path to the Pokemon ROM file"
    )
    parser.add_argument(
        "--steps", 
        type=int, 
        default=10, 
        help="Number of agent steps to run"
    )
    parser.add_argument(
        "--display", 
        action="store_true", 
        help="Run with display (not headless)"
    )
    parser.add_argument(
        "--sound", 
        action="store_true", 
        help="Enable sound (only applicable with display)"
    )
    parser.add_argument(
        "--max-history", 
        type=int, 
        default=30, 
        help="Maximum number of messages in history before summarization"
    )
    parser.add_argument(
        "--load-state", 
        type=str, 
        default=None, 
        help="Path to a saved state to load"
    )
    parser.add_argument(
        "--save-every", 
        type=int, 
        default=10, 
        help="每N步保存（默认10）"
    )
    parser.add_argument(
        "--save-dir", 
        type=str, 
        default="./saves", 
        help="保存目录（默认./saves）"
    )
    parser.add_argument(
        "--no-auto-save", 
        action="store_true", 
        help="禁用自动保存"
    )
    parser.add_argument(
        "--new-game", 
        action="store_true", 
        help="强制从头开始新游戏"
    )
    parser.add_argument(
        "--load-backup", 
        action="store_true", 
        help="从备份存档恢复"
    )
    parser.add_argument(
        "--save-info", 
        action="store_true", 
        help="显示当前存档信息"
    )
    
    args = parser.parse_args()
    
    # Get absolute path to ROM
    if not os.path.isabs(args.rom):
        rom_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), args.rom)
    else:
        rom_path = args.rom
    
    # 处理save-info命令
    if args.save_info:
        agent = SimpleAgent(
            rom_path=rom_path,
            headless=True,
            save_dir=args.save_dir
        )
        show_save_info(agent)
        agent.stop()
        return
    
    # Check if ROM exists
    if not os.path.exists(rom_path):
        logger.error(f"ROM文件未找到: {rom_path}")
        print("\n你需要提供宝可梦红版ROM文件来运行此程序。")
        print("将ROM放在根目录中或使用--rom指定其路径。")
        return
    
    # Create agent with new save/load parameters
    agent = SimpleAgent(
        rom_path=rom_path,
        headless=not args.display,
        sound=args.sound if args.display else False,
        max_history=args.max_history,
        load_state=args.load_state,
        save_interval=args.save_every,
        save_dir=args.save_dir,
        auto_save_enabled=not args.no_auto_save
    )
    
    # 确定加载状态（如果没有指定--load-state）
    if not args.load_state:
        load_path, load_steps = determine_load_state(args, agent)
        if load_path:
            logger.info(f"自动从最新存档继续: {load_path} (第{load_steps}步)")
            agent.load_complete_state(load_path)
        elif not args.new_game:
            logger.info("没有找到存档文件，开始新游戏")
    
    try:
        logger.info(f"开始代理，运行{args.steps}步")
        steps_completed = agent.run(num_steps=args.steps)
        logger.info(f"代理完成{steps_completed}步")
    except KeyboardInterrupt:
        logger.info("收到键盘中断，正在停止")
    except Exception as e:
        logger.error(f"运行代理时出错: {e}")
    finally:
        agent.stop()

if __name__ == "__main__":
    main()