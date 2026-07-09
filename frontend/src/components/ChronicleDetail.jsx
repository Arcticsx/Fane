import React from 'react';
import { useNavigate } from 'react-router-dom';
import ChronicleChat from './ChronicleChat';

export default function ChronicleDetail({ chronicleId: propId }) {
  const navigate = useNavigate();
  const id = propId || (() => {
    const p = window.location.pathname.split('/');
    return decodeURIComponent(p[p.length - 1]);
  })();

  return (
    <div className="flex h-screen">
      <div className="flex-1 overflow-hidden">
        <ChronicleChat chronicleId={id} onBack={() => navigate('/chronicle/discover')} />
      </div>
    </div>
  );
}
