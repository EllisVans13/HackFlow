import React,{useId} from 'react';

// Stable placement avoids particles jumping whenever the interface updates.
export const flakes = Array.from({ length: 40 }, (_, i) => {
  const duration = 16 + (i * 7) % 19;
  return {
    left: `${(i * 61.8034 + 3) % 100}%`,
    size: `${i % 5 === 0 ? 11 + i % 4 : 2 + i % 4}px`,
    duration: `${duration}s`,
    delay: `${-((i * 11.37 + 4) % duration)}s`,
    opacity: (0.24 + (i % 6) * 0.045).toFixed(2),
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
      {flake.crystal && <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.3" strokeLinecap="round" aria-hidden="true">
        <path d="M12 2v20M3.34 7l17.32 10M3.34 17L20.66 7M9 5l3 3 3-3M9 19l3-3 3 3M4.5 10.5l4.1-1.1-1.1-4.1M19.5 13.5l-4.1 1.1 1.1 4.1M7.5 18.7l1.1-4.1-4.1-1.1M16.5 5.3l-1.1 4.1 4.1 1.1"/>
      </svg>}
    </span></span>)}
  </div>;
}

export function WinterGarland({ enabled = false }) {
  const id='garland-'+useId().replace(/[^a-zA-Z0-9_-]/g,'');
  if (!enabled) return null;
  return <div className="winter-garland" aria-hidden="true"><svg viewBox="0 0 1000 62" preserveAspectRatio="xMidYMin slice" fill="none">
    <defs><radialGradient id={id+'-gold'} cx=".3" cy=".25"><stop stopColor="#fff7dd"/><stop offset=".5" stopColor="#f1d395"/><stop offset="1" stopColor="#c59551"/></radialGradient><radialGradient id={id+'-red'} cx=".3" cy=".25"><stop stopColor="#f1b0a2"/><stop offset=".5" stopColor="#c86f69"/><stop offset="1" stopColor="#9c4651"/></radialGradient></defs>
    <path d="M-20 5Q100 25 210 8T430 8T650 8T870 8T1090 8" stroke="#426b57" strokeWidth="5" strokeLinecap="round"/>
    {Array.from({length:40},(_,i)=><g key={i} transform={`translate(${i*26},${9+Math.sin(i*.73)*5}) rotate(${i%2?12:-12})`} strokeLinecap="round"><path d="M-9-4 3 7 11-4M-11 1 1 10 12 1" stroke={i%3===0?'#8da98d':'#61846c'} strokeWidth="2"/><path d="m-8-5 8 8 8-8" stroke="#e8e6d2" strokeOpacity=".48"/></g>)}
    {Array.from({length:13},(_,i)=><g key={i} transform={`translate(${26+i*79},${13+Math.sin(i*.8)*4})`}>
      <path d={'M0 0v'+(i%3===0?16:10)} stroke="#dac79e" strokeWidth="1"/>
      {i%3===0?<><path d="M-3 15h6v3h-6z" fill="#e6c78a"/><circle cy="25" r="7" fill={'url(#'+id+(i%2?'-gold)': '-red)')}/><path d="M-3 21q-3 3-1 6" stroke="#fff4d7" strokeWidth="1" strokeLinecap="round" opacity=".6"/></>:<><ellipse cy="15" rx="3" ry="4.5" className={i%2?'garland-gold':'garland-berry'}/><path d="M-2 9h4v3h-4z" fill="#cdb489"/></>}
    </g>)}
    {[145,382,619,856].map(x=><path key={x} d={`M${x} 21v7m-4-3 8 0m-7-3 6 6m-6 0 6-6`} stroke="#f4ddb0" strokeWidth="1" strokeLinecap="round" opacity=".8"/>)}
  </svg></div>;
}

export function HolidayHat({enabled=false}){
 if(!enabled)return null;
 return <svg className="holiday-brand-hat" viewBox="0 0 48 38" aria-hidden="true" focusable="false"><path d="M8 27Q17 1 36 7q7 2 5 15l-8-5-6 13Z" fill="#c05b61"/><path d="M8 27Q15 10 27 7q-6 9-7 22Z" fill="#a3414d"/><path d="M6 26q12-4 25 2l-1 7q-14-4-26-2Z" fill="#fff5e2"/><path d="M8 28q12-3 19 1" stroke="#e7d6bb" strokeWidth="1.5" fill="none"/><circle cx="41" cy="24" r="6" fill="#fff5e2"/></svg>;
}

export function HolidayScene({enabled=false}){
 const id='holiday-scene-'+useId().replace(/[^a-zA-Z0-9_-]/g,'');
 if(!enabled)return null;
 return <svg className="holiday-home-scene" viewBox="0 0 240 220" aria-hidden="true" focusable="false"><defs><linearGradient id={id} x1="0" y1="0" x2="1" y2="1"><stop stopColor="#718b6b"/><stop offset="1" stopColor="#365e4c"/></linearGradient></defs>
  <ellipse cx="127" cy="198" rx="94" ry="13" fill="#baa181" opacity=".16"/><path d="M42 192q30-17 70-6 56-21 95 9-77 18-165-3Z" fill="#fffdf7"/>
  <path d="M126 176v23" stroke="#8d6650" strokeWidth="9" strokeLinecap="round"/><path d="m126 30-35 66h16l-32 51h20l-32 38q64 23 127 0l-33-38h20l-31-51h15Z" fill={'url(#'+id+')'} stroke="#3c6351" strokeWidth="1.5" strokeLinejoin="round"/>
  <path d="m126 30-24 44m-10 42-12 23m77 20 21 21" stroke="#f5f1df" strokeWidth="5" strokeLinecap="round"/>
  <path d="m99 90q30 20 58 6m-69 44q45 26 83 9m-93 27q51 20 101 6" stroke="#dbba7d" strokeWidth="1.5" fill="none"/>
  <path d="m126 15 4 9 10 1-8 7 2 10-8-5-9 5 2-10-8-7 11-1Z" fill="#d9b36d" stroke="#f0d8a2" strokeWidth="1.3"/>
  {[[111,99],[145,119],[102,148],[157,166],[126,175]].map(([x,y],i)=><g key={x}><circle cx={x} cy={y} r={i%2?4:5} fill={i%2?'#e2c58e':'#b5575d'}/><circle cx={x-1} cy={y-1} r="1.2" fill="#fff1d6" opacity=".7"/></g>)}
  <g transform="rotate(-5 61 184)"><rect x="32" y="161" width="53" height="38" rx="3" fill="#ae505d"/><path d="M57 161v38M32 174h53" stroke="#efd7a3" strokeWidth="6"/><path d="M58 161q-23-2-17-12 9-8 17 12 4-23 14-16 10 10-14 16" stroke="#d8b376" strokeWidth="2.5" fill="none"/></g>
  <g transform="rotate(5 184 187)"><rect x="165" y="170" width="44" height="31" rx="3" fill="#e1c89b"/><path d="M187 170v31M165 180h44" stroke="#a34c57" strokeWidth="5"/><path d="M187 170q-20-2-15-10 10-5 15 10 5-19 12-12 6 8-12 12" stroke="#a34c57" strokeWidth="2" fill="none"/></g>
  <path d="M49 98v12m-6-6h12m137-33v10m-5-5h10M68 44v8m-4-4h8" stroke="#c8ad7a" strokeWidth="1.7" strokeLinecap="round"/><circle cx="179" cy="126" r="2" fill="#b5575d"/><circle cx="61" cy="133" r="2" fill="#d8bd82"/>
 </svg>;
}
