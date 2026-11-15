// Pure server rendering smoke check. This does not replace browser interaction QA.
import {build} from 'esbuild';
import {readFile,writeFile,mkdtemp,rm} from 'node:fs/promises';
import {tmpdir} from 'node:os';
import {join,resolve} from 'node:path';
import {pathToFileURL} from 'node:url';
const source=await readFile(new URL('../src/main.jsx',import.meta.url),'utf8');
const names=['Welcome','Auth','StaffHome','Snowfall','WinterGarland','HolidayHat','HolidayScene','ThemeSwitcher','MaterialCover','SidebarAccount','Avatar','Dashboard','DashboardView','AwardCertificates','Catalog','TeamPage','Cases','CaseCard','Board','BoardView','TeamCity','CityScene','CityBuilding','CityDetail','BoardEmpty','HackathonImage','Chat','Materials','SchedulePage','Roadmap','SubmissionPage','Organizer','Jury','Ranking','Peer','Appeals','Profile','SettingsPage','Notifications','Ratings','Admin','Expert','CodeCheck','CreateHackathon','MentorPicker','MentorWorkspace'];
const dir=await mkdtemp(join(tmpdir(),'hackflow-ui-'));
try{
 const text=source.replace("import './style.css';",'').replace("createRoot(document.getElementById('root')).render(<Root/>);",'')+`\nexport {${names.join(',')},resolvePage,MaterialCards,showParticipantResults,ArchiveCards,ResultsTable,ResultsDetail,ResultsArchive,CertificateVerification,Root};`;
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
  for(const page of ['team','kanban','jury','organizer','admin','submission']){
    if(components.resolvePage(page,{role:'mentor'})!=='mentor')throw Error('Mentor route must stay in mentor workspace: '+page);
  }
  const learningItems=Object.entries({video:'Смотреть видео',presentation:'Открыть презентацию',document:'Открыть материал',link:'Открыть материал',webinar:'Подключиться',consultation:'Подключиться',assignment:'Задание выполнено'}).map(([kind,label],i)=>({id:i+1,kind,title:'Учебный материал '+i,topic:'Разработка',description:'Условие на русском языке',language:'ru',url:kind==='assignment'?'':'https://rutube.ru/video/example/',label}));
  const learningHtml=renderToString(React.createElement(components.MaterialCards,{items:learningItems,c:context}));
  for(const item of learningItems)if(!learningHtml.includes(item.label))throw Error('Missing learning action: '+item.kind);
  if(!learningHtml.includes('noopener noreferrer')||!learningHtml.includes('На русском'))throw Error('Learning links/language must be explicit');
  const mentorLearning=renderToString(React.createElement(components.MaterialCards,{items:learningItems,c:{...context,user:{...user,role:'mentor'}}}));
  if(mentorLearning.includes('Материал изучен')||mentorLearning.includes('Задание выполнено'))throw Error('Mentor must not get participant completion actions');
  const picker=renderToString(React.createElement(components.MentorPicker,{c:{...context,h:{...h,organizer:false},user:{...user,id:1}},team:{...team,captain_id:1,mentor:{id:9,nickname:'Ментор',skills:'React',bio:'Помогаю'}}}));
  if(!picker.includes('Сменить ментора')||!picker.includes('React'))throw Error('Captain mentor choice missing');
  console.log('OK dedicated mentor routes, captain picker and seven learning formats');
  for(const role of ['admin','organizer','jury','mentor'])if(components.showParticipantResults({role,participant:false}))throw Error('Staff must not see participant results navigation: '+role);
  if(components.showParticipantResults({role:'participant',participant:false}))throw Error('Event jury must not see participant results navigation');
  if(!components.showParticipantResults({role:'participant',participant:true}))throw Error('Participant results navigation missing');
  if(components.resolvePage('archive',{role:'mentor'})!=='archive')throw Error('Mentor must have access to public archive');
  const archiveHtml=renderToString(React.createElement(components.ArchiveCards,{items:[{id:22,title:'Открытый итог',description:'Описание',end_at:date,results_published:true},{id:23,title:'Ожидаем публикации',description:'Описание',end_at:date,results_published:false}]}));
  if(!archiveHtml.includes('/results/22')||archiveHtml.includes('/results/23')||!archiveHtml.includes('Результаты ещё не опубликованы'))throw Error('Archive must link only published rankings');
  const resultsHtml=renderToString(React.createElement(components.ResultsTable,{data:{hackathon:{title:'Открытый итог'},items:[{place:1,team:'Первая команда',title:'Проект',score:91.5}],criteria:[{id:1,title:'Качество',maximum:100}],tie_rule:'Раньше сданный проект'}}));
  for(const text of ['Место','Первая команда','91,5','Баллы из 100'])if(!resultsHtml.includes(text))throw Error('Missing public ranking column: '+text);
  console.log('OK staff navigation hidden, archive available to mentors, public archive and places');
  for(const role of ['admin','organizer','jury','mentor','participant']){
    if(components.resolvePage('results/22',{role})!=='results')throw Error('Embedded results route must work for '+role);
  }
  if(components.resolvePage('hackathons',{role:'mentor'})!=='hackathons')throw Error('All hackathons button must work for mentor');
  const embeddedArchive=renderToString(React.createElement(components.ArchiveCards,{items:[{id:22,title:'Итоги',end_at:date,results_published:true}],onOpen:()=>{}}));
  if(embeddedArchive.includes('href="/results/22"')||!embeddedArchive.includes('<button'))throw Error('Cabinet archive must navigate within app');
  const embeddedDetail=renderToString(React.createElement(components.ResultsDetail,{id:22,onBack:()=>{},onAllHackathons:()=>{}}));
  if(!embeddedDetail.includes('Все хакатоны')||!embeddedDetail.includes('Прошедшие хакатоны')||embeddedDetail.includes('href="/results"'))throw Error('Embedded results must have internal back buttons');
  const verified=renderToString(React.createElement(components.CertificateVerification,{certificate:{valid:true,recipient_name:'Мария',place:1,team_name:'Команда',organizer_name:'Анна',number:'HF-000001'}}));
  if(!verified.includes('Диплом подтверждён')||!verified.includes('Мария'))throw Error('QR verification must display certificate');
  const revoked=renderToString(React.createElement(components.CertificateVerification,{certificate:{valid:false}}));
  if(!revoked.includes('Диплом не подтверждён'))throw Error('Revoked QR must not look valid');
  console.log('OK internal archive navigation, return buttons and certificate QR states');

  for(const path of ['/results','/results/22']){
    globalThis.location.pathname=path;
    const publicHtml=renderToString(React.createElement(components.Root));
    if(publicHtml.includes('С возвращением')||!publicHtml.includes('Все хакатоны'))throw Error('Public results must render without the login app');
  }
  globalThis.location.pathname='/';


  const cityTeam={...team,style:'tower',stage:'building',floors:3,total:8,done:4,progress:50,capacity:5,recruiting:true,case_title:'Городской сервис',project:null,can_customize:true,showcase:false};
  const caseItem={id:9,title:'Удобный кампус',company:'Кампус',description:'Короткая постановка задачи.',requirements:'Полные условия задачи',expected:'Работающий прототип',url:'https://example.com/case'};
  const cityData={items:[cityTeam],my_team_id:1,results_published:false,summary:{teams:1,members:1,tasks_done:4,submitted:0}};
  for(const name of names){renderToString(React.createElement(components[name],{...context,team:cityTeam,channel:'team',data:name==='CityScene'?cityData:{items:[]},status:'todo',go:()=>{},item:caseItem,c:context}));console.log('OK',name)}
  renderToString(React.createElement(components.SubmissionPage,{...context,team:{...team,submission:{id:1,code:'X7Q2',title:'Сданный проект',description:'Решение',submitted_at:date,github:'https://github.com/pallets/flask',demo:'https://example.com',presentation_id:1}}}));
  const draw=(props)=>renderToString(React.createElement(components.DashboardView,{...context,...props}));
  const empty=draw({tasks:{items:[]},materials:{items:[]},schedule:{items:[]}});
  for(const label of ['Обучение','Материалы','Расписание','Пригласить','Часовой пояс']){
    if(!empty.includes(label))throw Error('Missing home action: '+label);
  }
  if(empty.includes('0 / 0')||empty.includes('Большие идеи'))throw Error('Home must show work rather than placeholder stats/banner');
  const unteamed=draw({team:null,tasks:null,materials:{items:[]},schedule:{items:[]}});
  if(!unteamed.includes('Найти команду')||!unteamed.includes('Собери команду'))throw Error('Missing no-team guidance');
  const future=new Date(Date.now()+3600000).toISOString(),later=new Date(Date.now()+7200000).toISOString();
  const loaded=draw({tasks:{items:[{id:2,title:'Поздняя задача',status:'todo',deadline:later},{id:1,title:'Ближайшая задача',status:'doing',deadline:future}]},materials:{items:[{id:1,completed:true}]},schedule:{items:[{id:2,title:'Позднее событие',starts_at:later},{id:1,title:'Ближайшее событие',starts_at:future}]}});
  for(const text of ['Задачи команды','Ближайшие задачи','Ближайшая задача','Поздняя задача'])if(loaded.includes(text))throw Error('Task blocks must not appear on home');
  if(!loaded.includes('Ближайшее событие')||loaded.includes('Позднее событие'))throw Error('Home must show only the nearest event');
  const finished=draw({h:{...h,submission_deadline:'2020-01-01T00:00:00Z'},tasks:{items:[{id:1,status:'done'}]},materials:{items:[]},schedule:{items:[]}});
  if(!finished.includes('Срок завершён'))throw Error('Missing deadline completion state');
  console.log('OK compact home: no task blocks, nearest event and deadline');
  const compactCase=renderToString(React.createElement(components.CaseCard,{item:caseItem,c:context}));
  if(!compactCase.includes('<details')||!compactCase.includes('Подробнее')||!compactCase.includes(caseItem.requirements)||!compactCase.includes(caseItem.expected))throw Error('Case requirements must remain available in details');
  const references=renderToString(React.createElement(components.Cases,{...context,cases:[caseItem]}));
  if(!references.includes('Правила')||!references.includes('Критерии'))throw Error('Rules and criteria missing');
  console.log('OK compact case cards preserve full requirements, rules and criteria');
  for(const place of [1,2,3]){
    const award={id:'award-'+place,place,event_title:'Город рядом',recipient_name:'Мария Волкова',team_name:'Команда',number:'HF-000012',download_url:'/api/certificates/test/download',preview_url:'/api/certificates/test/preview'};
    const html=renderToString(React.createElement(components.AwardCertificates,{items:[award]}));
    for(const value of ['Скачать PDF',award.download_url,award.preview_url,award.recipient_name])if(!html.includes(value))throw Error('Missing certificate field: '+value);
  }
  const awardError=renderToString(React.createElement(components.AwardCertificates,{error:'Ошибка загрузки'}));
  if(!awardError.includes('role="alert"'))throw Error('Certificate load errors must be visible');
  console.log('OK awards: three podium places, personal names and authenticated download links');
  for(const theme of ['yellow','purple','holiday']){
    const html=renderToString(React.createElement(components.ThemeSwitcher,{theme}));
    if(!html.includes('aria-haspopup="dialog"')||!html.includes('aria-expanded="false"'))throw Error('Header theme trigger missing');
  }
  for(const [kind,material] of [['code',{topic:'Разработка',title:'React: практика',kind:'document'}],['design',{topic:'Дизайн',title:'Figma',kind:'document'}],['video',{topic:'Презентации',kind:'video'}],['reading',{topic:'Аналитика',kind:'document'}]]){
    const html=renderToString(React.createElement(components.MaterialCover,{material}));
    if(!html.includes('material-cover-'+kind)||!html.includes('<svg')||!html.includes(material.topic))throw Error('Missing bundled material illustration '+kind);
  }
  console.log('OK header theme triggers and four material cover types');
  const snow=renderToString(React.createElement(components.Snowfall,{enabled:true}));
  if(renderToString(React.createElement(components.Snowfall,{enabled:false}))!=='')throw Error('Snow must be disabled outside holiday theme');
  if((snow.match(/class="winter-flake"/g)||[]).length!==40)throw Error('Snow particles missing');
  const positions=[...snow.matchAll(/left:([^;]+)/g)].map(m=>m[1]);
  const speeds=[...snow.matchAll(/--fall-time:([^;]+)/g)].map(m=>m[1]);
  if(new Set(positions).size<35||new Set(speeds).size<10)throw Error('Snow must vary in position and speed');
  if(!snow.includes('aria-hidden="true"')||snow.includes('❄'))throw Error('Snow must be decorative vector particles');
  console.log('OK snowfall: disabled state, 40 dispersed particles, varied speed, decorative SVG');
  const garland=renderToString(React.createElement(components.WinterGarland,{enabled:true}));
  if(!garland.includes('aria-hidden="true"')||renderToString(React.createElement(components.WinterGarland,{enabled:false}))!=='')throw Error('Garland must be decorative and holiday-only');
  const avatarUser={...user,avatar:'/api/media/test-avatar'};
  const avatarTeam={...team,members:[{...team.members[0],avatar:avatarUser.avatar}]};
  for(const Component of [components.Avatar,components.SidebarAccount,components.TeamPage,components.DashboardView,components.Profile,components.SettingsPage]){
    const html=renderToString(React.createElement(Component,{...context,user:avatarUser,team:avatarTeam,tasks:{items:[]},materials:{items:[]},schedule:{items:[]}}));
    if(!html.includes(avatarUser.avatar))throw Error('Profile avatar missing in '+Component.name);
  }
  console.log('OK holiday garland and avatar consistency across profile, settings, team and home');
  const board=renderToString(React.createElement(components.BoardView,{...context,data:{items:[{id:9,title:'Моя задача',status:'todo',assignee_id:1}]}}));
  for(const label of ['Моя задача','Здесь начинается работа','Место для проверки','Здесь будут результаты'])if(!board.includes(label))throw Error('Missing board state '+label);
  const blank=renderToString(React.createElement(components.BoardView,{...context,data:{items:[]}}));
  if(!blank.includes('Создать задачу'))throw Error('Empty board needs create action');
  const cover=renderToString(React.createElement(components.HackathonImage,{event:{cover:'/hackathons/green.svg'}}));
  if(!cover.includes('/hackathons/green.svg'))throw Error('Cover image missing');
  console.log('OK bundled image and populated/empty board states');
  for(const style of ['workshop','tower','lab','aframe','treehouse'])for(const stage of ['plot','foundation','building','submitted']){
    const html=renderToString(React.createElement(components.CityBuilding,{team:{...cityTeam,style,stage,floors:5}}));
    if(!html.includes('city-building')||html.includes('NaN'))throw Error('Invalid city building '+style+' '+stage);
  }
  const scene=renderToString(React.createElement(components.CityScene,{data:cityData,go:()=>{}}));
  if(!scene.includes('Команда')||!scene.includes('К задачам')||!scene.includes('Архитектура'))throw Error('City detail/actions missing');
  if(scene.includes('https://'))throw Error('Unpublished city must not contain project links');
  const emptyCity=renderToString(React.createElement(components.CityScene,{data:{...cityData,items:[],my_team_id:null},go:()=>{}}));
  if(!emptyCity.includes('Создать команду'))throw Error('Empty city needs create-team action');
  const gallery=renderToString(React.createElement(components.CityDetail,{team:{...cityTeam,can_customize:false,stage:'submitted',project:{title:'Выставка',description:'Открытый проект',demo:'https://example.com/exhibit'}},resultsPublished:true,go:()=>{}}));
  if(!gallery.includes('https://example.com/exhibit')||!gallery.includes('Открыть демо'))throw Error('Published exhibition link missing');
  console.log('OK city: 20 building states, captain controls, empty city, exhibition');
  console.log(`Passed: ${names.length+54} render cases. Browser QA remains separate.`);
 }finally{await rm(modulePath,{force:true})}
}finally{await rm(dir,{recursive:true,force:true})}
