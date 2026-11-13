# AMBER website / AMBER 官网

[官方网站 / Website](https://ayr1k.github.io/) · [官方主题商城 / Official theme store](https://ayr1k.github.io/#/themes)

AMBER 与 AmberE 的双语产品网站，提供功能介绍、使用帮助和 1.3.5 正式版下载。主页沿用深绿、琥珀配色与真实产品截图，使用自由滚动；功能与帮助页以阅读为主，不启用滚动吸附。

A bilingual website for AMBER and AmberE, with features, guides and stable 1.3.5 downloads. The homepage uses a forest-green/amber palette and actual product screenshots. All pages scroll freely, without scroll snapping.

## 本地开发 / Local development

Requires Node.js and pnpm. Run in this directory:

```sh
pnpm install --frozen-lockfile
pnpm dev --host 127.0.0.1 --port 4188
```

## 发布 / Deployment

```sh
pnpm build
pnpm test:sites
```

`ayr1k/ayr1k.github.io` 的 `main` 分支通过 `.github/workflows/pages.yml` 自动构建并发布 `dist/client`。Hash 路由不依赖服务器重写。不要上传 node_modules、.qa 或本地账户数据。

The main branch of `ayr1k/ayr1k.github.io` deploys `dist/client` through the Pages workflow. Hash routing needs no server rewrite rules. Local dependencies and development profiles are excluded.

## 主题商城 / Theme store

- `#/themes`：官方主题目录、真实预览、大图查看、下载和 SHA-256；所有网站内的 .ambtheme 下载按钮集中在这里。
- `#/themes/help`：安装与制作帮助，双语帮助 ZIP、Schema 与示例 JSON。保留旧静态文件地址供已有链接使用，但不在其他页面重复展示主题下载按钮。
- `src/theme-catalog.js`：主题目录数据。未来新增主题只需添加一个条目及对应文件，不必重写页面或加入占位商品。
- `src/ThemeStore.jsx`、`src/theme-store.css`：商城、响应式主题列表与可键盘关闭的预览弹窗。
- `public/themes`：官方主题、每个主题的 `.sha256`、真实预览图和制作参考文件。

`#/themes` is the single storefront for all in-site .ambtheme download buttons. `#/themes/help` contains authoring guidance and reference files. Old static addresses remain available for existing links. Add future themes through `src/theme-catalog.js`; the responsive grid expands automatically without placeholder products.

添加主题时提供唯一 id、中英文名称/简介/特点、主题版本、最低客户端版本、准确大小、版本化文件名和实机预览图。附上同名 `.sha256`，更新 `public/themes/SHA256SUMS.txt`；核对图片许可，确保截图不包含真实账户、私人存档或路径。

Each entry needs an id, bilingual copy and tags, theme/minimum-client versions, accurate size, a versioned package and an actual application preview. Include its `.sha256`, refresh the checksum list and verify asset permissions. Use demonstration data, never private account or save data.

Alloy、Nocturne、Harvest（秋野）与 Verdant（青岚）预览来自 AMBER 1.2.1 发布构建及隔离的演示实例。主题独立下载，不预置，均兼容 AMBER 与 AmberE 1.2.1。秋野采用左侧导航与右侧标签分区，青岚采用顶部导航与下方日历／新闻分区。较矮窗口通过分区滚动查看更多内容。主页的经典外观示意保留自 1.2.0；品牌与 Sarasa 字体许可随素材保留。

Alloy, Nocturne, Harvest and Verdant previews show the AMBER 1.2.1 release build with isolated demonstration instances. All four are separate downloads for AMBER and AmberE 1.2.1. Harvest uses left navigation and right-side tabs; Verdant uses top navigation and a lower calendar/news band. Shorter windows use section scrolling for additional content. The classic appearance illustration on home remains from 1.2.0. Brand and Sarasa font notices are retained.

Sky（晴空）与 Bloom（樱序）为白蓝与白粉浅色主题，适配 AMBER / AmberE 1.5.3。预览来自 1.5.3 实际界面及隔离的演示实例；已在两款产品中验证导入、保存恢复和五种窗口尺寸。商城使用用户验收过的原始主题包，仅将下载文件名移除 `-preview`，包内容与 SHA-256 不变。

Sky and Bloom add white/pale-blue and white/pink themes for AMBER / AmberE 1.5.3. Previews show the actual 1.5.3 interface with isolated demonstration data. Import, persistence, recovery and five window sizes were checked in both products. Published packages preserve the user-accepted bytes; only the download filenames lose the `-preview` suffix. The preview dialog reports the capture version per theme.

Harvest、Verdant、Sky 与 Bloom 的背景为艺术化生成插画，非游戏实拍。主题配置采用 MPL-2.0，背景在适用权利范围内采用 CC BY 4.0，详见各主题包内的 LICENSE.txt。

Harvest, Verdant, Sky and Bloom backgrounds are generated artwork, not in-game captures. Theme configuration uses MPL-2.0; background artwork is offered under CC BY 4.0 to the extent rights apply. See LICENSE.txt in each package.

## 内容维护 / Content maintenance

`src/App.jsx` controls routes, bilingual feature/help copy and pinned release links. `src/Home.jsx` contains the homepage and FAQ. Update both products' installer/source/tag links when releasing. Theme files are static downloads; no account, checkout or third-party API is needed.

增加文案后可用 `python scripts/subset-fonts.py 原始字体目录` 重建字体子集；原始目录须包含 SarasaUiSC-Regular.woff2 和 SarasaUiSC-Bold.woff2，需 fonttools 与 brotli。缺失字形仍有系统字体回退。

Language and reduced-motion preferences are saved locally. The site has no analytics, account collection or submission forms. Rebuild font subsets after adding copy using `scripts/subset-fonts.py` with the original Sarasa fonts; system fallback remains available.

1.2.2: `#/features/downloads` introduces source selection, pause/resume and diagnostics. Theme files keep their existing versions and remain compatible. / 新增下载与恢复功能页；主题文件版本与兼容性保持不变。

1.2.3: `#/features/modpacks` explains local MRPACK/content ZIP import, format differences and restart recovery. / 新增本地整合包导入说明，解释格式区别与重启恢复。下载页同步 1.2.3，主题文件保持原样。

1.3.0: `#/features/workspace` covers avatars, screenshots, dependency views, the tabbed editor and gradient text. Both editions now link to stable 1.3.0 installers, source archives and checksums. Existing theme assets are unchanged. / 新增可视化与编辑功能说明；双版下载、源码及校验链接同步 1.3.0，主题资源保持原样。

1.3.5: stable paired downloads and selection-based gradient formatting guidance; theme files remain unchanged. / 双版正式下载及渐变选区格式说明同步更新，主题文件不变。

## 1.3.5 platform downloads / 多平台下载

`src/DownloadPage.jsx` lists Windows x64 EXE, macOS Intel/Apple Silicon ZIP, Linux x64 DEB and FreeBSD amd64 experimental bundles for both editions. Download URLs are version-pinned. Preserve visible validation labels, unsigned/notarized status and FreeBSD server/tools-only scope. Source/checksum links are product-specific. Deployment follows public release-asset verification.

## 1.3.6 publication

Windows downloads, source and checksums point to 1.3.6; macOS/Linux/FreeBSD stay on explicitly labelled 1.3.5 assets and retain their verification limits.

## 1.4.0 publication

Windows installer/source/checksum links target 1.4.0. macOS/Linux/FreeBSD remain explicitly labelled 1.3.5.

## 1.4.1 publication
All platform downloads, full source and checksums target 1.4.1 for both products. Preserve platform validation limits.

## 1.4.2 publication
All product/platform download, source and checksum links target 1.4.2. The page describes Quilt/Fabric content compatibility and Sakura Frp. Preserve platform validation limits, public theme assets and AmberX links. Deploy after both releases and their assets are public.

## 1.4.3 publication
All product/platform downloads, source and checksum links target 1.4.3. Download concurrency, server recycling and themed tool fixes are described in both languages. Deploy after both public releases; preserve theme assets and AmberX links.

## 1.4.4 publication
Paired all-platform downloads, source/checksums and bilingual server update, performance and bandwidth notes. Deploy after both stable releases. Theme assets and AmberX are unchanged.

## 1.4.5 publication
Paired all-platform downloads, source/checksums and bilingual screenshot viewer/server launch notes. Deploy after both stable releases. Theme assets and AmberX are unchanged.

## 1.4.6 publication
Paired all-platform download/source/checksum links and bilingual onboarding/import/feedback notes. Deploy after both stable releases are public.

## 1.4.7 publication
Paired all-platform downloads, full source/checksums and bilingual tray/server-scheduling notes. Deploy after both stable releases are public.

## 1.4.8 publication
Paired all-platform downloads, source/checksums and bilingual startup/large-download notes. Deploy after both stable releases are public.

## 1.5.0 publication
Paired all-platform downloads, source/checksums and bilingual instance-services/account-tools notes. Deploy after both stable releases are public. MySQL remains an optional Windows x64 component.

## 1.5.1 publication
Paired all-platform downloads, source/provenance/checksums and bilingual existing-installation import notes. Deploy after both stable releases are public.

## 1.5.2 publication
Paired all-platform downloads, source/provenance/checksums and bilingual room client synchronization notes. Deploy after both stable releases are public.

## 1.5.3 publication
Paired all-platform downloads, source/provenance/checksums and bilingual expanded room sharing/recovery notes. Deploy after both stable releases are public.

## 1.5.4 publication
Paired all-platform downloads, source/provenance/checksums and bilingual protected storage maintenance and filtered-list notes. Deploy after both stable releases are public. Preserve all six theme packages, previews and catalog versions.

## 1.6.0 publication
Paired all-platform downloads, source/provenance/checksums and bilingual launch-plan, component-choice and scoped memory notes. Deploy after both stable releases are public. Preserve all six theme packages, previews and catalog versions.

## 1.6.1 publication
Paired all-platform downloads, source/provenance/checksums and bilingual map/gradient/editor notes. Deploy after both stable releases are public. Preserve all six theme packages, previews and catalog versions.

## Independent artist themes
The store separates six official themes from independently credited artist artwork. Woodland Reverie II preserves the user-accepted v2 package unchanged. Artwork: Yaoaoin (CC BY-NC, version unspecified), with specific theme-background permission reported by the project owner. Theme design: AMBER. Public attribution notes distinguish the earlier local-review stage from this authorized publication.

## 1.6.2 publication
Paired all-platform downloads, source/provenance/checksums and bilingual structure-navigation/marker/scan-status notes. Deploy after both stable releases are public. Preserve six official themes and the independent artist collection, including all accepted package bytes and credits.

## 1.6.3 publication
Paired all-platform downloads, source/provenance/checksums and bilingual instance-editor comparison, backup and session-draft notes. Deploy after both stable releases are public. Preserve all seven theme packages, independent artist attribution and permanent community acknowledgements.

## 1.6.4 publication
Paired all-platform downloads, source/provenance/checksums and bilingual default-off prelaunch memory/cancellation notes. Deploy after both stable releases are public. Preserve all seven themes, independent artist attribution and permanent community acknowledgements.

## 1.7.0 publication
Paired all-platform downloads, source/provenance/checksums and bilingual initial-storage/multiple-library/external-recovery notes. Deploy after both stable releases are public. Preserve all seven themes, artist attribution and permanent acknowledgements, including @岩熵 (UID 1616300586).

## 1.7.1 publication
Paired all-platform downloads, source/provenance/checksums and bilingual native-library routing/layout repair notes. Deploy after both stable releases are public. Preserve all seven themes, artist attribution and permanent community acknowledgements.

## 1.7.2 publication
Paired all-platform downloads, source/provenance/checksums and bilingual server-address copy/theme-store shortcut notes. Deploy after both stable releases are public. Preserve all seven themes, artist attribution and permanent community acknowledgements.
