@echo off
cd /d "%~dp0"

where python >nul 2>&1
if %errorlevel% neq 0 (
    echo [错误] 未检测到 Python
    echo 请先安装 Python 3.10 或更高版本
    echo 下载地址: https://www.python.org/downloads/
    echo.
    echo 安装时请勾选 "Add Python to PATH"
    pause
    exit /b 1
)

echo ========================================
echo  订单同步系统 - 启动器
echo ========================================
echo.

echo [1/3] 正在检查依赖环境...
pip list 2>nul | findstr /C:"pandas" >nul
if %errorlevel% neq 0 (
    echo [2/3] 正在安装依赖（首次运行需要1-2分钟）...
    pip install -r requirements.txt
    if %errorlevel% neq 0 (
        echo [错误] 依赖安装失败，请检查网络连接
        pause
        exit /b 1
    )
    echo [2/3] 依赖安装完成
) else (
    echo [2/3] 依赖已就绪
)

echo [3/3] 正在执行订单同步...
echo.
python main.py

echo.
echo ========================================
echo  同步完成！按任意键退出
echo ========================================
pause
