import React,{useId} from 'react';

// Shared diorama and local paint IDs keep every preview independent.
export function BuildingScene({team,small=false,cabin=false,children}){
 const id='city-'+useId().replace(/[^a-zA-Z0-9_-]/g,'');
 const paint=name=>`url(#${id}-${name})`;
 const stage=team.stage||'plot',finished=stage==='submitted';
 return <svg className={'city-building '+(cabin?'cabin-building ':'')+(small?'small':'')} viewBox="0 0 220 245" aria-hidden="true" focusable="false">
  <defs>
   <linearGradient id={id+'-ground'} x1="0" y1="0" x2="1" y2="1"><stop stopColor="var(--city-ground)"/><stop offset="1" stopColor="var(--city-ground-edge)"/></linearGradient>
   <linearGradient id={id+'-front'} x1="0" y1="0" x2="1" y2="1"><stop stopColor="color-mix(in srgb,var(--city-front) 78%,white)"/><stop offset="1" stopColor="var(--city-front)"/></linearGradient>
   <linearGradient id={id+'-side'} x1="0" y1="0" x2="1" y2="1"><stop stopColor="var(--city-side)"/><stop offset="1" stopColor="color-mix(in srgb,var(--city-side) 76%,#263b3c)"/></linearGradient>
   <linearGradient id={id+'-roof'} x1="0" y1="0" x2="1" y2="1"><stop stopColor="color-mix(in srgb,var(--city-roof) 72%,#a7c6c3)"/><stop offset="1" stopColor="var(--city-roof)"/></linearGradient>
   <linearGradient id={id+'-glass'} x1="0" y1="0" x2="1" y2="1"><stop stopColor={finished?'#fff2c6':'#deebdf'}/><stop offset=".52" stopColor={finished?'var(--city-light)':'#b5ced0'}/><stop offset="1" stopColor={finished?'#d5a976':'#779a9e'}/></linearGradient>
   <linearGradient id={id+'-leaves'} x1="0" y1="0" x2="1" y2="1"><stop stopColor="#a4c391"/><stop offset=".45" stopColor="var(--city-tree)"/><stop offset="1" stopColor="#355f50"/></linearGradient>
   <radialGradient id={id+'-glow'}><stop stopColor="var(--city-light)" stopOpacity=".42"/><stop offset="1" stopColor="var(--city-light)" stopOpacity="0"/></radialGradient>
   <pattern id={id+'-siding'} width="8" height="8" patternUnits="userSpaceOnUse"><path d="M0 7.5h8" stroke="#38443a" strokeOpacity=".13" strokeWidth=".8"/></pattern>
   <pattern id={id+'-seams'} width="13" height="13" patternUnits="userSpaceOnUse" patternTransform="rotate(-23)"><path d="M.5 0v13" stroke="#e5ede0" strokeOpacity=".18" strokeWidth="1"/></pattern>
  </defs>
  <ellipse cx="112" cy="221" rx="86" ry="13" fill="#152920" opacity=".08"/>
  <ellipse cx="112" cy="219" rx="70" ry="8" fill="#152920" opacity=".07"/>
  <path d="m13 199 97 36 97-36v8l-97 36-97-36z" fill="var(--city-ground-edge)"/>
  <path d="m110 235 97-36v8l-97 36z" fill="#1d3935" opacity=".18"/>
  <path d="M13 199 110 163 207 199 110 235Z" fill={paint('ground')} stroke="var(--city-ground)" strokeWidth="1.5"/>
  <path d="m24 199 86-31 86 31-86 31z" fill="none" stroke="var(--city-path)" strokeWidth="1.4" opacity=".55" strokeDasharray={stage==='plot'?'4 5':undefined}/>
  <path d="m16 198 94-34 94 34" className="city-ground-snow"/>
  <g fill="var(--city-path)" opacity=".85"><path d="m65 217 11-4 9 3-11 4z"/><path d="m75 211 11-4 9 3-11 4z"/><path d="m85 205 11-4 9 3-11 4z"/></g>
  <ellipse cx="115" cy="193" rx="61" ry="13" fill="#1d3935" opacity=".15"/>
  <g className="city-garden-tree"><path d="M29 190v-28" stroke="var(--city-wood)" strokeWidth="3" strokeLinecap="round"/><path d="m29 139-15 31h30z" fill={paint('leaves')}/><path d="m29 152-19 33h38z" fill={paint('leaves')}/><path d="m18 167 11-28 11 28m-24 12 13-27 13 27" className="city-tree-snow"/></g>
  {stage==='plot'?<g>
   <path d="m60 188 50-19 50 19-50 19z" fill="none" stroke="var(--city-path)" strokeWidth="2" strokeDasharray="4 4"/>
   <path d="M88 195v-39m0 3h48v29H88" stroke="var(--city-wood)" strokeWidth="3" strokeLinejoin="round" fill={paint('roof')}/>
   <path d="m99 178 13-11 13 11m-21-4v10h16v-10" fill="none" stroke="#f3e6c7" strokeWidth="2" strokeLinecap="round"/>
   <path d="m144 196 18-6 10 4-18 7z" fill="var(--city-wood)"/><path d="m144 192 18-6 10 4-18 7z" fill="var(--city-path)"/>
   <path d="M60 190v-12m100 12v-12" stroke="var(--city-wood)" strokeWidth="2"/>
  </g>:stage==='foundation'?<g>
   <path d="m54 184 56-22 57 22v13l-57 23-56-23z" fill={paint('side')}/>
   <path d="m54 184 56-22 57 22-57 23z" fill={paint('front')}/>
   <path d="m66 184 44-17 45 17-45 18z" fill="var(--city-roof)" opacity=".25"/>
   <path d="M59 185v-31m51 52v-31m51 9v-31m-102 1 51-21 51 20m-51-20v41m-51-20 51 21 51-22" stroke="var(--city-wood)" strokeWidth="2.5" strokeLinecap="round" fill="none"/>
   <path d="m41 202 22-8 14 5-22 8z" fill="var(--city-path)"/><path d="m41 197 22-8 14 5-22 8z" fill="var(--city-wood)"/>
  </g>:children(paint)}
  <g className="city-garden-bed"><path d="m31 201 17-6 13 5-17 6v7l-13-5z" fill="var(--city-wood)"/><path d="m44 206 17-6v7l-17 6z" fill="var(--city-door)" opacity=".3"/><path d="M39 201q-10-12-3-15 8-1 9 13m2 2q-2-16 5-15 7 5-2 15" fill={paint('leaves')}/><circle cx="39" cy="190" r="2" fill="#e3b2a0"/><circle cx="52" cy="188" r="2" fill="#ecd5a4"/></g>
  <circle cx="188" cy="188" r="18" fill={paint('glow')}/>
  <path d="M188 207v-29m-5 0h10" stroke="var(--city-wood)" strokeWidth="2"/>
  <path d="m183 173 5-5 5 5v8h-10z" fill="var(--city-light)" stroke="var(--city-wood)" strokeWidth="1.4"/>
  <path d="M188 173v8" stroke="#fff3cc" strokeWidth="1"/>
  {finished&&<g className="city-build-finished"><path d="M201 171v-34" stroke="var(--city-wood)" strokeWidth="2"/><path d="M201 137h16l-3 7 3 8h-16z" fill="var(--city-light)"/><path d="m205 145 3 3 5-7" stroke="var(--city-door)" strokeWidth="1.7" fill="none" strokeLinecap="round"/></g>}
 </svg>;
}
