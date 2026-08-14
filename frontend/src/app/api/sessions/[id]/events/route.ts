/**
 * Tektos-Ultima v1 — API Route: Session Events
 *
 * GET /api/sessions/[id]/events — Query events for session
 */

import { NextResponse } from "next/server";

const BACKEND_URL = process.env.BACKEND_URL || "http://localhost:8020";

export async function GET(
  request: Request,
  { params }: { params: Promise<{ id: string }> }
) {
  const { id } = await params;
  const { searchParams } = new URL(request.url);
  const sinceSeq = searchParams.get("since_seq");
  const limit = searchParams.get("limit");

  try {
    const url = new URL(`${BACKEND_URL}/api/sessions/${id}/events`);
    if (sinceSeq) url.searchParams.set("since_seq", sinceSeq);
    if (limit) url.searchParams.set("limit", limit);

    const response = await fetch(url.toString(), {
      cache: "no-store",
    });

    if (!response.ok) {
      return NextResponse.json(
        { error: "Failed to fetch events" },
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
