"""
LLM Insight Generation via Offline Local Ollama

Uses a local Ollama instance (llama3.2:latest or llama3:latest)
to generate structured risk analysis from detected anomalies.

The LLM receives ONLY structured anomaly data — never raw document text.
This prevents hallucination and keeps the output grounded and auditable.

Falls back to a rule-based mock if Ollama is offline or unavailable.
"""
import os
import json
import httpx
import asyncio

OLLAMA_API_URL = os.environ.get("OLLAMA_API_URL", "http://localhost:11434")
OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL", "llama3.2:latest")
OLLAMA_FALLBACK_MODEL = os.environ.get("OLLAMA_FALLBACK_MODEL", "llama3:latest")

OLLAMA_SYSTEM_PROMPT = """You are a senior banking fraud risk analyst at an Indian NBFC.
Analyze the forensic anomalies in the loan document JSON payload and return a risk assessment.

Return ONLY a raw JSON object with EXACTLY these keys:
{
  "risk_level": "HIGH" | "MEDIUM" | "LOW",
  "summary": "2-3 sentence executive summary referencing exact anomalies.",
  "specific_findings": ["bullet point 1", "bullet point 2"],
  "recommended_action": "APPROVE" | "REJECT" | "ESCALATE" | "MANUAL_REVIEW",
  "confidence_rationale": "Why you are confident/uncertain in this decision.",
  "risk_factors": [{"factor": "name", "severity": "CRITICAL"|"HIGH"|"MEDIUM"|"LOW", "evidence": "evidence"}]
}

Instructions:
1. Base analysis ONLY on the provided anomalies. Do not invent details.
2. Be specific: reference anomalies (font mismatch, ELA residual, FFT, etc.)
3. Do not output any thinking process, conversational text, markdown formatting, or HTML tags. Return raw JSON only."""

async def generate_llm_insight(anomalies: list, extracted_data: dict = None, case_id: str = "") -> dict:
    """
    Generate structured LLM risk insight from detected anomalies using a local Ollama model.
    
    Args:
        anomalies: list of anomaly dicts from forensic pipeline
        extracted_data: OCR-extracted fields (name, PAN, income, etc.)
        case_id: for logging
    
    Returns:
        {
            risk_level: "HIGH"|"MEDIUM"|"LOW",
            summary: str,
            specific_findings: [str, ...],
            recommended_action: "APPROVE"|"REJECT"|"ESCALATE"|"MANUAL_REVIEW",
            confidence_rationale: str,
            risk_factors: [{factor, severity, evidence}, ...],
            llm_source: "ollama-llama3.2:latest" | "rule-based-mock",
            html_summary: str  # Formatted HTML for direct rendering
        }
    """
    if not anomalies:
        return _mock_clean_result()

    # Filter out INFO severity for LLM — only feed actionable anomalies
    actionable = [a for a in anomalies if a.get("severity", "INFO") != "INFO"]

    # Build structured input — LLM never sees raw document text
    anomaly_payload = {
        "case_id": case_id,
        "total_anomalies": len(anomalies),
        "actionable_anomalies": len(actionable),
        "extracted_fields": {
            k: v for k, v in (extracted_data or {}).items()
            if k not in ("bboxes", "textract_source", "raw_text")
        },
        "anomalies": [
            {
                "id": a.get("id"),
                "type": a.get("type"),
                "severity": a.get("severity"),
                "title": a.get("title"),
                "description": a.get("desc"),
                "confidence": a.get("conf"),
            }
            for a in actionable
        ]
    }

    user_message = (
        f"Analyze the following forensic anomalies detected in a loan application document "
        f"and provide a structured risk assessment:\n\n"
        f"```json\n{json.dumps(anomaly_payload, indent=2)}\n```\n\n"
        f"Return ONLY a JSON response conforming to the system prompt's instructions."
    )

    try:
        # Quick health check — skip all LLM calls if Ollama is not running
        ollama_reachable = False
        try:
            async with httpx.AsyncClient(timeout=2.0) as probe:
                probe_resp = await probe.get(f"{OLLAMA_API_URL}/api/tags")
                ollama_reachable = probe_resp.status_code == 200
        except Exception:
            pass

        if not ollama_reachable:
            print("[LLM Insight] Ollama not reachable, skipping LLM models")
            raise Exception("Ollama not available")

        async with httpx.AsyncClient(timeout=15.0) as client:
            models_to_try = [OLLAMA_MODEL, "qwen2.5:3b", OLLAMA_FALLBACK_MODEL]
            response_json = None
            used_model = None

            for model in models_to_try:
                try:
                    payload = {
                        "model": model,
                        "prompt": f"{OLLAMA_SYSTEM_PROMPT}\n\nUser Message:\n{user_message}",
                        "format": "json",
                        "stream": False,
                        "options": {
                            "temperature": 0.0
                        }
                    }
                    response = await client.post(
                        f"{OLLAMA_API_URL}/api/generate",
                        json=payload
                    )
                    if response.status_code == 200:
                        res_data = response.json()
                        response_text = res_data.get("response", "").strip()
                        if response_text:
                            # Parse JSON
                            response_json = json.loads(response_text)
                            used_model = model
                            break
                except Exception as model_err:
                    print(f"[LLM Insight] Ollama model {model} failed: {repr(model_err)}")
                    continue

            if response_json:
                required_keys = ["risk_level", "summary", "specific_findings", "recommended_action", "confidence_rationale", "risk_factors"]
                # Normalise/fill keys if missing
                for key in required_keys:
                    if key not in response_json:
                        if key == "risk_level":
                            response_json[key] = "MEDIUM"
                        elif key == "summary":
                            response_json[key] = "Ollama analysis generated with some missing structured fields."
                        elif key == "specific_findings":
                            response_json[key] = ["Font mismatch or compression anomaly observed."]
                        elif key == "recommended_action":
                            response_json[key] = "MANUAL_REVIEW"
                        elif key == "confidence_rationale":
                            response_json[key] = "Default confidence rationale due to missing keys in model response."
                        elif key == "risk_factors":
                            response_json[key] = []
                
                # Check enum constraints
                if response_json.get("risk_level") not in ["HIGH", "MEDIUM", "LOW"]:
                    response_json["risk_level"] = "MEDIUM"
                if response_json.get("recommended_action") not in ["APPROVE", "REJECT", "ESCALATE", "MANUAL_REVIEW"]:
                    response_json["recommended_action"] = "MANUAL_REVIEW"

                response_json["llm_source"] = f"ollama-{used_model}"
                response_json["html_summary"] = _render_html(response_json)
                return response_json

    except Exception as e:
        print(f"[LLM Insight] Ollama call failed completely: {e}")

    # Fallback if Ollama call fails
    return _rule_based_fallback(actionable, extracted_data)

def generate_llm_insight_sync(anomalies: list, extracted_data: dict = None, case_id: str = "") -> dict:
    """
    Synchronous wrapper for use in non-async contexts.
    """
    import asyncio
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as pool:
                future = pool.submit(asyncio.run, generate_llm_insight(anomalies, extracted_data, case_id))
                return future.result(timeout=180.0)
        else:
            return loop.run_until_complete(generate_llm_insight(anomalies, extracted_data, case_id))
    except Exception as e:
        print(f"[LLM Insight sync] {e}")
        actionable = [a for a in anomalies if a.get("severity", "INFO") != "INFO"]
        return _rule_based_fallback(actionable, extracted_data)

def _rule_based_fallback(anomalies: list, extracted_data: dict = None) -> dict:
    """
    Structured rule-based fallback when Ollama is unavailable.
    """
    high_count = sum(1 for a in anomalies if a.get("severity") == "HIGH")
    medium_count = sum(1 for a in anomalies if a.get("severity") == "MEDIUM")

    if high_count >= 2:
        risk_level = "HIGH"
        action = "REJECT"
        summary = (
            f"Document exhibits {high_count} HIGH-severity forensic anomalies including "
            f"{', '.join(a['title'] for a in anomalies if a.get('severity') == 'HIGH')[:120]}. "
            f"Multiple overlapping detection signals strongly indicate document manipulation. "
            f"Application should be rejected and escalated for investigation."
        )
    elif high_count == 1 or medium_count >= 2:
        risk_level = "MEDIUM"
        action = "ESCALATE"
        summary = (
            f"Document shows {high_count} high-severity and {medium_count} medium-severity anomalies. "
            f"While not conclusive, the combination warrants escalation to a senior analyst "
            f"for manual verification with original document collection."
        )
    elif medium_count == 1:
        risk_level = "MEDIUM"
        action = "MANUAL_REVIEW"
        summary = (
            f"One medium-severity anomaly detected. "
            f"Recommend requesting original document from applicant for comparison."
        )
    else:
        risk_level = "LOW"
        action = "APPROVE"
        summary = (
            "No significant forensic anomalies detected across font analysis, "
            "ELA compression testing, and metadata inspection. "
            "Document integrity appears consistent with authentic bank-generated output."
        )

    specific_findings = [
        f"[{a.get('severity', 'INFO')}] {a.get('title', '')}: {a.get('desc', '')[:100]}"
        for a in anomalies[:8]
    ] or ["No actionable anomalies detected."]

    risk_factors = [
        {
            "factor": a.get("title", "Unknown"),
            "severity": a.get("severity", "LOW"),
            "evidence": a.get("desc", "")[:120]
        }
        for a in anomalies[:6]
    ]

    result = {
        "risk_level": risk_level,
        "summary": summary,
        "specific_findings": specific_findings,
        "recommended_action": action,
        "confidence_rationale": (
            "Rule-based analysis engine (offline fallback mode). "
            "Local Ollama was unreachable."
        ),
        "risk_factors": risk_factors,
        "llm_source": "rule-based-mock",
    }
    result["html_summary"] = _render_html(result)
    return result

def _mock_clean_result() -> dict:
    result = {
        "risk_level": "LOW",
        "summary": (
            "No forensic anomalies were detected by the pipeline. "
            "Document metadata, typography, and pixel integrity checks passed. "
            "Proceed with standard credit assessment workflow."
        ),
        "specific_findings": [
            "Font analysis: No typeface inconsistencies detected on any line",
            "Metadata: No suspicious producer software signatures",
            "ELA: Compression residuals within expected range for authentic document",
        ],
        "recommended_action": "APPROVE",
        "confidence_rationale": "All forensic sub-modules returned clean results with no flagged anomalies.",
        "risk_factors": [],
        "llm_source": "rule-based-mock",
    }
    result["html_summary"] = _render_html(result)
    return result

def _render_html(result: dict) -> str:
    """Generate formatted HTML summary for the existing frontend dangerouslySetInnerHTML panel."""
    level = result.get("risk_level", "LOW")
    action = result.get("recommended_action", "MANUAL_REVIEW")
    source = result.get("llm_source", "unknown")

    color = {
        "HIGH": "#ef4444",
        "MEDIUM": "#f59e0b",
        "LOW": "#10b981"
    }.get(level, "#94a3b8")

    action_color = {
        "REJECT": "#ef4444",
        "ESCALATE": "#f59e0b",
        "APPROVE": "#10b981",
        "MANUAL_REVIEW": "#6366f1"
    }.get(action, "#94a3b8")

    if "ollama" in source:
        badge_text = f"🤖 Ollama ({source.replace('ollama-', '')})"
        bg_color = "#1e3a8a"
        text_color = "#93c5fd"
    elif "claude" in source:
        badge_text = "🤖 Claude Sonnet 4"
        bg_color = "#1e1b4b"
        text_color = "#a78bfa"
    else:
        badge_text = "⚙️ Rule Engine"
        bg_color = "#334155"
        text_color = "#cbd5e1"

    source_badge = (
        f'<span style="background:{bg_color};color:{text_color};padding:2px 8px;border-radius:4px;font-size:10px;font-weight:700;">'
        f'{badge_text}'
        f'</span>'
    )

    findings_html = "".join(
        f'<li style="margin-bottom:4px;">{f}</li>'
        for f in result.get("specific_findings", [])[:6]
    )

    return (
        f'<div style="line-height:1.6;">'
        f'{source_badge}'
        f'<p style="margin-top:8px;"><strong>Risk Level: </strong>'
        f'<span style="color:{color};font-weight:700;">{level}</span></p>'
        f'<p style="margin-top:4px;color:#cbd5e1;">{result.get("summary", "")}</p>'
        f'<ul style="margin-top:8px;padding-left:16px;color:#94a3b8;font-size:11px;">{findings_html}</ul>'
        f'<p style="margin-top:8px;"><strong>Recommended Action: </strong>'
        f'<span style="color:{action_color};font-weight:700;">{action}</span></p>'
        f'<p style="margin-top:4px;color:#64748b;font-size:10px;font-style:italic;">'
        f'{result.get("confidence_rationale", "")}</p>'
        f'</div>'
    )
