'use client';

import React, { useCallback, useEffect, useRef } from 'react';

type WavyBackgroundProps = {
  children?: React.ReactNode;
  className?: string;
  containerClassName?: string;
  colors?: string[];
  waveWidth?: number;
  backgroundFill?: string;
  blur?: number;
  speed?: 'slow' | 'fast';
  waveOpacity?: number;
};

export function WavyBackground({
  children,
  className,
  containerClassName,
  colors = ['#38bdf8', '#818cf8', '#c084fc', '#e879f9', '#22d3ee'],
  waveWidth = 50,
  backgroundFill = 'black',
  blur = 10,
  speed = 'fast',
  waveOpacity = 0.5,
}: WavyBackgroundProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const speedVal = speed === 'fast' ? 0.002 : 0.001;
  const offsetRef = useRef(0);

  const draw = useCallback(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;

    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    const w = canvas.width;
    const h = canvas.height;
    if (w <= 0 || h <= 0) return;

    ctx.clearRect(0, 0, w, h);
    ctx.fillStyle = backgroundFill;
    ctx.fillRect(0, 0, w, h);

    const now = offsetRef.current;
    const numWaves = colors.length;

    for (let i = 0; i < numWaves; i++) {
      ctx.beginPath();
      ctx.moveTo(0, h);

      for (let x = 0; x <= w + 10; x += 5) {
        const phase = (i / numWaves) * Math.PI * 2 + (x / w) * Math.PI * 2;
        const y =
          h -
          (h * 0.4) *
            (0.5 +
              0.5 *
                Math.sin(phase + now * 2) *
                Math.sin((x / w) * Math.PI * 4 + now));
        ctx.lineTo(x, y);
      }

      ctx.lineTo(w + 10, h);
      ctx.closePath();
      ctx.fillStyle = colors[i]!;
      ctx.globalAlpha = waveOpacity;
      ctx.fill();
      ctx.globalAlpha = 1;
    }

    offsetRef.current += speedVal;
  }, [colors, backgroundFill, waveOpacity, speedVal]);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;

    const resize = () => {
      const parent = canvas.parentElement;
      if (!parent) return;
      const rect = parent.getBoundingClientRect();
      let w = Math.round(rect.width);
      let h = Math.round(rect.height);
      if (w <= 0 || h <= 0) {
        w = typeof window !== 'undefined' ? window.innerWidth : 800;
        h = typeof window !== 'undefined' ? window.innerHeight : 600;
      }
      if (w <= 0 || h <= 0) return;
      canvas.width = w;
      canvas.height = h;
      draw();
    };

    requestAnimationFrame(resize);
    window.addEventListener('resize', resize);
    const parent = canvas.parentElement;
    const ro = parent ? new ResizeObserver(resize) : null;
    if (ro && parent) ro.observe(parent);

    let raf: number;
    const loop = () => {
      draw();
      raf = requestAnimationFrame(loop);
    };
    raf = requestAnimationFrame(loop);

    return () => {
      window.removeEventListener('resize', resize);
      ro?.disconnect();
      cancelAnimationFrame(raf);
    };
  }, [draw]);

  return (
    <div
      className={`relative overflow-hidden ${containerClassName ?? ''}`}
    >
      <canvas
        ref={canvasRef}
        className="absolute inset-0 h-full w-full"
        style={{ filter: `blur(${blur}px)` }}
        aria-hidden
      />
      <div className={`relative z-10 ${className ?? ''}`}>{children}</div>
    </div>
  );
}
