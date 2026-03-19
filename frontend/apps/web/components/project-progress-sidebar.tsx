'use client';

import { Check, Circle } from 'lucide-react';
import { cn } from '../lib/utils';

type ProgressStep = {
  id: number;
  title: string;
  completed: boolean;
  active: boolean;
};

type ProjectProgressSidebarProps = {
  steps: ProgressStep[];
};

export function ProjectProgressSidebar({ steps }: ProjectProgressSidebarProps) {
  return (
    <div className="rounded-2xl border border-border bg-surfaceSoft p-6">
        <h3 className="text-sm font-semibold text-text mb-6">Прогресс проекта</h3>
        <div className="relative">
          {/* Вертикальная линия прогресса */}
          <div className="absolute left-4 top-0 bottom-0 w-0.5 bg-border">
            <div
              className="absolute top-0 left-0 w-full bg-accent transition-all duration-500 ease-out"
              style={{
                height: `${(steps.filter((s) => s.completed).length / steps.length) * 100}%`,
              }}
            />
          </div>

          {/* Шаги */}
          <div className="space-y-6">
            {steps.map((step, index) => (
              <div key={step.id} className="relative flex items-start gap-4">
                {/* Иконка шага */}
                <div
                  className={cn(
                    'relative z-10 flex h-8 w-8 shrink-0 items-center justify-center rounded-full border-2 transition-all',
                    step.completed
                      ? 'border-accent bg-accent'
                      : step.active
                      ? 'border-accent bg-accent/10'
                      : 'border-border bg-surface'
                  )}
                >
                  {step.completed ? (
                    <Check className="h-4 w-4 text-primary" />
                  ) : (
                    <Circle className={cn('h-4 w-4', step.active ? 'text-accent' : 'text-textMuted')} />
                  )}
                </div>

                {/* Текст шага */}
                <div className="flex-1 pt-1">
                  <div
                    className={cn(
                      'text-sm font-medium transition-colors',
                      step.completed || step.active ? 'text-text' : 'text-textMuted'
                    )}
                  >
                    {step.title}
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
    </div>
  );
}
