# 数据维护系统 - 前端 UI/UX 设计规范

## 🎨 设计原则

### 1. 一致性 (Consistency)
- **色彩系统**: 统一的主色调、辅助色、状态色
- **字体规范**: 统一的字号、字重、行高
- **间距系统**: 8px 基准网格系统
- **组件样式**: 统一的按钮、表单、卡片样式

### 2. 清晰性 (Clarity)
- **信息层级**: 明确的标题、副标题、正文层级
- **视觉反馈**: 悬停、点击、加载状态的明确反馈
- **错误提示**: 友好、具体的错误信息
- **状态标识**: 成功、警告、错误的颜色区分

### 3. 效率性 (Efficiency)
- **快捷操作**: 常用功能的快捷键支持
- **批量操作**: 支持多选和批量处理
- **智能默认**: 合理的默认值和自动填充
- **进度提示**: 长时间操作的进度展示

### 4. 响应式 (Responsiveness)
- **适配多端**: 支持桌面端、平板、移动端
- **弹性布局**: 自适应不同屏幕尺寸
- **触控优化**: 移动端友好的交互设计

---

## 🌈 色彩系统

### 主色调 (Primary)
```css
--primary-color: #409EFF;          /* 主要品牌色 */
--primary-light-3: #79BBFF;        /* 浅色变体 */
--primary-light-5: #A0CFFF;
--primary-light-7: #C6E2FF;
--primary-light-8: #D9ECFF;
--primary-light-9: #ECF5FF;
--primary-dark-2: #337ECC;         /* 深色变体 */
```

### 辅助色 (Secondary)
```css
--success-color: #67C23A;          /* 成功 */
--warning-color: #E6A23C;          /* 警告 */
--danger-color: #F56C6C;           /* 危险/错误 */
--info-color: #909399;             /* 信息 */
```

### 中性色 (Neutral)
```css
--text-primary: #303133;           /* 主要文字 */
--text-regular: #606266;           /* 常规文字 */
--text-secondary: #909399;         /* 次要文字 */
--text-placeholder: #C0C4CC;       /* 占位文字 */

--border-color: #DCDFE6;           /* 边框 */
--border-color-light: #E4E7ED;
--border-color-extra-light: #EBEEF5;

--background-color: #F5F7FA;       /* 背景 */
--background-color-light: #FAFAFA;
```

### 状态色应用
| 状态 | 颜色 | 应用场景 |
|------|------|----------|
| 成功 | #67C23A | 同步完成、质量优秀、数据完整 |
| 警告 | #E6A23C | 部分缺失、质量一般、需要注意 |
| 错误 | #F56C6C | 同步失败、质量差、严重缺失 |
| 信息 | #909399 | 待处理、未知状态 |

---

## 📐 间距系统

基于 8px 网格系统：

```css
--spacing-xs: 4px;     /* 超小间距 */
--spacing-sm: 8px;     /* 小间距 */
--spacing-md: 16px;    /* 中间距 */
--spacing-lg: 24px;    /* 大间距 */
--spacing-xl: 32px;    /* 超大间距 */
--spacing-xxl: 48px;   /* 特大间距 */
```

**应用示例**:
- 卡片内边距: `padding: var(--spacing-lg)`
- 表单项间距: `margin-bottom: var(--spacing-md)`
- 按钮组间距: `gap: var(--spacing-sm)`
- 页面区块间距: `margin-bottom: var(--spacing-xl)`

---

## 🔤 字体规范

### 字体家族
```css
--font-family-base: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, 
                    "Helvetica Neue", Arial, "Noto Sans", sans-serif;
--font-family-code: "SF Mono", Monaco, "Cascadia Code", monospace;
```

### 字号层级
```css
--font-size-xs: 12px;      /* 辅助文字 */
--font-size-sm: 13px;      /* 小文字 */
--font-size-base: 14px;    /* 正文 */
--font-size-md: 16px;      /* 小标题 */
--font-size-lg: 18px;      /* 标题 */
--font-size-xl: 20px;      /* 大标题 */
--font-size-xxl: 24px;     /* 特大标题 */
```

### 字重
```css
--font-weight-light: 300;
--font-weight-regular: 400;
--font-weight-medium: 500;
--font-weight-bold: 600;
```

### 行高
```css
--line-height-tight: 1.2;
--line-height-base: 1.5;
--line-height-loose: 1.8;
```

---

## 🧩 组件规范

### 1. 按钮 (Button)

**尺寸**:
- Small: height=32px, padding=0 15px, font-size=12px
- Default: height=40px, padding=0 20px, font-size=14px
- Large: height=48px, padding=0 24px, font-size=16px

**类型**:
- Primary: 蓝色背景，白色文字
- Success: 绿色背景
- Warning: 橙色背景
- Danger: 红色背景
- Default: 白色背景，灰色边框
- Text: 无边框，仅文字

**状态**:
- Normal: 正常状态
- Hover: 亮度提升 10%
- Active: 亮度降低 10%
- Disabled: 透明度 50%，不可点击

### 2. 卡片 (Card)

**样式**:
```css
.card {
  background: #FFFFFF;
  border-radius: 4px;
  box-shadow: 0 2px 12px 0 rgba(0, 0, 0, 0.1);
  padding: var(--spacing-lg);
}
```

**头部**:
- 标题: font-size=16px, font-weight=600
- 副标题: font-size=14px, color=#909399
- 操作按钮: 右对齐

### 3. 表格 (Table)

**样式**:
- 表头: background=#F5F7FA, font-weight=600
- 行高: 48px
- 斑马纹: 偶数行 background=#FAFAFA
- 悬停: background=#ECF5FF
- 边框: 1px solid #EBEEF5

**状态标识**:
- 使用 Tag 组件显示状态
- 成功: type="success"
- 警告: type="warning"
- 错误: type="danger"

### 4. 表单 (Form)

**标签**:
- 位置: 顶部对齐（移动端）或左侧对齐（桌面端）
- 宽度: 固定 120px 或自适应
- 必填标识: 红色星号 *

**输入框**:
- 高度: 40px (default), 32px (small)
- 圆角: 4px
- 边框: 1px solid #DCDFE6
- 聚焦: border-color=#409EFF, box-shadow

**验证提示**:
- 错误: 红色文字，图标 + 消息
- 位置: 输入框下方
- 动画: 淡入效果

### 5. 对话框 (Dialog)

**尺寸**:
- Small: width=400px
- Default: width=600px
- Large: width=800px
- Full: width=90%

**结构**:
- 头部: 标题 + 关闭按钮
- 内容: 滚动区域
- 底部: 操作按钮（右对齐）

---

## 📊 数据可视化规范

### 1. 图表颜色

**折线图/柱状图**:
- 系列1: #409EFF
- 系列2: #67C23A
- 系列3: #E6A23C
- 系列4: #F56C6C
- 系列5: #909399

### 2. 仪表盘

**质量评分**:
- 90-100: 绿色 (#67C23A)
- 70-89: 蓝色 (#409EFF)
- 50-69: 橙色 (#E6A23C)
- 0-49: 红色 (#F56C6C)

### 3. 进度条

**样式**:
- 高度: 8px
- 圆角: 4px
- 背景: #EBEEF5
- 前景: 根据百分比变色

---

## 🎭 交互规范

### 1. 加载状态

**骨架屏**:
- 用于列表、卡片等复杂内容
- 灰色脉冲动画

**Loading 遮罩**:
- 半透明黑色背景 (rgba(0,0,0,0.3))
- 居中旋转图标
- 可选文字提示

**按钮加载**:
- 禁用按钮
- 显示旋转图标
- 文字变为"加载中..."

### 2. 空状态

**元素**:
- 图标: 64x64px，灰色
- 标题: "暂无数据"
- 描述: 具体说明
- 操作按钮: "刷新"或"创建"

### 3. 错误状态

**Toast 提示**:
- 位置: 顶部居中
- 持续时间: 3秒
- 可手动关闭
- 类型: success/warning/error/info

**页面级错误**:
- 大号错误图标
- 错误标题
- 详细描述
- 重试按钮

### 4. 确认操作

**危险操作**:
- 二次确认对话框
- 红色按钮突出显示
- 明确说明后果
- 默认选中"取消"

---

## 📱 响应式断点

```css
/* 移动端 */
@media (max-width: 767px) {
  --container-padding: 16px;
  --sidebar-width: 0; /* 隐藏侧边栏 */
}

/* 平板 */
@media (min-width: 768px) and (max-width: 1023px) {
  --container-padding: 24px;
  --sidebar-width: 200px;
}

/* 桌面 */
@media (min-width: 1024px) {
  --container-padding: 32px;
  --sidebar-width: 240px;
}

/* 大屏 */
@media (min-width: 1440px) {
  --container-padding: 48px;
  --sidebar-width: 280px;
}
```

---

## ♿ 无障碍规范

### 1. 键盘导航
- Tab 键顺序合理
- Enter/Space 触发按钮
- Esc 关闭对话框

### 2. 屏幕阅读器
- 所有图片有 alt 文本
- 表单字段有 label
- 错误消息关联到字段

### 3. 对比度
- 文字与背景对比度 >= 4.5:1
- 重要元素对比度 >= 3:1

---

## 📝 命名规范

### CSS 类名
```css
/* BEM 命名法 */
.block {}
.block__element {}
.block--modifier {}

/* 示例 */
.data-card {}
.data-card__header {}
.data-card__body {}
.data-card--loading {}
```

### 组件命名
```
PascalCase: DataCard, SyncButton, QualityMeter
kebab-case: data-card, sync-button, quality-meter
```

---

## 🎯 最佳实践

1. **保持一致性**: 相同功能的组件使用相同样式
2. **提供反馈**: 用户操作后立即给予视觉反馈
3. **减少认知负担**: 一次只展示必要信息
4. **优先移动端**: 先设计移动端，再扩展到桌面端
5. **性能优化**: 懒加载、虚拟滚动、图片压缩
6. **国际化准备**: 预留多语言支持空间

---

## 🔗 参考资源

- [Element Plus Design Guidelines](https://element-plus.org/en-US/guide/design.html)
- [Ant Design Specification](https://ant.design/docs/spec/introduce)
- [Material Design](https://material.io/design)
- [Apple Human Interface Guidelines](https://developer.apple.com/design/human-interface-guidelines)
