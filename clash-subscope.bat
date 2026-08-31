@echo off
chcp 936 >nul
setlocal
set "HERE=%~dp0"
set "PYTHONW=C:\Users\29436\anaconda3\pythonw.exe"
set "PYTHON=C:\Users\29436\anaconda3\python.exe"

REM ---- 检查解释器 ----
if not exist "%PYTHONW%" goto NOPY

REM ---- 检查 PyYAML ----
"%PYTHON%" -c "import yaml" >nul 2>&1
if not errorlevel 1 goto RUN

echo [提示] 缺少 PyYAML，正在安装，请稍候...
"%PYTHON%" -m pip install pyyaml
if errorlevel 1 goto PIPFAIL

:RUN
start "" "%PYTHONW%" "%HERE%main.py"
goto END

:NOPY
echo [错误] 未找到 Python 解释器：
echo        %PYTHONW%
echo 请修改本文件里的 PYTHONW / PYTHON 两个变量，指向你本机的
echo pythonw.exe 与 python.exe（GUI 需要用 pythonw 避免黑窗口）。
echo.
pause
goto END

:PIPFAIL
echo [错误] PyYAML 安装失败，请手动执行：
echo        "%PYTHON%" -m pip install pyyaml
echo.
pause
goto END

:END
endlocal
