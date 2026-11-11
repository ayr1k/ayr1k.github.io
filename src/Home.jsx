import React from 'react';
import {ArrowUpRight,ArrowRight,DownloadSimple,Cube,PuzzlePiece,Database, CaretDown} from '@phosphor-icons/react';
const asset=n=>`${import.meta.env.BASE_URL}assets/${n}`;
const highlights=[
 {id:'create',icon:Cube,title:['引导创建','Guided creation'],body:['从你想怎么玩开始。选择合适的版本与加载器，查看推荐方案，再决定安装什么。','Start with how you want to play. Review versions, loaders and recommendations before choosing what to install.']},
 {id:'content',icon:PuzzlePiece,title:['内容管理','Content management'],body:['模组、资源包与光影集中管理。按版本寻找内容，批量启停，让更新井然有序。','Keep mods, resource packs and shaders together. Find compatible files, manage them in batches and stay on top of updates.']},
 {id:'recovery',icon:Database,title:['备份与恢复','Backup & recovery'],body:['先在独立副本中尝试新内容。备份重要实例，在需要时找到恢复的入口。','Try new content in an independent copy. Back up important instances and keep a way back when you need it.']},
];
const questions=[
 {q:['整合包、模组清单和备份有什么区别？','Modpack, mod list or backup?'],a:['整合包按作者方案准备游戏内容，可能还需下载；模组清单用于重新匹配模组，不含实际文件、配置和存档；备份恢复你选定的数据。1.7.0 可将本地 MRPACK 或支持的内容 ZIP 导入独立实例。','A modpack prepares an author’s setup and may still need downloads. A mod list rematches mods without containing files, configurations or worlds. A backup restores selected data. Version 1.7.0 imports local MRPACKs and supported content ZIPs into independent instances.'],href:'#/features/modpacks',link:['了解本地整合包','Explore local modpacks']},
 {q:['下载慢或中断了怎么办？','What if downloads are slow or interrupted?'],a:['在下载设置中选择自动、官方优先或中国大陆优化；任务中心支持下载阶段的暂停与继续，并提供连接诊断。支持续传时保留进度，所有文件仍需校验。','Choose Automatic, Official first or Mainland China optimized in download settings. Pause and resume download stages and diagnose connections in Tasks. Resume where supported; all files still require verification.'],href:'#/features/downloads',link:['了解下载与恢复','Explore downloads & recovery']},
 {q:['支持哪些系统？','Which systems are supported?'],a:['提供 Windows x64、macOS Intel/Apple Silicon 和 Linux x64 下载。macOS 尚待实机验证，Linux 尚需完整桌面与游戏测试；FreeBSD 仅为服务端/工具实验包，暂不支持游戏客户端。','Windows x64, macOS Intel/Apple Silicon and Linux x64 downloads are available. macOS needs device testing; Linux needs full desktop/gameplay testing. FreeBSD is a server/tools experiment without game-client support.'],href:'#/download',link:['查看下载选项','View downloads']},
 {q:['如何保留已有实例？','How do I keep my existing instances?'],a:['升级同一产品会保留游戏数据。更换电脑或数据位置前，先备份重要实例，再通过备份与恢复功能恢复到独立实例。','Upgrading the same product retains game data. Before moving computers or data locations, back up important instances and restore them as independent instances.'],href:'#/features/recovery',link:['了解备份与恢复','Explore backup & recovery']},
 {q:['主题可以在两个版本间使用吗？','Can I use themes in both editions?'],a:['可以。AMBER 与 AmberE 共用 .ambtheme 格式。导入前请检查主题的版本要求；主题只改变外观，不改变账号规则或游戏数据。','Yes. AMBER and AmberE share the .ambtheme format. Check the required launcher version before importing. Themes change appearance, not account rules or game data.'],href:'#/themes',link:['浏览官方主题','Browse official themes']},
 {q:['更新前如何备份？','How do I back up before updating?'],a:['关闭游戏，在实例的“备份与恢复”中创建并校验备份。重要存档建议在另一块磁盘保留一份副本；回退启动器不会撤销世界里的变化。','Close the game, then create and verify a backup in the instance’s Backup & recovery tab. Keep important worlds on another drive too. Downgrading the launcher does not undo world changes.'],href:'#/features/recovery',link:['查看恢复方式','See recovery options']},
];
export function Home({en}){
 const t=(zh,english)=>en?english:zh;
 return <div className="home-page">
  <section className="home-hero" aria-labelledby="hero-title">
   <img className="stage-texture" src={asset('emerald-stage-texture.webp')} alt="" fetchPriority="high"/>
   <div className="hero-intro wrap">
    <p className="hero-kicker">{t('为每一次冒险，保留自由选择的空间。','Keep the freedom to choose, on every adventure.')}</p>
    <h1 id="hero-title">{t('你的世界，','Your world.')}<br/>{t('由你掌握。','Your way.')}</h1>
    <p className="hero-description">{t('创建实例、管理模组、定制外观。让每次出发，都更简单。','Create instances, manage mods, make it yours. Get ready for your next adventure.')}</p>
    <div className="hero-actions"><a href="#/download" className="button gold"><DownloadSimple size={21}/>{t('下载 AMBER','Download AMBER')}</a><a className="text-link" href="#/features">{t('探索功能','Explore features')}<ArrowUpRight size={19}/></a></div>
    <p className="platform-line">Windows 1.7.0 <span>·</span> macOS / Linux 1.7.0 <span>·</span> {t('免费开源','Free & open source')}</p>
   </div>
   <figure className="hero-product wrap"><img src={asset('launcher-alloy-1.2.1.png')} width="1280" height="840" alt={t('AMBER 的 Alloy 首页：实例启动、游玩日历与新闻模块','AMBER with Alloy: launch controls, play calendar and news')} fetchPriority="high"/><figcaption>{t('AMBER · Alloy 主题','AMBER · Alloy theme')}</figcaption></figure>
  </section>
  <section className="home-features wrap" aria-labelledby="feature-title">
   <div className="section-intro"><h2 id="feature-title">{t('从准备，到开玩。','From setup to play.')}</h2><p>{t('简单的步骤，完整的体验。让 Minecraft 按你的方式运行。','A simpler setup. A complete experience. Play Minecraft your way.')}</p></div>
   <div className="highlight-grid">{highlights.map(f=><a className="highlight" key={f.id} href={'#/features/'+f.id}><f.icon size={45} weight="light"/><h3>{f.title[en?1:0]}</h3><p>{f.body[en?1:0]}</p><span>{t('了解更多','Learn more')}<ArrowUpRight size={17}/></span></a>)}</div>
  </section>
  <section className="theme-showcase wrap" aria-labelledby="theme-title">
   <div className="theme-story"><span className="eyebrow">{t('个性化','MAKE IT YOURS')}</span><h2 id="theme-title">{t('你的启动器，你的样子。','Your launcher. Your look.')}</h2><p className="theme-capabilities">{t('.ambtheme 主题 · 配色 · 布局 · 分区滚动','.ambtheme themes · Colors · Layout · Section scrolling')}</p><p>{t('从深色到浅色，从简洁到丰富。先从基础设置开始，按需展开更多自由。','From dark to light, simple to detailed. Start with the basics and open up more possibilities when you need them.')}</p><a className="button gold" href="#/themes">{t('浏览官方主题','Browse official themes')}<ArrowUpRight size={20}/></a></div>
   <div className="theme-visual"><img className="theme-light" src={asset('launcher-classic-1.2.webp')} width="1280" height="840" loading="lazy" alt={t('AMBER 经典浅色外观','AMBER classic light appearance')}/><img className="theme-dark" src={asset('launcher-alloy-1.2.1.png')} width="1280" height="840" loading="lazy" alt={t('AMBER Alloy 深色外观','AMBER Alloy dark appearance')}/></div>
  </section>
  <section className="home-faq wrap" aria-labelledby="faq-title">
   <div className="faq-intro"><span className="eyebrow">{t('常见问题','GOOD TO KNOW')}</span><h2 id="faq-title">{t('开始之前，','Before you begin,')}<br/>{t('你可能想知道。','a few answers.')}</h2><p>{t('这里整理了常见问题，帮助你更快了解和使用 AMBER。更多操作说明，请查看使用指南。','A few things to help you get started with AMBER. Find more detailed instructions in the user guide.')}</p><a className="button outline" href={'https://github.com/ayr1k/amber-launcher/blob/main/'+(en?'docs/USER-GUIDE.md':'docs/zh-CN/USER-GUIDE.md')} target="_blank" rel="noopener noreferrer">{t('查看完整使用指南','Read the user guide')}<ArrowUpRight size={17}/></a></div>
   <div className="faq-list">{questions.map((q,i)=><details name="home-faq" key={i}><summary>{q.q[en?1:0]}<CaretDown size={20}/></summary><div className="faq-answer"><p>{q.a[en?1:0]}</p><a className="text-link" href={q.href}>{q.link[en?1:0]}<ArrowRight size={17}/></a></div></details>)}</div>
  </section>
  <section className="home-download wrap" aria-labelledby="ready-title"><div><span className="eyebrow">{t('即刻出发','READY WHEN YOU ARE')}</span><h2 id="ready-title">{t('开启你的下一段旅程。','Your next adventure awaits.')}</h2><p>{t('免费下载 AMBER，开始管理你的 Minecraft 世界。','Download AMBER for free and make room for your Minecraft worlds.')}</p></div><div className="final-action"><a className="button gold" href="#/download">{t('下载 AMBER','Download AMBER')}<DownloadSimple size={21}/></a><small>Windows · macOS · Linux · {t('免费开源','Free & open source')}</small></div></section>
 </div>;
}
