"""LM Studio APIを使用した要約モジュール"""

from dataclasses import dataclass
from typing import Callable

from openai import OpenAI

# チャンク分割のための設定
MAX_CHUNK_CHARS = 20000  # 1チャンクあたりの最大文字数（日本語は1文字≒1-2トークン）


@dataclass
class SummaryResult:
    """要約結果"""

    summary: str
    key_points: list[str]
    action_items: list[str]
    model: str


# 議事録生成用のシステムプロンプト
MEETING_MINUTES_PROMPT = """あなたは会議の議事録を作成する専門家です。
与えられた文字起こしテキストを分析し、以下の形式で議事録を作成してください。

## 出力形式

### 要約
会議の概要を3-5文で簡潔にまとめてください。

### 主要なポイント
- 議論された重要なトピックを箇条書きでリストアップしてください
- 各ポイントは1-2文で簡潔に記述してください

### アクションアイテム
- 決定された具体的なタスクや次のステップがあれば箇条書きでリストアップしてください
- 担当者や期限が言及されていれば含めてください
- アクションアイテムがない場合は「特になし」と記載してください

## 注意事項
- 日本語で出力してください
- 客観的かつ正確に情報をまとめてください
- 推測や解釈は避け、文字起こしに基づいた内容のみを含めてください
"""

# 話者名推定用のシステムプロンプト
SPEAKER_IDENTIFICATION_PROMPT = """あなたは文字起こしテキストから話者を特定する専門家です。
以下の話者分離された文字起こしを分析し、文脈から各話者の実際の名前を推定してください。

## 推定のヒント
- 自己紹介: 「私は田中です」「山田と申します」
- 呼びかけ: 「山田さん、どう思いますか？」「部長、報告があります」
- 役職や立場: 「司会の田中です」「営業部の山田です」
- 他者への言及: 「田中さんの意見に賛成です」

## 出力形式
以下のJSON形式で出力してください。推定できない話者は元のラベルのままにしてください。

```json
{
  "話者1": "推定した名前または話者1",
  "話者2": "推定した名前または話者2"
}
```

## 注意事項
- 確信が持てない場合は元のラベル（話者1、話者2など）のままにしてください
- 名前だけでなく、役職（司会、部長など）でも構いません
- JSON以外の説明文は出力しないでください
"""


class Summarizer:
    """LM Studio APIを使用してテキストを要約するクラス"""

    DEFAULT_BASE_URL = "http://localhost:1234/v1"

    def __init__(
        self,
        base_url: str | None = None,
        api_key: str = "lm-studio",
        model: str | None = None,
        chunk_size: int | None = None,
    ):
        """
        Args:
            base_url: LM Studio APIのベースURL
            api_key: APIキー（LM Studioでは通常不要）
            model: 使用するモデル名（Noneの場合、ロードされているモデルを使用）
            chunk_size: チャンク分割時の最大文字数（デフォルト: 20000）
        """
        self.base_url = base_url or self.DEFAULT_BASE_URL
        self.api_key = api_key
        self.model = model
        self.chunk_size = chunk_size or MAX_CHUNK_CHARS
        self._client: OpenAI | None = None

    def _get_client(self) -> OpenAI:
        """OpenAIクライアントを遅延初期化"""
        if self._client is None:
            self._client = OpenAI(
                base_url=self.base_url,
                api_key=self.api_key,
            )
        return self._client

    def _get_model(self) -> str:
        """使用するモデル名を取得"""
        if self.model:
            return self.model

        # LM Studioでロードされているモデルを取得
        client = self._get_client()
        models = client.models.list()

        # エンベディングモデルを除外してLLMを探す
        llm_models = [
            m.id for m in models.data
            if not m.id.startswith("text-embedding")
            and "embed" not in m.id.lower()
        ]

        if llm_models:
            return llm_models[0]

        if models.data:
            # フォールバック: 最初のモデルを使用
            return models.data[0].id

        raise RuntimeError(
            "LM Studioにモデルがロードされていません。"
            "LM Studioでモデルをロードしてください。"
        )

    def summarize(
        self,
        text: str,
        system_prompt: str | None = None,
        max_tokens: int = 2000,
        temperature: float = 0.3,
    ) -> SummaryResult:
        """
        テキストを要約して議事録形式で返す

        Args:
            text: 要約するテキスト（文字起こし結果）
            system_prompt: カスタムシステムプロンプト
            max_tokens: 最大出力トークン数
            temperature: 生成の温度パラメータ

        Returns:
            SummaryResult: 要約結果
        """
        client = self._get_client()
        model = self._get_model()

        prompt = system_prompt or MEETING_MINUTES_PROMPT

        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": prompt},
                {
                    "role": "user",
                    "content": f"以下の文字起こしテキストから議事録を作成してください：\n\n{text}",
                },
            ],
            max_tokens=max_tokens,
            temperature=temperature,
        )

        content = response.choices[0].message.content or ""

        # レスポンスをパース
        summary, key_points, action_items = self._parse_response(content)

        return SummaryResult(
            summary=summary,
            key_points=key_points,
            action_items=action_items,
            model=model,
        )

    def _parse_response(
        self, content: str
    ) -> tuple[list[str], list[str], list[str]]:
        """
        LLMのレスポンスをパース

        Args:
            content: LLMのレスポンス

        Returns:
            tuple: (summary, key_points, action_items)
        """
        # セクションごとに分割を試みる
        summary = content
        key_points: list[str] = []
        action_items: list[str] = []

        lines = content.split("\n")
        current_section = "summary"
        summary_lines: list[str] = []

        for line in lines:
            line_lower = line.lower().strip()

            # セクションヘッダーを検出
            if "要約" in line_lower or "概要" in line_lower:
                current_section = "summary"
                continue
            elif "主要" in line_lower or "ポイント" in line_lower or "トピック" in line_lower:
                current_section = "key_points"
                continue
            elif "アクション" in line_lower or "タスク" in line_lower or "次のステップ" in line_lower:
                current_section = "action_items"
                continue

            # 空行やヘッダー行をスキップ
            if not line.strip() or line.startswith("#"):
                continue

            # 箇条書きの処理
            if line.strip().startswith(("-", "*", "•", "・")):
                item = line.strip().lstrip("-*•・").strip()
                if item:
                    if current_section == "key_points":
                        key_points.append(item)
                    elif current_section == "action_items":
                        action_items.append(item)
                    else:
                        summary_lines.append(line.strip())
            else:
                if current_section == "summary":
                    summary_lines.append(line.strip())

        summary = " ".join(summary_lines) if summary_lines else content

        return summary, key_points, action_items

    def summarize_raw(
        self,
        text: str,
        system_prompt: str | None = None,
        max_tokens: int = 2000,
        temperature: float = 0.3,
        on_chunk_progress: Callable[[int, int], None] | None = None,
    ) -> str:
        """
        テキストを要約して生のレスポンスを返す
        長いテキストは自動的にチャンク分割して要約

        Args:
            text: 要約するテキスト
            system_prompt: カスタムシステムプロンプト
            max_tokens: 最大出力トークン数
            temperature: 生成の温度パラメータ
            on_chunk_progress: チャンク処理の進捗コールバック (current, total)

        Returns:
            str: LLMの生のレスポンス
        """
        # テキストが長い場合はチャンク分割して要約
        if len(text) > self.chunk_size:
            return self._summarize_long_text(
                text, system_prompt, max_tokens, temperature, on_chunk_progress
            )

        return self._summarize_single(text, system_prompt, max_tokens, temperature)

    def _summarize_single(
        self,
        text: str,
        system_prompt: str | None = None,
        max_tokens: int = 2000,
        temperature: float = 0.3,
    ) -> str:
        """単一のテキストを要約"""
        client = self._get_client()
        model = self._get_model()

        prompt = system_prompt or MEETING_MINUTES_PROMPT

        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": prompt},
                {
                    "role": "user",
                    "content": f"以下の文字起こしテキストから議事録を作成してください：\n\n{text}",
                },
            ],
            max_tokens=max_tokens,
            temperature=temperature,
        )

        return response.choices[0].message.content or ""

    def _split_text_into_chunks(self, text: str) -> list[str]:
        """テキストを行単位でチャンクに分割"""
        lines = text.split("\n")
        chunks = []
        current_chunk = []
        current_length = 0

        for line in lines:
            line_length = len(line) + 1  # +1 for newline
            if current_length + line_length > self.chunk_size and current_chunk:
                chunks.append("\n".join(current_chunk))
                current_chunk = [line]
                current_length = line_length
            else:
                current_chunk.append(line)
                current_length += line_length

        if current_chunk:
            chunks.append("\n".join(current_chunk))

        return chunks

    def _summarize_long_text(
        self,
        text: str,
        system_prompt: str | None = None,
        max_tokens: int = 2000,
        temperature: float = 0.3,
        on_chunk_progress: Callable[[int, int], None] | None = None,
    ) -> str:
        """長いテキストをチャンク分割して要約"""
        client = self._get_client()
        model = self._get_model()

        chunks = self._split_text_into_chunks(text)
        chunk_summaries = []

        # 各チャンクを要約
        chunk_prompt = """あなたは会議の文字起こしを要約する専門家です。
与えられたテキストの重要なポイントを箇条書きで簡潔にまとめてください。
- 主要な議題や決定事項
- 重要な発言や提案
- アクションアイテムがあれば記載

簡潔に、要点のみを抽出してください。"""

        for i, chunk in enumerate(chunks):
            if on_chunk_progress:
                on_chunk_progress(i + 1, len(chunks))

            response = client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": chunk_prompt},
                    {
                        "role": "user",
                        "content": f"以下のテキストを要約してください：\n\n{chunk}",
                    },
                ],
                max_tokens=1000,
                temperature=temperature,
            )
            chunk_summaries.append(response.choices[0].message.content or "")

        # 全チャンクの要約を統合して最終的な議事録を生成
        combined_summary = "\n\n---\n\n".join(chunk_summaries)

        final_prompt = system_prompt or MEETING_MINUTES_PROMPT

        final_response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": final_prompt},
                {
                    "role": "user",
                    "content": f"以下は会議の各部分の要約です。これらを統合して、一つの完全な議事録を作成してください：\n\n{combined_summary}",
                },
            ],
            max_tokens=max_tokens,
            temperature=temperature,
        )

        return final_response.choices[0].message.content or ""

    def identify_speakers(
        self,
        text: str,
        speakers: list[str],
        temperature: float = 0.1,
    ) -> dict[str, str]:
        """
        文脈から話者名を推定

        Args:
            text: 話者分離された文字起こしテキスト
            speakers: 話者ラベルのリスト（例: ["話者1", "話者2"]）
            temperature: 生成の温度パラメータ（低めが推奨）

        Returns:
            話者名のマッピング {"話者1": "田中さん", "話者2": "山田さん"}
        """
        import json

        client = self._get_client()
        model = self._get_model()

        # テキストが長すぎる場合は先頭部分のみを使用
        max_chars = 10000
        if len(text) > max_chars:
            text = text[:max_chars] + "\n\n... (以下省略)"

        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": SPEAKER_IDENTIFICATION_PROMPT},
                {
                    "role": "user",
                    "content": f"話者リスト: {', '.join(speakers)}\n\n文字起こし:\n{text}",
                },
            ],
            max_tokens=500,
            temperature=temperature,
        )

        content = response.choices[0].message.content or ""

        # JSONをパース
        try:
            # コードブロックを除去
            content = content.strip()
            if content.startswith("```"):
                lines = content.split("\n")
                content = "\n".join(lines[1:-1] if lines[-1] == "```" else lines[1:])
            content = content.strip()

            mapping = json.loads(content)
            # 元の話者リストに含まれないキーを除去
            return {k: v for k, v in mapping.items() if k in speakers}
        except json.JSONDecodeError:
            # パースに失敗した場合は空のマッピングを返す
            return {}

