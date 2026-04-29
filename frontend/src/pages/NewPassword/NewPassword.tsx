import { SyntheticEvent, useState } from "react"
import { useSearchParams, useNavigate } from "react-router-dom"
import { Lock, LockKeyhole, ArrowLeft } from "lucide-react"
import { Link } from "react-router-dom"
import logo from "../../assets/logo.png"
import "../resetPassword/resetPassword.css"

export default function NewPassword() {
  const [searchParams] = useSearchParams()
  const navigate = useNavigate()
  const token = searchParams.get("token") ?? ""

  const [password, setPassword] = useState("")
  const [confirm, setConfirm] = useState("")
  const [error, setError] = useState("")
  const [loading, setLoading] = useState(false)

  const handleSubmit = async (e: SyntheticEvent) => {
    e.preventDefault()
    setError("")

    if (password.length < 8) { setError("A senha deve ter no mínimo 8 caracteres."); return }
    if (password !== confirm) { setError("As senhas não coincidem."); return }
    if (!token) { setError("Token inválido. Solicite um novo link."); return }

    setLoading(true)
    try {
      const res = await fetch(`${import.meta.env.VITE_API_PATH}/auth/reset-password`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ token, new_password: password }),
      })

      if (!res.ok) {
        const data = await res.json().catch(() => ({}))
        throw new Error(data.detail ?? "Erro ao redefinir senha.")
      }

      navigate("/login", { replace: true, state: { passwordReset: true } })
    } catch (err) {
      setError(err instanceof Error ? err.message : "Erro ao redefinir senha.")
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="reset-password-page">
      <div className="reset-password-card">

        <div className="reset-password-header">
          <img src={logo} className="reset-password-logo" alt="SmartScout" />
          <h2 className="reset-password-title">Nova Senha</h2>
          <p className="reset-password-subtitle">
            Escolha uma nova senha para a sua conta.
          </p>
        </div>

        <form className="reset-password-form" onSubmit={handleSubmit}>

          <div className="input-group">
            <label className="input-label">Nova Senha</label>
            <div className="input-wrapper">
              <span className="input-icon"><Lock size={16} /></span>
              <input type="password" className="input-base with-icon"
                placeholder="Mínimo 8 caracteres" value={password}
                onChange={(e) => setPassword(e.target.value)} />
            </div>
          </div>

          <div className="input-group">
            <label className="input-label">Confirmar Senha</label>
            <div className="input-wrapper">
              <span className="input-icon"><LockKeyhole size={16} /></span>
              <input type="password" className="input-base with-icon"
                placeholder="Repita a senha" value={confirm}
                onChange={(e) => setConfirm(e.target.value)} />
            </div>
          </div>

          {error && <p className="reset-error">{error}</p>}

          <button type="submit" className="btn btn-primary reset-password-button"
            disabled={loading}>
            {loading ? "Salvando..." : "Salvar nova senha"}
          </button>

          <p className="back-to-login">
            <Link to="/login" className="login-link">
              <ArrowLeft size={14} /> Voltar para o Login
            </Link>
          </p>

        </form>
      </div>
    </div>
  )
}