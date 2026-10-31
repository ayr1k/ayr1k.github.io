# AMBER website

AMBER 的独立产品网站，提供中文和英文页面。主页包含森林首屏、功能入口和产品分支介绍；功能页采用普通滚动；下载页提供 AMBER / AmberE 安装包、源码和校验文件入口。

## 本地运行

需要 Node.js 和 pnpm。在本目录执行：

```sh
pnpm install --frozen-lockfile
pnpm dev --host 127.0.0.1 --port 4188
```

打开 `http://127.0.0.1:4188/`。

## 静态发布

```sh
pnpm build
pnpm test:sites
```

GitHub Pages 只需要发布 **dist/client** 内的内容。站点使用相对资源路径和 hash 路由，可放在用户主页或项目子目录，不需要服务器重写规则。部署前将 GitHub Pages 的产物目录设为 dist/client；不上传 node_modules、.qa 或 dist/server。

网站地址：https://ayr1k.github.io/ 。网站源码独立维护在 ayr1k/ayr1k.github.io，main 分支更新后由 GitHub Actions 自动构建并部署到 Pages，也可在 Actions 手动运行。

## 内容维护

- `src/App.jsx`：中英文文案、路由、功能说明、产品分支与 Release 下载地址。
- `src/styles.css`：排版、响应式和动效。
- `public/assets`：品牌、森林视觉、产品界面插图和本地字体。
- `index.html`：页面基础描述与主题色。

更新版本时同步更新首页版本号、下载页标签、两个产品的 Release tag 和安装包／源码包文件名。下载链接采用固定版本，不依赖第三方请求或访问者的 GitHub API 限额。

主页在所有尺寸使用自由滚动，保留轻量视差和入场效果，不再自动吸附或归位。功能页始终使用普通滚动。页脚“减少动画”选项本地保存，并默认遵循操作系统偏好。语言偏好也只保存在本机，没有统计追踪、登录或表单收集。

## 视觉素材

品牌沿用项目现有素材。森林为本网站制作的氛围插图。产品图通过现有 1.0 组件和示例实例渲染，标注为“界面示意”，没有使用真实用户账号或存档。Sarasa 字体许可随素材保留。

字体按现有文案生成子集。增加文案后，可安装 Python 的 fonttools 与 brotli，然后执行 `python scripts/subset-fonts.py 原始字体目录` 更新；原始目录需包含 SarasaUiSC-Regular.woff2 和 SarasaUiSC-Bold.woff2。缺失字形仍有系统字体回退。

---

Independent AMBER product website with Chinese and English copy. Run `pnpm install --frozen-lockfile` and `pnpm dev`; build with `pnpm build`. Publish only `dist/client` to GitHub Pages. Relative assets and hash routing support both account and project sites. Live site: https://ayr1k.github.io/ . Pushes to main build and deploy through GitHub Actions; manual deployment is also available.

Release URLs are explicitly versioned in `src/App.jsx`. Language and reduced-motion preferences stay in local storage. The site does not collect accounts, forms or analytics. The product illustration uses the existing 1.0 interface with example data.





