#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
API测试配置文件
可以快速修改测试参数而不需要修改主测试文件
"""

# API连接配置
API_CONFIG = {
    "api_key": "sk-ksbCidPFhLiGTRo_I4fflYASF92UHYC8S1DNHp2kkbTaJkRShC8oOKPIJdI",
    "base_url": "https://chatapi.leyidc.net/claude",
}

# ============================================================================
# 🎯 用户自定义测试模型列表 - 在这里修改你想测试的模型
# ============================================================================

# 你可以在这里输入任何你想测试的模型列表
USER_TEST_MODELS = [
    #"claude-3-7-sonnet-20250219",
    "claude-sonnet-4-20250514", 
    #"gemini-2.5-flash",
    #"gpt-4.1"
    # "claude-3-sonnet-20240229",
    # "claude-3-opus-20240229",
    
    # 添加更多模型只需要在这里添加即可，例如：
    # "gpt-4-turbo",  # 如果你的API支持其他模型
]

# 要测试的模型列表 (用于单模型测试)
MODELS_TO_TEST = USER_TEST_MODELS

# 测试参数
TEST_SETTINGS = {
    "test_rounds": 1,           # 每个配置测试几轮
    "request_delay": 1.0,       # 请求间隔(秒)，避免频率限制
    "timeout": 30,              # 请求超时时间(秒)
    "temperature": 0.7,         # 模型温度参数
    "show_response_content": True,  # 显示模型回答内容用于评估效果
}

# 性能基准 (用于对比)
PERFORMANCE_BENCHMARKS = {
    "excellent": 2.0,    # 2秒以内为优秀
    "good": 5.0,         # 5秒以内为良好  
    "acceptable": 10.0,  # 10秒以内为可接受
    "poor": 15.0,        # 15秒以上为较差
}

def generate_quick_test_configs(models_list=None):
    """
    根据用户输入的模型列表动态生成测试配置
    不预设任何模型性能特征，完全基于用户输入
    
    Args:
        models_list: 要测试的模型列表，如果为None则使用USER_TEST_MODELS
    
    Returns:
        list: 生成的测试配置列表
    """
    if models_list is None:
        models_list = USER_TEST_MODELS
    
    if not models_list:
        return []
    
    configs = []
    
    # 为每个模型生成基础配置
    for i, model in enumerate(models_list):
        # 基础配置 (1024 tokens)
        configs.append({
            "name": f"模型{i+1}: {model}",
            "model": model,
            "max_tokens": 1024,
            "description": f"测试模型: {model}"
        })
        
        # 高token配置 (2048 tokens)
        configs.append({
            "name": f"模型{i+1}+: {model} (高token)",
            "model": model,
            "max_tokens": 4000,
            "description": f"测试模型: {model} - 高token版本"
        })
    
    return configs

# 动态生成快速测试配置
QUICK_TEST_CONFIGS = generate_quick_test_configs()

# 打印当前生成的配置（用于调试）
if __name__ == "__main__":
    print("🎯 当前用户定义的测试模型:")
    for i, model in enumerate(USER_TEST_MODELS, 1):
        print(f"  {i}. {model}")
    
    print(f"\n📋 生成的快速测试配置 ({len(QUICK_TEST_CONFIGS)}个):")
    for config in QUICK_TEST_CONFIGS:
        print(f"  • {config['name']}: {config['model']} ({config['max_tokens']} tokens)")
        print(f"    {config['description']}")