import Link from 'next/link';

type ButtonVariant = 'primary' | 'secondary' | 'outline';
type ButtonSize = 'md' | 'sm';

export function Container(props: { children: React.ReactNode }) {
  return <div className="mx-auto w-full max-w-6xl px-6">{props.children}</div>;
}

export function Button(
  props: React.ButtonHTMLAttributes<HTMLButtonElement> & {
    variant?: ButtonVariant;
    size?: ButtonSize;
  },
) {
  const variant = props.variant ?? 'primary';
  const size = props.size ?? 'md';

  const variantClass =
    variant === 'primary'
      ? 'bg-indigo-500 text-white hover:bg-indigo-400'
      : variant === 'secondary'
        ? 'bg-zinc-800 text-zinc-50 hover:bg-zinc-700'
        : 'border border-zinc-300/60 bg-zinc-100/60 text-zinc-800 hover:bg-zinc-200/70';

  const sizeClass = size === 'sm' ? 'px-3 py-1.5 text-xs' : 'px-4 py-2 text-sm';

  const className = `inline-flex items-center justify-center rounded-lg font-medium transition ${variantClass} ${sizeClass}`;

  return <button {...props} className={`${className} ${props.className ?? ''}`} />;
}

export function LinkButton(props: { href: string; children: React.ReactNode; variant?: 'primary' | 'secondary' }) {
  const variant = props.variant ?? 'primary';
  const className =
    variant === 'primary'
      ? 'inline-flex items-center rounded-lg bg-indigo-500 px-4 py-2 font-medium text-white hover:bg-indigo-400'
      : 'inline-flex items-center rounded-lg bg-zinc-800 px-4 py-2 font-medium text-zinc-50 hover:bg-zinc-700';
  return (
    <Link href={props.href} className={className}>
      {props.children}
    </Link>
  );
}
