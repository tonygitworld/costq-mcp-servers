#!/bin/bash
# 一键运行测试脚本

set -e

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}================================${NC}"
echo -e "${BLUE}测试 _setup_account_context 函数${NC}"
echo -e "${BLUE}================================${NC}"
echo ""

# 获取脚本所在目录
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# 检查 Python 版本
echo -e "${YELLOW}🔍 检查 Python 版本...${NC}"
if ! command -v python3 &> /dev/null; then
    echo -e "${RED}❌ 未找到 python3${NC}"
    exit 1
fi

PYTHON_VERSION=$(python3 --version | awk '{print $2}')
echo -e "${GREEN}✅ Python 版本: $PYTHON_VERSION${NC}"
echo ""

# 检查虚拟环境
if [ ! -d ".venv" ]; then
    echo -e "${YELLOW}📦 创建虚拟环境...${NC}"
    python3 -m venv .venv
    echo -e "${GREEN}✅ 虚拟环境创建完成${NC}"
else
    echo -e "${GREEN}✅ 虚拟环境已存在${NC}"
fi
echo ""

# 激活虚拟环境
echo -e "${YELLOW}🔧 激活虚拟环境...${NC}"
source .venv/bin/activate
echo -e "${GREEN}✅ 虚拟环境已激活${NC}"
echo ""

# 安装依赖
echo -e "${YELLOW}📥 检查依赖...${NC}"
if [ -f "requirements.txt" ]; then
    echo -e "${BLUE}安装 requirements.txt...${NC}"
    pip install -q -r requirements.txt
    echo -e "${GREEN}✅ 依赖安装完成${NC}"
else
    echo -e "${YELLOW}⚠️  未找到 requirements.txt，跳过依赖安装${NC}"
fi
echo ""

# 设置默认环境变量
echo -e "${YELLOW}🔧 设置环境变量...${NC}"
export AWS_REGION="${AWS_REGION:-ap-northeast-1}"
export RDS_SECRET_NAME="${RDS_SECRET_NAME:-costq/rds/postgresql-dev}"
echo -e "${GREEN}✅ AWS_REGION=$AWS_REGION${NC}"
echo -e "${GREEN}✅ RDS_SECRET_NAME=$RDS_SECRET_NAME${NC}"
echo ""

# 检查 AWS 凭证
echo -e "${YELLOW}🔐 检查 AWS 凭证...${NC}"
if aws sts get-caller-identity &> /dev/null; then
    ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
    IDENTITY_ARN=$(aws sts get-caller-identity --query Arn --output text)
    echo -e "${GREEN}✅ AWS 凭证有效${NC}"
    echo -e "${GREEN}   账号: $ACCOUNT_ID${NC}"
    echo -e "${GREEN}   身份: $IDENTITY_ARN${NC}"
else
    echo -e "${RED}❌ AWS 凭证无效或未配置${NC}"
    echo -e "${YELLOW}请配置 AWS 凭证:${NC}"
    echo -e "  aws configure --profile 3532"
    echo -e "  或设置环境变量:"
    echo -e "  export AWS_ACCESS_KEY_ID=..."
    echo -e "  export AWS_SECRET_ACCESS_KEY=..."
    exit 1
fi
echo ""

# 运行测试
echo -e "${BLUE}================================${NC}"
echo -e "${BLUE}🚀 开始运行测试...${NC}"
echo -e "${BLUE}================================${NC}"
echo ""

python3 test_setup_context.py

# 获取退出码
EXIT_CODE=$?

echo ""
if [ $EXIT_CODE -eq 0 ]; then
    echo -e "${GREEN}================================${NC}"
    echo -e "${GREEN}🎉 测试成功完成!${NC}"
    echo -e "${GREEN}================================${NC}"
else
    echo -e "${RED}================================${NC}"
    echo -e "${RED}❌ 测试失败 (退出码: $EXIT_CODE)${NC}"
    echo -e "${RED}================================${NC}"
    echo ""
    echo -e "${YELLOW}常见问题排查:${NC}"
    echo -e "1. 数据库连接失败 → 检查 RDS_SECRET_NAME 和网络"
    echo -e "2. 账号不存在 → 确认数据库中是否有账号 000451883532"
    echo -e "3. AKSK 解密失败 → 设置 ENCRYPTION_KEY 环境变量"
    echo -e "4. AssumeRole 失败 → 检查 IAM 权限和信任策略"
    echo ""
    echo -e "${YELLOW}查看详细文档:${NC}"
    echo -e "  cat README_TEST.md"
fi

exit $EXIT_CODE
