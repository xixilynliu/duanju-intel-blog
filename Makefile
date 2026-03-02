.PHONY: setup preview full scrape generate manual clean

# 首次安装依赖
setup:
	pip3 install -r scrapers/requirements.txt
	@echo "依赖安装完成"

# 本地预览Hugo站点
preview:
	cd hugo-site && hugo server -D

# 完整流程：采集 + 处理 + 生成周报 + 预览
full:
	cd scrapers && python3 main.py
	cd hugo-site && hugo server -D

# 仅采集
scrape:
	cd scrapers && python3 main.py --scrape-only

# 仅生成周报（使用已有数据）
generate:
	cd scrapers && python3 main.py --generate-only

# 添加手动笔记
manual:
	bash scripts/manual-input.sh

# 构建静态文件
build:
	cd hugo-site && hugo --minify

# 清理
clean:
	rm -rf hugo-site/public
	rm -rf scrapers/data/raw/*.json
	rm -rf scrapers/data/processed/*.json
	@echo "清理完成"
