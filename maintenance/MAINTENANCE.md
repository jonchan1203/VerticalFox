# VerticalFox Maintenance Guide / 维护手册

> **语言**: 中文正文 + [English Summary](#english-summary)(文末)
> **适用**: Firefox 157+ / Sidebery 5.6.x / Windows(脚本;方法论跨平台)
> **状态**: 上游(christorange/VerticalFox)已停止维护,本仓库为社区延续版本。
> 最近一次适配:**Firefox Developer Edition 157.0**(2026-09),详见第 3 节。

---

## 1. 背景与现状

VerticalFox 通过 `userChrome.css` + Sidebery 实现 Edge 风格自动隐藏垂直标签栏。
Firefox 大版本更新会频繁重构浏览器 chrome 的 DOM/CSS,导致主题失效。本项目
核心资产是三部分:

1. `windows/userChrome.css` — 浏览器 chrome 主题(含 **Fx157 兼容补丁段**,文件末尾注释块)
2. `windows/user.js` — **必须**随主题一起部署到 profile 根目录(Fx157 硬性要求,见 3.1)
3. `sidebery/sidebery_styles.css` — 粘贴进 Sidebery 设置 → Styles editor(或用脚本自动写入,见 4.2)

## 2. 环境档案(通用化)

| 项目 | 值 / 获取方式 |
|---|---|
| Profile 路径 | `about:profiles` 或 `%APPDATA%\Mozilla\Firefox\Profiles\<profile>`;下文记作 `<profile>` |
| userChrome 开关 pref | `toolkit.legacyUserProfileCustomizations.stylesheets = true`(`user.js` 已内置) |
| Sidebery 版本 | 5.6.x,扩展 ID `{3c078156-979c-498b-8990-85f7987dd929}`(AMO 公开 ID,各机相同) |
| Sidebery UUID | 每个 profile 不同,**从 `<profile>/prefs.js` 的 `extensions.webextensions.uuids` 读取**(`deploy_sidebery_css.py` 已自动完成) |
| 扩展 storage.local 位置 | **Firefox ~14x 起** `browser-extension-data/<id>/storage.js` 已废弃,改用 LSNG:`<profile>/storage/default/moz-extension+++<uuid>/ls/data.sqlite` |
| 浏览器 chrome DOM/CSS 真源 | `<firefox>/browser/omni.ja`(优化 zip,**用 7z 读,Python zipfile 会报 BadZipFile**) |
| 主题对 Fx 的关键 pref | `sidebar.verticalTabs=true`(必须有)、`sidebar.visibility=always-show`(推荐) |

## 3. Firefox 157 破坏点与修复原理

> 未来 Fx158+ 失效时,按第 7 节方法论重新 diff omni.ja,大概率仍是同类问题。

### 3.1 旧侧边栏系统整体废弃(最关键)

`browser-shared.css`(omni.ja 内)新增:

```css
@media not -moz-pref("sidebar.verticalTabs") {
  #sidebar-container, #sidebar-launcher-splitter, #sidebar-box, #sidebar-splitter { display: none; }
}
```

**即:`sidebar.verticalTabs=false` 时 `#sidebar-box` 根本不存在,Sidebery 无处显示。**
修复:`windows/user.js` 强制 `sidebar.verticalTabs=true` + `sidebar.visibility=always-show`
(后者防止 Firefox 自己的 "expand-on-hover / hide-on-close" 逻辑收起面板)。

### 3.2 新侧边栏 DOM 结构(157)

```
#browser
├─ #sidebar-container            ← 仅包启动器,整体 display:none
│   └─ <html:sidebar-main>       ⚠ 自定义标签名,**没有 id**,#sidebar-main 选择器无效
│       └─ #vertical-tabs        原生垂直标签容器(slot="tabstrip")
├─ #sidebar-launcher-splitter    ← display:none
└─ #sidebar-box                  ← 主题的 40px 收缩条 + overlay 悬停展开作用于此
    ├─ #sidebar-header           仍存在;主题继续隐藏它
    └─ stack.sidebar-browser-stack
        └─ browser#sidebar       ⚠ 不再是 #sidebar-box 的直接子元素!
```

修复要点(见 `userChrome.css` 补丁段 2/3/4/5):
- 隐藏 `#sidebar-container` + `#sidebar-launcher-splitter`(而非 `#sidebar-main`)
- 悬停展开规则必须用**后代选择器** `#sidebar-box:hover #sidebar`
- 补 `overflow: visible` 防 `#sidebar-container` 等新容器裁剪 overlay

### 3.3 扩展面板头部移入面板文档内

`webext-panels.xhtml` 末尾新增 `<html:sidebar-panel-header id="sidebar-panel-header"/>`,
即 "Sidebery ✕" 标题行渲染在 `#sidebar` 浏览器元素**内部**,chrome 的 `#sidebar-header`
隐藏规则管不到它。修复:补丁段 7 直接 `#sidebar-panel-header { display:none }`
(userChrome.css 同样作用于 chrome 内容文档)。

### 3.4 urlbar 重构为 `moz-urlbar` 自定义元素

旧主题大量使用 `#urlbar-background` / `#urlbar-input-container` **ID** 选择器;
157 中它们变成 **class**(`div.urlbar-background` / `div.urlbar-input-container`),
所有旧规则静默失效。另外 Dev Edition 默认主题在 `.urlbar-background` 上画
`repeating-linear-gradient(-45deg, …)` 红色斜条纹。修复:补丁段 9 按 class 重写
背景/圆角/聚焦/展开样式,并 `background-image:none` 去纹理。

### 3.5 其他确认点

- `#appcontent` 已不存在 → 主题中 `#appcontent #statuspanel` 等规则为死代码(无害)
- 窗口控制按钮:`#nav-bar .titlebar-buttonbox-container` 存在且可用绝对定位钉到右上
  (补丁段 6);垂直标签模式下按钮可能被移进已隐藏的启动器,强制 nav-bar 副本可见
- 原生 `.tabbrowser-tab` 折叠规则对垂直标签同样生效(它们就是同一批元素),与目标一致

## 4. 部署

### 4.1 自动(推荐,Windows)

```powershell
cd maintenance
.\deploy.ps1 -Profile "<profile 路径>" -Launch
```

自动完成:Firefox 优雅关闭 → `backup.ps1` 备份 → 复制 `userChrome.css`+`user.js` →
`deploy_sidebery_css.py` 写入 Sidebery 样式 → 启动。

### 4.2 手动

1. 关闭 Firefox;
2. 备份 `<profile>/chrome/userChrome.css`、`prefs.js`、LSNG `data.sqlite`;
3. 复制 `windows/userChrome.css` → `<profile>/chrome/`(没有 chrome 目录则新建,小写);
4. 复制 `windows/user.js` → `<profile>/` 根目录;
5. Sidebery 样式二选一:
   - 脚本:`python maintenance/deploy_sidebery_css.py --profile <profile>`
   - 手动:启动 Firefox → Sidebery 设置 → Styles editor → 粘贴 `sidebery/sidebery_styles.css` 全文
6. 启动 Firefox 验证。

### 4.3 Sidebery 侧要求

- Sidebery ≥ 5.x;"Navigation bar in one line" 在 5.6.1 中为默认值
  (`navBarLayout: "horizontal"` + `navBarInline: true`),无需手动设置
- 主题 CSS 依赖的 Sidebery 存储 key 是 **`sidebarCSS`**(Styles editor 内容)

## 5. 自动化测试

```powershell
# 行为断言:收缩 40px → 悬停 260px overlay 且页面不推挤 → 回缩
python maintenance/hovertest.py --profile <profile>
```

原理:Marionette 驱动 + Win32 `SetCursorPos` 模拟悬停 + chrome 上下文读取
`#sidebar`/`#sidebar-box`/`#tabbrowser-tabbox` 的 `getBoundingClientRect` 断言。
输出 `AUTO-HIDE+EXPAND: PASS | PAGE NOT PUSHED: PASS` 即通过。

其他检查项(启动后人工/截图):横向标签栏消失、收缩条仅 favicon、
窗口控制按钮在右上、地址栏为干净药丸、深浅色跟随系统。

## 6. Marionette 调试指南(chrome 特权脚本)

```powershell
# 1) 带远程调试启动(必须 -remote-allow-system-access,否则 SetContext(chrome) 报错)
firefox.exe -no-remote -profile <profile> -marionette -remote-allow-system-access

# 2) 各类探针(见 probe.py 文件头)
python maintenance/probe.py static                 # 几何+计算样式全景
python maintenance/probe.py point 20 500 1200 20   # elementFromPoint 祖先链(定位"谁在画")
python maintenance/probe.py pseudo "#nav-bar"      # 伪元素背景(纹理常藏在这)
python maintenance/probe.py urlbar                 # urlbar 内部 DOM 及背景
python maintenance/probe.py panel                  # 面板文档内的 sidebar-panel-header
python maintenance/probe.py drawwindow out.png     # Firefox 自绘帧(见 7.3)
```

协议要点(protocol 3):帧格式 `<长度>:<JSON>`;命令 `[0,id,name,params]`;
响应 `[1,id,error,result]`;脚本必须显式 `return`;`sandbox:"system"` 已不支持,
特权执行一律走 `Marionette:SetContext → chrome`。

## 7. 调试方法论与陷阱(本次实战总结)

1. **哨兵规则二分**:在 userChrome.css 末尾加高可见度规则(如 `#nav-bar{background:#f00!important}`)
   确认文件是否整体加载;再按段插桩定位"从哪条规则开始失效"。
2. **elementFromPoint 定位绘制者**:截图上可疑像素处,chrome 上下文 `elementFromPoint(x,y)`
   拿祖先链 + computed style。注意:web 页/扩展页内部命中的是 `browser#sidebar` 一层。
3. **`ctx.drawWindow` 是 chrome UI 真相**:OS 截图(GDI)在高 DPI 下坐标被虚拟化
   (本例 dpr=2,像素与 CSS px 比例漂移),且 DWM/窗口边框会引入伪影(左缘"黄条"即
   边框区域误入截图)。`drawwindow.py` 用 Firefox 自己的合成器输出,所见即主题所绘。
4. **读 omni.ja 用 7z**:`7z e <firefox>/browser/omni.ja <内部路径> -so`;远程代理相关模块
   (marionette driver)在**安装根目录**的 omni.ja 而非 browser 下。查破坏点 = 在
   `browser.xhtml`/`browser-shared.css`/`browser.css` 里 grep 目标 id。
5. **读扩展 XPI 找存储键**:`python` + `zipfile` 直接内存读 `extensions/<id>.xpi`,
   grep `storage.local.get/set` 即可确认 `sidebarCSS` 等键名,不必解压。
6. **无效规则是静默的**:ID→class 重构(如 urlbar)不会报错,只会"样式悄悄消失";
   全景探针 `probe.py static`/`urlbar` 配合哨兵法最快定位。

## 8. 已知误报与未决事项

**误报(不要当 bug 修)**:
- 地址栏红色斜纹 = Dev Edition 默认主题的 urlbar 纹理(已由补丁段 9 清除);
  `about:profiles` 页面头部自带同款装饰,那是页面内容,不是 chrome。
- 截图左缘黄色细条 = 窗口边框/DWM 区域混入截图,非渲染缺陷(用 drawwindow 验证)。

**未决/低优先**:
- `userChrome.css` 中 `.Tab .lvl-wrapper:*` 规则在 Sidebery 5.6.1 已失效
  (5.6.1 无该元素;树状缩进线改由 `.Tab[data-pin=false]:not([data-lvl="0"]) .body:after`
  的多重 box-shadow + `--tabs-indent` 实现,折叠态已被 `--tabs-indent:-1000px` 推出屏外)。
  留着无害,但别指望它生效。
- `.toolbar-items { visibility: collapse }` 是全局规则,若未来 nav-bar 结构套用同名
  class 会误伤,升级时留意。
- 主题内 `#appcontent`/`#urlbar-background` 等 ID 选择器为死代码,可择机清理。

## 9. 回滚

- **主题文件**:修改前版本在 git 历史(适配前最后一次提交)——
  `git show <适配前commit>:windows/userChrome.css > <profile>/chrome/userChrome.css`;
  或用 `backup.ps1` 的输出(注意默认输出在 `%TEMP%`,会被系统清理,重要回滚点请 `-Out` 到持久目录)。
- **Sidebery 样式**:重新跑 `deploy_sidebery_css.py` 覆盖,或设置界面手动清空 Styles editor。
- **prefs**:`user.js` 每次启动都会重新应用;删除 `user.js` 并在 `about:config` 重置
  `sidebar.verticalTabs` / `sidebar.visibility` 即恢复 Firefox 默认行为。
- 完整 profile 级恢复:使用 Firefox 自带的 "About Profiles → Refresh" 或系统快照。

---

## English Summary

VerticalFox (auto-hiding vertical tabs via Sidebery) was re-adapted for **Firefox 157**;
upstream is unmaintained, this repo carries the fixes.

**Deploy**: close Firefox → run `maintenance/deploy.ps1 -Profile <profile>` (backs up,
installs `windows/userChrome.css` + `windows/user.js` into the profile, injects
`sidebery/sidebery_styles.css` into Sidebery's storage, optional `-Launch`).
Manual steps and the storage format (LSNG sqlite key `sidebarCSS`) are in §4.

**Why 157 broke the theme** (§3): (1) the legacy sidebar `#sidebar-box` is `display:none`
unless `sidebar.verticalTabs=true` — `windows/user.js` enforces it; (2) the new launcher
is `<html:sidebar-main>` — a tag without an id, so hide `#sidebar-container` instead;
(3) `browser#sidebar` is no longer a direct child of `#sidebar-box` — hover-expand rules
need descendant selectors + `overflow:visible`; (4) the extension-panel header is now
rendered *inside* the panel document (`#sidebar-panel-header`) — hidden via patch §7;
(5) urlbar internals became classes (`div.urlbar-background`) and Dev Edition paints a
striped texture there — rewritten in patch §9.

**Debugging** (§6–7): launch with `-marionette -remote-allow-system-access`, then use
`probe.py` (static geometry / elementFromPoint / pseudo-elements / urlbar walk),
`drawwindow.py` (Firefox-side canvas capture — immune to DPI/DWM screenshot artifacts),
and read `omni.ja` with 7-Zip to diff the real DOM/CSS. Sentinel CSS rules help bisect
which part of `userChrome.css` still applies.

**Known non-bugs**: red urlbar stripes = Dev Edition texture (fixed) / about:profiles
page decoration; yellow left edge = window-frame capture artifact. Dead rules kept
harmlessly: `.lvl-wrapper` (removed in Sidebery 5.6.1), `#appcontent`, `#urlbar-background`.
