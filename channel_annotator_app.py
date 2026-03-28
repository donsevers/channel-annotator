import json
import re
import streamlit as st
import anthropic

st.set_page_config(page_title="The Deconflator", layout="centered")

st.title("The Deconflator")
st.markdown("**Scope ≠ Fidelity ≠ Source Character ≠ Truth**")

COLORS = {
    "SCOPE": "#cce5ff",
    "FIDELITY": "#d4edda",
    "SOURCE_CHARACTER": "#fff3cd",
    "TRUTH": "#f8d7da",
    "CONFLATION": "#e2d9f3",
}

SYSTEM_PROMPT = """\
You are an epistemological annotation assistant trained in channel-theoretic epistemology.

FOUR INDEPENDENT DIMENSIONS OF EPISTEMIC CLAIMS:

Think of knowledge transmission like a post office:

SCOPE — How many receivers share access to the channel. How many mailboxes the \
post office delivers to. "Everyone agrees" is a scope claim: it says the channel \
is wide, not that the message is true.

FIDELITY — How faithfully the channel transmits. Whether the post office delivers \
letters without smudging them. "I saw it with my own eyes" is a fidelity claim: it \
says the channel is clean, not that the content is true.

SOURCE_CHARACTER — Signals about the trustworthiness of whoever put the message \
into the channel. "According to leading scientists" is a source-character claim: it \
says the sender is credible, not that the message is true. Also covers adversarial \
or unknown sources: a high-fidelity channel to a mendacious source delivers perfectly \
transmitted error. "The algorithm determined" and "simulations predict" belong here.

TRUTH — Whether the message corresponds to reality. "It's a fact" is a truth claim.

THE KEY INSIGHT — These four dimensions are independent. The Genie example: imagine \
a genie tells only you a true fact. The scope is minimal (only you), the fidelity \
is perfect (genie-to-you, no distortion), the source character is unknown (do you \
trust genies?), and the truth may be genuine — but none of these dimensions implies \
the others. Knowing something is true doesn't make it public; knowing it's public \
doesn't make it true.

CONFLATION — The most important category. A CONFLATION fires when a single phrase \
does the work of two or more dimensions simultaneously, treating them as equivalent \
when they are not. "Objectively true" is the canonical example: it collapses scope \
(objective = accessible to all) and truth (true = corresponds to reality) into one \
phrase, as though wide scope guarantees correspondence. Be sensitive to subtle cases: \
high-confidence language often smuggles in fidelity-as-truth conflations. \
Institutional or consensus language often smuggles in scope-as-truth conflations.

EXAMPLES (use this exact JSON format):

{"annotations": [
  {"phrase": "everyone agrees", "type": "SCOPE", "explanation": "Wide-scope claim: asserts convergence across receivers without addressing fidelity or truth.", "dimensions_conflated": []},
  {"phrase": "I saw it with my own eyes", "type": "FIDELITY", "explanation": "High-fidelity claim: asserts clean transmission without addressing truth.", "dimensions_conflated": []},
  {"phrase": "studies show", "type": "SOURCE_CHARACTER", "explanation": "Source authority invoked without fidelity or truth warrant.", "dimensions_conflated": []},
  {"phrase": "the fact of the matter is", "type": "TRUTH", "explanation": "Direct truth claim without scope or fidelity warrant given.", "dimensions_conflated": []},
  {"phrase": "the science is settled", "type": "CONFLATION", "explanation": "Presents consensus (scope) as equivalent to correspondence (truth). These are independent dimensions.", "dimensions_conflated": ["SCOPE", "TRUTH"]},
  {"phrase": "I know what I saw, and that proves it", "type": "CONFLATION", "explanation": "Asserts that clean transmission (fidelity) constitutes proof of correspondence (truth). These are independent dimensions.", "dimensions_conflated": ["FIDELITY", "TRUTH"]}
]}

Return ONLY valid JSON, no preamble, no markdown fences."""

USER_PROMPT_TEMPLATE = (
    'Analyze this text and return a JSON object with this structure:\n'
    '{{"annotations": [{{"phrase": "exact phrase from text", "type": '
    '"SCOPE|FIDELITY|SOURCE_CHARACTER|TRUTH|CONFLATION", "explanation": "one sentence", '
    '"dimensions_conflated": ["only for CONFLATION type, list the dimensions"], '
    '"flex_speak": "If a standard fallacy name applies (ad populum, ad verecundiam, etc.), give it. '
    'If the conflation happens before the argument is even made — at the vocabulary level — say '
    'pre-inferential conflation."}}]}}\n\n'
    'Text to analyze:\n{user_text}'
)

ABOUT_TEXT = """
The Deconflator separates what you know from how you know it.

Most epistemological errors aren't lies. They're conflations — one word quietly doing the work of four distinct questions:

**SCOPE** — How many receivers share the channel?

**FIDELITY** — How cleanly does the channel transmit?

**SOURCE CHARACTER** — Do you trust who packed the box?

**TRUTH** — Does the content hold up? (Correspondence, coherence, pragmatic consequence — pick your theory. The Deconflator doesn't. It just flags when scope or fidelity are being passed off as a substitute for whichever one you meant.)

The post office delivers. It does not certify. A billion-person consensus is a fact about the delivery network. It says nothing about what was in the package.

The Genie knows this. The Salem jury did not.
"""


def call_claude_concept(concept: str, api_key: str) -> dict:
    client = anthropic.Anthropic(api_key=api_key)

    # Call 1 — Identification
    id_message = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=512,
        system=SYSTEM_PROMPT,
        messages=[
            {"role": "user", "content": (
                f"Identify the folk concept or philosophical assumption invoked by: '{concept}'\n"
                "What domain does it belong to (philosophy of mind, epistemology, ethics, etc.)?\n"
                "Reply in 2-3 sentences only."
            )}
        ],
    )
    identification = id_message.content[0].text.strip()

    # Call 2 — Dimensional analysis
    analysis_message = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=1536,
        system=SYSTEM_PROMPT,
        messages=[
            {"role": "user", "content": (
                f"Apply the four-dimension taxonomy to this concept or claim: '{concept}'\n\n"
                "For each dimension, answer:\n"
                "1. Does this concept implicate this dimension? (Yes / No / Partially)\n"
                "2. What hidden assumption does it carry about this dimension?\n"
                "3. Is that assumption doing hidden work — i.e., would the concept change or "
                "break apart if the assumption were made explicit? (Yes / No)\n\n"
                "Then write a Conflation Summary: one paragraph naming which dimensions this "
                "concept bundles together that are independently variable, and why separating "
                "them matters philosophically. If there is no conflation, say so plainly.\n\n"
                "Return ONLY valid JSON in this exact structure, no preamble, no markdown fences:\n"
                '{\n'
                '  "identification": "the 2-3 sentence identification from context",\n'
                '  "dimensions": {\n'
                '    "SCOPE": {"implicated": "Yes|No|Partially", "assumption": "...", "hidden_work": "Yes|No"},\n'
                '    "FIDELITY": {"implicated": "Yes|No|Partially", "assumption": "...", "hidden_work": "Yes|No"},\n'
                '    "SOURCE_CHARACTER": {"implicated": "Yes|No|Partially", "assumption": "...", "hidden_work": "Yes|No"},\n'
                '    "TRUTH": {"implicated": "Yes|No|Partially", "assumption": "...", "hidden_work": "Yes|No"}\n'
                '  },\n'
                '  "conflation_summary": "..."\n'
                '}'
            )}
        ],
    )
    raw = analysis_message.content[0].text.strip()
    if raw.startswith("```"):
        raw = re.sub(r"^```(?:json)?\s*", "", raw)
        raw = re.sub(r"\s*```$", "", raw)

    data = json.loads(raw)
    data["identification"] = identification
    return data


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


def _normalize(s: str) -> str:
    """Collapse whitespace and strip punctuation edges for fuzzy matching."""
    return re.sub(r"\s+", " ", s).strip()


def _find_phrase(text: str, phrase: str) -> int:
    """Find phrase in text with exact, case-insensitive, and normalized fallbacks."""
    idx = text.find(phrase)
    if idx != -1:
        return idx
    idx = text.lower().find(phrase.lower())
    if idx != -1:
        return idx
    # Normalize whitespace in both and search
    norm_text = _normalize(text)
    norm_phrase = _normalize(phrase)
    idx = norm_text.lower().find(norm_phrase.lower())
    if idx != -1:
        # Map back to original text position approximately
        # Count how many chars in original text correspond to idx chars in normalized
        orig_idx = 0
        norm_idx = 0
        for orig_idx, ch in enumerate(text):
            if norm_idx >= idx:
                break
            if ch.isspace():
                if orig_idx == 0 or not text[orig_idx - 1].isspace():
                    norm_idx += 1
            else:
                norm_idx += 1
        return orig_idx
    return -1


def build_annotated_html(text: str, annotations: list[dict]) -> str:
    spans = []
    for ann in annotations:
        phrase = ann["phrase"]
        idx = _find_phrase(text, phrase)
        if idx != -1:
            spans.append((idx, idx + len(phrase), ann))

    # Sort: CONFLATION annotations first (priority), then by start position
    spans.sort(key=lambda s: (0 if s[2]["type"] == "CONFLATION" else 1, s[0]))

    # Remove overlaps: CONFLATION wins because it's sorted first
    filtered = []
    taken = []  # list of (start, end) already claimed
    for start, end, ann in spans:
        overlaps = any(s < end and e > start for s, e in taken)
        if not overlaps:
            filtered.append((start, end, ann))
            taken.append((start, end))

    # Re-sort by position for rendering
    filtered.sort(key=lambda s: s[0])

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
                f'font-weight:bold">⚠ FLEX: {phrase_html}</span>'
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

with st.expander("✈ Tips for Passage (how to avoid delays at customs)"):
    st.markdown("""
- Customs flags *bundled cargo*. One word doing the work of four concepts is a declaration violation.
- "Objectively true" will be detained every time. Declare scope and truth separately.
- High fidelity is not a passport. The channel ran clean. That's it. That's all it means.
- Source character goes in a separate bag. "Studies show" is not a truth claim. It is a claim about who packed the box.
- The Genie is always at the border. Before you trust the transmission, ask: do I know this Genie? Friendly, indifferent, or malicious? That answer changes everything downstream.
- First-person reports get the same treatment as everything else. "I was there" clears fidelity. It does not clear truth. You may not know what you saw.
- Pre-inferential conflations are the hardest to catch because they happen before you start arguing. "The science is settled" has already done the damage before the next sentence begins.
- If your sentence contains "objectively," "clearly," "everyone knows," "the fact is," or "it's obvious" — go to secondary screening.
""")

tab_passage, tab_concept = st.tabs(["Passage", "Concept"])

# --- Tab 1: Passage (existing UI, unchanged) ---
with tab_passage:
    user_text = st.text_area(
        "Input text",
        placeholder="Paste some bullshit here.",
        height=200,
        label_visibility="collapsed",
    )

    if st.button("Analyze", type="primary"):
        if not api_key:
            st.error("Set ANTHROPIC_API_KEY in .streamlit/secrets.toml")
        elif not user_text.strip():
            st.warning("Please enter some text to analyze.")
        else:
            raw_response = ""
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
                        row["Flex-speak"] = ann.get("flex_speak", "")
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

# --- Tab 2: Concept (dimensional analysis mode) ---
with tab_concept:
    concept_input = st.text_input(
        "Concept or claim",
        placeholder="Enter a concept or claim (e.g. 'mental privacy', 'fMRI reads your mind', 'objectivity')",
        label_visibility="collapsed",
    )

    if st.button("Decompose", type="primary", key="decompose_btn"):
        if not api_key:
            st.error("Set ANTHROPIC_API_KEY in .streamlit/secrets.toml")
        elif not concept_input.strip():
            st.warning("Please enter a concept or claim to decompose.")
        else:
            try:
                with st.spinner("Identifying concept..."):
                    with st.spinner("Running dimensional analysis..."):
                        result = call_claude_concept(concept_input, api_key)

                # Identification
                st.markdown(f"**Identification:** {escape_html(result['identification'])}")

                # Dimension cards
                dim_labels = {
                    "SCOPE": "SCOPE",
                    "FIDELITY": "FIDELITY",
                    "SOURCE_CHARACTER": "SOURCE CHARACTER",
                    "TRUTH": "TRUTH",
                }
                for dim_key, dim_label in dim_labels.items():
                    dim = result["dimensions"][dim_key]
                    color = COLORS.get(dim_key, "#eee")
                    card_html = (
                        f'<div style="background-color:{color};padding:12px 16px;border-radius:6px;margin-bottom:10px">'
                        f'<strong>{dim_label}</strong><br>'
                        f'Implicated: {escape_html(dim["implicated"])}<br>'
                        f'Hidden assumption: {escape_html(dim["assumption"])}<br>'
                        f'Doing hidden work: {escape_html(dim["hidden_work"])}'
                        f'</div>'
                    )
                    st.markdown(card_html, unsafe_allow_html=True)

                # Conflation Summary
                st.markdown("### Conflation Summary")
                st.markdown(result["conflation_summary"])

            except json.JSONDecodeError as e:
                st.error(f"Failed to parse the API response: {e}")
            except anthropic.APIError as e:
                st.error(f"API error: {e}")

# About
with st.expander("About this tool"):
    st.markdown(ABOUT_TEXT)
