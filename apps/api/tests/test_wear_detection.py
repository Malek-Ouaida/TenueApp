from __future__ import annotations

from app.domains.wear.detection import (
    DetectedOutfitItem,
    _build_generation_config,
    _extract_http_error_payload,
    _format_http_error_message,
    _merge_lower_body_recovery_detections,
    _should_run_lower_body_recovery,
    resolve_gemini_endpoint,
)

def test_generation_config_uses_json_mode_without_response_schema() -> None:
    generation_config = _build_generation_config()

    assert generation_config["responseMimeType"] == "application/json"
    assert "responseJsonSchema" not in generation_config
    assert generation_config["maxOutputTokens"] == 3072


def test_resolve_gemini_endpoint_appends_generate_content_for_model_paths() -> None:
    resolved = resolve_gemini_endpoint(
        base_url="https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash-lite",
        model="gemini-2.5-flash-lite",
    )

    assert (
        resolved
        == "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash-lite:generateContent"
    )


def test_http_400_message_preserves_google_error_detail() -> None:
    extracted = _extract_http_error_payload(
        '{"error":{"code":400,"message":"Invalid JSON schema: unsupported anyOf","status":"INVALID_ARGUMENT"}}'
    )

    message = _format_http_error_message(status_code=400, extracted_error=extracted)

    assert message == "Gemini request failed with HTTP 400: Invalid JSON schema: unsupported anyOf"


def test_lower_body_recovery_runs_when_upper_body_exists_without_lower_body() -> None:
    assert _should_run_lower_body_recovery(
        [
            DetectedOutfitItem(role="top", sort_index=0),
            DetectedOutfitItem(role="bag", sort_index=1),
        ]
    )


def test_lower_body_recovery_merges_bottom_detection_into_existing_result() -> None:
    merged = _merge_lower_body_recovery_detections(
        base_detections=[
            DetectedOutfitItem(role="top", sort_index=0),
            DetectedOutfitItem(role="bag", sort_index=1),
        ],
        recovery_detections=[
            DetectedOutfitItem(role="bag", sort_index=0, confidence=0.4),
            DetectedOutfitItem(role="bottom", sort_index=2, confidence=0.91),
        ],
    )

    assert [item.role for item in merged] == ["top", "bag", "bottom"]
