/**
 * Явный прокси /app-api/* → Core.
 * Next.js rewrites иногда не пересылают тело POST — этот route гарантирует передачу body.
 * GET/POST/PUT/DELETE и заголовки (X-User-Id и др.) пробрасываются в Core.
 */
import { NextRequest, NextResponse } from 'next/server';

export const dynamic = 'force-dynamic';
export const runtime = 'nodejs';

const CORE_TARGET =
  process.env.APP_API_PROXY_TARGET || process.env.CORE_API_URL || 'http://localhost:8000';

async function proxy(request: NextRequest, pathSegments: string[]) {
  const target = CORE_TARGET.replace(/\/$/, '');
  const path = pathSegments.length ? pathSegments.join('/') : '';
  const search = request.nextUrl.search;
  const url = `${target}/${path}${search}`;

  const headers = new Headers();
  request.headers.forEach((value, key) => {
    if (
      key.toLowerCase() === 'host' ||
      key.toLowerCase() === 'connection' ||
      key.toLowerCase() === 'content-length'
    )
      return;
    headers.set(key, value);
  });

  const method = request.method;
  const hasBody = method !== 'GET' && method !== 'HEAD' && request.body != null;
  // process-book-stage4 и превью могут долго выполняться на Core — таймаут 5 мин
  const timeoutMs = 300_000;

  const res = await fetch(url, {
    method,
    headers,
    ...(hasBody ? { body: request.body, duplex: 'half' as const } : {}),
    signal: AbortSignal.timeout(timeoutMs),
  } as RequestInit);

  const buf = await res.arrayBuffer();
  const outHeaders = new Headers();
  res.headers.forEach((value, key) => {
    // content-encoding может ломать ответы при повторной упаковке
    if (key.toLowerCase() === 'content-encoding') return;
    outHeaders.set(key, value);
  });
  return new NextResponse(Buffer.from(buf), {
    status: res.status,
    headers: outHeaders,
  });
}

export async function GET(
  request: NextRequest,
  { params }: { params: Promise<{ path?: string[] }> }
) {
  const { path = [] } = await params;
  try {
    return proxy(request, path);
  } catch (e) {
    const msg = e instanceof Error ? e.message : String(e);
    return NextResponse.json(
      {
        detail: `Core API недоступен (${CORE_TARGET}). Ошибка: ${msg}. Проверьте APP_API_PROXY_TARGET.`,
      },
      { status: 502 }
    );
  }
}

export async function POST(
  request: NextRequest,
  { params }: { params: Promise<{ path?: string[] }> }
) {
  const { path = [] } = await params;
  try {
    return proxy(request, path);
  } catch (e) {
    const msg = e instanceof Error ? e.message : String(e);
    return NextResponse.json(
      {
        detail: `Core API недоступен (${CORE_TARGET}). Ошибка: ${msg}. Проверьте APP_API_PROXY_TARGET.`,
      },
      { status: 502 }
    );
  }
}

export async function PUT(
  request: NextRequest,
  { params }: { params: Promise<{ path?: string[] }> }
) {
  const { path = [] } = await params;
  try {
    return proxy(request, path);
  } catch (e) {
    const msg = e instanceof Error ? e.message : String(e);
    return NextResponse.json(
      { detail: `Core API недоступен. Ошибка: ${msg}.` },
      { status: 502 }
    );
  }
}

export async function DELETE(
  request: NextRequest,
  { params }: { params: Promise<{ path?: string[] }> }
) {
  const { path = [] } = await params;
  try {
    return proxy(request, path);
  } catch (e) {
    const msg = e instanceof Error ? e.message : String(e);
    return NextResponse.json(
      { detail: `Core API недоступен. Ошибка: ${msg}.` },
      { status: 502 }
    );
  }
}
