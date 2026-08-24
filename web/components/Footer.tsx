export default function Footer() {
  const year = new Date().getFullYear();
  return (
    <footer className="border-t border-black/[.08] dark:border-white/[.1]">
      <div className="mx-auto flex max-w-3xl flex-col items-center justify-between gap-3 px-6 py-8 text-sm text-black/50 sm:flex-row dark:text-white/50">
        <p>© {year} Balaconnect. Built by Bala.</p>
        <a
          href="https://github.com/bala-builder/friday-movie-agent"
          target="_blank"
          rel="noopener noreferrer"
          className="transition-colors hover:text-black dark:hover:text-white"
        >
          View on GitHub
        </a>
      </div>
    </footer>
  );
}
