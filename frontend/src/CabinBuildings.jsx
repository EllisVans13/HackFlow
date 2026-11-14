import React from 'react';

export function CabinBuilding({team,small=false}){
 const stage=team.stage||'plot',tree=team.style==='treehouse';
 const level=stage==='submitted'?5:Math.max(1,Math.min(5,team.floors||1));
 const light=stage==='submitted'?'var(--city-light)':'var(--city-window)';
 return <svg className={'city-building cabin-building '+(small?'small':'')} viewBox="0 0 220 245" aria-hidden="true" focusable="false">
  <ellipse cx="110" cy="217" rx="87" ry="16" fill="#000" opacity=".12"/>
  <path d="M12 202 110 167 208 202 110 238Z" fill="var(--city-ground)"/>
  <path d="m12 202 98 36 98-36v6l-98 35-98-35z" fill="var(--city-ground-edge)"/>
  <path d="m30 202 80-28 80 28-80 29z" stroke="var(--city-path)" strokeWidth="2" strokeDasharray={stage==='plot'?'4 5':undefined} fill="none"/>
  {stage==='plot'?<g><path d="M90 202v-38m0 3h43v26H90" stroke="var(--city-wood)" strokeWidth="3" fill="var(--city-roof)"/><path d={tree?'M104 186v-11m-6 6 6-7 6 7':'m101 185 10-13 10 13z'} stroke="var(--city-light)" strokeWidth="2" fill="none"/></g>:stage==='foundation'?<g><path d="m51 181 59-23 60 23v13l-60 24-59-24z" fill="var(--city-side)"/><path d="m51 181 59-23 60 23-60 24z" fill="var(--city-roof)"/><path d={tree?'M108 190V93m0 44-29-28m29 12 26-30':'M55 181l50-94 54 96M70 190l49-94 48 87'} stroke="var(--city-wood)" strokeWidth={tree?10:3} strokeLinecap="round" fill="none"/></g>:tree?<g>
   <path d="M104 215c-7-43 12-62 3-117m2 36L75 86m34 27 33-42m-34 49L96 56" stroke="#84644b" strokeWidth="14" strokeLinecap="round" fill="none"/>
   <g fill="var(--city-tree)"><circle cx="61" cy="72" r="30"/><circle cx="96" cy="52" r="32"/><circle cx="139" cy="52" r="31"/><circle cx="166" cy="77" r="28"/><circle cx="109" cy="80" r="42"/></g>
   <path d="M33 63q12-25 35-18m8-17q23-19 48-3m15 0q25-4 34 18m-97 24q27-18 49-3m20-13q20-5 35 10" className="city-tree-snow"/>
   <path d="m42 164 68-25 69 25-69 27z" fill="var(--city-front)" stroke="var(--city-wood)" strokeWidth="2"/>
   <path d="m42 164 68 27 69-27v8l-69 27-68-27z" fill="var(--city-side)"/>
   {level>=2?<><path d="m70 117 54 16v43l-54-17z" fill="var(--city-front)"/><path d="m124 133 36-18v42l-36 19z" fill="var(--city-side)"/><path d="m66 117 40-37 23 52z" fill="var(--city-roof)"/><path d="m106 80 34-14 24 49-35 17z" fill="var(--city-roof)" stroke="var(--city-wood)" strokeWidth="2"/><path d="m66 117 40-37 34-14 24 49" className="city-roof-snow"/>
    <path d="m80 132 16 5v19l-16-5z" fill={level>=3?light:'var(--city-wood)'}/><path d="m136 139 15-7v19l-15 7z" fill={level>=3?light:'var(--city-wood)'}/><path d="M88 135v18m-8-11 16 5m48-12v20m-8-10 15-7" stroke="var(--city-wood)" strokeWidth="1.5"/>
    <path d="m104 141 13 4v28l-13-4z" fill="var(--city-door)"/></>:<path d="M71 155v-39l35-36 52 36v41m-87-41 53 17 34-17m-34 17v44" stroke="var(--city-wood)" strokeWidth="3" fill="none"/>}
   <path d="m71 184-32 28m9-24 23 9m-30-2 22 9m-31-2 22 9m-31-2 22 9" stroke="var(--city-wood)" strokeWidth="4" strokeLinecap="round"/>
   {level>=4&&<><path d="m151 177 35 14 17-6m-52-18 35 14 17-6m-44-5v12m13-7v12m14-6v12m10-17v12" stroke="var(--city-wood)" strokeWidth="2.5" fill="none"/><path d="M49 157v16m13-11v16m13-11v16m13-11v16m14-11v16M49 157l55 21" stroke="var(--city-wood)" strokeWidth="2" fill="none"/></>}
   {level>=5&&<g><path d="m51 155q25 22 51 21" stroke="var(--city-wood)" fill="none"/>{[57,69,81,93].map((x,i)=><circle key={x} cx={x} cy={161+i*4} r="1.8" fill={light}/>)}</g>}
  </g>:<g transform={`translate(${110*(1-(.8+level*.04))} ${202*(1-(.8+level*.04))}) scale(${.8+level*.04})`}>
   <path d="m51 188 102 0 22 13-102 0z" fill="var(--city-front)"/><path d="m73 201 102 0v6H73z" fill="var(--city-side)"/>
   {level>=2&&<><path d="m103 69 42-21 54 122-46 20z" fill="var(--city-roof)"/><path d="m53 190 50-121 50 121z" fill="var(--city-front)"/>
    <path d="m103 91-37 87h74z" fill={level>=3?light:'var(--city-side)'} opacity={level>=3 ? .85 : 1}/>
    <path d="M103 92v87m-21-38 42 0m-52 25h62" stroke="var(--city-wood)" strokeWidth="3"/>
    <path d="M103 151h17v37h-17z" stroke="var(--city-wood)" strokeWidth="2" fill="var(--city-door)"/>
    <path d="m53 190 50-121 50 121" stroke="var(--city-wood)" strokeWidth="6" fill="none" strokeLinejoin="round"/><path d="m53 190 50-121 42-21 54 122" className="city-roof-snow"/></>}
   {level===1&&<path d="m53 190 50-121 50 121m-82 5 48-113 49 111M103 69l16-8m-16 90 29-9M72 147l47-65" fill="none" stroke="var(--city-wood)" strokeWidth="4" strokeLinejoin="round"/>}
   {level>=4&&<><path d="M91 208h49v5H91m-6 1h49v5H85m-6 1h49v5H79" stroke="var(--city-wood)" strokeWidth="4"/><path d="M56 189v-13m13 13v-13m-13 0h13m86 15v-16m14 21v-16m-14-5 14 5" stroke="var(--city-wood)" strokeWidth="2"/></>}
   {level>=5&&<><path d="M71 126V87l13-5v35" fill="#8d8876" stroke="#625e51" strokeWidth="2"/><path d="m69 87 15-6 4 5-15 6z" fill="#c9c3b1"/><g stroke="var(--city-wood)" strokeWidth="4" strokeLinecap="round"><path d="m43 201 12 4m-12-10 12 4m-12-10 12 4"/></g></>}
  </g>}
  <path d="M190 207v-29m-5 0h10" stroke="var(--city-wood)" strokeWidth="2"/><path d="m186 171 4-4 4 4v8h-8z" fill={light}/>
  {stage==='submitted'&&<g className="cabin-complete"><path d="M202 175v-35" stroke="var(--city-wood)" strokeWidth="2"/><path d="M202 140h15l-3 7 3 7h-15z" fill="var(--city-light)"/><path d="m205 148 3 2 5-6" stroke="var(--city-door)" strokeWidth="1.5" fill="none"/></g>}
 </svg>;
}
