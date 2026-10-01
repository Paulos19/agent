"""
Design System, Motion Principles and 3D Templates for the DevOps & Frontend Assistant.
Inspired by /frontend-design, /impeccable, /motion-design, GSAP and Three.js references.
"""

THREE_HERO_SCENE_TEMPLATE = '''"use client";

import React, { useEffect, useRef } from "react";
import * as THREE from "three";

interface ThreeHeroSceneProps {
  variant?: "glass-orb" | "cyber-mesh" | "particles";
  className?: string;
}

export default function ThreeHeroScene({ variant = "glass-orb", className = "" }: ThreeHeroSceneProps) {
  const mountRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const mount = mountRef.current;
    if (!mount) return;

    const width = mount.clientWidth || window.innerWidth;
    const height = mount.clientHeight || 500;

    // 1. Scene, Camera, Renderer
    const scene = new THREE.Scene();
    const camera = new THREE.PerspectiveCamera(45, width / height, 0.1, 1000);
    camera.position.z = 6;

    const renderer = new THREE.WebGLRenderer({ alpha: true, antialias: true, powerPreference: "high-performance" });
    renderer.setSize(width, height);
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    mount.appendChild(renderer.domElement);

    // 2. Lights
    const ambientLight = new THREE.AmbientLight(0xffffff, 0.8);
    scene.add(ambientLight);

    const pointLight1 = new THREE.PointLight(0xa855f7, 2.5, 50); // Lilac / Violet
    pointLight1.position.set(5, 5, 5);
    scene.add(pointLight1);

    const pointLight2 = new THREE.PointLight(0x06b6d4, 2.0, 50); // Cyan
    pointLight2.position.set(-5, -5, 2);
    scene.add(pointLight2);

    // 3. Meshes
    const group = new THREE.Group();
    scene.add(group);

    // Main central geometry: Icosahedron / Glass Sphere
    const mainGeometry = new THREE.IcosahedronGeometry(1.6, 3);
    const mainMaterial = new THREE.MeshPhysicalMaterial({
      roughness: 0.1,
      transmission: 0.9,
      thickness: 1.2,
      ior: 1.5,
      reflectivity: 0.5,
      clearcoat: 1.0,
      clearcoatRoughness: 0.1,
      color: 0xffffff,
      wireframe: false,
    });
    const mainMesh = new THREE.Mesh(mainGeometry, mainMaterial);
    group.add(mainMesh);

    // Outer wireframe shell
    const outerGeometry = new THREE.IcosahedronGeometry(2.1, 1);
    const outerMaterial = new THREE.MeshBasicMaterial({
      color: 0x7c3aed,
      wireframe: true,
      transparent: true,
      opacity: 0.25,
    });
    const outerMesh = new THREE.Mesh(outerGeometry, outerMaterial);
    group.add(outerMesh);

    // Particle constellation
    const particleCount = 180;
    const particleGeometry = new THREE.BufferGeometry();
    const positions = new Float32Array(particleCount * 3);

    for (let i = 0; i < particleCount * 3; i += 3) {
      positions[i] = (Math.random() - 0.5) * 8;
      positions[i + 1] = (Math.random() - 0.5) * 6;
      positions[i + 2] = (Math.random() - 0.5) * 4;
    }
    particleGeometry.setAttribute("position", new THREE.BufferAttribute(positions, 3));

    const particleMaterial = new THREE.PointsMaterial({
      size: 0.04,
      color: 0xc084fc,
      transparent: true,
      opacity: 0.7,
      blending: THREE.AdditiveBlending,
    });
    const particles = new THREE.Points(particleGeometry, particleMaterial);
    scene.add(particles);

    // 4. Mouse Interactive Parallax
    let targetX = 0;
    let targetY = 0;
    let windowHalfX = width / 2;
    let windowHalfY = height / 2;

    const onMouseMove = (e: MouseEvent) => {
      targetX = (e.clientX - windowHalfX) * 0.0008;
      targetY = (e.clientY - windowHalfY) * 0.0008;
    };
    window.addEventListener("mousemove", onMouseMove);

    // Resize Handler
    const onResize = () => {
      if (!mount) return;
      const newW = mount.clientWidth;
      const newH = mount.clientHeight;
      camera.aspect = newW / newH;
      camera.updateProjectionMatrix();
      renderer.setSize(newW, newH);
      windowHalfX = newW / 2;
      windowHalfY = newH / 2;
    };
    window.addEventListener("resize", onResize);

    // 5. Animation Loop
    let animationFrameId: number;
    const clock = new THREE.Clock();

    const animate = () => {
      animationFrameId = requestAnimationFrame(animate);
      const elapsed = clock.getElapsedTime();

      // Smooth rotation
      mainMesh.rotation.y = elapsed * 0.25;
      mainMesh.rotation.x = elapsed * 0.15;

      outerMesh.rotation.y = -elapsed * 0.18;
      outerMesh.rotation.z = elapsed * 0.12;

      particles.rotation.y = elapsed * 0.05;

      // Parallax easing (Disney anticipation / follow through)
      group.rotation.y += (targetX - group.rotation.y) * 0.05;
      group.rotation.x += (targetY - group.rotation.x) * 0.05;

      // Subtle breathing scale
      const scale = 1 + Math.sin(elapsed * 1.5) * 0.03;
      mainMesh.scale.set(scale, scale, scale);

      renderer.render(scene, camera);
    };
    animate();

    // 6. Cleanup
    return () => {
      window.removeEventListener("mousemove", onMouseMove);
      window.removeEventListener("resize", onResize);
      cancelAnimationFrame(animationFrameId);
      if (mount && renderer.domElement) {
        mount.removeChild(renderer.domElement);
      }
      mainGeometry.dispose();
      mainMaterial.dispose();
      outerGeometry.dispose();
      outerMaterial.dispose();
      particleGeometry.dispose();
      particleMaterial.dispose();
      renderer.dispose();
    };
  }, [variant]);

  return (
    <div
      ref={mountRef}
      className={`relative w-full h-[420px] md:h-[540px] flex items-center justify-center overflow-hidden pointer-events-none ${className}`}
    />
  );
}
'''

FLOATING_DOCK_TEMPLATE = '''"use client";

import React from "react";
import { Camera, Volume2, BatteryCharging, ShieldCheck, ArrowUpRight } from "lucide-react";

interface DockItem {
  icon: React.ReactNode;
  title: string;
  subtitle: string;
}

const items: DockItem[] = [
  { icon: <Camera className="w-5 h-5 text-neutral-800 dark:text-neutral-200" />, title: "Capture Everything", subtitle: "Ultra-wide 4K optic sensors" },
  { icon: <Volume2 className="w-5 h-5 text-neutral-800 dark:text-neutral-200" />, title: "Spatial Audio", subtitle: "Immersive 360 soundscape" },
  { icon: <BatteryCharging className="w-5 h-5 text-neutral-800 dark:text-neutral-200" />, title: "All-Day Power", subtitle: "High-density silicon battery" },
  { icon: <ShieldCheck className="w-5 h-5 text-neutral-800 dark:text-neutral-200" />, title: "Autonomous AI", subtitle: "Neural coprocessor onboard" },
];

export default function FloatingGlassDock() {
  return (
    <div className="fixed bottom-6 left-1/2 -translate-x-1/2 z-40 w-[95%] max-w-4xl">
      <div className="backdrop-blur-2xl bg-white/70 dark:bg-black/60 border border-white/80 dark:border-white/10 shadow-[0_20px_50px_rgba(0,0,0,0.1)] rounded-full p-2 md:p-3 flex items-center justify-between gap-2 md:gap-4 transition-all duration-300 hover:shadow-[0_25px_60px_rgba(0,0,0,0.15)]">
        <div className="hidden sm:grid grid-cols-4 gap-3 flex-1 px-2">
          {items.map((item, idx) => (
            <div
              key={idx}
              className="flex items-center gap-3 p-2 rounded-2xl transition-all duration-200 hover:bg-neutral-100/70 dark:hover:bg-neutral-800/50 cursor-pointer group"
            >
              <div className="p-2.5 rounded-xl bg-white dark:bg-neutral-900 shadow-sm border border-neutral-200/50 dark:border-neutral-800 group-hover:scale-105 transition-transform duration-200">
                {item.icon}
              </div>
              <div className="text-left">
                <p className="text-xs font-semibold text-neutral-900 dark:text-white leading-tight">{item.title}</p>
                <p className="text-[10px] text-neutral-500 dark:text-neutral-400 truncate">{item.subtitle}</p>
              </div>
            </div>
          ))}
        </div>
        <button className="flex items-center gap-2 bg-neutral-950 dark:bg-white text-white dark:text-neutral-950 font-medium text-xs md:text-sm px-5 py-3 rounded-full hover:opacity-90 active:scale-95 transition-all shadow-md group whitespace-nowrap">
          <span>Explore Architecture</span>
          <ArrowUpRight className="w-4 h-4 group-hover:translate-x-0.5 group-hover:-translate-y-0.5 transition-transform" />
        </button>
      </div>
    </div>
  );
}
'''

MOTION_CSS_SNIPPET = """
/* Adicione em globals.css para animações fluidas estilo Apple / Stripe / Vercel */
@keyframes floatSlow {
  0%, 100% {
    transform: translateY(0px) rotate(0deg);
  }
  50% {
    transform: translateY(-10px) rotate(1deg);
  }
}

@keyframes pulseGlow {
  0%, 100% {
    opacity: 0.4;
    transform: scale(1);
  }
  50% {
    opacity: 0.7;
    transform: scale(1.05);
  }
}

.animate-float {
  animation: floatSlow 6s ease-in-out infinite;
}

.animate-glow {
  animation: pulseGlow 8s ease-in-out infinite;
}

/* Glassmorphism helpers */
.glass-panel {
  background: rgba(255, 255, 255, 0.65);
  backdrop-filter: blur(20px);
  -webkit-backdrop-filter: blur(20px);
  border: 1px solid rgba(255, 255, 255, 0.5);
}

.dark .glass-panel {
  background: rgba(10, 10, 12, 0.6);
  backdrop-filter: blur(20px);
  -webkit-backdrop-filter: blur(20px);
  border: 1px solid rgba(255, 255, 255, 0.08);
}
"""

BENTO_GRID_TEMPLATE = '''"use client";

import React from "react";
import { Zap, ShieldCheck, Layers, BarChart3 } from "lucide-react";

interface BentoItem {
  title: string;
  description: string;
  header: React.ReactNode;
  className?: string;
  icon?: React.ReactNode;
}

export default function BentoGridDemo() {
  const items: BentoItem[] = [
    {
      title: "Real-time Neural Engine",
      description: "Autonomous models fine-tuned for millisecond decision execution.",
      header: (
        <div className="flex flex-1 w-full h-full min-h-[6rem] rounded-2xl bg-gradient-to-br from-violet-500/20 via-purple-500/5 to-transparent border border-white/10 p-4 flex items-center justify-center">
          <div className="flex items-center gap-2 px-3 py-1.5 rounded-full bg-violet-500/20 border border-violet-400/30 text-violet-300 text-xs font-mono">
            <span className="w-2 h-2 rounded-full bg-violet-400 animate-ping" />
            99.98% Latency SLA
          </div>
        </div>
      ),
      className: "md:col-span-2",
      icon: <Zap className="h-4 w-4 text-violet-400" />,
    },
    {
      title: "Encrypted Vaults",
      description: "Hardware security modules guard every secret in your cloud.",
      header: (
        <div className="flex flex-1 w-full h-full min-h-[6rem] rounded-2xl bg-gradient-to-br from-emerald-500/20 via-teal-500/5 to-transparent border border-white/10 p-4 flex items-center justify-center">
          <ShieldCheck className="w-12 h-12 text-emerald-400/80" />
        </div>
      ),
      className: "md:col-span-1",
      icon: <ShieldCheck className="h-4 w-4 text-emerald-400" />,
    },
    {
      title: "Multi-cluster Sync",
      description: "Continuous deployments across global edge regions in one click.",
      header: (
        <div className="flex flex-1 w-full h-full min-h-[6rem] rounded-2xl bg-gradient-to-br from-cyan-500/20 via-blue-500/5 to-transparent border border-white/10 p-4 flex items-center justify-center">
          <Layers className="w-12 h-12 text-cyan-400/80" />
        </div>
      ),
      className: "md:col-span-1",
      icon: <Layers className="h-4 w-4 text-cyan-400" />,
    },
    {
      title: "Predictive Analytics",
      description: "Forecast compute needs before traffic spikes hit production.",
      header: (
        <div className="flex flex-1 w-full h-full min-h-[6rem] rounded-2xl bg-gradient-to-br from-amber-500/20 via-orange-500/5 to-transparent border border-white/10 p-4 flex items-center justify-center">
          <BarChart3 className="w-12 h-12 text-amber-400/80" />
        </div>
      ),
      className: "md:col-span-2",
      icon: <BarChart3 className="h-4 w-4 text-amber-400" />,
    },
  ];

  return (
    <div className="grid grid-cols-1 md:grid-cols-3 gap-4 max-w-7xl mx-auto w-full">
      {items.map((item, i) => (
        <div
          key={i}
          className={`row-span-1 rounded-3xl group/bento hover:shadow-2xl transition duration-300 p-6 bg-neutral-950/60 backdrop-blur-xl border border-white/10 justify-between flex flex-col space-y-4 hover:border-white/20 hover:-translate-y-1 ${item.className || ""}`}
        >
          {item.header}
          <div className="group-hover/bento:translate-x-1 transition duration-200">
            <div className="flex items-center gap-2 mb-2">
              {item.icon}
              <h3 className="font-semibold text-neutral-100 text-base">{item.title}</h3>
            </div>
            <p className="font-normal text-neutral-400 text-xs leading-relaxed">{item.description}</p>
          </div>
        </div>
      ))}
    </div>
  );
}
'''

AURORA_BACKGROUND_TEMPLATE = '''"use client";

import React from "react";

interface AuroraBackgroundProps {
  children: React.ReactNode;
  className?: string;
}

export default function AuroraBackground({ children, className = "" }: AuroraBackgroundProps) {
  return (
    <div className={`relative flex flex-col min-h-screen items-center justify-center bg-zinc-950 text-slate-100 overflow-hidden ${className}`}>
      <div className="absolute inset-0 overflow-hidden pointer-events-none">
        <div
          className="
            [--aurora:repeating-linear-gradient(100deg,#3b82f6_10%,#a855f7_15%,#06b6d4_20%,#ec4899_25%,#6366f1_30%)]
            [background-image:var(--aurora)]
            [background-size:300%,_200%]
            filter blur-[80px]
            opacity-35
            animate-float
            absolute -inset-[10px]
          "
        />
      </div>
      <div className="relative z-10 w-full flex flex-col items-center">{children}</div>
    </div>
  );
}
'''

SHIMMER_BUTTON_TEMPLATE = '''"use client";

import React from "react";
import { ArrowRight } from "lucide-react";

interface ShimmerButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  children: React.ReactNode;
}

export default function ShimmerButton({
  children,
  className = "",
  ...props
}: ShimmerButtonProps) {
  return (
    <button
      className={`relative inline-flex items-center justify-center p-[1px] overflow-hidden rounded-full font-medium text-sm transition-all duration-300 active:scale-95 group shadow-[0_0_25px_rgba(168,85,247,0.35)] hover:shadow-[0_0_35px_rgba(168,85,247,0.6)] ${className}`}
      {...props}
    >
      <span className="absolute inset-0 w-full h-full bg-gradient-to-r from-violet-600 via-fuchsia-500 to-cyan-400 animate-spin duration-3000 rounded-full" />
      <span className="relative px-6 py-3 transition-all ease-out bg-neutral-950 text-white rounded-full flex items-center gap-2 group-hover:bg-neutral-900">
        {children}
        <ArrowRight className="w-4 h-4 transition-transform group-hover:translate-x-1" />
      </span>
    </button>
  );
}
'''

# ==============================================================================
# CANVAS UI INTEGRATION (https://canvasui.dev/ - Creative WebGL & WebGPU)
# ==============================================================================
CANVAS_UI_REGISTRY_COMPONENTS = {
    "particle-reveal": "npx shadcn@latest add @canvas-ui/particle-reveal-react",
    "force-field": "npx shadcn@latest add @canvas-ui/force-field-react",
    "flame-wrap": "npx shadcn@latest add @canvas-ui/flame-wrap-react",
    "glass-object": "npx shadcn@latest add @canvas-ui/glass-object-react",
    "decrypt-reveal": "npx shadcn@latest add @canvas-ui/decrypt-reveal-react",
    "glyph-rain": "npx shadcn@latest add @canvas-ui/glyph-rain-react",
    "frost": "npx shadcn@latest add @canvas-ui/frost-react",
    "bubble": "npx shadcn@latest add @canvas-ui/bubble-react",
    "clouds": "npx shadcn@latest add @canvas-ui/clouds-react",
    "grid": "npx shadcn@latest add @canvas-ui/grid-react",
    "ascii-object": "npx shadcn@latest add @canvas-ui/ascii-object-react",
    "liquid": "npx shadcn@latest add @canvas-ui/liquid-react"
}

# Template de Efeito de Partículas Interativas em Canvas Puro (Zero dependências adicionais)
CANVAS_INTERACTIVE_PARTICLES_TEMPLATE = '''"use client";

import React, { useEffect, useRef } from "react";

interface CanvasParticlesProps {
  particleCount?: number;
  particleColor?: string;
  lineColor?: string;
  className?: string;
}

export default function CanvasInteractiveParticles({
  particleCount = 50,
  particleColor = "rgba(168, 85, 247, 0.7)",
  lineColor = "rgba(168, 85, 247, 0.15)",
  className = "",
}: CanvasParticlesProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    let animationFrameId: number;
    let width = (canvas.width = canvas.parentElement?.clientWidth || window.innerWidth);
    let height = (canvas.height = canvas.parentElement?.clientHeight || 500);

    const onResize = () => {
      if (!canvas) return;
      width = canvas.width = canvas.parentElement?.clientWidth || window.innerWidth;
      height = canvas.height = canvas.parentElement?.clientHeight || 500;
    };
    window.addEventListener("resize", onResize);

    // Mouse tracker
    const mouse = { x: -1000, y: -1000, radius: 120 };
    const onMouseMove = (e: MouseEvent) => {
      const rect = canvas.getBoundingClientRect();
      mouse.x = e.clientX - rect.left;
      mouse.y = e.clientY - rect.top;
    };
    window.addEventListener("mousemove", onMouseMove);

    // Particles setup
    const particles = Array.from({ length: particleCount }, () => ({
      x: Math.random() * width,
      y: Math.random() * height,
      vx: (Math.random() - 0.5) * 0.8,
      vy: (Math.random() - 0.5) * 0.8,
      size: Math.random() * 2 + 1,
    }));

    const render = () => {
      ctx.clearRect(0, 0, width, height);

      // Draw and connect particles
      for (let i = 0; i < particles.length; i++) {
        const p = particles[i];
        p.x += p.vx;
        p.y += p.vy;

        if (p.x < 0 || p.x > width) p.vx *= -1;
        if (p.y < 0 || p.y > height) p.vy *= -1;

        // Interaction with mouse
        const dx = mouse.x - p.x;
        const dy = mouse.y - p.y;
        const dist = Math.sqrt(dx * dx + dy * dy);
        if (dist < mouse.radius) {
          const force = (mouse.radius - dist) / mouse.radius;
          p.x -= (dx / dist) * force * 2;
          p.y -= (dy / dist) * force * 2;
        }

        ctx.beginPath();
        ctx.arc(p.x, p.y, p.size, 0, Math.PI * 2);
        ctx.fillStyle = particleColor;
        ctx.fill();

        for (let j = i + 1; j < particles.length; j++) {
          const p2 = particles[j];
          const d2 = Math.hypot(p.x - p2.x, p.y - p2.y);
          if (d2 < 110) {
            ctx.beginPath();
            ctx.moveTo(p.x, p.y);
            ctx.lineTo(p2.x, p2.y);
            ctx.strokeStyle = lineColor;
            ctx.lineWidth = 1 - d2 / 110;
            ctx.stroke();
          }
        }
      }

      animationFrameId = requestAnimationFrame(render);
    };

    render();

    return () => {
      window.removeEventListener("resize", onResize);
      window.removeEventListener("mousemove", onMouseMove);
      cancelAnimationFrame(animationFrameId);
    };
  }, [particleCount, particleColor, lineColor]);

  return <canvas ref={canvasRef} className={`absolute inset-0 pointer-events-none z-0 ${className}`} />;
}
'''


