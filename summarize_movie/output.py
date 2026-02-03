"""出力フォーマット処理モジュール"""

from datetime import datetime
from pathlib import Path
from typing import Literal

from .summarizer import SummaryResult
from .transcriber import TranscriptionResult


OutputFormat = Literal["markdown", "text"]

# 音声ファイルの拡張子
AUDIO_EXTENSIONS = {".mp3", ".wav", ".m4a", ".flac", ".ogg", ".aac", ".wma"}


class OutputFormatter:
    """議事録の出力フォーマットを処理するクラス"""

    def __init__(
        self,
        video_path: str | Path,
        transcription: TranscriptionResult,
        summary_content: str,
    ):
        """
        Args:
            video_path: 元の動画/音声ファイルパス
            transcription: 文字起こし結果
            summary_content: 要約内容（LLMからの生のレスポンス）
        """
        self.video_path = Path(video_path)
        self.transcription = transcription
        self.summary_content = summary_content
        self.created_at = datetime.now()
        # メディアタイプを判別
        self.is_audio = self.video_path.suffix.lower() in AUDIO_EXTENSIONS
        self.media_label = "音声ファイル" if self.is_audio else "動画ファイル"
        self.duration_label = "音声の長さ" if self.is_audio else "動画の長さ"

    def format(self, output_format: OutputFormat = "markdown") -> str:
        """
        指定されたフォーマットで出力を生成

        Args:
            output_format: 出力形式 ("markdown" or "text")

        Returns:
            str: フォーマットされた出力
        """
        if output_format == "markdown":
            return self._format_markdown()
        else:
            return self._format_text()

    def _format_markdown(self) -> str:
        """Markdown形式で出力を生成"""
        duration_str = self._format_duration(self.transcription.duration)

        # 話者情報がある場合は追加
        speaker_info = ""
        if self.transcription.has_speakers:
            speakers = self.transcription.speakers
            speaker_info = f"**話者**: {', '.join(speakers)}  \n"

        output = f"""# 議事録: {self.video_path.name}

**作成日時**: {self.created_at.strftime("%Y年%m月%d日 %H:%M")}  
**{self.media_label}**: {self.video_path.name}  
**{self.duration_label}**: {duration_str}  
**検出言語**: {self.transcription.language}  
{speaker_info}
---

{self.summary_content}

---

## 文字起こし全文

{self.transcription.text_with_timestamps}
"""
        return output

    def _format_text(self) -> str:
        """プレーンテキスト形式で出力を生成"""
        duration_str = self._format_duration(self.transcription.duration)

        # Markdownの記号を除去してプレーンテキストに変換
        summary_text = self._strip_markdown(self.summary_content)

        # 話者情報がある場合は追加
        speaker_info = ""
        if self.transcription.has_speakers:
            speakers = self.transcription.speakers
            speaker_info = f"話者: {', '.join(speakers)}\n"

        output = f"""議事録: {self.video_path.name}

作成日時: {self.created_at.strftime("%Y年%m月%d日 %H:%M")}
{self.media_label}: {self.video_path.name}
{self.duration_label}: {duration_str}
検出言語: {self.transcription.language}
{speaker_info}
{"=" * 50}

{summary_text}

{"=" * 50}

文字起こし全文

{self.transcription.text_with_timestamps}
"""
        return output

    def _format_duration(self, seconds: float) -> str:
        """秒数を読みやすい形式に変換"""
        hours, remainder = divmod(int(seconds), 3600)
        minutes, secs = divmod(remainder, 60)

        if hours > 0:
            return f"{hours}時間{minutes}分{secs}秒"
        elif minutes > 0:
            return f"{minutes}分{secs}秒"
        else:
            return f"{secs}秒"

    def _strip_markdown(self, text: str) -> str:
        """Markdown記法を除去してプレーンテキストに変換"""
        lines = []
        for line in text.split("\n"):
            # ヘッダーの#を除去
            if line.startswith("#"):
                line = line.lstrip("#").strip()

            # 太字・斜体の記号を除去
            line = line.replace("**", "").replace("*", "").replace("__", "")

            lines.append(line)

        return "\n".join(lines)

    def save(
        self,
        output_path: str | Path | None = None,
        output_format: OutputFormat = "markdown",
    ) -> Path:
        """
        フォーマットされた出力をファイルに保存

        Args:
            output_path: 出力先パス（Noneの場合は自動生成）
            output_format: 出力形式

        Returns:
            Path: 保存されたファイルのパス
        """
        if output_path is None:
            # 出力パスを自動生成
            extension = ".md" if output_format == "markdown" else ".txt"
            timestamp = self.created_at.strftime("%Y%m%d_%H%M%S")
            output_path = self.video_path.parent / f"{self.video_path.stem}_summary_{timestamp}{extension}"
        else:
            output_path = Path(output_path)

        content = self.format(output_format)
        output_path.write_text(content, encoding="utf-8")

        return output_path


def generate_output(
    video_path: str | Path,
    transcription: TranscriptionResult,
    summary_content: str,
    output_path: str | Path | None = None,
    output_format: OutputFormat = "markdown",
) -> Path:
    """
    議事録を生成してファイルに保存するヘルパー関数

    Args:
        video_path: 元の動画ファイルパス
        transcription: 文字起こし結果
        summary_content: 要約内容
        output_path: 出力先パス
        output_format: 出力形式

    Returns:
        Path: 保存されたファイルのパス
    """
    formatter = OutputFormatter(video_path, transcription, summary_content)
    return formatter.save(output_path, output_format)

