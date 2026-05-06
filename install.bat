@echo off
cd /d "%~dp0"

title 订单同步系统 - 一键部署

echo ========================================
echo  订单同步系统 - 一键部署
echo ========================================
echo.

where python >nul 2>&1
if %errorlevel% neq 0 (
    echo [步骤 1/4] Python 未检测到
    echo.
    echo 请先安装 Python 3.10 或更高版本:
    echo   1. 打开 https://www.python.org/downloads/
    echo   2. 下载最新版 Python
    echo   3. 安装时勾选 "Add Python to PATH"
    echo   4. 安装完成后重新运行本脚本
    echo.
    pause
    exit /b 1
)
echo [步骤 1/4]  Python 已就绪

echo [步骤 2/4]  正在检查配置文件...
if not exist ".env" (
    if exist ".env.example" (
        copy ".env.example" ".env" >nul
        echo.
        echo   [!] 已自动创建 .env 配置文件
        echo   请用记事本打开 .env 文件
        echo   在等号后面填入你的 Webhook 地址
        echo   保存后重新运行本脚本
        echo.
        start notepad ".env"
        pause
        exit /b 0
    ) else (
        echo [错误] 找不到 .env.example 模板文件
        pause
        exit /b 1
    )
)
echo [步骤 2/4]  配置文件已就绪

echo [步骤 3/4]  正在安装依赖（首次运行需要1-2分钟）...
pip install -r requirements.txt
if %errorlevel% neq 0 (
    echo [错误] 依赖安装失败，请检查网络连接
    pause
    exit /b 1
)
echo [步骤 3/4]  依赖安装完成

echo [步骤 4/4]  正在启动订单同步...
echo.
python main.py

echo.
echo ========================================
echo  部署完成！按任意键退出
echo ========================================
pause
