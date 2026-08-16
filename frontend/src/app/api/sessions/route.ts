/**
 * Proxy all API requests to the Tektos backend (App Router)
 * 
 * Forwards /api/sessions/* to http://localhost:8020/api/sessions/*
 * Handles GET, POST, PATCH, DELETE methods.
 */

import { NextResponse } from 'next/server';

const BACKEND_URL = 'http://localhost:8020';

/**
 * Build the backend path from the Next.js route path.
 * 
 * Examples:
 *   /api/sessions           -> /api/sessions
 *   /api/sessions/abc       -> /api/sessions/abc
 *   /api/sessions/abc/events -> /api/sessions/abc/events
 */
function buildBackendPath(pathname: string, searchParams?: URLSearchParams): string {
  // Strip the /api prefix to get the actual API path
  const stripped = pathname.startsWith('/api') ? pathname.slice(4) : pathname;
  const backendPath = '/api' + stripped;
  const qs = searchParams && searchParams.toString() ? '?' + searchParams.toString() : '';
  return backendPath + qs;
}

export async function GET(request: Request) {
  const url = new URL(request.url);
  const backendPath = buildBackendPath(url.pathname, url.searchParams);
  
  try {
    const response = await fetch(BACKEND_URL + backendPath, {
      method: 'GET',
      headers: { 'Content-Type': 'application/json' },
    });
    const data = await response.json();
    return NextResponse.json(data, { status: response.status });
  } catch (error) {
    console.error('GET proxy error:', error);
    return NextResponse.json({ error: 'Backend proxy failed' }, { status: 500 });
  }
}

export async function POST(request: Request) {
  const url = new URL(request.url);
  const backendPath = buildBackendPath(url.pathname);
  const body = await request.json();
  
  try {
    const response = await fetch(BACKEND_URL + backendPath, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    });
    const data = await response.json();
    return NextResponse.json(data, { status: response.status });
  } catch (error) {
    console.error('POST proxy error:', error);
    return NextResponse.json({ error: 'Backend proxy failed' }, { status: 500 });
  }
}

export async function PATCH(request: Request) {
  const url = new URL(request.url);
  const backendPath = buildBackendPath(url.pathname);
  const body = await request.json();
  
  try {
    const response = await fetch(BACKEND_URL + backendPath, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    });
    const data = await response.json();
    return NextResponse.json(data, { status: response.status });
  } catch (error) {
    console.error('PATCH proxy error:', error);
    return NextResponse.json({ error: 'Backend proxy failed' }, { status: 500 });
  }
}

export async function DELETE(request: Request) {
  const url = new URL(request.url);
  const backendPath = buildBackendPath(url.pathname);
  
  try {
    const response = await fetch(BACKEND_URL + backendPath, {
      method: 'DELETE',
    });
    const data = await response.json();
    return NextResponse.json(data, { status: response.status });
  } catch (error) {
    console.error('DELETE proxy error:', error);
    return NextResponse.json({ error: 'Backend proxy failed' }, { status: 500 });
  }
}
