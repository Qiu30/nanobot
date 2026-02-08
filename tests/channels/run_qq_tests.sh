#!/bin/bash
# QQ Channel 测试运行脚本

set -e

echo "=========================================="
echo "QQ Channel 测试套件"
echo "=========================================="
echo ""

# 检查 Python 版本
echo "检查 Python 版本..."
python_version=$(python --version 2>&1 | awk '{print $2}')
echo "当前 Python 版本: $python_version"

required_version="3.11"
if [ "$(printf '%s\n' "$required_version" "$python_version" | sort -V | head -n1)" != "$required_version" ]; then
    echo "❌ 错误: 需要 Python 3.11 或更高版本"
    echo "   当前版本: $python_version"
    exit 1
fi
echo "✅ Python 版本检查通过"
echo ""

# 检查依赖
echo "检查测试依赖..."
if ! python -c "import pytest" 2>/dev/null; then
    echo "❌ pytest 未安装"
    echo "   运行: pip install pytest pytest-asyncio"
    exit 1
fi

if ! python -c "import pytest_asyncio" 2>/dev/null; then
    echo "❌ pytest-asyncio 未安装"
    echo "   运行: pip install pytest-asyncio"
    exit 1
fi
echo "✅ 依赖检查通过"
echo ""

# 运行测试
echo "运行测试..."
echo "=========================================="

# 根据参数决定运行哪些测试
if [ "$1" == "basic" ]; then
    echo "运行基础测试..."
    python -m pytest tests/channels/test_qq.py::TestQQChannelBasic -v
elif [ "$1" == "config" ]; then
    echo "运行配置测试..."
    python -m pytest tests/channels/test_qq.py::TestQQChannelConfig -v
elif [ "$1" == "integration" ]; then
    echo "运行集成测试..."
    python -m pytest tests/channels/test_qq.py::TestQQChannelIntegration -v
elif [ "$1" == "all" ]; then
    echo "运行所有测试（包括跳过的）..."
    python -m pytest tests/channels/test_qq.py -v
elif [ "$1" == "coverage" ]; then
    echo "运行测试并生成覆盖率报告..."
    python -m pytest tests/channels/test_qq.py --cov=nanobot.channels.qq --cov-report=html --cov-report=term
    echo ""
    echo "覆盖率报告已生成到: htmlcov/index.html"
else
    echo "运行可执行的测试（跳过标记为 skip 的）..."
    python -m pytest tests/channels/test_qq.py -v -m "not skip"
fi

echo ""
echo "=========================================="
echo "测试完成"
echo "=========================================="
