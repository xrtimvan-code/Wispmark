@echo off
chcp 65001 >nul
cd /d "%~dp0"
title 悬笺 Markdown

rem 检查 Python
set "PY="
where pythonw >nul 2>nul && set "PY=pythonw"
if not defined PY (
    where python >nul 2>nul && set "PY=python"
)
if not defined PY (
    echo.
    echo  [悬笺 Markdown] 未检测到 Python，第一次使用需要先安装：
    echo.
    echo    1. 打开 https://www.python.org/downloads/
    echo    2. 下载并安装 Python 3.10 或更高版本
    echo    3. 安装时务必勾选 "Add python.exe to PATH"
    echo.
    echo  安装完成后重新双击本文件即可。
    echo.
    pause
    exit /b 1
)

rem 检查并自动安装依赖
python -c "import PySide6" >nul 2>nul
if errorlevel 1 (
    echo  [悬笺 Markdown] 正在安装依赖 PySide6，首次安装约 1 分钟，请稍候...
    python -m pip install -r requirements.txt
    if errorlevel 1 (
        echo  默认源安装失败，尝试清华镜像...
        python -m pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple
    )
    if errorlevel 1 (
        echo.
        echo  [悬笺 Markdown] 依赖安装失败，请检查网络后重试。
        pause
        exit /b 1
    )
)

start "" %PY% floating_notepad.py
