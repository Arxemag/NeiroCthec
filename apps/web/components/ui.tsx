import Link from 'next/link';

export function Container(props: { children: React.ReactNode }) {
  return <div className="mx-auto w-full max-w-6xl px-6">{props.children}</div>;
}

export function Button(props: React.ButtonHTMLAttributes<HTMLButtonElement> & { variant?: 'primary' | 'secondary' }) {
  const variant = props.variant ?? 'primary';
  const className =
    variant === 'primary'
      ? 'rounded-lg bg-indigo-500 px-4 py-2 font-medium text-white hover:bg-indigo-400'
      : 'rounded-lg bg-zinc-800 px-4 py-2 font-medium text-zinc-50 hover:bg-zinc-700';
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

