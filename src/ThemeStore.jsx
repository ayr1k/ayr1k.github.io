import React, {useEffect, useRef, useState} from 'react';
import {ArrowDown, ArrowUpRight, DownloadSimple, MagnifyingGlassPlus, X} from '@phosphor-icons/react';
import {officialThemes} from './theme-catalog.js';
import './theme-store.css';

const resource=name=>`${import.meta.env.BASE_URL}themes/${name}`;

function Preview({theme,en,onClose}) {
 const ref=useRef(null);
 useEffect(()=>{
  const dialog=ref.current,previous=document.activeElement;
  const overflow=document.body.style.overflow;
  dialog.showModal();document.body.style.overflow='hidden';
  return ()=>{dialog.close();document.body.style.overflow=overflow;previous?.focus();};
 },[]);
 const title=en?theme.name:theme.nameZh;
 return <dialog ref={ref} className="theme-preview-dialog" aria-labelledby="preview-title" onCancel={e=>{e.preventDefault();onClose();}} onClick={e=>{if(e.target===e.currentTarget)onClose();}}>
  <div className="theme-preview-top"><h2 id="preview-title">{title}</h2><button autoFocus className="preview-close" onClick={onClose} aria-label={en?'Close preview':'关闭预览'}><X size={24}/></button></div>
  <img src={resource(theme.preview)} width="1280" height="840" alt={en?theme.alt:theme.altZh}/>
  <p>{en?`Captured in AMBER ${theme.previewVersion||theme.version} with demonstration data. Your instances and records will appear here.`:`使用演示数据在 AMBER ${theme.previewVersion||theme.version} 中截取。实际界面显示你自己的实例与记录。`}</p>
 </dialog>;
}

export function ThemeStore({en}) {
 const [preview,setPreview]=useState(null);
 const t=(zh,enText)=>en?enText:zh;
 return <section className="page theme-store">
  <div className="store-heading"><span className="eyebrow">AMBER / OFFICIAL THEMES</span><h1>{t('换个风景，继续冒险。','A new look. The same adventure.')}</h1><p className="lede">{t('官方主题商城。为 AMBER 与 AmberE 选择一套外观，或从它开始，调整成你的样子。','The official theme store. Find a look for AMBER and AmberE, then make it your own.')}</p>
   <div className="store-intro-links"><span>{t(`${officialThemes.length} 款官方主题 · 全部免费下载`,`${officialThemes.length} official themes · All free`)}</span><a href="#/themes/help">{t('安装与制作帮助','Installation & authoring guide')}<ArrowUpRight size={18}/></a></div>
  </div>
  <div className="theme-catalog">{officialThemes.map(theme=><article key={theme.id} className="theme-product" id={'theme-'+theme.id}>
   <button className="theme-preview-button" onClick={()=>setPreview(theme)} aria-label={t(`查看 ${theme.nameZh} 大图`,`Preview ${theme.name}`)}><img src={resource(theme.preview)} width="1280" height="840" alt={en?theme.alt:theme.altZh}/><span><MagnifyingGlassPlus size={19}/>{t('查看大图','View preview')}</span></button>
   <div className="theme-product-body"><div className="theme-product-heading"><h2>{en?theme.name:theme.nameZh}</h2><span className="theme-price">{t('免费','Free')}</span></div><p>{en?theme.description:theme.descriptionZh}</p><ul className="theme-tags" aria-label={t('主题特点','Theme features')}>{(en?theme.tags:theme.tagsZh).map(tag=><li key={tag}>{tag}</li>)}</ul>
    <div className="theme-specs"><span>AMBER / AmberE ≥ {theme.minVersion}</span><span>{t('主题版本','Theme version')} {theme.version}</span><span>{theme.size} · .ambtheme</span></div>
    <div className="theme-product-actions"><a className="button gold" href={resource(theme.file)} download><DownloadSimple size={20}/>{t('下载主题','Download theme')}</a><a className="theme-checksum" href={resource(theme.file+'.sha256')} download>SHA-256<ArrowDown size={16}/></a></div>
   </div>
  </article>)}</div>
  <div className="store-instructions"><div><span className="eyebrow">MAKE IT YOURS</span><h2>{t('下载之后，三步换装。','Three steps to a new look.')}</h2></div><ol><li><strong>{t('打开主题库','Open your theme library')}</strong><p>{t('设置 → 外观与主题 → 主题库。','Settings → Appearance & themes → Theme library.')}</p></li><li><strong>{t('导入 .ambtheme','Import the .ambtheme')}</strong><p>{t('选择下载的文件，无需解压。','Select your downloaded file. No extraction needed.')}</p></li><li><strong>{t('应用并确认','Apply and confirm')}</strong><p>{t('首次应用后确认显示正常，随时可以恢复原外观。','Confirm the first application looks right. Restore your previous appearance whenever you need.')}</p></li></ol></div>
  <div className="store-creator"><div><h2>{t('也可以，从自己的想法开始。','Or start with your own idea.')}</h2><p>{t('在软件内调整配色与布局，保存成自己的主题。这里会继续收录新的官方外观。','Adjust colors and layouts in the app and save your own theme. More official designs will join this collection.')}</p></div><div className="store-creator-links"><a href="#/themes/help">{t('阅读制作帮助','Read the authoring guide')}<ArrowUpRight size={18}/></a><a href={resource('AMBER-Theme-Starter.ambtheme')} download>{t('下载基础示例','Download the starter')}<ArrowDown size={18}/></a></div></div>
  {preview&&<Preview theme={preview} en={en} onClose={()=>setPreview(null)}/>}
 </section>;
}
