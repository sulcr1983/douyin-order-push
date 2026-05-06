@echo off
cd /d "%~dp0"

title 订单同步系统 - Nuitka 打包脚本

echo ========================================
echo  订单同步系统 - Nuitka 打包
echo ========================================
echo.

where nuitka >nul 2>&1
if %errorlevel% neq 0 (
    echo [1/2] Nuitka 未检测到，正在安装...
    pip install nuitka
    if %errorlevel% neq 0 (
        echo [错误] Nuitka 安装失败
        pause
        exit /b 1
    )
    echo [1/2] Nuitka 安装完成
)

echo [2/2] 正在编译为单文件 EXE（首次编译需要 3-5 分钟）...
echo.
echo 编译完成后在 dist/ 目录下找到 订单同步系统.exe
echo.

pip install ordered-set zstandard >nul 2>&1

nuitka ^
    --standalone ^
    --onefile ^
    --enable-plugin=tk-inter ^
    --windows-console-mode=attach ^
    --output-dir=dist ^
    --output-name=订单同步系统.exe ^
    --file-version=3.0.0 ^
    --product-version=3.0.0 ^
    --file-description="订单同步系统" ^
    --copyright="sulcr@qq.com" ^
    --remove-output ^
    main.py

echo.
if %errorlevel% equ 0 (
    echo ========================================
    echo  打包成功！
    echo  输出文件: dist\订单同步系统.exe
    echo.
    echo  使用方法：将 .env 和店铺文件夹与 exe 同目录放置
    echo  双击 订单同步系统.exe 即可运行
    echo ========================================
) else (
    echo [错误] 编译失败，请查看上方错误信息
)

pause
