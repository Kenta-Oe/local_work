import json
import os
from datetime import datetime, timedelta

class ArticleManager:
    def __init__(self, storage_file):
        self.storage_file = storage_file
        self.processed_articles = self._load_processed_articles()

    def _load_processed_articles(self):
        """保存済みの記事IDを読み込む"""
        if os.path.exists(self.storage_file):
            try:
                with open(self.storage_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except json.JSONDecodeError:
                print("記事履歴ファイルが破損しています。新規作成します。")
                return {}
        return {}

    def _save_processed_articles(self):
        """処理済み記事IDを保存"""
        with open(self.storage_file, 'w', encoding='utf-8') as f:
            json.dump(self.processed_articles, f, ensure_ascii=False, indent=2)

    def is_article_processed(self, article_id, article_url):
        """記事が既に処理済みかチェック"""
        return article_id in self.processed_articles

    def mark_article_as_processed(self, article_id, article_url, title):
        """記事を処理済みとしてマーク"""
        self.processed_articles[article_id] = {
            'url': article_url,
            'title': title,
            'processed_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        }
        self._save_processed_articles()

    def cleanup_old_entries(self, days=30):
        """30日以上前の記事を履歴から削除"""
        cutoff_date = datetime.now() - timedelta(days=days)
        current_entries = self.processed_articles.copy()
        
        for article_id, data in current_entries.items():
            processed_at = datetime.strptime(data['processed_at'], '%Y-%m-%d %H:%M:%S')
            if processed_at < cutoff_date:
                del self.processed_articles[article_id]
        
        self._save_processed_articles()