from services.msg91_whatsapp import (
    build_template_vars,
    clip_var,
    format_questions,
    india_whatsapp_number,
    notes_or_dash,
    question_slots,
)


def test_empty_notes_become_a_dash():
    assert notes_or_dash("") == "—"
    assert notes_or_dash("   ") == "—"
    assert notes_or_dash("Confirm WC brand") == "Confirm WC brand"


def test_questions_are_numbered_and_clipped():
    text = format_questions(
        [
            "Confirm GST is included.",
            "Confirm N/A lines were not quoted.",
            "List what the lumpsum includes.",
        ]
    )
    assert text.startswith("1) Confirm GST")
    assert "2) Confirm N/A" in text
    assert " | " in text
    assert len(text) <= 400


def test_long_notes_are_clipped_not_rejected():
    long = "word " * 500
    clipped = notes_or_dash(long)
    assert clipped != "—"
    assert len(clipped) <= 200
    assert clipped.endswith("…")


def test_default_country_code_from_env(monkeypatch):
    monkeypatch.setenv("MSG91_DEFAULT_COUNTRY_CODE", "91")
    assert india_whatsapp_number("9513158197") == "919513158197"


def test_india_phone_gets_country_code():
    assert india_whatsapp_number("9513158197") == "919513158197"
    assert india_whatsapp_number("+91 95131 58197") == "919513158197"
    assert india_whatsapp_number("") == ""


def test_template_vars_work_with_empty_notes():
    vars_ = build_template_vars(
        vendor_name="INFOSYS LIMITED",
        quote_number="Q2OE1CX",
        questions=["Confirm GST is included."],
        notes="",
    )
    assert vars_["body_1"] == "INFOSYS LIMITED"
    assert vars_["body_2"] == "Q2OE1CX"
    assert vars_["body_3"] == "1"
    assert vars_["body_4"].startswith("1) Confirm GST")
    assert vars_["body_5"] == "—"
    assert "body_7" not in vars_


def test_v2_layout_one_variable_per_question(monkeypatch):
    monkeypatch.setenv(
        "MSG91_ASK_VENDOR_TEMPLATE", "tatvaops_quotesense_ask_vendor_v2_en"
    )
    vars_ = build_template_vars(
        vendor_name="INFOSYS LIMITED",
        quote_number="Q2OE1CX",
        questions=[
            "Confirm quantities use the same unit.",
            "Confirm N/A lines were not quoted.",
            "List what the lumpsum includes.",
        ],
        notes="Confirm WC brand\nand warranty.",
    )
    assert vars_["body_4"] == "Confirm quantities use the same unit."
    assert vars_["body_5"] == "Confirm N/A lines were not quoted."
    assert vars_["body_6"] == "List what the lumpsum includes."
    assert vars_["body_7"] == "Confirm WC brand and warranty."


def test_question_slots_pad_and_overflow():
    assert question_slots(["Only one"]) == ("Only one", "—", "—")
    q1, q2, q3 = question_slots(["A", "B", "C", "D"])
    assert q1 == "A"
    assert q2 == "B"
    assert q3.startswith("C")
    assert "4) D" in q3


def test_clip_var():
    assert clip_var("  hello   world  ", 80) == "hello world"
    assert len(clip_var("x" * 50, 10)) == 10
