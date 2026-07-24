import React from 'react';
import { BrowserRouter, Routes, Route, useLocation, useNavigate } from 'react-router-dom';
import PersonalitySelector from './components/PersonalitySelector.jsx';
import SessionSelector from './components/SessionSelector.jsx';
import Chat from './components/Chat.jsx';
import Sidebar from './components/Sidebar';
import ChronicleCreator from './components/ChronicleCreator';
import ChronicleSelector from './components/ChronicleSelector';
import ChronicleSessionSelector from './components/ChronicleSessionSelector';
import ChronicleDetail from './components/ChronicleDetail';
import ChronicleChat from './components/ChronicleChat';
import themes from './themes';

function AppContent() {
  const navigate = useNavigate();
  const location = useLocation();
  const [selectedThemeId, setSelectedThemeId] = React.useState(() => {
    try {
      return localStorage.getItem('appTheme') || 'purpur';
    } catch (e) {
      return 'purpur';
    }
  });
  const [customBackgroundUrl, setCustomBackgroundUrl] = React.useState(() => {
    try {
      return localStorage.getItem('appCustomBackgroundUrl') || '';
    } catch (e) {
      return '';
    }
  });

  const [gradientEnabled, setGradientEnabled] = React.useState(() => {
    try {
      const stored = localStorage.getItem('appGradientEnabled');
      return stored === null ? true : stored === 'true';
    } catch (e) {
      return true;
    }
  });

  const [themeList, setThemeList] = React.useState(() => {
    try {
      const stored = JSON.parse(localStorage.getItem('appThemes') || 'null');
      return stored && Array.isArray(stored) ? [...themes, ...stored] : themes;
    } catch (e) {
      return themes;
    }
  });

  const [previewThemeId, setPreviewThemeId] = React.useState(null);
  const [previewThemeObject, setPreviewThemeObject] = React.useState(null);

  const currentTheme = previewThemeObject
    ? previewThemeObject
    : themeList.find((theme) => theme.id === (previewThemeId || selectedThemeId)) || themeList[0];

  React.useEffect(() => {
    localStorage.setItem('appTheme', selectedThemeId);
  }, [selectedThemeId]);

  React.useEffect(() => {
    localStorage.setItem('appGradientEnabled', String(gradientEnabled));
  }, [gradientEnabled]);

  React.useEffect(() => {
    try {
      const custom = themeList.filter((t) => t.custom === true);
      localStorage.setItem('appThemes', JSON.stringify(custom));
    } catch (e) {}
  }, [themeList]);

  React.useEffect(() => {
    if (customBackgroundUrl) {
      localStorage.setItem('appCustomBackgroundUrl', customBackgroundUrl);
    } else {
      localStorage.removeItem('appCustomBackgroundUrl');
    }
  }, [customBackgroundUrl]);

  const handleUploadBackground = (file) => {
    const reader = new FileReader();
    reader.onload = () => {
      setCustomBackgroundUrl(reader.result);
    };
    reader.readAsDataURL(file);
  };

  const handleCreateCustomTheme = (theme) => {
    const id = `custom-${Date.now()}`;
    const t = { id, ...theme, custom: true };
    setThemeList((prev) => [...prev, t]);
    setSelectedThemeId(id);
  };

  const handleDeleteTheme = (id) => {
    setThemeList((prev) => {
      const next = prev.filter((t) => t.id !== id);
      if (selectedThemeId === id) {
        setSelectedThemeId(next[0]?.id || themes[0]?.id || 'purpur');
      }
      return next;
    });
  };

  const handleUpdateTheme = (id, updates) => {
    setThemeList((prev) => prev.map((t) => (t.id === id ? { ...t, ...updates } : t)));
    if (selectedThemeId === id) {
      setSelectedThemeId(id);
    }
  };

  const handleHoverPreview = (themeOrId) => {
    if (!themeOrId) return;
    if (typeof themeOrId === 'object') {
      setPreviewThemeObject(themeOrId);
      setPreviewThemeId(null);
    } else {
      setPreviewThemeObject(null);
      setPreviewThemeId(themeOrId);
    }
  };
  const handleHoverPreviewEnd = () => {
    setPreviewThemeId(null);
    setPreviewThemeObject(null);
  };

  const handleSelectTheme = (id) => {
    setSelectedThemeId(id);
    setPreviewThemeId(null);
    setPreviewThemeObject(null);
  };

  const routePersona = location.state?.persona || null;
  const routeSession = location.state?.session || null;
  const personaRef = React.useRef(routePersona);
  personaRef.current = routePersona;

  const navigateWithHistory = React.useCallback((to, options = {}) => {
    const historyState = { ...(location.state || {}), ...(options.state || {}) };
    navigate(to, { ...options, state: historyState });
  }, [location.state, navigate]);

  const handlePersonaSelected = (persona) => {
    navigateWithHistory(`/sessions/${encodeURIComponent(persona.key)}`, { state: { persona } });
  };

  const handleSessionSelected = (session) => {
    const persona = personaRef.current;
    if (!persona?.key) {
      console.error('No persona selected for session navigation');
      return;
    }
    const targetPath = session
      ? `/chat/${encodeURIComponent(persona.key)}/${session.id}`
      : `/chat/${encodeURIComponent(persona.key)}`;
    navigateWithHistory(targetPath, { state: { persona, session } });
  };

  const handleBackToPersonalities = () => {
    navigateWithHistory('/');
  };

  const handleBackToSessions = () => {
    const persona = personaRef.current;
    if (!persona?.key) return;
    navigateWithHistory(`/sessions/${encodeURIComponent(persona.key)}`, { state: { persona } });
  };

  const themeVars = {
    '--color-bg': currentTheme.bgColor,
    '--color-surface': currentTheme.surface,
    '--color-surface-2': currentTheme.surface2,
    '--color-border': currentTheme.border,
    '--color-text': currentTheme.text,
    '--color-muted': currentTheme.muted,
    '--color-accent': currentTheme.accent,
    '--color-accent2': currentTheme.accent2,
  };

  const rootStyle = {
    ...themeVars,
    ...(customBackgroundUrl
      ? {
          backgroundImage: `url('${customBackgroundUrl}')`,
          backgroundSize: 'cover',
          backgroundPosition: 'center',
          backgroundRepeat: 'no-repeat',
        }
      : gradientEnabled
        ? { background: currentTheme.background }
        : { backgroundColor: currentTheme.bgColor }),
  };

  return (
    <div className="min-h-screen text-text" style={rootStyle}>
      <Routes>
        <Route
          path="/"
          element={
            <PersonalitySelector
              onPersonaSelected={handlePersonaSelected}
              selectedThemeId={selectedThemeId}
              customBackgroundUrl={customBackgroundUrl}
              gradientEnabled={gradientEnabled}
              onToggleGradient={() => setGradientEnabled((prev) => !prev)}
              themes={themeList}
              onSelectTheme={handleSelectTheme}
              onCreateCustomTheme={handleCreateCustomTheme}
              onUploadBackground={handleUploadBackground}
              onClearCustomBackground={() => setCustomBackgroundUrl('')}
              onHoverPreview={handleHoverPreview}
              onHoverPreviewEnd={handleHoverPreviewEnd}
              onDeleteTheme={handleDeleteTheme}
              onUpdateTheme={handleUpdateTheme}
            />
          }
        />
        <Route
          path="/sessions/:personaKey"
          element={
            <div className="flex h-screen">
              <Sidebar
                activeView="create"
                onViewChange={() => {}}
                onCreateClick={handleBackToPersonalities}
              />
              <main className="flex-1 overflow-hidden">
                <SessionSelector
                  persona={routePersona}
                  onSessionSelected={handleSessionSelected}
                  onBack={handleBackToPersonalities}
                />
              </main>
            </div>
          }
        />
        <Route
          path="/chat/:personaKey/:sessionId?"
          element={
            <div className="flex h-screen">
            <Sidebar
              activeView="discover"
              onViewChange={() => {}}
              onCreateClick={handleBackToPersonalities}
            />
            <main className="flex-1 overflow-hidden">
              <Chat
                persona={routePersona}
                session={routeSession}
                onBack={handleBackToSessions}
              />
            </main>
          </div>
          }
        />
        <Route
          path="/chronicle"
          element={
            <div className="flex h-screen">
              <Sidebar
                activeView="Chronicle"
                onViewChange={() => {}}
                onCreateClick={() => navigate('/chronicle')}
              />
              <main className="flex-1 overflow-hidden">
                <ChronicleCreator />
              </main>
            </div>
          }
        />
        <Route
          path="/chronicle/discover"
          element={
            <div className="flex h-screen">
              <Sidebar
                activeView="Chronicle"
                onViewChange={() => {}}
                onCreateClick={() => navigate('/chronicle')}
              />
              <main className="flex-1 overflow-hidden">
                <ChronicleSelector />
              </main>
            </div>
          }
        />
        <Route
          path="/chronicle/list"
          element={
            <div className="flex h-screen">
              <Sidebar
                activeView="Chronicle"
                onViewChange={() => {}}
                onCreateClick={() => navigate('/chronicle')}
              />
              <main className="flex-1 overflow-hidden">
                <ChronicleSelector />
              </main>
            </div>
          }
        />
        <Route
          path="/chronicle/:chronicleId"
          element={
            <div className="flex h-screen">
              <Sidebar activeView="Chronicle" onViewChange={() => {}} onCreateClick={() => navigate('/chronicle')} />
              <main className="flex-1 overflow-hidden">
                <ChronicleDetail />
              </main>
            </div>
          }
        />
      </Routes>
    </div>
  );
}

// keep existing exports

function App() {
  return (
    <BrowserRouter>
      <AppContent />
    </BrowserRouter>
  );
}

export default App;