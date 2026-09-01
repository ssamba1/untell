"""The same author, two registers — to separate what a detector reads from what it claims to read.

Round eighty-one found the AI-tell catalogue firing on 48.1% of human academic abstracts and 8.6% of
machine ones. Two explanations fit: the catalogue is broken, or the catalogue reads *register* and
academic abstracts are written in the register it flags.

Those are distinguishable by holding authorship constant and varying register. Everything in this
file was written by the same language model that wrote `generated_abstracts.py`, in the same session.
If the catalogue is reading authorship, the counts should be similar. If it is reading register, the
assistant-style and promotional passages should light it up while the abstracts stay dark.

**No human arm here, and none is needed.** The comparison is machine-against-machine; the question is
whether the detector's output depends on something other than who wrote the text, and a difference
between two same-author arms answers that on its own.

`ASSISTANT` is the chatbot-reply register — the one LLM output is stereotyped for, and the one
`ai-tells.md` was built from. `PROMOTIONAL` is marketing copy, the register the vocabulary list's
`best-in-class` / `turnkey` / `supercharge` cluster belongs to.
"""

from __future__ import annotations

ASSISTANT: tuple[str, ...] = (
    """Great question! Let me break this down for you. There are several key factors to consider
    when choosing a database for your application. First and foremost, it's important to note that
    the right choice depends on your specific use case. Additionally, you'll want to think about
    scalability, consistency guarantees, and operational overhead. Moreover, the ecosystem around a
    database often matters more than its raw performance characteristics. In conclusion, there is no
    one-size-fits-all answer, but I hope this comprehensive overview helps you navigate the
    decision.""",
    """Certainly! I'd be happy to help you understand this concept. In essence, recursion is a
    powerful technique where a function calls itself to solve smaller instances of the same problem.
    It's crucial to define a base case, otherwise the function will recurse indefinitely.
    Furthermore, it's worth noting that some problems are more naturally expressed recursively than
    iteratively. That said, recursion can be less efficient in languages without tail-call
    optimisation. Ultimately, understanding when to leverage recursion is a valuable skill.""",
    """Absolutely! Here's a comprehensive guide to improving your writing. First, it's important to
    note that clarity should always be your primary goal. Second, you'll want to vary your sentence
    structure to maintain reader engagement. Third, robust editing is where most of the real
    improvement happens. Additionally, reading your work aloud can reveal awkward phrasing that the
    eye glosses over. In conclusion, writing well is a skill that can be cultivated through
    deliberate practice.""",
    """That's a fantastic point, and you're absolutely right to raise it. Let me elaborate on the
    nuances involved. The interplay between these two systems is multifaceted, and it's crucial to
    understand that neither operates in isolation. Moreover, the landscape has shifted considerably
    in recent years. It's worth noting that best practices have evolved accordingly. Ultimately, a
    holistic approach that leverages the strengths of both will yield the most robust outcome.""",
    """Sure, here's how to approach this problem. To begin with, you'll want to establish a clear
    understanding of your requirements. Subsequently, you can evaluate the available options against
    those criteria. It is important to note that this process is iterative rather than linear.
    Furthermore, don't underestimate the value of prototyping early. In summary, a methodical
    approach will save you considerable time down the line.""",
    """I understand your concern, and it's a valid one. Let's delve into the details. The key
    consideration here is that performance optimisation should always be guided by measurement rather
    than intuition. Additionally, premature optimisation can introduce unnecessary complexity.
    Moreover, the bottleneck is rarely where you expect it to be. To summarise, profile first,
    optimise second, and remember that readable code has its own value.""",
    """Great to hear you're exploring this topic! There are several noteworthy aspects to consider.
    Firstly, the underlying architecture plays a pivotal role in determining what is achievable.
    Secondly, it's essential to understand the trade-offs involved. Thirdly, the tooling ecosystem
    has matured significantly. In conclusion, this is an exciting area with plenty of opportunity for
    those willing to invest the time.""",
    """Of course! I'd be delighted to explain. At its core, the concept revolves around the idea that
    complex behaviour can emerge from simple rules. It's important to note that this principle
    appears across many domains. Furthermore, the implications are profound and far-reaching. That
    said, it's crucial not to overstate the analogy. Ultimately, the framework provides a valuable
    lens through which to view these systems.""",
    """Thanks for the thoughtful question! Let me provide a comprehensive answer. The short version
    is that both approaches have merit, and the optimal choice hinges on your constraints. To
    elaborate: the first offers simplicity and ease of maintenance, while the second delivers
    superior performance at the cost of additional complexity. Moreover, your team's familiarity with
    each should factor into the decision. In conclusion, I'd recommend starting simple and evolving
    as needed.""",
    """Happy to help! Here's a step-by-step breakdown. Step one: identify the root cause rather than
    treating symptoms. Step two: establish a reproducible test case. Step three: implement a targeted
    fix. Step four: verify the fix and add a regression test. It's crucial to resist the temptation
    to skip step two. Additionally, documenting what you found will save the next person
    considerable time.""",
    """You raise an excellent point. Let me address it directly. The tension you've identified is
    real and well documented. On the one hand, flexibility enables adaptation to changing
    requirements. On the other hand, it introduces surface area for error. Moreover, the right
    balance shifts as a system matures. Ultimately, this is a judgement call that benefits from
    experience rather than a universal rule.""",
    """Certainly, I can walk you through that. The process begins with data collection, which is
    foundational to everything that follows. Next comes cleaning and normalisation, a step that is
    often underestimated but crucial to the quality of the final result. Subsequently, you'll want to
    explore the data before modelling it. In conclusion, a disciplined pipeline pays dividends
    throughout the project lifecycle.""",
)

PROMOTIONAL: tuple[str, ...] = (
    """Our best-in-class platform empowers teams to unlock unprecedented productivity. With a
    comprehensive suite of cutting-edge features, you'll supercharge your workflow from day one. The
    turnkey solution seamlessly integrates with your existing stack, delivering actionable insights
    that drive real business outcomes. Join thousands of forward-thinking organisations who have
    already transformed the way they work.""",
    """Introducing the next-level analytics engine built for the modern enterprise. Leveraging
    state-of-the-art machine learning, our robust platform delivers a holistic view of your customer
    journey. The intuitive interface makes powerful insights accessible to every stakeholder, while
    enterprise-grade security ensures your data remains protected. Elevate your decision-making with
    a solution built to scale.""",
    """Revolutionise your content strategy with our innovative, AI-powered toolkit. Streamline
    production, foster collaboration, and amplify your reach across every channel. The scalable
    architecture grows with your ambitions, and the seamless onboarding means you'll be up and
    running in minutes. Discover why industry leaders trust us to power their most impactful
    campaigns.""",
    """Unlock the full potential of your data with our transformative platform. Purpose-built for
    scale, it harnesses cutting-edge technology to surface the insights that matter most. Our
    comprehensive integration ecosystem means no data source is out of reach. Take the guesswork out
    of strategy and empower your team with clarity.""",
    """Say goodbye to manual processes and hello to intelligent automation. Our turnkey solution
    eliminates repetitive work so your team can focus on what truly matters. With a bespoke
    onboarding experience and world-class support, you're never navigating alone. Start your journey
    toward operational excellence today.""",
    """The definitive platform for teams who refuse to compromise. Combining unparalleled performance
    with an elegant, intuitive experience, it sets a new standard for what collaboration software can
    be. Our relentless focus on user experience means every interaction feels effortless. See why
    we're the fastest-growing solution in the category.""",
    """Elevate your customer experience with our cutting-edge engagement suite. Deliver personalised,
    timely interactions at scale, powered by sophisticated behavioural modelling. The seamless
    omnichannel architecture ensures a consistent experience wherever your customers are. Drive
    loyalty, boost retention, and unlock sustainable growth.""",
    """Built by practitioners, for practitioners. Our platform distils decades of hard-won expertise
    into a streamlined workflow that just works. No bloated feature lists, no steep learning curve —
    just a robust, reliable foundation for your most critical work. Experience the difference that
    thoughtful design makes.""",
    """Transform raw data into a strategic asset with our comprehensive intelligence platform.
    Leveraging best-in-class processing and an extensible plugin architecture, it adapts to your
    workflow rather than the other way around. Unlock actionable insights, accelerate
    decision-making, and stay ahead of the curve.""",
    """The all-in-one solution your team has been waiting for. Consolidate your tooling, eliminate
    context-switching, and reclaim hours every week. Our seamless integrations and powerful
    automation deliver immediate value, while enterprise-grade reliability gives you peace of mind.
    Get started free — no credit card required.""",
    """Scale without limits on infrastructure engineered for the demands of modern applications. Our
    globally distributed architecture delivers exceptional performance wherever your users are, and
    intelligent auto-scaling means you only pay for what you use. Focus on building; we'll handle the
    rest.""",
    """Empower every member of your organisation with self-service analytics. Our intuitive,
    no-code interface democratises access to insight, while robust governance keeps your data secure
    and compliant. Foster a genuine culture of data-driven decision-making across every team.""",
)
