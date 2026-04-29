import "./resetPassword.css"
import logo from "../../assets/logo.png"
import { SyntheticEvent, useState } from "react"
import { Mail, ArrowLeft } from "lucide-react"
import { Link } from "react-router-dom"
import { requestPasswordReset } from "../../services/api"

export default function ResetPassword() {
  const [email, setEmail] = useState("")
  const [message, setMessage] = useState("")
  const [error, setError] = useState("")
  const [loading, setLoading] = useState(false)

  const handleResetPassword = async (e: SyntheticEvent) => {
    e.preventDefault()
    setError("")
    setMessage("")
    if (!email.trim()) { setError("Informe seu e-mail."); return }
    setLoading(true)
    try {
      await requestPasswordReset({ email: email.trim() })
      setMessage("Instruções enviadas! Verifique sua caixa de entrada.")
    } catch (err) {
      setError(err instanceof Error ? err.message : "Erro ao enviar instruções.")
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="reset-password-page">
      <div className="reset-password-card">

        <div className="reset-password-header">
          <img src={logo} className="reset-password-logo" alt="SmartScout" />
          <h2 className="reset-password-title">Redefinir Senha</h2>
          <p className="reset-password-subtitle">
            Insira o e-mail associado à sua conta e enviaremos instruções para redefinir sua senha.
          </p>
        </div>

        <form className="reset-password-form" onSubmit={handleResetPassword}>

          <div className="input-group">
            <label className="input-label">E-mail</label>
            <div className="input-wrapper">
              <span className="input-icon"><Mail size={16} /></span>
              <input type="email" className="input-base with-icon"
                placeholder="seu-email@email.com" value={email}
                onChange={(e) => setEmail(e.target.value)}
                disabled={!!message} />
            </div>
          </div>

          {message && <p className="success-message">{message}</p>}
          {error   && <p className="reset-error">{error}</p>}

          <button type="submit" className="btn btn-primary reset-password-button"
            disabled={loading || !!message}>
            {loading ? "Enviando..." : message ? "Enviado!" : "Prosseguir"}
          </button>

          <p className="back-to-login">
            <Link to="/login" className="login-link">
              <ArrowLeft size={14} />
              Voltar para o Login
            </Link>
          </p>

        </form>
      </div>
    </div>
  )
}