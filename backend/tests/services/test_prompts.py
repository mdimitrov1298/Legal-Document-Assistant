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

HITS_EN = [
    {
        "chunk_id": "d1:0",
        "text": "The deadline is 30 days.",
        "metadata": {"document_filename": "contract.txt"},
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


# --- English prompt tests ---


def test_english_system_prompts_request_json():
    for system in (prompts.SUMMARIZE_SYSTEM_EN, prompts.VERIFY_SYSTEM_EN):
        assert "JSON" in system
        assert "English" in system
    assert "inconclusive" in prompts.VERIFY_SYSTEM_EN


def test_english_verify_prompt():
    text = prompts.build_verify_prompt(
        "The deadline is 30 days", HITS_EN, language="en"
    )
    assert "CLAIM:\nThe deadline is 30 days" in text
    assert "[0] document=contract.txt chunk=d1:0\nThe deadline is 30 days." in text


def test_english_summarize_prompt():
    text = prompts.build_summarize_prompt("Case", HITS_EN, language="en")
    assert "Case title: Case" in text
    assert "EXCERPTS:" in text


def test_english_summarize_prompt_no_hits():
    text = prompts.build_summarize_prompt("Case", [], language="en")
    assert prompts.NO_EXCERPTS_EN in text


def test_get_summarize_system_bg():
    assert prompts.get_summarize_system("bg") == prompts.SUMMARIZE_SYSTEM


def test_get_summarize_system_en():
    assert prompts.get_summarize_system("en") == prompts.SUMMARIZE_SYSTEM_EN


def test_get_verify_system_bg():
    assert prompts.get_verify_system("bg") == prompts.VERIFY_SYSTEM


def test_get_verify_system_en():
    assert prompts.get_verify_system("en") == prompts.VERIFY_SYSTEM_EN


def test_get_prompt_version():
    assert prompts.get_prompt_version("bg") == "bg-v1"
    assert prompts.get_prompt_version("en") == "en-v1"


def test_en_prompt_uses_same_verdict_labels():
    """English prompts use the same verdict labels as Bulgarian."""
    for label in ("supported", "denied", "inconclusive"):
        assert label in prompts.VERIFY_SYSTEM_EN


# --- Ask prompt tests ---


def test_ask_system_bg_requests_json():
    assert "JSON" in prompts.ASK_SYSTEM
    assert "not_found" in prompts.ASK_SYSTEM
    assert "evidence" in prompts.ASK_SYSTEM


def test_ask_system_en_requests_json():
    assert "JSON" in prompts.ASK_SYSTEM_EN
    assert "not_found" in prompts.ASK_SYSTEM_EN
    assert "evidence" in prompts.ASK_SYSTEM_EN


def test_get_ask_system_bg():
    assert prompts.get_ask_system("bg") == prompts.ASK_SYSTEM


def test_get_ask_system_en():
    assert prompts.get_ask_system("en") == prompts.ASK_SYSTEM_EN


def test_build_ask_prompt_bg():
    text = prompts.build_ask_prompt("Какъв е срокът?", HITS)
    assert "ВЪПРОС:\nКакъв е срокът?" in text
    assert "ОТКЪСИ:" in text


def test_build_ask_prompt_en():
    text = prompts.build_ask_prompt("What is the deadline?", HITS_EN, language="en")
    assert "QUESTION:\nWhat is the deadline?" in text
    assert "EXCERPTS:" in text
