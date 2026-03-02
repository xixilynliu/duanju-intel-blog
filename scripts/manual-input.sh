#!/bin/bash
# 手动笔记辅助脚本
# 用法: ./scripts/manual-input.sh [YYYY-WNN]
# 自动创建当周的手动笔记YAML文件并打开编辑器

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
NOTES_DIR="$PROJECT_DIR/hugo-site/data/manual_notes"

# 获取周次
if [ -n "$1" ]; then
    WEEK_ID="$1"
else
    WEEK_ID=$(date +%G-W%V)
fi

NOTES_FILE="$NOTES_DIR/${WEEK_ID}.yaml"

# 创建目录
mkdir -p "$NOTES_DIR"

# 如果文件不存在，创建模板
if [ ! -f "$NOTES_FILE" ]; then
    cat > "$NOTES_FILE" << EOF
# ${WEEK_ID} 手动补充笔记
# 在 notes 列表中添加本周手动收集的情报

notes:
  # - "【公司动态】描述..."
  # - "【行业会议】描述..."
  # - "【政策】描述..."
  # - "【投资】描述..."
EOF
    echo "已创建笔记文件: $NOTES_FILE"
else
    echo "笔记文件已存在: $NOTES_FILE"
fi

# 打开编辑器
EDITOR="${EDITOR:-vim}"
echo "正在用 $EDITOR 打开..."
$EDITOR "$NOTES_FILE"
