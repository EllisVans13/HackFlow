// Pure server rendering smoke check. This does not replace browser interaction QA.
import {build} from 'esbuild';
import {readFile,writeFile,mkdtemp,rm} from 'node:fs/promises';
import {tmpdir} from 'node:os';
import {join,resolve} from 'node:path';
import {pathToFileURL} from 'node:url';
const source=await readFile(new URL('../src/main.jsx',import.meta.url),'utf8');
const names=['Auth','Dashboard','Catalog','TeamPage','Cases','Board','Chat','Materials','SchedulePage','Roadmap','SubmissionPage','Organizer','Jury','Ranking','Peer','Appeals','Profile','SettingsPage','Notifications','Ratings','Admin','Expert','CodeCheck','CreateHackathon'];
const dir=await mkdtemp(join(tmpdir(),'hackflow-ui-'));
try{
 const text=source.replace("import './style.css';",'').replace("createRoot(document.getElementById('root')).render(<App/>);",'')+`\nexport {${names.join(',')}};`;
 const transformed=await build({stdin:{contents:text,resolveDir:resolve('src'),loader:'jsx'},bundle:true,platform:'node',format:'esm',write:false,external:['react','react-dom','react-dom/*','lucide-react']});
 // Put temporary module next to node_modules for correct React resolution.
 const modulePath=resolve('.smoke-components.mjs');
 await writeFile(modulePath,transformed.outputFiles[0].text);
 try{
  const components=await import(pathToFileURL(modulePath));
  const React=await import('react');const {renderToString}=await import('react-dom/server');
  globalThis.location={search:'',hash:'',pathname:'/'};
  const date=new Date().toISOString();
  const h={id:1,title:'Хакатон',status:'active',organizer:true,jury:true,start_at:date,end_at:date,submission_deadline:date,team_size:5,rules:'Правила'};
  const user={id:1,nickname:'Тест',email:'test@example.com',role:'organizer',created_at:date,theme:'yellow'};
  const team={id:1,name:'Команда',members:[{id:1,nickname:'Тест',captain:true}],captain_id:1,progress:0,requests:[],description:'Описание'};
  const context={h,hid:1,user,team,cases:[],criteria:[],events:[h],notes:[],revision:0,theme:'yellow',go:()=>{},run:()=>{},form:()=>{},setHid:()=>{},setTheme:()=>{},setUser:()=>{},onLogin:()=>{}};
  for(const name of names){renderToString(React.createElement(components[name],{...context,channel:'team'}));console.log('OK',name)}
  renderToString(React.createElement(components.SubmissionPage,{...context,team:{...team,submission:{id:1,code:'X7Q2',title:'Сданный проект',description:'Решение',submitted_at:date,github:'https://github.com/pallets/flask',demo:'https://example.com',presentation_id:1}}}));
  console.log(`Passed: ${names.length+1} render cases. Browser QA remains separate.`);
 }finally{await rm(modulePath,{force:true})}
}finally{await rm(dir,{recursive:true,force:true})}
