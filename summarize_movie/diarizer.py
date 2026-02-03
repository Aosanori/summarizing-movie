"""pyannote.audioを使用した話者分離モジュール"""

import os
import subprocess
import tempfile
import warnings
from dataclasses import dataclass
from pathlib import Path

import torch

# 警告を抑制
warnings.filterwarnings("ignore", category=UserWarning, module="pyannote")
warnings.filterwarnings("ignore", category=UserWarning, module="speechbrain")
warnings.filterwarnings("ignore", category=UserWarning, module="torchaudio")
warnings.filterwarnings("ignore", category=FutureWarning)

# PyTorch 2.6+のweights_only制限を緩和（pyannoteモデルの読み込みに必要）
# pytorch_lightningがtorch.loadを呼び出す際にweights_only=Falseを使用するように設定
import lightning_fabric.utilities.cloud_io as _cloud_io
_original_load = _cloud_io._load

def _patched_load(path_or_url, map_location=None, weights_only=None):
    # pyannoteのモデル読み込みではweights_only=Falseが必要
    return _original_load(path_or_url, map_location=map_location, weights_only=False)

_cloud_io._load = _patched_load


@dataclass
class DiarizationSegment:
    """話者分離セグメント"""

    start: float
    end: float
    speaker: str


class Diarizer:
    """pyannote.audioを使用して話者分離を行うクラス"""

    def __init__(
        self,
        hf_token: str | None = None,
        num_speakers: int | None = None,
        min_speakers: int | None = None,
        max_speakers: int | None = None,
        device: str = "auto",
    ):
        """
        Args:
            hf_token: Hugging Face認証トークン（環境変数HF_TOKENでも可）
            num_speakers: 話者数（既知の場合）
            min_speakers: 最小話者数
            max_speakers: 最大話者数
            device: 実行デバイス ("auto", "cpu", "cuda", "mps")
        """
        self.hf_token = hf_token or os.environ.get("HF_TOKEN")
        if not self.hf_token:
            raise ValueError(
                "Hugging Face認証トークンが必要です。"
                "--hf-token オプションまたは環境変数 HF_TOKEN を設定してください。"
            )

        self.num_speakers = num_speakers
        self.min_speakers = min_speakers
        self.max_speakers = max_speakers
        self.device = self._get_device(device)
        self._pipeline = None

    def _get_device(self, device: str) -> torch.device:
        """実行デバイスを決定"""
        if device == "auto":
            if torch.cuda.is_available():
                return torch.device("cuda")
            elif torch.backends.mps.is_available():
                return torch.device("mps")
            else:
                return torch.device("cpu")
        return torch.device(device)

    def _get_pipeline(self):
        """pyannoteパイプラインを遅延初期化"""
        if self._pipeline is None:
            from pyannote.audio import Pipeline

            self._pipeline = Pipeline.from_pretrained(
                "pyannote/speaker-diarization-3.1",
                use_auth_token=self.hf_token,
            )
            self._pipeline.to(self.device)
        return self._pipeline

    def _extract_audio(self, video_path: Path) -> Path:
        """
        動画ファイルから音声を抽出

        Args:
            video_path: 動画ファイルのパス

        Returns:
            抽出された音声ファイルのパス
        """
        # 一時ファイルとして音声を抽出
        audio_path = video_path.parent / f"{video_path.stem}_audio.wav"

        # ffmpegで音声を抽出（16kHz, モノラル）
        cmd = [
            "ffmpeg", "-y",
            "-i", str(video_path),
            "-vn",  # 映像なし
            "-acodec", "pcm_s16le",  # 16bit PCM
            "-ar", "16000",  # 16kHz
            "-ac", "1",  # モノラル
            str(audio_path)
        ]

        try:
            subprocess.run(cmd, check=True, capture_output=True)
        except subprocess.CalledProcessError as e:
            raise RuntimeError(f"音声抽出に失敗しました: {e.stderr.decode()}")
        except FileNotFoundError:
            raise RuntimeError(
                "ffmpegが見つかりません。ffmpegをインストールしてください。\n"
                "macOS: brew install ffmpeg"
            )

        return audio_path

    def diarize(self, media_path: str | Path) -> list[DiarizationSegment]:
        """
        音声/動画ファイルの話者分離を実行

        Args:
            media_path: 音声または動画ファイルのパス

        Returns:
            話者分離セグメントのリスト
        """
        media_path = Path(media_path)
        if not media_path.exists():
            raise FileNotFoundError(f"ファイルが見つかりません: {media_path}")

        # 動画ファイルの場合は音声を抽出
        video_extensions = {".mp4", ".mov", ".avi", ".mkv", ".webm", ".m4v"}
        if media_path.suffix.lower() in video_extensions:
            audio_path = self._extract_audio(media_path)
            cleanup_audio = True
        else:
            audio_path = media_path
            cleanup_audio = False

        try:
            pipeline = self._get_pipeline()

            # 話者数の設定
            kwargs = {}
            if self.num_speakers is not None:
                kwargs["num_speakers"] = self.num_speakers
            if self.min_speakers is not None:
                kwargs["min_speakers"] = self.min_speakers
            if self.max_speakers is not None:
                kwargs["max_speakers"] = self.max_speakers

            # 進捗表示付きで話者分離を実行
            from pyannote.audio.pipelines.utils.hook import ProgressHook
            with ProgressHook() as hook:
                diarization = pipeline(str(audio_path), hook=hook, **kwargs)
        finally:
            # 一時音声ファイルを削除
            if cleanup_audio and audio_path.exists():
                audio_path.unlink()

        # 結果をセグメントリストに変換
        segments = []
        for turn, _, speaker in diarization.itertracks(yield_label=True):
            segments.append(
                DiarizationSegment(
                    start=turn.start,
                    end=turn.end,
                    speaker=speaker,
                )
            )

        return segments

    def get_speaker_mapping(
        self, segments: list[DiarizationSegment]
    ) -> dict[str, str]:
        """
        話者ラベルを連番に変換するマッピングを生成

        Args:
            segments: 話者分離セグメントのリスト

        Returns:
            話者ラベルのマッピング {"SPEAKER_00": "話者1", ...}
        """
        speakers = sorted(set(seg.speaker for seg in segments))
        return {speaker: f"話者{i + 1}" for i, speaker in enumerate(speakers)}


def assign_speakers_to_transcript(
    transcript_segments: list,
    diarization_segments: list[DiarizationSegment],
    speaker_mapping: dict[str, str] | None = None,
) -> list:
    """
    文字起こしセグメントに話者情報を付与

    Args:
        transcript_segments: TranscriptSegmentのリスト
        diarization_segments: DiarizationSegmentのリスト
        speaker_mapping: 話者ラベルのマッピング（省略時は自動生成）

    Returns:
        話者情報が付与されたTranscriptSegmentのリスト
    """
    if not diarization_segments:
        return transcript_segments

    # 話者マッピングを生成
    if speaker_mapping is None:
        speakers = sorted(set(seg.speaker for seg in diarization_segments))
        speaker_mapping = {speaker: f"話者{i + 1}" for i, speaker in enumerate(speakers)}

    # 各文字起こしセグメントに話者を割り当て
    for trans_seg in transcript_segments:
        # セグメントの中間点を使用して話者を決定
        midpoint = (trans_seg.start + trans_seg.end) / 2

        # 中間点を含む話者分離セグメントを探す
        best_speaker = None
        best_overlap = 0

        for diar_seg in diarization_segments:
            # オーバーラップを計算
            overlap_start = max(trans_seg.start, diar_seg.start)
            overlap_end = min(trans_seg.end, diar_seg.end)
            overlap = max(0, overlap_end - overlap_start)

            if overlap > best_overlap:
                best_overlap = overlap
                best_speaker = diar_seg.speaker

        # 話者を設定
        if best_speaker is not None:
            trans_seg.speaker = speaker_mapping.get(best_speaker, best_speaker)

    return transcript_segments
