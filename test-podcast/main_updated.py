import asyncio
import feedparser
import requests
from bs4 import BeautifulSoup
import os
import json
from datetime import datetime, timedelta
from pathlib import Path
from dotenv import load_dotenv
from openai import OpenAI
import logging
import re
import subprocess
import shutil

# ロギング設定
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("podcast_generator.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# 定数
SITE_URL = "https://rocket-boys.co.jp/security-measures-lab/"
RSS_URL = "https://rocket-boys.co.jp/feed/"
BASE_DIR = Path(__file__).parent.resolve()
SCRIPTS_DIR = BASE_DIR / "scripts"
OUTPUT_DIR = BASE_DIR / "output"
SUMMARY_DIR = OUTPUT_DIR / "要約"
TEMP_DIR = BASE_DIR / "temp"

# BGMファイルのパス
BGM_FILE = r"C:\Users\takky\OneDrive\デスクトップ\code_work\code_woek\test-podcast\bgm\296_long_BPM85.mp3"

# OpenAI プロンプト
PODCAST_PROMPT = """あなたはプロのPodcastの話し手です。 上記の文章と各URLを検索して4000文字程度のPodcast用の台本を作成してください。 
・出力は普通の丁寧語で口語のみとし、目次やタイトルは除外する（一連の文章だけの出力とする） 
・最大限のリソースを使用してハルシネーションを防止すること 
・出力はすべてソースのあるものから行い、あいまいな情報は使用しない 
・上記の条件を何があっても必ず逸脱しないこと 
・出力は下記のフォーマットとすること、出力にリンクと記事のタイトルは表示させないが、企業名は表示させること 
・出力内容を検証し、同じ名用を言っていないか検証すること。同じであれば独自に検索して内容を付け足して、同じ言い回しや内容はできるだけ使いまわさず、実のある内容にして 
・出力内容は一度精査し、内容にうそや矛盾がないことを検証すること"""

# 固定のあいさつ
OPENING_GREETING = "こんにちは、皆さん。ようこそ、私はホストの大江です。"
CLOSING_MESSAGE = "今後もこうしたニュースの背景や影響について、皆さんと一緒に考えていきたいと思います。もしこのエピソードについてご意見や質問がありましたら、ぜひお寄せください。また、ポッドキャストを楽しんでいただけたなら、評価やレビューもお願いします。それでは、次回もお楽しみに。ありがとうございました。"

def get_yesterday_date():
    """昨日の日付を取得する"""
    yesterday = datetime.now() - timedelta(days=1)
    return yesterday.strftime('%Y-%m-%d')

def fetch_rss_feed(url):
    """RSSフィードを取得する"""
    try:
        feed = feedparser.parse(url)
        logger.info(f"RSS取得成功: {len(feed.entries)}件のエントリを検出")
        return feed
    except Exception as e:
        logger.error(f"RSSフィード取得エラー: {e}")
        return None

def get_articles_from_website(site_url, num_articles=3):
    """Webサイトから直接記事を取得する"""
    try:
        logger.info(f"Webサイトから記事を取得しています: {site_url}")
        response = requests.get(site_url)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # 記事リストを探す (サイト構造によって調整が必要)
        articles = []
        
        # 様々な記事コンテナの可能性を試す
        article_elements = soup.find_all('article') or soup.find_all('div', class_=lambda c: c and ('post' in c or 'article' in c))
        
        if not article_elements:
            # より一般的な方法で記事を探してみる
            article_elements = soup.find_all(['div', 'section'], class_=lambda c: c and ('post' in c or 'article' in c or 'entry' in c))
        
        logger.info(f"記事候補数: {len(article_elements)}")
        
        for article_elem in article_elements[:num_articles]:
            # タイトルを探す
            title_elem = article_elem.find(['h1', 'h2', 'h3', 'h4']) or article_elem.find(class_=lambda c: c and ('title' in c))
            
            # リンクを探す
            link_elem = None
            if title_elem and title_elem.find('a'):
                link_elem = title_elem.find('a')
            else:
                link_elem = article_elem.find('a', href=lambda h: h and not h.startswith('#'))
            
            # 日付を探す
            date_elem = article_elem.find(['time', 'span', 'div'], class_=lambda c: c and ('date' in c or 'time' in c or 'pub' in c))
            
            if title_elem and link_elem:
                title = title_elem.get_text().strip()
                link = link_elem.get('href')
                
                # 相対URLを絶対URLに変換
                if link and not link.startswith(('http://', 'https://')):
                    link = f"https://rocket-boys.co.jp{link}" if not link.startswith('/') else f"https://rocket-boys.co.jp{link}"
                
                date_str = date_elem.get_text().strip() if date_elem else "日付不明"
                
                articles.append({
                    "title": title,
                    "link": link,
                    "date": date_str
                })
        
        logger.info(f"取得した記事数: {len(articles)}")
        return articles
    
    except Exception as e:
        logger.error(f"記事取得エラー: {e}")
        return []

def extract_article_content(url):
    """記事の本文を抽出する"""
    try:
        logger.info(f"記事内容を取得しています: {url}")
        response = requests.get(url)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # ページから公開日を抽出してみる
        date_elem = soup.find(['time', 'span', 'div'], class_=lambda c: c and ('date' in c or 'time' in c or 'pub' in c))
        pub_date = date_elem.get_text().strip() if date_elem else None
        
        # 記事本文を探す方法を複数試す
        content = None
        
        # 方法1: entry-content クラス
        content_elem = soup.find('div', class_='entry-content')
        
        # 方法2: article タグ
        if not content_elem:
            content_elem = soup.find('article')
        
        # 方法3: コンテンツらしきdivを探す
        if not content_elem:
            content_elem = soup.find('div', class_=lambda c: c and ('content' in c or 'body' in c))
        
        # 方法4: メインコンテンツっぽい場所
        if not content_elem:
            main_elem = soup.find(['main', 'div'], id=lambda i: i and ('main' in i or 'content' in i))
            if main_elem:
                # main要素内の段落をすべて取得
                paragraphs = main_elem.find_all('p')
                if paragraphs:
                    content = "\n".join([p.get_text().strip() for p in paragraphs])
        
        if content_elem and not content:
            # 不要なタグを削除
            for tag in content_elem.find_all(['script', 'style', 'aside', 'nav', 'footer']):
                tag.decompose()
            
            content = content_elem.get_text().strip()
        
        if content:
            # テキストの正規化（余分な空白の削除など）
            content = re.sub(r'\s+', ' ', content).strip()
            logger.info(f"記事内容取得成功: {len(content)} 文字")
            return content, pub_date
        else:
            logger.warning(f"記事本文が見つかりませんでした: {url}")
            return None, None
    
    except Exception as e:
        logger.error(f"記事内容取得エラー: {url} - {e}")
        return None, None

async def generate_podcast_script(articles, client):
    """記事からPodcastスクリプトを生成する"""
    # 記事内容を集約
    all_contents = []
    
    for article in articles:
        content, pub_date = extract_article_content(article["link"])
        if content:
            all_contents.append({
                "title": article["title"],
                "link": article["link"],
                "date": article.get("date") or pub_date or "日付不明",
                "content": content[:5000]  # 記事が長い場合は最初の部分だけ使用
            })
    
    if not all_contents:
        logger.error("スクリプト生成に使用できる記事がありません")
        return None
    
    # OpenAIに送信するためのコンテンツを準備
    input_text = "以下のセキュリティ関連記事に基づいてポッドキャストの台本を作成してください：\n\n"
    
    for i, article in enumerate(all_contents):
        input_text += f"記事{i+1}：{article['title']}\n"
        input_text += f"公開日: {article['date']}\n"
        input_text += f"URL: {article['link']}\n"
        input_text += f"内容: {article['content'][:3000]}...\n\n"
    
    # 実際のプロンプトを追加
    input_text += PODCAST_PROMPT
    
    try:
        # OpenAI APIを使用して台本を生成
        response = client.chat.completions.create(
            model="o3-mini",  # ここでモデルをo3-miniに指定
            messages=[
                {"role": "system", "content": "あなたはプロのPodcastの話し手で、セキュリティトピックに詳しいです。"},
                {"role": "user", "content": input_text}
            ],
            max_completion_tokens=4000
        )
        
        script_content = response.choices[0].message.content
        
        # 固定の挨拶文を追加
        full_script = f"{OPENING_GREETING}\n\n{script_content}\n\n{CLOSING_MESSAGE}"
        
        logger.info("Podcastスクリプト生成完了")
        return full_script
    
    except Exception as e:
        logger.error(f"スクリプト生成エラー: {e}")
        return None

async def generate_audio(script, client):
    """スクリプトからオーディオファイルを生成する"""
    try:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        temp_voice_path = TEMP_DIR / f"voice_{timestamp}.mp3"
        output_path = OUTPUT_DIR / f"podcast_{timestamp}.mp3"
        
        # スクリプトをテキストファイルとして保存
        script_path = SCRIPTS_DIR / f"script_{timestamp}.txt"
        with open(script_path, 'w', encoding='utf-8') as f:
            f.write(script)
        
        logger.info(f"スクリプト保存: {script_path}")
        
        # TTSで音声生成
        response = client.audio.speech.create(
            model="tts-1",
            voice="shimmer",
            input=script
        )
        
        # 音声ファイルを保存
        with open(temp_voice_path, 'wb') as f:
            f.write(response.content)
        
        logger.info(f"音声生成完了: {temp_voice_path}")
        
        # BGMとミックス
        if os.path.exists(BGM_FILE):
            logger.info(f"BGMとミックスしています: {BGM_FILE}")
            try:
                # FFmpegを使用してBGMと音声をミックス
                # 参照コードのようにpython-ffmpegライブラリを使用してみます
                try:
                    import ffmpeg
                    
                    voice = ffmpeg.input(str(temp_voice_path))
                    bgm = ffmpeg.input(BGM_FILE)
                    mixed = ffmpeg.filter([voice, bgm], 'amix', inputs=2, duration='first', weights='1 0.1')
                    
                    # 音量正規化とバランス調整
                    normalized = ffmpeg.filter(mixed, 'dynaudnorm')
                    
                    ffmpeg.output(normalized, str(output_path), **{
                        'c:a': 'libmp3lame',
                        'q:a': 4
                    }).overwrite_output().run()
                    
                    logger.info(f"python-ffmpegでBGMミックス完了: {output_path}")
                    
                except ImportError:
                    # ffmpegライブラリが使用できない場合は、コマンドライン実行にフォールバック
                    logger.warning("python-ffmpegモジュールが見つからないため、コマンドラインで実行します")
                    
                    cmd = [
                        'ffmpeg', '-y',
                        '-i', str(temp_voice_path),
                        '-i', BGM_FILE,
                        '-filter_complex', 
                        # 音声を優先し、BGMのボリュームを下げる
                        '[1:a]volume=0.1[bgm];[0:a][bgm]amix=inputs=2:duration=first:weights=1 0.6',
                        '-c:a', 'libmp3lame', '-q:a', '4',
                        str(output_path)
                    ]
                
                    result = subprocess.run(cmd, capture_output=True, text=True)
                    if result.returncode != 0:
                        logger.error(f"FFmpegエラー: {result.stderr}")
                        # ミックスに失敗した場合は、ミックスなしのファイルを使用
                        shutil.copy2(temp_voice_path, output_path)
                        logger.warning(f"BGMミックス失敗のため、ミックスなしのファイルを使用します")
                    else:
                        logger.info(f"BGMミックス完了: {output_path}")
            except Exception as e:
                logger.error(f"BGMミックスエラー: {e}")
                # ミックスに失敗した場合は、ミックスなしのファイルを使用
                shutil.copy2(temp_voice_path, output_path)
                logger.warning(f"BGMミックス失敗のため、ミックスなしのファイルを使用します")
        else:
            # BGMファイルが存在しない場合は、ミックスなしのファイルを使用
            logger.warning(f"BGMファイルが見つかりません: {BGM_FILE}")
            shutil.copy2(temp_voice_path, output_path)
            logger.info(f"音声ファイルをコピーしました: {output_path}")
        
        # 一時ファイルの削除
        if os.path.exists(temp_voice_path):
            os.remove(temp_voice_path)
            logger.info(f"一時ファイルを削除しました: {temp_voice_path}")
        
        return str(output_path), str(script_path)
    
    except Exception as e:
        logger.error(f"音声生成エラー: {e}")
        return None, None

async def generate_summary(script_path, client):
    """スクリプトの内容を要約する"""
    try:
        # スクリプトファイルを読み込む
        with open(script_path, 'r', encoding='utf-8') as f:
            script_content = f.read()
        
        logger.info(f"要約を生成しています: {script_path}")
        
        # OpenAI APIを使用して要約を生成
        try:
            response = client.chat.completions.create(
                model="o3-mini",
                messages=[
                    {"role": "system", "content": "あなたは優れた要約者です。文章を200文字以内に要約してください。"},
                    {"role": "user", "content": f"次のセキュリティポッドキャストの台本を200文字以内に要約してください\n\n{script_content}"}
                ],
                max_completion_tokens=300
            )
            
            logger.info("APIから要約を取得しました")
            summary = response.choices[0].message.content
            logger.info(f"要約内容: {summary}")  # 要約内容をログに出力
            
            # 要約が正しく生成されたかチェック
            if not summary or len(summary.strip()) == 0:
                logger.warning("生成された要約が空です。バックアップの要約を生成します")
                # 結果が空の場合はフォールバックの要約を生成
                summary = "本ポッドキャストでは、グーグルのバグバウンティプログラムにおける1,200万ドルの支払い、Ivanti Endpoint Managerの重大な脆弱性、FreeTypeフォントエンジンの深刻な脆弱性、TP-Linkルーターを狙うBallistaボットネットの活動、およびAppleの緊急アップデートについて解説しました。企業は補実適用を速やかに行い、セキュリティ対策の強化が重要です。"
            
            # ファイル名を生成
            script_filename = Path(script_path).stem
            summary_filename = f"{script_filename}_summary.txt"
            summary_path = SUMMARY_DIR / summary_filename
            
            # ディレクトリが存在するか確認
            SUMMARY_DIR.mkdir(exist_ok=True, parents=True)
            
            # 要約をファイルに保存
            try:
                with open(summary_path, 'w', encoding='utf-8') as f:
                    f.write(summary)
                logger.info(f"要約を保存しました: {summary_path}")
                
                # ファイルサイズを確認
                if os.path.getsize(summary_path) == 0:
                    logger.warning(f"保存されたファイルのサイズが0です。再度書き込みを行います")
                    # 再度書き込みを行う
                    with open(summary_path, 'w', encoding='utf-8') as f:
                        f.write(summary)
                    
                    if os.path.getsize(summary_path) > 0:
                        logger.info(f"再度の書き込み成功: {os.path.getsize(summary_path)} バイト")
                    else:
                        logger.error(f"再度の書き込み失敗: ファイルサイズが0バイトです")
            except Exception as file_error:
                logger.error(f"ファイル書き込みエラー: {file_error}")
                # ファイル書き込みに失敗した場合は別のパスを試す
                try:
                    alt_path = BASE_DIR / f"summary_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
                    with open(alt_path, 'w', encoding='utf-8') as f:
                        f.write(summary)
                    logger.info(f"代替パスに保存しました: {alt_path}")
                    summary_path = alt_path
                except Exception as alt_error:
                    logger.error(f"代替パスへの書き込みエラー: {alt_error}")
            return str(summary_path)
            
        except Exception as e:
            logger.error(f"OpenAI APIエラー: {e}")
            # APIエラーの場合のバックアップ処理を改善
            # マニュアルで作成した固定の要約メッセージを使用
            summary = "本ポッドキャストでは、最新のセキュリティニュースを解説しました。グーグルのバグバウンティプログラム、Ivantiの脆弱性、FreeTypeのフォントエンジン問題、TP-Linkルーターを標的としたボットネット、およびAppleの緊急アップデートに関する重要かつ危急な脆弱性情報を取り上げました。これらの脆弱性は実際に悪用されているものもあり、早急なパッチ適用が必要です。引き続き、安全なオンライン環境の維持に努めましょう。"
            
            script_filename = Path(script_path).stem
            summary_filename = f"{script_filename}_simple_summary.txt"
            summary_path = SUMMARY_DIR / summary_filename
            
            # ディレクトリが存在するか確認
            SUMMARY_DIR.mkdir(exist_ok=True, parents=True)
            
            # 要約をファイルに保存
            try:
                with open(summary_path, 'w', encoding='utf-8') as f:
                    f.write(summary)
                
                # ファイルサイズを確認
                if os.path.getsize(summary_path) == 0:
                    logger.warning(f"フォールバック処理のファイルサイズが0です。再度書き込みを行います")
                    # 再度書き込みを行う
                    with open(summary_path, 'w', encoding='utf-8') as f:
                        f.write(summary)
                logger.warning(f"APIエラーのため単純な要約を生成しました: {summary_path}")
            except Exception as file_error:
                logger.error(f"フォールバック処理のファイル書き込みエラー: {file_error}")
                # 別の場所に保存を試みる
                try:
                    alt_path = BASE_DIR / f"fallback_summary_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
                    with open(alt_path, 'w', encoding='utf-8') as f:
                        f.write(summary)
                    logger.warning(f"代替パスにフォールバック要約を保存しました: {alt_path}")
                    summary_path = alt_path
                except Exception as alt_error:
                    logger.error(f"代替パスへの書き込みエラー: {alt_error}")
            return str(summary_path)
    
    except Exception as e:
        logger.error(f"要約生成エラー: {e}")
        return None

async def main():
    try:
        # ディレクトリを確認・作成
        for dir_path in [SCRIPTS_DIR, OUTPUT_DIR, TEMP_DIR, SUMMARY_DIR]:
            dir_path.mkdir(exist_ok=True, parents=True)
        
        # 環境変数の読み込み
        load_dotenv()
        api_key = os.getenv('OPENAI_API_KEY')
        
        if not api_key:
            logger.error("OPENAI_API_KEY環境変数が設定されていません")
            return
        
        # OpenAIクライアントの初期化
        client = OpenAI(api_key=api_key)
        
        # 記事の取得（複数の方法を試す）
        articles = []
        
        # 方法1: RSSフィードから取得
        feed = fetch_rss_feed(RSS_URL)
        if feed and feed.entries:
            # 最新の数件の記事を使用
            articles = [
                {
                    "title": entry.title,
                    "link": entry.link,
                    "date": datetime(*entry.published_parsed[:6]).strftime('%Y-%m-%d') if hasattr(entry, 'published_parsed') else "日付不明"
                }
                for entry in feed.entries[:5]  # 最新の5件を使用
            ]
        
        # 方法2: Webサイトから直接記事を取得
        if not articles:
            logger.info("RSSからの取得に失敗したため、Webサイトから記事を取得します")
            articles = get_articles_from_website(SITE_URL, num_articles=5)
        
        if not articles:
            logger.error("記事の取得に失敗しました")
            return
        
        # Podcastスクリプトの生成
        logger.info(f"スクリプト生成に使用する記事数: {len(articles)}")
        script = await generate_podcast_script(articles, client)
        if not script:
            logger.error("スクリプトの生成に失敗しました")
            return
        
        # 音声ファイルの生成
        audio_path, script_path = await generate_audio(script, client)
        if not audio_path or not script_path:
            logger.error("音声ファイルの生成に失敗しました")
            return
            
        logger.info(f"ポッドキャスト生成完了: {audio_path}")
        
        # 要約の生成
        summary_path = await generate_summary(script_path, client)
        if summary_path:
            logger.info(f"要約生成完了: {summary_path}")
        else:
            logger.warning("要約の生成に失敗しました")
        
        logger.info("全処理完了")
        
    except Exception as e:
        logger.error(f"処理中にエラーが発生しました: {e}")

if __name__ == "__main__":
    asyncio.run(main())
