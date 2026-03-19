import { NextResponse } from 'next/server';
import type { NextRequest } from 'next/server';
import { AUTH_COOKIE_NAME } from './lib/auth';

/**
 * Личный кабинет (/app/*) только для авторизованных пользователей.
 * При отсутствии cookie редирект на страницу входа с сохранением целевого URL.
 */
export function middleware(request: NextRequest) {
  const { pathname } = request.nextUrl;
  if (!pathname.startsWith('/app')) {
    return NextResponse.next();
  }
  const signedIn = request.cookies.get(AUTH_COOKIE_NAME)?.value === '1';
  if (signedIn) {
    return NextResponse.next();
  }
  const loginUrl = new URL('/auth/login', request.url);
  loginUrl.searchParams.set('next', pathname);
  return NextResponse.redirect(loginUrl);
}

export const config = {
  matcher: ['/app', '/app/:path*'],
};
