# Diretrizes de UI/UX e Design System com Mobbin MCP

Esta regra deve ser aplicada sempre que houver criação, reformulação ou formatação de interfaces de usuário (Web, Mobile, Dashboards, Landing Pages ou Componentes).

---

## 1. Pesquisa e Benchmark Visual com Mobbin MCP

Antes de gerar ou refatorar interfaces visuais, utilize o servidor Mobbin MCP para extrair referências de produtos de alto padrão do mercado (ex.: Stripe, Linear, Airbnb, Notion, Revolut, Vercel).

### Ferramentas a utilizar:
- **`search_screens`**: Para telas individuais completas (ex.: dashboards analíticos, telas de login, páginas de perfil, configurações, tabelas de dados).
- **`search_sections`**: Para seções modulares específicas (ex.: tabelas de preços/pricing, heros, rodapés, banners de conversão, modais de confirmação).
- **`search_flows`**: Para jornadas completas com múltiplos passos (ex.: fluxo de onboarding, checkout em etapas, funil de assinatura, redefinição de credenciais).

### Diretriz de Busca:
- Realize buscas com termos em inglês detalhados (ex.: `"dark mode analytics dashboard"`, `"minimalist saas pricing cards"`, `"multi-step onboarding flow"`).
- Se a busca falhar ou o Mobbin estiver offline/desconectado, utilize os princípios abaixo como guia absoluto de qualidade visual.

---

## 2. Princípios de Execução e Qualidade Visual (Anti-Genérico)

### A. Hierarquia e Tipografia
- Nunca utilize fontes genéricas do sistema quando for possível aplicar fontes modernas (ex.: Inter, Outfit, Plus Jakarta Sans, Geist).
- Estabeleça contraste nítido de hierarquia entre títulos (`h1`, `h2`), subtítulos, textos de apoio e rótulos auxiliares (muted text).
- Mantenha tamanhos e line-heights harmoniosos com legibilidade impecável.

### B. Paleta de Cores e Superfícies
- **Evite cores primárias brutas/puras** (como azul #0000FF ou verde puro). Utilize paletas semânticas bem equilibradas com variações de matiz e saturação cuidadosas.
- Em **Dark Mode**:
  - Evite preto absoluto (#000000) chapado em tudo; utilize camadas de profundidade (background profundo, cards ligeiramente elevados com superfícies em tons como `#12161f` ou `#181b22`).
  - Aplique bordas sutis e translúcidas (ex.: `rgba(255, 255, 255, 0.08)` ou classes equivalentes `border-white/10`) para delimitar blocos visuais.
  - Utilize efeitos sutis de vidro e blur (`backdrop-blur-md`, gradientes radiais suaves de iluminação de fundo).

### C. Espaçamento e Ritmo Visual
- Respeite uma escala proporcional consistente (múltiplos de 4px ou 8px).
- Evite aglomeração de dados; garanta "respiro" entre seções e agrupamentos lógicos de conteúdo.
- Agrupe elementos semanticamente relacionados dentro de cards, seções ou painéis bem definidos.

### D. Estados de Interação e Microinterações
Toda interface de excelência precisa parecer "viva" e responsiva:
- **Hover & Active**: Feedback visual suave em botões, links e cards clicáveis (mudança sutil de luminosidade, borda acentuada ou leve transição de escala).
- **Loading & Empty States**: Nunca deixe telas vazias sem contexto. Apresente ilustrações/ícones adequados, mensagem descritiva e botão de ação (CTA) para o próximo passo.
- **Transições**: Animações de entrada e saída suaves (150ms a 300ms com curvas de desaceleração como `ease-out` ou `cubic-bezier`).

---

## 3. Fluxo de Trabalho do Agente

1. **Compreensão do Requisito**: Identificar os dados necessários, o objetivo do usuário e o tipo de interface.
2. **Benchmark no Mobbin**: Executar `search_screens` ou `search_sections` para encontrar 2 a 3 referências de interfaces consagradas no mesmo domínio.
3. **Mapeamento de Padrões**: Observar a disposição de controles, ações principais versus secundárias e feedback visual das referências.
4. **Implementação de Código**: Construir os componentes com atenção aos detalhes de acabamento, acessibilidade e responsividade.
5. **Revisão Visual**: Validar se o resultado transmite um aspecto profissional, moderno e refinado antes de finalizar.
