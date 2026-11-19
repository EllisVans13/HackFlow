import React,{useState,useEffect} from 'react';

export function canPeerReview(user,event){return user?.role==='participant'&&user.participant!==false&&event?.admitted===true&&!event.organizer&&!event.jury&&!event.mentor&&!event.expert}

export function reviewAction(work,data,c){
 if(work.reviewed)return {disabled:true,label:'Оценка отправлена',reason:'Ваша команда уже оценила этот проект. Повторная отправка недоступна.'};
 if(data.published)return {disabled:true,label:'Оценить проект',reason:'Приём оценок завершён: результаты опубликованы.'};
 if(!data.can_review){
  return {disabled:true,label:'Оценить проект',reason:'Оценку от команды отправляет только её текущий капитан. Текущий состав можно проверить в разделе «Моя команда».'};
 }
 return {disabled:false,label:'Оценить проект',reason:''};
}

export function PeerCards({data,c,onGrade}){return <>{data.items.map(s=>{const action=reviewAction(s,data,c);return <section className="panel spaced" key={s.id}><div className="section-title"><h3>Анонимный проект {s.code}</h3><span className="badge">{s.reviewed?'Оценка отправлена':data.published?'Приём оценок завершён':'Ожидает оценки'}</span></div><p className="pre-line">{s.text}</p>{s.material_url?<div className="panel-actions"><a className="button secondary" href={s.material_url} target="_blank" rel="noopener noreferrer">Открыть PDF проекта</a><a className="button secondary" href={s.material_url+'?download=1'}>Скачать PDF</a></div>:<p>Обезличенный файл ещё не подготовлен организатором.</p>}<button className="button spaced" disabled={action.disabled} onClick={()=>onGrade(s)}>{action.label}</button>{action.reason&&<p role="status">{action.reason}</p>}</section>})}</>}

export function PeerReview({c}){
 const allowed=canPeerReview(c.user,c.h);
 const [data,setData]=useState(null),[error,setError]=useState(''),[selected,setSelected]=useState(null),[scores,setScores]=useState({}),[comment,setComment]=useState(''),[version,setVersion]=useState(0);
 useEffect(()=>{
  if(!allowed)return;
  let active=true,pending=false;setData(null);setError('');
  const load=async()=>{if(pending)return;pending=true;try{const d=await c.api(`/hackathons/${c.hid}/peer`);if(active){setData(d);setError('')}}catch(e){if(active){setData(null);setError(e.message)}}finally{pending=false}};
  const refreshVisible=()=>{if(document.visibilityState==='visible')load()};
  load();const timer=setInterval(refreshVisible,15000);
  window.addEventListener('focus',refreshVisible);document.addEventListener('visibilitychange',refreshVisible);
  return()=>{active=false;clearInterval(timer);window.removeEventListener('focus',refreshVisible);document.removeEventListener('visibilitychange',refreshVisible)};
 },[c.hid,c.revision,version,allowed]);
 useEffect(()=>{if(!selected)return;const fn=e=>{if(e.key==='Escape')setSelected(null)};window.addEventListener('keydown',fn);return()=>window.removeEventListener('keydown',fn)},[selected]);
 if(!allowed)return <section className="panel"><p>Peer Review доступен только участникам этого хакатона.</p></section>;
 const refresh=()=>setVersion(v=>v+1);
 const grade=s=>{setSelected(s);setScores({});setComment('')};
 return <>{error&&<p className="notice danger" role="alert">{error}</p>}<section className="panel"><span className="badge">Peer Review</span><h2>Peer Review</h2>{c.user?.email&&<p>Вы вошли как <strong>{c.user.email}</strong></p>}<p>{data?.weighted?'Итог из 100: 80% средней оценки жюри + 20% средней оценки назначенных команд. Каждая работа оценивается по критериям из 100; система применяет веса автоматически.':'Это мероприятие использует прежний формат отдельного Peer Review; официальная оценка определяется жюри.'}</p><p>Проверок вашего проекта получено: {data?.own_progress??0} / {data?.required??'…'}. Один отзыв от команды отправляет капитан.</p></section>{data&&<PeerCards data={data} c={c} onGrade={grade}/ >}{data&&!data.items.length&&<section className="panel spaced"><p>Назначений пока нет. Проекты распределяются автоматически после подготовки материалов и начала этапа проверки.</p></section>}{selected&&<div className="modal-backdrop" onClick={e=>{if(e.target===e.currentTarget)setSelected(null)}}><section className="modal" role="dialog" aria-modal="true" aria-label="Оценка Peer Review"><div className="section-title"><h2>Проект {selected.code}</h2><button className="icon-button" onClick={()=>setSelected(null)} aria-label="Закрыть">×</button></div><p>Оценка из 100. Вес 20% применится автоматически.</p><form onSubmit={e=>{e.preventDefault();c.run(async()=>{await c.api(`/peer/${selected.id}`,'POST',{scores,comment});setSelected(null);refresh();c.flash('Оценка команды сохранена')})}}>{c.criteria.map(x=><label key={x.id}>{x.title} · максимум {x.maximum}<input type="number" min="0" max={x.maximum} step="0.01" required value={scores[x.id]??''} onChange={e=>setScores({...scores,[x.id]:Number(e.target.value)})}/></label>)}<label>Обоснование<textarea required maxLength={5000} rows={4} value={comment} onChange={e=>setComment(e.target.value)}/></label><button className="button" disabled={c.busy}>Отправить оценку команды</button></form></section></div>}</>
}

export function AnonymousMaterial({submission,c}){
 const [file,setFile]=useState(null),[confirmed,setConfirmed]=useState(false),[ready,setReady]=useState(Boolean(submission.anonymous_file_id));
 return <section className="anonymous-material spaced"><h3>Обезличенный PDF для жюри и Peer Review</h3><p>Удалите из страниц имена, команду, контакты и ссылки, раскрывающие авторство. Метаданные и аннотации PDF очищаются сервером.</p>{ready&&<a href={`/api/submissions/${submission.id}/anonymous-file`} target="_blank" rel="noopener noreferrer" className="text-button">Открыть подготовленный PDF</a>}<input aria-label="Обезличенный PDF" type="file" accept="application/pdf" onChange={e=>setFile(e.target.files[0])}/><label className="check-label"><input type="checkbox" checked={confirmed} onChange={e=>setConfirmed(e.target.checked)}/>PDF проверен: на страницах нет сведений об авторах</label><button className="button secondary" disabled={!file||!confirmed||c.busy} onClick={()=>c.run(async()=>{const form=new FormData();form.append('file',file);form.append('confirmed','true');await c.api(`/submissions/${submission.id}/anonymous-file`,'POST',form);setReady(true);setFile(null);c.flash('Обезличенный PDF сохранён')})}>Сохранить обезличенный файл</button></section>
}
