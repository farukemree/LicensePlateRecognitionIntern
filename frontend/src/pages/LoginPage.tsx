import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import VisibilityOffOutlinedIcon from '@mui/icons-material/VisibilityOffOutlined'
import VisibilityOutlinedIcon from '@mui/icons-material/VisibilityOutlined'
import dhlLogo from '../assets/dhl-logo.png'

function LoginPage() {
  const [showPassword, setShowPassword] = useState(false)
  const navigate = useNavigate()

  return (
    <main className="login-page" aria-label="Plaka Tanıma Sistemi giriş sayfası">
      <header className="topbar">
        <div className="brand">
          <img className="dhl-logo" src={dhlLogo} alt="DHL" />
          <h1>Plaka Tanıma Sistemi</h1>
        </div>

        <nav className="language-switcher" aria-label="Dil seçimi">
          <a href="#tr" aria-current="page">
            TR
          </a>
          <span>|</span>
          <a href="#en">EN</a>
        </nav>
      </header>

      <div className="login-area">
        <form
          className="login-card"
          onSubmit={(event) => {
            event.preventDefault()
            navigate('/dashboard')
          }}
        >
          <div className="card-heading">
            <h2>Giriş Yap</h2>
            <p>Lütfen kullanıcı bilgileriniz ile giriş yapınız.</p>
          </div>

          <label className="field">
            <span>Kullanıcı Adı</span>
            <input type="text" name="username" autoComplete="username" />
          </label>

          <label className="field">
            <span>Şifre</span>
            <div className="password-control">
              <input
                type={showPassword ? 'text' : 'password'}
                name="password"
                autoComplete="current-password"
              />
              <button
                type="button"
                className="password-toggle"
                aria-label={showPassword ? 'Şifreyi gizle' : 'Şifreyi göster'}
                aria-pressed={showPassword}
                onClick={() => setShowPassword((current) => !current)}
              >
                {showPassword ? <VisibilityOffOutlinedIcon /> : <VisibilityOutlinedIcon />}
              </button>
            </div>
          </label>

          <label className="remember">
            <input type="checkbox" name="remember" />
            <span>Beni Hatırla</span>
          </label>

          <button className="login-submit" type="submit">
            Giriş Yap
          </button>
        </form>
      </div>
    </main>
  )
}

export default LoginPage
