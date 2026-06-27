# Spec — detector.py (Milestones 3 & 4)

Implements the two detection signals and the confidence-scoring logic.

## `llm_signal(text) -> {"p_ai": float, "rationale": str}`  (M3)
- Sends `text` to Groq (`llama-3.3-70b-versatile`) with a prompt asking whether the writing
  reads as human or AI-generated.
- Returns `p_ai ∈ [0, 1]` (probability AI-generated) and a short rationale.
- **Blind spot:** fooled by framing and lightly edited AI; non-deterministic.

## `stylometric_signal(text) -> {"style_score": float, "metrics": {...}}`  (M4)
- Pure Python. Computes: sentence-length variance, type-token ratio, punctuation density.
- Maps the metrics to `style_score ∈ [0, 1]` (higher = more AI-like / uniform).
- **Blind spot:** length-sensitive and genre-blind; mis-scores uniform human writing.

## `combine_signals(llm_score, style_score) -> {"p_ai": float, "attribution": str}`  (M4)
- `p_ai = 0.6 * llm_score + 0.4 * style_score`, then pull toward 0.5 when the signals disagree.
- Attribution bands: `≥ 0.80 → likely_ai`, `0.30–0.80 → uncertain`, `≤ 0.30 → likely_human`.
- Asymmetric thresholds suppress false positives (see `planning.md` §3).
