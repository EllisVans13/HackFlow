import React from 'react';
import {Award,Download,ExternalLink} from 'lucide-react';

export function AwardCertificates({items=[],error}){
 if(error)return <p className="notice danger" role="alert">Дипломы: {error}</p>;
 if(!items.length)return null;
 return <section className="panel award-section"><div className="section-title"><h2><Award size={21}/>Дипломы</h2><span className="badge">{items.length}</span></div><div className="award-grid">{items.map(item=><article className={'award-card award-place-'+item.place} key={item.id}>
  <a className="award-document" href={item.preview_url} target="_blank" rel="noreferrer" aria-label={`Открыть диплом за ${item.place} место: ${item.event_title}`}><span className="award-ribbon"><span className="award-brand">hackflow</span><span className="award-roman">{['','I','II','III'][item.place]}</span><span className="award-ribbon-label">МЕСТО</span></span><span className="award-paper"><span className="award-paper-title">Диплом</span><span className="award-paper-kicker">ПОБЕДИТЕЛЯ ХАКАТОНА</span><strong>{item.recipient_name}</strong><span className="award-paper-reason">за {item.place} место в хакатоне</span><span className="award-paper-event">{item.event_title}</span><span className="award-paper-team">{item.team_name}</span><small>{item.number}</small></span></a>
  <div className="award-card-body"><div className="award-card-title"><h3>{item.event_title}</h3>{item.is_demo&&<span className="badge">Демо</span>}</div><div className="award-actions"><a className="button" href={item.download_url}><Download size={15}/>Скачать PDF</a><a className="text-button" href={item.preview_url} target="_blank" rel="noreferrer">Открыть<ExternalLink size={14}/></a></div></div>
 </article>)}</div></section>;
}
