export function LoadingState({ label = "Загрузка" }: { label?: string }) {
  return <p className="text-sm text-stone-600">{label}…</p>;
}

export function EmptyState({ title, body }: { title: string; body: string }) {
  return (
    <div className="rounded-3xl border border-dashed border-line bg-white/60 p-8">
      <h2 className="font-serif text-2xl">{title}</h2>
      <p className="mt-2 max-w-xl text-sm leading-6 text-stone-700">{body}</p>
    </div>
  );
}

export function ErrorState({ message }: { message: string }) {
  return (
    <div role="alert" className="rounded-2xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-900">
      {message}
    </div>
  );
}
