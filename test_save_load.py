#!/usr/bin/env python3
"""
宝可梦红版AI代理 - 保存/加载功能测试脚本
"""

import os
import sys
import logging
import time
from agent.simple_agent import SimpleAgent

# 设置日志
logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger(__name__)

def test_auto_save():
    """测试自动保存功能"""
    logger.info("=== 测试1: 自动保存功能 ===")
    
    # 获取ROM路径
    rom_path = "pokemon.gb"
    if not os.path.exists(rom_path):
        logger.error(f"ROM文件不存在: {rom_path}")
        return False
    
    # 创建代理，设置每2步保存一次（用于快速测试）
    agent = SimpleAgent(
        rom_path=rom_path,
        headless=True,
        save_interval=2,
        save_dir="./test_saves",
        auto_save_enabled=True
    )
    
    try:
        # 运行5步，应该在第2步和第4步保存
        logger.info("运行5步，测试自动保存...")
        steps_completed = agent.run(num_steps=5)
        logger.info(f"完成了{steps_completed}步")
        
        # 检查是否生成了存档文件
        save_files = []
        if os.path.exists("./test_saves"):
            for filename in os.listdir("./test_saves"):
                if filename.startswith("pokemon_save_step") and filename.endswith(".pkl"):
                    save_files.append(filename)
        
        logger.info(f"生成的存档文件: {save_files}")
        
        if len(save_files) >= 1:
            logger.info("✅ 自动保存测试通过")
            return True
        else:
            logger.error("❌ 自动保存测试失败：没有生成存档文件")
            return False
            
    except Exception as e:
        logger.error(f"❌ 自动保存测试失败: {e}")
        return False
    finally:
        agent.stop()

def test_load_save():
    """测试加载存档功能"""
    logger.info("=== 测试2: 加载存档功能 ===")
    
    rom_path = "pokemon.gb"
    if not os.path.exists(rom_path):
        logger.error(f"ROM文件不存在: {rom_path}")
        return False
    
    # 查找最新的存档文件
    agent = SimpleAgent(
        rom_path=rom_path,
        headless=True,
        save_dir="./test_saves"
    )
    
    try:
        latest_save_path, latest_steps = agent.find_latest_save()
        
        if not latest_save_path:
            logger.error("❌ 没有找到存档文件进行加载测试")
            return False
        
        logger.info(f"找到最新存档: {latest_save_path} (第{latest_steps}步)")
        
        # 测试加载
        agent.load_complete_state(latest_save_path)
        logger.info(f"成功加载存档，当前累计步数: {agent.total_steps}")
        
        if agent.total_steps == latest_steps:
            logger.info("✅ 加载存档测试通过")
            return True
        else:
            logger.error(f"❌ 加载存档测试失败：步数不匹配 (期望{latest_steps}，实际{agent.total_steps})")
            return False
            
    except Exception as e:
        logger.error(f"❌ 加载存档测试失败: {e}")
        return False
    finally:
        agent.stop()

def test_emergency_save():
    """测试紧急保存功能"""
    logger.info("=== 测试3: 紧急保存功能 ===")
    
    rom_path = "pokemon.gb"
    if not os.path.exists(rom_path):
        logger.error(f"ROM文件不存在: {rom_path}")
        return False
    
    agent = SimpleAgent(
        rom_path=rom_path,
        headless=True,
        save_dir="./test_saves",
        auto_save_enabled=True
    )
    
    try:
        # 运行1步然后模拟异常退出
        agent.run(num_steps=1)
        
        # 记录当前步数
        current_steps = agent.total_steps
        logger.info(f"当前步数: {current_steps}")
        
        # 执行紧急保存
        agent.emergency_save()
        
        # 检查是否生成了紧急存档
        latest_save_path, latest_steps = agent.find_latest_save()
        
        if latest_save_path and latest_steps == current_steps:
            logger.info("✅ 紧急保存测试通过")
            return True
        else:
            logger.error("❌ 紧急保存测试失败")
            return False
            
    except Exception as e:
        logger.error(f"❌ 紧急保存测试失败: {e}")
        return False
    finally:
        agent.stop()

def test_backup_mechanism():
    """测试备份机制"""
    logger.info("=== 测试4: 备份机制测试 ===")
    
    rom_path = "pokemon.gb"
    if not os.path.exists(rom_path):
        logger.error(f"ROM文件不存在: {rom_path}")
        return False
    
    agent = SimpleAgent(
        rom_path=rom_path,
        headless=True,
        save_interval=1,  # 每步都保存
        save_dir="./test_saves",
        auto_save_enabled=True
    )
    
    try:
        # 运行3步，每步都会保存，测试备份机制
        agent.run(num_steps=3)
        
        # 检查存档和备份文件
        save_files = []
        backup_files = []
        
        if os.path.exists("./test_saves"):
            for filename in os.listdir("./test_saves"):
                if filename.startswith("pokemon_save_step") and filename.endswith(".pkl"):
                    if "backup" in filename:
                        backup_files.append(filename)
                    else:
                        save_files.append(filename)
        
        logger.info(f"主存档文件: {save_files}")
        logger.info(f"备份文件: {backup_files}")
        
        # 应该只有一个主存档文件和至少一个备份文件
        if len(save_files) == 1 and len(backup_files) >= 1:
            logger.info("✅ 备份机制测试通过")
            return True
        else:
            logger.error("❌ 备份机制测试失败")
            return False
            
    except Exception as e:
        logger.error(f"❌ 备份机制测试失败: {e}")
        return False
    finally:
        agent.stop()

def cleanup_test_files():
    """清理测试文件"""
    import shutil
    if os.path.exists("./test_saves"):
        shutil.rmtree("./test_saves")
        logger.info("已清理测试文件")

def main():
    """运行所有测试"""
    logger.info("开始保存/加载功能测试")
    
    # 清理之前的测试文件
    cleanup_test_files()
    
    tests = [
        test_auto_save,
        test_load_save,
        test_emergency_save,
        test_backup_mechanism
    ]
    
    passed = 0
    total = len(tests)
    
    for test_func in tests:
        try:
            if test_func():
                passed += 1
            time.sleep(1)  # 测试间隔
        except Exception as e:
            logger.error(f"测试 {test_func.__name__} 出现异常: {e}")
    
    logger.info(f"\n=== 测试结果 ===")
    logger.info(f"通过: {passed}/{total}")
    
    if passed == total:
        logger.info("🎉 所有测试通过！")
        # 保留测试文件供检查
    else:
        logger.error("❌ 部分测试失败")
        # 保留测试文件供调试
    
    return passed == total

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)