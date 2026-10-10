"""Prompt builders and model-specific templates."""

from __future__ import annotations

from app.services import prompts

HITS = [
    {
        "chunk_id": "d1:0",
        "text": "Срокът е 30 дни.",
        "metadata": {"document_filename": "dogovor.txt"},
    }
]


def test_verify_prompt_numbers_quotes():
    text = prompts.build_verify_prompt("Срокът е 30 дни", HITS)
    assert "ТВЪРДЕНИЕ:\nСрокът е 30 дни" in text
    assert "[0] документ=dogovor.txt фрагмент=d1:0\nСрокът е 30 дни." in text


def test_summarize_prompt_without_hits():
    text = prompts.build_summarize_prompt("Дело", [])
    assert prompts.NO_EXCERPTS in text


def test_system_prompts_are_bulgarian_and_request_json():
    for system in (prompts.SUMMARIZE_SYSTEM, prompts.VERIFY_SYSTEM):
        assert "JSON" in system
        assert "български" in system
    assert "inconclusive" in prompts.VERIFY_SYSTEM


def test_render_default_models_keep_system_field():
    for model in ("qwen2.5:7b", "llama3.1:8b"):
        rendered = prompts.render_for_model(model, "P", "S")
        assert rendered == prompts.RenderedPrompt(prompt="P", system="S", raw=False)


def test_render_bggpt_inst_template():
    rendered = prompts.render_for_model("BgGPT-7B-Instruct", "P", "S")
    assert rendered.raw is True
    assert rendered.system is None
    assert rendered.prompt == "[INST] S\n\nP [/INST]"
    assert prompts.render_for_model("bggpt-7b", "P", None).prompt == "[INST] P [/INST]"


def test_bggpt_v1_gemma_uses_ollama_chat_template():
    for model in (
        "s_emanuilov/BgGPT-v1.0:9b",
        "INSAIT-Institute/BgGPT-Gemma-2-9B-IT-v1.0",
        "pazoff/bggpt-gemma-2-9b-it-v1.0.q4_k_m.gguf",
    ):
        rendered = prompts.render_for_model(model, "P", "S")
        assert rendered.raw is False
        assert rendered.prompt == "P"
        assert rendered.system == "S"
