import Link from "next/link";

export default function Header() {
  return (
    <header className="sticky top-0 z-50 border-b border-black/[.08] bg-white/80 backdrop-blur-sm dark:border-white/[.1] dark:bg-black/60">
      <div className="mx-auto flex max-w-3xl items-center justify-between px-6 py-4">
        <a
          href="https://balaconnect.com"
          className="text-sm text-black/50 transition-colors hover:text-black dark:text-white/50 dark:hover:text-white"
        >
          ← balaconnect
        </a>
        <Link href="/" className="text-base font-semibold tracking-tight">
          🎬 Friday Movie Agent
        </Link>
      </div>
    </header>
  );
}
