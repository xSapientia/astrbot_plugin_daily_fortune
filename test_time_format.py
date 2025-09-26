#!/usr/bin/env python3
"""
测试时间格式修改
"""

from datetime import datetime

def test_time_format():
    """测试新的时间格式"""
    # 模拟原来的格式（只有年月日）
    old_format = datetime.now().strftime("%Y-%m-%d")
    print(f"原来的时间格式: {old_format}")
    
    # 新的格式（年月日时分秒）
    new_format = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"新的时间格式: {new_format}")
    
    # 检查格式差异
    print(f"格式长度对比: 原格式 {len(old_format)} 字符, 新格式 {len(new_format)} 字符")
    
    # 测试是否可以解析
    try:
        parsed_old = datetime.strptime(old_format, "%Y-%m-%d")
        print(f"原格式解析成功: {parsed_old}")
    except Exception as e:
        print(f"原格式解析失败: {e}")
    
    try:
        parsed_new = datetime.strptime(new_format, "%Y-%m-%d %H:%M:%S")
        print(f"新格式解析成功: {parsed_new}")
    except Exception as e:
        print(f"新格式解析失败: {e}")

if __name__ == "__main__":
    test_time_format()
