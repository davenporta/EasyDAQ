pyinstaller easyDAQ.spec
xcopy .\config.txt .\dist\ /Y
xcopy .\logos\* .\dist\logos\ /e /Y
PAUSE