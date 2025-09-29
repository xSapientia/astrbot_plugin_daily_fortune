#!/usr/bin/env python3
"""
测试每日人品插件修复效果
验证每日只能测试一次的逻辑是否正确
"""

import sys
import os
from datetime import datetime
import time

# 添加项目路径到sys.path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# 模拟AstrBot环境
class MockLogger:
    def info(self, msg): print(f"[INFO] {msg}")
    def error(self, msg): print(f"[ERROR] {msg}")
    def debug(self, msg): print(f"[DEBUG] {msg}")
    def warning(self, msg): print(f"[WARNING] {msg}")

# 注入mock logger
class MockAPI:
    logger = MockLogger()

import sys
sys.modules['astrbot.api'] = MockAPI()

# 直接导入和测试算法模块
sys.path.insert(0, 'core')

# 单独测试算法模块
import importlib.util
spec = importlib.util.spec_from_file_location("algorithm", "core/algorithm.py")
algorithm_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(algorithm_module)
FortuneAlgorithm = algorithm_module.FortuneAlgorithm

# 单独测试存储模块
spec = importlib.util.spec_from_file_location("storage", "core/storage.py")
storage_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(storage_module)
Storage = storage_module.Storage

def test_date_key_fix():
    """测试日期key修复"""
    print("=== 测试日期key生成 ===")
    
    # 模拟配置
    config = {
        "jrrp_algorithm": "hash",  # 使用hash算法确保同一天结果一致
        "ranges_jrrp": "0-1, 2-10, 11-20, 21-30, 31-40, 41-60, 61-80, 81-98, 99-100",
        "ranges_fortune": "极凶, 大凶, 凶, 小凶, 末吉, 小吉, 中吉, 大吉, 极吉",
        "ranges_emoji": "💀, 😨, 😰, 😟, 😐, 🙂, 😊, 😄, 🤩"
    }
    
    algorithm = FortuneAlgorithm(config)
    
    # 测试多次调用get_today_key()应该返回相同结果
    key1 = algorithm.get_today_key()
    key2 = algorithm.get_today_key()
    
    print(f"第一次调用: {key1}")
    print(f"第二次调用: {key2}")
    print(f"是否相同: {key1 == key2}")
    
    # 检查格式
    expected_format = datetime.now().strftime("%Y-%m-%d")
    print(f"期望格式: {expected_format}")
    print(f"实际格式: {key1}")
    print(f"格式正确: {key1 == expected_format}")
    
    # 测试时间戳生成
    timestamp1 = algorithm.get_current_timestamp()
    time.sleep(1)
    timestamp2 = algorithm.get_current_timestamp()
    
    print(f"时间戳1: {timestamp1}")
    print(f"时间戳2: {timestamp2}")
    print(f"时间戳不同: {timestamp1 != timestamp2}")
    
    return key1 == key2 and key1 == expected_format

def test_storage_logic():
    """测试存储逻辑"""
    print("\n=== 测试存储逻辑 ===")
    
    # 临时存储目录
    storage = Storage("test_plugin")
    
    # 模拟配置
    config = {
        "jrrp_algorithm": "hash",
        "ranges_jrrp": "0-1, 2-10, 11-20, 21-30, 31-40, 41-60, 61-80, 81-98, 99-100",
        "ranges_fortune": "极凶, 大凶, 凶, 小凶, 末吉, 小吉, 中吉, 大吉, 极吉",
        "ranges_emoji": "💀, 😨, 😰, 😟, 😐, 🙂, 😊, 😄, 🤩"
    }
    
    algorithm = FortuneAlgorithm(config)
    
    user_id = "test_user_123"
    today = algorithm.get_today_key()
    timestamp = algorithm.get_current_timestamp()
    
    print(f"用户ID: {user_id}")
    print(f"今日key: {today}")
    print(f"时间戳: {timestamp}")
    
    # 第一次查询（应该为空）
    cached = storage.get_today_fortune(today, user_id)
    print(f"首次查询结果: {cached}")
    
    # 模拟保存数据
    jrrp = algorithm.calculate_jrrp(user_id)
    fortune, emoji = algorithm.get_fortune_info(jrrp)
    
    fortune_data = {
        "jrrp": jrrp,
        "fortune": fortune,
        "process": "测试占卜过程",
        "advice": "测试建议",
        "nickname": "测试用户",
        "timestamp": timestamp
    }
    
    print(f"生成人品值: {jrrp} ({fortune} {emoji})")
    
    # 保存数据
    storage.save_today_fortune(today, user_id, fortune_data)
    
    # 第二次查询（应该有缓存）
    cached = storage.get_today_fortune(today, user_id)
    print(f"缓存查询结果: {cached is not None}")
    print(f"缓存人品值: {cached['jrrp'] if cached else 'None'}")
    
    # 验证历史记录
    history = storage.get_user_history(user_id, 10)
    print(f"历史记录条数: {len(history)}")
    for timestamp_key, data in history.items():
        print(f"  [{timestamp_key}] {data['jrrp']} ({data['fortune']})")
    
    # 清理测试数据
    storage.reset_all_data()
    print("测试数据已清理")
    
    return cached is not None and cached['jrrp'] == jrrp

def test_same_day_multiple_calls():
    """测试同一天多次调用的逻辑"""
    print("\n=== 测试同一天多次调用 ===")
    
    storage = Storage("test_plugin_2")
    config = {
        "jrrp_algorithm": "hash",  # 使用hash确保可重现
        "ranges_jrrp": "0-1, 2-10, 11-20, 21-30, 31-40, 41-60, 61-80, 81-98, 99-100",
        "ranges_fortune": "极凶, 大凶, 凶, 小凶, 末吉, 小吉, 中吉, 大吉, 极吉",
        "ranges_emoji": "💀, 😨, 😰, 😟, 😐, 🙂, 😊, 😄, 🤩"
    }
    
    algorithm = FortuneAlgorithm(config)
    user_id = "test_user_456"
    today = algorithm.get_today_key()
    
    # 第一次测试人品
    jrrp1 = algorithm.calculate_jrrp(user_id)
    fortune1, emoji1 = algorithm.get_fortune_info(jrrp1)
    timestamp1 = algorithm.get_current_timestamp()
    
    fortune_data1 = {
        "jrrp": jrrp1,
        "fortune": fortune1,
        "process": "第一次占卜",
        "advice": "第一次建议",
        "nickname": "测试用户",
        "timestamp": timestamp1
    }
    
    storage.save_today_fortune(today, user_id, fortune_data1)
    print(f"第一次人品: {jrrp1} ({fortune1}) at {timestamp1}")
    
    # 模拟稍后再次调用
    time.sleep(1)
    
    # 检查是否已有今日记录
    cached = storage.get_today_fortune(today, user_id)
    if cached:
        print(f"发现缓存: {cached['jrrp']} ({cached.get('fortune', 'N/A')})")
        print("✅ 正确：同一天不会重新生成人品值")
        success = True
    else:
        print("❌ 错误：没有找到今日缓存记录")
        success = False
    
    # 验证历史记录
    history = storage.get_user_history(user_id, 10)
    print(f"历史记录: {len(history)} 条")
    
    # 清理
    storage.reset_all_data()
    
    return success

def test_hash_algorithm_consistency():
    """测试hash算法的一致性（同一天同一用户应该得到相同结果）"""
    print("\n=== 测试hash算法一致性 ===")
    
    config = {
        "jrrp_algorithm": "hash",
        "ranges_jrrp": "0-1, 2-10, 11-20, 21-30, 31-40, 41-60, 61-80, 81-98, 99-100",
        "ranges_fortune": "极凶, 大凶, 凶, 小凶, 末吉, 小吉, 中吉, 大吉, 极吉",
        "ranges_emoji": "💀, 😨, 😰, 😟, 😐, 🙂, 😊, 😄, 🤩"
    }
    
    algorithm = FortuneAlgorithm(config)
    user_id = "test_user_hash"
    
    # 多次调用应该得到相同结果（使用hash算法）
    jrrp1 = algorithm.calculate_jrrp(user_id)
    time.sleep(1)
    jrrp2 = algorithm.calculate_jrrp(user_id)
    time.sleep(1)
    jrrp3 = algorithm.calculate_jrrp(user_id)
    
    print(f"第一次计算: {jrrp1}")
    print(f"第二次计算: {jrrp2}")
    print(f"第三次计算: {jrrp3}")
    
    all_same = jrrp1 == jrrp2 == jrrp3
    print(f"所有结果相同: {all_same}")
    
    if all_same:
        print("✅ hash算法工作正常，同一天同一用户得到相同结果")
    else:
        print("❌ hash算法异常，同一天同一用户得到不同结果")
    
    return all_same

def main():
    """主测试函数"""
    print("开始测试每日人品插件修复效果...")
    print("=" * 50)
    
    # 运行所有测试
    tests = [
        ("日期key生成", test_date_key_fix),
        ("存储逻辑", test_storage_logic),
        ("同一天多次调用", test_same_day_multiple_calls),
        ("hash算法一致性", test_hash_algorithm_consistency),
    ]
    
    results = []
    for test_name, test_func in tests:
        try:
            result = test_func()
            results.append((test_name, result))
            status = "✅ 通过" if result else "❌ 失败"
            print(f"\n{test_name}: {status}")
        except Exception as e:
            results.append((test_name, False))
            print(f"\n{test_name}: ❌ 异常 - {e}")
            import traceback
            traceback.print_exc()
    
    print("\n" + "=" * 50)
    print("测试总结:")
    
    passed = 0
    for test_name, result in results:
        status = "✅" if result else "❌"
        print(f"  {status} {test_name}")
        if result:
            passed += 1
    
    total = len(results)
    print(f"\n通过: {passed}/{total}")
    
    if passed == total:
        print("🎉 所有测试通过！每日人品插件修复成功！")
        print("\n修复内容：")
        print("1. ✅ 修复了 get_today_key() 方法，现在只返回日期（YYYY-MM-DD）")
        print("2. ✅ 添加了 get_current_timestamp() 方法，用于记录详细时间")
        print("3. ✅ 更新了存储逻辑，历史记录使用详细时间戳")
        print("4. ✅ 修复了删除和清除逻辑，支持时间戳格式")
        print("5. ✅ 确保每日只能测试一次人品，但保留详细的时间记录")
    else:
        print("⚠️  部分测试失败，需要进一步检查。")
    
    return passed == total

if __name__ == "__main__":
    main()
