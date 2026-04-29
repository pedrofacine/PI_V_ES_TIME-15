import "./Login.css"
import logo from "../../assets/logo.png"
import { SyntheticEvent, useState } from "react"
import { Lock, Mail } from "lucide-react"
import { Link, useNavigate, useLocation } from "react-router-dom"
import { login, saveSession } from "../../services/api"

export default function Login() {
  const navigate = useNavigate()
  const location = useLocation()
  const justRegistered = location.state?.registered === true
  const [email, setEmail] = useState("")
  const [password, setPassword] = useState("")
  const [error, setError] = useState("")
  const [loading, setLoading] = useState(false)

  const handleLogin = async (e: SyntheticEvent) => {
    e.preventDefault()
    if (!email || !password) { setError("Preencha e-mail e senha."); return }
    setError("")
    setLoading(true)
    try {
      const data = await login({ email: email.trim(), password })
      saveSession(data)
      navigate("/", { replace: true })
    } catch (err) {
      setError(err instanceof Error ? err.message : "Erro ao fazer login.")
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="login-page">
      <div className="login-card">

        <div className="login-header">
          <img src={logo} className="login-logo" alt="SmartScout" />
          <h2 className="login-title">Bem-vindo de volta</h2>
          <p className="login-subtitle">Acesse sua conta SmartScout</p>
        </div>

        {justRegistered && (
          <p className="login-success">Conta criada com sucesso! Faça login para continuar.</p>
        )}

        <form className="login-form" onSubmit={handleLogin}>

          <div className="input-group">
            <label className="input-label">E-mail</label>
            <div className="input-wrapper">
              <span className="input-icon"><Mail size={16} /></span>
              <input type="email" className="input-base with-icon"
                placeholder="seu-email@email.com" value={email}
                onChange={(e) => setEmail(e.target.value)} />
            </div>
          </div>

          <div className="input-group">
            <label className="input-label">Senha</label>
            <div className="input-wrapper">
              <span className="input-icon"><Lock size={16} /></span>
              <input type="password" className="input-base with-icon"
                placeholder="Digite sua senha" value={password}
                onChange={(e) => setPassword(e.target.value)} />
            </div>
          </div>

          <div className="forgot-password">
            <Link to="/reset-password" className="login-link">Esqueceu a senha?</Link>
          </div>

          {error && <p className="login-error">{error}</p>}

          <button type="submit" className="btn btn-primary login-button" disabled={loading}>
            {loading ? "Entrando..." : "Entrar"}
          </button>

          <div className="login-divider"><span>ou</span></div>

          <p className="create-account">
            Ainda não possui conta?{" "}
            <Link to="/signup" className="login-link">Criar conta</Link>
          </p>

        </form>
      </div>
    </div>
  )
}