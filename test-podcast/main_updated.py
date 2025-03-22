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

# 過去に使用した記事の記録ファイル
USED_ARTICLES_FILE = BASE_DIR / "used_articles.json"

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

def load_used_articles():
    """過去に使用した記事のURLリストを読み込む"""
    if os.path.exists(USED_ARTICLES_FILE):
        try:
            with open(USED_ARTICLES_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"過去の記事読み込みエラー: {e}")
    return {"urls": [], "last_updated": ""}

def save_used_articles(articles):
    """使用した記事のURLを保存する"""
    try:
        # 過去のデータを読み込む
        used_data = load_used_articles()
        
        # 新しいURLを追加
        for article in articles:
            if article["link"] not in used_data["urls"]:
                used_data["urls"].append(article["link"])
        
        # 最終更新日時を更新
        used_data["last_updated"] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        # 100件を超える場合は古いものから削除
        if len(used_data["urls"]) > 100:
            used_data["urls"] = used_data["urls"][-100:]
        
        # 更新したデータを保存
        with open(USED_ARTICLES_FILE, 'w', encoding='utf-8') as f:
            json.dump(used_data, f, ensure_ascii=False, indent=2)
            
        logger.info(f"使用済み記事を更新しました: 合計{len(used_data['urls'])}件")
    except Exception as e:
        logger.error(f"使用済み記事の保存エラー: {e}")

def filter_articles_by_date(articles, target_date=None):
    """指定日付の記事だけをフィルタリングする
    target_dateが指定されていない場合は昨日の記事を使用する
    """
    if target_date is None:
        target_date = get_yesterday_date()
    
    logger.info(f"フィルタリング対象日付: {target_date}")
    
    # 日付のフォーマットに関わらず照合するため、日付の一部を指定日付と比較
    filtered_articles = []
    for article in articles:
        article_date = article.get("date")
        if article_date and target_date in article_date:
            filtered_articles.append(article)
    
    logger.info(f"日付フィルタリング結果: {len(filtered_articles)}件の記事が該当 ({target_date})")
    return filtered_articles

def filter_unused_articles(articles):
    """過去に使用していない記事だけをフィルタリングする"""
    used_data = load_used_articles()
    used_urls = used_data["urls"]
    
    unused_articles = [article for article in articles if article["link"] not in used_urls]
    
    logger.info(f"未使用記事フィルタリング結果: {len(unused_articles)}件の新しい記事が利用可能 (全{len(articles)}件中)")
    return unused_articles

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
        # scriptsディレクトリから最新のスクリプトファイルを取得
        if not os.path.exists(script_path):
            logger.warning(f"指定されたスクリプトファイルが存在しません: {script_path}")
            # scriptsディレクトリから最新のファイルを探す
            script_files = list(SCRIPTS_DIR.glob('*.txt'))
            if not script_files:
                logger.error("scriptsディレクトリにスクリプトファイルが見つかりません")
                return None
            
            # 最新のファイルを選択
            latest_script = max(script_files, key=os.path.getmtime)
            script_path = str(latest_script)
            logger.info(f"最新のスクリプトファイルを使用します: {script_path}")
        
        # スクリプトファイルを読み込む
        with open(script_path, 'r', encoding='utf-8') as f:
            script_content = f.read()
        
        logger.info(f"要約を生成しています: {script_path}")
        
        # OpenAI APIを使用して要約を生成
        try:
            response = client.chat.completions.create(
                model="o3-mini",
                messages=[
                    {"role": "system", "content": "あなたは優れた要約者です。文章を200文字以内に要約してください。セキュリティに関する具体的なトピック、企業名、脆弱性の種類、重要なポイントを盛り込んだ内容にしてください。"},
                    {"role": "user", "content": f"次のセキュリティポッドキャストの台本について:\n1. 登場する企業名や組織名を必ず含める\n2. 具体的な脆弱性の種類や攻撃手法を含める\n3. 合計200文字以内で要約する\n\n台本内容:\n{script_content}"}
                ],
                max_completion_tokens=300
            )
            
            logger.info("APIから要約を取得しました")
            summary = response.choices[0].message.content
            logger.info(f"要約内容: {summary}")  # 要約内容をログに出力
            
            # 要約が明らかに不十分な場合のみチェックと再生成を行う
            if not summary or len(summary.strip()) < 20 or "本ポッドキャストでは、最新のセキュリティニュースを解説しました" in summary:
                logger.warning("生成された要約が不十分です。詳細なバックアップ要約を生成します")
                # より詳細なバックアップ要約を生成
                content_text = re.sub(r'\s+', ' ', script_content).strip()
                
                # スクリプトから重要なキーワードを抽出（セキュリティ関連用語）
                keywords = []
                security_terms = ["脆弱性", "サイバー攻撃", "マルウェア", "ランサムウェア", "フィッシング", "ゼロデイ", "不正アクセス", "データ漏洩", 
                                "MITM", "AITM", "中間者攻撃", "DDoS", "SQLインジェクション", "XSS", "クロスサイトスクリプティング", "バッファオーバーフロー"]
                
                for term in security_terms:
                    if term in content_text:
                        keywords.append(term)
                
                # 企業名・組織名を探す (よく出てくる組織名)
                orgs = ["KDDI", "ソフトバンク", "NTT", "楽天", "Google", "Microsoft", "Apple", "Meta", "Twitter", "X", "OpenAI", 
                       "JPCERT", "IPA", "NISC", "TP-Link", "Cisco", "IBM", "AWS", "Amazon", "Firebase", "Cloudflare"]
                found_orgs = [org for org in orgs if org in content_text]
                
                # 製品やサービスの名前を探す
                products = ["Windows", "macOS", "iOS", "Android", "Chrome", "Firefox", "Safari", "Edge", "Office", 
                           "Azure", "AWS", "ChatGPT", "Gmail", "Google Workspace", "Slack", "Teams", "Zoom", "ホームゲートウェイ", "Wi-Fiルーター"]
                found_products = [product for product in products if product in content_text]
                
                # キーワードと組織名と製品名から要約を構成
                if keywords and (found_orgs or found_products):
                    topics = "、".join(keywords[:3])
                    entities = list(set(found_orgs + found_products))[:3]
                    entities_text = "、".join(entities)
                    summary = f"本ポッドキャストでは、{entities_text}に関連する{topics}について詳細に解説しました。セキュリティインシデントの具体的な手法分析と、ユーザーが実践できる効果的な対策方法を紹介しています。"
                elif keywords:
                    # 組織名や製品名が見つからない場合はキーワードだけで構成
                    topics = "、".join(keywords[:4])
                    summary = f"本ポッドキャストでは、{topics}に関する最新のセキュリティ情報を解説しました。攻撃手法の仕組みやその影響、効果的な対策について詳細な情報を提供しています。"
                else:
                    # スクリプトから具体的な内容を抽出する試み
                    # OPENING_GREETINGとCLOSING_MESSAGEを除外
                    main_content = content_text.replace(OPENING_GREETING, "").replace(CLOSING_MESSAGE, "")
                    
                    # 最初の段落で具体的な内容を見つける
                    sentences = main_content.split("。")
                    content_sentences = [s for s in sentences[:5] if len(s) > 10 and not s.startswith("こんにちは") and not s.startswith("ようこそ")]
                    
                    if content_sentences:
                        first_para = content_sentences[0] + "。"
                        summary = f"本ポッドキャストでは、最新のセキュリティトピックについて解説しました。{first_para}"
                    else:
                        # それでも見つからない場合は一般的な文言で
                        summary = "本ポッドキャストでは、最新のセキュリティ脅威と対策について解説しました。サイバー攻撃の手法やその影響、効果的な防御策について詳細な情報を提供しています。"
                
                if len(summary) > 200:
                    summary = summary[:197] + "..."
                    
                logger.info(f"バックアップ要約を生成しました: {summary}")
            
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
            # APIエラーの場合、スクリプトから直接要約を生成
            # スクリプトの内容から重要なキーワードを抽出
            topics = []
            if "AITM" in script_content or "中間者攻撃" in script_content:
                topics.append("中間者攻撃(AITM)")
            if "KDDI" in script_content or "ホームゲートウェイ" in script_content:
                topics.append("KDDIのホームゲートウェイ脆弱性")
            if "TP-Link" in script_content or "Wi-Fiルーター" in script_content:
                topics.append("TP-Linkルーターの脆弱性")
            if "楽天モバイル" in script_content:
                topics.append("楽天モバイルへの不正アクセス")
            if "OpenAI" in script_content or "ChatGPT" in script_content:
                topics.append("ChatGPTインフラの脆弱性")
            
            # トピックが見つからない場合はスクリプトをより詳細に分析
            if not topics:
                # もっと広範なキーワードで検索 (前回の検索よりも対象を広げる)
                security_terms = ["脆弱性", "攻撃", "マルウェア", "ランサムウェア", "フィッシング", "セキュリティ", "ハッキング", "不正", "漏洩", 
                                  "インシデント", "パッチ", "更新", "対策", "防御", "暗号", "認証", "アクセス制御", "ファイアウォール", "VPN", 
                                  "バックドア", "ボット", "ウイルス", "トロイの木馬", "スパイウェア", "DoS", "DDoS"]
                found_terms = []
                
                for term in security_terms:
                    if term in script_content:
                        found_terms.append(term)
                
                # 企業名や組織名を検索 (より高度な検出パターン)
                # 大文字始まりの英語の組織名や、日本語の組織名パターンを探す
                company_patterns = [
                    r'([A-Z][A-Za-z]+\s*[A-Za-z]*)',  # 英語の組織名 (例: Microsoft, Google Cloud)
                    r'([ぁ-んァ-ン一-龥]{2,}(株式会社|社|グループ|サービス|会社))',  # 日本語の組織名
                    r'([ぁ-んァ-ン一-龥]{1,}[A-Za-z]+)'  # 日本語+英語の混合 (例: 楽天モバイル)
                ]
                
                all_companies = []
                for pattern in company_patterns:
                    matches = re.findall(pattern, script_content)
                    if matches:
                        for match in matches:
                            if isinstance(match, tuple):
                                all_companies.append(match[0])
                            else:
                                all_companies.append(match)
                
                # フィルタリング - 一般的なトークンを除外
                exclude_words = ["The", "This", "That", "These", "Those", "We", "Our", "You", "Your", "They", "Their", 
                                "今日", "皆さん", "私", "方法", "情報", "内容", "対策", "今回", "問題", "利用", "技術", "機能"]
                company_names = [c for c in all_companies if c not in exclude_words and len(c) > 1]
                
                # 重複除去と上位の企業名取得
                unique_companies = []
                for c in company_names:
                    if c not in unique_companies:
                        unique_companies.append(c)
                        if len(unique_companies) >= 3:  # 最大3つまで
                            break
                
                # 製品名や技術名も探す
                tech_terms = ["Windows", "macOS", "Linux", "iOS", "Android", "Chrome", "Firefox", "Safari", "Edge", 
                             "Office", "Teams", "Zoom", "Azure", "AWS", "GCP", "ChatGPT", "Wi-Fi", "Bluetooth", "VPN", 
                             "ファイアウォール", "ルーター", "スマートフォン", "PC", "サーバー"]
                found_tech = [term for term in tech_terms if term in script_content]
                
                if found_terms and (unique_companies or found_tech):
                    terms_text = "、".join(found_terms[:3])
                    entities = unique_companies + found_tech
                    if entities:
                        entities_text = "、".join(entities[:3])
                        summary = f"本ポッドキャストでは、{entities_text}に関連する{terms_text}について詳しく解説しています。具体的な脅威の事例分析や、効果的な防御策を実践的に紹介しています。"
                    else:
                        summary = f"本ポッドキャストでは、{terms_text}に関する最新情報を詳細に解説しました。重要なセキュリティインシデントの分析と効果的な対策方法を提示しています。"
                else:
                    # 最終手段：スクリプトの重要な部分を抽出
                    opening_part = script_content.replace(OPENING_GREETING, "").replace(CLOSING_MESSAGE, "").strip()
                    
                    # 文章を分割して具体的な内容を持つ文を探す
                    sentences = re.split(r'。|\.|！|\!', opening_part)
                    content_sentences = [s.strip() for s in sentences if len(s.strip()) > 15]
                    
                    if content_sentences:
                        # 最初の具体的な文を基に要約を作成
                        first_meaningful_sentence = content_sentences[0] + "。"
                        summary = f"本ポッドキャストでは、最新のセキュリティトピックについて解説しました。{first_meaningful_sentence}"
                    else:
                        # どうしても具体的な内容が抽出できない場合の最終手段
                        summary = "本ポッドキャストでは、最新のサイバーセキュリティ脅威と防御策について詳細に解説しています。企業やユーザーが直面する具体的なリスクと、実践可能な対策方法を紹介しています。"
            else:
                topic_text = "、".join(topics)
                summary = f"本ポッドキャストでは、{topic_text}について詳細に解説しました。各脆弱性や攻撃手法の仕組みと効果的な対策方法を紹介し、パッチ適用や設定見直しの重要性を強調しています。"
            
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
                logger.warning(f"APIエラーのためスクリプト内容から要約を生成しました: {summary_path}")
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
        
        # コマンドライン引数でスクリプトだけの処理を行うかチェック
        import sys
        generate_summary_only = '--summary-only' in sys.argv
        
        if generate_summary_only:
            logger.info("要約生成のみのモードで実行します")
            # scriptsディレクトリから最新のスクリプトを取得
            script_files = list(SCRIPTS_DIR.glob('*.txt'))
            if not script_files:
                logger.error("scriptsディレクトリにスクリプトファイルが見つかりません")
                return
            
            # 最新のファイルを使用
            latest_script = max(script_files, key=os.path.getmtime)
            logger.info(f"最新のスクリプトファイルを使用します: {latest_script}")
            
            # 要約のみ生成
            summary_path = await generate_summary(str(latest_script), client)
            if summary_path:
                logger.info(f"要約生成完了: {summary_path}")
            else:
                logger.warning("要約の生成に失敗しました")
            
            return
        
        # 通常の処理（記事取得から始める）
        articles = []
        
        # 方法1: RSSフィードから取得
        feed = fetch_rss_feed(RSS_URL)
        if feed and feed.entries:
            # 記事情報を取得
            all_articles = [{
                "title": entry.title,
                "link": entry.link,
                "date": datetime(*entry.published_parsed[:6]).strftime('%Y-%m-%d') if hasattr(entry, 'published_parsed') else "日付不明"
            } for entry in feed.entries]  # 全ての記事を取得
            
            # 昨日の記事だけをフィルタリング
            target_date = get_yesterday_date()
            filtered_articles = filter_articles_by_date(all_articles, target_date)
            
            # 過去に使用していない記事だけを取得
            articles = filter_unused_articles(filtered_articles)
            
            # 昨日の記事がないか、既に使用済みの記事しかない場合は、フィルターを緩和する
            if not articles:
                logger.warning(f"昨日 ({target_date}) の未使用記事が見つかりません。直近の記事を使用します")
                # 最新で未使用の記事を最大5件取得
                unused_articles = filter_unused_articles(all_articles)
                articles = unused_articles[:5]
        
        # 方法2: Webサイトから直接記事を取得
        if not articles:
            logger.info("RSSからの取得に失敗したため、Webサイトから記事を取得します")
            website_articles = get_articles_from_website(SITE_URL, num_articles=10)  # 最大5件で3件→上限を多めに設定
            
            # 過去に使用していない記事だけをフィルタリング
            unused_website_articles = filter_unused_articles(website_articles)
            articles = unused_website_articles[:5]  # 最大5件使用
        
        if not articles:
            logger.error("使用可能な記事が見つかりませんでした")
            return
        
        # 使用する記事の最終確認
        if len(articles) > 3:
            # 記事数が多い場合は3件に絞る
            logger.info(f"{len(articles)}件の記事が見つかりましたが、3件に絞ります")
            articles = articles[:3]
        
        # 使用する記事情報を記録
        logger.info(f"スクリプト生成に使用する記事数: {len(articles)}")
        for i, article in enumerate(articles):
            logger.info(f"  {i+1}. {article['title']} ({article['date']})")
        
        # Podcastスクリプトの生成
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
        
        # 使用した記事を保存
        save_used_articles(articles)
        
        logger.info("全処理完了")
        
    except Exception as e:
        logger.error(f"処理中にエラーが発生しました: {e}")

if __name__ == "__main__":
    asyncio.run(main())
