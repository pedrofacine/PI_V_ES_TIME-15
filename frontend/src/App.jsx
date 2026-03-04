import { useRef, useState } from "react";

export default function App() {
  const [numbers, setNumbers] = useState([]);
  const [connected, setConnected] = useState(false);
  const esRef = useRef(null);

  function connect() {
    if (esRef.current) return;

    setNumbers([]);
    setConnected(true);

    const es = new EventSource("http://127.0.0.1:8000/stream");
    esRef.current = es;

    es.onmessage = (e) => {
      setNumbers((prev) => [...prev, Number(e.data)]);
    };

    es.addEventListener("done", () => {
      es.close();
      esRef.current = null;
      setConnected(false);
    });

    es.onerror = () => {
      es.close();
      esRef.current = null;
      setConnected(false);
    };
  }

  function disconnect() {
    if (esRef.current) {
      esRef.current.close();
      esRef.current = null;
    }
    setConnected(false);
  }

  return (
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
    </div>
  );
}