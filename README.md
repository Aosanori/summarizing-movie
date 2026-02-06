# summarize-movie

動画・音声ファイルを要約して議事録を生成するCLIツールです。文字起こしには mlx-whisper（Apple Silicon最適化）、要約には LM Studio のローカルLLMを使用し、完全にローカル環境で動作します。

## 特徴

- 🎥 動画・音声ファイルから自動で文字起こし（mlx-whisper / Apple Silicon最適化）
- 🤖 ローカルLLMで要約・議事録生成（LM Studio）
- 📝 Markdown / テキスト形式で出力
- 🔒 完全ローカル処理（インターネット接続不要）
- ⏱️ タイムスタンプ付きの文字起こし

## 対応ファイル形式

- **動画**: mp4, mov, avi, mkv, webm, m4v
- **音声**: mp3, wav, m4a, flac, ogg, aac, wma

## 前提条件

### 1. FFmpeg

動画から音声を抽出するために FFmpeg が必要です（Homebrew でインストールした場合は自動で入ります）。

```bash
brew install ffmpeg
```

### 2. LM Studio

1. [LM Studio](https://lmstudio.ai/) をダウンロードしてインストール
2. 任意のモデルをダウンロード（日本語対応モデル推奨）
3. 「Local Server」タブでサーバーを起動（デフォルト: `http://localhost:1234`）

### 3. Python 3.9以上（pip インストールの場合）

```bash
python --version  # 3.9以上であることを確認
```

## インストール

### Homebrew（推奨）

```bash
brew tap aosanori/tap
brew install summarize-movie
```

### pip

```bash
git clone https://github.com/Aosanori/summarizing-movie.git
cd summarizing-movie
pip install .
```

## 使用方法

### 基本的な使い方

```bash
# 動画ファイル
summarize-movie meeting.mp4

# 音声ファイル
summarize-movie recording.mp3
```

これにより、`meeting_summary_YYYYMMDD_HHMMSS.md` という名前で議事録が生成されます。

### オプション

```bash
# 出力ファイル名と形式を指定
summarize-movie meeting.mp4 -o meeting_notes.md -f markdown

# テキスト形式で出力
summarize-movie meeting.mp4 -f text

# より高精度なWhisperモデルを使用
summarize-movie meeting.mp4 --model large-v3

# 英語の動画を処理
summarize-movie presentation.mp4 --language en

# 音声ファイルを処理
summarize-movie podcast.m4a -v

# 詳細な出力を表示
summarize-movie meeting.mp4 -v
```

### 全オプション一覧

| オプション | 短縮形 | 説明 | デフォルト |
|-----------|-------|------|-----------|
| `--output` | `-o` | 出力ファイルパス | 自動生成 |
| `--format` | `-f` | 出力形式 (markdown/text) | markdown |
| `--model` | | Whisperモデルサイズ | large-v3-turbo |
| `--language` | `-l` | 文字起こし言語 | ja |
| `--lm-studio-url` | | LM Studio APIのURL | http://localhost:1234/v1 |
| `--device` | | 実行デバイス (auto/cpu/cuda) | auto |
| `--chunk-size` | | 要約時のチャンク分割サイズ（文字数） | 20000 |
| `--no-timestamps` | | タイムスタンプを含めない | false |
| `--verbose` | `-v` | 詳細な出力 | false |

### Whisperモデルサイズ（mlx-whisper）

| モデル | 精度 | 速度 | メモリ使用量 |
|--------|------|------|-----------|
| tiny | ★☆☆☆☆ | 最速 | ~1GB |
| base | ★★☆☆☆ | 速い | ~1GB |
| small | ★★★☆☆ | 普通 | ~2GB |
| medium | ★★★★☆ | 遅い | ~5GB |
| large-v3 | ★★★★★ | 高精度 | ~10GB |
| large-v3-turbo | ★★★★★ | **推奨** | ~6GB |

**注意**: Apple Silicon (M1/M2/M3/M4) Mac専用です。

## 出力例

### Markdown形式

```markdown
# 議事録: meeting.mp4

**作成日時**: 2024年01月15日 14:30  
**動画ファイル**: meeting.mp4  
**動画の長さ**: 45分30秒  
**検出言語**: ja

---

### 要約
本会議では、新プロジェクトの進捗状況と今後のスケジュールについて議論されました...

### 主要なポイント
- プロジェクトAは予定通り進行中
- 新機能のリリースは来月を予定
- ...

### アクションアイテム
- 田中: 設計書のレビューを今週中に完了
- 鈴木: テスト環境の構築を開始
- ...

---

## 文字起こし全文

[00:00:00] それでは会議を始めます...
[00:00:15] まず、プロジェクトの進捗について...
```

## トラブルシューティング

### LM Studioに接続できない

```
❌ エラー: LM Studioに接続できません。
```

→ LM Studioが起動しているか、Local Serverがアクティブか確認してください。

### モデルがロードされていない

```
RuntimeError: LM Studioにモデルがロードされていません。
```

→ LM Studioでモデルをロードしてから再実行してください。

### FFmpegが見つからない

```
FileNotFoundError: [Errno 2] No such file or directory: 'ffmpeg'
```

→ FFmpegをインストールしてください（前提条件を参照）。

### メモリ不足

→ より小さいWhisperモデル（`--model tiny` や `--model base`）を使用してください。

### 長い動画で要約がエラーになる

→ 長い動画は自動的にチャンク分割して処理されます。LM Studioのコンテキスト長が短い場合は、より大きなコンテキスト長でモデルをロードしてください。

## ライセンス

MIT License

