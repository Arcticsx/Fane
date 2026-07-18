import React, { useState, useEffect, useCallback } from 'react';
import { useLocation, useNavigate, useParams } from 'react-router-dom';
import { api, getImageUrl } from '../api';

function Sidebar({ activeView, onViewChange, onCreateClick }) {
  const [width, setWidth] = useState(224);
  const [recentItems, setRecentItems] = useState([]);
  const [loading, setLoading] = useState(true);

  const navigate = useNavigate();
  const location = useLocation();
  const { sessionId: activeSessionId, chronicleId: activeChronicleId } = useParams();
  const isChronicleRoute = location.pathname.startsWith('/chronicle');

  useEffect(() => {
    let cancelled = false;

    const fetchItems = async () => {
      setLoading(true);

      try {
        if (isChronicleRoute) {
          const chronicles = await api.getRecentChronicles();
          if (!cancelled) {
            setRecentItems((chronicles || []).slice(0, 6));
          }
        } else {
          const data = await api.getRecentSessions();
          if (!cancelled) {
            setRecentItems((data.sessions || []).slice(0, 6));
          }
        }
      } catch (err) {
        console.error('Failed to load recent items', err);
        if (!cancelled) {
          setRecentItems([]);
        }
      } finally {
        if (!cancelled) {
          setLoading(false);
        }
      }
    };

    fetchItems();

    const interval = setInterval(fetchItems, 30000);

    return () => {
      cancelled = true;
      clearInterval(interval);
    };
  }, [isChronicleRoute]);

  const formatDate = (dateStr) => {
    const date = new Date(dateStr);
    const now = new Date();

    const diffDays = Math.floor(
      (now - date) / (1000 * 60 * 60 * 24)
    );

    if (diffDays === 0) return 'Today';
    if (diffDays === 1) return 'Yesterday';

    return date.toLocaleDateString(undefined, {
      month: 'short',
      day: 'numeric',
    });
  };

  const handleMouseDown = useCallback(
    (e) => {
      e.preventDefault();

      const startX = e.clientX;
      const startWidth = width;

      const onMouseMove = (e) => {
        const newWidth = Math.min(
          400,
          Math.max(
            160,
            startWidth + e.clientX - startX
          )
        );

        setWidth(newWidth);
      };

      const onMouseUp = () => {
        document.removeEventListener(
          'mousemove',
          onMouseMove
        );

        document.removeEventListener(
          'mouseup',
          onMouseUp
        );
      };

      document.addEventListener(
        'mousemove',
        onMouseMove
      );

      document.addEventListener(
        'mouseup',
        onMouseUp
      );
    },
    [width]
  );

  const resolvedActiveView = activeView || (location.pathname.startsWith('/chronicle') ? 'Chronicle' : location.pathname.startsWith('/sessions') ? 'create' : 'discover');

  const handleNav = (itemKey) => {
    const currentState = location.state || {};

    if (itemKey === 'create') {
      if (location.pathname.startsWith('/chronicle')) {
        navigate('/chronicle', { state: currentState });
      } else if (typeof onCreateClick === 'function') {
        onCreateClick();
      } else {
        navigate('/', { state: currentState });
      }
      return;
    }

    if (itemKey === 'discover') {
      navigate('/', { state: currentState });
      return;
    }

    if (itemKey === 'Chronicle') {
      navigate('/chronicle/discover', { state: currentState });
      return;
    }

    if (typeof onViewChange === 'function') {
      onViewChange(itemKey);
    }
  };

  const items = [
    {
      key: 'create',
      label: 'Create',
      icon: (
        <span className="material-symbols-outlined">
          add
        </span>
      ),
    },
    {
      key: 'discover',
      label: 'Discover',
      icon: (
        <span className="material-symbols-outlined">
          explore
        </span>
      ),
    },
    {
      key: 'Chronicle',
      label: 'Chronicle',
      icon: (
        <span className="material-symbols-outlined">
          cruelty_free
        </span>
      ),
    },
    
  ];

  return (
    <aside
      style={{ width: `${width}px` }}
      className="relative flex shrink-0 flex-col border-r border-border/70 bg-surface/80 px-0 py-5 backdrop-blur-xl"
    >
      {/* Logo */}
      <div
        onClick={() => navigate('/', { state: location.state || {} })}
        className="px-6 pb-6 cursor-pointer transition-opacity duration-300 hover:opacity-70"
        role="button"
        tabIndex={0}
        onKeyDown={(e) =>
          e.key === 'Enter' && navigate('/', { state: location.state || {} })
        }
      >
        <div className="absolute inset-0 -z-10 opacity-0 group-hover:opacity-100 transition-opacity duration-500">
          <div className="absolute inset-0 bg-accent/20 blur-2xl rounded-full"></div>
        </div>
        <div className="relative inline-block">
          <span className="text-3xl font-bold tracking-tight text-text/90 hover:text-text transition-colors duration-300">
            fane.
          </span>
        </div>
      </div>

      {/* Navigation */}
      <nav className="flex flex-col gap-2 px-3">
        {items.map((item) => {
          const isActive =
            resolvedActiveView === item.key;

          return (
            <button
              key={item.key}
              onClick={() => handleNav(item.key)}
              className={`relative flex items-center gap-3 rounded-xl px-3 py-2.5 text-left text-sm font-medium transition-all duration-200 ${
                isActive
                  ? 'bg-accent/10 text-accent shadow-[inset_0_1px_0_rgba(255,255,255,0.1)]'
                  : 'text-muted hover:bg-surface/80 hover:text-text'
              }`}
            >
              {isActive && (
                <div className="absolute left-0 top-1/2 -translate-y-1/2 h-6 w-0.5 bg-accent rounded-r-full shadow-[0_0_10px_rgba(99,102,241,0.5)]" />
              )}

              <span
                className={`flex h-5 w-5 items-center justify-center transition-transform duration-200 ${
                  isActive
                    ? 'scale-110'
                    : ''
                }`}
              >
                {item.icon}
              </span>

              <span>{item.label}</span>
            </button>
          );
        })}
      </nav>

      {/* Recent Items */}
      <div className="mt-6 flex flex-col gap-1 px-3 overflow-y-auto flex-1">
        <p className="px-3 py-1 text-xs font-semibold uppercase tracking-widest text-muted/60">
          {isChronicleRoute ? 'Recent Chronicles' : 'Recent'}
        </p>

        {loading ? (
          <p className="px-3 text-xs text-muted/50">
            Loading...
          </p>
        ) : recentItems.length === 0 ? (
          <p className="px-3 text-xs text-muted/50">
            {isChronicleRoute ? 'No recent chronicles.' : 'No recent sessions.'}
          </p>
        ) : (
          recentItems.map((item) => {
            const isActive = isChronicleRoute
              ? activeChronicleId === String(item.id)
              : activeSessionId === String(item.id);

            if (isChronicleRoute) {
              return (
                <button
                  key={item.id}
                  onClick={() => navigate(`/chronicle/${encodeURIComponent(item.id)}`)}
                  className={`relative flex items-center gap-2.5 rounded-xl px-3 py-2.5 text-left transition-all duration-200 ${
                    isActive
                      ? 'bg-accent/10 shadow-[inset_0_1px_0_rgba(255,255,255,0.1)]'
                      : 'hover:bg-surface/80'
                  }`}
                >
                  {isActive && (
                    <div className="absolute left-0 top-1/2 -translate-y-1/2 h-6 w-0.5 bg-accent rounded-r-full shadow-[0_0_10px_rgba(99,102,241,0.5)]" />
                  )}

                  <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-gradient-to-br from-accent2 to-accent text-sm font-semibold text-text">
                    {(item.title || 'C').charAt(0).toUpperCase()}
                  </div>

                  <div className="flex min-w-0 flex-1 flex-col gap-0.5">
                    <div className="flex items-center justify-between gap-2">
                      <span className="truncate text-sm font-medium text-text">
                        {item.title || 'Untitled Chronicle'}
                      </span>

                      <span className="shrink-0 text-xs text-muted/50">
                        {formatDate(item.created_at || item.updated_at)}
                      </span>
                    </div>

                    <span className="truncate text-xs text-muted/60">
                      {item.synopsis || item.setup_status || 'No description yet'}
                    </span>
                  </div>
                </button>
              );
            }

            return (
              <button
                key={item.id}
                onClick={() =>
                  navigate(
                    `/chat/${item.persona_key}/${item.id}`,
                    {
                      state: {
                        persona: {
                          key: item.persona_key,
                          name: item.persona_name,
                          avatar: item.persona_avatar,
                        },
                        session: item,
                      },
                    }
                  )
                }
                className={`relative flex items-center gap-2.5 rounded-xl px-3 py-2.5 text-left transition-all duration-200 ${
                  isActive
                    ? 'bg-accent/10 shadow-[inset_0_1px_0_rgba(255,255,255,0.1)]'
                    : 'hover:bg-surface/80'
                }`}
              >
                {isActive && (
                  <div className="absolute left-0 top-1/2 -translate-y-1/2 h-6 w-0.5 bg-accent rounded-r-full shadow-[0_0_10px_rgba(99,102,241,0.5)]" />
                )}

                <div className="h-8 w-8 shrink-0 overflow-hidden rounded-full bg-gradient-to-br from-accent2 to-accent">
                  {item.persona_avatar ? (
                    <img
                      src={getImageUrl(item.persona_avatar)}
                      alt={item.persona_name}
                      className="h-full w-full object-cover"
                    />
                  ) : (
                    <div className="flex h-full w-full items-center justify-center text-sm font-semibold text-text">
                      {item.persona_name?.charAt(0)}
                    </div>
                  )}
                </div>

                <div className="flex min-w-0 flex-1 flex-col gap-0.5">
                  <div className="flex items-center justify-between gap-2">
                    <span className="truncate text-sm font-medium text-text">
                      {item.persona_name}
                    </span>

                    <span className="shrink-0 text-xs text-muted/50">
                      {formatDate(item.updated_at)}
                    </span>
                  </div>

                  <span className="truncate text-xs text-muted/60">
                    {item.last_user_message ?? 'No messages yet'}
                  </span>
                </div>
              </button>
            );
          })
        )}
      </div>

      {/* Drag handle */}
      <div
        onMouseDown={handleMouseDown}
        className="absolute right-0 top-0 h-full w-1 cursor-col-resize group"
      >
        <div className="absolute inset-0 bg-transparent group-hover:bg-accent/30 transition-colors duration-300" />

        <div className="absolute inset-y-0 -left-1 w-3 bg-transparent" />

        <div className="absolute top-1/2 -translate-y-1/2 right-[-2px] flex flex-col gap-1 opacity-0 group-hover:opacity-100 transition-opacity duration-300">
          <div className="w-1 h-1 rounded-full bg-accent/60" />
          <div className="w-1 h-1 rounded-full bg-accent/60" />
          <div className="w-1 h-1 rounded-full bg-accent/60" />
        </div>
      </div>
    </aside>
  );
}

export default Sidebar;