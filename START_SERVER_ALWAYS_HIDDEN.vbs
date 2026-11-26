Set WshShell = CreateObject("WScript.Shell")
WshShell.Run "powershell -NoProfile -ExecutionPolicy Bypass -File ""E:\Anton\awesome-llm-apps-main\university-ai-agents\run_server_forever.ps1""", 0, False
