# mainの完全版を提供
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
