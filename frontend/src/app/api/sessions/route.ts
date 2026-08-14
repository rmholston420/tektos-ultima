/**
 * Tektos-Ultima v1 — API Route: Sessions Collection
 *
 * GET /api/sessions — List sessions
 * POST /api/sessions — Create session
 */

import { NextResponse } from "next/server";

const BACKEND_URL = process.env.BACKEND_URL || "http://localhost:8020";

// GET /api/sessions
export async function GET(request: Request) {
  const { searchParams } = new URL(request.url);
  const archived = searchParams.get("archived");
  const limit = searchParams.get("limit");

  try {
    const params = new URLSearchParams();
    if (archived !== null) params.set("archived", archived);
    if (limit) params.set("limit", limit);

    const response = await fetch(`${BACKEND_URL}/api/sessions?${params}`, {
      cache: "no-store",
    });

    if (!response.ok) {
      return NextResponse.json(
        { error: "Failed to fetch sessions" },
        { status: response.status }
      );
    }

    const data = await response.json();
    return NextResponse.json(data);
  } catch (error) {
    return NextResponse.json(
      { error: "Backend unreachable", details: String(error) },
      { status: 503 }
    );
  }
}

// POST /api/sessions
export async function POST(request: Request) {
  try {
    const body = await request.json();

    const response = await fetch(`${BACKEND_URL}/api/sessions`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });

    if (!response.ok) {
      const error = await response.text();
      return NextResponse.json(
        { error: "Failed to create session", details: error },
        { status: response.status }
      );
    }

    const data = await response.json();
    return NextResponse.json(data);
  } catch (error) {
    return NextResponse.json(
      { error: "Backend unreachable", details: String(error) },
      { status: 503 }
    );
  }
}
