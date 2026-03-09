import Login from './pages/Login/Login';
import SignUp from './pages/SignUp/SignUp';
import { BrowserRouter, Routes, Route } from 'react-router-dom';
import { MainLayout } from "./layouts/MainLayout";
import InputPage from "./pages/input/input";
import ProcessingClipsPage from './pages/processing-clips/processingClips';

export default function App() {

  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<MainLayout />}>
          <Route index element={<InputPage></InputPage>} />
        </Route>
        <Route path="/login">
          <Route index element={<Login/>} />
        </Route>
        <Route path="/signup">
          <Route index element={<SignUp/>} />
        </Route>
        <Route path='/processing-clips' element={<MainLayout/>}>
          <Route index element={<ProcessingClipsPage/>} />
        </Route>
      </Routes>
    </BrowserRouter>
    

      /*Prova de conceito
      <div className="bg-gradient" style={{ padding: 24, fontFamily: "system-ui" }}>
      <h2>FastAPI → React (SSE)</h2>

      <div style={{ display: "flex", gap: 8 }}>
        <button className="btn btn-secondary" onClick={connect} disabled={connected}>
          Conectar
        </button>
        <button onClick={disconnect} disabled={!connected}>
          Desconectar
        </button>
      </div>

      <p style={{ marginTop: 16 }}>
        Status: <b>{connected ? "conectado" : "desconectado"}</b>
      </p>

      <div>
        <b>Números:</b> {numbers.join(", ")}
      </div>

      <div className="input-group">
        <label className="input-label">E-mail</label>
        <div className="input-wrapper">
          <span className="input-icon">✉️</span> 
          <input 
            type="email" 
            className="input-base with-icon" 
            placeholder="seu-email@email.com" 
          />
        </div>
      </div>

      <div className="input-group">
        <label className="input-label">Sobrenome</label>
        <div className="input-wrapper">
          <input 
            type="text" 
            className="input-base" 
            placeholder="********" 
          />
        </div>
      </div>
    </div>*/
  );
}