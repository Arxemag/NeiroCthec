/**
 * Прокси загрузки книги в Core API.
 * Next.js rewrites в dev не всегда пересылают тело POST — используем явный прокси.
 * POST /app/proxy-core/books/upload → Core POST /api/books/upload
 */
import { NextRequest, NextResponse } from 'next/server';

export const dynamic = 'force-dynamic';
export const runtime = 'nodejs';

const CORE_TARGET =
  process.env.APP_API_PROXY_TARGET || process.env.CORE_API_URL || 'http://localhost:8000';

export async function POST(request: NextRequest) {
  const target = CORE_TARGET.replace(/\/$/, '');
  const url = `${target}/api/books/upload`;

  const headers = new Headers();
  const xUserId = request.headers.get('x-user-id');
  const xProjectId = request.headers.get('x-project-id');
  const contentType = request.headers.get('content-type');
  if (xUserId) headers.set('X-User-Id', xUserId);
  if (xProjectId) headers.set('X-Project-Id', xProjectId);
  if (contentType) headers.set('Content-Type', contentType);

  try {
    const res = await fetch(url, {
      method: 'POST',
      headers,
      body: request.body,
      duplex: 'half',
    } as RequestInit);

    const resContentType = res.headers.get('content-type') || 'application/json';
    const text = await res.text();

    return new NextResponse(text, {
      status: res.status,
      headers: { 'Content-Type': resContentType },
    });
  } catch (e) {
    const msg = e instanceof Error ? e.message : String(e);
    return NextResponse.json(
      {
        detail: `Core API недоступен (${target}). Ошибка: ${msg}. Проверьте, что сервис core запущен и APP_API_PROXY_TARGET задан.`,
      },
      { status: 502 }
    );
  }
}
