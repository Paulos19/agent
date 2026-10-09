# Diretrizes de UI/UX, Design System, Motion GSAP e Shaders Canvas UI (Anti-AI Slop)

Esta regra é de cumprimento OBRIGATÓRIO em toda criação, reformulação ou evolução de interfaces de usuário (Web Apps, SaaS, Dashboards, Landing Pages, Mobile e Componentes) operadas pelo agente via WhatsApp ou Telegram.

---

## 1. Protocolo de Execução em Duas Fases

### A. Aplicações Fullstack / Plataformas com Backend
1. **Fase 1: Engenharia Estrutural & Backend (Infraestrutura First)**:
   - Definição de rotas, API endpoints, serviços e schema de banco de dados (Prisma, Drizzle, PostgreSQL, SQLite).
   - Coleta de credenciais: Consultar primeiro as chaves reais no `.env` da VPS via `get_vps_env_var()`. Caso alguma chave de API de terceiro (Stripe, Resend, OpenAI) ou URL externa do banco não esteja presente, solicitar de forma objetiva ao usuário via WhatsApp/Telegram antes de seguir.
   - **Gate de Validação**: Executar `npm run build` no terminal para garantir compilação sem erros (`0 errors`).
2. **Transição Automática para Fase 2**:
   - Assim que o backend estiver estável e compilado, emitir notificação amigável e **ATIVAR IMEDIATAMENTE O MÓDULO WEB DESIGNER**.

### B. Landing Pages, Portfólios e Projetos Visuais
- **Ativação Direta**: Ativar imediatamente a **Fase 2 (Módulo Web Designer)** sem perda de tempo com configurações de banco ou backend desnecessárias.

---

## 2. Fase 2: Módulo Web Designer & Coleta Visual (Anti-AI Slop)

O agente deve recusar sumariamente a criação de layouts genéricos, caixas cinzas sem vida, minimalismo vazio ou layouts previsíveis de IA ("AI slop").

### A. Coleta Ativa de Inspirações:
1. **Entrada do Usuário no Chat**:
   - Convidar o usuário a mandar prints, fotos ou links de sites que ele achou incríveis diretamente no WhatsApp/Telegram.
   - O agente analisa os prints com visão multimodal em alta resolução para extrair padrões e layout.
2. **Pesquisa Autônoma no Dribbble & Pinterest (Playwright Headless + IA Multimodal)**:
   - `search_dribbble_and_analyze_ui(query="...", project_path="...")`: Acessa o Dribbble em navegador headless, captura screenshots em alta definição dos melhores shots de design premiados e disseca a estética (paleta hex, tipografia, microinterações GSAP e shaders).
   - `search_pinterest_and_analyze_ui(query="...", project_path="...")`: Acessa o Pinterest em navegador headless, limpa popups, fotografa boards e pins de UI/UX modernos e disseca referências visuais com visão multimodal.
   - `search_mobbin_screens(query="...")`: Consulta benchmarks globais (Linear, Stripe, Apple, Vercel, Supabase, Raycast).
   - `capture_and_analyze_design(url="...", focus="...")`: Disseca qualquer URL de referência indicada pelo usuário.

### B. Ativação das Skills Globais de Design:
- **`frontend-design`**: Senso estético ousado, direção de arte intencional e quebra de monotonia.
- **`impeccable`**: Polimento cirúrgico de espaçamentos, micro-hierarquia e acabamento de luxo.
- **`motion-design`**: Coreografia de movimento, curvas cúbicas e timing perfeito.
- **`tailwind-4-docs` (Lombiq)**: Configuração moderna CSS-first com `@theme`, dispensando arquivos JS obsoletos.
- **`canvas-ui`**: Shaders WebGL/WebGPU interativos em tempo real.
- **`Three.js`**: Geometrias procedurais sem assets externos quebrados.

---

## 3. Padrão Oficial de Animações & Parallax: GSAP & ScrollTrigger

Para animações dinâmicas, scroll suave e efeitos de parallax, a biblioteca oficial é o **GSAP** (`gsap`, `@gsap/react`, `ScrollTrigger`).

### A. Instalação:
```bash
npm i gsap @gsap/react
```

### B. Arquitetura Segura em Next.js / React 19:
- Sempre usar `"use client"`.
- Registrar os plugins no topo:
  ```tsx
  import gsap from "gsap";
  import { ScrollTrigger } from "gsap/ScrollTrigger";
  import { useGSAP } from "@gsap/react";

  gsap.registerPlugin(ScrollTrigger, useGSAP);
  ```
- Utilizar o hook com escopo (`scope: containerRef`) para garantir limpeza automática de memória e evitar bugs de hidratação:
  ```tsx
  useGSAP(() => {
    // Parallax em camada com scrub
    gsap.to(bgLayerRef.current, {
      y: 100,
      ease: "none",
      scrollTrigger: {
        trigger: containerRef.current,
        start: "top bottom",
        end: "bottom top",
        scrub: 1.2,
      },
    });

    // Entrada em cascata (stagger) dos cards
    gsap.from(".gsap-stagger-item", {
      opacity: 0,
      y: 40,
      stagger: 0.15,
      duration: 1.0,
      ease: "power3.out",
      scrollTrigger: {
        trigger: containerRef.current,
        start: "top 75%",
      },
    });
  }, { scope: containerRef });
  ```
- Utilizar o componente pronto `GSAP_PARALLAX_SCENE_TEMPLATE` disponível em `agent/design_system.py`.

---

## 4. Integração de Shaders com Canvas UI (https://canvasui.dev/docs)

Componentes WebGL e WebGPU criativos que rodam diretamente sobre HTML real compatíveis com o ecossistema shadcn.

### A. Instalação via shadcn registry:
```bash
npx shadcn@latest add @canvas-ui/<componente>-react
```

### B. Catálogo Completo de Shaders (35+ Efeitos):
1. **Fluidos & Líquidos**:
   - `liquid`: Simulação de fluido com ponteiro que distorce texto e cards reais do DOM.
   - `liquid-object`: Objeto 3D com física de fluido e refração.
   - `ripple`: Ondas concêntricas na água propagando ao mover ou clicar.
   - `droplets`: Gotas de condensação escorrendo e refratando o fundo.
   - `bubble`: Bolhas orgânicas com aberração cromática.
2. **Física & Energia**:
   - `force-field`: Campo magnético interativo que repele elementos ao passar o cursor.
   - `flame-wrap`: Chamas energéticas envolvendo botões, badges ou cards.
   - `cloth`: Tecido 3D com física de vento, gravidade e arrasto.
   - `laser`: Feixe de laser escaneando tipografias e bordas.
3. **Refração Vítrea & 3D**:
   - `glass`: Refração cáustica de vidro fosco de altíssimo realismo.
   - `glass-object`: Objeto 3D vítreo orbitando a interface.
   - `displacement`: Distorção vetorial orgânica na tipografia ao passar o mouse.
   - `bend`: Curvatura 3D cilíndrica deformando o container.
4. **Revelação & Cyberpunk**:
   - `decrypt-reveal`: Descriptografia de dados em tempo real com glifos cibernéticos.
   - `particle-reveal`: Vórtice de partículas WebGL revelando títulos ou imagens.
   - `particle-scroll`: Nuvem de partículas com profundidade no scroll.
   - `glyph-rain`: Chuva digital de glifos estilo Matrix.
5. **Retrô & Arte ASCII**:
   - `ascii-object`: Renderizador volumétrico 3D em tempo real em caracteres ASCII interativos.
   - `ascii-sweep`: Transição de varredura convertendo elementos em arte ASCII.
   - `retro-dither`: Dithering Bayer estilo hardware dos anos 90 / lo-fi brutalista.
   - `vhs` & `glitch`: Distorção analógica CRT com tracking noise e pulso de canal RGB.
6. **Atmosfera & Ambiente**:
   - `clouds`: Nuvens procedurais volumétricas com luz ambiente.
   - `frost`: Cristais de gelo se espalhando pelas bordas no hover.
   - `grid`: Malha cibernética em perspectiva 3D.
   - `shatter`: Estilhaçamento geométrico com quebra em múltiplos fragmentos.

---

## 5. Arquitetura de Motion Design (3 Camadas)

1. **Camada 1 (Primária - Entrada)**:
   - Entradas coreografadas em cascata (stagger < 400ms) com curvas de desaceleração (cubic-bezier(0.16, 1, 0.3, 1) ou GSAP `power3.out`).
2. **Camada 2 (Secundária - Interação)**:
   - Micro-interações de feedback tátil: `hover:-translate-y-1`, `hover:border-white/20`, `active:scale-95`, `group-hover:translate-x-1.5`.
3. **Camada 3 (Terciária - Ambiente)**:
   - Vida contínua de background (shaders Canvas UI em loop, Three.js em requestAnimationFrame, dots com `animate-ping`).

---

## 6. Validação e Entrega Final

- Toda aplicação gerada deve compilar no terminal (`npm run build`) sem erros de lint ou TypeScript.
- Apresentar com clareza as escolhas visuais tomadas: paleta hex, tipografia editorial, componentes Canvas UI e cenas GSAP parallax aplicadas.
