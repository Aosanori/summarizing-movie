"""CLIエントリーポイント"""

import sys
from pathlib import Path

import click

from . import __version__
from .output import OutputFormat, generate_output
from .summarizer import Summarizer
from .transcriber import Transcriber


# サポートする拡張子
SUPPORTED_VIDEO_EXTENSIONS = {".mp4", ".mov", ".avi", ".mkv", ".webm", ".m4v"}
SUPPORTED_AUDIO_EXTENSIONS = {".mp3", ".wav", ".m4a", ".flac", ".ogg", ".aac", ".wma"}
SUPPORTED_EXTENSIONS = SUPPORTED_VIDEO_EXTENSIONS | SUPPORTED_AUDIO_EXTENSIONS


@click.command()
@click.version_option(version=__version__, prog_name="summarize-movie")
@click.argument("media_path", type=click.Path(exists=True, path_type=Path))
@click.option(
    "-o",
    "--output",
    "output_path",
    type=click.Path(path_type=Path),
    default=None,
    help="出力ファイルパス（省略時は自動生成）",
)
@click.option(
    "-f",
    "--format",
    "output_format",
    type=click.Choice(["markdown", "text"]),
    default="markdown",
    help="出力形式 (デフォルト: markdown)",
)
@click.option(
    "--model",
    "whisper_model",
    type=click.Choice(["tiny", "base", "small", "medium", "large", "large-v3", "large-v3-turbo"]),
    default="large-v3-turbo",
    help="Whisperモデルサイズ (デフォルト: large-v3-turbo)",
)
@click.option(
    "--language",
    "-l",
    default="ja",
    help="文字起こし言語コード (デフォルト: ja)",
)
@click.option(
    "--lm-studio-url",
    default="http://localhost:1234/v1",
    help="LM Studio APIのURL (デフォルト: http://localhost:1234/v1)",
)
@click.option(
    "--device",
    type=click.Choice(["auto", "cpu", "cuda"]),
    default="auto",
    help="Whisper実行デバイス (デフォルト: auto)",
)
@click.option(
    "--lm-model",
    default=None,
    help="LM Studioで使用するモデル名（省略時は自動検出）",
)
@click.option(
    "--no-timestamps",
    is_flag=True,
    default=False,
    help="文字起こしにタイムスタンプを含めない",
)
@click.option(
    "-v",
    "--verbose",
    is_flag=True,
    default=False,
    help="詳細な出力を表示",
)
@click.option(
    "--chunk-size",
    type=int,
    default=20000,
    help="要約時のチャンク分割サイズ（文字数） (デフォルト: 20000)",
)
def main(
    media_path: Path,
    output_path: Path | None,
    output_format: str,
    whisper_model: str,
    language: str,
    lm_studio_url: str,
    device: str,
    lm_model: str | None,
    no_timestamps: bool,
    verbose: bool,
    chunk_size: int,
) -> None:
    """
    動画/音声ファイルを要約して議事録を生成します。

    MEDIA_PATH: 処理する動画または音声ファイルのパス
    """
    try:
        # ファイル形式を判定
        file_ext = media_path.suffix.lower()
        is_audio = file_ext in SUPPORTED_AUDIO_EXTENSIONS
        media_type = "🎵 音声" if is_audio else "📹 動画"

        # Step 1: 文字起こし
        click.echo(f"{media_type}を処理中: {media_path.name}")
        click.echo(f"🎯 Whisperモデル: {whisper_model}")

        if verbose:
            click.echo(f"   デバイス: {device}")
            click.echo(f"   言語: {language}")

        click.echo("\n⏳ 文字起こしを開始...")

        transcriber = Transcriber(
            model_size=whisper_model,
            device=device,
        )

        transcription = transcriber.transcribe(
            file_path=media_path,
            language=language if language != "auto" else None,
        )

        duration_str = _format_duration(transcription.duration)
        duration_label = "音声の長さ" if is_audio else "動画の長さ"
        click.echo(f"✅ 文字起こし完了 ({duration_label}: {duration_str})")

        if verbose:
            click.echo(f"   検出言語: {transcription.language}")
            click.echo(f"   セグメント数: {len(transcription.segments)}")

        # Step 2: 要約
        click.echo("\n⏳ 要約を生成中...")

        summarizer = Summarizer(base_url=lm_studio_url, model=lm_model, chunk_size=chunk_size)

        # 文字起こしテキストを準備
        if no_timestamps:
            text_for_summary = transcription.full_text
        else:
            text_for_summary = transcription.text_with_timestamps

        def on_chunk_progress(current: int, total: int) -> None:
            click.echo(f"   チャンク {current}/{total} を処理中...", nl=False)
            click.echo("\r", nl=False)

        summary_content = summarizer.summarize_raw(
            text_for_summary,
            on_chunk_progress=on_chunk_progress if verbose else None,
        )

        click.echo("✅ 要約生成完了")

        # Step 3: 出力
        click.echo("\n⏳ 議事録を保存中...")

        output_fmt: OutputFormat = "markdown" if output_format == "markdown" else "text"
        saved_path = generate_output(
            video_path=media_path,
            transcription=transcription,
            summary_content=summary_content,
            output_path=output_path,
            output_format=output_fmt,
        )

        click.echo(f"✅ 議事録を保存しました: {saved_path}")
        click.echo("\n🎉 処理が完了しました！")

    except FileNotFoundError as e:
        click.echo(f"❌ エラー: {e}", err=True)
        sys.exit(1)
    except ConnectionError:
        click.echo(
            "❌ エラー: LM Studioに接続できません。\n"
            f"   LM Studioが起動しているか確認してください。\n"
            f"   URL: {lm_studio_url}",
            err=True,
        )
        sys.exit(1)
    except Exception as e:
        click.echo(f"❌ エラーが発生しました: {e}", err=True)
        if verbose:
            import traceback

            click.echo(traceback.format_exc(), err=True)
        sys.exit(1)


def _format_duration(seconds: float) -> str:
    """秒数を読みやすい形式に変換"""
    hours, remainder = divmod(int(seconds), 3600)
    minutes, secs = divmod(remainder, 60)

    if hours > 0:
        return f"{hours}時間{minutes}分{secs}秒"
    elif minutes > 0:
        return f"{minutes}分{secs}秒"
    else:
        return f"{secs}秒"


if __name__ == "__main__":
    main()

