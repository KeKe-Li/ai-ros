# 机器人 Agent Runtime 原型容器镜像
# 演示工程化部署：构建后默认运行端到端 pick-and-place 闭环 demo。
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# 先复制依赖清单以利用构建缓存
COPY pyproject.toml README.md ./
COPY src ./src

# 以普通 wheel 安装，并用无登录权限的非 root 用户运行。
RUN pip install --no-cache-dir . \
    && addgroup --system robot \
    && adduser --system --ingroup robot robot

USER robot

# 默认运行演示；可在 docker run 时覆盖，如：
#   docker run --rm <image> python -m robot_agent.cli demo --inject-failure --verbose
CMD ["python", "-m", "robot_agent.cli", "demo", "--verbose"]
