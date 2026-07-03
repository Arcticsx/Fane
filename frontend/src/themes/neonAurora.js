// neonAurora.js
const neonAurora = {
  id: 'neonAurora',
  name: 'Neon Aurora',
  description: 'A riot of electric cyan and magenta against a velvet‑dark cosmos, with golden sparks of light.',
  background: `
    radial-gradient(circle at 20% 30%, rgba(0, 240, 255, 0.30), transparent 35%),
    radial-gradient(circle at 80% 70%, rgba(255, 107, 157, 0.35), transparent 40%),
    radial-gradient(circle at 50% 50%, rgba(255, 215, 0, 0.08), transparent 60%),
    linear-gradient(135deg, #0b081a 0%, #1b1240 50%, #0f0b2a 100%)
  `,
  bgColor: '#0b081a',       // deep cosmic purple‑black
  surface: '#1a1435',       // dark violet for cards
  surface2: '#2a1f4a',      // richer purple for hover states
  border: '#ff6b9d',        // hot pink borders – instant pop
  text: '#f5f0ff',          // crisp, slightly lavender white
  muted: '#b8a8d0',         // soft lilac for secondary text
  accent: '#00f0ff',        // pure cyan – the primary action colour
  accent2: '#ffd700',       // gold – for highlights, badges, or toggles
};

export default neonAurora;