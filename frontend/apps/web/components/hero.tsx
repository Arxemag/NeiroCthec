'use client';

import { Container } from './ui/container';
import { Button } from './ui/button';
import { Card } from './ui/card';

export interface HeroProps {
  title: string;
  description: string;
  primaryAction?: {
    label: string;
    href: string;
  };
  secondaryAction?: {
    label: string;
    href: string;
  };
}

export function Hero({ title, description, primaryAction, secondaryAction }: HeroProps) {
  return (
    <section className="relative py-20 md:py-32 lg:py-40 overflow-hidden">
      {/* Декоративный фон */}
      <div className="absolute inset-0 bg-gradient-to-b from-surface via-surfaceSoft to-surface opacity-50" />
      
      <Container className="relative z-10">
        <div className="text-center max-w-4xl mx-auto">
          <h1 className="font-heading font-bold text-4xl md:text-5xl lg:text-6xl mb-6 text-balance">
            {title}
          </h1>
          <p className="text-lg md:text-xl text-textSecondary mb-10 text-balance max-w-2xl mx-auto">
            {description}
          </p>
          
          {(primaryAction || secondaryAction) && (
            <div className="flex flex-col sm:flex-row gap-4 justify-center items-center">
              {primaryAction && (
                <Button asChild size="lg">
                  <a href={primaryAction.href}>{primaryAction.label}</a>
                </Button>
              )}
              {secondaryAction && (
                <Button variant="secondary" asChild size="lg">
                  <a href={secondaryAction.href}>{secondaryAction.label}</a>
                </Button>
              )}
            </div>
          )}
        </div>
      </Container>
    </section>
  );
}
