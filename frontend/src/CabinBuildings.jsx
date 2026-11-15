import React from 'react';
import {BuildingScene} from './BuildingScene.jsx';

export function CabinBuilding({team,small=false}){
 const tree=team.style==='treehouse';
 const level=team.stage==='submitted'?5:Math.max(1,Math.min(5,team.floors||1));
 return <BuildingScene team={team} small={small} cabin>{paint=>tree?<g>
   <path d="M104 215c-7-43 12-62 3-117m2 36L75 86m34 27 33-42m-34 49L96 56" stroke="#84644b" strokeWidth="14" strokeLinecap="round" fill="none"/>
   <g fill={paint('leaves')}><circle cx="61" cy="72" r="30"/><circle cx="96" cy="52" r="32"/><circle cx="139" cy="52" r="31"/><circle cx="166" cy="77" r="28"/><circle cx="109" cy="80" r="42"/></g><path d="M42 65q10-21 28-15m17-20q20-12 39 1m21 10q16 1 23 15M68 81q18 11 36 1" fill="none" stroke="#dfe6c7" strokeWidth="4" strokeLinecap="round" opacity=".18"/><g fill="#c4d5a9" opacity=".3"><ellipse cx="62" cy="62" rx="5" ry="2" transform="rotate(-25 62 62)"/><ellipse cx="149" cy="61" rx="5" ry="2" transform="rotate(25 149 61)"/></g>
   <path d="M33 63q12-25 35-18m8-17q23-19 48-3m15 0q25-4 34 18m-97 24q27-18 49-3m20-13q20-5 35 10" className="city-tree-snow"/>
   <path d="m42 164 68-25 69 25-69 27z" fill={paint('front')} stroke="var(--city-wood)" strokeWidth="2"/>
   <path d="m42 164 68 27 69-27v8l-69 27-68-27z" fill={paint('side')}/>
   {level>=2?<><path d="m70 117 54 16v43l-54-17z" fill={paint('front')}/><path d="m124 133 36-18v42l-36 19z" fill={paint('side')}/><path d="m66 117 40-37 23 52z" fill={paint('roof')}/><path d="m106 80 34-14 24 49-35 17z" fill={paint('roof')} stroke="var(--city-wood)" strokeWidth="2"/><path d="m66 117 40-37 34-14 24 49" className="city-roof-snow"/>
    <path d="m80 132 16 5v19l-16-5z" fill={level>=3?paint('glass'):'var(--city-wood)'}/><path d="m136 139 15-7v19l-15 7z" fill={level>=3?paint('glass'):'var(--city-wood)'}/><path d="M88 135v18m-8-11 16 5m48-12v20m-8-10 15-7" stroke="var(--city-wood)" strokeWidth="1.5"/>
    <path d="m104 141 13 4v28l-13-4z" fill="var(--city-door)"/></>:<path d="M71 155v-39l35-36 52 36v41m-87-41 53 17 34-17m-34 17v44" stroke="var(--city-wood)" strokeWidth="3" fill="none"/>}
   <path d="m71 184-32 28m9-24 23 9m-30-2 22 9m-31-2 22 9m-31-2 22 9" stroke="var(--city-wood)" strokeWidth="4" strokeLinecap="round"/>
   {level>=4&&<><path d="m151 177 35 14 17-6m-52-18 35 14 17-6m-44-5v12m13-7v12m14-6v12m10-17v12" stroke="var(--city-wood)" strokeWidth="2.5" fill="none"/><path d="M49 157v16m13-11v16m13-11v16m13-11v16m14-11v16M49 157l55 21" stroke="var(--city-wood)" strokeWidth="2" fill="none"/></>}
   {level>=5&&<g><path d="m51 155q25 22 51 21" stroke="var(--city-wood)" fill="none"/>{[57,69,81,93].map((x,i)=><circle key={x} cx={x} cy={161+i*4} r="1.8" fill={paint('glass')}/>)}</g>}
  </g>:<g transform={`translate(${110*(1-(.8+level*.04))} ${202*(1-(.8+level*.04))}) scale(${.8+level*.04})`}>
   <path d="m51 188 102 0 22 13-102 0z" fill={paint('front')}/><path d="m73 201 102 0v6H73z" fill={paint('side')}/>
   {level>=2&&<><path d="m103 69 42-21 54 122-46 20z" fill={paint('roof')}/><path d="m103 69 42-21 54 122-46 20z" fill={paint('seams')}/>{level>=3&&<g><path d="m130 88 18-8 22 49-19 9z" fill={paint('glass')} stroke="var(--city-wood)" strokeWidth="2"/><path d="m139 84 22 49m-22-22 19-9" stroke="var(--city-roof)" strokeWidth="1.4"/><path d="m132 91 3-1 18 41-3 1z" fill="#fff" opacity=".3"/></g>}<path d="m53 190 50-121 50 121z" fill={paint('front')}/><path d="m53 190 50-121 50 121z" fill={paint('siding')}/>
    <path d="m103 91-37 87h74z" fill={level>=3?paint('glass'):'var(--city-side)'} opacity={level>=3 ? .85 : 1}/>
    <path d="M103 92v87m-21-38 42 0m-52 25h62" stroke="var(--city-wood)" strokeWidth="3"/>
    <path d="M103 151h17v37h-17z" stroke="var(--city-wood)" strokeWidth="2" fill="var(--city-door)"/>
    <path d="m53 190 50-121 50 121" stroke="var(--city-wood)" strokeWidth="6" fill="none" strokeLinejoin="round"/><path d="m53 190 50-121 42-21 54 122" className="city-roof-snow"/></>}
   {level===1&&<path d="m53 190 50-121 50 121m-82 5 48-113 49 111M103 69l16-8m-16 90 29-9M72 147l47-65" fill="none" stroke="var(--city-wood)" strokeWidth="4" strokeLinejoin="round"/>}
   {level>=4&&<><path d="M91 208h49v5H91m-6 1h49v5H85m-6 1h49v5H79" stroke="var(--city-wood)" strokeWidth="4"/><path d="M56 189v-13m13 13v-13m-13 0h13m86 15v-16m14 21v-16m-14-5 14 5" stroke="var(--city-wood)" strokeWidth="2"/></>}
   {level>=5&&<><path d="M71 126V87l13-5v35" fill="#8d8876" stroke="#625e51" strokeWidth="2"/><path d="m69 87 15-6 4 5-15 6z" fill="#c9c3b1"/><g stroke="var(--city-wood)" strokeWidth="4" strokeLinecap="round"><path d="m43 201 12 4m-12-10 12 4m-12-10 12 4"/></g></>}
  </g>}</BuildingScene>;
}
