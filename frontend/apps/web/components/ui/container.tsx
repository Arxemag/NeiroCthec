import * as React from 'react';
import { cn } from '@/lib/utils';

export interface ContainerProps extends React.HTMLAttributes<HTMLDivElement> {
  /**
   * Максимальная ширина контейнера
   * @default 'default' - 1200px
   */
  maxWidth?: 'sm' | 'default' | 'lg' | 'xl' | 'full';
}

const maxWidthClasses = {
  sm: 'max-w-[800px]',
  default: 'max-w-[1200px]',
  lg: 'max-w-[1400px]',
  xl: 'max-w-[1600px]',
  full: 'max-w-full',
};

const Container = React.forwardRef<HTMLDivElement, ContainerProps>(
  ({ className, maxWidth = 'default', ...props }, ref) => {
    return (
      <div
        ref={ref}
        className={cn(
          'mx-auto px-4 sm:px-6 lg:px-8',
          maxWidthClasses[maxWidth],
          className
        )}
        {...props}
      />
    );
  }
);
Container.displayName = 'Container';

export { Container };
