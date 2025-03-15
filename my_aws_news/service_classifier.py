def load_service_list(filepath: str):
    """
    サービスリストをロードし、完全一致用の辞書を作成
    """
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            services = [line.strip() for line in f if line.strip() and not line.startswith('#')]
            return services
    except FileNotFoundError:
        print(f"Service list file not found: {filepath}")
        return []

def find_service_for_article(services, title: str) -> str:
    """
    タイトルに含まれるサービス名を完全一致で検索
    """
    for service in services:
        if service in title:
            print(f"サービス名 '{service}' がタイトルで一致しました")
            return service
    
    return "Other"