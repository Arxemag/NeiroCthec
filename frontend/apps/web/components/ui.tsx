// Экспорт новых компонентов дизайн-системы
export { Button, buttonVariants } from './ui/button';
export type { ButtonProps } from './ui/button';

export {
  Card,
  CardHeader,
  CardFooter,
  CardTitle,
  CardDescription,
  CardContent,
} from './ui/card';

export { Container } from './ui/container';
export type { ContainerProps } from './ui/container';

// Утилиты для обратной совместимости
import { Button as NewButton } from './ui/button';
import Link from 'next/link';

/**
 * Компонент для создания ссылок-кнопок
 */
export function LinkButton(props: { href: string; children: React.ReactNode; variant?: 'primary' | 'secondary' }) {
  return (
    <Link href={props.href}>
      <NewButton variant={props.variant === 'secondary' ? 'secondary' : 'primary'} asChild>
        {props.children}
      </NewButton>
    </Link>
  );
}
