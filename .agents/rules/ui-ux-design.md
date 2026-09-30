# Diretrizes de UI/UX, Design System e Pesquisa Autônoma de Referências

Esta regra deve ser aplicada sempre que houver criação, reformulação ou formatação de interfaces de usuário (Web, Mobile, Dashboards, Landing Pages ou Componentes).

---

## 1. Pesquisa Autônoma e Benchmark Visual de Elite

Antes de gerar ou refatorar qualquer interface, o agente deve buscar referências ativas de produtos de padrão mundial (Linear, Stripe, Apple, Vercel, Supabase, Raycast):

### Fontes e Ferramentas:
1. **Mobbin MCP / API**:
   - `search_screens`, `search_sections`, `search_flows` (quando disponível plano pago).
2. **Bibliotecas Open-Source de "Design Engineering" (Gratuitas e Abertas)**:
   - **[Aceternity UI](https://ui.aceternity.com/)**: Referência para Bento Grids, Aurora Backgrounds, 3D Pin cards, Glowing Stars e Tabs dinâmicas.
   - **[Magic UI](https://magicui.design/)**: Referência para Shimmer Buttons, Text effects, Particle trails e Landing pages modernas.
   - **[21st.dev](https://21st.dev/)**: Componentes comunitários em Tailwind CSS + Motion de alta fidelidade.
   - **[Godly Website](https://godly.website/)** e **[Lapa Ninja](https://www.lapa.ninja/)**: Galerias visuais gratuitas para layout, tipografia e espaçamento.
3. **Mecanismo de Pesquisa Ativa**:
   - Quando não houver Mobbin pago, a ferramenta `search_mobbin_screens` executa automaticamente buscas na web via DuckDuckGo em `ui.aceternity.com`, `magicui.design` e `21st.dev` para extrair receitas de código e padrões visuais atualizados.

---

## 2. Proatividade & Modo "Diretor Criativo"

O agente não é apenas um executor passivo de HTML/CSS:
- **Alinhamento Estético Inicial**: Ao receber uma solicitação de tela ou projeto, o agente formula uma direção criativa marcante (Arquétipo, paleta e componentes de destaque) e avisa ou sugere a estética para o usuário antes de começar a codificar.
- **Sugestão de Componentes de Luxo**: Propõe ativamente a inclusão de elementos como:
  - *Bento Grid* assimétrico com bordas translúcidas e glow no hover.
  - *ThreeHeroScene* (Three.js 3D procedural gerado em código com orbe de vidro, malha física e partículas que reagem ao mouse).
  - *FloatingGlassDock* (barra inferior flutuante em vidro fosco com ícones Lucide).
  - *AuroraBackground* (efeito de luz ambiente dinâmico).
  - *ShimmerButton* (botão CTA com borda de luz animada).

---

## 3. Princípios de Execução e Qualidade Visual (Anti-Genérico)

### A. Hierarquia e Tipografia
- Use fontes sans-serif contemporâneas (Geist, Inter, Outfit, Plus Jakarta Sans) com tracking ajustado.
- Contraste rígido de peso entre títulos display e subtítulos muted.

### B. Paleta de Cores e Superfícies
- **Evite cores primárias brutas ou puras**. Use paletas semânticas equilibradas.
- Em **Dark Mode**:
  - Camadas de profundidade: Fundo escuro profundo (`#090A0F`), cards ligeiramente elevados (`#11141D` ou `#161922`).
  - Bordas sutis e translúcidas (`border-white/10` ou `rgba(255, 255, 255, 0.08)`).
  - Vidro fosco e blur (`backdrop-blur-xl bg-neutral-950/60`).

### C. Microinterações e Motion (3 Camadas)
1. **Entrada (Primária)**: Transições suaves em cascata com desaceleração.
2. **Interação (Secundária)**: `hover:-translate-y-0.5`, `hover:border-white/20`, `active:scale-95`.
3. **Ambiente (Terciária)**: Animações sutis contínuas em background (`animate-float`, `animate-pulse`, `animate-ping` nos badges de status).

---

## 4. Fluxo de Trabalho do Agente

1. **Pesquisa Autônoma**: Executar `search_mobbin_screens(query="...")` para capturar referências na web e tokens do arquétipo.
2. **Comunicação Proativa**: Informar o usuário sobre a escolha estética proposta.
3. **Implementação de Excelência**: Criar os arquivos aplicando os templates de `agent/design_system.py`, cuidando de cada detalhe de espaçamento, responsividade e contraste.
4. **Validação & Entrega**: Revisar se o visual transmite acabamento de produto mundial antes de finalizar.
