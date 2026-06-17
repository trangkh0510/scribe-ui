"""Route A — single-file analyzer.

Injects the user's objectives/context + the transcript into the chosen type's Brain
prompt, calls the LLM for schema-validated JSON, and returns it as a plain dict ready
for the renderer.
"""
from app.brain_schema import BRAIN_SCHEMA
from app.llm import call_structured
from app.prompt_loader import load_brain_prompt, fill_user

# Output-language directives appended to the Brain system prompt. The prompts are
# written in Vietnamese and otherwise default to Vietnamese output; this lets the UI's
# language selector actually steer the report's prose language. Structural section
# headers are owned by render.py and stay Vietnamese — only the LLM-authored text
# fields (summaries, findings, reasons, suggestions...) follow this directive.
_LANG_DIRECTIVE = {
    "vi": ("YÊU CẦU NGÔN NGỮ: Viết toàn bộ nội dung văn bản trong JSON (tóm tắt, nhận "
           "định, lý do verdict, gợi ý, ghi chú, mô tả...) bằng TIẾNG VIỆT."),
    "en": ("LANGUAGE REQUIREMENT: Write ALL natural-language text fields in the JSON "
           "output (summaries, findings, verdict reasons, suggestions, notes, "
           "descriptions) in ENGLISH. Keep verbatim user quotes in their original "
           "spoken language — do NOT translate the quotes."),
}
# auto / unknown → follow the transcript's own dominant language.
_LANG_AUTO = ("YÊU CẦU NGÔN NGỮ: Viết nội dung văn bản trong JSON bằng cùng ngôn ngữ "
              "chủ đạo của transcript.")


def _apply_language(system: str, language: str) -> str:
    directive = _LANG_DIRECTIVE.get((language or "auto").lower(), _LANG_AUTO)
    return f"{system}\n\n{directive}"


def analyze_single(client, model, *, type: str, transcript_text: str,
                   objectives: str, context: str = "", language: str = "auto") -> dict:
    system, user_template = load_brain_prompt(type)
    system = _apply_language(system, language)
    user = fill_user(type, user_template, objectives=objectives,
                     context=context, transcript=transcript_text)
    result = call_structured(client, model, system, user, BRAIN_SCHEMA[type],
                             temperature=0.0, thinking=False)
    return result.model_dump()
