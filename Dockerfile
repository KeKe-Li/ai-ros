# 机器人 Agent Runtime 原型容器镜像
# 演示工程化部署：构建后默认运行端到端 pick-and-place 闭环 demo。
FROM python:3.12-slim

WORKDIR /app

# 先复制依赖清单以利用构建缓存
COPY pyproject.toml README.md ./
COPY src ./src

# 安装本包（核心零运行时依赖）
RUN pip install --no-cache-dir -e .

# 默认运行演示；可在 docker run 时覆盖，如：
#   docker run --rm <image> python -m robot_agent.cli demo --inject-failure --verbose
CMD ["python", "-m", "robot_agent.cli", "demo", "--verbose"]
