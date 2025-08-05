#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
API性能测试工具
用于测试不同Claude模型的响应时间和性能表现
"""

import time
import json
import base64
import io
from datetime import datetime
from anthropic import Anthropic
from PIL import Image, ImageDraw

# 测试配置
TEST_CONFIG = {
    "api_key": "sk-ksbCidPFhLiGTRo_I4fflYASF92UHYC8S1DNHp2kkbTaJkRShC8oOKPIJdI",
    "base_url": "https://chatapi.leyidc.net/claude",
    "models": [
        "claude-3-haiku-20240307",           # 最快的模型
        "claude-3-5-haiku-20241022",         # 新版Haiku
        "claude-3-5-sonnet-20241022",        # 当前使用的模型
        "claude-3-sonnet-20240229",          # 旧版Sonnet
    ],
    "max_tokens_options": [512, 1024, 2048],  # 不同的token限制
    "test_rounds": 3,  # 每个配置测试轮数
}

def create_test_screenshot():
    """创建一个模拟的游戏截图用于测试"""
    # 创建一个160x144的图像（Game Boy分辨率）
    img = Image.new('RGB', (160, 144), color='lightgreen')
    draw = ImageDraw.Draw(img)
    
    # 绘制一些简单的游戏元素
    # 主角
    draw.rectangle([75, 65, 85, 85], fill='red', outline='black')
    
    # 一些建筑物
    draw.rectangle([20, 20, 50, 50], fill='brown', outline='black')
    draw.rectangle([110, 30, 140, 60], fill='blue', outline='black')
    
    # 道路
    draw.rectangle([0, 90, 160, 110], fill='gray')
    
    # 树木
    for x in [30, 60, 100, 130]:
        draw.ellipse([x-5, 70, x+5, 80], fill='green')
    
    # 转换为base64
    buffered = io.BytesIO()
    img.save(buffered, format="PNG")
    return base64.standard_b64encode(buffered.getvalue()).decode()

# 测试用的系统提示
SYSTEM_PROMPT = """你正在玩宝可梦红版。你可以看到游戏画面并通过执行模拟器命令来控制游戏。

你的目标是通关宝可梦红版并最终击败四天王。根据你在屏幕上看到的内容做出决策。

在每个动作之前，简要解释你的推理，然后选择下一个动作。"""

# 测试用的工具定义
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
                    "description": "List of buttons to press in sequence."
                }
            },
            "required": ["buttons"],
        },
    }
]

def create_test_messages():
    """创建测试用的消息历史"""
    screenshot_b64 = create_test_screenshot()
    
    return [
        {
            "role": "user",
            "content": [
                {
                    "type": "text",
                    "text": "你现在可以开始游戏了。这是当前的游戏截图："
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
                    "text": "游戏状态信息:\n位置: 真新镇\n主角: 小智\n宝可梦队伍: 皮卡丘 (Lv.5)\n\n请选择下一个动作。"
                }
            ]
        }
    ]

def test_api_call(client, model, max_tokens, messages, tools):
    """执行单次API调用测试"""
    start_time = time.time()
    
    try:
        response = client.messages.create(
            model=model,
            max_tokens=max_tokens,
            system=SYSTEM_PROMPT,
            messages=messages,
            tools=tools,
            temperature=0.7,
        )
        
        end_time = time.time()
        duration = end_time - start_time
        
        # 提取响应信息
        response_text = ""
        tool_calls = []
        
        for block in response.content:
            if block.type == "text":
                response_text += block.text
            elif block.type == "tool_use":
                tool_calls.append(block.name)
        
        return {
            "success": True,
            "duration": duration,
            "usage": response.usage,
            "response_length": len(response_text),
            "tool_calls": tool_calls,
            "error": None
        }
        
    except Exception as e:
        end_time = time.time()
        duration = end_time - start_time
        
        return {
            "success": False,
            "duration": duration,
            "usage": None,
            "response_length": 0,
            "tool_calls": [],
            "error": str(e)
        }

def run_performance_test():
    """运行完整的性能测试"""
    print("🚀 开始API性能测试")
    print("=" * 60)
    
    # 初始化客户端
    client = Anthropic(
        api_key=TEST_CONFIG["api_key"],
        base_url=TEST_CONFIG["base_url"]
    )
    
    # 准备测试数据
    messages = create_test_messages()
    tools = AVAILABLE_TOOLS
    
    # 存储所有测试结果
    all_results = []
    
    # 遍历所有配置组合
    for model in TEST_CONFIG["models"]:
        for max_tokens in TEST_CONFIG["max_tokens_options"]:
            print(f"\n📊 测试配置: {model} (max_tokens={max_tokens})")
            print("-" * 50)
            
            model_results = []
            
            # 多轮测试
            for round_num in range(TEST_CONFIG["test_rounds"]):
                print(f"   第{round_num + 1}轮测试...", end=" ")
                
                result = test_api_call(client, model, max_tokens, messages, tools)
                model_results.append(result)
                
                if result["success"]:
                    print(f"✅ {result['duration']:.3f}秒")
                else:
                    print(f"❌ 失败: {result['error']}")
                
                # 避免请求过于频繁
                time.sleep(1)
            
            # 计算统计信息
            successful_results = [r for r in model_results if r["success"]]
            
            if successful_results:
                durations = [r["duration"] for r in successful_results]
                avg_duration = sum(durations) / len(durations)
                min_duration = min(durations)
                max_duration = max(durations)
                
                # 计算token使用情况
                if successful_results[0]["usage"]:
                    avg_input_tokens = sum(r["usage"].input_tokens for r in successful_results) / len(successful_results)
                    avg_output_tokens = sum(r["usage"].output_tokens for r in successful_results) / len(successful_results)
                else:
                    avg_input_tokens = 0
                    avg_output_tokens = 0
                
                print(f"   📈 平均耗时: {avg_duration:.3f}秒")
                print(f"   ⚡ 最快: {min_duration:.3f}秒")
                print(f"   🐌 最慢: {max_duration:.3f}秒")
                print(f"   📝 平均输入tokens: {avg_input_tokens:.0f}")
                print(f"   📤 平均输出tokens: {avg_output_tokens:.0f}")
                print(f"   ✅ 成功率: {len(successful_results)}/{len(model_results)}")
                
                # 保存结果
                all_results.append({
                    "model": model,
                    "max_tokens": max_tokens,
                    "avg_duration": avg_duration,
                    "min_duration": min_duration,
                    "max_duration": max_duration,
                    "success_rate": len(successful_results) / len(model_results),
                    "avg_input_tokens": avg_input_tokens,
                    "avg_output_tokens": avg_output_tokens,
                    "raw_results": model_results
                })
            else:
                print(f"   ❌ 所有测试都失败了")
    
    # 生成性能报告
    generate_performance_report(all_results)
    
    return all_results

def generate_performance_report(results):
    """生成性能测试报告"""
    print("\n" + "=" * 60)
    print("📊 性能测试报告")
    print("=" * 60)
    
    if not results:
        print("❌ 没有成功的测试结果")
        return
    
    # 按平均耗时排序
    results.sort(key=lambda x: x["avg_duration"])
    
    print("\n🏆 性能排行榜 (按平均响应时间排序):")
    print("-" * 60)
    
    for i, result in enumerate(results, 1):
        model_short = result["model"].split("-")[-1] if "-" in result["model"] else result["model"]
        print(f"{i:2d}. {result['model']:<35} "
              f"({result['max_tokens']:4d} tokens) "
              f"{result['avg_duration']:6.3f}秒")
    
    # 找出最佳配置
    best_result = results[0]
    print(f"\n🥇 最佳配置:")
    print(f"   模型: {best_result['model']}")
    print(f"   Max Tokens: {best_result['max_tokens']}")
    print(f"   平均耗时: {best_result['avg_duration']:.3f}秒")
    print(f"   成功率: {best_result['success_rate']*100:.1f}%")
    
    # 速度对比
    if len(results) > 1:
        slowest_result = results[-1]
        speedup = slowest_result["avg_duration"] / best_result["avg_duration"]
        print(f"   相比最慢配置快 {speedup:.1f}x")
    
    # Token效率分析
    print(f"\n📊 Token使用效率:")
    print("-" * 40)
    for result in results[:5]:  # 只显示前5名
        if result["avg_input_tokens"] > 0:
            tokens_per_second = (result["avg_input_tokens"] + result["avg_output_tokens"]) / result["avg_duration"]
            model_short = result["model"].split("-")[-1] if "-" in result["model"] else result["model"]
            print(f"{model_short:15s}: {tokens_per_second:6.0f} tokens/秒")
    
    # 保存详细报告到文件
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    report_file = f"api_performance_report_{timestamp}.json"
    
    with open(report_file, 'w', encoding='utf-8') as f:
        json.dump(results, f, ensure_ascii=False, indent=2, default=str)
    
    print(f"\n💾 详细报告已保存到: {report_file}")

def quick_test(model_name, max_tokens=1024):
    """快速测试单个模型"""
    print(f"🔍 快速测试: {model_name} (max_tokens={max_tokens})")
    
    client = Anthropic(
        api_key=TEST_CONFIG["api_key"],
        base_url=TEST_CONFIG["base_url"]
    )
    
    messages = create_test_messages()
    result = test_api_call(client, model_name, max_tokens, messages, AVAILABLE_TOOLS)
    
    if result["success"]:
        print(f"✅ 成功! 耗时: {result['duration']:.3f}秒")
        if result["usage"]:
            print(f"📊 Token使用: 输入{result['usage'].input_tokens}, 输出{result['usage'].output_tokens}")
        print(f"📝 响应长度: {result['response_length']} 字符")
        if result["tool_calls"]:
            print(f"🛠️ 工具调用: {', '.join(result['tool_calls'])}")
    else:
        print(f"❌ 失败: {result['error']}")
    
    return result

if __name__ == "__main__":
    print("🎮 Claude API性能测试工具")
    print("=" * 40)
    
    # 选择测试模式
    print("请选择测试模式:")
    print("1. 完整性能测试 (测试所有模型和配置)")
    print("2. 快速测试 (测试单个模型)")
    print("3. 推荐配置测试 (只测试推荐的几个配置)")
    
    try:
        choice = input("\n请输入选择 (1-3): ").strip()
        
        if choice == "1":
            # 完整测试
            results = run_performance_test()
            
        elif choice == "2":
            # 快速测试
            print("\n可用模型:")
            for i, model in enumerate(TEST_CONFIG["models"], 1):
                print(f"{i}. {model}")
            
            model_choice = input(f"\n请选择模型 (1-{len(TEST_CONFIG['models'])}): ").strip()
            try:
                model_index = int(model_choice) - 1
                if 0 <= model_index < len(TEST_CONFIG["models"]):
                    model = TEST_CONFIG["models"][model_index]
                    quick_test(model)
                else:
                    print("❌ 无效选择")
            except ValueError:
                print("❌ 请输入数字")
                
        elif choice == "3":
            # 推荐配置测试
            recommended_configs = [
                ("claude-3-haiku-20240307", 1024),
                ("claude-3-5-haiku-20241022", 1024),
                ("claude-3-5-sonnet-20241022", 1024),
            ]
            
            print("\n🎯 测试推荐配置...")
            for model, max_tokens in recommended_configs:
                print(f"\n测试 {model}...")
                quick_test(model, max_tokens)
                time.sleep(1)  # 避免请求过于频繁
                
        else:
            print("❌ 无效选择")
            
    except KeyboardInterrupt:
        print("\n\n⏹️ 测试被用户中断")
    except Exception as e:
        print(f"\n❌ 测试过程中出现错误: {e}")
    
    print("\n🏁 测试完成!")