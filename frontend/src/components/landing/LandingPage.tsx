/**
 * Tektos-Ultima v1 — Landing Page
 *
 * A mind-blowing animated welcome screen inspired by the attached image:
 * warm, meditative, earthy tones with radial glow, floating particles,
 * and TTS integration.
 *
 * Style: Dark olive/gold palette, organic painterly aesthetic,
 * breathing animations, golden dust motes, radial pulse.
 */

"use client";

import React, { useState, useEffect, useRef, useCallback } from "react";

/* ─── Particle type ─────────────────────────────────────────── */

interface Particle {
  id: number;
  x: number;
  y: number;
  size: number;
  opacity: number;
  speed: number;
  drift: number;
  phase: number;
}

/* ─── Canvas-based particle system ──────────────────────────── */

function ParticleCanvas({ active }: { active: boolean }) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const particlesRef = useRef<Particle[]>([]);
  const animFrameRef = useRef<number>(0);

  const initParticles = useCallback((w: number, h: number) => {
    const count = 60;
    const particles: Particle[] = [];
    for (let i = 0; i < count; i++) {
      particles.push({
        id: i,
        x: Math.random() * w,
        y: Math.random() * h,
        size: Math.random() * 2.5 + 0.5,
        opacity: Math.random() * 0.6 + 0.1,
        speed: Math.random() * 0.3 + 0.05,
        drift: (Math.random() - 0.5) * 0.2,
        phase: Math.random() * Math.PI * 2,
      });
    }
    return particles;
  }, []);

  useEffect(() => {
    if (!active) return;
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    const resize = () => {
      canvas.width = window.innerWidth;
      canvas.height = window.innerHeight;
      particlesRef.current = initParticles(canvas.width, canvas.height);
    };
    resize();
    window.addEventListener("resize", resize);

    const draw = () => {
      ctx.clearRect(0, 0, canvas.width, canvas.height);
      const particles = particlesRef.current;
      const time = Date.now() * 0.001;

      for (const p of particles) {
        // Gentle upward drift + sine wave
        p.y -= p.speed;
        p.x += p.drift + Math.sin(time + p.phase) * 0.15;

        // Wrap around
        if (p.y < -10) {
          p.y = canvas.height + 10;
          p.x = Math.random() * canvas.width;
        }
        if (p.x < -10) p.x = canvas.width + 10;
        if (p.x > canvas.width + 10) p.x = -10;

        // Twinkle
        const twinkle = 0.5 + 0.5 * Math.sin(time * 1.5 + p.phase);
        const alpha = p.opacity * twinkle;

        // Golden color
        ctx.beginPath();
        ctx.arc(p.x, p.y, p.size, 0, Math.PI * 2);
        ctx.fillStyle = `rgba(204, 199, 99, ${alpha})`;
        ctx.fill();

        // Glow
        ctx.beginPath();
        ctx.arc(p.x, p.y, p.size * 3, 0, Math.PI * 2);
        ctx.fillStyle = `rgba(204, 199, 99, ${alpha * 0.15})`;
        ctx.fill();
      }

      animFrameRef.current = requestAnimationFrame(draw);
    };

    draw();

    return () => {
      window.removeEventListener("resize", resize);
      cancelAnimationFrame(animFrameRef.current);
    };
  }, [active, initParticles]);

  if (!active) return null;

  return (
    <canvas
      ref={canvasRef}
      className="pointer-events-none fixed inset-0 z-20"
      style={{ mixBlendMode: "screen" }}
    />
  );
}

/* ─── Radial glow overlay ───────────────────────────────────── */

function RadialGlow() {
  return (
    <div
      className="pointer-events-none fixed inset-0 z-10"
      style={{
        background: `
          radial-gradient(ellipse 60% 50% at 50% 45%,
            rgba(157, 151, 61, 0.12) 0%,
            rgba(100, 112, 67, 0.06) 30%,
            transparent 70%
          ),
          radial-gradient(ellipse 80% 70% at 50% 50%,
            rgba(204, 199, 99, 0.04) 0%,
            transparent 60%
          )
        `,
        animation: "breathe 6s ease-in-out infinite",
      }}
    />
  );
}

/* ─── Typing animation ──────────────────────────────────────── */

function TypingText({ text, speed = 60 }: { text: string; speed?: number }) {
  const [displayed, setDisplayed] = useState("");
  const [done, setDone] = useState(false);

  useEffect(() => {
    let i = 0;
    const interval = setInterval(() => {
      if (i < text.length) {
        setDisplayed(text.slice(0, i + 1));
        i++;
      } else {
        setDone(true);
        clearInterval(interval);
      }
    }, speed);
    return () => clearInterval(interval);
  }, [text, speed]);

  return (
    <span>
      {displayed}
      {!done && <span className="animate-pulse">▌</span>}
    </span>
  );
}

/* ─── TTS Welcome ───────────────────────────────────────────── */

function TTSWelcome({ backendUrl }: { backendUrl: string }) {
  const spokenRef = useRef(false);

  useEffect(() => {
    if (spokenRef.current) return;
    spokenRef.current = true;

    const text =
      "Welcome to Tektos. Your autonomous coding agent is ready.";

    fetch(`${backendUrl}:8020/api/voice/tts`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ text }),
    })
      .then((r) => {
        if (!r.ok) throw new Error(`TTS failed: ${r.status}`);
        return r.blob();
      })
      .then((blob) => {
        const url = URL.createObjectURL(blob);
        const audio = new Audio(url);
        audio.onended = () => URL.revokeObjectURL(url);
        audio.play().catch(() => {
          // Autoplay blocked — user can click to enter
        });
      })
      .catch(() => {
        // TTS unavailable — no error shown
      });
  }, [backendUrl]);

  return null;
}

/* ─── Main Landing Page ─────────────────────────────────────── */

interface LandingPageProps {
  onEnter: () => void;
  backendUrl?: string;
}

export function LandingPage({ onEnter, backendUrl = "http://localhost:8020" }: LandingPageProps) {
  const [entered, setEntered] = useState(false);
  const [showContent, setShowContent] = useState(false);

  useEffect(() => {
    // Staggered entrance
    const t1 = setTimeout(() => setShowContent(true), 400);
    return () => clearTimeout(t1);
  }, []);

  const handleEnter = () => {
    setEntered(true);
    setTimeout(onEnter, 600);
  };

  return (
    <div
      className="fixed inset-0 z-50 flex flex-col items-center justify-center overflow-hidden"
      style={{
        background: "linear-gradient(180deg, #0a0c08 0%, #141810 40%, #1a1e14 100%)",
        transition: "opacity 0.6s ease, transform 0.6s ease",
        opacity: entered ? 0 : 1,
        transform: entered ? "scale(1.05)" : "scale(1)",
        pointerEvents: entered ? "none" : "auto",
      }}
    >
      {/* Background image with breathing scale */}
      <div
        className="absolute inset-0"
        style={{
          backgroundImage: "url(/tektos-landing.jpg)",
          backgroundSize: "cover",
          backgroundPosition: "center",
          backgroundRepeat: "no-repeat",
          animation: "breathe 8s ease-in-out infinite",
          transformOrigin: "center center",
          filter: "brightness(0.35) saturate(1.2)",
        }}
      />

      {/* Dark overlay for readability */}
      <div
        className="absolute inset-0"
        style={{
          background: "radial-gradient(ellipse 70% 60% at 50% 45%, transparent 0%, rgba(10,12,8,0.5) 100%)",
        }}
      />

      {/* Radial glow */}
      <RadialGlow />

      {/* Particles */}
      <ParticleCanvas active={!entered} />

      {/* Content */}
      <div
        className="relative z-30 flex flex-col items-center gap-8 px-6"
        style={{
          opacity: showContent ? 1 : 0,
          transform: showContent ? "translateY(0)" : "translateY(20px)",
          transition: "opacity 1s ease 0.3s, transform 1s ease 0.3s",
        }}
      >
        {/* Wordmark */}
        <div className="flex flex-col items-center gap-4">
          <h1
            className="text-7xl md:text-8xl font-bold tracking-widest"
            style={{
              fontFamily: "'Collapse', sans-serif",
              background: "linear-gradient(180deg, #d4c878 0%, #9d973d 40%, #647043 100%)",
              WebkitBackgroundClip: "text",
              WebkitTextFillColor: "transparent",
              filter: "drop-shadow(0 0 30px rgba(204, 199, 99, 0.2))",
            }}
          >
            TEKTOS
          </h1>

          {/* Decorative line */}
          <div
            className="h-px w-48"
            style={{
              background: "linear-gradient(90deg, transparent, rgba(204,199,99,0.4), transparent)",
            }}
          />

          {/* Subtitle with typing animation */}
          <p
            className="text-lg md:text-xl tracking-[0.3em] uppercase"
            style={{
              color: "rgba(139, 159, 125, 0.8)",
              fontFamily: "'Inter', system-ui, sans-serif",
              fontWeight: 300,
              letterSpacing: "0.35em",
            }}
          >
            <TypingText text="Autonomous Coding Agent" speed={70} />
          </p>
        </div>

        {/* Enter button */}
        <button
          onClick={handleEnter}
          className="group relative mt-4 px-10 py-3 rounded-full text-sm tracking-[0.25em] uppercase font-medium transition-all duration-300 hover:scale-105 focus:outline-none focus:ring-2 focus:ring-[#d4c878]/50"
          style={{
            background: "linear-gradient(135deg, rgba(100,112,67,0.2) 0%, rgba(157,151,61,0.15) 100%)",
            border: "1px solid rgba(204,199,99,0.2)",
            color: "rgba(212, 200, 120, 0.9)",
            boxShadow: "0 0 30px rgba(204,199,99,0.05), inset 0 0 30px rgba(204,199,99,0.03)",
          }}
          onMouseEnter={(e) => {
            e.currentTarget.style.boxShadow =
              "0 0 40px rgba(204,199,99,0.15), inset 0 0 40px rgba(204,199,99,0.08)";
            e.currentTarget.style.borderColor = "rgba(204,199,99,0.4)";
          }}
          onMouseLeave={(e) => {
            e.currentTarget.style.boxShadow =
              "0 0 30px rgba(204,199,99,0.05), inset 0 0 30px rgba(204,199,99,0.03)";
            e.currentTarget.style.borderColor = "rgba(204,199,99,0.2)";
          }}
        >
          <span className="relative z-10">Enter</span>
          {/* Hover glow */}
          <div
            className="absolute inset-0 rounded-full opacity-0 group-hover:opacity-100 transition-opacity duration-500"
            style={{
              background: "radial-gradient(circle at center, rgba(204,199,99,0.1) 0%, transparent 70%)",
            }}
          />
        </button>

        {/* Bottom hint */}
        <p
          className="text-xs tracking-widest uppercase"
          style={{ color: "rgba(139, 159, 125, 0.35)" }}
        >
          Press Enter or click to begin
        </p>
      </div>

      {/* TTS */}
      <TTSWelcome backendUrl={backendUrl} />

      {/* Global key listener */}
      <KeyboardHandler onEnter={handleEnter} />
    </div>
  );
}

/* ─── Keyboard handler ──────────────────────────────────────── */

function KeyboardHandler({ onEnter }: { onEnter: () => void }) {
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if (e.key === "Enter" || e.key === " ") {
        e.preventDefault();
        onEnter();
      }
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [onEnter]);

  return null;
}
