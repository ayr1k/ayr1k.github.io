import React from 'react';
import {ArrowUpRight,DownloadSimple,WindowsLogo,AppleLogo,LinuxLogo,TerminalWindow} from '@phosphor-icons/react';
import './downloads.css';

export function DownloadPage({en,product}) {
 const t=(zh,english)=>en?english:zh;
 const repo=`https://github.com/ayr1k/${product==='AMBER'?'amber-launcher':'AmberE'}`;
 const release=repo+'/releases/tag/v1.6.4';
 const file=name=>repo+'/releases/download/v1.6.4/'+name;
 const platforms=[
  {id:'windows',icon:WindowsLogo,title:'Windows',tag:t('已验证启动与界面','Startup & UI verified'),detail:t('x64 · 安装程序 EXE','x64 · EXE installer'),body:t('安装时可选择中英文。同产品覆盖安装保留游戏数据。','Choose Chinese or English during installation. Same-product upgrades retain game data.'),links:[['Windows x64',`${product}-1.6.4-Setup-x64.exe`]]},
  {id:'mac',icon:AppleLogo,title:'macOS',tag:t('待实机验证','Device testing pending'),detail:t('Intel / Apple Silicon · 应用 ZIP','Intel / Apple Silicon · App ZIP'),body:t('按芯片选择下载，解压后移入“应用程序”。未签名、未公证，Gatekeeper 可能阻止打开；尚未完成 Mac 实机和游戏验证。','Choose your chip, unzip, then move the app to Applications. Unsigned and not notarized; Gatekeeper may block it. Mac launch and gameplay have not been verified.'),links:[['Intel x64',`${product}-1.6.4-mac-x64.zip`],['Apple Silicon',`${product}-1.6.4-mac-arm64.zip`]]},
  {id:'linux',icon:LinuxLogo,title:'Linux',tag:t('部分验证','Partially verified'),detail:'x64 · Debian / Ubuntu · DEB',body:t('通过软件包管理器安装依赖，并配置可用的桌面密钥库。Ubuntu/WSL 已验证运行环境、地图和 Java 安装；完整桌面、账号加密与游戏仍需实测。','Install dependencies with your package manager and configure a desktop keyring. Runtime, map and Java installation were checked in Ubuntu/WSL; full desktop, credential encryption and gameplay still need testing.'),links:[['Linux x64',`${product}-1.6.4-linux-x64.deb`]]},
  {id:'freebsd',icon:TerminalWindow,title:'FreeBSD',tag:t('实验包 · 服务端与工具','Experimental · Servers & tools'),detail:'amd64 · TAR.GZ',body:t('暂不支持 Minecraft 游戏客户端，未做 FreeBSD 实机验证。需系统提供 Electron、OpenJDK、密钥库及 C 编译器，并按包内说明构建地图程序。','Minecraft client launch is unavailable; no FreeBSD device testing has been done. Requires system Electron, OpenJDK, a keyring and a C compiler. Build the map helper using the included instructions.'),links:[[t('FreeBSD 实验包','FreeBSD experimental'),`${product}-1.6.4-freebsd-x64-experimental.tar.gz`]]}
 ];
 return <section className="page download-page">
  <span className="eyebrow">DOWNLOAD / 1.6.4</span>
  <h1>{t('选择你的版本，开始下一次冒险。','Choose your edition. Start your next adventure.')}</h1>
  <p className="lede">{t("1.6.4：新增默认关闭的启动前保守内存整理，仅作用于启动器主进程，提供等待上限、共享冷却及跳过整理／取消整个启动的独立反馈。","1.6.4: Add optional, default-off conservative trimming of the launcher main process before Minecraft starts, with bounded waiting, shared cooldown and separate skip/whole-launch cancellation feedback.")}</p>
  <nav className="edition-switch" aria-label={t('产品版本','Product edition')}>
   {['AMBER','AmberE'].map(name=><a key={name} href={'#/download'+(name==='AmberE'?'?product=ambere':'')} aria-current={product===name?'page':undefined}>{name}</a>)}
  </nav>
  <div className="download-main"><div><h2>{product} <span>1.6.4</span></h2><p>{product==='AMBER'?t('微软登录、正版资格验证与已验证离线身份。','Microsoft sign-in, ownership verification and verified offline identities.'):t('独立的离线与第三方账号版本，不提供微软登录。','Independent offline and third-party edition, without Microsoft sign-in.')}</p></div><span className="release-label">{t('免费开源 · 未签名','Free & open source · Unsigned')}</span></div>
  <div className="platform-downloads">
   {platforms.map(p=><section className="platform-download" key={p.id} data-platform={p.id} aria-labelledby={'platform-'+p.id}>
    <div className="platform-heading"><p.icon size={30}/><div><h3 id={'platform-'+p.id}>{p.title} <small>{'1.6.4'}</small></h3><span>{p.detail}</span></div></div>
    <div className="platform-description"><span className="platform-status">{p.tag}</span><p>{p.body}</p></div>
    <div className="platform-actions">{p.links.map(([label,name])=><a className="button green" key={name} href={file(name)}><DownloadSimple size={19}/>{label}</a>)}</div>
   </section>)}
  </div>
  <div className="download-links">
   {[[t('发布说明','Release notes'),release],[t('完整源码','Full source'),file(`${product}-1.6.4-source.zip`)],['SHA-256',file('SHA256SUMS.txt')],[t('平台安装说明','Platform setup'),repo+'/blob/v1.6.4/prototype/PLATFORMS-1.3.5.md']].map(([label,url])=><a key={label} href={url} target="_blank" rel="noreferrer">{label}<ArrowUpRight size={18}/></a>)}
  </div>
  <div className="install-notes"><h3>{t('安装与升级','Installing and upgrading')}</h3><ul>
   <li>{t('升级前保存并停止服务端、关闭游戏与启动器，并备份重要存档。','Save and stop servers, close games and the launcher, and back up important worlds before upgrading.')}</li>
   <li>{t('全部包未签名；请核对 GitHub Releases 来源和 SHA-256。macOS 包也未公证。','All packages are unsigned. Verify the GitHub Releases source and SHA-256. macOS packages are also not notarized.')}</li>
   <li>{t('AMBER 与 AmberE 使用独立数据目录；账号加密记录不能直接跨系统迁移，请在新系统重新登录。','AMBER and AmberE use separate data directories. Encrypted account stores are not portable across operating systems; sign in again on the new system.')}</li>
  </ul></div>
  <a className="text-link" href={repo+'/releases'}>{t('查看历史版本','Browse previous releases')}<ArrowUpRight size={18}/></a>
 </section>;
}
