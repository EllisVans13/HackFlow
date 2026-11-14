// Pure server rendering smoke check. This does not replace browser interaction QA.
import {build} from 'esbuild';
import {readFile,writeFile,mkdtemp,rm} from 'node:fs/promises';
import {tmpdir} from 'node:os';
import {join,resolve} from 'node:path';
import {pathToFileURL} from 'node:url';
const source=await readFile(new URL('../src/main.jsx',import.meta.url),'utf8');
const names=['Welcome','Auth','StaffHome','Dashboard','DashboardView','Catalog','TeamPage','Cases','Board','Chat','Materials','SchedulePage','Roadmap','SubmissionPage','Organizer','Jury','Ranking','Peer','Appeals','Profile','SettingsPage','Notifications','Ratings','Admin','Expert','CodeCheck','CreateHackathon'];
const dir=await mkdtemp(join(tmpdir(),'hackflow-ui-'));
try{
 const text=source.replace("import './style.css';",'').replace("createRoot(document.getElementById('root')).render(<App/>);",'')+`\nexport {${names.join(',')},resolvePage};`;
 const transformed=await build({stdin:{contents:text,resolveDir:resolve('src'),loader:'jsx'},bundle:true,platform:'node',format:'esm',write:false,external:['react','react-dom','react-dom/*','lucide-react']});
 // Put temporary module next to node_modules for correct React resolution.
 const modulePath=resolve('.smoke-components.mjs');
 await writeFile(modulePath,transformed.outputFiles[0].text);
 try{
  const components=await import(pathToFileURL(modulePath));
  for(const role of ['admin','organizer','jury']){if(components.resolvePage('dashboard',{role,participant:false})!=='home')throw Error('Staff overview must resolve to home');}
  if(components.resolvePage('dashboard',{role:'participant',participant:true})!=='home')throw Error('Legacy overview must redirect to unified home');
  if(components.resolvePage('',{role:'participant'})!=='home')throw Error('Default page must be home');
  const React=await import('react');const {renderToString}=await import('react-dom/server');
  globalThis.location={search:'',hash:'',pathname:'/'};
  const date=new Date().toISOString();
  const h={id:1,title:'Хакатон',status:'active',organizer:true,jury:true,start_at:date,end_at:date,submission_deadline:date,team_size:5,rules:'Правила'};
  const user={id:1,nickname:'Тест',email:'test@example.com',role:'organizer',created_at:date,theme:'yellow'};
  const team={id:1,name:'Команда',members:[{id:1,nickname:'Тест',captain:true}],captain_id:1,progress:0,requests:[],description:'Описание'};
  const context={h,hid:1,user,team,cases:[],criteria:[],events:[h],notes:[],revision:0,theme:'yellow',go:()=>{},run:()=>{},form:()=>{},setHid:()=>{},setTheme:()=>{},setUser:()=>{},onLogin:()=>{}};
  for(const name of names){renderToString(React.createElement(components[name],{...context,channel:'team'}));console.log('OK',name)}
  renderToString(React.createElement(components.SubmissionPage,{...context,team:{...team,submission:{id:1,code:'X7Q2',title:'Сданный проект',description:'Решение',submitted_at:date,github:'https://github.com/pallets/flask',demo:'https://example.com',presentation_id:1}}}));
  const draw=(props)=>renderToString(React.createElement(components.DashboardView,{...context,...props}));
  const empty=draw({tasks:{items:[]},materials:{items:[]},schedule:{items:[]}});
  for(const label of ['Задач пока нет','Создать задачу','Материалов пока нет','Пригласить участников','Часовой пояс']){
    if(!empty.includes(label))throw Error('Missing home action: '+label);
  }
  if(empty.includes('0 / 0')||empty.includes('Большие идеи'))throw Error('Home must show work rather than placeholder stats/banner');
  const unteamed=draw({team:null,tasks:null,materials:{items:[]},schedule:{items:[]}});
  if(!unteamed.includes('Найти команду')||!unteamed.includes('Сначала собери команду'))throw Error('Missing no-team guidance');
  const future=new Date(Date.now()+3600000).toISOString(),later=new Date(Date.now()+7200000).toISOString();
  const loaded=draw({tasks:{items:[{id:2,title:'Поздняя задача',status:'todo',deadline:later},{id:1,title:'Ближайшая задача',status:'doing',deadline:future}]},materials:{items:[{id:1,completed:true}]},schedule:{items:[{id:2,title:'Позднее событие',starts_at:later},{id:1,title:'Ближайшее событие',starts_at:future}]}});
  if(loaded.indexOf('Ближайшая задача')>loaded.indexOf('Поздняя задача'))throw Error('Task deadlines must sort ascending');
  if(loaded.indexOf('Ближайшее событие')>loaded.indexOf('Позднее событие'))throw Error('Events must sort ascending');
  const finished=draw({h:{...h,submission_deadline:'2020-01-01T00:00:00Z'},tasks:{items:[{id:1,status:'done'}]},materials:{items:[]},schedule:{items:[]}});
  if(!finished.includes('Срок завершён')||!finished.includes('Все задачи выполнены'))throw Error('Missing completion states');
  console.log('OK unified home: empty, no-team, sorted tasks/events and finished states');
  console.log(`Passed: ${names.length+5} render cases. Browser QA remains separate.`);
 }finally{await rm(modulePath,{force:true})}
}finally{await rm(dir,{recursive:true,force:true})}
