import React,{useState,useEffect} from 'react';
import {Trophy,ArrowLeft,ArrowUpRight,Search} from 'lucide-react';

function usePublicData(path){
 const [data,setData]=useState(null),[error,setError]=useState('');
 useEffect(()=>{const controller=new AbortController();setData(null);setError('');fetch('/api'+path,{credentials:'include',signal:controller.signal}).then(async r=>{const body=await r.json();if(!r.ok)throw Error(body.error||'Не удалось загрузить результаты');return body}).then(setData).catch(e=>{if(e.name!=='AbortError')setError(e.message)});return()=>controller.abort()},[path]);
 return [data,error];
}
const eventDate=d=>new Date(d).toLocaleDateString('ru-RU',{day:'numeric',month:'long',year:'numeric'});

export function ArchiveCards({items}){
 const [query,setQuery]=useState('');
 const filtered=items.filter(h=>h.title.toLowerCase().includes(query.toLowerCase()));
 return <><label className="archive-search"><Search size={18}/><span className="sr-only">Поиск прошедших хакатонов</span><input value={query} onChange={e=>setQuery(e.target.value)} placeholder="Найти хакатон по названию"/></label><div className="catalog-grid">{filtered.map(h=><article className="panel archived-event" key={h.id}><img src={h.cover||'/hackathons/default.svg'} alt="" loading="lazy"/><div className="section-title"><span className="badge">Завершён</span>{h.is_demo&&<span className="badge">Демонстрационный</span>}</div><h2>{h.title}</h2><p>{h.description}</p><small>Завершение: {eventDate(h.end_at)}</small><div className="panel-actions spaced">{h.results_published?<a className="button" href={'/results/'+h.id}>Рейтинг команд<ArrowUpRight size={16}/></a>:<p role="status">Результаты ещё не опубликованы.</p>}</div></article>)}</div>{!filtered.length&&<section className="panel"><p>{items.length?'По этому названию ничего не найдено.':'Завершённых хакатонов пока нет.'}</p></section>}</>
}

export function ResultsArchive({embedded=false}){
 const [data,error]=usePublicData('/public/results');
 return <><div className="archive-intro">{!embedded&&<h1>Прошедшие хакатоны</h1>}<p>Официальный рейтинг команд доступен всем, в том числе без регистрации и участия.</p></div>{error?<p className="notice danger" role="alert">{error}</p>:data?<ArchiveCards items={data.items}/>:<p role="status">Загружаем хакатоны…</p>}</>
}

export function ResultsTable({data}){
 return <><section className="panel"><div className="section-title"><span className="badge">Официальные результаты</span>{data.hackathon.is_demo&&<span className="badge">Демонстрационные данные</span>}</div><h1>{data.hackathon.title}</h1><p>Места команд и итоговые оценки из 100 баллов.</p>{data.items.length?<div className="table-wrap public-ranking-table"><table><thead><tr><th>Место</th><th>Команда</th><th>Проект</th><th>Баллы из 100</th></tr></thead><tbody>{data.items.map(r=><tr key={r.place}><td><span className={'ranking-place place-'+r.place}>{r.place}</span></td><td><strong>{r.team}</strong></td><td>{r.title}</td><td><strong>{r.score.toLocaleString('ru-RU',{maximumFractionDigits:2})}</strong></td></tr>)}</tbody></table></div>:<p>В опубликованных результатах пока нет оценённых команд.</p>}{data.tie_rule&&<p className="ranking-tie-rule">При равных баллах: {data.tie_rule}</p>}</section>{data.criteria.length>0&&<section className="panel spaced"><h2>Критерии оценки</h2><ul>{data.criteria.map(c=><li key={c.id}>{c.title} — до {c.maximum} баллов</li>)}</ul></section>}</>
}

function ResultDetail({id}){
 const [data,error]=usePublicData(`/public/hackathons/${id}/results`);
 return <><a className="text-button public-back" href="/results"><ArrowLeft size={16}/>Все прошедшие хакатоны</a>{error?<section className="panel" role="alert"><h1>Результаты недоступны</h1><p>{error}</p></section>:data?<ResultsTable data={data}/>:<p role="status">Загружаем рейтинг…</p>}</>
}

export function PublicResults(){
 const id=location.pathname.match(/^\/results\/(\d+)\/?$/)?.[1];
 return <div className="public-results"><header className="public-results-header"><a className="brand" href="/">hack<span>flow</span></a><a className="button secondary" href="/">В HackFlow</a></header><main className="public-results-main">{id?<ResultDetail id={id}/>:<ResultsArchive/>}</main></div>
}
