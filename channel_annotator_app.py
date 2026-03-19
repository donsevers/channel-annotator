import json
import re
import streamlit as st
import anthropic

st.set_page_config(page_title="Channel Annotator", layout="centered")

st.title("Channel Annotator")
st.markdown("**Scope ≠ Fidelity ≠ Source Character ≠ Truth**")

COLORS = {
    "SCOPE": "#cce5ff",
    "FIDELITY": "#d4edda",
    "SOURCE_CHARACTER": "#fff3cd",
    "TRUTH": "#f8d7da",
    "CONFLATION": "#e2d9f3",
}

SYSTEM_PROMPT = (
    "You are an epistemological annotation assistant trained in channel-theoretic "
    "epistemology. Your task is to identify claims in text that involve scope, fidelity, "
    "source character, truth, or conflations of these. Be sensitive to subtle cases: "
    "high confidence language often smuggles in fidelity-as-truth conflations. "
    "Institutional or consensus language often smuggles in scope-as-truth conflations. "
    "Return ONLY valid JSON, no preamble, no markdown fences."
)

USER_PROMPT_TEMPLATE = (
    'Analyze this text and return a JSON object with this structure:\n'
    '{{"annotations": [{{"phrase": "exact phrase from text", "type": '
    '"SCOPE|FIDELITY|SOURCE_CHARACTER|TRUTH|CONFLATION", "explanation": "one sentence", '
    '"dimensions_conflated": ["only for CONFLATION type, list the dimensions"]}}]}}\n\n'
    'Text to analyze:\n{user_text}'
)

ABOUT_TEXT = """
**Channel-theoretic epistemology** separates four dimensions that everyday language routinely blurs together:

**Scope** — How many people share access to the information. Think of it as *how many mailboxes
the post office delivers to*. "Everyone agrees" is a scope claim — it says the channel is wide,
not that the message is true.

**Fidelity** — How faithfully the channel transmits. Like whether the post office delivers letters
*without smudging them*. "I saw it with my own eyes" is a fidelity claim — it says the channel
is clean, not that the content is true.

**Source Character** — Signals about the trustworthiness of whoever put the message into the channel.
"According to leading scientists" is a source-character claim — it says the sender is credible,
not that the message is true.

**Truth** — Whether the message corresponds to reality. "It's a fact" is a truth claim.

**The Genie example:** Imagine a genie tells only you a true fact. The *scope* is minimal (only you),
the *fidelity* is perfect (genie-to-you, no distortion), the *source character* is unknown (do you
trust genies?), and the *truth* may be genuine — but none of these dimensions *implies* the others.
Knowing something is true doesn't make it public; knowing it's public doesn't make it true.

**Conflation** is the most important category: it flags moments where a speaker collapses two or more
of these dimensions into one, treating them as equivalent when they are not.
"""


def call_claude(user_text: str, api_key: str) -> tuple[list[dict], str]:
    client = anthropic.Anthropic(api_key=api_key)
    message = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=4096,
        system=SYSTEM_PROMPT,
        messages=[
            {"role": "user", "content": USER_PROMPT_TEMPLATE.format(user_text=user_text)}
        ],
    )
    raw = message.content[0].text
    # Strip markdown fences if present
    cleaned = raw.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
        cleaned = re.sub(r"\s*```$", "", cleaned)
    data = json.loads(cleaned)
    return data["annotations"], raw


def build_annotated_html(text: str, annotations: list[dict]) -> str:
    # Build list of (start, end, annotation) sorted by position, first match wins
    spans = []
    for ann in annotations:
        phrase = ann["phrase"]
        idx = text.find(phrase)
        if idx == -1:
            # Try case-insensitive search
            idx = text.lower().find(phrase.lower())
        if idx != -1:
            spans.append((idx, idx + len(phrase), ann))

    # Sort by start position
    spans.sort(key=lambda s: s[0])

    # Remove overlaps: keep the first match
    filtered = []
    last_end = 0
    for start, end, ann in spans:
        if start >= last_end:
            filtered.append((start, end, ann))
            last_end = end

    # Build HTML
    parts = []
    cursor = 0
    for start, end, ann in filtered:
        # Add plain text before this span
        if cursor < start:
            parts.append(escape_html(text[cursor:start]))
        dim_type = ann["type"]
        color = COLORS.get(dim_type, "#eee")
        phrase_html = escape_html(text[start:end])
        if dim_type == "CONFLATION":
            parts.append(
                f'<span style="background-color:{color};padding:2px 4px;border-radius:3px;'
                f'font-weight:bold">⚠ {phrase_html}</span>'
            )
        else:
            parts.append(
                f'<span style="background-color:{color};padding:2px 4px;border-radius:3px">'
                f'{phrase_html}</span>'
            )
        cursor = end

    # Add remaining text
    if cursor < len(text):
        parts.append(escape_html(text[cursor:]))

    return "".join(parts)


def escape_html(s: str) -> str:
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace("\n", "<br>")


# --- UI ---

api_key = st.secrets.get("ANTHROPIC_API_KEY", "")

user_text = st.text_area(
    "Input text",
    placeholder="Paste any text to annotate...",
    height=200,
    label_visibility="collapsed",
)

if st.button("Analyze", type="primary"):
    if not api_key:
        st.error("Set ANTHROPIC_API_KEY in .streamlit/secrets.toml")
    elif not user_text.strip():
        st.warning("Please enter some text to analyze.")
    else:
        try:
            with st.spinner("Analyzing..."):
                annotations, raw_response = call_claude(user_text, api_key)

            # Annotated text
            html = build_annotated_html(user_text, annotations)
            st.markdown("### Annotated Text")

            # Legend
            legend_items = []
            for dim, color in COLORS.items():
                label = dim.replace("_", " ").title()
                legend_items.append(
                    f'<span style="background-color:{color};padding:2px 6px;border-radius:3px;'
                    f'margin-right:8px;font-size:0.85em">{label}</span>'
                )
            st.markdown(" ".join(legend_items), unsafe_allow_html=True)
            st.markdown(
                f'<div style="line-height:1.8;font-size:1.05em;margin-top:12px">{html}</div>',
                unsafe_allow_html=True,
            )

            # Annotations detail
            with st.expander("Annotations detail"):
                rows = []
                for ann in annotations:
                    row = {
                        "Phrase": ann["phrase"],
                        "Type": ann["type"],
                        "Explanation": ann["explanation"],
                    }
                    if ann["type"] == "CONFLATION" and ann.get("dimensions_conflated"):
                        row["Dimensions Conflated"] = ", ".join(ann["dimensions_conflated"])
                    else:
                        row["Dimensions Conflated"] = ""
                    rows.append(row)
                if rows:
                    st.table(rows)
                else:
                    st.info("No annotations found.")

        except json.JSONDecodeError as e:
            st.error(f"Failed to parse the API response: {e}")
            st.code(raw_response, language="text")
        except anthropic.APIError as e:
            st.error(f"API error: {e}")

# About
with st.expander("About this tool"):
    st.markdown(ABOUT_TEXT)
