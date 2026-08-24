const features = [
  {
    title: "7.5+ rated, always",
    description:
      "Every pick is strictly filtered for a 7.5 or higher rating on IMDb/TMDb with a meaningful number of votes — no filler.",
  },
  {
    title: "Already in your plan",
    description:
      "Only recommends titles included in your standard streaming subscriptions (Netflix, Prime Video, Apple TV+, Peacock, Max). No rentals, no surprise charges.",
  },
  {
    title: "Written for your taste",
    description:
      "Gemini writes a spoiler-free, 3–4 sentence pitch for each pick, tuned to what you've watched and liked before.",
  },
  {
    title: "Learns every week",
    description:
      "Your reactions — loved it, watching tonight, not for me — refine the taste profile for next Friday's picks.",
  },
];

const steps = [
  {
    step: "01",
    title: "Pull the field",
    description: "Fetches trending and top-rated titles from TMDb.",
  },
  {
    step: "02",
    title: "Filter hard",
    description:
      "Drops anything under 7.5 or not included in your base subscriptions.",
  },
  {
    step: "03",
    title: "Curate three",
    description:
      "Gemini picks the 3 best matches for your taste and writes a short pitch for each.",
  },
  {
    step: "04",
    title: "Deliver on Friday",
    description:
      "Lands in Telegram with one-tap buttons to react and teach it for next time.",
  },
];

export default function Home() {
  return (
    <div className="mx-auto max-w-3xl px-6">
      <section className="py-20 sm:py-28">
        <span className="inline-flex items-center gap-2 text-sm font-medium text-red-600">
          <span className="h-2 w-2 rounded-full bg-red-600" />
          Every Friday, 5pm ET
        </span>
        <h1 className="mt-4 text-4xl font-semibold tracking-tight sm:text-5xl">
          Three great movies, every Friday.
        </h1>
        <p className="mt-6 max-w-xl text-lg leading-relaxed text-black/60 dark:text-white/60">
          An autonomous agent that curates three high-quality movie
          recommendations each week — filtered to what&apos;s already in your
          streaming plans — and delivers them straight to Telegram.
        </p>
        <div className="mt-8 flex flex-wrap items-center gap-3">
          <a
            href="https://github.com/bala-builder/friday-movie-agent"
            target="_blank"
            rel="noopener noreferrer"
            className="inline-flex items-center rounded-full bg-red-600 px-6 py-3 text-sm font-medium text-white transition-opacity hover:opacity-90"
          >
            View the project on GitHub
            <span className="ml-2">↗</span>
          </a>
        </div>
        <p className="mt-3 text-xs text-black/40 dark:text-white/40">
          Runs on a schedule via GitHub Actions — no app to install.
        </p>
      </section>

      <section className="pb-20 sm:pb-28">
        <h2 className="text-sm font-medium uppercase tracking-wider text-black/40 dark:text-white/40">
          What it does
        </h2>
        <div className="mt-6 grid gap-4 sm:grid-cols-2">
          {features.map((feature) => (
            <div
              key={feature.title}
              className="rounded-2xl border border-black/[.08] p-6 dark:border-white/[.1]"
            >
              <h3 className="text-base font-semibold tracking-tight">
                {feature.title}
              </h3>
              <p className="mt-2 text-sm leading-relaxed text-black/60 dark:text-white/60">
                {feature.description}
              </p>
            </div>
          ))}
        </div>
      </section>

      <section className="pb-24 sm:pb-32">
        <h2 className="text-sm font-medium uppercase tracking-wider text-black/40 dark:text-white/40">
          How it works
        </h2>
        <div className="mt-6 grid gap-4 sm:grid-cols-2">
          {steps.map((s) => (
            <div key={s.step} className="flex gap-4">
              <span className="text-sm font-semibold text-red-600">
                {s.step}
              </span>
              <div>
                <h3 className="text-base font-semibold tracking-tight">
                  {s.title}
                </h3>
                <p className="mt-1 text-sm leading-relaxed text-black/60 dark:text-white/60">
                  {s.description}
                </p>
              </div>
            </div>
          ))}
        </div>
      </section>
    </div>
  );
}
