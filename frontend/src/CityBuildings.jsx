import React from 'react';
import {BuildingScene} from './BuildingScene.jsx';

export function UrbanBuilding({team,small=false}){
 const style=team.style||'workshop',floors=Math.max(1,Math.min(5,team.floors||1));
 const lab=style==='lab',tower=style==='tower',top=tower?146-floors*20:lab?130-floors*4:140-floors*6;
 const left=lab?48:tower?68:61,right=lab?173:tower?156:162;
 return <BuildingScene team={team} small={small}>{paint=><g>
  <path d={`M${left-5} 182 110 161 ${right+5} 182v9l-${right-105} 22-54-22z`} fill={paint('side')}/>
  <path d={`M${left-5} 182 110 161 ${right+5} 182 110 205z`} fill={paint('front')}/>
  <path d={`M${left} ${top} 110 ${top+22}V201l${left-110}-22z`} fill={paint('front')}/>
  <path d={`M110 ${top+22} ${right} ${top}V179l${110-right} 22z`} fill={paint('side')}/>
  {!tower&&<path d={`M${left} ${top} 110 ${top+22}V201l${left-110}-22z`} fill={paint('siding')}/>}
  {tower?<g>
   {Array.from({length:floors},(_,i)=>{const y=169-i*20;return <g key={i}>
    <path d={`M68 ${y-5} 110 ${y+15} 156 ${y-5}`} fill="none" stroke="var(--city-roof)" strokeWidth="2" opacity=".65"/>
    <path d={`m77 ${y-13} 11 5v13l-11-5zm17 8 10 5v13l-10-5zm24 4 11-5v13l-11 5zm17-8 11-5v13l-11 5z`} fill={paint('glass')} stroke="var(--city-roof)" strokeWidth="1.1"/>
    <path d={`m78 ${y-11} 8 4m33 7 8-4`} stroke="#fff" opacity=".4"/>
   </g>})}
   <path d={`M110 ${top+22}V201`} stroke="var(--city-roof)" strokeWidth="3"/>
   <path d={`M63 ${top-1} 110 ${top-21} 161 ${top-1} 110 ${top+23}z`} fill={paint('roof')}/>
   <path d={`M63 ${top-1}v7l47 23 51-23v-7l-51 24z`} fill="var(--city-roof)"/>
   <path d={`M68 ${top-2} 110 ${top-19} 156 ${top-2}`} className="city-roof-snow"/>
   {floors>=3&&<><path d={`M80 ${top-2}v-12l30-12 31 12v13m-61-13 30 13 31-13m-31 13v13`} fill="none" stroke="var(--city-wood)" strokeWidth="1.8"/><path d={`m83 ${top-14} 27-11 28 11-28 12z`} fill={paint('glass')} opacity=".85"/></>}
   {floors>=4&&<><path d={`m138 ${top+1} 10-4 8 3-10 5v6l-8-4z`} fill="var(--city-wood)"/><path d={`M146 ${top-1}v-13`} stroke="var(--city-wood)" strokeWidth="2"/><circle cx="146" cy={top-16} r="8" fill={paint('leaves')}/></>}
  </g>:lab?<g>
   <path d={`m59 ${top+13} 42 16v29l-42-17zm62 16 40-16v28l-40 17z`} fill={paint('glass')} stroke="var(--city-roof)" strokeWidth="2"/>
   <path d={`M73 ${top+18}v29m14-23v28m48-29v29m13-34v29`} stroke="var(--city-roof)" strokeWidth="2"/>
   {floors>=2?<><path d={`M44 ${top}Q108 ${top-96} 177 ${top}l-67 27z`} fill={paint('roof')} stroke="var(--city-roof)" strokeWidth="1.5"/><path d={`M110 ${top-47}Q151 ${top-43} 177 ${top}l-67 27z`} fill={paint('side')} opacity=".45"/><path d={`M52 ${top-4}Q110 ${top-83} 169 ${top-4}`} className="city-roof-snow"/>
    <path d={`M62 ${top-8}Q109 ${top-68} 157 ${top-8}l-13 7Q110 ${top-48} 76 ${top-1}Z`} fill={paint('glass')} opacity=".8"/>
    <path d={`M110 ${top-46}V${top+26}m-34-27 68 2`} stroke="var(--city-roof)" strokeWidth="2" opacity=".55"/></>:<path d={`M44 ${top}Q108 ${top-96} 177 ${top}m-67-47v74m-66-27 66 27 67-27`} stroke="var(--city-wood)" strokeWidth="2.5" fill="none"/>}
   {floors>=4&&<g><path d="m141 166 27-11 14 8-28 12z" fill="#527a85" stroke="#a4c1bd" strokeWidth="1.3"/><path d="m148 163 13 9m-4-13 13 9m-25 0 28-11" stroke="#adc7c7" strokeWidth=".8"/><path d="M154 175v9m22-17v8" stroke="var(--city-wood)" strokeWidth="2"/></g>}
  </g>:<g>
   <path d={`m73 ${top+23} 14 6v19l-14-6zm56 13 17-8v20l-17 8z`} fill={paint('glass')} stroke="var(--city-wood)" strokeWidth="2"/>
   <path d={`M80 ${top+26}v19m57-35v21`} stroke="var(--city-wood)" strokeWidth="1.4"/>
   <path d={`M56 ${top} 101 ${top-43} 112 ${top+23}z`} fill={paint('front')}/>
   <path d={`M101 ${top-43} 151 ${top-59} 167 ${top} 112 ${top+23}z`} fill={paint('roof')}/>
   <path d={`M101 ${top-43} 151 ${top-59} 167 ${top} 112 ${top+23}z`} fill={paint('seams')}/>
   <path d={`M56 ${top} 101 ${top-43} 151 ${top-59} 167 ${top}`} className="city-roof-snow"/>
   <path d={`M56 ${top} 101 ${top-43} 112 ${top+23}`} stroke="var(--city-wood)" strokeWidth="3" fill="none"/>
  </g>}
  <path d="m96 178 13 6v18l-13-6z" fill="var(--city-door)"/><path d="m99 181 7 3v10l-7-3z" fill={paint('glass')}/><circle cx="106" cy="195" r="1" fill="var(--city-light)"/>
  <path d="m83 204 25 10 17-7m-45 1 28 11 20-8" stroke="var(--city-path)" strokeWidth="3" fill="none"/>
  {floors>=4&&<><path d="m61 183 12 5v7l-12-5z" fill="var(--city-wood)"/><path d="m62 183q0-15 5-14 5 3 3 17" fill={paint('leaves')}/></>}
 </g>}</BuildingScene>;
}
