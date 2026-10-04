# 设置页草稿保护 / Unsaved settings protection

## 中文

设置页会统一跟踪普通配置、模型渠道和调度开关的未保存草稿，包括暂时无效的渠道名称。切换设置分类会保留这些局部编辑。

- 刷新、关闭标签页或通过站内链接和浏览器前进/后退离开时，未保存草稿会触发确认
- 取消离开保留草稿；确认放弃会清理所有草稿，并继续前往原目标地址
- 重置会同时恢复普通配置、模型渠道和调度本地覆盖；模型渠道仍通过独立保存按钮提交
- 模型保存及后续刷新进行中，重置、导入和站内确认离开需等待完成；已经发出的保存请求不会因离开页面而撤销
- 导入环境备份前也检查隐藏分类中的草稿；取消导入确认保留编辑

浏览器决定原生刷新/关闭提示的文案与显示条件，通常需要页面上已有用户交互；强制终止浏览器等情况无法保证弹窗。草稿只保留在当前页面内存中，不提供自动保存或跨刷新恢复。

## English

Settings tracks unsaved generic configuration, model-channel edits, and scheduler overrides, including temporarily invalid channel names. Switching categories retains these local drafts.

- Refresh, tab close, in-app links, and browser Back/Forward warn before discarding unsaved edits
- Cancel preserves drafts; confirmed discard clears all draft owners and continues to the original destination
- Reset restores generic fields, model channels, and local scheduler overrides; model channels retain their separate Save button
- While a model save or its subsequent refresh is pending, Reset, Import, and in-app departure confirmation wait for completion; leaving cannot cancel a request already sent
- Backup import also checks drafts hidden in other categories; cancelling its confirmation preserves those edits

Native unload wording and display conditions are controlled by the browser and generally require prior user interaction. A forced browser termination cannot guarantee a prompt. Drafts live only in the current page's memory; this feature does not autosave or restore them after a refresh.
