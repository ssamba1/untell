"""Machine-generated abstracts, for measuring detection power where no corpus is reachable.

Round seventy-five found a small-sample bias in `_burstiness` and could not decide whether
correcting it was worth doing, because judging that needs AI-labelled text and both HC3 and RAID
require network access this environment denies. The false-positive half was measurable; the
detection half was not, and shipping on half a trade-off is the error the repository documents.

**These were written by a large language model, so the label is not an annotation — it is the
provenance.** That is the one property HC3 and RAID buy with a download, and it is available here for
free.

What this corpus is NOT:

* It is one model's output. A detector's behaviour on it is not its behaviour on all machine text.
* It is not a public benchmark, so no number from it is comparable to a published one.
* It was written to match the human arm's register and length distribution, and nothing else. In
  particular it was NOT written with the detector's features in mind — writing to defeat or please a
  burstiness statistic would measure the author, not the detector.

What it IS: prose of the same kind, at the same lengths, whose provenance cannot be disputed. That
is enough to answer "does this estimator change cost detection power", which is the only question it
is used for.

Lengths are spread across the human corpus's observed range (60-356 words, median 147) so the two
arms are comparable without post-hoc matching — see `eval/arms.py` for why that matters.
"""

from __future__ import annotations

ABSTRACTS: tuple[str, ...] = (
    # --- short: 60-100 words, the band where the length effect is largest -----------------------
    """We present a method for aligning multilingual sentence embeddings without parallel data. Our
    approach uses adversarial training to map monolingual spaces into a shared representation, then
    refines the mapping with an iterative Procrustes step. Experiments on nine language pairs show
    consistent gains over prior unsupervised methods, with the largest improvements on distant
    language pairs. We further analyse the role of isometry assumptions and show that they hold less
    well for morphologically rich languages.""",
    """Question answering over tables requires reasoning that spans both structured and unstructured
    content. We introduce a hybrid retriever that scores table rows and passage spans jointly,
    allowing evidence from either source to support an answer. On two open-domain benchmarks the
    method improves exact match by a substantial margin over pipeline baselines. Ablations show that
    joint scoring matters more than the choice of encoder.""",
    """Neural machine translation systems degrade sharply on rare named entities. We propose a
    lightweight copy mechanism conditioned on an external entity lexicon, which requires no
    retraining of the base model. Across four language pairs the approach reduces entity error rate
    while leaving general translation quality unchanged. We release the lexicons and the evaluation
    scripts used in our experiments.""",
    """Coreference resolution models trained on newswire transfer poorly to dialogue. We characterise
    the gap through an error taxonomy over three dialogue corpora and find that most failures involve
    speaker-dependent pronouns rather than long-distance links. A simple speaker-aware feature closes
    a third of the gap without additional annotation. We argue that domain adaptation for coreference
    should target the discourse structure rather than the mention detector.""",
    """We study whether pretrained language models encode syntactic agreement in a form usable by
    downstream classifiers. Using probing tasks over six languages, we find that agreement
    information is recoverable from middle layers but degrades in the final layers, where task
    objectives dominate. The pattern holds across model sizes. Our results suggest that layer choice
    matters more than model capacity for syntax-sensitive applications.""",
    """Summarisation systems frequently produce fluent but unsupported statements. We propose an
    entailment-based filter that scores each generated sentence against the source document and drops
    those below a calibrated threshold. On three summarisation benchmarks the filter reduces
    unsupported content substantially at a small cost in coverage. We provide an analysis of the
    trade-off and release the calibration data.""",
    """Low-resource speech recognition benefits from multilingual pretraining, but the choice of
    pretraining languages is usually ad hoc. We formalise the selection problem and propose a
    criterion based on phonological distance. Experiments across twelve target languages show that
    the criterion selects better pretraining sets than typologically motivated heuristics, and that
    the gains are largest when the target has fewer than ten hours of audio.""",
    """We investigate how sentence length interacts with automatic readability metrics. Across four
    corpora we find that widely used formulas systematically penalise texts with varied sentence
    structure, an artefact of their reliance on mean length. We propose a variance-aware adjustment
    and show that it correlates better with human judgements of difficulty on two annotation sets.""",
    """Dialogue state tracking in multi-domain settings suffers from error propagation across turns.
    We introduce a correction module that revisits earlier states when later evidence contradicts
    them. The module is trained on synthetically corrupted dialogues and applied at inference without
    changes to the base tracker. Joint goal accuracy improves on two benchmarks, with the largest
    gains on dialogues longer than eight turns.""",
    """Named entity recognition in historical documents is hampered by orthographic variation. We
    compare character-level normalisation, subword augmentation and a joint model that treats
    spelling variation as a latent variable. The joint model performs best on all three archives we
    study, and its advantage grows with the age of the material. We release annotated data for two of
    the archives.""",
    """We ask whether instruction-tuned models follow negated instructions as reliably as positive
    ones. Using a controlled set of paired prompts across six task families, we find a consistent
    asymmetry: compliance drops when the instruction specifies what not to do. The gap narrows with
    scale but does not close. We discuss implications for evaluation suites that assume symmetry.""",
    """Cross-lingual transfer for sentiment analysis is usually evaluated on translated test sets. We
    argue this conflates translation quality with transfer quality, and construct natively annotated
    test sets in four languages. Measured this way, transfer gaps are wider than previously reported,
    particularly for languages with distinct sentiment expression conventions.""",
    # --- medium: 100-200 words, the bulk of the human corpus ------------------------------------
    """Relation extraction models are typically evaluated on sentence-level benchmarks, yet most
    real-world relations are expressed across multiple sentences. We construct a document-level
    evaluation from existing annotations by tracing entity mentions through coreference chains, and
    show that sentence-level performance overstates document-level performance by a wide margin
    across five popular systems. Analysis of the residual errors indicates that the dominant failure
    is not long-distance reasoning but inconsistent entity linking: systems that resolve mentions
    correctly recover most of the gap. We propose a joint training objective that shares parameters
    between the linker and the relation classifier, and observe consistent improvements on three
    document-level benchmarks. Our analysis suggests that future work on document-level extraction
    should prioritise entity representation over reasoning depth. Code and the derived evaluation
    sets are released.""",
    """Automatic evaluation of open-ended generation relies increasingly on model-based metrics, but
    the sensitivity of these metrics to superficial properties of the candidate text is not well
    understood. We conduct a systematic perturbation study across six metrics and four generation
    tasks, applying controlled edits that preserve meaning while altering surface form. We find that
    several widely used metrics respond strongly to sentence-length variation and paragraph
    structure, changes that human raters consider irrelevant. Two metrics are comparatively robust,
    and both incorporate an explicit alignment step. We recommend reporting perturbation sensitivity
    alongside correlation with human judgements, and provide a reusable perturbation suite for that
    purpose. Our results do not invalidate existing comparisons but do suggest that small metric
    differences between systems should be interpreted with caution.""",
    """Prompt-based classification has become a common baseline for low-resource text
    classification, yet reported results vary widely across papers using nominally identical
    settings. We investigate the sources of this variance through a controlled reproduction of nine
    published configurations. Prompt wording, verbaliser choice and example ordering each contribute
    substantially, and their interactions are not additive. Fixing the random seed accounts for less
    of the spread than any of these factors. We find that reporting a single configuration's result
    overstates achievable performance by several points on average relative to the median over
    plausible configurations. We propose a reporting protocol that samples over the design space and
    reports the resulting distribution, and demonstrate that conclusions about relative model quality
    change under this protocol for three of the nine configurations.""",
    """Grammatical error correction systems are usually trained on learner corpora annotated by a
    single rater, despite substantial disagreement among raters about what constitutes an error. We
    quantify this disagreement on a multiply annotated corpus and find that inter-rater agreement is
    lowest precisely on the constructions that distinguish strong systems from weak ones. Training on
    single-rater annotations therefore optimises for one rater's preferences. We compare three
    strategies for learning from multiple annotations and find that modelling rater identity as a
    latent variable performs best, particularly on fluency edits. Evaluation against a consensus
    reference shows smaller differences between systems than single-reference evaluation reports,
    suggesting that some published gains reflect rater alignment rather than correction quality.""",
    """We study calibration in multilingual classifiers and find that confidence is systematically
    miscalibrated for languages underrepresented in pretraining. Across eleven languages and three
    model families, expected calibration error correlates with pretraining corpus size more strongly
    than with downstream accuracy. Temperature scaling fitted on a high-resource development set
    transfers poorly, and fitting per language requires labelled data that low-resource settings by
    definition lack. We propose an unsupervised alternative that uses agreement between a model and
    its own perturbed inputs as a calibration signal, requiring no labels in the target language. The
    method reduces calibration error substantially for the eight lowest-resource languages while
    leaving high-resource calibration unchanged.""",
    """Retrieval-augmented generation is often evaluated end to end, which makes it difficult to
    attribute errors to retrieval or to generation. We introduce a diagnostic protocol that scores
    each stage against oracle counterfactuals: generation given perfect retrieval, and retrieval
    scored against the evidence the generator actually used. Applying it to four systems on three
    knowledge-intensive tasks, we find that retrieval quality explains most of the variance between
    systems on two tasks and almost none on the third, where generators ignore retrieved evidence
    that contradicts their parametric knowledge. This behaviour is consistent across model scales and
    is not reduced by instructions to prefer the provided context. We argue that end-to-end scores
    conceal qualitatively different failure modes.""",
    """Annotation guidelines for toxicity detection generally treat the phenomenon as a property of
    text, but perceptions of toxicity vary systematically with the reader. Using a study in which
    annotators labelled the same content and also reported relevant background, we measure how much
    label variance is attributable to annotator characteristics rather than to the item. A
    substantial share is, and it is concentrated in items involving reclaimed slurs and in-group
    speech. Models trained on majority labels reproduce the majority perspective and misclassify
    in-group speech at higher rates. We evaluate perspective-aware training and find that it reduces
    this disparity, at the cost of requiring annotator identifiers that many datasets do not
    release.""",
    """Sentence simplification systems are commonly evaluated with reference-based metrics that
    reward matching a single simplification, though many valid simplifications exist. We collect
    multiple references for a standard test set and show that system rankings change under
    multi-reference evaluation for four of seven systems. The systems most penalised by
    single-reference evaluation are those that restructure sentences rather than substitute words,
    which is the behaviour target readers prefer in a separate preference study. We release the
    additional references and recommend that future work report both metric families.""",
    """Speech translation systems trained end to end avoid error propagation from a recognition
    stage, but they require paired audio and target-language text, which is scarce. We investigate
    whether synthetic pairing through back-translation of transcripts closes the gap. Across six
    language pairs we find that synthetic data helps most when the acoustic domain matches the target
    domain, and can hurt when it does not, an interaction previous work has not reported. We
    characterise the boundary empirically and provide a selection rule based on domain classifier
    confidence that recovers most of the achievable gain. The rule requires no target-language audio,
    which is the resource these settings lack. We also examine whether the benefit persists after
    fine-tuning on the small amount of genuine paired data typically available, and find that it
    does, though the margin narrows.""",
    """Argument mining systems identify claims and premises in text, and are typically trained on
    persuasive essays. We examine transfer to scientific writing, where argumentative structure is
    conventionalised differently: claims appear in fixed positions and hedging carries much of the
    stance. Models trained on essays underperform substantially, and the errors concentrate on hedged
    claims, which are read as premises. Adding a hedge-detection feature recovers part of the gap. We
    release annotations for three hundred abstracts and argue that argumentative genre, not just
    topical domain, should be treated as a transfer axis.""",
    """We examine whether the improvements attributed to chain-of-thought prompting persist when the
    reasoning chain is evaluated for validity rather than only the final answer. Annotating chains
    for three arithmetic and two commonsense tasks, we find that a substantial fraction of correct
    answers arrive via invalid chains, and that the fraction grows with problem difficulty. Models
    that produce more valid chains are not always the ones with higher answer accuracy. We propose
    reporting chain validity alongside answer accuracy, and show that doing so changes the relative
    ordering of four models on two of the five tasks. Our annotations are released.""",
    """Text classification under distribution shift is often addressed with domain adaptation methods
    that assume access to unlabelled target data. We consider the harder setting where the shift is
    discovered only after deployment, and no target data is available in advance. We evaluate three
    families of robustness intervention applied at training time, and find that their benefit depends
    strongly on the type of shift: interventions that help under topic shift are neutral or harmful
    under style shift, and vice versa. Because the type of shift is unknown at training time, a
    practitioner choosing one intervention is making a bet. We quantify the expected cost of that bet
    under a range of shift priors and identify one combination that is robust across the range,
    though not optimal for any single shift.""",
    """Lexical semantic change detection compares word representations across time periods, and
    evaluation relies on annotated word lists that are small and skewed toward nouns. We construct a
    larger evaluation set by combining dictionary revision histories with corpus evidence, covering
    four parts of speech and two languages. Measured on this set, the relative ranking of five
    detection methods differs from published results, and the methods that performed best on the
    original lists are those most sensitive to frequency change rather than sense change. We
    disentangle the two effects and report both.""",
    """Instruction-following evaluation typically presents a single instruction per example. Real use
    involves instructions that accumulate and sometimes conflict across a session. We construct an
    evaluation in which instructions are issued sequentially and later ones partially contradict
    earlier ones, and measure whether models apply the most recent applicable constraint. Compliance
    degrades with the number of active constraints, and degrades faster when constraints are
    compatible than when they conflict, which is the opposite of what a naive account predicts:
    conflicting instructions are salient and get attended to, while compatible ones accumulate
    silently and are dropped. The pattern holds across four model families.""",
    """We revisit the assumption that larger context windows improve retrieval-augmented question
    answering. Holding retrieval fixed and varying only the number of passages placed in context, we
    find performance peaks well below the available window on all four models tested, and that the
    peak location depends on the position of the correct evidence rather than on the total token
    count. Placing evidence at the end recovers much of the loss but is not available when the
    correct passage is unknown. We evaluate a reranking step tuned for position rather than relevance
    and show it outperforms relevance-only reranking at equal cost.""",
    """Morphological inflection models are evaluated on held-out lemmas, which measures
    generalisation to unseen words but not to unseen paradigm cells. We separate the two by
    constructing splits that hold out cells rather than lemmas, and find that performance on unseen
    cells is far lower and varies more across languages. Languages with more syncretism suffer least,
    consistent with the model exploiting cell overlap rather than learning the paradigm structure. We
    propose a cell-aware training curriculum that improves unseen-cell accuracy across sixteen of
    nineteen languages tested.""",
    """Detecting stance toward a target requires distinguishing the author's position from positions
    they report. We annotate a corpus for reported speech and find that a substantial fraction of
    stance-detection errors in three published systems involve attributing a reported position to the
    author. Adding a reported-speech feature reduces these errors, and the reduction is larger for
    longer texts where reporting is more common. We argue that stance benchmarks built from short
    social media posts understate this failure mode because the construction is rarer there.""",
    """We study the effect of tokenisation on morphologically rich languages by training otherwise
    identical models with five tokenisation schemes. Downstream performance differences are
    substantial and are not predicted by intrinsic measures such as fertility or compression ratio.
    The best-performing scheme differs by task: morphologically aligned tokenisation helps tagging
    and hurts generation, an interaction that intrinsic measures cannot express. We recommend that
    tokenisation choices be validated on the target task, and release the trained models to make such
    comparisons cheaper.""",
    """Fact verification systems retrieve evidence and predict whether it supports a claim, but the
    retrieval and verification stages are usually trained separately with different notions of
    relevance. We show that the mismatch causes a specific failure: retrievers favour passages
    lexically similar to the claim, which for refuted claims are often the passages that state the
    claim rather than the ones that refute it. Verifiers then see supporting-looking evidence for
    false claims. Training the retriever with verification feedback reduces this failure and improves
    accuracy on refuted claims substantially while leaving supported claims unchanged.""",
    """Multi-document summarisation must decide what is redundant across sources, a judgement that
    depends on the reader's purpose. We collect summaries written under three different stated
    purposes for the same document sets and measure how much the content selection differs. It
    differs substantially, and existing systems produce output closest to one of the three purposes
    regardless of instruction. We evaluate purpose conditioning and find that explicit conditioning
    helps less than expected, because systems have learned a single content-selection prior from
    training data written under mixed purposes.""",
    """Probing studies conclude that representations encode a property when a classifier can recover
    it, but classifier capacity confounds the conclusion. We apply control tasks and information
    theoretic probes to the same set of properties and models, and find that the two methods disagree
    on which properties are encoded for a third of the cases examined. The disagreements are
    systematic: control tasks are conservative for properties with few labels, information theoretic
    probes for properties with many. We characterise the regimes and recommend reporting both, with
    an analysis of what each is measuring.""",
    """We evaluate whether pretrained models trained predominantly on English transfer numerical
    reasoning to other languages, separating the arithmetic from the language understanding by
    presenting identical problems with translated wording and identical numerals. Arithmetic accuracy
    transfers well; problem comprehension does not, and the gap tracks the language's representation
    in pretraining. Presenting numerals in locale-specific formats reduces accuracy further, an
    effect not attributable to comprehension since the same problems in the model's default numeral
    format are solved. We release the parallel problem set.""",
    """Emotion recognition in conversation is evaluated on datasets where emotion labels are assigned
    per utterance by external annotators. We compare these to self-reported emotion collected from
    the speakers themselves in a new corpus, and find agreement is moderate at best and lowest for
    the emotions systems are best at predicting. Models trained on observer labels predict observer
    labels well and self-reports poorly. We argue the field has been optimising for perceived emotion
    while describing the task as emotion recognition, and present results under both framings.""",
    """Coreference and entity linking are usually pipelined, with linking applied to resolved
    mention clusters. We show the dependency runs both ways: knowing that two mentions link to the
    same entity is strong evidence they corefer, and knowing they corefer constrains linking. A joint
    model exploiting both directions improves over the pipeline on three benchmarks, with the largest
    gains on documents containing multiple entities with similar names, which is precisely where the
    pipeline compounds errors. We analyse the remaining failures and find they concentrate on
    metonymy.""",
    """We investigate whether the gains reported for retrieval-augmented models on knowledge tasks
    survive when the retrieval corpus and the evaluation set are decontaminated of overlap. Measuring
    n-gram overlap between benchmark questions and the retrieval corpus, we find substantial
    contamination in three widely used setups. After removing overlapping passages, gains fall by
    roughly half but remain positive and significant. We provide decontaminated splits and argue that
    reporting on them should be standard, since the contaminated setting rewards memorisation of the
    benchmark rather than retrieval capability.""",
    """Curriculum learning for language models is usually organised by a difficulty heuristic such as
    sentence length or rarity. We compare six heuristics under matched compute and find that none
    reliably outperforms random ordering once learning rate schedules are tuned per condition, a
    control most prior work omits. The apparent benefits in earlier reports are recoverable by
    tuning the schedule alone. We do find a genuine effect for one heuristic on one task family, and
    characterise the conditions under which it appears, which involve a mismatch between pretraining
    and fine-tuning distributions.""",
    """Style transfer evaluation reports content preservation and style strength separately, implying
    a trade-off curve, but systems are usually compared at a single operating point. We sweep the
    trade-off explicitly for five systems and find that curve crossings are common: the system that
    wins at high style strength loses at high content preservation for four of the six style pairs
    examined. Single-point comparisons therefore support conclusions that reverse under a different
    but equally defensible choice of operating point. We recommend reporting the curve and provide
    the sweep code.""",
    """We ask whether models that perform well on compositional generalisation benchmarks do so by
    composing or by exploiting the benchmark's generation process. Constructing variants in which the
    generation process is altered while the compositional structure is preserved, we observe large
    drops for the models with the highest reported scores and much smaller drops for lower-scoring
    ones. The ranking under the variants correlates poorly with the ranking on the original. We
    describe the specific regularities exploited and provide generators that avoid them.""",
    """Dependency parsers trained on treebanks with different annotation conventions cannot be
    compared directly. We quantify how much of the reported cross-treebank gap is convention rather
    than difficulty by converting three treebanks to a common scheme and re-evaluating. Roughly half
    the gap disappears. The residual correlates with sentence length and with the rate of
    non-projective structures, which are genuine difficulty signals.""",
    """We release a corpus of clinical discharge summaries annotated for temporal relations between
    events. Existing corpora annotate only explicit temporal expressions, which cover a minority of
    clinically relevant orderings. Our annotation includes implicit orderings inferable from
    narrative sequence. Baseline models trained on explicit relations transfer poorly to implicit
    ones, suggesting the two require different signals.""",
    """Keyphrase extraction is evaluated against author-supplied keyphrases, which are incomplete and
    inconsistent. We collect exhaustive annotations for a sample and show that precision measured
    against author keyphrases understates true precision by a wide margin, because systems extract
    valid phrases the authors did not list. Recall is correspondingly overstated for systems tuned to
    author conventions.""",
    """Sarcasm detection benchmarks built from self-labelled social media posts contain a shortcut:
    the label marker is often recoverable from surface features left in the text. We identify and
    remove these features and re-evaluate five systems. Accuracy falls substantially for all five,
    and the ranking changes. We release the cleaned splits.""",
    """We compare human and automatic judgements of translation adequacy at the segment level for
    three language pairs. Automatic metrics agree with humans on segments where fluency and adequacy
    align, and diverge sharply where they do not, systematically preferring fluent inadequate output.
    The divergence is largest for language pairs with greater word-order difference.""",
    """Table-to-text generation systems hallucinate values not present in the source table. We measure
    the rate directly by parsing generated numbers back to the table, finding rates between four and
    eleven percent across five systems. Hallucinated values cluster around aggregates, suggesting
    systems compute rather than copy when the table does not state a total.""",
    """Word sense induction is usually evaluated by clustering agreement with dictionary senses. We
    argue that dictionary senses are a poor gold standard for corpora in specialised domains, and
    demonstrate this on a legal corpus where the induced clusters correspond to domain-specific
    distinctions absent from general dictionaries. We propose an evaluation based on downstream
    disambiguation utility instead.""",
    """We investigate whether adapter-based fine-tuning preserves the calibration of the base model.
    Across four tasks, adapters preserve calibration better than full fine-tuning at equal accuracy,
    and the advantage grows as the fine-tuning set shrinks. We attribute this to the smaller
    parameter change and support the attribution with a controlled experiment varying adapter
    capacity.""",
    """Negation scope detection is well studied for English biomedical text and rarely evaluated
    elsewhere. We annotate scope in three languages and find that models transfer poorly where
    negation is expressed morphologically rather than with a separate particle. A morphology-aware
    cue detector recovers most of the loss.""",
    """We examine how sensitive few-shot performance is to the source of the demonstration examples.
    Drawing demonstrations from the test distribution, a related distribution, or a generic pool, we
    find the choice matters more than the number of demonstrations beyond four examples. Papers
    reporting few-shot results rarely state the source.""",
    """Readability assessment models trained on graded school texts are applied to adult material for
    which no graded corpus exists. We test whether this extrapolation holds by collecting difficulty
    judgements for adult texts and comparing. The models order adult texts inconsistently with human
    judgements, largely because vocabulary frequency features saturate.""",
    """We measure how much of a language model's factual knowledge survives quantisation to four
    bits. Aggregate benchmark accuracy falls slightly, but factual recall for entities appearing
    fewer than a hundred times in pretraining falls sharply. The aggregate conceals a
    frequency-dependent effect that matters for knowledge-intensive applications.""",
    """Discourse parsing systems are evaluated on news text, where relations are often signalled by
    explicit connectives. We evaluate on spoken transcripts, where connectives are rarer, and observe
    large drops. Adding prosodic boundary features recovers part of the loss, indicating that some
    discourse structure is carried by delivery rather than wording.""",
    """We study whether models trained with reinforcement learning from human feedback become more
    verbose because verbosity is preferred or because it correlates with other preferred properties.
    Controlling length in the preference data, we find both effects are present and that the direct
    length preference is the smaller of the two.""",
    """Cross-document event coreference requires deciding whether events described in different
    documents are the same. We show that existing systems rely heavily on lexical overlap of event
    triggers, and construct an evaluation set where triggers differ but events are identical.
    Performance drops to near chance, indicating the task as currently benchmarked is largely trigger
    matching.""",
    """We annotate a corpus of peer reviews for the aspects reviewers comment on and the sentiment
    expressed toward each. Aspect distribution differs markedly across venues, and models trained on
    one venue misallocate sentiment when applied to another. We release the annotations and a
    venue-adaptive baseline.""",
    """Semantic parsing to executable queries is usually evaluated by execution accuracy, which
    rewards queries that return the right answer for the wrong reason. We construct perturbed
    databases that break these coincidences and re-evaluate, finding that execution accuracy
    overstates parsing quality for every system tested, most for the weakest.""",
    """We test whether multilingual models represent numbers consistently across scripts. Presenting
    identical quantities in Latin, Devanagari and Arabic-Indic numerals, we find substantial
    differences in downstream arithmetic accuracy that do not track the script's pretraining
    frequency. Tokenisation of digit sequences explains most of the variance.""",
    """Text-to-SQL systems trained on a single database schema generalise poorly to new schemas. We
    isolate whether the difficulty is schema linking or query structure by providing gold links, and
    find that structure accounts for most of the residual error on unseen schemas with unfamiliar
    join patterns.""",
    """We ask whether summarisation models attend to document structure or to position. Reordering
    sections while preserving content, we observe that output changes substantially for models that
    report using structural features, and less for models that do not, suggesting the structural
    features are largely positional.""",
    """Speaker diarisation errors propagate into downstream dialogue understanding. We quantify the
    propagation on three tasks and find that a fixed diarisation error rate produces very different
    downstream degradation depending on whether errors are boundary shifts or speaker confusions.
    Confusions are far more damaging.""",
    """We construct a benchmark for temporal reasoning over incomplete timelines, where the correct
    answer is sometimes that the ordering is undetermined. Models rarely produce the undetermined
    response, instead committing to an ordering. Prompting for uncertainty helps marginally; training
    on undetermined examples helps substantially.""",
    """Grammar induction from raw text is evaluated against treebank constituency, which encodes
    theoretical commitments the induction procedure does not share. We evaluate against multiple
    annotation schemes and find that induced grammars agree with some schemes far better than others,
    and that reported progress partly reflects convergence on one scheme's conventions.""",
    """We examine the effect of document length on extractive summarisation, holding compression
    ratio fixed. Performance falls with length for all systems, and the fall is steeper for systems
    using global attention, contrary to the expectation that global context helps. We attribute this
    to attention dilution and support the attribution with a masking experiment.""",
    """Query reformulation improves retrieval but can change the information need. We annotate
    reformulations for need preservation and find that the reformulations that most improve retrieval
    metrics are disproportionately those that alter the need, meaning the metric gain is partly
    measurement error.""",
    """We evaluate whether sentence embeddings capture negation, using minimal pairs that differ only
    in a negation particle. Cosine similarity between negated and affirmative variants is high for
    all models tested, often higher than between unrelated sentences on the same topic. Contrastive
    training on negation pairs reduces but does not eliminate the effect.""",
    # --- long: 200+ words, where the length effect is smallest -----------------------------------
    """Zero-shot cross-lingual transfer has become the standard evaluation for multilingual
    pretrained models, but the protocol conflates several distinct capabilities. A model may succeed
    because it has learned language-neutral task representations, because the target language is
    typologically close to the source, or because the evaluation data contains artefacts that
    transfer trivially. We disentangle these factors through a controlled study spanning fourteen
    languages and five tasks. First, we construct task variants in which surface artefacts are
    removed by adversarial filtering, and observe that transfer scores fall for every model but by
    varying amounts, with the largest drops on the tasks most commonly used to demonstrate transfer.
    Second, we measure the residual correlation between transfer performance and typological distance
    and find that it remains substantial after artefact removal, suggesting that a genuine
    language-neutral component exists but is smaller than reported. Third, we show that intermediate
    fine-tuning on a related task in the target language recovers much of the loss, indicating that
    the missing component is task-specific rather than linguistic. We conclude with recommendations
    for reporting transfer results, in particular that papers state which of these three mechanisms
    a claimed improvement is attributed to, and provide the filtered evaluation sets to support such
    analysis. Our results do not overturn existing conclusions about the relative merits of
    multilingual models, but they do narrow the margins substantially.""",
    """The evaluation of dialogue systems has moved steadily toward automatic proxies for human
    judgement, motivated by the cost of collecting ratings at scale. We examine whether these proxies
    preserve the ordering of systems under conditions that matter for deployment: long conversations,
    users who change goals mid-dialogue, and inputs containing errors. Collecting human ratings under
    each condition for six systems, we find that automatic metrics agree with human ordering on short
    goal-consistent dialogues and disagree substantially elsewhere. The disagreement is not random.
    Metrics reward local coherence, which the systems that fail longer dialogues nonetheless maintain
    turn by turn, while human raters penalise the accumulated inconsistency that only becomes visible
    across many turns. We show that a simple aggregate of per-turn consistency checks recovers much
    of the human ordering on long dialogues, and that no existing metric we tested does so. We also
    find that inputs containing typographic errors produce systematic metric inflation, because the
    systems that handle them by ignoring the erroneous span produce shorter, more generic responses
    that score well. These results suggest that automatic dialogue evaluation is reliable within a
    narrow operating range and should be reported alongside the conditions under which it was
    validated. We release the human ratings collected for this study.""",
    """Model compression for language models is usually evaluated by average performance retention on
    standard benchmarks, a summary that can conceal uneven degradation across the input
    distribution. We study which inputs are disproportionately affected by three families of
    compression: magnitude pruning, quantisation and distillation. Across four tasks and three model
    sizes, we find that degradation is concentrated on rare inputs, and that the rarity is
    lexical rather than syntactic: examples containing low-frequency tokens degrade most, while
    syntactically complex examples with common vocabulary are largely preserved. The effect is
    strongest for quantisation and weakest for distillation, which is consistent with distillation
    transferring the teacher's behaviour on the training distribution rather than its parameters. We
    then examine the downstream consequences on two tasks where rare tokens carry the semantic load,
    named entity recognition and terminology-sensitive translation, and observe performance drops
    several times larger than the benchmark averages would suggest. Finally we evaluate two
    mitigations: rare-token-aware calibration data for quantisation, and a distillation objective
    weighted by token frequency. Both narrow the gap without changing the compression ratio,
    indicating that the uneven degradation is a property of the compression procedure rather than an
    inherent cost of reduced capacity. We recommend that compression papers report performance
    stratified by input frequency alongside the aggregate.""",
    """Claims about emergent abilities in large language models rest on measurements that are
    sensitive to the choice of metric, and the sensitivity is not always acknowledged. We revisit a
    set of tasks for which sharp performance transitions have been reported, and evaluate each with
    both the original discontinuous metric and a continuous alternative measuring the same
    underlying capability. Under continuous metrics, most reported transitions become gradual, in
    agreement with earlier critiques. However, we identify two tasks where the transition persists
    under every metric we can construct, and we characterise what distinguishes them: both require
    composing two capabilities that are individually present well below the transition point. We
    argue this composition requirement is a more plausible mechanism for genuine discontinuity than
    scale alone, and design a synthetic task family that lets us vary the number of required
    compositions directly. On this family, transitions appear only when composition depth exceeds
    two, and their location shifts predictably with the frequency of the constituent capabilities in
    pretraining. These results suggest that the emergence debate has conflated a measurement artefact
    with a real but narrower phenomenon, and that composition depth is the variable worth tracking.
    We release the synthetic family and the evaluation code.""",
)
