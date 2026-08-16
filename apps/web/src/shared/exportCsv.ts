type CsvValue = string | number | boolean | null | undefined

function escapeCell(value: CsvValue): string {
  const text = value === null || value === undefined ? '' : String(value)
  if (/["",\n\r]/.test(text)) {
    return `"${text.replaceAll('"', '""')}"`
  }
  return text
}

export function downloadCsv(
  filename: string,
  header: string[],
  rows: CsvValue[][],
  meta: Record<string, string>,
): void {
  const lines = [
    '# CityPulse 导出',
    ...Object.entries(meta).map(([key, value]) => `# ${key}: ${value}`),
    '# 真实性声明：演示工作区数据为方法演示样本，不构成真实预测。',
    header.map(escapeCell).join(','),
    ...rows.map((row) => row.map(escapeCell).join(',')),
  ]
  const blob = new Blob([`\ufeff${lines.join('\n')}\n`], {
    type: 'text/csv;charset=utf-8',
  })
  const url = URL.createObjectURL(blob)
  const anchor = document.createElement('a')
  anchor.href = url
  anchor.download = filename
  document.body.appendChild(anchor)
  anchor.click()
  anchor.remove()
  URL.revokeObjectURL(url)
}
