type Props = {
  title: string
  message: string
}

function SecuritySectionPlaceholder({
  title,
  message,
}: Props) {
  return (
    <article className="manager-section-card">
      <h2>{title}</h2>

      <div className="manager-empty-state">
        {message}
      </div>
    </article>
  )
}

export default SecuritySectionPlaceholder