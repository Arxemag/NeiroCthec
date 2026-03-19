import type { Request, Response, NextFunction } from 'express';

type Options = {
  windowMs: number;
  max: number;
  key?: (req: Request) => string;
};

export function simpleRateLimit(opts: Options) {
  const buckets = new Map<string, { resetAt: number; count: number }>();
  const keyFn = opts.key ?? ((req) => req.ip || 'unknown');

  return (req: Request, res: Response, next: NextFunction) => {
    const now = Date.now();
    const key = keyFn(req);
    const cur = buckets.get(key);

    if (!cur || cur.resetAt <= now) {
      buckets.set(key, { resetAt: now + opts.windowMs, count: 1 });
      res.setHeader('X-RateLimit-Limit', String(opts.max));
      res.setHeader('X-RateLimit-Remaining', String(opts.max - 1));
      res.setHeader('X-RateLimit-Reset', String(Math.floor((now + opts.windowMs) / 1000)));
      return next();
    }

    if (cur.count >= opts.max) {
      res.setHeader('Retry-After', String(Math.ceil((cur.resetAt - now) / 1000)));
      return res.status(429).json({ message: 'Too many requests' });
    }

    cur.count += 1;
    res.setHeader('X-RateLimit-Limit', String(opts.max));
    res.setHeader('X-RateLimit-Remaining', String(Math.max(0, opts.max - cur.count)));
    res.setHeader('X-RateLimit-Reset', String(Math.floor(cur.resetAt / 1000)));
    return next();
  };
}

