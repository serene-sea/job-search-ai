/// <reference types="vite/client" />

declare module '*.vue' {
  import type { DefineComponent } from 'vue'
  const component: DefineComponent<object, object, unknown>
  export default component
}  // 声明 .vue 文件的模块类型，避免 TypeScript 报错。如果没有这个声明，TypeScript 会认为 .vue 文件不是有效的模块，从而导致编译错误。
