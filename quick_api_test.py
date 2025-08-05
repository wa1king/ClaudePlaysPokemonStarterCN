#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
快速API测试脚本
使用从真实游戏运行中保存的API请求参数进行测试
"""

import time
import json
import os
from datetime import datetime
from api_test_config import *
from anthropic import Anthropic

try:
    import openai
    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False
    print("⚠️  OpenAI模块未安装，将跳过非Claude模型的测试")

def get_api_client(model_name):
    """根据模型名称获取对应的API客户端"""
    if model_name.startswith("claude"):
        return Anthropic(
            api_key=API_CONFIG["api_key"],
            base_url=API_CONFIG["base_url"]
        ), "anthropic"
    elif not OPENAI_AVAILABLE:
        raise Exception(f"模型 {model_name} 需要OpenAI模块，但未安装。请运行: pip install openai")
    elif model_name.startswith("gpt") or model_name.startswith("o1"):
        return openai.OpenAI(
            api_key=API_CONFIG.get("openai_api_key", API_CONFIG["api_key"]),
            base_url=API_CONFIG.get("openai_base_url", "https://api.openai.com/v1")
        ), "openai"
    elif model_name.startswith("gemini"):
        # 对于Gemini，我们假设使用OpenAI兼容的接口
        return openai.OpenAI(
            api_key=API_CONFIG.get("gemini_api_key", API_CONFIG["api_key"]),
            base_url=API_CONFIG.get("gemini_base_url", API_CONFIG["base_url"])
        ), "openai"
    else:
        # 默认使用OpenAI兼容接口
        return openai.OpenAI(
            api_key=API_CONFIG["api_key"],
            base_url=API_CONFIG["base_url"]
        ), "openai"

def load_real_api_request():
    """加载真实的API请求参数"""
    real_request_file = "real_api_request.json"
    
    if not os.path.exists(real_request_file):
        print(f"❌ 未找到真实API请求文件: {real_request_file}")
        print("💡 请先运行游戏代理至少一步，以生成真实的API请求参数")
        return None
    
    try:
        with open(real_request_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        print(f"✅ 已加载真实API请求参数")
        print(f"   📅 生成时间: {data.get('timestamp', '未知')}")
        print(f"   🎯 游戏步数: {data.get('step_number', '未知')}")
        print(f"   📝 消息数量: {len(data.get('messages', []))}")
        
        return data
    except Exception as e:
        print(f"❌ 加载真实API请求参数失败: {e}")
        return None

def test_api_call_with_real_data(client, client_type, model_name, max_tokens, real_request_data):
    """使用真实数据进行API调用测试"""
    try:
        start_time = time.time()
        
        if client_type == "anthropic":
            # Anthropic API调用
            response = client.messages.create(
                model=model_name,
                max_tokens=max_tokens,
                system=real_request_data["system"],
                messages=real_request_data["messages"],
                tools=real_request_data["tools"],
                temperature=real_request_data["temperature"],
            )
            
            # 提取Anthropic回答内容
            response_text = ""
            tool_calls = []
            
            for block in response.content:
                if block.type == "text":
                    response_text += block.text
                elif block.type == "tool_use":
                    tool_calls.append({
                        "name": block.name,
                        "input": block.input
                    })
            
            usage = response.usage
            
        else:
            # OpenAI兼容API调用（包括Gemini）
            try:
                # 转换消息格式
                openai_messages = []
                if real_request_data.get("system"):
                    openai_messages.append({"role": "system", "content": real_request_data["system"]})
                
                for msg in real_request_data["messages"]:
                    if msg["role"] == "user":
                        content = ""
                        if isinstance(msg["content"], list):
                            for item in msg["content"]:
                                if item["type"] == "text":
                                    content += item["text"] + "\n"
                                elif item["type"] == "image":
                                    content += "[图片内容]\n"
                        else:
                            content = msg["content"]
                        openai_messages.append({"role": "user", "content": content})
                    else:
                        openai_messages.append(msg)
                
                # 转换工具格式
                openai_tools = []
                for tool in real_request_data.get("tools", []):
                    openai_tools.append({
                        "type": "function",
                        "function": {
                            "name": tool["name"],
                            "description": tool.get("description", ""),
                            "parameters": tool.get("input_schema", {})
                        }
                    })
                
                response = client.chat.completions.create(
                    model=model_name,
                    max_tokens=max_tokens,
                    messages=openai_messages,
                    tools=openai_tools if openai_tools else None,
                    temperature=real_request_data["temperature"],
                )
                
                # 提取OpenAI回答内容
                response_text = response.choices[0].message.content or ""
                tool_calls = []
                
                if response.choices[0].message.tool_calls:
                    for tool_call in response.choices[0].message.tool_calls:
                        tool_calls.append({
                            "name": tool_call.function.name,
                            "input": json.loads(tool_call.function.arguments)
                        })
                
                usage = response.usage
                
            except Exception as openai_error:
                # 如果OpenAI格式失败，尝试简化的调用
                print(f"   ⚠️  OpenAI格式调用失败，尝试简化调用: {str(openai_error)[:100]}")
                
                # 简化的消息格式
                simple_message = "请分析当前游戏截图并选择下一步行动。"
                if real_request_data.get("messages"):
                    for msg in real_request_data["messages"]:
                        if msg["role"] == "user" and isinstance(msg["content"], list):
                            for item in msg["content"]:
                                if item["type"] == "text":
                                    simple_message = item["text"][:500]
                                    break
                            break
                
                response = client.chat.completions.create(
                    model=model_name,
                    max_tokens=max_tokens,
                    messages=[{"role": "user", "content": simple_message}],
                    temperature=0.7,
                )
                
                response_text = response.choices[0].message.content or ""
                tool_calls = []
                usage = response.usage
        
        duration = time.time() - start_time
        
        return {
            "success": True,
            "duration": duration,
            "usage": usage,
            "response_text": response_text,
            "tool_calls": tool_calls,
            "response_length": len(response_text),
            "error": None
        }
        
    except Exception as e:
        return {
            "success": False,
            "duration": 0,
            "usage": None,
            "response_text": "",
            "tool_calls": [],
            "response_length": 0,
            "error": str(e)
        }

def run_quick_comparison_with_real_data():
    """使用真实数据运行快速对比测试"""
    print("⚡ 基于真实游戏数据的API性能对比测试")
    print("=" * 60)
    
    # 加载真实API请求数据
    real_request_data = load_real_api_request()
    if not real_request_data:
        return []
    
    results = []
    
    for config in QUICK_TEST_CONFIGS:
        print(f"\n🧪 测试 {config['name']}")
        print(f"   模型: {config['model']}")
        print(f"   Max Tokens: {config['max_tokens']}")
        print(f"   说明: {config['description']}")
        print("   " + "-" * 40)
        
        # 获取对应的API客户端
        try:
            client, client_type = get_api_client(config["model"])
        except Exception as e:
            print(f"   ❌ 无法创建API客户端: {e}")
            continue
        
        # 执行测试
        total_time = 0
        successful_tests = 0
        total_input_tokens = 0
        total_output_tokens = 0
        response_texts = []
        tool_calls_list = []
        
        for i in range(TEST_SETTINGS["test_rounds"]):
            print(f"   第{i+1}轮: ", end="")
            
            result = test_api_call_with_real_data(
                client, 
                client_type,
                config["model"], 
                config["max_tokens"], 
                real_request_data
            )
            
            if result["success"]:
                print(f"✅ {result['duration']:.3f}秒", end="")
                if result["usage"]:
                    input_tokens = getattr(result["usage"], 'input_tokens', getattr(result["usage"], 'prompt_tokens', 0))
                    output_tokens = getattr(result["usage"], 'output_tokens', getattr(result["usage"], 'completion_tokens', 0))
                    print(f" (输入:{input_tokens}, 输出:{output_tokens})")
                    total_input_tokens += input_tokens
                    total_output_tokens += output_tokens
                else:
                    print()
                
                # 保存回答内容用于显示
                response_texts.append(result["response_text"])
                tool_calls_list.append(result["tool_calls"])
                
                total_time += result['duration']
                successful_tests += 1
            else:
                print(f"❌ 失败: {result['error']}")
            
            time.sleep(TEST_SETTINGS["request_delay"])
        
        # 显示模型回答内容
        if response_texts and successful_tests > 0:
            print(f"\n   💭 模型回答示例:")
            sample_text = response_texts[0]
            if sample_text.strip():
                # 显示前200字符
                preview = sample_text[:200] + "..." if len(sample_text) > 200 else sample_text
                print(f"      {preview}")
            else:
                print(f"      [无文本回答]")
            
            if tool_calls_list and tool_calls_list[0]:
                print(f"   🔧 工具调用:")
                for tool_call in tool_calls_list[0]:
                    print(f"      - {tool_call['name']}: {tool_call['input']}")
            else:
                print(f"   🔧 工具调用: [无工具调用]")
        
        # 计算平均性能
        if successful_tests > 0:
            avg_time = total_time / successful_tests
            avg_input_tokens = total_input_tokens / successful_tests if successful_tests > 0 else 0
            avg_output_tokens = total_output_tokens / successful_tests if successful_tests > 0 else 0
            
            # 性能评级
            if avg_time <= PERFORMANCE_BENCHMARKS["excellent"]:
                grade = "🏆 优秀"
            elif avg_time <= PERFORMANCE_BENCHMARKS["good"]:
                grade = "🥈 良好"
            elif avg_time <= PERFORMANCE_BENCHMARKS["acceptable"]:
                grade = "🥉 可接受"
            else:
                grade = "🐌 较慢"
            
            print(f"   📊 平均耗时: {avg_time:.3f}秒 {grade}")
            print(f"   🔢 平均Token: 输入{avg_input_tokens:.0f}, 输出{avg_output_tokens:.0f}")
            
            results.append({
                "name": config["name"],
                "model": config["model"],
                "max_tokens": config["max_tokens"],
                "avg_time": avg_time,
                "avg_input_tokens": avg_input_tokens,
                "avg_output_tokens": avg_output_tokens,
                "success_rate": successful_tests / TEST_SETTINGS["test_rounds"],
                "grade": grade
            })
        else:
            print(f"   ❌ 所有测试失败")
    
    # 生成对比报告
    print("\n" + "=" * 60)
    print("📊 基于真实数据的性能对比结果")
    print("=" * 60)
    
    if results:
        # 按性能排序
        results.sort(key=lambda x: x["avg_time"])
        
        print(f"\n🏆 性能排行:")
        for i, result in enumerate(results, 1):
            efficiency = result["avg_output_tokens"] / result["avg_time"] if result["avg_time"] > 0 else 0
            print(f"{i}. {result['name']:<15} {result['avg_time']:6.3f}秒 {result['grade']} (效率:{efficiency:.1f} tokens/s)")
        
        # 推荐配置
        best = results[0]
        print(f"\n💡 最快配置: {best['name']}")
        print(f"   模型: {best['model']}")
        print(f"   Max Tokens: {best['max_tokens']}")
        print(f"   平均耗时: {best['avg_time']:.3f}秒")
        print(f"   Token效率: {best['avg_output_tokens']/best['avg_time']:.1f} tokens/s")
        
        # 显示真实数据统计
        print(f"\n📈 真实数据统计:")
        print(f"   原始模型: {real_request_data.get('model', '未知')}")
        print(f"   原始Max Tokens: {real_request_data.get('max_tokens', '未知')}")
        print(f"   消息历史长度: {len(real_request_data.get('messages', []))}")
        print(f"   可用工具数量: {len(real_request_data.get('tools', []))}")
        
        # 计算成本效益
        print(f"\n💰 成本效益分析 (基于平均token使用):")
        for result in results[:3]:  # 只显示前3名
            print(f"   {result['name']}: 输入{result['avg_input_tokens']:.0f} + 输出{result['avg_output_tokens']:.0f} tokens")
    
    return results

def test_single_model_with_real_data(model_name, max_tokens=1024, rounds=3):
    """使用真实数据测试单个模型"""
    print(f"🔍 基于真实数据的单模型测试: {model_name}")
    print(f"Max Tokens: {max_tokens}, 测试轮数: {rounds}")
    print("-" * 50)
    
    # 加载真实API请求数据
    real_request_data = load_real_api_request()
    if not real_request_data:
        return None
    
    # 获取对应的API客户端
    try:
        client, client_type = get_api_client(model_name)
    except Exception as e:
        print(f"❌ 无法创建API客户端: {e}")
        return None
    
    times = []
    token_stats = []
    response_examples = []
    
    for i in range(rounds):
        print(f"第{i+1}轮: ", end="")
        
        result = test_api_call_with_real_data(client, client_type, model_name, max_tokens, real_request_data)
        
        if result["success"]:
            times.append(result["duration"])
            print(f"✅ {result['duration']:.3f}秒", end="")
            
            if result["usage"]:
                input_tokens = getattr(result["usage"], 'input_tokens', getattr(result["usage"], 'prompt_tokens', 0))
                output_tokens = getattr(result["usage"], 'output_tokens', getattr(result["usage"], 'completion_tokens', 0))
                token_stats.append({
                    "input": input_tokens,
                    "output": output_tokens
                })
                print(f" (输入:{input_tokens}, 输出:{output_tokens})")
            else:
                print()
            
            # 保存回答内容
            response_examples.append({
                "text": result['response_text'],
                "tool_calls": result['tool_calls']
            })
            
            # 显示模型回答内容
            if TEST_SETTINGS.get("show_response_content", True):
                response_preview = result['response_text'][:300] + "..." if len(result['response_text']) > 300 else result['response_text']
                print(f"💭 模型回答: {response_preview}")
                if result['tool_calls']:
                    print(f"🔧 工具调用:")
                    for tool_call in result['tool_calls']:
                        print(f"   - {tool_call['name']}: {tool_call['input']}")
                print("-" * 50)
        else:
            print(f"❌ 失败: {result['error']}")
        
        if i < rounds - 1:  # 最后一轮不需要等待
            time.sleep(TEST_SETTINGS["request_delay"])
    
    if times:
        avg_time = sum(times) / len(times)
        min_time = min(times)
        max_time = max(times)
        
        print(f"\n📈 性能统计:")
        print(f"   平均耗时: {avg_time:.3f}秒")
        print(f"   最快: {min_time:.3f}秒")
        print(f"   最慢: {max_time:.3f}秒")
        print(f"   成功率: {len(times)}/{rounds} ({len(times)/rounds*100:.1f}%)")
        
        if token_stats:
            avg_input = sum(s["input"] for s in token_stats) / len(token_stats)
            avg_output = sum(s["output"] for s in token_stats) / len(token_stats)
            efficiency = avg_output / avg_time
            
            print(f"\n🔢 Token统计:")
            print(f"   平均输入: {avg_input:.0f} tokens")
            print(f"   平均输出: {avg_output:.0f} tokens")
            print(f"   生成效率: {efficiency:.1f} tokens/s")
            
            # 预估每小时游戏步数
            steps_per_hour = 3600 / avg_time
            print(f"\n🎮 游戏性能预估:")
            print(f"   每小时可完成: {steps_per_hour:.0f} 步")
            print(f"   每分钟可完成: {steps_per_hour/60:.1f} 步")
        
        return avg_time
    else:
        print("\n❌ 所有测试都失败了")
        return None

if __name__ == "__main__":
    print("🎮 基于真实游戏数据的API性能测试")
    print("=" * 40)
    
    # 检查是否存在真实数据文件
    if not os.path.exists("real_api_request.json"):
        print("⚠️  未找到真实API请求数据文件")
        print("💡 请先运行以下命令生成真实数据:")
        print("   python main.py --steps 1")
        print("\n   这将运行游戏一步并保存真实的API请求参数")
        exit(1)
    
    print("选择测试模式:")
    print("1. 快速对比测试 (使用真实数据)")
    print("2. 单模型详细测试 (使用真实数据)")
    print("3. 显示真实数据信息")
    
    try:
        choice = input("\n请选择 (1-3): ").strip()
        
        if choice == "1":
            results = run_quick_comparison_with_real_data()
            
        elif choice == "2":
            print("\n可用模型:")
            for i, model in enumerate(MODELS_TO_TEST, 1):
                print(f"{i}. {model}")
            
            model_choice = input(f"\n选择模型 (1-{len(MODELS_TO_TEST)}): ").strip()
            try:
                model_index = int(model_choice) - 1
                if 0 <= model_index < len(MODELS_TO_TEST):
                    model = MODELS_TO_TEST[model_index]
                    
                    # 询问token数量
                    tokens_input = input(f"Max tokens (默认1024): ").strip()
                    max_tokens = int(tokens_input) if tokens_input else 1024
                    
                    # 询问测试轮数
                    rounds_input = input(f"测试轮数 (默认3): ").strip()
                    rounds = int(rounds_input) if rounds_input else 3
                    
                    test_single_model_with_real_data(model, max_tokens, rounds)
                else:
                    print("❌ 无效选择")
            except ValueError:
                print("❌ 请输入有效数字")
                
        elif choice == "3":
            real_data = load_real_api_request()
            if real_data:
                print("\n📋 真实API请求数据信息:")
                print(f"   🤖 模型: {real_data.get('model', '未知')}")
                print(f"   🔢 Max Tokens: {real_data.get('max_tokens', '未知')}")
                print(f"   🌡️  温度: {real_data.get('temperature', '未知')}")
                print(f"   📅 生成时间: {real_data.get('timestamp', '未知')}")
                print(f"   🎯 游戏步数: {real_data.get('step_number', '未知')}")
                print(f"   💬 消息数量: {len(real_data.get('messages', []))}")
                print(f"   🛠️  工具数量: {len(real_data.get('tools', []))}")
                
                # 显示消息结构
                messages = real_data.get('messages', [])
                if messages:
                    print(f"\n📝 消息结构:")
                    for i, msg in enumerate(messages):
                        role = msg.get('role', '未知')
                        content = msg.get('content', [])
                        if isinstance(content, list):
                            content_types = [item.get('type', '未知') for item in content]
                            print(f"   {i+1}. {role}: {', '.join(content_types)}")
                        else:
                            print(f"   {i+1}. {role}: 文本")
        else:
            print("❌ 无效选择")
            
    except KeyboardInterrupt:
        print("\n\n⏹️ 测试被中断")
    except Exception as e:
        print(f"\n❌ 错误: {e}")
    
    print("\n🏁 测试完成!")