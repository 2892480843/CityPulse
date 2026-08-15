export function PlaceholderPage({ title, stage }: { title: string; stage: string }) {
  return (
    <section className="page">
      <p className="eyebrow">CITYPULSE / ROADMAP</p>
      <h1>{title}</h1>
      <p className="muted">
        {title}模块将在{stage}交付：数据快照、评分版本与任务中心就绪后，此处接入真实运行结果，
        不展示任何模拟数值。
      </p>
    </section>
  )
}
