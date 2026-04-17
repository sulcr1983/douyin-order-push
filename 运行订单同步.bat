@echo on

REM 切换到当前目录
cd /d "%~dp0"

REM 运行Python脚本
python main.py

REM 执行完成后暂停，以便查看结果
pause