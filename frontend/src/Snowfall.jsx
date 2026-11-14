import React from 'react';

// Stable placement avoids particles jumping whenever the interface updates.
export const flakes = Array.from({ length: 40 }, (_, i) => {
  const duration = 16 + (i * 7) % 19;
  return {
    left: `${(i * 61.8034 + 3) % 100}%`,
    size: `${i % 5 === 0 ? 11 + i % 4 : 2 + i % 4}px`,
    duration: `${duration}s`,
    delay: `${-((i * 11.37 + 4) % duration)}s`,
    opacity: (0.16 + (i % 6) * 0.045).toFixed(2),
    drift: `${(i % 2 ? -1 : 1) * (18 + i % 53)}px`,
    sway: `${3 + i % 9}px`,
    swayTime: `${3 + i % 5}s`,
    crystal: i % 5 === 0,
  };
});

export default function Snowfall({ enabled = false }) {
  if (!enabled) return null;
  return <div className="winter-snow" aria-hidden="true">
    {flakes.map((flake, i) => <span className="winter-flake" key={i} style={{
      left: flake.left,
      '--flake-size': flake.size,
      '--fall-time': flake.duration,
      '--fall-delay': flake.delay,
      '--flake-opacity': flake.opacity,
      '--flake-drift': flake.drift,
      '--flake-sway': flake.sway,
      '--sway-time': flake.swayTime,
    }}><span className={'winter-particle ' + (flake.crystal ? 'crystal' : 'powder')}>
      {flake.crystal && <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.1" strokeLinecap="round" aria-hidden="true">
        <path d="M12 2v20M3.34 7l17.32 10M3.34 17L20.66 7M9 5l3 3 3-3M9 19l3-3 3 3M4.5 10.5l4.1-1.1-1.1-4.1M19.5 13.5l-4.1 1.1 1.1 4.1M7.5 18.7l1.1-4.1-4.1-1.1M16.5 5.3l-1.1 4.1 4.1 1.1"/>
      </svg>}
    </span></span>)}
  </div>;
}
