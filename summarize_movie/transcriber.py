"""mlx-whisperを使用した動画の文字起こしモジュール（Apple Silicon最適化）"""

from dataclasses import dataclass
from pathlib import Path

import mlx_whisper


@dataclass
class TranscriptSegment:
    """文字起こしセグメント"""

    start: float
    end: float
    text: str

    def format_timestamp(self) -> str:
        """タイムスタンプを HH:MM:SS 形式でフォーマット"""
        hours, remainder = divmod(int(self.start), 3600)
        minutes, seconds = divmod(remainder, 60)
        return f"{hours:02d}:{minutes:02d}:{seconds:02d}"


@dataclass
class TranscriptionResult:
    """文字起こし結果"""

    segments: list[TranscriptSegment]
    language: str
    duration: float

    @property
    def full_text(self) -> str:
        """全文を結合して返す"""
        return " ".join(seg.text.strip() for seg in self.segments)

    @property
    def text_with_timestamps(self) -> str:
        """タイムスタンプ付きのテキストを返す"""
        lines = []
        for seg in self.segments:
            timestamp = seg.format_timestamp()
            lines.append(f"[{timestamp}] {seg.text.strip()}")
        return "\n".join(lines)


class Transcriber:
    """動画/音声ファイルを文字起こしするクラス（mlx-whisper使用）"""

    # mlx-whisperで使用可能なモデル
    MODEL_MAP = {
        "tiny": "mlx-community/whisper-tiny-mlx",
        "base": "mlx-community/whisper-base-mlx",
        "small": "mlx-community/whisper-small-mlx",
        "medium": "mlx-community/whisper-medium-mlx",
        "large": "mlx-community/whisper-large-v3-mlx",
        "large-v3": "mlx-community/whisper-large-v3-mlx",
        "large-v3-turbo": "mlx-community/whisper-large-v3-turbo",
    }

    def __init__(
        self,
        model_size: str = "large-v3-turbo",
        **kwargs,  # 互換性のため他の引数を受け取る
    ):
        """
        Args:
            model_size: Whisperモデルサイズ (tiny, base, small, medium, large, large-v3, large-v3-turbo)
        """
        if model_size not in self.MODEL_MAP:
            raise ValueError(
                f"サポートされていないモデル: {model_size}. "
                f"使用可能: {', '.join(self.MODEL_MAP.keys())}"
            )

        self.model_size = model_size
        self.model_path = self.MODEL_MAP[model_size]

    def transcribe(
        self,
        file_path: str | Path,
        language: str | None = "ja",
        **kwargs,  # 互換性のため他の引数を受け取る
    ) -> TranscriptionResult:
        """
        動画/音声ファイルを文字起こし

        Args:
            file_path: 動画または音声ファイルのパス
            language: 言語コード (例: "ja", "en")。Noneで自動検出

        Returns:
            TranscriptionResult: 文字起こし結果
        """
        file_path = Path(file_path)
        if not file_path.exists():
            raise FileNotFoundError(f"ファイルが見つかりません: {file_path}")

        # mlx_whisperで文字起こし
        result = mlx_whisper.transcribe(
            str(file_path),
            path_or_hf_repo=self.model_path,
            language=language,
            verbose=False,
        )

        # セグメントを変換
        segments = []
        for seg in result.get("segments", []):
            segments.append(
                TranscriptSegment(
                    start=seg["start"],
                    end=seg["end"],
                    text=seg["text"],
                )
            )

        # 動画の長さを計算
        duration = 0.0
        if segments:
            duration = segments[-1].end

        return TranscriptionResult(
            segments=segments,
            language=result.get("language", language or "unknown"),
            duration=duration,
        )
