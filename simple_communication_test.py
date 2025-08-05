import time
import json
import sys
from anthropic import Anthropic
from api_test_config import API_CONFIG

def test_real_data_comparison(model_name="claude-3-7-sonnet-20250219", rounds=3):
    """使用真实配置调用接口，打印回复和时长信息，比较完整消息和最后两条消息的差异"""
    # 读取真实请求配置
    with open("real_api_request.json", "r", encoding="utf-8") as f:
        real_config = json.load(f)
    
    # 初始化客户端
    client = Anthropic(api_key=API_CONFIG["api_key"], base_url=API_CONFIG["base_url"])
    
    # 测试1: 使用完整消息历史
    print("\n===== 测试1: 使用完整消息历史 =====")
    print(f"消息数量: {len(real_config['messages'])}")
    print(f"消息大小: {sys.getsizeof(json.dumps(real_config['messages']))} 字节")
    
    full_times = []
    for i in range(rounds):
        print(f"\n轮次 {i+1}/{rounds}:")
        start_time = time.time()
        full_response = client.messages.create(
            model=real_config["model"],
            messages=real_config["messages"],
            system=real_config["system"],
            max_tokens=real_config["max_tokens"],
            temperature=real_config["temperature"],
            tools=real_config["tools"]
        )
        duration = time.time() - start_time
        full_times.append(duration)
        print(f"耗时: {duration:.3f}秒")
        print(f"回复: {full_response.content[0].text[:100]}...")
        time.sleep(1)  # 避免频率限制
    
    avg_full_time = sum(full_times) / len(full_times)
    print(f"\n完整消息平均耗时: {avg_full_time:.3f}秒")
    
    # 测试2: 使用最后两条消息
    last_two_messages = real_config["messages"][-2:] if len(real_config["messages"]) >= 2 else real_config["messages"]
    print("\n===== 测试2: 使用最后两条消息 =====")
    print(f"消息数量: {len(last_two_messages)}")
    print(f"消息大小: {sys.getsizeof(json.dumps(last_two_messages))} 字节")
    
    last_times = []
    for i in range(rounds):
        print(f"\n轮次 {i+1}/{rounds}:")
        start_time = time.time()
        last_response = client.messages.create(
            model=real_config["model"],
            messages=last_two_messages,
            system=real_config["system"],
            max_tokens=real_config["max_tokens"],
            temperature=real_config["temperature"],
            tools=real_config["tools"]
        )
        duration = time.time() - start_time
        last_times.append(duration)
        print(f"耗时: {duration:.3f}秒")
        print(f"回复: {last_response.content[0].text[:100]}...")
        time.sleep(1)  # 避免频率限制
    
    avg_last_time = sum(last_times) / len(last_times)
    print(f"\n最后两条消息平均耗时: {avg_last_time:.3f}秒")
    
    # 打印总结
    print("\n===== 性能对比 =====")
    print(f"完整消息平均耗时: {avg_full_time:.3f}秒")
    print(f"最后两条消息平均耗时: {avg_last_time:.3f}秒")
    if avg_full_time > avg_last_time:
        speedup = avg_full_time / avg_last_time
        print(f"使用最后两条消息比完整消息快 {speedup:.2f} 倍")
    else:
        speedup = avg_last_time / avg_full_time
        print(f"使用完整消息比最后两条消息快 {speedup:.2f} 倍")

if __name__ == "__main__":
    test_real_data_comparison()