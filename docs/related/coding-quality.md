# ROCm coding-quality matrix (2026-10-02)

*Source: `~/LLM/testing_resources/coder_benchmark/REVIEW.md`, reviewed
2026-10-02; file mtime 2026-10-03 00:38 +0200. This is a ROCm-only
coding-quality experiment, not a backend comparison. The harness code and model
outputs are not included. The body below is the original review, unchanged.*

---

# Qwen coder benchmark review

Reviewed 2026-10-02. All four conditions finished in **65.75 minutes**; none was omitted. **No implementation passed every acceptance check.** The strongest observed partial solution used DFlash2 with six draft tokens and thinking disabled.

## Results

Primary acceptance scores count the same **27 checks**: eight public and 19 independent checks. Worker-written tests do not increase this denominator. Timings include each condition's loading, generation and execution; the whole matrix includes orchestration overhead.

- **DFlash on, thinking off:** **24/27**, **11.71 minutes**, all three visible task gates completed. Generated 4,227 tokens across 18 turns; no reasoning trace. Draft acceptance 50.16%.
- **DFlash off, thinking off:** **22/27**, **20.10 minutes**, all three visible task gates completed. Generated 6,912 tokens across 17 turns; no reasoning trace.
- **DFlash on, thinking budget 2048:** **9/27**, **13.71 minutes**, stopped at the first task's eight-turn limit. Generated 8,691 tokens; saved reasoning contained 12,058 characters. Draft acceptance 55.98%.
- **DFlash off, thinking budget 2048:** **8/27**, **20.23 minutes**, stopped at the first task's eight-turn limit. Generated 11,381 tokens; saved reasoning contained 28,364 characters.

The scores in `runs/summary.json` identify checks by class and method. An earlier summarizer collapsed identically named methods in different classes; that accounting defect was corrected for this review.

## Independent code findings

Both thinking-off implementations reject valid reordered CSV headers, omit the required word “header” in the empty-input error, and accept malformed quoted CSV containing trailing junk. The DFlash version implements the actual command-line entry point and passes the CLI checks. The baseline leaves `ledgerkit/__main__.py` as a stub, although it places a CLI function in the export module. The plan's task-three file listing was ambiguous about the second path; the specification and starter identify the entry point, but clearer paths and a mandatory CLI check would improve the benchmark.

Both thinking-off versions implement weighted cost using a remaining total-cost accumulator. Recomputing average cost after a partial sale introduces a Decimal rounding drift: `1.666666666666666666666666667` becomes `1.666666666666666666666666666`. The specification requires average cost to remain unchanged on a partial sale.

The two **post-hoc supplemental checks** are separate from the primary 27-check scores. Both thinking-off implementations passed the fsync-failure preservation/cleanup check and failed the partial-sale average-cost check: **1/2 each**. Both 2048 implementations errored on these checks because replay/export were still unimplemented; those are incomplete tasks, not separate findings about completed code. The reference implementation passes both supplemental checks.

## Why the thinking comparison is confounded

The harness froze the worker's own tests after its first RED run. Both 2048 conditions generated incorrect parser tests and later correctly recognized that those tests needed repair:

- DFlash/2048 concatenated CSV headers into data rows while expecting valid case-sensitive IDs to parse successfully.
- Baseline/2048 expected a valid header and valid transaction to raise a header error.

Their requested repairs were blocked by the freeze, and they exhausted the eight-turn limit without progressing to replay or export. These requests were legitimate corrections to invalid tests, **not evidence that the model tried to weaken valid tests to hide a bug**. A failure against an unimplemented stub proves RED, but does not prove the test itself is valid.

Follow-up empirical verification on 2026-10-03 executed the three disputed original tests against the reference parser: all three failed or errored, confirming defective test inputs/expectations independently of the worker implementation. The baseline's proposed replacement passes the reference and retains the intended invalid-header assertion. The DFlash proposal is **incomplete**: it deletes the malformed, assertion-free `test_case_sensitive_id` method but leaves the duplicate header in `test_id_case_sensitive`, which still errors against the reference. A correctly constructed CSV with IDs `a` and `A` succeeds. Thus the models correctly identified test defects, but only the baseline supplied a demonstrated valid repair; the DFlash edit should not have been approved unchanged. No saved benchmark source or tests were modified for this check.

Both 2048 conditions also initially used the wrong JSON action wrapper and recovered after rejection. Thus their lower scores combine test-authoring mistakes, tool-protocol overhead and an overly strict harness policy. This experiment does **not** establish that a 2048-token thinking budget intrinsically reduces coding quality.

## Integrity and verification

All four saved implementations were reviewed independently against the specification and graded artifacts. Protected source contracts, public tests and task documents match their saved hashes. Every accepted worker test file was written once and remains unchanged. Each thinking-off condition has three recorded RED-to-GREEN task cycles; each 2048 condition has one RED cycle and no completed task. Passing visible gates did not imply full acceptance.

The original acceptance grader passed the reference and rejected the starter. Six harness-control tests passed. Supplemental checks ran in isolated containers without editing generated source or tests. Evidence is saved per condition in `runs/`: `independent-grade.log`, `supplemental-grade.log`, `integrity-review.json`, request/response records, thinking traces and implementation diffs.

## Performance interpretation

This was a ROCm matrix at the shared-memory BIOS setting, with full target/draft GPU offload recorded in server logs. All conditions used the same quantized Qwen target, deterministic sampling, 64K context capacity, disabled request caching and a 4,096-token response limit. A 64K capacity is not a test with 64K of occupied context. The thinking allowance was per turn.

DFlash/thinking-off finished 41.8% sooner than baseline/thinking-off, but also generated 38.8% fewer tokens and different code/tests. That elapsed improvement cannot be attributed entirely to speculative decoding. Generation wall rates were 6.22 versus 5.82 tokens/sec; these include prompt processing and are not pure decoding rates. The 2048 conditions had higher wall token rates (10.79 and 9.51) while completing less verified work. Turning thinking off can reduce total latency by avoiding reasoning tokens; it does not guarantee a large increase in token generation speed.

There was only one run per condition in a fixed order. This matrix does not compare ROCm against Vulkan, DFlash1 against DFlash2, or six against seven draft tokens.

## Recommendation

Use **DFlash2 on, six draft tokens, thinking off** as the provisional configuration for a small coding worker following a precise plan, with protected acceptance checks and independent review before accepting its changes. It produced the best partial result here; it is not yet demonstrated to deliver fully correct work unattended.

Before another quality comparison, validate the worker's tests independently or supply planner-reviewed tests. Keep acceptance tests immutable, but provide independent adjudication for legitimate defects in newly authored tests. Make CLI paths explicit and require a CLI smoke check. Repeat matched tasks across configurations after that harness correction. Do not rank 2048 thinking as worse on the basis of these blocked runs, and do not use test count or tokens/sec as a substitute for time to verified completion.
