@echo off
echo セキュリティポッドキャスト生成を開始します...
echo 開始時刻: %date% %time%

cd /d "C:\Users\takky\OneDrive\デスクトップ\code_work\code_woek\test-podcast"

REM Pythonの実行とログの保存
"C:\Users\takky\AppData\Local\Programs\Python\Python310\python.exe" "C:\Users\takky\OneDrive\デスクトップ\code_work\code_woek\test-podcast\main_with_summary.py" > podcast_run_log.txt 2>&1

echo 終了時刻: %date% %time%
echo 処理が完了しました。
echo ログは podcast_run_log.txt を確認してください。
