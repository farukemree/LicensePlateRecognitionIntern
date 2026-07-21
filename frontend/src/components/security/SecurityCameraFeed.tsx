type SecurityCameraFeedProps = {
  title: string
  active?: boolean
}

function SecurityCameraFeed({
  title,
  active = false,
}: SecurityCameraFeedProps) {
  return (
    <section
      className={`dashboard-panel camera-panel${
        active ? ' camera-panel-active' : ''
      }`}
    >
      <header>{title}</header>
      <div className="camera-feed" />
    </section>
  )
}

export default SecurityCameraFeed