/**
 * Tektos-Ultima v1 — API Route: Session Archive
 *
 * POST /api/sessions/[id]/archive — Archive session
 */

import { NextResponse } from "next/server";

const BACKEND_URL = process.env.BACKEND_URL || "http://localhost:8020";

export async function POST(
  request: Request,
  { params }: { params: Promise<{ id: string }> }
) {
  const { id } = await params;

  try {
    const response = await fetch(`${BACKEND_URL}/api/sessions/${id}/archive`, {
      method: "POST",
    });

    if (!response.ok) {
      return NextResponse.json(
        { error: "Failed to archive session" },
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
