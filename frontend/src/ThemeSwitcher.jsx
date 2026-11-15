import React,{useEffect,useId,useRef,useState} from 'react';
import {Palette,ChevronDown,Check,Snowflake,LoaderCircle} from 'lucide-react';

const themes=[
 {id:'yellow',name:'Чёрно-жёлтая',caption:'Графит и тёплый жёлтый'},
 {id:'purple',name:'Фиолетовая',caption:'Светлая и спокойная'},
 {id:'holiday',name:'Новогодняя',caption:'Клюква, хвоя и огни'},
];

export function ThemeSwitcher({theme='holiday',onSelect,busy=false,snowEnabled=true,onSnowChange}){
 const [open,setOpen]=useState(false),[pending,setPending]=useState('');
 const root=useRef(null),trigger=useRef(null),choices=useRef(null),id=useId();
 const current=themes.find(t=>t.id===theme)||themes[2];
 const close=(focus=false)=>{setOpen(false);if(focus)trigger.current?.focus()};
 useEffect(()=>{
  if(!open)return;
  const outside=e=>{if(!root.current?.contains(e.target))setOpen(false)};
  const escape=e=>{if(e.key==='Escape'){e.preventDefault();close(true)}};
  document.addEventListener('pointerdown',outside);document.addEventListener('keydown',escape);
  choices.current?.querySelector('[aria-pressed="true"]')?.focus();
  return()=>{document.removeEventListener('pointerdown',outside);document.removeEventListener('keydown',escape)};
 },[open]);
 const choose=async value=>{
  if(value===theme){close(true);return}
  setPending(value);
  try{if(await onSelect(value)!==false)close(true)}finally{setPending('')}
 };
 const navigate=e=>{
  if(!['ArrowDown','ArrowUp','Home','End'].includes(e.key))return;
  const buttons=[...choices.current.querySelectorAll('button:not(:disabled)')];if(!buttons.length)return;
  e.preventDefault();const index=buttons.indexOf(document.activeElement);
  buttons[e.key==='Home'?0:e.key==='End'?buttons.length-1:(index+(e.key==='ArrowDown'?1:-1)+buttons.length)%buttons.length].focus();
 };
 return <div className="header-theme" ref={root} onBlur={e=>{if(e.relatedTarget&&!e.currentTarget.contains(e.relatedTarget))setOpen(false)}}>
  <button className="header-theme-trigger" ref={trigger} aria-label={'Тема оформления: '+current.name} aria-haspopup="dialog" aria-expanded={open} aria-controls={id} onClick={()=>setOpen(v=>!v)}><Palette size={17}/><span>{current.name}</span><ChevronDown size={12} className={open?'turned':''}/></button>
  {open&&<div className="header-theme-popover" id={id} role="dialog" aria-label="Тема оформления" aria-busy={!!pending}><h3>Оформление</h3><div className="header-theme-choices" ref={choices} role="group" aria-label="Темы" onKeyDown={navigate}>{themes.map(t=><button className={'header-theme-choice theme-'+t.id} key={t.id} disabled={!!pending||busy} aria-pressed={theme===t.id} onClick={()=>choose(t.id)}><span className="header-theme-preview" aria-hidden="true"><i/><i/><i/></span><span className="header-theme-caption"><strong>{t.name}</strong><small>{t.caption}</small></span><span className="header-theme-check">{pending===t.id?<LoaderCircle size={15} className="theme-saving"/>:theme===t.id?<Check size={15}/>:null}</span></button>)}</div>
   {theme==='holiday'&&onSnowChange&&<label className="header-snow-setting"><Snowflake size={16}/><span>Показывать снег</span><input type="checkbox" role="switch" aria-label="Показывать снег" checked={snowEnabled} onChange={e=>onSnowChange(e.target.checked)}/></label>}
  </div>}
 </div>;
}
