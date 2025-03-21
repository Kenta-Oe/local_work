# セキュリティ関連ポッドキャスト生成ツール

このツールは、指定されたRSSフィードから最新のセキュリティ関連記事を取得し、OpenAI APIを使用してポッドキャスト用の台本を作成し、音声ファイルを生成します。

## セットアップ

1. 必要なライブラリをインストールします：
   ```
   pip install -r requirements.txt
   ```

2. OpenAI APIキーを設定します。`.env`ファイルにAPI keyを記載してください：
   ```
   OPENAI_API_KEY=your_openai_api_key_here
   ```

3. FFmpegをインストールしてください。音声とBGMのミックスに必要です。
   - Windowsの場合は、[FFmpeg公式サイト](https://ffmpeg.org/download.html)からダウンロードし、PATH環境変数に追加してください。

## 使い方

以下のコマンドを実行して、ポッドキャストを生成します：

```
python main.py
```

- このスクリプトは、指定されたRSSフィード（デフォルトでは https://rocket-boys.co.jp/security-measures-lab/feed/）から昨日の記事を取得します。
- 昨日の記事が見つからない場合は、最新の記事を使用します。
- OpenAIのo3-miniモデルを使って4000文字程度のポッドキャスト台本を生成します。
- OpenAIのTTS（Text-to-Speech）を使用して音声ファイルを生成します。

## 出力ファイル

- 生成された台本は `scripts` ディレクトリに保存されます。
- 生成された音声ファイルは `output` ディレクトリに保存されます。
- 一時ファイルは `temp` ディレクトリに保存されます。

## カスタマイズ

`main.py` ファイルを編集することで、以下の設定をカスタマイズできます：

- RSS_URL: 取得するRSSフィードのURL
- OPENING_GREETING: ポッドキャストの冒頭の挨拶
- CLOSING_MESSAGE: ポッドキャストの締めくくりのメッセージ
- TTSの音声タイプ（デフォルトは"shimmer"）
- BGMのミキシング設定（ウェイトや音量）

## 注意点

- このツールはOpenAI APIを使用するため、API使用料が発生します。
- 大量の記事や長い台本を処理する場合は、APIの使用料が高くなる可能性があります。
#   l o c a l _ w o r k  
 