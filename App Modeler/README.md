# App Modeler プロジェクト

## はじめに

このプロジェクトは、[App Modeler](https://app-modeler.hexabase.com/c/usecases)というアプリケーション開発支援ツールを使用して作成されました。App Modelerは、システム設計からプロトタイプ作成までをサポートする統合開発プラットフォームです。このツールを活用することで、アプリケーションの設計定義からCloudFormationテンプレートの生成まで一貫したワークフローで開発を進めることができます。

## 概要

このリポジトリでは、AWSを基盤とするウェブサイト公開システムの設計とインフラストラクチャーコードを管理しています。主要なAWSサービス（CloudFront、API Gateway、EC2、Aurora PostgreSQL、ElastiCache、S3など）を活用し、スケーラブルで信頼性の高いEコマースウェブサイトの構築を目的としています。

システムは主にオンラインショッピングのユースケースに焦点を当てており、製品閲覧からチェックアウトまでの一連の機能と、それを支えるインフラストラクチャーが含まれています。

## フォルダ構成

このリポジトリは以下のフォルダ構成になっています：

```
App Modeler/
├── Cloudformation/          # CloudFormationテンプレートと解説
│   ├── cloudformation-template.txt        # メインのCloudFormationテンプレート
│   ├── Cloudformation初期設定.txt         # 初期設定に関する情報
│   └── explanation.txt                    # テンプレートの詳細解説
│
└── 設計定義/                # システム設計の定義ファイル
    ├── index.html                        # 設計ドキュメントのインデックス
    ├── システム企画書.html                # システム全体の概要と要件
    ├── MVP企画書.html                    # 最小実行可能製品の定義
    ├── ユースケース一覧.html              # ユーザーの利用シナリオ
    ├── 機能一覧.html                     # システムの主要機能の詳細
    ├── 画面一覧.html                     # ウェブサイトの画面構成
    ├── WF_1.html ~ WF_6.html            # 各画面のワイヤーフレーム
    ├── アクションフローチャート.html       # ユーザーの行動フロー
    ├── データベースドラフト.html           # データベース設計と構造
    └── テストケース一覧.html              # システムのテスト計画
```

## CloudFormation テンプレート

`Cloudformation`フォルダには、AWS環境に自動的にリソースをデプロイするためのCloudFormationテンプレートが含まれています。このテンプレートには以下の主要なAWSリソースが定義されています：

- **ネットワーク**: VPC、サブネット、インターネットゲートウェイ、NATゲートウェイ
- **コンピューティング**: EC2インスタンス（Auto Scaling Group）
- **データベース**: Aurora PostgreSQL
- **キャッシュ**: ElastiCache (Redis)
- **配信**: CloudFront、Application Load Balancer
- **API管理**: API Gateway
- **セキュリティ**: GuardDuty、セキュリティグループ
- **監視**: CloudWatch、SNS通知

詳細な説明は`explanation.txt`ファイルに記載されています。

## 設計定義

`設計定義`フォルダには、システムの設計に関する様々なドキュメントが含まれています。主な内容は以下の通りです：

### システム企画書・MVP企画書

これらのドキュメントでは、システムの概要、目的、要件（Must have/Should have/Could have/Won't have）、動機、制約、ターゲットユーザー、トラフィック予測、セキュリティ要件、パフォーマンス要件、監視項目などが定義されています。

### 機能一覧

システムの主要機能が定義されており、以下のような機能が含まれています：

- **ユーザー向け機能**: ウェブサイトアクセス、製品閲覧、ショッピングカート追加、チェックアウト、支払い情報入力、注文確定
- **インフラ機能**: コンテンツ配信、リクエスト受信、アプリケーション処理、データベース操作、キャッシュ処理、ログ保存、監視、異常通知

### データベースドラフト

データベース設計が定義されており、以下のテーブルが含まれています：

- **users**: ユーザー情報
- **products**: 製品情報
- **categories**: カテゴリ情報
- **product_categories**: 製品とカテゴリの関連付け
- **orders**: 注文情報
- **order_items**: 注文に含まれる製品の詳細
- **cart_items**: ショッピングカートの内容
- **reviews**: 製品レビュー

### ワイヤーフレームとフローチャート

`WF_1.html`から`WF_6.html`までのファイルには、各画面のワイヤーフレームが含まれています。また、`アクションフローチャート.html`にはユーザーの行動フローが定義されています。

## 技術スタック

本プロジェクトでは以下の技術スタックを使用しています：

### AWSサービス
- **CloudFront**: コンテンツ配信ネットワーク
- **API Gateway**: APIリクエスト処理
- **GuardDuty**: セキュリティ監視
- **EC2**: アプリケーションサーバー
- **Aurora PostgreSQL**: データベース
- **ElastiCache**: キャッシュサーバー
- **S3**: ストレージとログ保存
- **CloudWatch**: モニタリング
- **SNS**: 通知サービス

## システム要件

### パフォーマンス目標
- ページロード時間: 3秒以内
- サーバー応答時間: 200ミリ秒以内
- 最適化戦略: CDN利用、画像最適化、キャッシュ戦略

### セキュリティ対策
- SSL/TLS暗号化
- 二要素認証
- 定期的なセキュリティ監査
- GDPRおよびCCPA準拠のデータ保護

### 監視項目
- EC2インスタンス: CPU使用率、メモリ使用率、ディスクI/O、ネットワークトラフィック
- API Gateway: リクエスト数、エラーレート、レイテンシ

## 導入方法

システムはCloudFormationテンプレートを使用してデプロイできます。以下の手順に従ってください：

1. AWS Management Consoleにログイン
2. CloudFormationサービスに移動
3. 「スタックの作成」を選択
4. `Cloudformation/cloudformation-template.txt`をアップロード
5. 必要なパラメータを設定
6. スタックの作成を確認

詳細な導入方法や注意点については、`Cloudformation/explanation.txt`を参照してください。

## 注意点と改善ポイント

- **セキュリティ**: 本番環境では、SSH接続の制限やデータベースパスワードの管理などセキュリティの強化が必要です。
- **コスト最適化**: NATゲートウェイや常時有効なGuardDutyなど、コストを最適化する余地があります。
- **拡張性**: データベースのリードレプリカやElastiCacheの冗長性など、さらなる拡張性の向上が可能です。

## まとめ

このプロジェクトは、App Modelerを使用して設計からCloudFormationテンプレートの生成まで一貫して開発された、AWSベースのEコマースウェブサイト基盤です。システム設計とインフラコードを統合的に管理することで、効率的な開発と運用を実現します。