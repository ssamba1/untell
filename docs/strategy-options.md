# What untell should be — four options, decided on the evidence

The research rounds validated the *evidence*. They did not test the *choice*. This document does
that: given what the literature now establishes, what is the highest-value thing this repository can
be? Four candidate identities, each judged against the verified findings in
[`research-verification.md`](research-verification.md).

The evidence that decides it, in one line each:

- **E1** — Measured false-positive rates on genuine human writing span **~0% to 61%** across refereed
  studies, differing by population, domain, detector set and aggregation rule.
- **E2** — **Aggregation is the largest single lever**: union (any detector flags) measured 44.44%,
  majority 4.17%, unanimous ~0%.
- **E3** — **The label drives human judgment, not the text**: >30% preference for text labelled
  "human", holding even when labels were swapped.
- **E4** — The field publishes **164 papers on evasion robustness to 20 on false positives** and 13
  on fairness. That is the *census* — all 1,718 ACL Anthology volumes, a partial clone described in
  the ledger. The shipped tool covers a 96-volume subset and finds 139 / 13 / 8
  (`python -m eval.litreview --download --json`); **the ratio is what matters and it is the same
  either way.** Quote whichever you like, but say which — round fifteen of the ledger exists because
  these two figures were allowed to blur.
- **E5** — Detector bias is real but **inconsistent across systems**, and absent entirely in at least
  one language (Czech).
- **E6** — Minimal AI polishing is already flagged; detectors cannot grade degree of involvement.
- **E7** — **These tools are already deciding admissions.** On 1,490 surgical residency personal
  statements GPTZero flagged 36.6% and Copyleaks 22.5% where both agreeing flagged 21.2%; the
  flagged group had non-English native language characteristics 38.7% against 19.6% (p<0.001); and
  in a separate study human statements written before ChatGPT existed scored 64–100% AI. The
  humanizer literature is **one record** in the same corpus.

---

## Option A — Evasion tool (what the repo grew out of)

Make the rewriting loop stronger; compete on bypass rates.

**Rejected, and the repo already knows why.** Its own measurements show the loop moves detectors it
optimises against and **does not move an unseen one**, and the GPU-trained research systems are out
of reach without hardware. **E4** makes it worse than a losing race — it is the crowded 30% of the
field. And it inverts the ethics: **E3** means the product's output would be a tool for shifting
labels, in a world where labels override reading.

## Option B — Detector benchmark (compete with MGTEVAL)

Score many detectors on shared corpora, publish a leaderboard.

**Rejected on evidence.** MGTEVAL already ships 25+ detectors, 12+ attack families, bootstrap CIs,
ECE, Brier and risk-coverage, with a web UI. We do not win on breadth or statistics. More
fundamentally, E1 says **a leaderboard is the wrong object**: a detector's rank on someone else's
corpus does not predict its false-positive rate on yours, so the artefact itself misleads its reader.
Building a better version of a misleading artefact is not a strategy.

## Option C — Deployment auditor ✅ **the choice**

Point it at *your* corpus. Get per-subgroup false-positive rates, at the vendor's shipped threshold
and at a calibrated one, under all three aggregation rules, with an AI-assisted arm and confidence
intervals.

**Every validated finding supports this and no other option.**

- **E1** makes it the *only* measurement that means anything — a published FPR is not transferable,
  so it has to be re-measured per deployment. That is not a feature, it is the consequence.
- **E5** kills the alternative of citing a paper instead: bias is inconsistent across systems and
  language-dependent, so "detectors are biased" is not an answer an institution can act on. Only
  their own number is.
- **E2** gives the single highest-leverage output — the union/majority/unanimous spread *is* the
  policy decision, and nobody currently shows it.
- **E6** says the audit must include an AI-assisted arm, because that is where the failure lives and
  where a detector at 0.00% FPR turned out to be the most biased one.
- **E4** says the niche is empty: the field is not doing this, and 20 papers across the Anthology's
  entire published history is the measure of how empty.
- **E7** decides between building this and merely describing it. Every other finding is a benchmark
  result; E7 is the same failures running against applicants who did not consent to being measured,
  in institutions that are demonstrably not reading the detection literature. **The user is not a
  researcher comparing detectors — it is the program director who licensed one tool rather than
  another and has no way to know what that choice did to their applicant pool.** That is a concrete
  person with a corpus, which is exactly what Option C serves and what B and D do not.
- **E3** supplies the reason it matters rather than merely being unoccupied. A false positive is not
  a recoverable error; it permanently changes how the work is read. Measuring exposure before
  deployment is the only intervention that acts *before* the label exists.

**What it means concretely:** the loop stops being the product and becomes one probe among several —
the one that answers "does this verdict survive editing". The product is the report.

## Option D — Standards / policy instrument

Publish an auditing protocol and push for its adoption; ride Article 50.

**Not rejected — sequenced second.** It is where Option C leads, and the same work produces both:
an audit nobody can run is not a standard. Article 50's marking obligations give it a date, and the
watermark-survival arm is a natural extension. But a protocol with no reference implementation is a
position paper, and this repo's advantage has always been that it measures rather than argues.
Ship C, then propose D from a tool people already run.

---

## What this changes about the repo's self-description

The README leads with the rewriting loop and calls the negative result its headline. That was right
when the loop was the product. On this analysis the ordering inverts:

- **The report is the product.** Per-subgroup FPR, three aggregation rules, vendor vs. calibrated
  threshold, human-vs-AI *and* AI-assisted arms, intervals on everything.
- **The loop is a probe**, kept because verdict stability under meaning-preserving editing is one
  column of that report — and because **E6** says it is a column detectors fail.
- **The claim to stop making** is any bare false-positive percentage as a property of a detector.
  Ours included: "the ensemble flags 17% of human HC3 answers" is a fact about HC3, and **E1** is the
  reason to say so every time.

That last one is uncomfortable and it is the point. The strongest finding in six rounds of research
disciplines this repository's own headline numbers before it disciplines anyone else's.
