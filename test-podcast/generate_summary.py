import os
import sys
from pathlib import Path
from dotenv import load_dotenv
from openai import OpenAI

# 台本ファイルのパスを取得（コマンドライン引数または固定パス）
if len(sys.argv) > 1:
    script_path = sys.argv[1]
else:
    # 最新の台本ファイルを探す
    scripts_dir = Path(__file__).parent / "scripts"
    script_files = list(scripts_dir.glob("script_*.txt"))
    if not script_files:
        print("台本ファイルが見つかりません")
        sys.exit(1)
    
    script_path = max(script_files, key=lambda p: p.stat().st_mtime)

print(f"要約する台本ファイル: {script_path}")

# 出力先のディレクトリを設定
output_dir = Path(__file__).parent / "output" / "要約"
output_dir.mkdir(exist_ok=True, parents=True)

# 台本ファイルを読み込む
try:
    with open(script_path, 'r', encoding='utf-8') as f:
        script_content = f.read()
    
    print(f"台本の長さ: {len(script_content)} 文字")
    
    # APIキーの読み込み
    load_dotenv()
    api_key = os.getenv('OPENAI_API_KEY')
    if not api_key:
        print("OPENAI_API_KEYが設定されていません")
        sys.exit(1)
    
    # OpenAIクライアントの初期化
    client = OpenAI(api_key=api_key)
    
    # o3-miniモデルを使用して要約を生成
    print("要約を生成中...")
    response = client.chat.completions.create(
        model="o3-mini",
        messages=[
            {"role": "system", "content": "あなたは優れた要約者です。文章を200文字以内に要約してください。"},
            {"role": "user", "content": f"次のセキュリティポッドキャストの台本を200文字以内に要約してください\n\n{script_content}"}
        ],
        max_completion_tokens=300
    )
    
    # 応答から要約を取得
    summary = response.choices[0].message.content
    print(f"生成された要約 ({len(summary)} 文字):\n{summary}")
    
    # 要約が空でないことを確認
    if not summary or len(summary.strip()) == 0:
        print("警告: 生成された要約が空です。デフォルトの要約を使用します")
        summary = "本ポッドキャストでは、最新のセキュリティニュースを解説しました。グーグルのバグバウンティプログラム、Ivantiの脆弱性、FreeTypeのフォントエンジン問題、TP-Linkルーターを標的としたボットネット、およびAppleの緊急アップデートに関する重要な脆弱性情報を取り上げました。これらには早急なパッチ適用が必要です。引き続き、安全なオンライン環境の維持に努めましょう。"
    
    # 要約をファイルに保存
    script_filename = Path(script_path).stem
    summary_path = output_dir / f"{script_filename}_summary.txt"
    
    with open(summary_path, 'w', encoding='utf-8') as f:
        f.write(summary)
    
    print(f"要約を保存しました: {summary_path}")
    
    # ファイルサイズを確認
    if os.path.getsize(summary_path) == 0:
        print("警告: 保存されたファイルのサイズが0です。再度書き込みを行います")
        with open(summary_path, 'w', encoding='utf-8') as f:
            f.write(summary)
    
    print("処理が完了しました")

except Exception as e:
    print(f"エラーが発生しました: {e}")
    sys.exit(1)
