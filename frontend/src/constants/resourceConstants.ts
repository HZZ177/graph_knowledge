// 资源库页面共享常量

export const STEP_TYPE_LABELS: Record<string, string> = {
  inner: '内部步骤',
  outer: '外部步骤',
  '': '其他',
}

export const IMPL_TYPE_LABELS: Record<string, string> = {
  api: '接口',
  function: '内部方法',
  job: '定时任务',
  '': '其他',
}

export const DATA_TYPE_LABELS: Record<string, string> = {
  table: '库表',
  redis: 'Redis',
  '': '其他',
}
