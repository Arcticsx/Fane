# Frontend Guide

## Stack

- **React 18.3** -- UI framework
- **React Router 7.18** -- Client-side routing
- **Vite 6** -- Dev server and bundler
- **Tailwind CSS 4** -- Utility-first styling
- **Lucide React** -- Icon library

## Project Structure

```
frontend/
├── src/
│   ├── components/          # 14 React components
│   │   ├── Chat.jsx
│   │   ├── ChronicleChat.jsx
│   │   ├── ChronicleCreator.jsx
│   │   ├── ChronicleDetail.jsx
│   │   ├── ChronicleList.jsx
│   │   ├── ChronicleSelector.jsx
│   │   ├── ChronicleSessionSelector.jsx
│   │   ├── ConfirmModal.jsx
│   │   ├── EditModal.jsx
│   │   ├── PersonalitySelector.jsx
│   │   ├── SessionSelector.jsx
│   │   ├── Sidebar.jsx
│   │   ├── ThemeModal.jsx
│   │   └── ThemeSelector.jsx
│   ├── api.js               # Centralized API client
│   ├── App.jsx              # Root component with routing and theme
│   ├── index.jsx            # ReactDOM entry point
│   └── themes.js            # Built-in theme definitions
├── index.html
├── package.json
└── vite.config.js
```

## Routing

| Path | Component | Description |
|------|-----------|-------------|
| `/` | `PersonalitySelector` | Home page: personality grid, chronicle links, theme settings |
| `/sessions/:personaKey` | `SessionSelector` | Session list for a personality |
| `/chat/:personaKey/:sessionId?` | `Chat` | Chat interface |
| `/chronicle` | `ChronicleCreator` | Create new chronicle + upload PDF |
| `/chronicle/discover` | `ChronicleSelector` | Browse/manage chronicles |
| `/chronicle/list` | `ChronicleSelector` | Same as discover |
| `/chronicle/:chronicleId` | `ChronicleDetail` → `ChronicleChat` | Chronicle chat interface |

Routes with sidebar: `/sessions/*`, `/chat/*`, `/chronicle/*`.  
Route without sidebar: `/` (PersonalitySelector has its own layout).

## Components

### PersonalitySelector (528 lines)

Home page and main entry point.

- Grid of personality cards with avatars, names, descriptions
- Search/filter personalities
- Create new personality (opens `EditModal`)
- Edit/delete existing personalities
- Theme selector integration
- Navigation to chronicle section

### SessionSelector (197 lines)

Session list for a specific personality.

- Sessions grouped by date: Today, Yesterday, Older
- Search/filter sessions
- Delete sessions with confirmation
- Create new session
- Navigate to chat with selected session

### Chat (293 lines)

Main chat interface.

- Message bubbles (user right, assistant left)
- Auto-resize textarea
- Auto-save on each message exchange
- Load session on mount (resumes or creates new)
- Opening prompt display for new sessions
- Back navigation to session list

### Sidebar (379 lines)

Resizable navigation sidebar.

- Navigation items: Create, Discover, Chronicle
- Recent sessions/chronicles list
- Drag handle for resizing
- Active view highlighting

### ChronicleCreator (209 lines)

Form to create a new chronicle.

- Fields: title, synopsis, genre, world rules, avatar
- PDF file upload
- Processing status polling with progress display
- Navigation to chronicle on completion

### ChronicleSelector (498 lines)

Chronicle browser and manager.

- Grid of chronicle cards with avatars, titles, genres
- Search/filter chronicles
- Edit chronicle (modal with form)
- Delete chronicle with confirmation
- Process status modal with phase/step progress bar
- Navigate to chronicle chat

### ChronicleChat (205 lines)

Chronicle-specific chat interface.

- Similar to Chat but uses chronicle API endpoints
- Sends messages to `POST /story/{id}/chat`
- Displays narrator responses
- Loads full message history on mount

### ChronicleDetail (19 lines)

Thin wrapper that renders `ChronicleChat` with the chronicle ID from route params.

### ChronicleList (97 lines)

Simple chronicle list with open/delete actions.

### ChronicleSessionSelector (192 lines)

Session picker for chronicles. Groups sessions by date.

### EditModal (204 lines)

Personality create/edit form.

- Fields: name, description, system prompt, scenario, opening prompt
- Avatar image upload with preview
- Form validation
- Create or update mode

### ThemeSelector (171 lines)

Theme customization panel.

- Grid of 8 built-in themes with preview swatches
- Custom theme creation (pick colors for each variable)
- Background image upload (stored as base64 data URL)
- Delete custom themes
- Hover preview (temporary theme application)

### ThemeModal (43 lines)

Modal wrapper for `ThemeSelector`.

### ConfirmModal (30 lines)

Generic confirmation dialog with message and confirm/cancel buttons.

## API Client (`api.js`)

Centralized fetch wrapper. All methods return parsed JSON or throw on error.

**Base URL:** `VITE_API_URL` env var or `http://localhost:8000`

**Key methods:**

| Method | Endpoint | Description |
|--------|----------|-------------|
| `getPersonalities()` | `GET /personalities` | List all personalities |
| `createPersonality(data)` | `POST /personalities` | Create with FormData |
| `updatePersonality(key, data)` | `PUT /personalities/{key}` | Update with FormData |
| `deletePersonality(key)` | `DELETE /personalities/{key}` | Delete personality |
| `getRecentSessions()` | `GET /sessions/recent` | Last 10 sessions |
| `getSessions(personaName)` | `GET /sessions/{name}` | Sessions for persona |
| `loadSession(personaKey, session)` | `POST /sessions/load` | Load session messages |
| `saveSession(...)` | `POST /sessions/save` | Persist session |
| `deleteSession(...)` | `DELETE /sessions/{name}/{id}` | Delete session |
| `sendMessage(...)` | `POST /chat` | Send chat message |
| `createChronicle(data)` | `POST /story` | Create chronicle |
| `uploadChronicleDocument(id, file)` | `POST /story/{id}/docs` | Upload PDF |
| `getDocumentStatus(sessionId, docId)` | `GET /story/{id}/docs/{docId}/status` | Poll processing |
| `listChronicles()` | `GET /story` | List all chronicles |
| `getChronicle(id)` | `GET /story/{id}` | Get chronicle details |
| `chatChronicle(id, input)` | `POST /story/{id}/chat` | Chronicle chat |
| `updateChronicle(id, data)` | `PUT /story/{id}` | Update chronicle |
| `deleteChronicle(id)` | `DELETE /story/{id}` | Delete chronicle |

**Error handling:** `handleResponse()` parses JSON, extracts error details from `payload.detail` (supports both string and array formats from Pydantic validation errors).

## Theme System

8 built-in themes defined in `themes.js`:

| Theme | ID | Style |
|-------|----|-------|
| Purpur (default) | `purpur` | Purple gradient, dark surfaces |
| Neon Aurora | `neon-aurora` | Cyan/green neon on dark |
| Ember | `ember` | Warm orange/red tones |
| Midnight | `midnight` | Deep blue/black |
| Sunset | `sunset` | Orange/pink gradient |
| Forest | `forest` | Green earth tones |
| Forest Dusk | `forest-dusk` | Dark green/purple |
| Midnight Teal | `midnight-teal` | Dark teal accents |

Each theme defines CSS custom properties:

```
--color-bg          Background color
--color-surface     Card/panel background
--color-surface-2   Elevated surface
--color-border      Border color
--color-text        Primary text
--color-muted       Secondary text
--color-accent      Primary accent
--color-accent-2    Secondary accent
```

Plus a `background` property for CSS gradients.

**Custom themes:** Users can create custom themes by picking colors for each variable. Custom themes are stored in `localStorage` under `appThemes`.

**Background images:** Users can upload a custom background image (stored as base64 data URL in `localStorage` under `appCustomBackgroundUrl`). This overrides the theme's `background` gradient.

**Persistence:**
- Selected theme ID: `localStorage.appTheme`
- Custom themes: `localStorage.appThemes` (JSON array)
- Custom background: `localStorage.appCustomBackgroundUrl` (base64 data URL)

**Hover preview:** Hovering over a theme temporarily applies it. Moving away restores the selected theme.

## State Management

No external state management library. All state is managed with React hooks:

- `useState` for local component state
- `useRef` for values that persist across renders without triggering re-renders
- `useEffect` for side effects (localStorage sync, polling)
- `useCallback` for memoized callbacks
- `useNavigate` / `useLocation` from React Router for navigation state

Navigation state (persona, session) is passed via `location.state` and preserved across route changes.

## Development

```bash
cd frontend
npm install
npm run dev     # Starts Vite dev server on port 5173
```

The Vite config proxies API requests (`/personalities`, `/sessions`, `/chat`, `/story`) to `http://localhost:8000`.
